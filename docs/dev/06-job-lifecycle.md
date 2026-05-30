# Cleaning Job Lifecycle

Traces every state, transition, side effect, and event across the full life of
a room-cleaning job — from queue build through finalization. A developer should
be able to follow the entire flow from source code using this document.

**Primary source files:**
- `custom_components/eufy_vacuum/core/manager.py`
- `custom_components/eufy_vacuum/jobs/active_job.py`
- `custom_components/eufy_vacuum/jobs/job_monitor.py`
- `custom_components/eufy_vacuum/__init__.py`
- `custom_components/eufy_vacuum/learning/job_finalizer.py`
- `custom_components/eufy_vacuum/learning/services.py`
- `custom_components/eufy_vacuum/const.py`

---

## 1. Pre-job: Queue Build

### `build_queue`

`EufyVacuumManager.build_queue(vacuum_entity_id, map_id)` reads the managed
room records from the map bucket, passes them to
`build_queue_from_managed_rooms` (`queue/queue_engine.py`), and writes the
result to `self.data["queue"][vacuum_entity_id][map_id]`. Also updates the
runtime object: `runtime.selected_map_id` and `runtime.queue_room_ids`.

Only rooms whose `enabled` flag is `True` are included. Output shape:

```
{
  "vacuum_entity_id": str
  "map_id":           str
  "room_count":       int
  "queue_room_ids":   list[int]
  "queue_rooms":      list[QueueRoomSummary]
}
```

### `build_room_payload`

`EufyVacuumManager.build_room_payload(vacuum_entity_id, map_id)` builds the
`room_clean` command payload. Before building, it applies carpet/mop invariants
via `_protected_room_config` on every room and fetches:

- the current queue state for `queue_room_ids`
- stored room profiles from `self.data["profiles"]["room_profiles"]`
- vacuum capabilities via `get_vacuum_capabilities`

Result stored at `self.data["payloads"][vacuum_entity_id][map_id]`. Contains
the raw `payload` dict plus a `resolved_rooms` list with full per-room settings.

### `get_start_status` — blocker reasons

`get_start_status` calls `_build_effective_start_plan` (which evaluates all
room rules against live HA states), `get_lifecycle_state`, and
`get_onboarding_state` and assembles a status dict. It returns early with
`blocked: True` and the following `reason` strings in priority order:

| `reason` | Condition |
|---|---|
| `"job_paused"` | `active_job["status"] == "paused"` |
| `"onboarding_required"` | One or more enabled rooms are missing a floor type |
| `"all_selected_rooms_blocked"` | All selected rooms were blocked by rules; none remain |
| `"no_target_map"` | `selected_map_id` is empty |
| `"map_mismatch"` | `selected_map_id` != vacuum's active map |
| `"no_rooms_selected"` | Queue is empty |
| `"invalid_payload"` | Payload room count is 0 |
| `"mid_job_service"` | Dock or task status is in a hard service state (washing, recycling, emptying) |
| `"active_job_running"` | A room-clean job is already active |
| `"vacuum_busy"` | Vacuum is busy and not dockable/idle |
| `"incomplete_access_graph"` | Room access graph is partially configured |
| `"access_graph_required_for_rules"` | Rules are present but no access graph exists |
| `"access_graph_required"` | Blocker rules exist without an access graph |

The lifecycle state `"dock_drying"` is a non-blocking warning — it sets
`blocked: False` with `warning: True` and `reason: "dock_drying"`.

#### Preflight rule evaluation (`_build_effective_start_plan`)

This is the authoritative rule-evaluation site for job start (the only other
site is `get_runtime_path_block_report` for mid-job path changes). Steps:

1. All managed rooms with automation rules are loaded.
2. Blocker rules are evaluated against live HA entity states. Matching rooms go
   into `direct_blocked`.
3. Modifier rules are evaluated; matching changes are accumulated in
   `modifier_matches`.
4. Access-graph propagation: rooms that require traversal through a
   directly-blocked room are also marked blocked.
5. `included_room_ids` = selected minus blocked.
6. `requires_confirmation` becomes `True` when `blocked_ratio_time >= 0.20` or
   `blocked_ratio_rooms >= 0.40`. When confirmation is required, a
   `confirm_token` (opaque hash of the preflight parameters) is generated.

