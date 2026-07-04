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
| `manager.py` | Orchestrator. Coordinates all modules. Maintains an in-memory cache of `room_stats` and `accuracy_stats`. |
| `services.py` | HA service registration only. No math. Each handler validates inputs and delegates to `LearningManager`. |
| `utils.py` | Shared helpers (`_safe_int`, `_safe_float`, `_safe_bool`, etc.) used across the learning package. |
| `external_ingest.py` | Captures runs started from the Eufy app (not HA-dispatched), builds the pending record, and re-segments / confirms them into learned jobs via the review wizard. Also runs **pose-based room attribution** (via `room_attribution_engines.py`) to pre-fill the cleaned-room set, and builds a stand-alone attributed record when counter segmentation yields nothing. |
| `job_segmenter_engines.py` | The pluggable `JobSegmenter` engine seam (`eufy_counter_v1`) over the counter-plateau primitives; selected by adapter config, with an Eufy fallback. |
| `room_attribution_engines.py` | Pluggable room-attribution seam — recovers the cleaned-room *set* of an undispatched (app-started) run from a pose stream (counter owns time/area, this owns *which managed room*); Eufy engine `eufy_anchor_winding_v1`; selected via the adapter's `room_attribution.engine`, with an Eufy fallback. |

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
`effective_mode`, and the estimator's match lookup.

**Fields written per entry:**

| Field | Type | Source | Description |
|---|---|---|---|
| `map_id` | int | `job_profile.map_id` | Which map this room belongs to |
| `room_slug` | str | `resolved_rooms[].slug` | Lowercase slug identifier |
| `effective_mode` | str | `resolved_rooms[].clean_mode` | `vacuum`, `mop`, or `vacuum_mop` |
| `clean_times` | int | `resolved_rooms[].clean_passes` (clamped to 1 or 2) | Number of cleaning passes |
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

**Area-quality gate (schema 6):** a full clean covers the room's whole floor, so a clean whose area falls more than 1.5 m² off the room's **median** (once it has ≥ 4 area samples) is a partial/interrupted clean — its short **time** would poison the baseline, so its minutes sample is excluded from `avg_minutes` / the minutes band. `partial_excluded_count` reports how many were dropped, `timing_sample_count` the kept count; area / battery / water keep all samples. The band is per-room (area is settings-invariant), validated on the archive (~12% flagged; Kitchen time stddev 101 → 80 s — `scratch-external-estimator/gate.py`).

Because area is settings-invariant (a room's floor area doesn't change with mode or intensity), the per-room `room_baselines` entry carries the most robust `avg_area_m2`.

**Per-room baselines and setting buckets (`room_baselines` array):**

`room_stats.json` also carries a `room_baselines` array — one entry per `{map_id, room_slug}` that collapses *all* settings into a single per-room average (`avg_minutes`, `avg_battery_used`, `avg_area_m2`, plus the `effective_modes` / `clean_times` / carpet counts). Each baseline additionally breaks its averages out by the two settings that most affect duration:

- `by_clean_times` — `{"1": {…}, "2": {…}}`, keyed by pass count
- `by_edge_mopping` — `{"on": {…}, "off": {…}}`

Each bucket holds `{sample_count, avg_minutes, minutes_min, minutes_max, minutes_stddev, avg_battery_used}` — the min/max/stddev band lets a consumer match *within variance* rather than against a brittle point mean. All stats are **learning-jobs-only** (cancelled / failed / sanity-blocked runs are excluded before aggregation, so a bad run never skews a bucket). The full per-room average is retained; the buckets are **additive**, so a consumer can match a job's settings (e.g. a 2-pass, edge-mop run) to the right sub-average. Area is intentionally **not** bucketed — a room's floor area does not change with passes or edge mopping.

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
`gap_transit_s=inf` and `kinds={wash_plateau, area_jump}`, so it sees only the
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
(`learning/room_attribution_engines.py`, Eufy `eufy_anchor_winding_v1`; resolved by
`external_ingest._resolve_attribution` from the adapter's `room_attribution.engine`, Eufy
fallback) — recovers the cleaned-room **set** from the run's per-tick pose stream
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
branch behaves exactly as pre-W5c.

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

- **Strict-order (sequenced) jobs** — each phase cleaned one room and docked, so the
  whole-run counter stream can't be segmented across the per-room dock trips against a
  single last-phase queue. Instead each phase captured its **own** `room_timing` from its
  own counter slice at advance time (`jobs/PhaseRunner._capture_finishing_phase_timing` →
  `_phase_room_timing`, `jobs/phase_runner.py`). `build_completed_job_payload` concatenates
  those per-phase timings in phase order, sets `transitions = []` (the inter-phase gaps are
  dock overhead, not room-to-room transit), and `transit_capture_valid` is `True` only when
  **every** phase captured a timing.
