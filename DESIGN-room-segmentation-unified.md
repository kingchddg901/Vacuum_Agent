# Unified Room Segmentation & Per-Room Learning — Implementation Design

Merges two efforts into one: my transit/travel work (Phases 1–5, shipped-but-uncommitted)
and `scratch-external-estimator/FORK-FINDINGS.md` (counter-plateau segmentation). This is
the go-forward plan. Large-change workflow: **approval pause before any code; phased waves;
not-a-rewrite; explicit contracts.**

---

## 1. The core primitive — counter-plateau segmentation

`cleaning_time` and `cleaning_area` are cumulative **progress counters**, not state:
- `cleaning_time` = a pure 30 s clock (+30 per tick while actively cleaning). Plateaus during
  transit/wash. Resets to 0 at job start; **may or may not reset per room** (firmware/mode
  dependent — ByRoom wash = cumulative+plateau; some modes reset). **So resets are NOT the
  boundary signal.**
- `cleaning_area` = unique m² covered (+~1 per new floor). **Flat** while re-covering
  (multi-pass) or transiting.

**Boundary signals, in robustness order:**
1. **Job boundary** = both counters reset to 0 together. Hard.
2. **Room boundary, ByRoom wash** = a minutes-long **plateau** (both counters stop = the
   inter-room wash trip). Hard.
3. **Room boundary, no wash / adjacent** = a **delayed `cleaning_time` step** (a "blip":
   gap `> 30 s clock + ~5 s slack`) **after which `cleaning_area` rises ≥ ~2 m²** in the
   stretch before the next blip (new floor covered).
4. **Pass-turn (NOT a boundary)** = a blip after which `cleaning_area` stays **flat**
   (re-covering the same room).

The discriminator for 3 vs 4 is the **forward** area trace — read the area-rise in the
stretch *after* the blip (up to the next blip), **not at the same instant**, because area
packets *lag* the clock. `cleaning_time` step size is never the signal (it's a fixed 30 s
clock; the delay is "30 + extra", turn ≈ +6 s vs boundary ≈ +13 s); the signal is
**gap-timing + the forward area trace**. The original *same-instant* rule failed on a real
path-varied run (1 segment, not 2) — see **Wave 6 → "Segmenter correction"** for the proof
and the corrected contract. Validated in `FORK-FINDINGS.md` (`segment_internal.py`,
`nomop_boundary.py`), my CSV trace, and the multi-setting external CSV.

## 2. Per-room decomposition (what each segment yields)

Segment the post-reset stream by boundaries → contiguous increment-runs = per-room bouts.
Per segment:
- **area Δ** = `cleaning_area` delta = that room's **true area** (exact, no estimation — works
  for multi-room, which Phase 3 couldn't do).
- **time (wall)** = wall-clock span of the bout = the **learnable duration** (NOT the counter
  delta — `cleaning_time` *undercounts* in-room time, 390 s vs 9.64 min). Counter delta stored
  too (active-cleaning time).
- **battery Δ** over the bout.
- **inter-room gap** = wall-clock from this bout's last rise to the next bout's first rise =
  transit (+ wash, in ByRoom).

## 3. Room identity

- **Internal:** segment K → dispatched **queue room K** (certain; `active_cleaning_target` is
  also populated for internal jobs as a cross-check).
- **External (later phase):** identity is hidden by the device → area + return-leg **top-3
  shortlist** (~80%) → **user confirms** → norms-gate. Auto-attribution caps at ~67%.

## 4. Learning-quality gate (the "gold")

Per segment, compare observed **area vs the room's learned expected area** (`room_baselines`
band):
- observed area ≪ expected ⇒ **partial/interrupted clean** ⇒ exclude from **timing** learning
  (its short time would poison the baseline). ~12% of cleans flagged; tightened Kitchen
  stddev **101 → 80 s** on the archive.
- multi-pass room whose area never plateaus-then-holds ⇒ **dropped-pass** flag.
- in-norms ⇒ learn.

This fixes a live bug: today multi-room jobs write `room_cleaning_minutes: null` yet
`used_for_learning: true`, so a good per-room sample is wasted while a light "Quick" pass
rides along ungated.

## 5. Capability-gated geometry (adapter's call — locked constraint)

The bounds/position layer **stays in core**, but **whether to trust it is the adapter's
call**. Core is brand-neutral and never hardcodes "geometry unreliable." It asks the adapter
(e.g. `position_lock_reliable` capability / method); **Eufy answers false** (firmware
re-bases the raw frame every session — no fixed anchor), other brands may answer true. Do not
delete the layer; do not generalize Eufy's failure.

