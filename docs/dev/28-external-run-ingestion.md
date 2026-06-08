# 28 — External-Run Ingestion

How an **app-started clean** — a job the integration did **not** dispatch — is
detected, captured, segmented into rooms, **re-segmented** by the user (room
count or per-boundary split/merge), reviewed, and folded into the same learned
baselines as an internal run.

This is the only path in the system that learns from a run it didn't start. It
exists because most households still kick off cleans from the Eufy app, the
voice assistant, or the robot's button, and every one of those runs is real
data the timing model would otherwise never see.

> **Prerequisite reading:** [10-learning-system](10-learning-system.md) (the
> counter-plateau segmenter + the per-room area/timing buckets this feeds) and
> [06-job-lifecycle](06-job-lifecycle.md) (the internal lifecycle this mirrors).

---

## 1. Why external is different

An internal run is fully known: we built the queue, dispatched the rooms, and
the device reports `active_cleaning_target`. An external run hides almost all of
that.

| | Internal (we dispatched) | External (app-started) |
|---|---|---|
| Started by | our `room_clean` dispatch | the Eufy app / voice / button |
| `active_cleaning_target` | populated | **unavailable** (hidden for app jobs) |
| Room identity | segment K → queue room K (certain) | **unknown** → human-confirmed |
| Per-room settings | we sent them | **recovered from device state** |
| Edge-mop | we sent it | **not recoverable** → user supplies |

So external ingestion is built around two facts: the device-hidden bits
(**identity**, **edge-mop**) are filled by a **human in a review card**, and
everything else is recovered from the counters + the live setting selects.

The detection key is deliberately simple and robust: **if the vacuum is cleaning
and there is no dispatched `active_job`, it's external.** Internal starts are
blocked while any run is in progress (a start-blocker in the job monitor), so the
two can never be confused.

---

## 2. End-to-end flow

```
app starts a clean
      │
      ▼
lifecycle listener: vacuum→cleaning + no dispatched job   ── detection (§3)
      │
      ▼
active_jobs slot, status="external"  (counters + setting selects buffer in)  ── capture (§3)
      │
      ▼  (robot returns home: vacuum→docked/idle)
finalize → find_candidates (every blip) + select_active (confident default)
           + build_segments + recover per-segment {area,time,passes,settings}
           + EMBED the raw samples + candidate pool                       ── pending record (§4,§5)
      │
      ▼
external_jobs/job_<detection_ts>.json   (status="pending", schema v2)
      │   + EVENT_EXTERNAL_RUN_PENDING fired
      ▼
"External Jobs" review card → set room count / split-here / merge-up   ── re-segment (§5a)
      │   resegment service → re-run the segmenter on the FROZEN samples → rewrite in place
      ▼
   (loop until the room count looks right) → confirm room per segment + edge-mop   ── card (§7)
      │
      ▼
confirm service → tier-1 identity gate → build a normal completed-job record   ── gate + graduate (§6)
      │
      ▼
jobs/ext-<id>.json (origin="external", used_for_learning) → rebuild → learned room_stats
```

Nothing between detection and confirm touches the learned baselines. The pending
record is an **inbox**; the raw samples ride along inside it so the run can be
**re-segmented** to any room count or boundary set without re-capturing (§5a),
and only the confirm service graduates a run into learning.

---

## 3. Detection + capture

**Detection** lives in the lifecycle listener
([`listeners/lifecycle.py`](../../custom_components/eufy_vacuum/listeners/lifecycle.py),
`_process`), which already fires on every watched-entity change. For each vacuum
it calls `manager.maybe_handle_external_run(vacuum_entity_id)` *before* the
per-map internal loop (which only handles `status in {started, paused}`).

[`core/manager.py`](../../custom_components/eufy_vacuum/core/manager.py)
`maybe_handle_external_run`:

- Scan all maps: if any slot is `started`/`paused`, **internal owns the run** →
  return. If a slot is already `external`, remember its map.
