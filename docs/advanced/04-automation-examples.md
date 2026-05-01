# Automation Examples

This section gives ready-to-use Home Assistant automation YAML for the most common
eufy_vacuum patterns. Every example is built from the actual event names, service
names, and payload fields used in the integration — nothing here is invented.

---

## 1. Retry Missed Rooms

**What it does:** When a run ends early (cancelled, failed, or interrupted) and at
least one queued room was not cleaned, the integration fires
`eufy_vacuum_run_incomplete`. This automation catches that event and immediately
calls `eufy_vacuum.retry_missed_rooms` to re-queue only the skipped rooms and
start a new job.

```yaml
automation:
  alias: "Vacuum — retry missed rooms"
  description: >
    Re-queue and restart only the rooms that were skipped after an
    incomplete run. Triggered by eufy_vacuum_run_incomplete.
  trigger:
    - platform: event
      event_type: eufy_vacuum_run_incomplete
      event_data:
        vacuum_entity_id: vacuum.alfred
  condition: []
  action:
    - service: eufy_vacuum.retry_missed_rooms
      data:
        vacuum_entity_id: "{{ trigger.event.data.vacuum_entity_id }}"
        # map_id is optional — the service reads it from the incomplete run log.
        # confirm_reduced_run defaults to true, which is the right default for
        # automation use since there is no interactive confirmation step.
```

**Customization points:**

- Replace `vacuum.alfred` in the trigger `event_data` filter with your vacuum
  entity ID. Filtering by `vacuum_entity_id` in the trigger is recommended when
  you have more than one vacuum so the automation does not fire for the wrong
  device.
- You can set `map_id` explicitly if you need to override the map that was active
  during the incomplete run. In most cases you can omit it.
- Set `confirm_reduced_run: false` if you want the retry to abort rather than
  proceed when blocker rules are still active. The default (`true`) keeps things
  fully automated.
- Add a `path_block_action` field (`event_only`, `pause_and_event`, or
  `cancel_and_event`) to control what happens if a path-blocking rule fires
  during the retry run itself.

**Caveats:**

- The service returns `{"started": false, "reason": "no_missed_rooms"}` if the
  incomplete run log is absent or already cleared. In a pure event-triggered
  automation this is harmless, but you can add a `wait_for_trigger` or a
  `condition` checking the `eufy_vacuum_run_incomplete` payload's
  `missed_room_ids` list if you want to guard against edge cases.
- `retry_missed_rooms` clears the incomplete run log on success. Calling it twice
  for the same event will result in a no-op on the second call.

---

## 2. Stall Response

**What it does:** When the vacuum has been in a room for at least twice its learned
duration threshold and is still waiting to exit, the integration fires
`eufy_vacuum_stall_detected`. This automation sends a mobile notification that
includes the room name, how long the vacuum has been there, and how long it was
expected to take.

The event fires at most once per room per job, so you will not receive duplicate
alerts for the same stall.

```yaml
automation:
  alias: "Vacuum — stall alert"
  description: >
    Send a notification when the vacuum stalls in a room for longer than
    its learned threshold.
  trigger:
    - platform: event
      event_type: eufy_vacuum_stall_detected
      event_data:
        vacuum_entity_id: vacuum.alfred
  condition: []
  action:
    - service: notify.mobile_app_your_phone
      data:
        title: "Vacuum stalled — {{ trigger.event.data.room_name }}"
        message: >
          {{ trigger.event.data.vacuum_entity_id }} has been in
          {{ trigger.event.data.room_name }} for
          {{ trigger.event.data.elapsed_minutes | round(1) }} min
          (expected {{ trigger.event.data.expected_minutes | round(1) }} min,
          ratio {{ trigger.event.data.stall_ratio | round(2) }}).
          It may need attention.
```

**Event payload fields used:**

| Field | Type | Description |
|---|---|---|
| `vacuum_entity_id` | string | Entity ID of the vacuum |
| `map_id` | string | Map the job is running on |
| `room_id` | int | Room where the stall was detected |
| `room_name` | string | Display name of the stalled room |
| `elapsed_minutes` | float | Minutes the vacuum has been in this room |
| `expected_minutes` | float | Learned expected duration for this room |
| `stall_ratio` | float | `elapsed / expected` — always >= 2.0 at fire time |