## 6. Reuse vs rebuild (from my Phases 1–5)

| Piece | Disposition |
|---|---|
| Phase 1 `_apply_cleaning_time_sample` (reset-based, cleaning_time only) | **Rebuild** → buffer time-aligned (t, ct, ca, batt) samples + a pure `segment_counters()` |
| Phase 2 job-record blocks (`room_timings`/`transitions`/`transit_capture_valid`/`overhead_observed`) | **Keep + extend** (add per-room `area_m2`, wall time, battery; segmentation confidence) |
| Phase 3 aggregation (`transit_stats`/`access_graph_edges`/ingress-egress/overhead) | **Keep**; now also gets per-room area for multi-room + the area gate |
| Phase 4 estimator (transit fallback chain, `estimated_transit_minutes_before`, `transition_source`) | **Keep**; wire to new per-room data |
| Schema bumps (room_stats 5 / job_stats 4) | **Keep**; may extend |
| Segmentation unit tests | **Rewrite** (reset → counter-plateau); downstream tests mostly keep |

## 7. Contracts

**Capture (core, brand-agnostic).** Buffer one event per counter change into
`active_job["counter_samples"]`, carrying last-seen of the other counter + battery:
`[{t, cleaning_time, cleaning_area, battery}]`. Replaces the incremental segmenter + the
cleaning_area-only sensor write feeding learning.

**Segmenter (pure, testable).** Called on the partial stream (live → tentative
`current_room_id`) and the full stream (finalization → authoritative):
```
segment_counters(samples, *, expected_rooms=None, clean_passes=None,
                 cadence_s=30.0, gap_factor=1.4) -> list[Segment]
Segment = {index, t_start, t_end, area_start, area_end, area_delta_m2,
           time_wall_s, time_active_s, battery_delta, gap_before_s,
           kind: "room"|"job_start", boundary: "reset"|"wash_plateau"|"area_jump"}
```
Internal constraint: expect exactly `expected_rooms-1` area-jump transitions and
`sum(passes-1)` flat-area pass-turns; resolve ambiguity against that budget.

**Gate (reuses learning infra).**
```
gate_segment_for_learning(segment, room_baseline) -> {learn: bool, reason, flags}
```

## 8. Phasing (each wave is an approval checkpoint)

- **Wave 1** — capture rework: buffer counter samples; `segment_counters()` in core; replace
  reset-segmenter. Rewrite segmentation tests. *(Pure/unit — no live-path risk yet.)*
- **Wave 2** — finalization: segment→queue mapping (internal), per-room blocks incl.
  `area_m2`/wall-time/battery + segmentation confidence. Adapt finalizer + history_store.
- **Wave 3** — aggregation + **area-quality gate**: per-room area from multi-room; gate
  partials out of timing learning. Verify the 101→80 s tightening on the archive.
- **Wave 4** — estimator: consume the new per-room data (Phase 4 is mostly there).
- **Wave 5** — capability-gated geometry: adapter `position_lock_reliable`; demote Eufy's
  bounds AND-gate; fold plateau boundary into live `_maybe_roll_current_room_by_timing`.
- **Wave 6 — external-run ingestion** *(design closed 2026-06-06; full contracts in the
  dedicated **Wave 6** section below)* — identity can't be auto-resolved (~67% ceiling), so
  the Lovelace card *is* the resolver. Split into five committed sub-waves **W6.1–W6.5**
  (segmenter fix → capture/detect/pending → confirm-service/gate/graduate → card wizard →
  docs/live).

## 9. Test + verification
- Pure-Python unit tests per wave (`pytest tests --no-cov`, 0 warnings).
- Re-segment the real archive jobs; confirm per-room splits sum to job totals (validated:
  Hallway 240 s/6 m² + Kitchen 90 s/2 m² = 330 s/8 m²) and the gate flags ~12%.
- Live: a multi-room ByRoom run + a no-wash run + a 2-pass single-room run (the three cases
  in §1) confirm boundaries and pass-turns.

## 10. Open decisions (need your call before Wave 1)
1. **Scope:** internal per-room + counter-plateau + area-gate now (Waves 1–5); external
   (Wave 6) as a separate design later? *(recommend yes)*
2. **Capture model:** buffer raw counter samples + pure re-segmenter (live + final),
   replacing the incremental reset-segmenter? *(recommend yes — robust, testable, serves both)*
