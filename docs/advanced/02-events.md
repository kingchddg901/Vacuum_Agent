# HA Events Reference

The integration fires events on the Home Assistant event bus at specific points in a cleaning job's lifecycle. You can listen to any of these events in an automation using the `event` trigger platform. All payloads are plain dictionaries — no custom objects to unwrap.

---

## eufy_vacuum_job_finished

### When it fires

Fires after a cleaning job has been finalized. This covers every path to job completion:

- The robot finishes normally and returns to the dock (auto-finalization via the lifecycle listener in `listeners/lifecycle.py`)
- You call `eufy_vacuum.cancel_active_job` and cancellation succeeds
- A paused job times out and is auto-cancelled
- A path blocker is configured with `cancel_and_event` and triggers a cancellation
- You call `eufy_vacuum.finalize_learning_job` directly

### Payload fields

| Field | Type | Description |
|---|---|---|
| `vacuum_entity_id` | `str` | Entity ID of the vacuum, e.g. `vacuum.alfred` |
| `map_id` | `str` | Map ID the job ran on, as a string |
| `job_id` | `str \| null` | Internal job identifier assigned at job start |
| `status` | `str` | Outcome of the job — `completed`, `cancelled`, `failed`, or `interrupted` |
| `reason_detail` | `str \| null` | Human-readable lifecycle message, e.g. `"pause_timeout"` or `null` for clean completions |
| `used_for_learning` | `bool \| null` | Whether this job was included in the learning system's stats; `null` when learning is not active |
| `finalized_at` | `str \| null` | ISO 8601 timestamp of finalization |
| `room_count` | `int \| null` | Number of rooms that were queued in the job |
| `duration_minutes` | `float \| null` | Wall-clock duration of the job in minutes, net of pauses and recharges. Same value used by the post-job summary banner in the panel. **Present only on the auto-finalize paths** (lifecycle/pause-timeout/path-blocker) — omitted from the payload when the job is finalized via the `eufy_vacuum.finalize_learning_job` service. |
| `actual_cleaning_minutes` | `float \| null` | Time the robot actually spent cleaning, derived from the Returning state transition. Excludes the return-to-dock trip. Only set for single-room jobs; `null` for multi-room jobs (where it would not be meaningful). **Present only on the auto-finalize paths** (lifecycle/pause-timeout/path-blocker) — omitted from the payload when the job is finalized via the `eufy_vacuum.finalize_learning_job` service. |
| `job_path` | `str \| null` | Filesystem path to the saved completed-job JSON file, or `null` if learning is not enabled |

### Example trigger

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_job_finished
    event_data:
      vacuum_entity_id: "vacuum.alfred"
```

**Practical use:** Send a push notification with the outcome. Check `trigger.event.data.status` to vary the message between `completed` and `cancelled` jobs. `duration_minutes` and `room_count` are useful for one-line summaries without having to read the saved job file.

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_job_finished
    event_data:
      vacuum_entity_id: "vacuum.alfred"
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "Alfred finished"
      message: >
        Job {{ trigger.event.data.status }} —
        {{ trigger.event.data.room_count }} room(s).
```

---

## eufy_vacuum_room_started

### When it fires

Fires when the integration determines the robot has begun cleaning a new room. There are two firing sites:

- `source: "job_start"` — fired immediately after a job is started, for the first room in the queue
- `source: "timing_rollover"` — fired when the previous room's timing threshold is exceeded and the integration advances to the next room in the queue
- `source: "bounds_exit_early"` — fired when a confident coordinate signal advances to the next room before the timing threshold is reached

### Payload fields

| Field | Type | Description |
|---|---|---|
| `vacuum_entity_id` | `str` | Entity ID of the vacuum |
| `map_id` | `str` | Map ID the job is running on |
| `job_id` | `str` | Job identifier |
| `room_id` | `str` | Room ID as a string |
| `room_name` | `str` | Human-readable room name |
| `started_at` | `str \| null` | ISO 8601 timestamp of when the room started |
| `source` | `str` | One of `"job_start"`, `"timing_rollover"`, or `"bounds_exit_early"` |
| `completed_room_ids` | `list[int]` | List of room IDs already completed in this job |

### Example trigger

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_room_started
    event_data:
      vacuum_entity_id: "vacuum.alfred"