**Customization points:**

- Replace `notify.mobile_app_your_phone` with your notification service.
- Add an `if` condition on `trigger.event.data.stall_ratio` to suppress
  notifications below a threshold you consider acceptable (for example, only
  alert when `stall_ratio > 3`).
- You can also automatically pause or cancel the job from this automation by
  calling `eufy_vacuum.pause_active_job` or `eufy_vacuum.cancel_active_job`
  with the `vacuum_entity_id` and `map_id` from the event payload.

---

## 3. Scheduled Clean with a Run Profile

**What it does:** Runs a saved run profile on a fixed schedule using
`eufy_vacuum.start_run_profile`. The service applies the profile's room
selection and per-room settings, rebuilds the queue, and starts the job through
the same protected start flow used by the dashboard card.

```yaml
automation:
  alias: "Vacuum — weekday morning full clean"
  description: >
    Start the 'Full House' run profile every weekday at 9 AM.
  trigger:
    - platform: time
      at: "09:00:00"
  condition:
    - condition: time
      weekday:
        - mon
        - tue
        - wed
        - thu
        - fri
  action:
    - service: eufy_vacuum.start_run_profile
      data:
        vacuum_entity_id: vacuum.alfred
        map_id: map_6
        profile_id: full_house
        confirm_reduced_run: true
        path_block_action: pause_and_event
```

**Finding your `profile_id`:** Call `eufy_vacuum.get_saved_run_profiles` with
your `vacuum_entity_id` and `map_id`. The response lists every saved run profile;
use the `id` field from the profile you want.

**Customization points:**

- Adjust the `at` time and `weekday` list to match your schedule.
- Set `confirm_reduced_run: false` if you want the job to abort rather than
  start with a reduced set of rooms when blockers are active. The default is
  `false` for `start_run_profile` — set it to `true` explicitly if you want
  fully unattended operation.
- `path_block_action` controls what happens mid-run if a blocker rule fires.
  `pause_and_event` is a good default for attended schedules (you get an alert
  and the job pauses). Use `cancel_and_event` for overnight or unattended runs.
- Add `pause_timeout_minutes_override: 30` to cap how long the job may remain
  paused before it auto-cancels. Set it to `0` to disable auto-cancel for this
  run.

**Caveats:**

- If the profile's run is reduced by active blocker rules and
  `confirm_reduced_run` is `false` (the default), the service returns
  `{"status": "confirmation_required"}` and the job does not start. Set
  `confirm_reduced_run: true` for fully automated schedules.
- `start_run_profile` requires the vacuum to be docked and idle. It will return
  an error if a job is already in progress.

---

## 4. Post-Job Notification

**What it does:** Sends a summary notification every time a job finishes. The
`eufy_vacuum_job_finished` event includes a `room_count` and a `status` field so
you can see at a glance whether the run completed normally or was cancelled.

```yaml
automation:
  alias: "Vacuum — job finished summary"
  description: >
    Send a notification when any job finishes, including the room count
    and final status.
  trigger:
    - platform: event
      event_type: eufy_vacuum_job_finished
      event_data:
        vacuum_entity_id: vacuum.alfred
  condition: []
  action:
    - service: notify.mobile_app_your_phone
      data:
        title: >
          Vacuum job {{ trigger.event.data.status }}
        message: >
          {{ trigger.event.data.vacuum_entity_id }} finished
          {% if trigger.event.data.room_count is not none %}
          cleaning {{ trigger.event.data.room_count }} room(s).
          {% else %}
          a cleaning job.
          {% endif %}
          Status: {{ trigger.event.data.status }}.
          {% if trigger.event.data.reason_detail %}
          Detail: {{ trigger.event.data.reason_detail }}.
          {% endif %}
          Finalized at: {{ trigger.event.data.finalized_at }}.
```

**Event payload fields used:**