- Resolve the **active map** from the adapter's `active_map` entity
  (`_resolve_active_map_id` — brand-agnostic; reads the entity the adapter
  declares, not a Eufy-specific call).
- **Start:** vacuum state `cleaning` + no external slot → `start_external_capture`
  opens a slot with `status="external"` + `started_at`.
- **End:** an external slot exists + vacuum state `docked`/`idle` → finalize
  (§4) and clear the slot. External runs hide `active_cleaning_target`, so the
  end is keyed on the **vacuum entity returning home**, not the completion
  signals the internal path uses.

**Capture** reuses the existing metrics chokepoint. The slot is in-flight
(`started_at` set, no `ended_at`), so
[`jobs/active_job.py`](../../custom_components/eufy_vacuum/jobs/active_job.py)
`record_counter_sample` already buffers `counter_samples` for it. For external
slots it **also** snapshots the per-room setting selects:

- `_snapshot_settings_selects(vacuum)` reads the adapter's `settings_selects`
  block (§9) — a dict of `{canonical_key: {entity_id, value_map}}` — from the
  live HA state, applying `value_map` (e.g. `"Vacuum and mop" → "vacuum_mop"`)
  where present, raw otherwise.
- The result is appended to `settings_samples` **only when it changes** (one
  entry per flip), giving a compact settings-flip timeline alongside the 30 s
  counter clock.

`settings_samples` is empty for internal jobs — we dispatched their settings and
never read them back.

---

## 4. The pending record (schema v2)

On finalize, `_finalize_external_run` runs the captured stream through
[`learning/external_ingest.py`](../../custom_components/eufy_vacuum/learning/external_ingest.py)
`build_pending_record` (pure) and writes the result atomically to
`learning/<slug>/external_jobs/job_<detection_ts>.json` (peer to `jobs/`).

The v2 record is **self-contained**: it embeds the raw `counter_samples` /
`settings_samples` and the **full candidate pool** so the run can be re-segmented
server-side (§5a) at any room count or boundary set, with no re-capture. The
samples are bounded at finalize by `_MAX_COUNTER_SAMPLES` (= 2000, in
`jobs/active_job.py`), so the on-disk record stays ~100–200 KB worst case. They
are **stripped** (`strip_samples`) before the record is served to the card — the
card never needs them; re-segmentation reads them on the server.

```jsonc
{
  "schema_version": 2,
  "status": "pending",
  "origin": "external",
  "detection_ts": "...",
  "map_id": "6",
  "segment_count": 2,
  "suggested_room_count": 2,            // = the confident-only segment count (§5)
  "gap_transit_s": 60.0,               // the transit-band threshold used, from the resolved engine tuning (re-segment reads it back)
  "candidates": [                      // EVERY detected blip — the split-here menu
    { "id": 7, "position": 7, "gap_s": 95.0, "area_after_m2": 0.0,
      "kind": "wash_plateau", "strength": 4000.16, "confident": true, "t": "...Z" },
    { "id": 14, "position": 14, "gap_s": 72.0, "area_after_m2": 0.3,
      "kind": "transit", "strength": 2000.12, "confident": false, "t": "...Z" },
    ...
  ],
  "active_boundaries": [ 7 ],          // candidate ids currently producing `segments`
  "counter_samples": [ ... ],          // STRIPPED on serve; kept on disk for re-segment
  "settings_samples": [ ... ],         // STRIPPED on serve
  "segments": [
    {
      "order": 0,
      "boundary_id": null,              // the active candidate id that STARTED this segment (null for order 0)
      "t_start": "...", "t_end": "...",
      "area_m2": 6.0,                    // unique m² = true room size
      "time_wall_s": 210, "time_active_s": 240,
      "pass_count": 1,                   // area-plateau pattern
      "settings": { "clean_mode": "vacuum_mop", "fan_speed": "Turbo", ... },
      "boundary": "job_start",          // the kind of cut that opened it (job_start / wash_plateau / transit / area_jump / weak)
      "confident_boundary": null,        // null for order 0; bool for K>0
      "shortlist": [ { "room_id", "slug", "name", "is_carpet", "learned_area_m2", "settings_score", "score" }, ... ]
    },
    ...
  ]
}
```