```

**Practical use:** Log each room start to a helper or push a live update. You can filter to a specific room by adding `room_id` to `event_data`.

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_room_started
    event_data:
      vacuum_entity_id: "vacuum.alfred"
      room_id: "3"
action:
  - service: notify.mobile_app_your_phone
    data:
      message: "Alfred started cleaning {{ trigger.event.data.room_name }}"
```

---

## eufy_vacuum_room_finished

### When it fires

Fires when the integration marks a room complete and advances to the next one. This is the same `_maybe_roll_current_room_by_timing` path that also fires `eufy_vacuum_room_started` for the following room. The rollover happens either because the room's timing threshold was exceeded (`source: "timing_rollover"`) or because a confident coordinate signal advanced past the room early (`source: "bounds_exit_early"`).

### Payload fields

| Field | Type | Description |
|---|---|---|
| `vacuum_entity_id` | `str` | Entity ID of the vacuum |
| `map_id` | `str` | Map ID the job is running on |
| `job_id` | `str \| null` | Job identifier |
| `room_id` | `str` | ID of the room that was just completed |
| `room_name` | `str` | Human-readable name of the completed room |
| `completed_at` | `str` | ISO 8601 timestamp of completion |
| `source` | `str` | Either `"timing_rollover"` or `"bounds_exit_early"` |
| `actual_duration_minutes` | `float` | How long the robot spent in the room, in minutes, rounded to 2 decimal places |
| `confidence` | `float \| null` | Confidence score from the timing estimate, or `null` if no estimate was available |
| `completed_room_ids` | `list[int]` | Full list of room IDs now completed in this job (includes the room just finished) |

### Example trigger

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_room_finished
    event_data:
      vacuum_entity_id: "vacuum.alfred"
```

**Practical use:** Build a running log of actual cleaning durations per room to compare against learning estimates.

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_room_finished
    event_data:
      vacuum_entity_id: "vacuum.alfred"
action:
  - service: logbook.log
    data:
      name: "Alfred room done"
      message: >
        {{ trigger.event.data.room_name }}
        in {{ trigger.event.data.actual_duration_minutes }} min
```

---

## eufy_vacuum_run_incomplete

### When it fires

Fires from `finalize_learning_job` (in `learning/services.py`) after a job that ended with status `cancelled`, `failed`, or `interrupted` — but only when at least one queued room was not cleaned. If the job completed normally, or if all queued rooms were cleaned before the job ended, this event does not fire.

The integration derives missed rooms by computing the difference between the rooms that were queued at job start and the rooms recorded as completed in `active_job_state.completed_room_ids`.

### Payload fields

| Field | Type | Description |
|---|---|---|
| `vacuum_entity_id` | `str` | Entity ID of the vacuum |
| `job_id` | `str` | Job identifier |
| `outcome_status` | `str` | Why the job ended — `cancelled`, `failed`, or `interrupted` |
| `missed_room_ids` | `list[int]` | IDs of rooms that were queued but not cleaned |
| `missed_rooms` | `list[dict]` | One entry per missed room, each with `room_id` (int) and `name` (str) |

### Example trigger

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_run_incomplete
    event_data:
      vacuum_entity_id: "vacuum.alfred"
```

**Practical use:** Automatically re-queue missed rooms using the `eufy_vacuum.retry_missed_rooms` service. This is the canonical pattern documented in the source.

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_run_incomplete
    event_data:
      vacuum_entity_id: "vacuum.alfred"
action:
  - service: eufy_vacuum.retry_missed_rooms
    data:
      vacuum_entity_id: "{{ trigger.event.data.vacuum_entity_id }}"
```

You can also gate on outcome to only retry cancelled jobs, not failed ones:

```yaml
condition:
  - condition: template
    value_template: "{{ trigger.event.data.outcome_status == 'cancelled' }}"
```

---

## eufy_vacuum_external_run_pending

### When it fires

Fires when an **app-started (external) clean** finishes and is captured as a
pending review record under `learning/<slug>/external_jobs/`. Subscribe to surface
a notification prompting the user to confirm which rooms it cleaned (the card's
"External Jobs" subtab). See the
[external-run ingestion dev doc](../dev/28-external-run-ingestion.md).

### Payload fields

