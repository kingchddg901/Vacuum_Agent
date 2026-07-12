# 10 — Learning System

> **Scope:** This document is a complete implementation reference for the eufy_vacuum learning system. Every formula, constant, threshold, and file path is derived directly from the source. A developer should be able to re-implement the system from this document alone.

---

## 1. Overview

The learning system observes completed cleaning jobs and uses them to produce progressively more accurate ETA predictions. It answers three questions:

1. **How long will this job take?** — per-room timing estimates derived from historical samples.
2. **How confident should the UI be?** — a 0.0–1.0 confidence score per room (and a job-level minimum) that drives UI variant selection.
3. **Which rooms are chronically missed?** — a trouble-rooms counter that flags rooms with persistent miss patterns.

The system is entirely optional. The core integration runs without it; the learning modules are only loaded when the learning services are registered. All state lives in JSON files on disk — there is no database, no sensor state, and no in-memory persistence that survives a HA restart beyond what is explicitly cached.

**Module roles:**

| Module | Role |
|---|---|
| `estimator.py` | All estimation and confidence math. Pure computation, no orchestration. |
| `history_store.py` | File I/O. Reads and writes every JSON and CSV file. |
| `stats_rebuilder.py` | Full rebuild of `job_stats.json`, `room_stats.json`, and `jobs_index.json` from raw job files. |
| `job_finalizer.py` | Finalizes a completed job: builds the payload, writes it, triggers a stats rebuild, updates trouble rooms. |
| `manager.py` | Orchestrator. Coordinates all modules. Maintains an in-memory cache of `room_stats` and `accuracy_stats`. All classes (`LearningHistoryStore`, `LearningStatsRebuilder`, `LearningJobFinalizer`) take `hass: HomeAssistant` in `__init__` and are HA-bound; they instantiate their collaborators internally (not stateless utilities). |
| `services.py` | HA service registration only. No math. Each handler validates inputs and delegates to `LearningManager`. |
| `utils.py` | Shared helpers (`_safe_int`, `_safe_float`, `_safe_bool`, etc.) used across the learning package. |
| `external_ingest.py` | Captures runs started from the Eufy app (not HA-dispatched), builds the pending record, and re-segments / confirms them into learned jobs via the review wizard. Also runs **pose-based room attribution** (via `room_attribution_engines.py`) to pre-fill the cleaned-room set, and builds a stand-alone attributed record when counter segmentation yields nothing. For **dispatched** runs it reconciles the finalizer's positional room identity against the native current-room (`reconcile_dispatched_identity`, §2.4). |
| `job_segmenter_engines.py` | The pluggable `JobSegmenter` engine seam (`eufy_counter_v1`) over the counter-plateau primitives; selected by adapter config, with an Eufy fallback. |
| `room_attribution_engines.py` | Pluggable room-attribution seam — recovers *which managed room* a run's segments cleaned from a per-tick room stream (counter owns time/area, this owns identity). Brand-agnostic engine `eufy_anchor_winding_v1` (its **robust** clean-vs-park decision keys on swept `cleaning_area`, so it needs no pose); selected via the adapter's `room_attribution.engine`, Eufy fallback. Both Eufy and Roborock declare it (§2.4). |

---

## 2. Data Collected Per Room

### 2.1 Room stats (`room_stats.json` → `room_stats` array)

Each entry in the `room_stats` array represents one unique combination of room identity and cleaning settings. It is keyed internally by the exact string:

```
{map_id}::{room_slug}::{effective_mode}::{clean_times}::{is_carpet_int}::{clean_intensity}::{edge_int}
```

where `is_carpet_int` is `1` for carpet / `0` for hard floor, and `edge_int` is `1`
for edge-mopping on / `0` for off. Edge-mopping is in the key because it materially
changes cleaning time, so edge-on and edge-off runs are learned separately.

`effective_mode` is **canonicalized** before it enters the key: the historical
display string `"vacuum and mop"` (and `"vacuum & mop"`, `"vacuum+mop"`, …) folds to
the token `"vacuum_mop"`, so internal (queue-dispatched) and external (app-started)
runs of the same physical mode land in **one** bucket instead of splitting on a
vocabulary artifact. The normalization lives in `learning/utils.py::_canonical_clean_mode`
and is applied by `_room_key`, `_room_profile_key`, the rebuilder's stored
`effective_mode`, and the estimator's match lookup. The full `_CLEAN_MODE_CANONICAL`
alias set is `"vacuum and mop"`, `"vacuum & mop"`, `"vacuum+mop"`, `"vac & mop"`, and
`"vacmop"` (5 explicit aliases), plus a substring fallback that folds any string
containing both `"vacuum"` and `"mop"` to `"vacuum_mop"`; all other modes pass through
lowercased.

**Fields written per entry:**

| Field | Type | Source | Description |
|---|---|---|---|
| `map_id` | int | `job_profile.map_id` | Which map this room belongs to |
| `room_slug` | str | `resolved_rooms[].slug` | Lowercase slug identifier |
| `effective_mode` | str | `resolved_rooms[].clean_mode` | `vacuum`, `mop`, or `vacuum_mop` |
| `clean_times` | int | `resolved_rooms[].clean_passes`, coerced via `_safe_int(v, 1)` (min 1; the real count is preserved, not clamped) | Number of cleaning passes — **brand-dependent**: Eufy 1–2, Roborock 1–3 |
| `is_carpet` | bool | `resolved_rooms[].is_carpet` or `resolved_rooms[].carpet` | Floor type flag |
| `clean_intensity` | str | `resolved_rooms[].clean_intensity` (default `"standard"`) | Fan/suction level |
| `edge_mopping` | bool | `resolved_rooms[].edge_mopping` | Edge-mop flag — part of the key (materially affects time) |
| `sample_count` | int | Incremented once per qualifying job | How many learning jobs contributed |
| `avg_minutes` | float | `sum(gated_minutes) / timing_sample_count` (area-gated) | Mean cleaning duration — excludes partial/interrupted cleans per the schema-6 area gate (`sample_count` still counts every contributing job) |
| `minutes_stddev` | float | Population stddev of per-job duration samples | Spread of observed durations |
| `minutes_min` | float | `min(samples)` | Shortest observed duration |
| `minutes_max` | float | `max(samples)` | Longest observed duration |
| `avg_battery_used` | float | `total_estimated_battery_used / sample_count` | Mean battery consumed |
| `avg_drift_minutes` | float | Equally allocated from job-level drift | Signed mean prediction error |
| `avg_abs_drift_minutes` | float | Absolute value of drift | Mean magnitude of prediction error |
| `area_sample_count` | int | Count of single-room jobs with a recorded `cleaning_area_m2` | How many area samples contributed (≤ `sample_count`) |
| `avg_area_m2` | float | Mean per-room area (segment capture, single + multi-room; `0.0` if none) | Mean cleaned floor area for this room |
| `area_m2_min` | float | `min(area_samples)` | Smallest observed cleaned area |
| `area_m2_max` | float | `max(area_samples)` | Largest observed cleaned area |
| `area_m2_stddev` | float | Population stddev of area samples | Spread of observed areas |
| `avg_robot_water_used_ml` | float | `total_robot_water_used_ml / sample_count` (per-room allocation) | Mean robot tank water per room |
| `avg_water_overhead_ml` | float | `total_water_overhead_ml / sample_count` (dock wash + refill per-room) | Mean dock water overhead per room |
| `avg_total_water_used_ml` | float | Sum of robot + overhead, per room | Mean total water used per room |

**How `avg_minutes` is computed (cumulative average):**

The rebuilder scans all learning jobs from scratch on every rebuild. For each job, the per-room duration is approximated as:

```
per_room_duration = job.duration_minutes / room_count
```

This allocation is equal across all rooms in the job — there is no per-room actual timing sensor. For single-room jobs, `actual_cleaning_minutes` (derived from the state transition to `returning`) is preferred over `duration_minutes`.

All per-room samples are collected into `room_samples[exact_key]`. The final `avg_minutes` is:

```
avg_minutes = sum(room_samples[key]) / len(room_samples[key])
```

This is a **full cumulative average recalculated from scratch on every rebuild**, not a rolling average. There is no exponential smoothing or windowing.

**How `minutes_stddev` is computed:**

Population standard deviation of all samples for the key:

```python
def _stddev(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    return round(math.sqrt(variance), 4)
```

Returns `0.0` when `n < 2`.

**How `avg_area_m2` is computed (per room — multi-room now included):**