`external_jobs/` is purely the pending inbox — see §5a for re-segmentation and §6
for what happens on accept. (v1 records — written before this change, no embedded
samples — still load and confirm; they simply cannot be re-segmented and degrade
to the legacy merge-only review, see §5a.)

---

## 5. Segmentation, the suggested count, and the shortlist

**Segmentation is now a three-stage pipeline** whose brand-specific stages live
behind the **pluggable job-segmenter engine**
([`learning/job_segmenter_engines.py`](../../custom_components/eufy_vacuum/learning/job_segmenter_engines.py))
— the **counter/run** segmenter, not the map segmenter
([`mapping/segmenter_engines.py`](../../custom_components/eufy_vacuum/mapping/segmenter_engines.py),
`eufy_cv_v1`, unchanged). The Eufy engine (`eufy_counter_v1`) delegates **verbatim**
to the primitives in
[`counter_segmentation.py`](../../custom_components/eufy_vacuum/counter_segmentation.py)
([10-learning-system](10-learning-system.md) §segmenter), so the same frozen
samples can be re-cut at any granularity (this is what makes §5a exact):

```
engine.find_candidates(samples)     -> EVERY blip, kinded + ranked  (no discards)   [engine]
select_active(candidates, ...)      -> pick the active set (count / explicit / default)  [framework]
engine.build_segments(samples, …)   -> the per-room segment dicts for THAT set      [engine]
```