> **See also:** [09-room-rules-system](09-room-rules-system.md) §5 for the full rule evaluation pipeline and operator reference; [07-queue-engine](07-queue-engine.md) §5 for the access graph data structure `_build_effective_start_plan` traverses to propagate indirect blocks.

---

## 2. Job Start

### 2a. `start_selected_rooms`

`async EufyVacuumManager.start_selected_rooms(vacuum_entity_id, map_id,
confirm_reduced_run, confirm_token, path_block_action,
pause_timeout_minutes_override)`

**Step-by-step flow:**

1. **Blocker check** — calls `get_start_status`. If `blocked`, returns
   immediately with `started: False`.
2. **Confirmation handshake** — if `requires_confirmation` is set, start is
   blocked unless:
   - `confirm_reduced_run=True` (bypass flag for automations), **or**
   - the caller supplies a `confirm_token` matching the preflight token.
   If neither, returns `{"started": False, "reason": "confirmation_required", "confirm_token": <token>}`.
3. **Rebuild plan** — calls `_build_effective_start_plan` again (rules may have
   changed since `get_start_status`) and writes the final queue/payload.
4. **Vacuum entity check** — if the HA state object is missing, returns
   `{"started": False, "reason": "vacuum_missing"}`.
5. **Command dispatch** — calls `vacuum.send_command` with
   `command="room_clean"` and the payload as `params` (blocking).
6. **Active job initialisation** — calls `build_active_job_state` then enriches:
   - `job_metadata` from `build_job_metadata_from_payload`
   - `job_id` (generated as `"job_{YYYY-MM-DDTHH-MM-SS}"`)
   - `started_at` (UTC ISO timestamp)
   - `battery_start`
   - `current_room_started_at` = `started_at`
   - `path_block_action` (normalised; default `"event_only"`)
   - `pause_timeout_minutes` (from config or override)
   - `water_estimate` from `get_planned_job_estimate`
7. **Storage write** — saves to `self.data["active_jobs"][vacuum_entity_id][map_id]`.
8. **Room-started event** — if `current_room_id` is set, fires
   `eufy_vacuum_room_started` (see §9 event table).
9. **Runtime update** — `runtime.active_job_room_ids` is set; room selections
   are cleared via `_clear_room_selections_after_start`.
10. **Learning snapshot** — `save_learning_snapshot_for_active_job` is called.
    The snapshot freezes the queue/payload/active_job state to disk
    non-blockingly (via executor). Failures are caught and logged; they do not
    abort the job.

### 2b. `start_run_profile`

`async EufyVacuumManager.start_run_profile(vacuum_entity_id, map_id,
profile_id, ...)` is the saved-run-profile alternative entry point.

1. Calls `apply_run_profile(profile_id)` — loads the saved room list from
   `data["run_profiles"]`, re-enables exactly those rooms, and overwrites their
   settings from the saved snapshot. Returns `applied: False` if the profile ID
   is not found.
2. Calls `build_queue` and `build_room_payload` to rebuild derived state from
   the new room configuration.
3. Delegates to `start_selected_rooms` (all confirmation/blocking logic applies
   identically). Adds `profile_id` and `profile` to the return dict.

---

## 3. Active Job Monitoring

### `get_job_progress_snapshot`

`EufyVacuumManager.get_job_progress_snapshot(vacuum_entity_id, map_id)` is the
main polling endpoint for the card. It does not mutate storage unless a timing
rollover occurs. Each call:

1. Loads and normalises `active_job` via `_normalize_active_job`.
2. Calls `get_lifecycle_state` for the current lifecycle context.
3. Reads current battery level.
4. **Timeline construction** — if the learning system is available and
   `resolved_rooms` is set:
   - First call: `learning.estimate_from_manager` produces a full
     `room_timeline` (`timeline_source = "estimate"`).
   - After any room completes: `learning.reanchor_timeline` replaces estimates
     with actual completed-room durations (`timeline_source = "reanchored"`).
   - No learning system: `timeline_source = "none"`.
5. **Current room resolution** — reads `active_job["current_room_id"]`. Falls
   back to the first unresolved room if the stored ID is not in
   `unresolved_room_ids`.
6. **Elapsed time** — calls `_compute_current_room_elapsed_minutes` on
   `ActiveJobTracker`: wall-clock elapsed since `current_room_started_at` minus
   accumulated `current_room_paused_seconds` and any ongoing pause.