| Field | Description |
|---|---|
| `vacuum_entity_id` | The vacuum that ran. |
| `map_id` | The map the run cleaned. |
| `record_path` | Path to the pending record JSON. |
| `segment_count` | Number of detected cleaning segments. |
| `detection_ts` | When detection first fired (the pending record id basis). |

---

## eufy_vacuum_room_completed

### When it fires

Fires from the **mapping tracker** when the robot's live coordinates leave a room's stored boundary box. This is a position-based signal, distinct from the timing-rollover path that fires `eufy_vacuum_room_finished`. It requires the interactive map to be configured and the vacuum to expose a position entity (`robot_position_x` / `robot_position_y`).

Because it is derived from coordinate tracking rather than learned timing, it can fire for rooms the learning system has no history for, and it fires independently of whether the room was part of the current queue.

### Payload fields

| Field | Type | Description |
|---|---|---|
| `vacuum_entity_id` | `str` | Entity ID of the vacuum |
| `map_id` | `str` | Map ID the job is running on |
| `room_id` | `str` | ID of the room whose boundary was exited, as a string |
| `room_name` | `str` | Human-readable room name |
| `confidence` | `float` | Coordinate-tracking confidence score for the room exit |
| `duration_seconds` | `float` | How long the robot was inside the room's boundary, in seconds, rounded to 1 decimal place |
| `entered_at` | `str \| null` | ISO 8601 UTC timestamp of when the robot entered the room's boundary, or `null` if unknown |

### Example trigger

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_room_completed
    event_data:
      vacuum_entity_id: "vacuum.alfred"
```

**Practical use:** Use as a position-accurate room-exit signal when the interactive map is configured. Pairs well with `eufy_vacuum_room_finished` for cross-validation — if one fires but not the other, the coordinate or timing model may need review.

---

## eufy_vacuum_job_progress_tick

### When it fires

Fires on a fixed 5-second interval from the job-progress listener (`listeners/job_progress.py`) for every managed vacuum/map that has an active job. The tick fires only while the active job's status is `started` or `paused` — it stops once the job is finalized. On each tick the listener recomputes the job progress snapshot (the same path that can fire `eufy_vacuum_stall_detected`) and then emits this event so dashboards and automations can refresh on a heartbeat rather than polling a service.

The payload deliberately carries no job state — it is a pull signal. Use it as a trigger to call `get_job_progress_snapshot`, `get_dashboard_snapshot`, or another state-inspection service for the current values.

### Payload fields

| Field | Type | Description |
|---|---|---|
| `vacuum_entity_id` | `str` | Entity ID of the vacuum with the active job |
| `map_id` | `str` | Map ID the active job is running on, as a string |

### Example trigger

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_job_progress_tick
    event_data:
      vacuum_entity_id: "vacuum.alfred"
```

**Practical use:** Drive a live progress refresh. Trigger on the tick, then call `eufy_vacuum.get_job_progress_snapshot` (with `response_variable`) to pull the current room, completed rooms, and completion percentage into a helper or notification.

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_job_progress_tick
    event_data:
      vacuum_entity_id: "vacuum.alfred"
action:
  - service: eufy_vacuum.get_job_progress_snapshot
    data:
      vacuum_entity_id: "{{ trigger.event.data.vacuum_entity_id }}"
      map_id: "{{ trigger.event.data.map_id }}"
    response_variable: progress
```

---

## eufy_vacuum_stall_detected

### When it fires

Fires from `get_job_progress_snapshot()` (called on every dashboard poll) when both of the following are true:

1. The integration is already in `awaiting_bounds_exit` state for the current room — meaning the timing threshold was met but the robot has not yet crossed the room boundary
2. The robot has been in the room for **at least 2× the learned timing threshold** for that room (`_STALL_RATIO`)

The integration tracks which rooms have already triggered this event per job via `_stall_notified_room_ids` on the active job, so **it fires at most once per room per job** regardless of how many dashboard polls occur.

This event requires the learning system to have timing data for the room. If no learned threshold exists, the stall check is skipped.

### Payload fields

| Field | Type | Description |
|---|---|---|
| `vacuum_entity_id` | `str` | Entity ID of the vacuum |
| `map_id` | `str` | Map ID the job is running on |
| `room_id` | `int` | ID of the stalled room (integer, not a string) |
| `room_name` | `str` | Human-readable name of the stalled room |
| `elapsed_minutes` | `float` | How long the robot has been in the room, rounded to 1 decimal place |
| `expected_minutes` | `float` | The learned timing threshold for the room, rounded to 1 decimal place |
| `stall_ratio` | `float` | `elapsed_minutes / expected_minutes`, rounded to 2 decimal places — always >= 2.0 when this event fires |

### Example trigger

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_stall_detected
    event_data:
      vacuum_entity_id: "vacuum.alfred"
```