`find_candidates` / `build_segments` are the **brand-specific** stages, reached
through the engine; `select_active` is pure ranking/filtering over the candidate
*shape*, so it stays a **direct framework import**
(`counter_segmentation.select_active`) and is shared across brands. The engine is
resolved per-vacuum by `_resolve_engine_tuning(vacuum_entity_id)` (new optional
param on `build_pending_record` / `resegment_pending_record`; absent → the Eufy
`eufy_counter_v1` engine + its `DEFAULT_TUNING`, byte-identical, and what the unit
tests hit since they pass no vacuum id). The gap/area/cadence thresholds — including
the persisted `gap_transit_s` — now come from that resolved engine tuning (the
adapter's `job_segmenter.tuning` overlaid on `DEFAULT_TUNING`), not from a direct
`counter_segmentation` module constant. `external_ingest.py` no longer imports
`segment_counters` (only `select_active`).

`build_pending_record` runs the pipeline **blind** (no dispatched queue to
constrain it):

1. `engine.find_candidates(counter_samples)` returns **every** `cleaning_time` blip
   (a gap > `gap_delayed_s` ≈ 35 s) as a `JobBoundaryCandidate` `{id, position,
   gap_s, area_after_m2, kind, strength, confident, t}` dict — `id == position` (the
   increment-tick index) is a stable handle the card toggles by. The **kinds** are:
   - **`wash_plateau`** (gap > `gap_plateau_s` ≈ 90 s) — a minutes-long mop wash
     (ByRoom) or long transit. Unambiguous.
   - **`transit`** (`gap_transit_s` ≈ 60 s < gap ≤ 90 s **and** area stays flat) —
     a ~60–90 s inter-room hop that covered no new floor yet. **NEW** — this is the
     real transition the old filter discarded (it required an area jump), which
     left under-splits unrecoverable.
   - **`area_jump`** (`cleaning_area` rises ≥ `area_jump_m2` ≈ 2 m² in the stretch
     *after* the blip, read forward to the next blip — the area lag) — new floor.
   - **`weak`** (a short delayed step, flat area) — most likely a multi-pass turn
     (re-covering the same room); not a boundary unless the user splits it.
2. `_mark_candidate_confidence` then upgrades `confident` on each candidate (see
   "Suggested room count" below).
3. `select_active(candidates, default="confident")` (framework) keeps **only the
   confident cuts** for the default view; `engine.build_segments` materializes the
   per-room dicts.

> **The default segmentation is the confident-only view** — it reproduces the
> pre-v2 segmentation exactly (`segment_counters` is now a byte-identical
> back-compat wrapper over the same three stages: `gap_transit_s=inf` collapses
> the transit band and `kinds={wash_plateau, area_jump}` drops the rest, so its
> internal-queue and test callers are unchanged). The extra `transit`/`weak`/
> uncertain cuts are **kept in the record** as inactive candidates and surface in
> the card as **split-here** markers (§7) — they only become active when the user
> re-segments (§5a). Blind, the default may still over- or under-split; that's
> resolved by the human.

**Per-segment recovery** (`_enrich_segments`, shared by finalize *and*
re-segment so the two never drift):

| Field | Source | Note |
|---|---|---|
| `area_m2` | `cleaning_area` Δ (`area_delta_m2`) | true unique size, path/pass-**invariant** |
| `time_wall_s` | wall-clock span | path/pass-**inflated** (not a size signal) |
| `pass_count` | area-plateau pattern | `_estimate_passes`: total / span-until-area-stopped-rising |
| `settings` | the captured selects active during the segment | clean_mode is canonical; others raw |
| `boundary` / `boundary_id` | the active candidate that opened the segment | `boundary_id` survives the trailing-segment drop so re-segment can recover `active_boundaries` |

`_enrich_segments` also drops only **trailing** sub-room stretches (an
end-of-run station clean / re-pass under `_MIN_ROOM_AREA_M2` ≈ 0.5 m²) and
re-indexes the kept segments `0..N-1`; a leading/middle ~0 m² segment is **kept**
(the area lag can land a short first room's m² on the next tick).

**Suggested room count.** This is the one place the settings timeline does more
than fill the per-segment `settings` — it disambiguates the boundaries by
**upgrading `confident`** (`_mark_candidate_confidence`):

- A cut is **confident** when it is a **long wash plateau** OR the per-room
  settings **changed across it** (a flip — the app set the next room's settings).
  Confidence is computed the pre-v2 way (over the wash/area_jump finest, comparing
  consecutive segment-end settings) so the default view matches the old count.
- A short delayed step with **flat settings** is **uncertain** (`transit`/`weak`/
  flat `area_jump`) — it could be an edge→fill turn *inside* a room or a
  same-settings adjacent room. The counters alone can't tell them apart.
- `suggested_room_count` = the **confident-only segment count** (= `segment_count`
  on a fresh record). Uncertain/transit/weak cuts stay in `candidates` with
  `confident: false` and surface as toggleable split-here markers, **default off**
  (merged).

> Settings-flip is a **suggestion-layer corroborator only**. The core segmenter
> stays counters-only / settings-independent (`find_candidates` sets the geometric
> base `confident = (kind == "wash_plateau")`; the ingest layer floats a
> settings-corroborated cut up), because internal runs resolve the count from the
> dispatched queue, never from flips.

**The shortlist** (`_rank_shortlist`) ranks the active map's rooms per segment,
**settings-first** (since `cleaning_area` is path/pass-cumulative and a weak
identity signal):

- **settings-match** (primary sort key) — a weighted score over the segment's
  recovered selects vs the room's config: `clean_mode` (4.0), `clean_passes`
  (3.0), `clean_intensity` (2.0), `fan_speed` (1.0), `water_level` (1.0).
- **area-match** (tiebreak among settings-equal rooms) — `-|segment_area −
  room.avg_area_m2|` from the learned `room_baselines` (cold rooms with no
  baseline score last but stay selectable).
- **carpet filter** — when the segment was mopped (`clean_mode ∈ {mop,
  vacuum_mop}`), rooms whose `floor_type` starts with `carpet` are dropped (you
  can't mop carpet; the card's "all rooms" override can still reach them).
- Top-3 baked into the record (each with `settings_score` + area `score`); the
  card's "all rooms" select is the override tail.

*(Deferred: a sequence/habitual-order prior. Settings + area is the shipped
ranker.)*

---

## 5a. Re-segmentation (server-side, from the frozen samples)

Because the v2 record carries its own raw samples + candidate pool, the user can
re-cut the run **without re-capturing it**. The card calls
`eufy_vacuum.resegment_external_run` (§8); the work runs on the executor in
`manager.resegment_external_run`, which loads the record (incl. samples), delegates
to `external_ingest.resegment_pending_record`, **rewrites the file in place**, and
returns the new sample-stripped record + a selection `meta`.

`resegment_pending_record` resolves the same per-vacuum engine
(`_resolve_engine_tuning`, absent → Eufy fallback) and re-runs
`engine.find_candidates` (over the resolved tuning, but pinned to the record's
stored `gap_transit_s` so the pool reproduces exactly) + `_mark_candidate_confidence`
over the **frozen** samples, then picks the active set by exactly one mode (via the
framework `select_active`), then `engine.build_segments` + the shared
`_enrich_segments`:

| Mode | Input | `select_active` call | `meta` |
|---|---|---|---|
| **count** | `expected_rooms` (≥ 1) | strongest `N−1` by `(confident, strength)` | `{mode:"count", requested, available, capped, capped_at}` + a `message` when capped |
| **explicit** | `active_boundaries: [id…]` | exactly those candidate ids | `{mode:"explicit"}` |
| **reset** | neither | `default="confident"` | `{mode:"reset"}` |

The count mode is **capped to the detectable pool** (`available = len(candidates)
+ 1`): asking for more rooms than there are boundaries clamps to `capped_at` and
reports `capped: true` + a "Only N room(s) detectable from this run." message —
it never invents a cut. Recomputing the pool + confidence from the frozen samples
is what keeps the result internally consistent (a client-side regroup of the
served segments could not re-derive area attribution across a wash plateau).

**Guardrails:**

- A missing record, a **v1 record (no samples)**, or a selection that yields no
  segment returns an error **without** touching the file — a usable record is
  never blanked (`not_resegmentable` / `empty_segmentation`).
- The returned record preserves the full `candidates` list + samples on disk and
  re-computes `active_boundaries` from the kept segments' `boundary_id`.
- `get_external_pending_runs` flags each served record `resegmentable =
  bool(counter_samples)` *before* stripping the samples, so the card knows whether
  to show the re-segment controls (v2) or fall back to legacy merge-only (v1).

---

## 6. Confirm: gate + graduate

The card calls `eufy_vacuum.confirm_external_run` (§8) with per-room
**assignments**. Each assignment maps one or more blind `segment_orders` (merged
uncertain cuts) to a room, plus `edge_mopping`, an `override` flag, and optional
setting `overrides`.

[`external_ingest.py`](../../custom_components/eufy_vacuum/learning/external_ingest.py)
`build_graduated_job` turns confirmed assignments into a **normal completed-job
record** — no new learning path. Per assignment:

1. **Tier-1 identity gate** (`gate_segment_identity`): the merged segment area vs
   the confirmed room's learned band. Deliberately **wide** — only a *clear*
   mismatch blocks (`> max(3·stddev, 0.5·avg, 3 m²)`), because the human already
   asserted the room. A cold room (no band) is accepted as a **bootstrap**
   sample; `override=true` forces a flagged mismatch through.
2. **Atomic:** if *any* assignment is blocked without override, the whole confirm
   returns `{ok: false, blocked: [...]}` and graduates nothing. The card shows
   the warnings → re-pick or "keep anyway".
3. On success, emit a `room_timings` entry + a `job_profile.rooms` entry per room
   (settings = override → recovered → room config; passes clamped to 1/2;
   `is_carpet` from the room's `floor_type`; `edge_mopping` from the user).

The record sets `record_type="completed_job"`, `outcome.status="completed"`,
`outcome.used_for_learning=True`, `origin="external"`, and crucially
`job.transit_capture_valid=True` with `job.transitions=[]` — that flag is what
gates the rebuilder's use of `room_timings[].area_m2`, so it must be true for the
per-room area/timing to ingest; external runs simply emit no transit edges.

It also sets `outcome.sanity_passed=True` + `outcome.sanity_flags=[]`
**explicitly** — a run only graduates *after* passing the tier-1 identity gate
(with a valid duration + room set), so it is sane by construction. Setting the key
rather than leaving it absent is load-bearing: the history snapshot
([`learning/manager.py`](../../custom_components/eufy_vacuum/learning/manager.py))
now reads `item.get('sanity_passed') is False` (was `not item.get('sanity_passed',
True)`), so a missing/`None` value no longer mislabels the run. The jobs index had
stored the key as `None`, which made the `.get(..., True)` default never fire and
tagged **every** graduated external run "This run failed the backend sanity
checks" — that is the bug this fixes.

> **Tier-2 is free.** The rebuilder's W3 area-quality gate
> ([10-learning-system](10-learning-system.md) §area gate) runs over all samples
> at rebuild time, so a confirmed-but-partial clean (area below the room's band)
> is automatically excluded from the **timing** stats. Tier-1 (identity) is the
> only check the confirm path adds.

`manager.confirm_external_run` (sync, on the executor) then: writes
`jobs/ext-<pending_id>.json`, deletes the pending file, and calls
`rebuild_learning`. The rebuilder ingests the graduated record exactly like an
internal multi-room job — verified end-to-end in
`tests/unit/test_learning_external_ingest.py::test_graduated_record_ingests_into_room_stats`.

---

## 7. The review card

The Lovelace card surfaces all of this as an **"External Jobs" subtab** of the
Learning Review view. Source under `src/` (see
[19-card-architecture](19-card-architecture.md) for the module pattern):

- `state/external-jobs.js` — subtab selection, the pending list, and the wizard.
  In v2 the **server owns segmentation**, so the wizard state mirrors the served
  record: `candidates` (the full boundary menu), `activeBoundaries` (the cuts
  currently producing `segments`), and `resegmentable`. `setExternalRoomCount` and
  `toggleExternalBoundary` drive re-segmentation; the segments come back from the
  server rather than being derived client-side.
- `actions/external-jobs.js` — `fetchExternalPendingRuns`, `confirmExternalRun`,
  `discardExternalRun`, and **`resegmentExternalRun`** (→
  `eufy_vacuum.resegment_external_run`, sends either a target room count *or* an
  explicit `active_boundaries`).
- `renderers/external-jobs.js` — the subtab list + the two-step wizard modal.
- `bindings/external-jobs.js` — subtab events + modal-host events + the submit
  flow; the re-segment controls call `resegmentExternalRun` (guarded on
  `resegmentable`) and refresh the wizard from the returned record.
- `styles/external-jobs.js` — subtab/list (shadow root) + wizard (modal host),
  **canonical foundation tokens only** (no new tokens). Includes a dropdown
  readability fix: `.evcc-ext-allrooms option` is pinned dark-bg/light-text for
  Windows Chrome.

**The wizard:**

- **Step 1 — room count.** A live **room-count stepper** (− / +, clamped to
  `1..candidates.length + 1`) plus, per detected cut, an **action-first**
  split/merge control: an active boundary shows **"↥ Merge up"** (collapse this
  room into the one above); an inactive candidate shows **"↳ Split here"**
  (re-open a detected cut inside a room, tagged `· uncertain` when not confident).
  Each control re-segments **server-side** (§5a) and the segment list + count
  refresh from the rewritten record; a cap shows the "Only N room(s) detectable…"
  message. A **v1 record** (no samples → `resegmentable: false`) hides the stepper
  and degrades to legacy merge-only.
- **Step 2 — per room.** For each room group: a shortlist chip row (+ an "all
  rooms" select to override), editable `clean_mode` + passes chips, an
  **edge-mop toggle highlighted** (the one field with no signal), and a
  **per-room settings editor** for `fan_speed` / `clean_intensity` /
  `water_level` driven by the **adapter vocabulary** (the same option source as
  the room editor; the captured value is the default). Confirm submits; a tier-1
  block surfaces inline warnings + a "keep anyway" override.

Discovery is lightweight: the subtab shows a badge count (the list is fetched
once on first render and on subtab entry). *(Deferred: a real-time toast driven
by `EVENT_EXTERNAL_RUN_PENDING`.)*

---

## 8. Services + event

Registered in
[`learning/services.py`](../../custom_components/eufy_vacuum/learning/services.py)
(all `supports_response`):

| Service | Args | Returns |
|---|---|---|
| `eufy_vacuum.get_external_pending_runs` | `vacuum_entity_id` | `{pending: [record…], count, brand}` (newest first, each tagged `pending_job_id` + `resegmentable`, samples stripped, full `rooms` list attached) |
| `eufy_vacuum.resegment_external_run` | `vacuum_entity_id, map_id, pending_job_id, ` **Exclusive** `(expected_rooms:int≥1 \| active_boundaries:[int])` | `{ok, …new record…, …meta}` or `{ok: false, error}` (rewrites the pending file in place; §5a) |
| `eufy_vacuum.confirm_external_run` | `vacuum_entity_id, map_id, pending_job_id, room_assignments[], rebuild_stats?` | `{ok, job_id, job_path, rooms_learned, rebuilt}` or `{ok: false, blocked: [...]}` |
| `eufy_vacuum.discard_external_run` | `vacuum_entity_id, pending_job_id` | `{ok}` (deletes the pending file) |

`expected_rooms` and `active_boundaries` are mutually exclusive
(`vol.Exclusive`); passing neither resets to the confident-only default. Each
handler resolves room state on the loop, then runs the disk-heavy work on the
executor. **Event:** `EVENT_EXTERNAL_RUN_PENDING`
(`eufy_vacuum_external_run_pending`) is fired after a pending record is written —
payload `{vacuum_entity_id, map_id, record_path, segment_count, detection_ts}`.

---

## 9. Adapter contract

Additions to the adapter config (see
[22-adapter-config-reference](22-adapter-config-reference.md)):

- **`settings_selects`** — the global select entities that mirror the *current
  room's* per-room settings while a job runs. We dispatch these for internal
  jobs but never read them back; for external runs they are the only window into
  what the app set. Shape: `{canonical_key: {entity_id, value_map}}`, where
  `value_map` (optional) normalizes raw firmware strings to canonical. Eufy
  declares `clean_mode/fan_speed/water_level/clean_intensity/mop_intensity`, each
  pointing at the **named `select.<object_id>_*` entity** (not the dispatch or
  number entity) — so `water_level` captures the level name ("High"), not the
  tank-percent number, and `clean_intensity` resolves even when capability
  detection skipped it.
  `edge_mopping` is **absent** — it is a dispatch-only payload field with no
  readback entity, so the user supplies it in review.
- **`rooms_unique_per_job`** capability — `True` when a room is cleaned at most
  once per job (no "vacuum-then-mop" whole-home mode). Eufy answers `True`, so
  the card hard-blocks picking an already-used room; a brand with a vac-then-mop
  pass would answer `False` (each room visited twice). Same capability discipline
  as `position_lock_reliable` — core asks the adapter, never assumes.
- **`brand`** — short brand/app name (e.g. `"Eufy"`) returned by
  `get_external_pending_runs` and shown in the card's empty state ("Start a clean
  from the {brand} app"). Absent → the card uses generic phrasing. Keeps brand
  strings out of the otherwise brand-agnostic card.

Graduated external runs feed the **same** learning buckets as internal runs:
`clean_mode` is canonicalized in the room key (`"vacuum and mop"` → `"vacuum_mop"`),
so an app-started vacuum-and-mop run merges with queue-dispatched runs of the same
settings instead of forming a parallel bucket. See
[10-learning-system](10-learning-system.md).

---

## 10. Files

| Area | File |
|---|---|
| Segmenter (shared, 3-stage) | `custom_components/eufy_vacuum/counter_segmentation.py` (`find_candidates`, `select_active`, `build_segments`; `segment_counters` is the back-compat wrapper) |
| Job-segmenter engine seam | `learning/job_segmenter_engines.py` (`EufyCounterSegmenter`/`eufy_counter_v1` delegates to the primitives verbatim; `get_job_segmenter_engine` falls back to Eufy; `JobBoundaryCandidate`/`JobSegment` TypedDicts) |
| Capture + external slot | `jobs/active_job.py` (`record_counter_sample`, `_snapshot_settings_selects`, `start_external_capture`, `_MAX_COUNTER_SAMPLES`) |
| Detection + orchestration | `listeners/lifecycle.py`, `core/manager.py` (`maybe_handle_external_run`, `_finalize_external_run`, `confirm_external_run`, `get_external_pending_runs`, `resegment_external_run`, `discard_external_run`) |
| Pending record + re-segment + gate + graduate | `learning/external_ingest.py` (`build_pending_record`, `resegment_pending_record`, `_resolve_engine_tuning`, `_enrich_segments`, `strip_samples`, `gate_segment_identity`, `build_graduated_job`, `load_pending_runs`) |
| Services + event | `learning/services.py` (`resegment_external_run` incl.), `const.py` (`EVENT_EXTERNAL_RUN_PENDING`) |
| Adapter contract | `adapters/eufy/adapter.py`, `adapters/config_schema.py` |
| Card | `src/{state,actions,renderers,bindings,styles}/external-jobs.js` |
| Tests | `tests/unit/test_learning_external_ingest.py`, `tests/unit/test_jobs_active_job.py`, `tests/unit/test_counter_segmentation.py` |

---

## 11. Known limitations / deferred

- **ByTime mid-room wash** — a wash that interrupts a room mid-coverage (the room
  resumes covering *new* floor after) reads as a boundary, like the old behavior.
  Distinguishing it would need wash-mode awareness; out of scope. The user's
  ByRoom setup is unaffected, and the room-count stepper / "Merge up" let the user
  collapse it (§5a).
- **Live-validated (2026-06-07)** — detection, counter + settings capture (all
  five selects, value-mapped), finalize on `docked`/`idle`, the review wizard, and
  Confirm → graduate → rebuild were confirmed end-to-end on real firmware. The
  `settings_selects` ids use the `select.<object_id>_*` convention; the end-signal
  is `docked`/`idle`. Both still degrade gracefully (empty settings → area-only;
  no false finalize). The schema-v2 re-segmentation pipeline (embedded samples,
  `resegment_external_run`, the count stepper + split/merge) is newer than this
  validation note — re-confirm the live round-trip when convenient.
- **v1 records** — pending records written before schema v2 carry no embedded
  samples, so they cannot be re-segmented; they load and confirm fine and the card
  degrades to legacy merge-only (`resegmentable: false`).
- **Deferred polish** — real-time `EVENT_EXTERNAL_RUN_PENDING` toast (badge
  fetches on entry today); a sequence/habitual-order prior in the shortlist ranker.
- **Untested orchestration** — the I/O glue (`confirm_external_run`,
  `maybe_handle_external_run`, `_finalize_external_run`, `resegment_external_run`)
  has no unit tests; the pure logic (`build_pending_record`,
  `resegment_pending_record`, `build_graduated_job`, `gate_segment_identity`,
  `load_pending_runs`, the 3-stage segmenter, the capture spine) is covered, and
  the orchestration is validated live.
