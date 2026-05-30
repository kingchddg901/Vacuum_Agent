# Learning System — Developer Reference

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

---

## 2. Data Collected Per Room

### 2.1 Room stats (`room_stats.json` → `room_stats` array)

Each entry in the `room_stats` array represents one unique combination of room identity and cleaning settings. It is keyed internally by the exact string:

```
{map_id}::{room_slug}::{effective_mode}::{clean_times}::{is_carpet_int}::{clean_intensity}
```

where `is_carpet_int` is `1` for carpet, `0` for hard floor.

**Fields written per entry:**

| Field | Type | Source | Description |
|---|---|---|---|
| `map_id` | int | `job_profile.map_id` | Which map this room belongs to |
| `room_slug` | str | `resolved_rooms[].slug` | Lowercase slug identifier |
| `effective_mode` | str | `resolved_rooms[].clean_mode` | `vacuum`, `mop`, or `vacuum_mop` |
| `clean_times` | int | `resolved_rooms[].clean_passes` (clamped to 1 or 2) | Number of cleaning passes |
| `is_carpet` | bool | `resolved_rooms[].is_carpet` or `resolved_rooms[].carpet` | Floor type flag |
| `clean_intensity` | str | `resolved_rooms[].clean_intensity` (default `"standard"`) | Fan/suction level |
| `sample_count` | int | Incremented once per qualifying job | How many learning jobs contributed |
| `avg_minutes` | float | `total_estimated_minutes / sample_count` | Mean cleaning duration for this room |
| `minutes_stddev` | float | Population stddev of per-job duration samples | Spread of observed durations |
| `minutes_min` | float | `min(samples)` | Shortest observed duration |
| `minutes_max` | float | `max(samples)` | Longest observed duration |
| `avg_battery_used` | float | `total_estimated_battery_used / sample_count` | Mean battery consumed |
| `avg_drift_minutes` | float | Equally allocated from job-level drift | Signed mean prediction error |
| `avg_abs_drift_minutes` | float | Absolute value of drift | Mean magnitude of prediction error |

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

### 2.2 Accuracy store (`accuracy_stats.json` → `rooms` dict)

A separate file tracking how accurate estimates have been against actuals. Keyed by the same room key format as `room_stats`. Updated incrementally after every job (not rebuilt from scratch).

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

### 5.1 Room stat lookup — four-pass fallback

`_find_room_match` searches the `room_stats` list in four passes, stopping at the first match:

| Pass | Match dimensions | `intensity_mismatch` |
|---|---|---|
| 1 | `map_id + slug + clean_mode + clean_passes + is_carpet + clean_intensity` (exact) | `False` |
| 2 | `map_id + slug + clean_mode + clean_passes + is_carpet` (ignore intensity) | `True` |
| 3 | `map_id + slug + clean_mode + clean_passes` (ignore carpet) | `True` |
| 4 | `map_id + slug + clean_mode` (ignore passes and carpet) | `True` |

When no match is found at any pass, the room gets `source = "default"` with hardcoded fallbacks:
- `avg_minutes = 6.0`
- `avg_battery_used = 0.8`

### 5.2 Room timeline computation

The estimator walks `ordered_rooms` in sequence, accumulating a `cumulative_minutes` cursor:

```
for each room (position 0..n-1):
    start_offset = cumulative_minutes
    cumulative_minutes += minutes          # learned avg_minutes or default 6.0
    end_offset = cumulative_minutes
    eta_at = job_start_dt + end_offset (minutes)
```

Each room entry in the timeline carries `start_offset_minutes`, `end_offset_minutes`, and `eta_at` (ISO timestamp). The ETA anchor is `started_at` when provided; otherwise `utc_now()` at estimate time.

### 5.3 Overhead computation

After all rooms are summed, overhead is computed and added to `room_minutes_total`:

```
total_minutes = room_minutes_total + overhead_minutes
```

**Overhead components:**

| Component | Formula | Description |
|---|---|---|
| startup | `1.0` (fixed) | Pre-clean startup time |
| transitions | `max(room_count - 1, 0) * 0.75` | Navigation between room boundaries |
| recharge | `total_battery_estimate * 0.05` | 0.05 minutes per 1% battery estimated used |
| mop wash | `floor(projected_mop_minutes / wash_interval) * 1.5` | Only in `by_time` mode |
| dust empty | `(room_minutes_total / 10.0) * 0.3` | 0.3 minutes per 10 job minutes |
| return | `1.0` (fixed) | Return-to-dock trip |

**Mop wash detail:**

The wash mode and interval are read live from HA entities derived from the vacuum entity ID:

```
mode entity:     select.{object_id}_wash_frequency_mode
interval entity: number.{object_id}_wash_frequency_value_time
```

Where `object_id` is the part of the vacuum entity id after the dot (e.g. `alfred` from `vacuum.alfred`).

The interval is clamped to `[15.0, 25.0]` minutes and defaults to `20.0` when unavailable.

Wash cycles are only counted when `mode == "by_time"` and `projected_mop_minutes > 0`:
```
wash_cycle_count = floor(projected_mop_minutes / wash_interval_minutes)
mop_wash_minutes = wash_cycle_count * 1.5
```

`projected_mop_minutes` is the sum of `avg_minutes` for all rooms whose `clean_mode` is `vacuum_mop` or `mop`.

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

The overhead is carried over unchanged from the original estimate — it is not recomputed on reanchor.

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
| `room_stats.json` | `avg_minutes`, `minutes_stddev`, `minutes_min`, `minutes_max`, `avg_battery_used`, `avg_drift_minutes`, `avg_abs_drift_minutes`, `sample_count` for every room key |
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

`room_stats.json` and `job_stats.json` are written with `schema_version: 3`. The `jobs_index.json` uses `schema_version: 1`. There is no migration path for older schema versions — a full rebuild produces fresh files.

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

To add a new metric (e.g. area cleaned per room) to the learning system, touch these locations in order:

### Step 1 — Collect the raw value at finalization

In `job_finalizer.py`, `finalize_from_inputs` assembles the `completed_job` payload. The raw value (e.g. from a HA sensor) should be read in `_collect_finalization_inputs` alongside `cleaning_area_m2` and stored in the `inputs` dict. Then in `finalize_from_inputs`, write it onto the appropriate section of `completed_job`.

### Step 2 — Store it per job

The `completed_job` dict written to `jobs/{job_id}.json` is the source of truth. Add your field to the appropriate nested section (e.g. `job.cleaning_area_m2` already exists). No schema change is needed — JSON files accept additional keys.

### Step 3 — Aggregate in `stats_rebuilder.py`

In `build_room_stats_payload`, the rebuilder loops over all rooms in all learning jobs. Add your field to the accumulator dict (e.g. `"total_area_m2": 0.0`), accumulate per-room allocations in the loop, and compute `avg_area_m2 = total_area_m2 / sample_count` in the output block. Write it into `output_exact` entries.

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