**Practical use:** Alert when the robot is stuck or taking unusually long in one room, then decide whether to intervene.

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_stall_detected
    event_data:
      vacuum_entity_id: "vacuum.alfred"
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "Alfred may be stuck"
      message: >
        Stalled in {{ trigger.event.data.room_name }}
        ({{ trigger.event.data.elapsed_minutes }} min,
        expected {{ trigger.event.data.expected_minutes }} min,
        ratio {{ trigger.event.data.stall_ratio }}x)
```

---

## eufy_vacuum_path_blocked

### When it fires

Fires when a monitored entity (a door sensor, a binary sensor, or any state-tracked entity configured as a path blocker) changes state while a job is active, and that state change affects at least one remaining room in the queue. The integration computes which rooms are directly blocked (the room itself is behind the blocker) and which are indirectly blocked (the only access path to that room passes through a blocked room).

This event fires once per unique blocking signature. If the same combination of blocker entity, state, and affected rooms is already recorded on the active job, the event is suppressed to prevent duplicate firings on rapid state fluctuations.

The event also carries the outcome of whatever `path_block_action` was configured for the job (`event_only`, `pause_and_event`, or `cancel_and_event`). When the action is `cancel_and_event` and the cancellation succeeds, `eufy_vacuum_job_finished` fires first, then `eufy_vacuum_path_blocked` fires with `action_taken: "cancelled"`.

### Payload fields

| Field | Type | Description |
|---|---|---|
| `vacuum_entity_id` | `str` | Entity ID of the vacuum |
| `map_id` | `str` | Map ID the job is running on |
| `job_id` | `str \| null` | Job identifier |
| `trigger_entity_id` | `str` | Entity ID of the blocker that changed state |
| `trigger_entity_state` | `str` | New state of the triggering entity |
| `affected_remaining_room_ids` | `list[str]` | IDs (as strings) of all remaining rooms that are now blocked (directly or indirectly) |
| `affected_remaining_room_names` | `list[str]` | Human-readable names of those rooms |
| `directly_blocked_room_ids` | `list[str]` | Rooms whose own access is directly blocked by the triggering entity |
| `indirectly_blocked_room_ids` | `list[str]` | Rooms blocked because their access path passes through a directly blocked room |
| `remaining_room_ids` | `list[str]` | All remaining (unfinished) room IDs in the current queue at the time of the event |
| `reason_codes` | `list[str]` | Deduplicated set of reason codes from the affected rooms' block configurations |
| `affected_rooms` | `list[dict]` | Full detail list of affected rooms, each containing `room_id`, `name`, and `reason` |
| `requires_attention` | `bool` | Always `true` |
| `event_scope` | `str` | Always `"active_job_path_blocked"` |
| `path_block_action` | `str` | The configured action — `event_only`, `pause_and_event`, or `cancel_and_event` |
| `action_taken` | `str` | What actually happened — `event_only`, `paused`, `pause_failed`, `already_paused`, `cancelled`, or `cancel_failed` |
| `action_result` | `dict` | Present only when an action was attempted; contains the result from `pause_active_job` or `cancel_active_job` |

### Example trigger

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_path_blocked
    event_data:
      vacuum_entity_id: "vacuum.alfred"
```

**Practical use:** When using `event_only` mode (you want manual control), send a notification listing which rooms are now unreachable so you can decide to pause, re-route, or cancel.

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_path_blocked
    event_data:
      vacuum_entity_id: "vacuum.alfred"
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "Alfred: path blocked"
      message: >
        {{ trigger.event.data.trigger_entity_id }} went
        {{ trigger.event.data.trigger_entity_state }}.
        Affected rooms:
        {{ trigger.event.data.affected_remaining_room_names | join(', ') }}
```