7. **Timing rollover** — delegates to
   `active_job.tracker._maybe_roll_current_room_by_timing` (see §4).
8. **Bounds-exit detection** (`awaiting_bounds_exit`).
9. **Stall detection** (see below).

### `awaiting_bounds_exit` logic

After the timing rollover attempt, if the room did *not* roll (i.e.
`current_room_id` is unchanged), the snapshot checks whether elapsed time has
passed the timing completion threshold. If so, `awaiting_bounds_exit = True`.
This signals the card to switch to a short poll interval (~5 s) because the
robot is still physically inside the room and the rollover gate is blocked by
bounds.

### Stall detection

A stall is detected when:
- `awaiting_bounds_exit` is already `True` (timing threshold exceeded), **and**
- `current_room_elapsed_minutes >= threshold * 2.0` (`_STALL_RATIO = 2.0`)

`EVENT_STALL_DETECTED` fires at most once per room per job. Already-notified
rooms are tracked in `active_job["_stall_notified_room_ids"]` (written back to
storage). Subsequent snapshot calls suppress the event for those rooms.

### `has_observed_active_lifecycle`

Set to `True` the first time the lifecycle listener observes a state that
indicates the robot is actively cleaning (not at the dock). This flag is the
mandatory pre-condition for auto-finalization. Without it, a stale pre-run dock
state (e.g. `dock_drying`) could complete the job before it actually started.

---

## 4. Room Transitions

### What triggers `room_started` / `room_finished`

`EVENT_ROOM_STARTED` fires in two situations:
- At job start (`source: "job_start"`), when `current_room_id` is non-null.
- After each timing rollover, for the *next* room (`source: "timing_rollover"`
  or `"bounds_exit_early"`).

`EVENT_ROOM_FINISHED` fires from `_maybe_roll_current_room_by_timing` after
rollover. There is no HA-entity-state-driven room transition mechanism — all
transitions are timing-based.

### Timing rollover (`_maybe_roll_current_room_by_timing`)

Defined in `ActiveJobTracker` (`jobs/active_job.py`). Called from
`get_job_progress_snapshot`. Two rollover paths:

**Slow-room path (timing has expired):**
1. Requires `active_job["status"] == "started"` and a valid `current_room_id`.
2. Elapsed >= `_timing_completion_threshold_minutes(current_room)`.
3. Checks whether the robot has left the room bounds via
   `mapping_manager.get_room_bounds_snapshot`. If bounds exist and the robot is
   still inside, rollover is blocked (`awaiting_bounds_exit` will be `True`).
4. If bounds are unavailable (room not yet mapped), timing alone determines rollover.
5. On rollover: fires `EVENT_ROOM_FINISHED` with `source="timing_rollover"`,
   calls `record_completed_room`, then fires `EVENT_ROOM_STARTED` for the next room.

**Fast-room path (early bounds exit):**
1. Elapsed < `_timing_completion_threshold_minutes` but >=
   `_MIN_ELAPSED_MIN_FOR_BOUNDS_ROLLOVER` (1.5 min / 90 s).
2. The mapping tracker's confidence model has signalled via
   `_pending_fast_rollover` on the active job that the robot finished and left.
3. Signal is consumed (popped from `active_job`) on use so it cannot trigger twice.
4. Fires `EVENT_ROOM_FINISHED` with `source="bounds_exit_early"`.

The 90-second floor on the fast path prevents doorway transits from triggering
a false rollover on the next snapshot poll.

### Timing completion threshold formula

`_timing_completion_threshold_minutes(room)` in `ActiveJobTracker`:

```
threshold = estimated_minutes + slack_minutes

overrun_ratio:
  0.06  if confidence_score >= 0.85
  0.10  if confidence_score >= 0.65
  0.15  if confidence_score >= 0.45
  0.22  otherwise

slack_minutes = max(0.75, estimated_minutes * overrun_ratio)
              + 1.0  if sample_count <= 1
              + 0.5  if sample_count <= 3
              + min(estimated_minutes * drift_ratio * 0.25, 1.5) if drift_ratio > 0

slack_minutes is capped at max(4.0, estimated_minutes * 0.35)
```

The stall threshold is `2 × _timing_completion_threshold_minutes`.

### `reanchor_learning_timeline`