| Field | Type | Description |
|---|---|---|
| `vacuum_entity_id` | string | Entity ID of the vacuum |
| `map_id` | string | Map the job ran on |
| `job_id` | string or null | Unique job identifier |
| `status` | string | Outcome: `completed`, `cancelled`, `failed`, `interrupted` |
| `reason_detail` | string or null | Human-readable lifecycle message |
| `used_for_learning` | bool or null | Whether the job was used to update learned stats |
| `finalized_at` | string or null | ISO timestamp when the job was finalized |
| `room_count` | int or null | Number of rooms in the job |
| `job_path` | string or null | Path to the archived job file |

**Customization points:**

- Filter on `status` in the trigger `event_data` to only notify for specific
  outcomes — for example, `status: cancelled` to alert when a job did not
  complete.
- Use `job_id` to look up more detail with `eufy_vacuum.get_active_job` or to
  cross-reference learning history.
- `room_count` is `null` when the job record does not include it (rare, typically
  manual finalization). Guard against it with `is not none` as shown above.

---

## 5. Path Blocked Alert

**What it does:** When a blocker rule fires during an active job and one or more
remaining rooms become inaccessible, the integration fires
`eufy_vacuum_path_blocked`. This automation sends a notification listing which
rooms are affected so you can decide whether to intervene.

The event fires at most once per unique blocked-room signature per job, so you
will not receive duplicate alerts for the same blocking state.

```yaml
automation:
  alias: "Vacuum — path blocked alert"
  description: >
    Notify when a path-blocking rule fires during an active job and
    remaining rooms can no longer be reached.
  trigger:
    - platform: event
      event_type: eufy_vacuum_path_blocked
      event_data:
        vacuum_entity_id: vacuum.alfred
  condition: []
  action:
    - service: notify.mobile_app_your_phone
      data:
        title: "Vacuum path blocked"
        message: >
          {{ trigger.event.data.vacuum_entity_id }} — path blocked
          during job {{ trigger.event.data.job_id }}.
          Affected rooms:
          {{ trigger.event.data.affected_remaining_room_names | join(', ') }}.
          Trigger entity: {{ trigger.event.data.trigger_entity_id }}
          ({{ trigger.event.data.trigger_entity_state }}).
          Action taken: {{ trigger.event.data.action_taken }}.
```

**Event payload fields used:**

| Field | Type | Description |
|---|---|---|
| `vacuum_entity_id` | string | Entity ID of the vacuum |
| `map_id` | string | Map the job is running on |
| `job_id` | string or null | Unique job identifier |
| `trigger_entity_id` | string or null | HA entity whose state change triggered the block |
| `trigger_entity_state` | string or null | New state of the trigger entity |
| `affected_remaining_room_ids` | list of strings | IDs of rooms now blocked or inaccessible |
| `affected_remaining_room_names` | list of strings | Display names of those rooms |
| `directly_blocked_room_ids` | list of strings | Rooms blocked by a direct blocker rule |
| `indirectly_blocked_room_ids` | list of strings | Rooms blocked by access dependency on a blocked room |
| `remaining_room_ids` | list of strings | All remaining room IDs in the job at fire time |
| `reason_codes` | list of strings | Unique reason strings from affected rooms |
| `affected_rooms` | list of dicts | Full per-room block detail (source, reason, rule IDs) |
| `requires_attention` | bool | Always `true` when this event fires |
| `event_scope` | string | Always `"active_job_path_blocked"` |
| `path_block_action` | string | The `path_block_action` that was configured for this run |
| `action_taken` | string | What the integration actually did: `none`, `paused`, `pause_failed`, `cancelled`, `cancel_failed` |

**Customization points:**

- The `path_block_action` the integration takes (pause, cancel, or event-only)
  is configured when you start the job via `start_run_profile` or
  `start_selected_rooms`, not in this automation. This automation is the
  notification layer that runs regardless of which action was taken.
- Use `trigger.event.data.action_taken` in your message to communicate whether
  the vacuum was paused or cancelled automatically.
- If you set `path_block_action: event_only` on the job, you can use this
  automation to take your own action — for example, calling
  `eufy_vacuum.cancel_active_job` after sending a notification.
- You can also filter notifications by `trigger.event.data.directly_blocked_room_ids`
  to distinguish a hard block (a rule matched) from an indirect block (a downstream
  room became unreachable because its access-gating room was blocked).