Per-room area comes from **counter-plateau capture** — `room_timings[].area_m2` on `transit_capture_valid` jobs (the `cleaning_area` delta per segment is the room's exact area, for single **and** multi-room jobs) — falling back to a single-room job's `cleaning_area_m2` total when there's no capture. (Previously multi-room jobs were skipped because the only signal was the job total, which equal-splitting would corrupt; the segmenter removes that limitation.) `avg_area_m2` and `area_m2_min/max/stddev` are computed over those samples; `area_sample_count` is their count (can be lower than `sample_count` for un-captured jobs). A room with no area samples gets `avg_area_m2 = 0.0`.

**How `avg_drift_minutes` is computed:**

Drift is computed **fresh from job timestamps**, not from stored estimates. For each job: `actual_seconds = (ended_at − started_at).total_seconds()`, `predicted_seconds = duration_minutes × 60`, `drift_seconds = actual_seconds − predicted_seconds`, rounded to 2 dp. This job-level drift is then equally allocated per room: `per_room_drift = job_drift / room_count`. The per-room drifts are accumulated and averaged into `avg_drift_minutes = sum(per_room_drift) / sample_count` (also 2 dp). `avg_abs_drift_minutes` is computed the same way over absolute values.

**Area-quality gate (schema 6):** a full clean covers the room's whole floor, so a clean whose area falls more than 1.5 m² off the room's **median baseline area** (once the baseline has ≥ 4 area samples) is a partial/interrupted clean — its short **time** would poison the baseline, so its minutes sample is excluded from `avg_minutes` / the minutes band. `partial_excluded_count` reports how many were dropped, `timing_sample_count` the kept count; area / battery / water keep all samples. The baseline area median is computed per-room (area is settings-invariant, using baseline-level samples), and is identified by the baseline key `{map_id_int}::{slug.strip().lower()}` (from `_room_baseline_key(map_id, slug)` in utils.py). The gate was validated on the archive (~12% flagged; Kitchen time stddev 101 → 80 s — see `scratch-external-estimator/gate.py`).

Because area is settings-invariant (a room's floor area doesn't change with mode or intensity), the per-room `room_baselines` entry carries the most robust `avg_area_m2`.

**Per-room baselines and setting buckets (`room_baselines` array):**

`room_stats.json` also carries a `room_baselines` array — one entry per `{map_id, room_slug}` that collapses *all* settings into a single per-room average (`avg_minutes`, `avg_battery_used`, `avg_area_m2`, plus the `effective_modes` / `clean_times` / carpet counts). Each baseline additionally breaks its averages out by the two settings that most affect duration:

- `by_clean_times` — `{"1": {…}, "2": {…}}` (Roborock also produces a `"3"` bucket), keyed by pass count
- `by_edge_mopping` — `{"on": {…}, "off": {…}}`

Each bucket holds `{sample_count, avg_minutes, minutes_min, minutes_max, minutes_stddev, avg_battery_used}` — the min/max/stddev band lets a consumer match *within variance* rather than against a brittle point mean. All stats are **learning-jobs-only** (cancelled / failed / sanity-blocked runs are excluded before aggregation, so a bad run never skews a bucket). The full per-room average is retained; the buckets are **additive**, so a consumer can match a job's settings (e.g. a 2-pass, edge-mop run) to the right sub-average. Area is intentionally **not** bucketed — a room's floor area does not change with passes or edge mopping.

**Water metrics in `room_baselines`:** Paralleling `room_stats`, each baseline also carries `avg_robot_water_used_ml`, `avg_water_overhead_ml`, and `avg_total_water_used_ml` (all rounded to 2 dp).

**Carpet counts in `room_baselines`:** The baseline holds `carpet_true_count` (runs on carpet) and `carpet_false_count` (runs on hard floor) — a tally of runs per surface type. Effective modes are tracked as a dict `{mode: count}` (keyed by mode, incremented once per run).

### 2.2 Transit / travel-time learning (`transit_stats` / `access_graph_edges`)

Travel time between rooms is captured **going forward** and surfaced in
`room_stats.json` (schema 5). It is **time-based / frame-invariant** — raw robot
coordinates drift wildly across sessions (the physically-fixed dock reports
y≈21 / 108 / 1526 on three different runs), so transit is **never** derived from
geometry. Instead it is read from the cleaning-time signal:

Both progress counters are read: `sensor.<vacuum>_cleaning_time` (a pure ~30 s
clock) and `sensor.<vacuum>_cleaning_area` (unique m² covered). They rise while
cleaning a room and **plateau** during transit / mop-wash. The runtime listener
(`listeners/job_metrics.py`) snapshots the last-seen pair (+ battery) into the
active job via `record_counter_sample` (`jobs/active_job.py`) on every counter
change, building a `counter_samples` stream. Capture degrades gracefully —
adapters that don't declare these entities never subscribe and fall back to the
constant overhead (§5.3).

The job segmenter (`counter_segmentation`'s primitives, reached through the engine seam
described below) turns that stream into ordered per-room segments **without geometry**.
A boundary is a **long plateau** (gap between
cleaning_time ticks > ~90 s, e.g. the ByRoom mop-wash) or a **delayed step**
(~35 s gap) after which `cleaning_area` **rises ≥ ~2 m²** in the stretch *before
the next blip* (new floor = a room transition); a delayed step with **flat** area
after it is a multi-pass turn, *not* a boundary. The area-rise is read **forward**
to the next blip, not at the same instant — area packets lag the clock, so the
next room's jump can land a tick after the boundary (the earlier same-instant
check returned 1 segment for a real 2-room run). The counter is firmware/mode-
dependent (some firmwares reset per room; ByRoom is cumulative + plateaus), so the
signal is gap-timing + the forward area trace, **never a reset**. `cleaning_area`
is read via `area_at(t)` (the monotonic area reached by time t), robust to the
area packet lagging the clock at a shared timestamp.

`segment_counters(expected_rooms=N)` caps over-splitting when the room count is
known (internal: the dispatched queue length) — the counters alone can't tell an
edge→fill / progressive-area pass-turn from a true boundary, so only the strongest
boundaries (long plateau > short step, then larger forward rise) are kept. Internal
(finalize / history) callers pass the queue length and this path is unchanged.

`segment_counters` is a **byte-identical back-compat wrapper** over a decomposed
pipeline (`find_candidates` → `select_active` → `build_segments`): it pins
`gap_transit_s=inf`, `kinds={wash_plateau, area_jump}`, and `default="all"`, so it sees only the
plateau/area-jump boundaries it always did. The decomposition adds a third boundary
**kind** the old single-pass filter dropped — **transit** (a 60–90 s inter-room hop
with *flat* area, between `_GAP_TRANSIT_S` and `_GAP_PLATEAU_S`) — alongside
`wash_plateau` (gap > 90 s) and `area_jump` (forward area rise ≥ 2 m²). Only
`wash_plateau` forward-reads area (`_FORWARD_AREA_KINDS`); transit and area_jump read
the same-instant area. `find_candidates` emits **every** blip as a candidate;
`select_active` picks the active set by count XOR explicit-ids XOR confident-only
default; `build_segments` turns the active set into per-room segments. This same
transit-aware decomposition now also feeds the **live** job-queue rollover (see
[07-queue-engine](07-queue-engine.md)) — see the live-detection paragraph below.

**The three consumers reach these stages through a pluggable job-segmenter engine,
not by importing `counter_segmentation` directly** (`learning/job_segmenter_engines.py`,
mirroring the dispatch-engine seam of `queue/dispatch_engines.py`). The adapter
selects an engine via its `job_segmenter.engine` block; `get_job_segmenter_engine(name)`
resolves it, **falling back to the Eufy engine** (`eufy_counter_v1`,
`EufyCounterSegmenter`) for an absent/unknown name — *not* a noop — so live rollover and
learned history keep working byte-for-byte with no adapter registered. The Eufy engine
delegates **verbatim** to the `counter_segmentation` primitives (`find_candidates`,
`build_segments`, and `segment_counters` for its `segment_legacy`), and its
`DEFAULT_TUNING` (`gap_delayed_s`/`gap_transit_s`/`gap_plateau_s`/`area_jump_m2`/`cadence_s`)
is defined *by reference* to that module's constants, so the Eufy path can never drift
from the pre-engine code. **`select_active` stays a framework function** in
`counter_segmentation` — it is pure ranking over the candidate *shape* (`kind` /
`confident` / `strength` / `id`), so it is brand-agnostic and is **not** on the engine;
the engine owns only the brand-specific `find_candidates` / `build_segments` stages. The
cross-engine contract is two TypedDicts (`JobBoundaryCandidate`, `JobSegment`) — the
exact union the primitives already emit — so a future brand emitting the same shape needs
no consumer changes. (The Eufy `kind` literals — `wash_plateau` / `transit` / `area_jump`
/ `weak`, and the `kinds={wash_plateau, area_jump}` legacy filter — stay at the Eufy call
sites as the documented extension point.) The gap/area/cadence thresholds now live in the
adapter's `job_segmenter.tuning` block (see [07-queue-engine](07-queue-engine.md)); the
`counter_segmentation` module constants remain the framework defaults the Eufy engine
references.