3. **Per-room duration metric:** wall-clock span as the learnable time (counter delta also
   stored)? *(recommend yes — counter undercounts)*
4. **Commit strategy:** commit current Phase 1–5 as a baseline checkpoint first, then rework
   on top; or keep uncommitted and commit the unified result? *(recommend: branch + commit
   baseline for a revert point)*
5. **Coordination:** confirm I own all the shared files now (`active_job.py`,
   `job_finalizer.py`, `history_store.py`, `stats_rebuilder.py`, `estimator.py`) — the other
   agent's work is the design doc + prototypes, done?

*(All five resolved: branch+commit baseline · buffer raw samples + pure re-segmenter ·
wall-clock per-room time · internal-first/external-later · this agent owns the shared files.
Waves 0–5 shipped; Wave 6 designed below.)*

---

# Wave 6 — External-run ingestion (detailed design)

**Status: design closed 2026-06-06; awaiting approval to code.** Novel for this system — the
first path that ingests a run the integration did **not** dispatch. Internal runs resolve
identity from the dispatched queue; external (app-started) runs hide it, so a **human
resolves identity in the card** and the backend learns from the result.

## Why external is different

| | Internal | External |
|---|---|---|
| Started by | our `room_clean` dispatch | the Eufy app |
| `active_cleaning_target` | populated | **unavailable** (hidden for app jobs) |
| Room identity | segment K → queue room K (certain) | **unknown** → human-confirmed |
| Settings | we dispatched them | **recovered from device state** |

Pipeline: **observed-only capture → segment → recover what we can → shortlist → human
confirms in a wizard → gate → graduate into normal learning.**

## Segmenter correction — the forward area-rise rule (supersedes §1.3)

§1 said a boundary is a delayed step where `cleaning_area` jumps **at that instant**. That is
**wrong on path-varied runs**, proven on a real multi-setting external run:

- Room 1 ran **Narrow** intensity → 3 m² unique area for 360 s of cleaning (Narrow
  re-covers), so area had **plateaued** well before the boundary.
- Room 2's area-jump **lagged the boundary by ~60 s** (area packets trail the clock).
- ⇒ the same-instant test saw `Δarea = 0` at the boundary → **1 segment, not 2.**

**The fix** (we parse at *terminal* — the full buffered stream is in hand). A **blip** is a
`cleaning_time` gap above the 30 s clock + slack. It is a **boundary** when EITHER:

> - it is a **long plateau** (`gap > ~90 s`) — a minutes-long mop wash / transit (pass-turns
>   are seconds, never minutes); **or**
> - `cleaning_area` rises **≥ ~2 m²** in the stretch *after* it, read **FORWARD** to the next
>   blip (the area lag means the new room's jump can land a tick later).
>
> Otherwise the short delayed step is a **pass-turn** (flat area after — re-covering).

Only the *short delayed step* changed (same-instant → forward); the long-plateau shortcut is
kept so the **live** path can roll the moment a wash starts. Re-run on the CSV: **2 segments**
(the +6 s turn → flat after → turn; the +13 s boundary, area flat at the instant but 3→8 m²
after → boundary).

What it buys:
- **Settings-independent** — works when adjacent rooms share settings (no flip to lean on).
- **Fixes the path-varied boundary** — the short delayed step is now area-gated *forward*, so
  a Narrow room that has re-covered (flat area at the gap) still splits once the next room's
  area catches up.
- **Improves internal** — today internal survives a path-varied run only via the queue-count
  check; the forward rule makes it correct.

**Over-split needs the queue count.** A single room cleaned **edges-then-fill** (or any
progressive-area multi-pass) has area rising *across* its internal turn — indistinguishable
from a real boundary by the counters alone (validated: `run1` split into 2 instead of 1). So
`segment_counters` takes **`expected_rooms`**: internal callers pass the dispatched queue
length and the segmenter keeps only the strongest boundaries (long plateau > short step, then
larger forward rise). External passes `None` and may over-split — the **wizard's count step**
is the human merge. *(A genuine ByTime mid-room wash, where the same room resumes covering new
floor, still reads as a boundary — neither rule handles that; it would need wash-mode
awareness, out of scope.)*

`cleaning_time` is a hard **30 s clock**; the delay is **"30 + extra"** (turn ≈ +6 s,
boundary ≈ +13 s). Detect on *delay past the clock*, never an absolute 40 s — a 40 s cutoff
would miss the +6 s turn.

## What's recoverable from device state (the external "sensors")

| Field | Source | Notes |
|---|---|---|
| **area** | `cleaning_area` Δ per segment | **true unique size** — path/pass-**invariant** |
| **time** | wall-clock span | path/pass-**inflated** (not a size signal) |
| **pass-count** | area-plateau pattern | area rises then holds = re-covering |
| **settings** | the live selects | `cleaning_mode/suction/water/mop_intensity/cleaning_intensity` — **all flip per room** (validated) |
| **map** | `get_active_map_id` (`sensor.{obj}_active_map`) | scopes the shortlist |
| **edge-mop** | — | **not recoverable** (dispatch-only payload, no readback) → **user supplies** |

## Detection + capture lifecycle

- **Detect** (lifecycle listener): trigger A (`vacuum → cleaning`) **and** no dispatched
  `active_job` (`status ∉ {started, paused}`) ⇒ external. Safe: internal starts are *already*
  blocked during an external run (the lifecycle start-blocker), and dispatch commits
  `status="started"` synchronously right after the service call — so "no active_job" reliably
  means "we didn't start this one."
- **Capture**: reuse the `active_jobs` slot with **`status="external"`**; buffer counters +
  the setting selects + `active_map_id`.
- **Finalize** (run-end, external branch): `segment_counters` (forward rule) over the full
  buffer → per-segment structure; recover settings/passes per segment; bake the shortlist;
  write the pending record.

## The pending record

- Path: `learning/<slug>/external_jobs/job_<detection_ts>.json` (peer to `jobs/`, normal
  timestamp naming).
- Shape: `{map_id, status: "pending", detection_ts, segments: [{order, area_m2, time_wall_s,
  pass_count, settings{…}, shortlist: [{room_id, score, …}]}]}`.
- `external_jobs/` is a **pending inbox only** (see *Graduate into normal learning*).

## Identity — the shortlist (ranker + filters)

Identity is **map + room** (locked). The map is recovered, so the shortlist is **scoped to
the active map's rooms**; the user picks a *room*, never a map (override only for the rare
just-switched-map case).

**Ranker (combined score):**
- **area-match** — robust base (unique m² = an objective, path-invariant size match).
- **settings-match** *(new)* — segment settings vs the room's typical learned settings;
  *distinctive* (rooms are configured differently) → separates same-size rooms.
- **sequence prior** — weak: habitual order, from the access-graph data we already learn.
- **position** — capability-gated **off for Eufy**, on for stable-lock brands.

**Filter stack (per segment):**
```
map-scope
  → drop already-picked   (HARD, iff rooms_unique_per_job)
  → carpet soft-drop      (when mopped: floor_type carpet_* ⇒ is_carpet; only mop excludes)
  → rank (area + settings + sequence)
  → top-3 default;  "all rooms" reveals every UNPICKED room (universal override)
```
The **ranker sorts**, the **filters shape the default**, the **human decides**, the **gate
checks**. Carpet is **soft** (override exists for mop auto-lift / mislabel / washable rug).
The **universal override** is always present because a run can be a *brand-new type* our
history can't rank (a never-cleaned room, a first-time settings combo) — those land in
cold-start downstream.

## New capability — `rooms_unique_per_job`