`learning.reanchor_timeline(original_estimate, completed_rooms, ...)` takes the
original pre-job estimate and a list of `{room_id, actual_duration_minutes}`
entries for completed rooms, replaces estimated durations with actuals, then
recalculates all downstream ETAs and battery projections from the reanchor
point. Called from `get_job_progress_snapshot` on every snapshot call after any
room completes.

---

## 5. Mid-job Observations

The lifecycle listener in `__init__.py` fires callbacks on state changes during
a job. `ActiveJobTracker` mutates `data["active_jobs"]` directly for these
observations:

### Recharge observation (`update_active_job_recharge_observation`)

Fired when the vacuum's task status indicates a low-battery return. Two-stage
detection:
1. `pending_mid_job_recharge_return = True` when `_is_low_battery_return_state`
   fires.
2. On the next observation where `_is_charging()` is `True`:
   `observed_mid_job_recharge = True`, `observed_mid_job_recharge_count` incremented,
   `pending` flags cleared. Mapping tracker `pause_sampling` is called.
3. When charging ends (not charging while `observed_mid_job_recharge = True`):
   accumulate `recharge_seconds_accumulated`, clear flag, call
   `tracker.resume_sampling`.

### Mop wash observation (`update_active_job_mop_wash_observation`)

Debounced at 60 s (`_MOP_WASH_DEBOUNCE_SECONDS`). Each confirmed wash event
increments `observed_mop_wash_count`, appends to `observed_mop_wash_cycles`
(capped at 50), and updates `observed_mop_wash_last_at`.

### State transition recording (`record_active_job_transition`)

The listener appends every relevant entity state change to
`active_job["state_transitions"]` (capped at 12 entries). Used by the
finalization cancel-detection heuristic.

### Sensor value recording (`record_active_job_sensor_value`)

Called from the job-metrics listener whenever tracked sensors
(`cleaning_time_seconds`, `cleaning_area_m2`, etc.) change. Writes directly to
all in-flight active jobs for the vacuum. Finalization reads from `active_job`
instead of issuing a live HA state read at job-end, avoiding the DPS timing race.

---

## 6. Job End Paths

### 6a. Normal completion

**Trigger:** The lifecycle listener observes `task_status == "completed"` AND
`active_cleaning_target` is cleared, while
`active_job["has_observed_active_lifecycle"] == True`.

**Code path:** `_handle_lifecycle_change → _process()` in
`_register_lifecycle_listeners`. When completion signals are met:
`finalize_learning_for_active_job` → `mark_active_job_finalized` →
`EVENT_JOB_FINISHED`.

### 6b. Manual cancel (service call)

**Trigger:** `eufy_vacuum.cancel_active_job` service.

**Code path:** `async_cancel_active_job` → `vacuum.return_to_base` (blocking)
→ polls every 2 s for up to 30 s (`_CANCEL_CONFIRM_TIMEOUT_S`) for
`vacuum_state in {"docked", "idle"}` or `task_status in {"completed", "complete"}`.
If not confirmed within 30 s, finalizes anyway with a warning. Calls
`finalize_learning_for_active_job` with `forced_outcome_status="cancelled"` and
`forced_lifecycle_state="job_cancelled"`, then `mark_active_job_finalized`.

### 6c. Pause timeout

**Trigger:** A paused job whose `pause_timeout_minutes > 0` has been paused
beyond the configured limit.

**Code path:** `_register_pause_timeout_listener` sets a 1-minute
`async_track_time_interval` tick. On each tick,
`get_paused_job_timeout_report` is called for each known job. If it returns a
report, `async_cancel_active_job` is called with
`forced_lifecycle_state="pause_timeout_cancelled"`.

### 6d. Path blocker cancel

**Trigger:** A watched entity whose state matches a blocker rule changes while
`path_block_action == "cancel_and_event"`.

**Code path:** `_register_path_blocker_listeners` watches all rule entities. On
state change, `get_runtime_path_block_report` re-evaluates rules. Behaviour by
`path_block_action`:
- `"event_only"` — fires `EVENT_PATH_BLOCKED` only.
- `"pause_and_event"` — `async_pause_active_job` + `EVENT_PATH_BLOCKED`.
- `"cancel_and_event"` — `async_cancel_active_job` + `EVENT_JOB_FINISHED` +
  `EVENT_PATH_BLOCKED`.

### 6e. Cancel detection heuristic (automatic)

