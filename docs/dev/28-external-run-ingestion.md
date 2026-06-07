# 28 — External-Run Ingestion

How an **app-started clean** — a job the integration did **not** dispatch — is
detected, captured, segmented into rooms, reviewed by the user, and folded into
the same learned baselines as an internal run.

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
finalize → segment_counters (blind) + recover per-segment {area,time,passes,settings}
           + settings-flip-corroborated suggested count + area+settings shortlist
      │
      ▼
external_jobs/job_<detection_ts>.json   (status="pending")   ── pending record (§4,§5)
      │   + EVENT_EXTERNAL_RUN_PENDING fired
      ▼
"External Jobs" review card → user confirms room per segment + edge-mop   ── card (§7)
      │
      ▼
confirm service → tier-1 identity gate → build a normal completed-job record   ── gate + graduate (§6)
      │
      ▼
jobs/ext-<id>.json (origin="external", used_for_learning) → rebuild → learned room_stats
```

Nothing between detection and confirm touches the learned baselines. The pending
record is an **inbox**; only the confirm service graduates a run into learning.

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

## 4. The pending record

On finalize, `_finalize_external_run` runs the captured stream through
[`learning/external_ingest.py`](../../custom_components/eufy_vacuum/learning/external_ingest.py)
`build_pending_record` (pure) and writes the result atomically to
`learning/<slug>/external_jobs/job_<detection_ts>.json` (peer to `jobs/`).

```jsonc
{
  "schema_version": 1,
  "status": "pending",
  "origin": "external",
  "detection_ts": "...",
  "map_id": "6",
  "segment_count": 2,
  "suggested_room_count": 2,            // confident boundaries + 1 (§5)
  "segments": [
    {
      "order": 0,
      "t_start": "...", "t_end": "...",
      "area_m2": 6.0,                    // unique m² = true room size
      "time_wall_s": 210, "time_active_s": 240,
      "pass_count": 1,                   // area-plateau pattern
      "settings": { "clean_mode": "vacuum_mop", "fan_speed": "Turbo", ... },
      "boundary": "job_start",
      "confident_boundary": null,        // null for order 0; bool for K>0
      "shortlist": [ { "room_id", "slug", "name", "is_carpet", "learned_area_m2", "score" }, ... ]
    },
    ...
  ]
}
```

`external_jobs/` is purely the pending inbox — see §6 for what happens on accept.

---

## 5. Segmentation, the suggested count, and the shortlist

**Segmentation** uses the shared counter-plateau segmenter
([10-learning-system](10-learning-system.md) §segmenter) called **blind**
(`expected_rooms=None`) — external has no queue to constrain it. The forward
area-rise rule applies: a `cleaning_time` blip is a boundary when it is a long
wash plateau **or** `cleaning_area` rises ≥ ~2 m² in the stretch after it. Blind,
this may over-split a single room cleaned edges-then-fill (area rises across its
internal turn) — that's resolved by the human, below.

**Per-segment recovery:**

| Field | Source | Note |
|---|---|---|
| `area_m2` | `cleaning_area` Δ | true unique size, path/pass-**invariant** |
| `time_wall_s` | wall-clock span | path/pass-**inflated** (not a size signal) |
| `pass_count` | area-plateau pattern | `_estimate_passes`: total / span-until-area-stopped-rising |
| `settings` | the captured selects active during the segment | clean_mode is canonical; others raw |

**Suggested room count.** This is the one place the settings timeline does more
than fill the per-segment `settings` — it disambiguates the boundaries:

- A boundary is **confident** when it is a **long wash plateau** OR the per-room
  settings **changed across it** (a flip — the app set the next room's settings).
- A short delayed step with **flat settings** is **uncertain** — it could be an
  edge→fill turn *inside* a room or a same-settings adjacent room. The counters
  alone can't tell them apart.
- `suggested_room_count = 1 + (confident boundaries)`. Uncertain cuts are kept in
  the record (with `confident_boundary: false`) and surfaced in the card as
  toggleable "maybe split here" markers, **default off** (merged).

> Settings-flip is a **suggestion-layer corroborator only**. The core segmenter
> stays counters-only / settings-independent, because internal runs resolve the
> count from the dispatched queue, never from flips.

**The shortlist** (`_rank_shortlist`) ranks the active map's rooms per segment:

- **area-match** — `-|segment_area − room.avg_area_m2|` from the learned
  `room_baselines` (cold rooms with no baseline score last but stay selectable).
- **settings-match** — a `+1.5 m²`-equivalent nudge when the segment's recovered
  `clean_mode` matches the room's configured `clean_mode` (breaks ties between
  same-size rooms).
- **carpet filter** — when the segment was mopped (`clean_mode ∈ {mop,
  vacuum_mop}`), rooms whose `floor_type` starts with `carpet` are dropped (you
  can't mop carpet; the card's "all rooms" override can still reach them).
- Top-3 baked into the record; the card's "all rooms" select is the override tail.

*(Deferred: a sequence/habitual-order prior. Area + settings is the shipped
ranker.)*

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

- `state/external-jobs.js` — subtab selection, the pending list, and the wizard
  (open run, per-boundary split toggles, per-segment assignments). `externalWizardGroups`
  derives room groups from the split toggles.
- `actions/external-jobs.js` — `fetchExternalPendingRuns`, `confirmExternalRun`,
  `discardExternalRun` (the three services).
- `renderers/external-jobs.js` — the subtab list + the two-step wizard modal.
- `bindings/external-jobs.js` — subtab events + modal-host events + the submit
  flow.
- `styles/external-jobs.js` — subtab/list (shadow root) + wizard (modal host),
  **canonical foundation tokens only** (no new tokens).

**The wizard:**

- **Step 1 — room count.** Lists the segments; each uncertain boundary is a
  split/merge toggle (confident boundaries default split). The room count
  updates live from the toggles.
- **Step 2 — per room.** For each room group: a shortlist chip row (+ an "all
  rooms" select to override), editable `clean_mode` + passes chips, an
  **edge-mop toggle highlighted** (the one field with no signal), and the
  detected fan/water/intensity shown read-only. Confirm submits; a tier-1 block
  surfaces inline warnings + a "keep anyway" override.

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
| `eufy_vacuum.get_external_pending_runs` | `vacuum_entity_id` | `{pending: [record…], count}` (newest first, each tagged `pending_job_id`) |
| `eufy_vacuum.confirm_external_run` | `vacuum_entity_id, map_id, pending_job_id, room_assignments[], rebuild_stats?` | `{ok, job_id, job_path, rooms_learned}` or `{ok: false, blocked: [...]}` |
| `eufy_vacuum.discard_external_run` | `vacuum_entity_id, pending_job_id` | `{ok}` (deletes the pending file) |

Each handler resolves room state on the loop, then runs the disk-heavy work on
the executor. **Event:** `EVENT_EXTERNAL_RUN_PENDING`
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
| Segmenter (shared) | `custom_components/eufy_vacuum/counter_segmentation.py` |
| Capture + external slot | `jobs/active_job.py` (`record_counter_sample`, `_snapshot_settings_selects`, `start_external_capture`) |
| Detection + orchestration | `listeners/lifecycle.py`, `core/manager.py` (`maybe_handle_external_run`, `_finalize_external_run`, `confirm_external_run`, `get_external_pending_runs`, `discard_external_run`) |
| Pending record + gate + graduate | `learning/external_ingest.py` |
| Services + event | `learning/services.py`, `const.py` (`EVENT_EXTERNAL_RUN_PENDING`) |
| Adapter contract | `adapters/eufy/adapter.py`, `adapters/config_schema.py` |
| Card | `src/{state,actions,renderers,bindings,styles}/external-jobs.js` |
| Tests | `tests/unit/test_learning_external_ingest.py`, `tests/unit/test_jobs_active_job.py`, `tests/unit/test_counter_segmentation.py` |

---

## 11. Known limitations / deferred

- **ByTime mid-room wash** — a wash that interrupts a room mid-coverage (the room
  resumes covering *new* floor after) reads as a boundary, like the old behavior.
  Distinguishing it would need wash-mode awareness; out of scope. The user's
  ByRoom setup is unaffected, and the count step lets the user merge it.
- **Live-validated (2026-06-07)** — detection, counter + settings capture (all
  five selects, value-mapped), finalize on `docked`/`idle`, the review wizard, and
  Confirm → graduate → rebuild were confirmed end-to-end on real firmware. The
  `settings_selects` ids use the `select.<object_id>_*` convention; the end-signal
  is `docked`/`idle`. Both still degrade gracefully (empty settings → area-only;
  no false finalize).
- **Deferred polish** — real-time `EVENT_EXTERNAL_RUN_PENDING` toast (badge
  fetches on entry today); fan/water/intensity per-room overrides in the card
  (mode/passes/edge-mop are editable now; the others are shown detected); a
  sequence prior in the shortlist ranker.
- **Untested orchestration** — the I/O glue (`confirm_external_run`,
  `maybe_handle_external_run`, `_finalize_external_run`) has no unit tests; the
  pure logic (`build_pending_record`, `build_graduated_job`, `gate_segment_identity`,
  `load_pending_runs`, the capture spine) is covered, and the orchestration is
  validated live.