- **Atomic / legacy jobs** (`phases` absent) — `_build_transit_blocks`
  (`learning/history_store.py`) resolves the job-segmenter engine from the adapter (optional
  `vacuum_entity_id` param; absent/unknown → the Eufy fallback) and calls
  `engine.segment_legacy(...)` — byte-identical to the legacy `segment_counters` — then maps
  the segments onto the dispatched queue order (internal: segment K → queue room K).

Either path writes three additive blocks to the job record's `job` object:

| Field | Shape | Meaning |
|---|---|---|
| `room_timings` | `[{room_id, slug, cleaning_start, cleaning_end, cleaning_seconds, cleaning_wall_seconds, area_m2, battery_delta, boundary}]` | Per-room window — incl. exact per-room **`area_m2`, now available for multi-room jobs** |
| `transitions` | `[{from_room_id, from_slug, to_room_id, to_slug, transit_seconds}]` | Inter-room gap (the segment's `gap_before_s` = transit + wash) |
| `transit_capture_valid` | bool | True only when the segment count equals the queued room count |

`transit_capture_valid` is the **poison guard**: a glitchy run (missed sample,
extra split) sets it `False` so it never corrupts the aggregate, while the
partial timings are still written for audit. A single-room job is valid with an
empty `transitions` list.

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

**Job-level overhead** (`overhead_observed`, retroactive-safe) is attached to each
job by the finalizer via `compute_overhead_observed` (`learning/utils.py`):
`{total_overhead_minutes, entry_minutes, inter_room_minutes, return_minutes,
recharge_minutes, wash_minutes}`. `total_overhead_minutes = duration_minutes −
cleaning_minutes`, and the `return` / `recharge` components come from fields
present on **every** finalized job — so a plain rebuild populates job-level
overhead for the entire historical corpus even though per-room transit is
forward-only (`entry` / `inter_room` stay `null` until a valid capture supplies
them). `job_stats.json` (schema 4) aggregates these into `avg_overhead_minutes`
(+band) and per-component means (`avg_overhead_inter_room_minutes`, etc.).

### 2.3 Accuracy store (`accuracy_stats.json` → `rooms` dict)

A separate file tracking how accurate estimates have been against actuals. Keyed by the **same** `_room_key` as `room_stats` (one shared builder in `utils.py`, so the two can never drift) — which now includes `edge_mopping`, so drift is tracked per edge variant. Updated incrementally after every job (not rebuilt from scratch); because it is never rebuilt, any entries written under the older key format (before edge was added) are simply orphaned — harmless, and they fall out of use as new keys accumulate.

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

`build_completed_job_payload` computes a `learning_blockers` list. Any populated blocker forces `used_for_learning = False` on the outcome. The complete set of blocker strings that the system writes:

| Blocker string | Condition |
|---|---|
| `invalid_room_count` | `room_count <= 0` |
| `invalid_duration` | `duration_minutes <= 0` |
| `missing_resolved_rooms` | `resolved_rooms` list is empty |
| `job_cancelled` | `was_cancelled == True` or `status == "cancelled"` |
| `job_failed` | `was_failed == True` or `status == "failed"` |
| `job_interrupted` | `was_interrupted == True` or `status == "interrupted"` |
| `test_job` | `is_test_job == True` or `status == "test"` |
| `floor_time_too_short` | Cancel detection: actual floor time < 1.5 min (single-room only) |
| `early_return_likely_cancelled` | Cancel detection: duration < 40% of expected, cancel-like transition found |

The cancel detection blockers (`floor_time_too_short`, `early_return_likely_cancelled`) are written from the `cancel_detection.reason` field when `cancel_likely == True` in `_detect_cancel_likely_run`.

Manual exclusion via the `exclude_learning_job` service adds two additional blockers: `manually_excluded` and whatever reason string was passed (default `manual_exclusion`).

> **See also:** [06-job-lifecycle](06-job-lifecycle.md) §7 for the finalization pipeline that evaluates these blockers and writes `used_for_learning` onto the completed job record.

### 3.3 Sanity tag (history snapshot, distinct from the learning gate)

Separate from `used_for_learning`, each job carries an `outcome.sanity_passed` /
`outcome.sanity_flags` pair used only by the **history snapshot** the card renders
(`manager.py::get_learning_history_snapshot`), not by the aggregation gate above. The snapshot
maps known sanity flags (e.g. `failed_sanity` → "This run failed the backend sanity
checks.") to display text and contributes to the per-job `outlier_score` / the
"suggest exclude" hint.

Two rules matter here:

- **Only an explicit `False` is a failure.** Both the `outlier_score` bump and the
  exclude-suggestion check test `item.get("sanity_passed") is False`, *not* a
  `.get("sanity_passed", True)` default. The jobs index stores the key as `None` for
  records that never set it, so the old default never fired and tagged **every** such
  run "failed the backend sanity checks." A missing/`None` value now counts as
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
score = clamp(score, 0.0, 1.0)
score = round(score, 4)
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

The estimator walks `ordered_rooms` in sequence, accumulating a `cumulative_minutes` cursor:

```
for each room (position 0..n-1):
    transit_before = 0.0 if position == 0 else learned inter-room leg (§5.3)
    cumulative_minutes += transit_before   # travel time, folded into the timeline
    start_offset = cumulative_minutes
    cumulative_minutes += minutes          # learned avg_minutes or default 6.0
    end_offset = cumulative_minutes
    eta_at = job_start_dt + end_offset (minutes)
```

Each room entry carries `start_offset_minutes`, `end_offset_minutes`, `eta_at` (ISO timestamp), and — for rooms after the first — `estimated_transit_minutes_before` + `transit_source` (the learned inter-room leg, folded into the offsets so travel time is positioned *between* rooms rather than lumped at the end). Their sum equals `overhead.transition_minutes` (§5.3). The position-0 entry leg (dock → first room) stays in `startup`. Each entry also carries `estimated_area_m2` (the learned per-room area) and feeds confidence/velocity from the area-gated `timing_sample_count` (not the raw `sample_count`), since `avg_minutes` is computed from the gated samples (§2.1). The ETA anchor is `started_at` when provided; otherwise `utc_now()` at estimate time.

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
| 3 | Job-level global per-boundary average (`job_stats.avg_overhead_inter_room_minutes ÷ avg boundaries`) | `learned_global` |
| 4 | The `_TRANSITION_PER_ROOM = 0.75` constant | `default` |

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
- `reanchor_at` — ISO timestamp to anchor remaining ETAs from (defaults to `utc_now()`)

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

| Output file | Recalculated fields |
|---|---|
| `job_stats.json` | `total_jobs`, `avg_duration_minutes`, `avg_battery_used`, `avg_room_count`, `avg_drift_minutes`, `avg_abs_drift_minutes`, `min/max_duration_minutes`, `min/max_battery_used`, `latest_job_ended_at` |
| `room_stats.json` | `avg_minutes`, `minutes_stddev`, `minutes_min`, `minutes_max`, `avg_battery_used`, `avg_drift_minutes`, `avg_abs_drift_minutes`, `sample_count`, plus `avg_area_m2`, `area_m2_min`, `area_m2_max`, `area_m2_stddev`, `area_sample_count` (per room, single + multi-room) for every room key; `room_baselines` additionally carries `by_clean_times` / `by_edge_mopping` setting breakouts |
| `jobs_index.json` | Per-job summary list, per-room aggregate list, per-profile aggregate list |

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

---

## 9. File Layout

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

**Naming conventions:**

- Job files: `{job_id}.json` where `job_id` defaults to `job_{YYYY-MM-DDTHH-MM-SS}` when not supplied.
- All JSON files use 2-space indentation, UTF-8 encoding, trailing newline.
- CSV files write header on first row if the file is empty or does not exist.

**`LearningPaths` dataclass fields:**

| Field | Path |
|---|---|
| `root` | `{base_dir}/{vacuum_slug}` |
| `jobs_dir` | `root/jobs` |
| `learned_dir` | `root/learned` |
| `exports_dir` | `root/exports` |
| `live_dir` | `root/live` |

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

### Checklist summary

| Location | What to change |
|---|---|
| `job_finalizer.py` `_collect_finalization_inputs` | Read new value from HA state |
| `job_finalizer.py` `finalize_from_inputs` | Write value onto `completed_job` |
| `stats_rebuilder.py` `build_room_stats_payload` | Accumulate and average per room key |
| `estimator.py` `estimate` | Read from matched stats, add to timeline entry |
| `history_store.py` CSV headers | Add column to jobs/rooms CSV schema |
| `stats_rebuilder.py` `_job_export_row` / `_room_export_rows` | Add value to CSV rows |