**External** (app-started) runs no longer simply over-split into a merge-only card.
At finalize the full candidate pool **and the raw samples** are embedded in the
pending record (schema v2), so the review card can re-segment the run server-side at
any user-set room count or explicit boundary set
(`learning/external_ingest.resegment_pending_record`, exposed by the
`resegment_external_run` service) — not just merge. The default view is the
*confident-only* cuts (matching the pre-v2 segmentation); transit/weak/uncertain cuts
surface as inactive "split here" candidates. `build_pending_record` /
`resegment_pending_record` / `_mark_candidate_confidence` call the resolved engine's
`find_candidates` / `build_segments` (an optional `vacuum_entity_id` selects the
adapter's engine; absent → the Eufy fallback, byte-identical) while importing
`select_active` directly as a framework function. The persisted v2 `gap_transit_s`
field (Eufy: unchanged `60.0`) now sources from the resolved engine tuning rather than
the module constant — same value, moved provenance. See
[28-external-run-ingestion](28-external-run-ingestion.md).

**Pose-based room attribution (W5c).** An app-started run carries no dispatched queue,
so the counter segmenter can only split *time/area* — it can't name *which managed room*
each segment is. A second pluggable seam — the room-attribution engine
(`learning/room_attribution_engines.py`, brand-agnostic `eufy_anchor_winding_v1`; resolved by
`external_ingest._resolve_attribution` from the adapter's `room_attribution.engine`, Eufy
fallback) — recovers the cleaned-room **set** from the run's per-tick room stream
(`pose_samples`). It runs in two modes: **robust** (uses the `cleaning_area` swept-area
delta as the clean-vs-parked-dock separator) and **anchor_only** (a best-effort fallback
when `cleaning_area` is absent, which may false-positive a parked dock — callers gate on
`mode`). The classifier is used two ways at finalize: (1) **enrich** — when counter
segmentation produced segments, label each with its dominant cleaned room and promote that
room to `shortlist[0]` (robust mode only), so the review card opens *pre-answered*; and
(2) **stand-alone** — when counter segmentation produces nothing (the common app-run case),
`build_attributed_job` stands up a pending record straight from the pose attribution (one
segment per cleaned room, swept-m² area, identity pre-filled), tagged with
`attribution_mode` so the card can flag anchor-only results. The raw `pose_samples` are
embedded so the run can be **re-attributed** server-side after an engine fix — the pose-path
sibling of re-segmentation. When there is no pose stream (non-map brand / no live map) every
branch behaves exactly as pre-W5c. **Shipped in 1.8.0 this path extends to Roborock and to
dispatched runs: the per-tick capture source is adapter-declared and the dispatched reconcile
is a third consumer — see §2.4.**

**Boundary classification formula.** The `_classify` function applies a strict 4-branch precedence:

1. **wash_plateau**: gap > `gap_plateau_s` (>90 s) — unambiguous long pause
2. **transit**: gap > `gap_transit_s` (60–90 s) AND area_after < `area_jump_m2` (flat area) — inter-room hop without new floor
3. **area_jump**: area_after ≥ `area_jump_m2` (≥2 m²) — new floor covered, regardless of gap
4. **weak**: short gap with flat area — most likely a pass-turn, not a boundary

So a gap of 70 s with +2.5 m² area is classified **area_jump** (branch 3), not transit.

**Boundary strength ranking.** Each candidate's strength score drives count-based selection (`expected_rooms` mode):

```
strength = _KIND_WEIGHT[kind] + max(area_after, 0.0) + min(gap, 600.0) / 600.0
```

where the kind weights dominate: `{wash_plateau: 4000, transit: 2000, area_jump: 1000, weak: 0}`. Area is added at full m² scale (dominates the gap term). The gap is clamped to 600 s and normalized to [0, 1] as a tie-breaker.

**Worked example:** A gap of 70 s, area_after 0.5 m², classified as transit:

```
strength = 2000.0 + max(0.5, 0.0) + min(70.0, 600.0) / 600.0
         = 2000.0 + 0.5 + 0.117
         = 2000.617  →  ranked above all area_jump and weak
```

The same segmenter also drives **live** room-transition detection: in
`jobs/active_job._maybe_roll_current_room_by_timing`, when the per-vacuum boundary
count (`_live_boundary_count`, via the resolved engine's `find_candidates` + framework
`select_active`, or `engine.segment_legacy` under the disabled kill-switch) exceeds the
recorded completions, it fires `EVENT_ROOM_FINISHED`
(`source="counter_plateau"`) ahead of the timing threshold — a high-confidence,
frame-invariant boundary. Geometry/bounds confirmation is **capability-gated**
(`position_lock_reliable` — the adapter's call; Eufy = false because its frame
drifts), so on Eufy the plateau + timing carry the rollover and the bounds check
never wrongly blocks it, while a brand with a stable lock re-enables it.

At finalization there are **two paths** to the per-room timing blocks, chosen by
`build_completed_job_payload` (`learning/history_store.py`):

- **Strict-order (sequenced) jobs** (`phases` present in `active_job_state`) — each phase cleaned one room and docked, so the
  whole-run counter stream can't be segmented across the per-room dock trips against a
  single last-phase queue. Instead each phase captured its **own** `room_timing` from its
  own counter slice at advance time (`jobs/PhaseRunner._capture_finishing_phase_timing` →
  `_phase_room_timing`, `jobs/phase_runner.py`). `build_completed_job_payload` concatenates
  those per-phase timings in phase order, sets `transitions = []` (the inter-phase gaps are
  dock overhead, not room-to-room transit), and `transit_capture_valid` is `True` only when
  **every** phase captured a timing.
- **Atomic / legacy jobs** (`phases` absent) — called at line 1117 of `build_completed_job_payload`,
  the module-level function `_build_transit_blocks` (`learning/history_store.py` lines 47–117)
  resolves the job-segmenter engine from the adapter (optional `vacuum_entity_id` param;
  absent/unknown → the Eufy fallback) and calls `engine.segment_legacy(...)` — byte-identical
  to the legacy `segment_counters` — then maps the segments onto the dispatched queue order
  (internal: segment K → queue room K).

Either path writes three additive blocks to the job record's `job` object:

| Field | Shape | Meaning |
|---|---|---|
| `room_timings` | `[{room_id, slug, cleaning_start, cleaning_end, cleaning_seconds, cleaning_wall_seconds, area_m2, battery_delta, boundary}]` | Per-room window — incl. exact per-room **`area_m2`, now available for multi-room jobs** |
| `transitions` | `[{from_room_id, from_slug, to_room_id, to_slug, transit_seconds}]` | Inter-room gap (the segment's `gap_before_s` = transit + wash) |
| `transit_capture_valid` | bool | True only when the segment count equals the queued room count |
**`build_completed_job_payload` signature (§2.2 and history_store.py):**

Called from `LearningJobFinalizer.finalize_from_inputs` with ~14 explicit keyword parameters:

```python
def build_completed_job_payload(
    self,
    *,
    vacuum_entity_id: str,              # e.g. "vacuum.alfred"
    job_id: str,                        # e.g. "job_2025-01-15T14-30-42"
    started_at: str,                    # ISO timestamp
    ended_at: str,                      # ISO timestamp
    battery_start: int,                 # % at start
    battery_end: int,                   # % at end
    queue_state: dict[str, Any],        # queue.queue_rooms, queue.queue_room_ids
    payload_state: dict[str, Any],      # resolved_rooms from initial dispatch state
    active_job_state: dict[str, Any],   # running job state: completed_room_ids, room_count, state_transitions, etc.
    used_for_learning: bool = True,     # STORE computes this; finalizer passes it
    outcome_status: str = "completed",  # e.g. "completed", "cancelled", "failed"
    was_cancelled: bool = False,        # separate signal for cancel detection
    was_failed: bool = False,           # separate signal for failure
    was_interrupted: bool = False,      # separate signal for interruption
    is_test_job: bool = False,          # test-run marker
    extra_outcome: dict[str, Any] | None = None,  # additional outcome fields
) -> dict[str, Any]
```

The `used_for_learning` flag is **computed by the store** (see `is_learning_job` gate in §3.1), not passed by the caller. The `LearningJobFinalizer` evaluates blocker conditions and calls the store with the computed flag. All ~14 params are explicit keywords; there is no `inputs` dict parameter — the finalizer assembles the payload from state objects.

`transit_capture_valid` is the **poison guard**: a glitchy run (missed sample,
extra split) sets it `False` so it never corrupts the aggregate, while the
partial timings are still written for audit. A single-room job is valid with an
empty `transitions` list.**Window preparation (`_prepare_window`)** — internal helper used by `find_candidates` and `build_segments`. Normalizes and sorts counter samples by timestamp (UTC-aware parse via `timestamp_utils.parse_timestamp`), trims to the last `cleaning_time` reset (dropping stale pre-reset samples from a prior job), and constructs two monotonic lookup functions:

- `area_at(t)` — returns the cumulative area reached by time t (handles lagged area packets via `bisect_right`)
- `batt_at(t)` — returns the battery level at or before time t

Returns `None` if the stream has no usable signal (empty, or no cleaning_time increments after reset). Both functions are used by `build_segments` to attribute area and battery deltas across a segment, which is why area attribution must be recomputed per active boundary set (the `wash_plateau` forward-reads lagged area, others stay same-instant).

The rebuilder aggregates only `transit_capture_valid` jobs into two **room_stats**
arrays (one source of truth for both the estimator and any access-graph consumer):

- `transit_stats` — per room-pair, in **seconds**: `{from_room_id, to_room_id,
  from_slug, to_slug, sample_count, avg_seconds, seconds_min, seconds_max,
  seconds_stddev}`
- `access_graph_edges` — the same pairs in **minutes** for the estimator:
  `{…, sample_count, transit_minutes_mean, transit_minutes_stddev}`

Each `room_baselines` entry also gains `avg_ingress_transit_seconds` (transit
*into* the room) and `avg_egress_transit_seconds` (transit *out of* it), each with
a `_min/_max/_stddev` band plus `ingress_sample_count` / `egress_sample_count`.
**Reader-side caching (§6 and LearningManager):**

Room stats and accuracy stats are cached in memory (`LearningManager._room_stats_cache` and `_accuracy_stats_cache`, both dicts keyed by `vacuum_entity_id`) to avoid repeated disk reads on every estimate poll. The caches are warm-loaded at startup via `async_preload_learning_stats` (runs on the executor) and are explicitly cleared when stats are rebuilt (`_invalidate_learning_stats_cache`). The cached data lives in the manager's instance, not in `hass.data` — each manager instance (and each vacuum) has its own copy. The estimator reads from the manager's cache and never hits disk during estimates.

**Job-level overhead** (`overhead_observed`, retroactive-safe) is attached to each
job by the finalizer via `compute_overhead_observed(job: dict[str, Any])` (`learning/utils.py` lines 123–160):
returns `{total_overhead_minutes, entry_minutes, inter_room_minutes, return_minutes,
recharge_minutes, wash_minutes}`. Signature reads:

- `duration_minutes` — total job wall time
- `cleaning_time_seconds` (preferred) or `actual_cleaning_minutes` (fallback) — device cleaning counter or single-room state-transition time
- `return_to_dock_minutes` (when present) — docking trip
- `recharge_seconds_accumulated` — mid-job recharge dwell

Formula: `total_overhead_minutes = duration_minutes − cleaning_minutes` (≥ 0, rounded 2dp). The `return` / `recharge` components come from fields present on **every** finalized job — so a plain rebuild populates job-level overhead for the entire historical corpus even though per-room transit is forward-only (`entry` / `inter_room` stay `null` until a valid capture supplies them). `job_stats.json` (schema 4) aggregates these into `avg_overhead_minutes` (+band) and per-component means (`avg_overhead_inter_room_minutes`, etc.).

### 2.3 Accuracy store (`accuracy_stats.json` → `rooms` dict)

A separate file tracking how accurate estimates have been against actuals. Keyed by the **same** `_room_key` as `room_stats` (one shared builder in `utils.py`, so the two can never drift) — which now includes `edge_mopping`, so drift is tracked per edge variant. Updated incrementally after every job (not rebuilt from scratch) via `record_estimate_accuracy` in the estimator; because it is never rebuilt, any entries written under the older key format (before edge was added) are simply orphaned — harmless, and they fall out of use as new keys accumulate.

**Fields per entry:**

| Field | Type | Description |
|---|---|---|
| `slug` | str | Room slug |
| `clean_mode` | str | Cleaning mode |
| `clean_passes` | int | Pass count |
| `is_carpet` | bool | Floor type |
| `clean_intensity` | str | Intensity |
| `map_id` | int | Map |
| `sample_count` | int | Total observations recorded |
| `single_room_sample_count` | int | Observations where actual duration is exact (not allocated) |
| `total_abs_pct_error` | float | Running sum of `abs(actual - estimated) / estimated` |
| `total_signed_error_minutes` | float | Running sum of `actual - estimated` |
| `mean_abs_pct_error` | float | `total_abs_pct_error / sample_count` — used as `accuracy_drift_ratio` in confidence scoring |
| `mean_signed_error_minutes` | float | `total_signed_error_minutes / sample_count` — signed bias |
| `last_updated` | ISO str | Timestamp of last update |

The percentage error formula for one observation:

```
pct_error = abs(actual_minutes - estimated_minutes) / estimated_minutes
```

`0.0` means perfect; `0.20` means 20% off on average.

### 2.4 Native room attribution & area normalization (1.8.0)

The pose-based attribution introduced in §2.2 shipped in 1.8.0 for **both brands** and for
**dispatched** as well as external runs. Three pieces matter for re-implementation.

**Adapter-declared capture source (`room_attribution.source`).** The attribution *engine*
(`eufy_anchor_winding_v1`) is brand-agnostic; *how* each per-tick `current_room` is captured is
declared by the adapter's `room_attribution.source` and read by the run-active sampler
(`listeners/pose_sampler.py`):

- `live_pose` (Eufy) — a raster lookup of the robot pixel in the fork's decoded map
  (`async_get_map_live_pose`); `anchor` / heading are populated.
- `native_current_room` (Roborock) — the live room-**NAME** entity
  (`entities.active_cleaning_target`, e.g. `sensor.<id>_current_room`), slugified and matched to a
  managed room id; no pose is decoded (`anchor` / heading stay `None`).

An absent `source` defaults to `live_pose` (back-compat). The sampler subscribes only when the
adapter declares the signal its source needs (`_can_sample`) and buffers `pose_samples` on **both
external and dispatched** runs (`_SAMPLED_STATUSES = ("external", "started")`). Because the
engine's **robust** clean-vs-park decision keys on the `cleaning_area` swept-m² delta — not on pose
spread / winding — Roborock (no pixel anchor) still resolves cleaned rooms in robust mode; the
`anchor_only` fallback, which needs pose, is the Eufy-only degraded path (it can false-positive a
parked dock, so callers gate on `mode`).

**Dispatched reconcile (`external_ingest.reconcile_dispatched_identity`).** For an **atomic**
dispatched run, the finalizer's positional identity (segment K → queue room K) is reconciled
against the room the pose stream says the robot dwelt in per segment (`_dominant_room` presence;
robust mode only — an anchor-only stream is left untouched). Per `room_timing`:

- **confirm** — pose room == positional room → stamp `pose_confidence="confirmed"`, no change.
- **rescue** — `positional_valid` is `False` (segment count ≠ queue count, so K→K is already
  known-unreliable) → overwrite `room_id` / `slug` with the pose room, stamp
  `pose_correction="rescued"` + `pose_prior_room_id`. The positional guess had nothing to lose and
  the run is already excluded from the aggregate (`transit_capture_valid` False).
- **flag** — `positional_valid` **and** the pose names a *different* room → keep the positional
  assignment, annotate `attribution_disagreement={positional, pose}` for review (the card's
  "Room Mismatch" badge). Never silently overridden; learning inclusion is unchanged.

Strict-order (phased) jobs never call this — each phase already captured its own timing.

**`cleaning_area` unit normalization + sanity (`learning/utils.py`).** HA presents an area sensor
in the box's unit system, so on an imperial HA Eufy's `cleaning_area` reports **ft²** while
Roborock's stays **m²** — a bare read silently mixes units (Eufy areas inflated ~10.76×). Every
capture normalizes to canonical m² via `cleaning_area_to_m2(value, unit)`, honoring the sensor's
live `unit_of_measurement` against `_AREA_TO_M2` (`ft²` → `0.09290304`; an unknown / absent unit is
assumed already-m², never guessed). Swept-area sums **positive per-tick increments**, so a
non-monotonic (reset / drop) counter is re-baselined rather than double-counted. `area_sanity(
attributed_m2, sensor_m2, tolerance=0.10)` checks the attributed per-room **sum** against the
device's own run total (the peak `cleaning_area`, `_max_cleaning_area_m2`): the sensor total is an
upper bound, so `attributed_sum > sensor_total × 1.10` sets `over_attributed` (surfaced as the
`area_over_attributed` job marker; §8.5). `diagnostics.py` adds an `area_units` block
(`detected_unit`, `normalized_m2`, `converted`, `recognized`, plus a warning for an unrecognized
unit).

> Roborock's `cleaning_time` (a bare count of **minutes**) is likewise unit-converted at capture —
> it was previously stored as seconds (60× too low).

---

## 3. Learning Eligibility

### 3.1 `is_learning_job` — the gate

`LearningHistoryStore.is_learning_job(job)` returns `True` only when all of the following hold:

```python
job["record_type"] == "completed_job"
job["outcome"]["status"].lower() == "completed"
bool(job["outcome"]["used_for_learning"]) == True
```

Any job that fails this check is visible in the jobs index and CSV exports but is excluded from `room_stats`, `job_stats`, and all confidence calculations.

### 3.2 Blockers — what sets `used_for_learning = False`

`build_completed_job_payload` (in `learning/history_store.py`) computes a `learning_blockers` list. Any populated blocker forces `used_for_learning = False` on the outcome. The complete set of blocker strings that the system writes:

| Blocker string | Source / Condition |
|---|---|
| `invalid_room_count` | `build_completed_job_payload`: `room_count <= 0` |
| `invalid_duration` | `build_completed_job_payload`: `duration_minutes <= 0` |
| `missing_resolved_rooms` | `build_completed_job_payload`: `resolved_rooms` list is empty |
| `job_cancelled` | `build_completed_job_payload`: `was_cancelled == True` or `status == "cancelled"` |
| `job_failed` | `build_completed_job_payload`: `was_failed == True` or `status == "failed"` |
| `job_interrupted` | `build_completed_job_payload`: `was_interrupted == True` or `status == "interrupted"` |
| `test_job` | `build_completed_job_payload`: `is_test_job == True` or `status == "test"` |
| `floor_time_too_short` | `build_completed_job_payload` reads `cancel_detection.reason` from `extra_outcome` when `cancel_likely == True` (reason is set by `_detect_cancel_likely_run` in `job_finalizer.py`) |
| `early_return_likely_cancelled` | `build_completed_job_payload` reads `cancel_detection.reason` from `extra_outcome` when `cancel_likely == True` (reason is set by `_detect_cancel_likely_run` in `job_finalizer.py`) |

**Blocker computation provenance:** All blockers are computed in `build_completed_job_payload` (lines 1018–1072 of `history_store.py`). The cancel-detection blockers are populated by appending `cancel_detection.get("reason")` from the `extra_outcome` dict parameter when it signals `cancel_likely == True` (line 1067).

Manual exclusion via the `exclude_learning_job` service adds two additional blockers: `manually_excluded` and whatever reason string was passed (default `manual_exclusion`).

### 3.2a Cancel Detection Algorithm

Cancel detection runs only on single-room completed jobs and has two triggers, both computed in `_detect_cancel_likely_run` (`job_finalizer.py`):

**Trigger 1: Floor time too short** — absolute floor threshold

```
actual_cleaning_minutes = (returning_transition_dt - started_dt - paused_seconds) / 60.0
floor_threshold = 1.5 minutes
floor_time_too_short when actual_cleaning_minutes < 1.5
```

The returning transition is found by scanning `state_transitions` in reverse for the last entry where `to_state == "returning"` (after normalizing the task_status entity ID from adapter config). The computation subtracts paused-time seconds to exclude manual pauses. If no returning transition is found, this trigger cannot fire.

**Trigger 2: Early return likely cancelled** — relative short-duration gate

```
expected_room_minutes = timeline[0].minutes from manager.estimate_from_manager(...)
short_threshold = max(min(expected_room_minutes * 0.4, expected_room_minutes), 0.75)
                = 1.0 (default) when expected_room_minutes <= 0

early_return_likely_cancelled when job_duration_minutes < short_threshold
                                   AND a cancel-like transition is observed
```

The cancel-like transition is either a **direct return** (task_status goes from an `active` state straight to `returning`) or a **paused-then-return** (a `paused` state followed by `returning`) — the active / paused / returning states are all adapter-configurable. A service-state exclusion layer (`cancel_service_exclusion_states` vocab) prevents false positives from normal service cycles (low-battery return, mop wash, dust empty). Non-single-room jobs, jobs missing timestamps, or jobs with no state transitions never trigger cancel detection.

> **See also:** [06-job-lifecycle](06-job-lifecycle.md) §7 for the finalization pipeline that evaluates these blockers and writes `used_for_learning` onto the completed job record.

### 3.3 Sanity tag (history snapshot, distinct from the learning gate)

Separate from `used_for_learning`, each job carries an `outcome.sanity_passed` /
`outcome.sanity_flags` pair used only by the **history snapshot** the card renders
(`manager.py::get_learning_history_snapshot`), not by the aggregation gate above. The snapshot
maps known sanity flags (e.g. `invalid_room_count` → an invalid room count was detected) to display text and contributes to the per-job `outlier_score` / the
"suggest exclude" hint.

**Sanity flag computation** (in `build_completed_job_payload`, lines 1019–1048 of `history_store.py`):

Two sanity flags are computed and appended to `sanity_flags` when conditions fail:
- `invalid_room_count` — appended when `room_count <= 0`
- `invalid_duration` — appended when `duration_minutes <= 0`

`sanity_passed` is then computed as `len(sanity_flags) == 0` — it is `True` only when the `sanity_flags` list is empty, and `False` when any flag is present. This is **distinct** from `learning_blockers`, which gate the learning gate (§3.2) — a job with sanity flags may still have `used_for_learning == True` if no learning blockers are present, but it will be flagged in the history snapshot.

**Two rules for history display:**

- **Only an explicit `False` is a failure.** Both the `outlier_score` bump and the
  exclude-suggestion check test `item.get("sanity_passed") is False`, *not* a
  `.get("sanity_passed", True)` default. The jobs index stores the key as `None` for
  records that never set it, so the old default never fired and tagged **every** such
  run as failed. A missing/`None` value now counts as
  *not failed*.
- **Graduated external runs set it `True` explicitly.** `build_graduated_job`
  (`learning/external_ingest.py`) writes `sanity_passed: True` + `sanity_flags: []`
  on the graduated `completed_job` outcome — an external run only graduates after
  passing the tier-1 identity gate (§ [28-external-run-ingestion](28-external-run-ingestion.md)),
  so it is sane by construction, and the explicit value keeps the history view from
  ever reading a missing key as a failure.

---

## 4. Confidence Scoring — Full Math

### 4.1 Constants

```python
_LEARNED_BASE                 = 0.55   # base score when a learned match is found
_DEFAULT_BASE                 = 0.20   # base score when falling back to defaults
_SAMPLE_BONUS_MAX             = 0.25   # maximum bonus from sample count
_SAMPLE_BONUS_SATURATE        = 10     # samples needed to earn full bonus
_VARIANCE_PENALTY_MAX         = 0.25   # maximum penalty from variance
_VARIANCE_PENALTY_CV_THRESHOLD = 0.5  # CV value at which full penalty applies
_INTENSITY_MISMATCH_PENALTY   = 0.15  # penalty when match is at different clean_intensity
_ACCURACY_PENALTY_MAX         = 0.20  # maximum penalty from historical drift
_ACCURACY_PENALTY_THRESHOLD   = 0.20  # drift ratio at which full penalty applies
```

### 4.2 Per-room confidence formula

```
score = base + sample_bonus - variance_penalty - intensity_penalty - accuracy_penalty
score = clamp(score, 0.0, 1.0)  # clamped inside _score_room_confidence
scored = round(score, 4)         # rounded in _confidence_result wrapper (line 172)
```

**Base score:**
```
base = 0.55  if source == "learned"
base = 0.20  if source == "default"
```

**Sample bonus** (saturates at 10 samples):
```
sample_bonus = min(sample_count / 10, 1.0) * 0.25
```

Maximum bonus of `+0.25` is reached at `sample_count >= 10`. A room with 5 samples earns `+0.125`.

**Variance penalty** (only applied when `source == "learned"` and both `avg_minutes > 0` and `minutes_stddev > 0`):
```
cv = minutes_stddev / avg_minutes
variance_penalty = min(cv / 0.5, 1.0) * 0.25
```

The coefficient of variation (CV) measures relative spread. A CV of 0.5 or above triggers the full penalty of `-0.25`. A CV of 0.25 triggers `-0.125`.
**Rounding convention:** Per-room timing, battery, area, and offset metrics round to **2 decimal places** (e.g., `minutes: round(minutes, 2)`). Confidence scores and accuracy drift ratio round to **4 decimal places** (e.g., `confidence_score: round(score, 4)`, `accuracy_drift_ratio: round(drift_ratio, 4)`). The accuracy penalty calculation uses the unrounded drift value; the round happens only in the output dict.

**Intensity mismatch penalty:**
```
intensity_penalty = 0.15  if intensity_mismatch == True
intensity_penalty = 0.0   otherwise
```

`intensity_mismatch` is set to `True` by `_find_room_match` when the returned match was found at a different `clean_intensity` than requested (lookup passes 2–4).

**Accuracy penalty** (based on historical estimate drift):
```
accuracy_penalty = min(accuracy_drift_ratio / 0.20, 1.0) * 0.20
```

`accuracy_drift_ratio` is `mean_abs_pct_error` from the accuracy store (0.0 = perfect, 1.0 = 100% off). A drift ratio of 0.20 (20% average error) triggers the full penalty of `-0.20`. When no accuracy data exists, `accuracy_drift_ratio = 0.0` and no penalty is applied.

### 4.3 Example calculations

**New learned room, 1 sample, no variance, no mismatch, no accuracy data:**
```
base          = 0.55
sample_bonus  = min(1/10, 1.0) * 0.25 = 0.025
variance      = 0.0   (stddev is 0 when n < 2)
intensity     = 0.0
accuracy      = 0.0
score         = 0.55 + 0.025 = 0.575  → "medium"
```

**Learned room, 10 samples, CV = 0.3, no mismatch, drift_ratio = 0.10:**
```
base          = 0.55
sample_bonus  = min(10/10, 1.0) * 0.25 = 0.25
variance      = min(0.3/0.5, 1.0) * 0.25 = 0.15
intensity     = 0.0
accuracy      = min(0.10/0.20, 1.0) * 0.20 = 0.10
score         = 0.55 + 0.25 - 0.15 - 0.10 = 0.55  → "medium"
```

**Default (no learned data):**
```
base          = 0.20
sample_bonus  = 0.0  (sample_count = 0)
variance      = 0.0
intensity     = 0.0
accuracy      = 0.0
score         = 0.20  → "low"
```

### 4.4 Confidence breakpoints

| Label | Score range | `ui_rank` | `ui_variant` |
|---|---|---|---|
| `high` | 0.80 – 1.00 | 3 | `"success"` |
| `medium` | 0.50 – 0.79 | 2 | `"warning"` |
| `low` | 0.00 – 0.49 | 1 | `"error"` |

The score range boundaries are inclusive on both ends. `_breakpoint_for_score` iterates the list in order (high → medium → low) and returns the first match. Scores that fall in gaps (e.g. exactly 0.495) fall through to the last entry (`low`).

### 4.5 Job confidence — why min?

```python
job_confidence_score = min(room_confidence_scores)
```

This is a hard architectural rule documented in the module header: **the weakest room drives the job estimate**. If any single room in the job has uncertain timing, the ETA for the entire job is uncertain — it makes no sense to report high confidence when one room is defaulted. The `_debug` field in the estimate payload also includes `weighted_avg_confidence_score` (the arithmetic mean) for diagnostic use only.

### 4.6 Learning velocity

The number of additional runs needed to reach MEDIUM and HIGH confidence is computed analytically from the scoring formula, assuming zero variance and no penalties:

```python
_SAMPLES_FOR_MEDIUM = ceil((0.50 - 0.55) / 0.25 * 10)   # negative: already there at base
_SAMPLES_FOR_HIGH   = ceil((0.80 - 0.55) / 0.25 * 10)   # = ceil(0.25/0.25*10) = 10
```

In practice `_SAMPLES_FOR_MEDIUM` evaluates to a non-positive number (the base score of 0.55 already clears the 0.50 threshold), so `runs_to_medium` will be 0 immediately. `_SAMPLES_FOR_HIGH` evaluates to 10 — you need 10 clean samples with low variance to reliably reach the `high` tier.

---

## 5. Timing Estimation — Full Math

### 5.1 Room stat lookup — five-pass fallback

`_find_room_match` searches the `room_stats` list in five passes, stopping at the first match. `clean_passes` and `edge_mopping` are kept longest because they move cleaning time the most; `is_carpet` is ~constant per room and `clean_intensity` is the smallest effect, so those relax first:

| Pass | Match dimensions | `mismatch` |
|---|---|---|
| 1 | `map_id + slug + clean_mode + clean_passes + is_carpet + clean_intensity + edge_mopping` (exact) | `False` |
| 2 | ignore `clean_intensity` (keep passes, carpet, edge) | `True` |
| 3 | ignore `is_carpet` (keep passes, edge) | `True` |
| 4 | ignore `edge_mopping` (keep passes) | `True` |
| 5 | ignore `clean_passes` | `True` |

When no match is found at any pass, the room gets `source = "default"` with hardcoded fallbacks:
- `avg_minutes = 6.0`
- `avg_battery_used = 0.8`

### 5.2 Room timeline computation

The estimator walks `ordered_rooms` in sequence, accumulating a `cumulative_minutes` cursor. All aggregated stats (per-room `avg_minutes`, `avg_battery_used`, per-room time/battery offsets, area) and room-level stats are rounded to **2 decimal places**. The only exception is `minutes_stddev` (and all `*_stddev` fields), which round to **4 decimal places**:

```
for each room (position 1..N in output, 0..n-1 internally):
    transit_before = 0.0 if position == 1 else learned inter-room leg (§5.3)
    cumulative_minutes += transit_before   # travel time, folded into the timeline
    start_offset = cumulative_minutes
    cumulative_minutes += minutes          # learned avg_minutes or default 6.0
    end_offset = cumulative_minutes
    eta_at = job_start_dt + end_offset (minutes)
```

Each room entry carries `start_offset_minutes`, `end_offset_minutes`, `eta_at` (ISO timestamp), `estimated_transit_minutes_before`, and `transit_source`. The first room has `estimated_transit_minutes_before = 0.0` and `transit_source = "none"`; rooms 2–N carry learned inter-room legs folded into the offsets so travel time is positioned *between* rooms rather than lumped at the end. Their sum equals `overhead.transition_minutes` (§5.3). The dock → first room leg stays in `startup` overhead. **Position is 1-indexed: `position` ranges from 1 to N.** Each entry also carries `estimated_area_m2` (the learned per-room area) and feeds confidence/velocity from the area-gated `timing_sample_count` (not the raw `sample_count`), since `avg_minutes` is computed from the gated samples (§2.1). The ETA anchor is `started_at` when provided; otherwise `utc_now()` at estimate time. Each entry also carries `estimated_area_m2` (the learned per-room area) and feeds confidence/velocity from the area-gated `timing_sample_count` (not the raw `sample_count`), since `avg_minutes` is computed from the gated samples (§2.1). The ETA anchor is `started_at` when provided; otherwise `utc_now()` at estimate time.

### 5.3 Overhead computation

After all rooms are summed, overhead is computed and added to `room_minutes_total`:

```
total_minutes = room_minutes_total + overhead_minutes
```

**Overhead components:**

| Component | Formula | Description |
|---|---|---|
| startup | `1.0` (fixed) | Pre-clean startup time |
| transitions | Σ per-room learned transit (fallback chain below); `max(room_count - 1, 0) * 0.75` at cold start | Navigation between room boundaries |
| recharge | `total_battery_estimate * 0.05` | 0.05 minutes per 1% battery estimated used |
| mop wash | `floor(projected_mop_minutes / wash_interval) * 1.5` | Only in `by_time` mode |
| dust empty | `(room_minutes_total / 10.0) * 0.3` | 0.3 minutes per 10 job minutes |
| return | `1.0` (fixed) | Return-to-dock trip |

**Mop wash detail:**

The wash mode and interval are read live from HA entities whose IDs are resolved from the adapter registry config — not string-formatted in the estimator:

```
mode entity:     adapter_cfg["entities"]["wash_frequency_mode"]
interval entity: adapter_cfg["entities"]["wash_frequency_value_time"]
```

`_load_mop_wash_config` calls `_get_adapter_config(vacuum_entity_id)` and reads those keys from its `entities` dict. The Eufy adapter populates them via `build_entity_id(...)`, so for Eufy they resolve to `select.{object_id}_wash_frequency_mode` / `number.{object_id}_wash_frequency_value_time` (where `object_id` is the part of the vacuum entity id after the dot, e.g. `alfred` from `vacuum.alfred`).

The interval is clamped to `[15.0, 25.0]` minutes and defaults to `20.0` when unavailable.

Wash cycles are only counted when `mode == "by_time"` and `projected_mop_minutes > 0`:
```
wash_cycle_count = floor(projected_mop_minutes / wash_interval_minutes)
mop_wash_minutes = wash_cycle_count * 1.5
```

`projected_mop_minutes` is the sum of `avg_minutes` for all rooms whose `clean_mode` is `vacuum_mop` or `mop`.

**Learned transition fallback chain:**

`transitions` is no longer a flat constant. For each room boundary,
`_lookup_transit_minutes` resolves the inter-room leg most-specific-first, and the
per-room legs are summed into `overhead.transition_minutes`
(`overhead.transition_source` records which tier won):

| Tier | Source | `transition_source` |
|---|---|---|
| 1 | Exact `from→to` edge in `access_graph_edges` (`sample_count ≥ 1`) | `learned_pairs` |
| 2 | Per-room ingress average (`room_baselines.avg_ingress_transit_seconds`) | `learned_room` |
| 3 | Job-level global per-boundary average: `avg_overhead_inter_room_minutes ÷ (avg_room_count − 1)` | `learned_global` |
| 4 | The `_TRANSITION_PER_ROOM = 0.75` constant (fallback, used at cold start / adapters without `cleaning_time`) | `default` |

**Overhead constants:**
- `_RECHARGE_PER_BATTERY_PCT = 0.05` — recharge time per 1% battery used
- `_DEFAULT_MOP_WASH_CYCLE_MINUTES = 1.5` — minutes per mop wash cycle
- `_DEFAULT_WASH_INTERVAL_MINUTES = 20.0` — fallback interval when wash mode has no readable state

A never-observed leg always degrades cleanly to the next tier, so an estimate is
always producible. With no learned data at all, every leg returns the constant and
`overhead.transition_minutes` equals the legacy `max(room_count - 1, 0) * 0.75` —
**backward-compatible** at cold start and on adapters without `cleaning_time`.
(Mixed sources across boundaries report `transition_source: learned_mixed`.)

### 5.4 Timeline reanchoring (`reanchor_timeline`)

Called from `EufyVacuumManager.get_job_progress_snapshot` on every snapshot
poll after at least one room has completed (`completed_rooms` is non-empty).
Reanchoring is NOT event-driven — it is recalculated on each card poll. The
algorithm replaces estimated durations for completed rooms with actual
measurements, then recomputes remaining ETAs from the new elapsed total.

**Inputs:**
- `original_estimate` — the full estimate dict produced at job start
- `completed_rooms` — list of `{room_id, actual_duration_minutes}` or `{slug, actual_duration_minutes}` entries
- `reanchor_at` — ISO timestamp for offset recalculation base (defaults to `utc_now()`)

**ETA anchor:** Remaining room ETAs are anchored from the **original job start** (`original_estimate["started_at"]`), not from `reanchor_at`. The `reanchor_at` parameter is used only as a fallback if `started_at` is missing. This ensures that all per-room offsets remain consistent with the original job timeline.

**Algorithm:**

```
actual_elapsed = 0.0
remaining_cursor = 0.0

for each room in original_timeline:
    if room has actual_duration:
        # completed room: use real data
        start_offset = actual_elapsed
        actual_elapsed += actual_duration
        end_offset = actual_elapsed
        entry.completed = True
    else:
        # remaining room: shift by actual elapsed + accumulated remaining
        estimated_minutes = room.minutes
        start_offset = actual_elapsed + remaining_cursor
        remaining_cursor += estimated_minutes
        end_offset = actual_elapsed + remaining_cursor
        entry.reanchored = True

total_minutes = actual_elapsed + remaining_cursor + original_overhead_minutes
job_eta_at = job_start_dt + total_minutes
```

After the loop, the first non-completed room gets `current = True`; all others get `current = False, remaining = True`.

The overhead is carried over unchanged from the original estimate — it is not recomputed on reanchor. `estimated_transit_minutes_before` / `transit_source` survive on each entry via the `dict(room)` copy, but reanchored offsets fold all overhead at the tail (actuals dominate live progress) rather than re-positioning per-room transit.

---

## 6. Stale Detection

```python
_STALE_THRESHOLD_DAYS = 30
```

`_is_stats_stale` returns `True` when:
- `room_stats_data` is `None` or empty, or
- `room_stats_data["rebuilt_at"]` is `None` or unparseable, or
- `(utc_now() - rebuilt_at).days > 30`

When `stats_stale == True`, the estimate payload includes `"stats_stale": True` and the card should display a warning that the learned data may be out of date. The stale flag does **not** change any timing estimate values — it is purely advisory.

The rebuilder writes `rebuilt_at` as an ISO timestamp whenever `rebuild_all` completes. The cache in `LearningManager` stores the last loaded `room_stats_data`, so the staleness check uses the cached `rebuilt_at` without a disk read on the event loop.

---

## 7. Trouble Rooms — Full Math

### 7.1 When `_update_trouble_rooms_log` is called

Called at the end of every `finalize_from_inputs` execution, regardless of job outcome. It runs after the completed job JSON is written and after stats are rebuilt. It updates a single overwrite file: `live/trouble_rooms.json`.

### 7.2 Tracking logic

The function processes every room ID that was in `queue.queue_room_ids` for the finalized job.

**For `outcome_status == "completed"` jobs:**
- `active_completed = queued_room_ids` (all rooms treated as cleaned — no missed rooms)

**For all other outcomes:**
- `active_completed` is read from `active_job_state["completed_room_ids"]`

`missed_ids = set(queued_room_ids) - set(active_completed)`

For each `room_id` in `queued_room_ids`:

```python
entry["run_count"] += 1
if room_id in missed_ids:
    entry["miss_count"] += 1
    entry["last_missed_at"] = ended_at
else:
    entry["last_cleaned_at"] = ended_at

run_count = max(entry["run_count"], 1)
entry["miss_rate"] = round(entry["miss_count"] / run_count, 3)
entry["is_trouble"] = (entry["miss_count"] >= 2 and entry["miss_rate"] >= 0.33)
```

### 7.3 `is_trouble` threshold

A room is flagged `is_trouble = True` when **both** conditions hold:
- `miss_count >= 2` — missed in at least 2 separate jobs
- `miss_rate >= 0.33` — missed in at least 33% of all jobs it was queued for

This two-condition gate prevents false positives: a room missed once out of one job has a 100% miss rate but does not qualify (miss_count < 2). A room missed twice out of 10 jobs has a miss_rate of 0.20 which does not qualify (below 0.33).

### 7.4 File location

```
eufy_vacuum/learning/{vacuum_slug}/live/trouble_rooms.json
```

Schema (top level):
```json
{
  "schema_version": 1,
  "record_type": "trouble_rooms_log",
  "vacuum_entity_id": "vacuum.alfred",
  "updated_at": "<ISO>",
  "rooms": {
    "3": {
      "room_id": 3,
      "name": "Kitchen",
      "run_count": 8,
      "miss_count": 3,
      "miss_rate": 0.375,
      "is_trouble": true,
      "last_missed_at": "<ISO>",
      "last_cleaned_at": "<ISO>"
    }
  }
}
```

---

## 8. Stats Rebuilder

### 8.1 What `rebuild_all` does

`LearningStatsRebuilder.rebuild_all(vacuum_entity_id, rebuild_csv=False)` performs a full, from-scratch rebuild:

1. Loads **all** completed job JSON files from `jobs/` via `load_all_completed_jobs`.
2. Filters to learning jobs (`is_learning_job == True`) → `learning_jobs` list.
3. Calls `build_job_stats_payload(jobs=learning_jobs)` → writes `learned/job_stats.json`.
4. Calls `build_room_stats_payload(jobs=learning_jobs)` → writes `learned/room_stats.json`.
5. Calls `build_jobs_index_payload(jobs=all_jobs)` (uses ALL jobs, not just learning jobs) → writes `learned/jobs_index.json`.
6. If `rebuild_csv=True`: calls `rebuild_csv_exports(jobs=all_jobs)` → writes `exports/jobs_flat.csv` and `exports/rooms_flat.csv`.

The `rebuilt_at` timestamp written into both `job_stats.json` and `room_stats.json` is used by the stale detection logic. `jobs_index.json` also carries `rebuilt_at`.

### 8.2 What gets recalculated

**`job_stats.json` (schema 4, nested structure):**

Top-level wrapper:
```json
{
  "schema_version": 4,
  "vacuum_entity_id": "vacuum.alfred",
  "rebuilt_at": "<ISO>",
  "job_stats": { ... all aggregates below ... }
}
```

Recalculated fields in `job_stats` object:

| Field | Type | Description |
|---|---|---|
| `total_jobs` | int | Count of learning jobs |
| `avg_duration_minutes` | float | Mean job duration |
| `avg_battery_used` | float | Mean battery consumed per job |
| `avg_robot_water_used_ml` | float | Mean robot cleaning water (not dock) |
| `avg_water_overhead_ml` | float | Mean dock wash + refill water |
| `avg_total_water_used_ml` | float | Total water (robot + overhead) |
| `min_total_water_used_ml` | float | Min total water |
| `max_total_water_used_ml` | float | Max total water |
| `avg_room_count` | float | Mean rooms per job |
| `avg_drift_minutes` | float | Signed mean prediction error |
| `avg_abs_drift_minutes` | float | Absolute magnitude prediction error |
| `min_duration_minutes` | float | Shortest job |
| `max_duration_minutes` | float | Longest job |
| `min_battery_used` | float | Min battery consumed |
| `max_battery_used` | float | Max battery consumed |
| `avg_overhead_minutes` | float | Total overhead (startup + transitions + return + recharge + mop wash + dust empty) |
| `min_overhead_minutes` | float | Min total overhead |
| `max_overhead_minutes` | float | Max total overhead |
| `overhead_minutes_stddev` | float | Overhead variance |
| `avg_overhead_entry_minutes` | float | Pre-clean entry time (only when captured) |
| `avg_overhead_inter_room_minutes` | float | Inter-room transit time (only when captured) |
| `avg_overhead_return_minutes` | float | Return-to-dock time (only when captured) |
| `avg_overhead_recharge_minutes` | float | Recharge time (retroactive, all jobs) |
| `overhead_sample_count` | int | Jobs contributing to total overhead |
| `overhead_entry_sample_count` | int | Jobs with captured entry time |
| `overhead_inter_room_sample_count` | int | Jobs with captured inter-room time |
| `latest_job_ended_at` | ISO str or null | Most recent job end timestamp |

**`room_stats.json` (schema 6):**

Recalculated fields per room-settings combination and per-room baseline:

`room_stats` array: `avg_minutes`, `minutes_stddev`, `minutes_min`, `minutes_max`, `avg_battery_used`, `avg_drift_minutes`, `avg_abs_drift_minutes`, `sample_count`, plus `avg_area_m2`, `area_m2_min`, `area_m2_max`, `area_m2_stddev`, `area_sample_count`, `partial_excluded_count`, `timing_sample_count` (per room-settings key)

`room_baselines` array: one entry per `{map_id, room_slug}` with full per-room aggregates collapsed across all settings, plus `by_clean_times` and `by_edge_mopping` setting breakouts (each carrying `sample_count`, `avg_minutes`, `minutes_min/max/stddev`, `avg_battery_used`), and `avg_ingress_transit_seconds` / `avg_egress_transit_seconds` (+ bands, sample counts) for transit into and out of the room

**`jobs_index.json` (schema 1):**

Top-level structure:
```json
{
  "schema_version": 1,
  "vacuum_entity_id": "vacuum.alfred",
  "rebuilt_at": "<ISO>",
  "job_count": 42,
  "jobs": [ ... ],
  "rooms": [ ... ],
  "room_profiles": [ ... ]
}
```

`jobs` array (one entry per completed job, all outcomes):
- `job_id`, `started_at`, `ended_at`, `duration_minutes`, `room_count`, `room_slugs` (list)
- `status`, `used_for_learning`, `sanity_passed`
- `battery_used`, `robot_water_used_ml`, `water_overhead_ml`, `total_water_used_ml`
- `cancel_detection` (object), `mid_job_recharge_observed` (bool)

`rooms` array (one entry per unique room slug, aggregated across all jobs):
- `room_slug`, `run_count`, `learning_run_count`, `avg_duration_minutes`, `avg_battery_used`
- `avg_robot_water_used_ml`, `avg_water_overhead_ml`, `avg_total_water_used_ml`
- `last_job_id`, `last_ended_at`, `status_counts` (dict), `profile_keys` (dict)

`room_profiles` array (one entry per unique `_room_profile_key(room)` — settings signature keyed by slug + profile_name + mode + intensity + fan_speed + water_level + clean_passes + carpet + edge_mopping):
- `profile_key`, `room_slug`, `selected_profile_name`, `resolved_profile_name`
- `clean_mode`, `clean_intensity`, `fan_speed`, `water_level`, `clean_passes`, `carpet`, `edge_mopping`
- `run_count`, `learning_run_count`, `avg_duration_minutes`, `avg_battery_used`
- `avg_robot_water_used_ml`, `avg_water_overhead_ml`, `avg_total_water_used_ml`
- `last_job_id`, `last_ended_at`, `status_counts` (dict)

The accuracy stats file (`learned/accuracy_stats.json`) is **not** rebuilt — it is only updated incrementally by `record_estimate_accuracy` after each job.

### 8.3 When to run a manual rebuild

Run `eufy_vacuum.rebuild_learning_stats` when:
- You have manually edited or deleted completed job JSON files.
- You have excluded or restored jobs via `exclude_learning_job` / `restore_learning_job` (these trigger an automatic rebuild internally).
- You suspect the learned stats are stale after a HA restart where finalization events did not fire.
- The `stats_stale` flag appears in estimate payloads and you know recent jobs were completed.

Under normal operation, a rebuild fires automatically at the end of every `finalize_learning_job` service call when `rebuild_stats=True` (the default).

### 8.4 `schema_version`

`room_stats.json` is written with `schema_version: 6` (6 added per-room area for multi-room jobs + the area-quality gate; 5 added `transit_stats` / `access_graph_edges` and the `room_baselines` ingress/egress bands; 4 added `avg_area_m2` and the `room_baselines` setting buckets — bumped from 3). `job_stats.json` is written with `schema_version: 4` (4 added the `overhead_observed` aggregates), and `jobs_index.json` with `schema_version: 1`. There is no migration path for older schema versions — a full rebuild produces fresh files. Additive fields are backward-compatible regardless: the estimator reads stats by key and ignores unknown ones.

### 8.5 Learning-processing toggle and self-heal index

**Collect-always, process-on-demand.** A box-level toggle
(`data["learning_processing_enabled"]`, default `True`) gates the *heavy* per-run stats rebuild
without ever dropping data. When it is **off**, a completed run is still collected (its JSON is
written to `jobs/`) but the rebuild is skipped — `finalize_learning_job`'s effective rebuild is
`rebuild_stats and learning_processing_enabled` — and a per-vacuum pending counter
(`data["learning_pending_runs"][vacuum]`) is bumped. Two services drive it (both flip *all*
vacuums):

- `set_learning_processing(enabled)` — sets the toggle. Turning it **on** after it was off
  immediately reprocesses the backlog (a full rebuild from history via
  `async_process_pending_learning`); turning it **off** just stops per-run rebuilds.
- `process_pending_runs` — reprocesses the collected-but-unprocessed backlog (full rebuild from
  history) and clears the pending counters **without** turning per-run processing back on.

A card snapshot surfaces `learning_processing: {enabled, pending_runs, has_last_estimate}` so the
UI can show an "N pending" hint.

**Self-heal jobs-index detector.** `jobs_index.json` gained card-facing marker keys over time
(`status`, `origin`, `has_attribution_disagreement`, `area_over_attributed`). On the next
history-snapshot read (`manager.get_learning_history_snapshot`), an index whose first job entry is
missing **any** of those keys is treated as stale and rebuilt **once** from full history
(`build_jobs_index_payload`), so existing runs retroactively pick up fields added since the index
was last built — no manual "Process pending runs" needed. Requiring all four keys means every such
upgrade self-heals (e.g. the `origin` key back-fills the External badge / Area-Cleaned cell and
sheds a stale "Sanity Failed" flag on old graduated external runs).

---

## 9. File Layout and Constructors

All learning files live under:
```
{config_dir}/eufy_vacuum/learning/{vacuum_slug}/
```

where `vacuum_slug` is the object_id part of the vacuum entity ID (e.g. `alfred` from `vacuum.alfred`).

The full directory tree per vacuum:

```
eufy_vacuum/learning/{vacuum_slug}/
├── jobs/
│   └── {job_id}.json          # one file per finalized job (all outcomes)
├── learned/
│   ├── job_stats.json         # aggregate job-level stats (learning jobs only)
│   ├── room_stats.json        # per-room timing stats (learning jobs only)
│   ├── jobs_index.json        # filter-friendly index (all jobs)
│   └── accuracy_stats.json    # estimate accuracy tracking (all jobs with estimates)
├── exports/
│   ├── jobs_flat.csv          # flat job export (optional, rebuild_csv=True)
│   └── rooms_flat.csv         # flat room export (optional, rebuild_csv=True)
└── live/
    ├── last_job_snapshot.json # live snapshot written at job start
    ├── incomplete_run.json    # last incomplete job log (single overwrite)
    └── trouble_rooms.json     # chronic trouble rooms counter (single overwrite)
```

**Access graph debug files** are written to a separate sibling path:
```
eufy_vacuum/learning/mapping/{vacuum_slug}/access_graph_{map_id}.json
```

**Naming conventions and I/O safety:**

- Job files: `{job_id}.json` where `job_id` defaults to `job_{YYYY-MM-DDTHH-MM-SS}` when not supplied.
- All JSON files use 2-space indentation, UTF-8 encoding, trailing newline.
- CSV files write header on first row if the file is empty or does not exist.
- **JSON writes are atomic:** `LearningHistoryStore.write_json` writes to a `tempfile.mkstemp()` in the target directory, then `os.replace()`s it into place. A reader or a process crash mid-write never sees a half-written file — the swap is atomic at the OS level.

### 9.1 Constructors and initialization

All learning system classes are bound to Home Assistant at instantiation:

| Class | Constructor | Role |
|---|---|---|
| `LearningHistoryStore` | `__init__(self, hass: HomeAssistant)` | File I/O for all JSON and CSV. Base dir from `hass.config.config_dir`. |
| `LearningStatsRebuilder` | `__init__(self, hass: HomeAssistant)` | Rebuilds stats. Owns `LearningHistoryStore` instance. |
| `LearningJobFinalizer` | `__init__(self, hass: HomeAssistant)` | Finalizes completed jobs. Owns `LearningHistoryStore` and `LearningStatsRebuilder` instances. |
| `LearningManager` | `__init__(self, hass: HomeAssistant)` | Orchestrates all modules. Owns `LearningHistoryStore`, `LearningJobFinalizer`, `LearningStatsRebuilder`, and `LearningEstimator` instances. |
| `LearningEstimator` | `__init__(self, hass: HomeAssistant)` | Estimation and confidence math. Pure computation but needs `hass` for entity lookups. |

Each instance constructs its own collaborators; there is no shared singleton registry. The typical entrypoint is `LearningManager`, which creates the others.

### 9.2 `LearningPaths` dataclass

```python
@dataclass(slots=True)
class LearningPaths:
    root: Path
    jobs_dir: Path
    learned_dir: Path
    exports_dir: Path
    live_dir: Path
```

Paths are `pathlib.Path` objects. Instances are created by `LearningHistoryStore.get_paths(vacuum_entity_id)` (returns path structure without creating dirs) or `ensure_dirs(vacuum_entity_id)` (creates all dirs and returns paths). Path getters like `jobs_csv_path(vacuum_entity_id)` call `ensure_dirs()` internally.

**Mapped fields:**

| Field | Path |
|---|---|
| `root` | `{base_dir}/{vacuum_slug}` |
| `jobs_dir` | `root/jobs` |
| `learned_dir` | `root/learned` |
| `exports_dir` | `root/exports` |
| `live_dir` | `root/live` |

### 9.3 Host contract — attaching learning to a host

Learning is written to **attach** to a host, not to import one. Every class takes only `hass` in its constructor (§9.1); the core manager arrives as a **method argument** (`estimate_from_manager(manager, …)`, `save_live_snapshot_from_manager`, the finalizer's `_collect_finalization_inputs`), and `ExternalRunManager` alone holds it as an injected back-reference (`ExternalRunManager(manager=self)`). The estimation engine — `estimator`, `stats_rebuilder`, `job_segmenter_engines`, `room_attribution_engines`, `counter_segmentation`, `utils` — has **no core-manager coupling at all**; it is pure over its inputs. So learning depends on its host through exactly two small contracts, and this section is their spec.

**Reconstruction / re-hosting note.** To rebuild — or mount elsewhere — the learning engine, you implement `LearningHost` and supply a `BrandFacts`. Nothing else about the host's internals is needed. In particular the host's persistent `data` dict is **never touched directly** (all access is method-mediated, below), and learning keeps its **own** file store (`config_dir/eufy_vacuum/learning/<vacuum>/`, `hass`-only), disjoint from the host's `.storage`.

**How the host is reached** — three channels, one object:

- *Injected per call* — `LearningManager` / `LearningJobFinalizer(hass=…)`; the manager is passed to the methods that need it.
- *Held back-ref* — `ExternalRunManager(manager=…)` keeps `self._manager` (the only class that does).
- *Runtime lookup* — `hass.data[DOMAIN]["runtime"]` returns the same manager (the service layer).

#### `LearningHost` — the method surface the host must provide

```python
from typing import Any, Protocol, runtime_checkable
from homeassistant.core import HomeAssistant

@runtime_checkable
class LearningHost(Protocol):
    """What the learning engine needs from whatever core manager hosts it.
    Signatures inferred from call sites; vacuum_entity_id / map_id are keyword args."""

    hass: HomeAssistant   # also uses .states, .bus, .async_*, .data, .config, .loop

    # READS — pure observation (idempotent)
    def get_known_map_ids(self, vacuum_entity_id: str) -> list[str]: ...
    def get_active_job(self, *, vacuum_entity_id: str, map_id: str) -> dict[str, Any]: ...
    def get_managed_rooms(self, *, vacuum_entity_id: str, map_id: str) -> dict[str, Any]: ...
    def get_queue_state(self, *, vacuum_entity_id: str, map_id: str) -> dict[str, Any]: ...
    def get_payload_state(self, *, vacuum_entity_id: str, map_id: str) -> dict[str, Any]: ...
    def get_vacuum_capabilities(self, *, vacuum_entity_id: str, refresh: bool = True) -> dict[str, Any]: ...
    def get_planned_job_estimate(self, *, vacuum_entity_id: str, map_id: str,
                                 resolved_rooms: list[dict[str, Any]] | None = None) -> dict[str, Any]: ...
    def get_dock_events(self, *, vacuum_entity_id: str) -> dict[str, Any]: ...   # optional (None-guarded)

    # WRITES — the irreducible core (external-run lifecycle)
    def start_external_capture(self, *, vacuum_entity_id: str, map_id: str) -> dict[str, Any]: ...
    def clear_active_job(self, *, vacuum_entity_id: str, map_id: str) -> dict[str, Any]: ...
    async def async_save(self) -> None: ...

    # WRITES — needed ONLY by the resume-incomplete-run service (host may omit)
    def set_rooms_enabled_subset(self, *, vacuum_entity_id: str, map_id: str,
                                 room_ids: list[int] | list[str]) -> dict[str, Any]: ...
    def build_queue(self, *, vacuum_entity_id: str, map_id: str) -> dict[str, Any]: ...
    async def start_selected_rooms(self, *, vacuum_entity_id: str, map_id: str,
                                   confirm_reduced_run: bool = False,
                                   path_block_action: str | None = None) -> dict[str, Any]: ...

    # Currently PRIVATE on the core manager — promote to public for a clean contract
    def resolve_active_map_id(self, vacuum_entity_id: str) -> str | None: ...              # was _resolve_active_map_id
    def get_station_clean_water_percent(self, *, vacuum_entity_id: str) -> float | None: ...  # was _get_station_clean_water_percent
    def protected_room_config(self, room: dict[str, Any]) -> dict[str, Any]: ...           # was _protected_room_config
```

The **reads** are pure observation. The three writes `start_external_capture` / `clear_active_job` / `async_save` are the **irreducible core** — the external-run lifecycle, the only writes the held `self._manager` back-ref performs. `build_queue` / `start_selected_rooms` / `set_rooms_enabled_subset` are used **only** by the resume-incomplete-run service and can be optional on a host that doesn't offer it. A fourth private call, `_get_learning_manager`, is **not** in the contract: it is re-entrant (learning fetching itself) — hand the finalizer its estimator seam directly instead.

`hass` must expose `states.get`, `bus.async_fire`, `async_create_task`, `async_add_executor_job`, `loop.call_soon_threadsafe`, `config.config_dir`, and a `data` dict carrying the manager at `data[DOMAIN]["runtime"]` (and, optionally, sibling subsystems at `DATA_ERROR_TRACKER` / `DATA_BATTERY` for the best-effort error-harvest read and battery-metrics push).

#### `BrandFacts` — everything learning needs to know about a brand

Learning reaches the brand adapter for only a handful of scalar facts. It **never branches on capability** — no pass-count caps, no mop/water-settable flags; `clean_times` / `clean_passes` ride through as *observed data*, used only as estimate lookup keys.

```python
from typing import Any, Protocol

EngineSpec = tuple[str | None, dict[str, Any] | None]   # (engine_name, tuning_overrides)

class BrandFacts(Protocol):
    """Everything learning needs to know about a brand — replaces direct adapter reads."""

    brand: str | None                                     # cosmetic label only

    def entity_id(self, key: str) -> str | None: ...      # "task_status", "cleaning_time", "cleaning_area",
                                                          # "wash_frequency_mode", "wash_frequency_value_time"
    def alias_map(self, key: str) -> dict[str, str]: ...  # "clean_mode", "clean_intensity", "fan_speed",
                                                          # "water_level", "wash_frequency_mode"

    mid_run_statuses: frozenset[str]                      # docked-but-will-resume
    cancel_service_exclusion_states: frozenset[str]       # early-return explained by a service call
    cancel_detection_states: dict[str, str | list[str]]   # {"active": …, "returning": …, "paused": …}

    job_segmenter: EngineSpec                             # (engine name, tuning) — resolved via learning's own registry
    room_attribution: EngineSpec
```

The engine *registry* (`job_segmenter_engines.py`, `room_attribution_engines.py`) lives **inside** learning and is brand-agnostic; `BrandFacts` supplies only the *selection*, not the implementation. A host that provides a `BrandFacts` with a noop segmenter and empty vocab still gets a fully functional timing/estimation learner, with no brand specifics at all.

#### Extraction status (2026-07-11) — Waves 1–3 landed; the rest is deliberate design, not cruft

The seam-tightening this draft first called "cruft" split into two on contact with the code: real age-artifacts (closed) and **deliberate, documented design that was mis-labelled** (left as-is).

**Closed** — learning now imports nothing from `core.manager` at module top and reads the host + brand through clean seams:

- **Promoted** the 3 private host methods to public; **dropped** the re-entrant `_get_learning_manager` (the finalizer takes an injected `estimate_fn` instead). *(Waves 2a/2b — 4be0544, 15b4812)*
- **Owned** `EXTERNAL_FINALIZE_GRACE_S` / `EXTERNAL_GRACE_MAX_RECHECKS` in `learning/constants.py`, which killed the import cycle **and** the `learning/__init__.py` deferral. *(Wave 1 — e278465)*
- **Swapped** every direct adapter read for `BrandFacts` (`learning/brand_facts.py`) — the whole package now reads the brand through exactly one seam. *(Wave 3 — 4465067 → 31b86c6)*

**NOT cruft — left as designed** (this draft was wrong to flag them; see `job_segmenter_engines.py`'s own docstring):

- **`select_active` stays a framework function** in `counter_segmentation`. It's brand-agnostic *by intent* — pure ranking over the `JobBoundaryCandidate` shape — so the external-review wizard's count/toggle logic is uniform across brands. Moving it into a per-brand plugin would break that uniformity, not fix a mislocation.
- **The Eufy fallback is intentional.** `get_job_segmenter_engine` falls back to the Eufy engine for an absent/unknown name so no-adapter / legacy devices keep segmenting **byte-for-byte**; flipping it to noop is a behavior change the code explicitly warns against. `NoopJobSegmenter` is registered for a genuinely signal-less brand but is deliberately *not* the default.
- **The engine layer is already a plugin system** (the registry + adapter-declared `job_segmenter.engine`; both Eufy and Roborock declare theirs). The Eufy engine living in learning with a by-reference-tuning verbatim delegation is a deliberate anti-drift design (the `[JE-7]` fidelity battery). Relocating it to `adapters/eufy` is a marginal portability gain for a Eufy-first integration — a deliberate choice if ever wanted, not a cleanup.

**Remaining optional polish:** the two sibling pushes (battery-metrics push + error-harvest read) can become injected sinks — they're already `None`-guarded, so they degrade gracefully today.

#### Why this contract is bigger than learning

The engine under this contract is **value-agnostic** — it learns a weighted estimate of *some* number from runs, indifferent to whether that number is minutes, battery-percent, water, or a boundary. **Battery, water, and bounds already reuse it.** So `LearningHost` + `BrandFacts` are not learning's contract alone — they are the **shared estimation engine's** contract. Each sibling attaches by supplying different *reads* and *weights* while the *use* stays identical: configurations, not copies. Formalized once here, they define how time / battery / water / bounds *all* mount on a host.

---

## 10. Adding a New Learning Metric

To add a new metric to the learning system, touch these locations in order. (`avg_area_m2` is used below as a worked example — its `room_stats` half is already implemented at schema v4.)

### Step 1 — Collect the raw value at finalization

In `job_finalizer.py`, `finalize_from_inputs` assembles the `completed_job` payload. The raw value (e.g. from a HA sensor) should be read in `_collect_finalization_inputs` alongside `cleaning_area_m2` and stored in the `inputs` dict. Then in `finalize_from_inputs`, write it onto the appropriate section of `completed_job`.

### Step 2 — Store it per job

The `completed_job` dict written to `jobs/{job_id}.json` is the source of truth. Add your field to the appropriate nested section (e.g. `job.cleaning_area_m2` already exists). No schema change is needed — JSON files accept additional keys.

### Step 3 — Aggregate in `stats_rebuilder.py`

In `build_room_stats_payload`, the rebuilder loops over all rooms in all learning jobs. Collect per-room samples and average them in the output block, writing the result into **both** `output_exact` and `output_baselines`.

**Worked example — `avg_area_m2` (schema 6):** per-room area comes from `room_timings[].area_m2` on `transit_capture_valid` jobs (a counter-plateau / `cleaning_area` delta per segment, for single **and** multi-room jobs), collected into `room_area_samples` / `baseline_area_samples` and averaged with a separate `area_sample_count`; it falls back to a single-room job's `cleaning_area_m2` total only when a room has no captured segment. (The single-room-only rule was schema v4; schema 6 removed it.) A metric that genuinely *can* be allocated per room (like duration) instead accumulates `per_room_value = total / room_count` on every job — pick whichever attribution is honest for your metric.

### Step 4 — Expose in the estimator

In `estimator.py`, `_find_room_match` returns a `match` dict. Read your new field:
```python
area_m2 = _safe_float(match.get("avg_area_m2"), 0.0)
```

Add it to the per-room `room_timeline` entry so the card can read it.

### Step 5 — Optionally add to the accuracy store

If you want to track estimation accuracy for the new metric, add a parallel field to `record_estimate_accuracy` in `estimator.py`. Follow the existing pattern for `mean_abs_pct_error`.

### Step 6 — Update CSV exports (if needed)

Add a column to `_job_export_row` or `_room_export_rows` in `stats_rebuilder.py` and update the corresponding header lists in `history_store.py` (`rebuild_jobs_csv` / `rebuild_rooms_csv`).

**Jobs CSV columns (19 total):**

Header order (in `history_store.rebuild_jobs_csv`):
```
job_id, started_at, ended_at, map_id, room_count, duration_minutes,
battery_start, battery_end, battery_used, status, used_for_learning, sanity_passed,
sanity_flags, learning_blockers, job_drift_minutes, job_abs_drift_minutes,
water_estimated_ml, water_end_station_pct, water_actual_used_ml
```

Rows are lists (in `stats_rebuilder._job_export_row`), not dicts. `sanity_flags` and `learning_blockers` are pipe-delimited strings (empty if empty list).

**Rooms CSV columns (27 total):**

Header order (in `history_store.rebuild_rooms_csv`):
```
job_id, started_at, ended_at, map_id, room_slug, room_id, room_order,
requested_mode, effective_mode, clean_times, fan_speed, water_level, clean_intensity,
edge_mopping, is_carpet, job_room_count, job_duration_minutes, job_battery_used,
status, used_for_learning, sanity_passed,
sanity_flags, learning_blockers, allocated_room_minutes, allocated_room_battery_used,
allocated_room_drift_minutes, allocated_room_abs_drift_minutes
```

Rows are lists (in `stats_rebuilder._room_export_rows`), not dicts. Each room in a job gets one row; multi-room jobs produce multiple rows with allocated duration/battery/drift. `sanity_flags` and `learning_blockers` are pipe-delimited strings (empty if empty list).

### Checklist summary

| Location | What to change |
|---|---|
| `job_finalizer.py` `_collect_finalization_inputs` | Read new value from HA state |
| `job_finalizer.py` `finalize_from_inputs` | Write value onto `completed_job` |
| `stats_rebuilder.py` `build_room_stats_payload` | Accumulate and average per room key |
| `estimator.py` `estimate` | Read from matched stats, add to timeline entry |
| `history_store.py` CSV headers | Add column to jobs/rooms CSV schema |
| `stats_rebuilder.py` `_job_export_row` / `_room_export_rows` | Add value to CSV rows |