During finalization, `_detect_cancel_likely_run` is called when
`forced_outcome_status` is `None`. It examines `state_transitions`.

**Conditions for `cancel_likely=True`** (single-room jobs only):
1. Transition history contains `cleaning → returning` or `paused → returning`
   via `task_status`.
2. No stronger service state in transitions (e.g. `"returning to charge"`,
   `"washing mop"`, `"emptying dust"`).
3. `actual_cleaning_minutes < 1.5` (absolute floor), **or**
   `actual_cleaning_minutes < expected_room_minutes × 0.4` (relative threshold).

When detected, `outcome_status` is overridden to `"cancelled"` with
`lifecycle_name = "cancel_likely"`.

---

## 7. Finalization

### `finalize_learning_for_active_job` (manager entry point)

`async EufyVacuumManager.finalize_learning_for_active_job(...)` reads
`started_at` and `battery_start` from the active job, reads current battery as
`battery_end`, then delegates to `learning.async_finalize_completed_job`. After
the result returns, calls `_ingest_completed_job_into_room_history` and fires
the room-history-updated notification if anything was ingested.

### `finalize_from_manager_state` / `finalize_from_inputs` (LearningJobFinalizer)

The finalizer separates event-loop work from file I/O:

**`_collect_finalization_inputs`** (event loop): loads the in-memory live
snapshot (falls back to disk), reads `queue_state`, `payload_state`,
`active_job_state`, and `lifecycle_state` from the manager. Determines
`outcome_status` from lifecycle name or cancel detection. Reads
`cleaning_time_seconds` and `cleaning_area_m2` from `active_job` (written there
by `record_active_job_sensor_value` during the run). Returns a frozen inputs
dict.

**`finalize_from_inputs`** (executor thread — pure computation and file I/O):
- Builds a `completed_job` payload via `store.build_completed_job_payload`.
- Calls `_apply_snapshot_estimates_to_completed_job` — attaches pre-run
  estimated minutes, battery, and confidence onto each resolved room.
- Calls `_apply_water_actuals` — computes actual water-used breakdown.
- Writes `learning_context` (queue shape key, estimate delta, access graph
  metadata).
- Saves `completed_job.json` via `store.save_completed_job`.
- Calls `_write_incomplete_run_log` (for cancelled/failed/interrupted only).
- Calls `_update_trouble_rooms_log`.
- Optionally rebuilds learned stats (`rebuilder.rebuild_all`).
- Optionally derives room boundary data.

### Learning eligibility

A job is **not** used for learning if `outcome_status` is any of:
`"cancelled"`, `"failed"`, `"interrupted"`, `is_test_job = True`.

Normal completions (`outcome_status = "completed"`) are eligible.

### What gets written where

| Data | Location |
|---|---|
| Live snapshot (job start) | `<config>/eufy_vacuum/learning/<vacuum_slug>/live_snapshot.json` |
| Completed job record | `<config>/eufy_vacuum/learning/<vacuum_slug>/jobs/<job_id>.json` |
| Incomplete run log | `<config>/eufy_vacuum/learning/<vacuum_slug>/live/incomplete_run.json` |
| Trouble rooms log | `<config>/eufy_vacuum/learning/<vacuum_slug>/live/trouble_rooms.json` |
| Rebuilt stats | `<config>/eufy_vacuum/learning/<vacuum_slug>/learned_stats.json` |

> **See also:** [10-learning-system](10-learning-system.md) §3 for learning eligibility rules and the full list of blocker strings; §8 for the stats rebuilder triggered at the end of `finalize_from_inputs`. [12-battery-system](12-battery-system.md) §14.3 for the battery metrics hook that runs inside the same finalizer call.

---

## 8. Incomplete Run

### When `EVENT_RUN_INCOMPLETE` fires

`EVENT_RUN_INCOMPLETE` is fired by the `handle_finalize_learning_job` service
handler in `learning/services.py` after finalization completes, **if**
`incomplete_run_log` is non-null and contains at least one `missed_room_id`.

The incomplete run log is only written when
`outcome_status in {"cancelled", "failed", "interrupted"}`. Normal completions
clear any stale log.

### `retry_missed_rooms` flow

`handle_retry_missed_rooms` in `learning/services.py`:

1. Reads the incomplete run log from disk via `learning.get_incomplete_run_log`.
   Returns `{"started": False, "reason": "no_missed_rooms"}` if empty.