A room is cleaned at most once per Eufy job (Eufy has no "vac-then-mop" whole-home mode that
visits each room twice). **Eufy answers `true`** → already-picked rooms are a **hard**
elimination. A brand with vac-then-mop answers **`false`** → the shortlist allows repeats
(built out when that adapter lands). Same discipline as `position_lock_reliable`: **core
asks the adapter, never assumes.** The escape for an apparent repeat on Eufy is **merge**
(the wizard's count step), not a duplicate pick — two segments that are really one room is a
*count error*, not a revisit.

## The card — review wizard

- **Surface**: an **"External Jobs" subtab** in the learning/review surface
  (`src/{state,actions,renderers,bindings}/review.js` + `learning.js` +
  `controllers/learning-controller.js`). A new pending record fires a **notification**.
- **Wizard** (modal; reuses `room-editor.js` for visual consistency):
  - **Step 1 — room count.** "Detected **N rooms** — Accept / Change." External has no
    `expected_rooms` yet, so the suggestion can't lean on the queue — instead the suggested
    **N = confident boundaries + 1**, where a *confident* boundary is a **long plateau** (wash)
    or a **settings-flip** (the app set the next room's settings, captured in W6.2). A short
    delayed step showing only an area-rise with **no flip** is **uncertain** — an edge→fill turn
    *within* a room or a same-settings adjacent room — so it is shown as a toggleable **"maybe
    split here"** marker, **default off** (a lone edge→fill room then suggests 1 and needs no
    action; a same-settings boundary is one tap to add). Changing the count re-runs
    `segment_counters` with `expected_rooms = N`. Capped at `#blips + 1`; needing more is ignored
    for v1 (the gate + **Discard** catch an under-split). *(Settings-flip is the external
    suggestion's corroborator only — the core segmenter stays counters-only / settings-independent,
    because internal resolves the count from the queue, not flips.)*
  - **Step 2 — per room (loop × count), styled as the room-editor.** Segment facts
    (order / area / time / clock) as ID cues; **room identity** pre-filled with the #1
    shortlist pick (tap → top-3 + all-rooms); **settings** (mode/suction/water/intensity/
    passes) pre-filled from detection, accept/override each; **edge-mop highlighted** (no
    signal → user sets). *Everything is correctable* — our recovery can err.
  - **Confirm | Discard.** Discard drops junk / false-start / un-splittable runs.
- **Gate feedback**: v1 = **server round-trip** on Confirm (no gate logic in the card); a
  blocked segment flips to a warning → **re-pick / keep-anyway** (override). An instant
  pre-warn is **deferred** (it would duplicate gate logic into the card); it can be added
  later as a *pure display* compare (segment area vs the room's band), no logic moved.

## Confirm service + gate

**Service** (post-review): apply `{count, per-segment room, edge-mop, setting overrides}` →
run the gate per segment → graduate.

**Gate** (reuses the §4 learning-quality infra), per segment:
- **tier-1 — identity sanity**: segment area vs the confirmed room's band. Mismatch ⇒
  **BLOCK + warn**; user re-picks **or overrides** (choice **A** — a mis-click never silently
  buries a run; override respects that *our* band can be wrong or the run is novel).
- **tier-2 — quality (the §4 area gate)**: area in band ⇒ **full** ⇒ ingest time + area into
  the **exact settings bucket**; area below band ⇒ **partial** ⇒ ingest area, **exclude time.**
- **cold-start** room (no baseline) ⇒ **bootstrap-ingest**, low confidence.
- **new settings combo** ⇒ **new exact bucket** (never blends — a gentle-mode run does not
  poison the Max/High norm).

Per-segment and independent: a multi-room external can ingest room A while blocking room B.

## Graduate into normal learning

On **accept**, the run **joins the normal jobs**:
- Write a **normal completed-job record** to `jobs/` — `room_timings` per confirmed segment
  carrying identity + settings + edge-mop + `area_m2` + wall-time; `origin: "external"`;
  `used_for_learning` per the gate.
- **Delete** the pending `external_jobs/` file.
- The **existing rebuild ingests it unchanged** (it already globs `jobs/`).

So `external_jobs/` is purely the pending inbox, and the accepted run shows up in the normal
**used/excluded** jobs list. *This supersedes the earlier "rebuild also reads `external_jobs/`"
sketch — the UI "join the normal ones" framing removed a whole read path.*

## Sub-wave plan (each green + committed, mirrors W0–5)

| Wave | Scope |
|---|---|
| **W6.1** | Segmenter forward-area-rule fix; re-verify run1/5/6/7 + the external CSV + full suite |
| **W6.2** | Capture (selects + `active_map_id`) + detection lifecycle + pending record + shortlist ranker/filters + `rooms_unique_per_job` capability |
| **W6.3** | Confirm service + gate + graduate-to-`jobs/` |
| **W6.4** | Card "External Jobs" subtab + wizard + notification |
| **W6.5** | Docs (`docs/dev` + this design) + end-to-end live validation → merge / release / HACS |

## Decisions made this session (resolved calls)

- Identity = **map + room**; map auto-recovered, user picks room.
- Gate runs **after** review (needs the confirmed room + edge-mop).
- **Edge-mop** user-supplied; everything else recovered is a **correctable pre-fill**.
- tier-1 mismatch = **block + override** (choice A), not flag-and-ingest.
- **Pre-warn deferred**; v1 = server gate round-trip.
- **Graduate to `jobs/`**; `external_jobs/` = inbox only.
- **Carpet** soft (override) / **uniqueness** hard for Eufy (capability-gated).
- **Override is universal** on the picker (novel runs).
- **Count** = relabel of candidate blips (merge / promote by area-rise strength).