2. Resolves `map_id` from the log (overridable via call data).
3. Calls `set_rooms_enabled_subset` — enables only missed rooms, disables all
   others.
4. Calls `build_queue` to rebuild the queue with those rooms.
5. Calls `start_selected_rooms` with `confirm_reduced_run=True` so automations
   bypass confirmation.
6. Persists via `async_save`.
7. If started successfully, clears the incomplete run log.
8. Returns the `start_selected_rooms` result plus `missed_room_ids` and
   `map_id`.

---

## 9. State Cleanup

After finalization, `mark_active_job_finalized` updates the active job record
in-place (on `ActiveJobTracker`) rather than clearing it:

```python
active_job["status"]   = "completed"
active_job["finalized"] = True
active_job["paused_at"] = None
active_job["has_observed_active_lifecycle"] = False   # reset
active_job["finalized_at"] = <from completed_job>
active_job["finalize_summary"] = {
    "job_id", "job_path", "used_for_learning",
    "sanity_passed", "sanity_flags", "learning_blockers", "status"
}
```

`runtime.active_job_room_ids` is reset to `[]`.

The `data["queue"]` and `data["payloads"]` snapshots are **not** cleared
automatically after finalization — they persist until the next `build_queue` /
`build_room_payload` call (e.g., when the user selects rooms for the next job).
The active job record stays at `status: "completed"` until overwritten by the
next job start.

---

## 10. Event Timeline

Chronological table of every HA event fired during a complete job (single
successful run, no cancellations or stalls).

| # | Event constant | String value | When | Key payload fields |
|---|---|---|---|---|
| 1 | `EVENT_ROOM_STARTED` | `eufy_vacuum_room_started` | Immediately after `vacuum.send_command`, if `current_room_id` is non-null | `vacuum_entity_id`, `map_id`, `job_id`, `room_id`, `room_name`, `started_at`, `source: "job_start"`, `completed_room_ids: []` |
| 2 | `EVENT_ROOM_FINISHED` | `eufy_vacuum_room_finished` | Each timing rollover (room N complete) | `vacuum_entity_id`, `map_id`, `job_id`, `room_id`, `room_name`, `completed_at`, `source`, `actual_duration_minutes`, `confidence`, `completed_room_ids` |
| 3 | `EVENT_ROOM_STARTED` | `eufy_vacuum_room_started` | Immediately after each `room_finished`, for the next room | `source: "timing_rollover"` or `"bounds_exit_early"` |
| 4 | `EVENT_STALL_DETECTED` | `eufy_vacuum_stall_detected` | Once per room per job, when elapsed >= 2× timing threshold | `vacuum_entity_id`, `map_id`, `room_id`, `room_name`, `elapsed_minutes`, `expected_minutes`, `stall_ratio` |
| 5 | `EVENT_PATH_BLOCKED` | `eufy_vacuum_path_blocked` | When a blocker entity changes during a job (any `path_block_action`) | `vacuum_entity_id`, `map_id`, `path_block_action`, `action_taken`, `affected_remaining_room_ids` |
| 6 | `EVENT_JOB_FINISHED` | `eufy_vacuum_job_finished` | After finalization completes | `vacuum_entity_id`, `map_id`, `job_id`, `status`, `reason_detail`, `used_for_learning`, `finalized_at`, `room_count`, `job_path` |
| 7 | `EVENT_RUN_INCOMPLETE` | `eufy_vacuum_run_incomplete` | After `job_finished`, only when rooms were missed | `vacuum_entity_id`, `job_id`, `outcome_status`, `missed_room_ids`, `missed_rooms` |

**Notes:**
- Events 2 and 3 repeat for each room beyond the first. A 4-room job produces 3
  pairs of `room_finished` / `room_started` plus the initial `room_started`.
- Event 4 fires at most once per room even on repeated polls.
- Events 5 and 7 are conditional and may not appear in every job.
- `EVENT_PATH_BLOCKED` and `EVENT_JOB_FINISHED` can both fire in the same job
  when `path_block_action == "cancel_and_event"`.
- `EVENT_JOB_PROGRESS_TICK` (`eufy_vacuum_job_progress_tick`) is fired
  periodically from `job_monitor.py` as a lightweight polling signal for
  automations — it does not map to a lifecycle transition.
