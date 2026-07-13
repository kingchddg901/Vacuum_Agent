# 04 — Automation Examples

This section gives ready-to-use Home Assistant automation YAML for the most common
eufy_vacuum patterns. Every example is built from the actual event names, service
names, and payload fields used in the integration — nothing here is invented.

---

## The automation surface (what you can call)

The integration exposes ~60 services, but most are dashboard-card getters and one-time
setup CRUD. For **automations** you touch a small, high-level surface — you say *what* and
*when*, and the integration owns *how* (payload assembly, room ordering, availability
gating, mixed-mode water safety). There are deliberately **no per-setting entities to poke**;
the intelligence is not meant to live in your automation.

**What an automation writes (per room):**

| Entity | Purpose |
|---|---|
| `switch.<vacuum>_<room>_selected_for_cleaning` | Include/exclude the room. On = `enabled` = in the payload. |
| `number.<vacuum>_<room>_order` | Clean order for that room. |

Per-room *settings* (mode, fan, water, intensity, passes, edge-mop) are **not** pokeable
entities — set them with the `update_room_fields` service (one call per room) or by applying
a profile.

**The verbs, by job:**

| Job | Services |
|---|---|
| **Start a clean** | `start_selected_rooms`, `start_run_profile`, `start_zone_clean`, `apply_run_profile` |
| **Configure rooms** | `update_room_fields`, `apply_room_profile` |
| **Control in-flight** | `pause_active_job`, `resume_active_job`, `cancel_active_job` |
| **Dock / upkeep** | `wash_mop`, `dry_mop`, `stop_dry_mop`, `empty_dust`, `reset_maintenance`, `battery_rebaseline` |
| **Learning** | `set_learning_processing`, `process_pending_runs` |
| **Read state** (each returns a `response_variable`) | `get_start_status`, `get_active_job`, `get_job_progress_snapshot`, `get_lifecycle_state`, `get_vacuum_capabilities`, `get_saved_run_profiles` |

**The normal sequence** is always the same shape:

1. **Select** — flip the room switches, or `update_room_fields` (enable + settings in one call), or apply a profile.
2. **Start** — `start_selected_rooms` (ad-hoc) or `start_run_profile` (a saved routine).
3. **React** (optional) — trigger on an `eufy_vacuum_*` event, or poll a `get_*` getter.

Every example below is a worked case of that shape. Full per-field docs for every service
live in **Developer Tools → Actions** in Home Assistant (and in `services.yaml`).

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

If the profile carries an ordered `steps` list — room **groups** separated by
`charge_wait` or `wait` stops — `start_run_profile` runs the whole sequence as
one job: it cleans a group, docks and charges to the target (or holds for the
wait), then continues with the next group. Nothing about the automation changes;
the same service call runs a plain profile or a stepped one.

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
        profile_id: full_house
        confirm_reduced_run: true
        path_block_action: pause_and_event
        # map_id is optional — defaults to the vacuum's current active map.
        # Set it explicitly only if you need to target a stored secondary map.
```

**Finding your `profile_id`:** Call `eufy_vacuum.get_saved_run_profiles` with
just your `vacuum_entity_id` (the map auto-resolves). The response lists every
saved run profile; use the `id` field from the profile you want.

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
- To define a stepped profile programmatically, call
  `eufy_vacuum.set_run_profile_steps` with the `profile_id` and an ordered
  `steps` list. Each step is a room group
  (`{type: room_group, rooms: [...]}`), a charge stop
  (`{type: charge_wait, target_battery_percent: 95}`, clamped 1–100), or a
  dry/hold stop (`{type: wait, wait_minutes: 20}`, clamped 1–1440). Leading and
  trailing stops are dropped and consecutive same-type stops collapse; the list
  must contain at least one room group.
- To watch the charge/wait phase from an automation, read
  `eufy_vacuum.get_job_progress_snapshot`. It exposes `charge_phase_active`,
  `charge_target_percent`, `charge_eta_minutes` (and `charge_eta_source`), plus
  `wait_phase_active` and `wait_minutes`. The `eufy_vacuum_job_progress_tick`
  event fires every 5 s during an active job as a "refresh now" trigger for
  re-reading the snapshot.

**Caveats:**

- If the profile's run is reduced by active blocker rules and
  `confirm_reduced_run` is `false` (the default), the service returns
  `{"started": false, "reason": "confirmation_required"}` (alongside
  `message`, `warning`, `preflight`, and `confirm_token`) and the job does
  not start. An automation that inspects the response must test
  `started == false` and `reason == "confirmation_required"` — there is no
  `status` field. Set `confirm_reduced_run: true` for fully automated
  schedules.
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
| `duration_minutes` | float or null | Total wall-clock duration of the job in minutes |
| `actual_cleaning_minutes` | float or null | Minutes the vacuum spent actively cleaning |
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
| `action_taken` | string | What the integration actually did: `event_only`, `already_paused`, `paused`, `pause_failed`, `cancelled`, `cancel_failed` |

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

---

## 6. Ad-hoc Room Clean (custom selection)

**What it does:** Builds a one-off clean from a specific set of rooms — the modern
replacement for hand-assembling a `vacuum.send_command` payload from a wall of helper
entities. The integration builds the queue, resolves the map, applies mixed-mode water
safety, and gates on availability; the automation only says *which* rooms and *how*.

**Entity-driven** — when the rooms are already configured the way you want and you only
need to pick which run (`on` = `enabled` = in the payload):

```yaml
automation:
  alias: "Vacuum — quick downstairs"
  trigger:
    - platform: state
      entity_id: input_button.clean_downstairs
  action:
    # 1. Select rooms
    - service: homeassistant.turn_on
      target:
        entity_id:
          - switch.alfred_kitchen_selected_for_cleaning
          - switch.alfred_hallway_selected_for_cleaning
    # 2. Start them
    - service: eufy_vacuum.start_selected_rooms
      data:
        vacuum_entity_id: vacuum.alfred
        confirm_reduced_run: true
```

**Service-driven** — when the automation should also set per-room behavior in the same
run. `update_room_fields` sets `enabled` **and** any settings in one call, so no
per-setting entities are needed and no switch toggle is required (`enabled: true` selects
the room):

```yaml
  action:
    - service: eufy_vacuum.update_room_fields
      data:
        vacuum_entity_id: vacuum.alfred
        room_id: 5               # Kitchen
        enabled: true
        clean_mode: vacuum_mop   # vacuum | mop | vacuum_mop
        fan_speed: Max
        water_level: High
    - service: eufy_vacuum.update_room_fields
      data:
        vacuum_entity_id: vacuum.alfred
        room_id: 4               # Hallway
        enabled: true
        clean_mode: vacuum       # carpet-safe: vacuum only
    - service: eufy_vacuum.start_selected_rooms
      data:
        vacuum_entity_id: vacuum.alfred
        confirm_reduced_run: true
```

**Customization points:**

- `confirm_reduced_run: true` keeps it unattended — the run proceeds even if blocker rules
  would reduce the room set. Omit it (default `false`) and the service returns
  `{"started": false, "reason": "confirmation_required", "confirm_token": ...}` instead of
  starting, so a supervised automation can inspect the response and decide.
- `update_room_fields` changes **only** the fields you pass; unset fields keep their stored
  values. It sets `profile_name` to `custom` to mark the room as diverged from a preset.
- **Water-on-carpet is enforced at payload time** regardless of what you pass — a carpet
  room is never wet-mopped even if you set a `water_level`.
- Add `strict_order: true` to `start_selected_rooms` to force the vacuum to honor the
  `number.<room>_order` sequence instead of path-optimizing.
- `start_selected_rooms` needs the vacuum docked/idle and returns an error if a job is
  already running. Guard with a `condition` on
  `states('vacuum.alfred') in ['docked','idle']` if the trigger might fire mid-run.

**Finding a `room_id`:** call `eufy_vacuum.get_vacuum_maps` (or `get_queue_state`) with a
`response_variable` — the response lists each room's `room_id` and name. These are the
device's own room numbers (the same ones the Eufy app uses).

---

## 7. Staged Clean with Native Waits (charge break in automation land)

**What it does:** Runs a multi-phase clean — vacuum, charge, then mop — where the
**automation** owns the pauses instead of a stepped run profile. Each phase is a normal
`start_selected_rooms` call; between phases you use Home Assistant's own wait primitives.

This is the inverse of a stepped run profile: there, the integration owns the `charge_wait`
break internally and the whole thing is *one* job. Here you orchestrate it in the open, and
every primitive you need is already exposed:

| Between-phase wait | How |
|---|---|
| **Phase finished** | `wait_for_trigger` on `eufy_vacuum_job_finished` |
| **Charge break** | the vacuum docks automatically after a clean — just `wait_template` on the battery level |
| **Timed hold** | plain `delay` |

```yaml
automation:
  alias: "Vacuum — vacuum, charge, then mop the main floor"
  trigger:
    - platform: time
      at: "09:00:00"
  action:
    # --- Phase 1: vacuum ---
    - service: eufy_vacuum.update_room_fields
      data: { vacuum_entity_id: vacuum.alfred, room_id: 5, enabled: true, clean_mode: vacuum }
    - service: eufy_vacuum.update_room_fields
      data: { vacuum_entity_id: vacuum.alfred, room_id: 7, enabled: true, clean_mode: vacuum }
    - service: eufy_vacuum.start_selected_rooms
      data: { vacuum_entity_id: vacuum.alfred, confirm_reduced_run: true }

    # Wait for phase 1 to finish (the vacuum docks itself at the end)
    - wait_for_trigger:
        - platform: event
          event_type: eufy_vacuum_job_finished
          event_data: { vacuum_entity_id: vacuum.alfred }
      timeout: "01:30:00"
      continue_on_timeout: false

    # --- Charge break: wait for the level (swap for `delay:` to make it a timed hold) ---
    - wait_template: "{{ state_attr('vacuum.alfred', 'battery_level') | int(0) >= 90 }}"
      timeout: "02:00:00"
      continue_on_timeout: false

    # --- Phase 2: mop the same rooms ---
    - service: eufy_vacuum.update_room_fields
      data: { vacuum_entity_id: vacuum.alfred, room_id: 5, enabled: true, clean_mode: mop, water_level: High }
    - service: eufy_vacuum.update_room_fields
      data: { vacuum_entity_id: vacuum.alfred, room_id: 7, enabled: true, clean_mode: mop, water_level: High }
    - service: eufy_vacuum.start_selected_rooms
      data: { vacuum_entity_id: vacuum.alfred, confirm_reduced_run: true }
```

**Learning still works — and it's actually cleaner.** Each phase goes out through
`start_selected_rooms`, so it is a **dispatched** job (started by the integration, not the
app). Every phase is captured and feeds per-room learning normally, with no attribution
guesswork — the integration sent the rooms, so it knows exactly what ran. And because the
charge happens *between* two separate jobs, it is invisible to either job's timing: the
vacuum phase learns vacuum timing, the mop phase learns mop timing, and the dead charge
time is learned by nobody. A stepped run profile has to *deliberately exclude* the
`charge_wait` phase from its timing; this pattern never has that problem, because there is
no charge inside a job to exclude.

**Choosing between this and a stepped run profile:**

| | Stepped run profile | Native waits (this) |
|---|---|---|
| **Records** | One composite `vac → charge → mop` job | One record per phase |
| **Charge timing** | Excluded via break-phase logic | Free — charge is dead time between jobs |
| **Orchestration** | Owned by the integration | Owned by your automation (transparent, debuggable) |
| **Room learning** | Yes | Yes, per phase |

Both feed learning. Pick the profile when you want one tidy record; pick native waits when
you want to see and control each phase.

**Customization points:**

- Swap the `wait_template` for `delay: "00:20:00"` to make it a timed hold instead of a
  charge break.
- `continue_on_timeout: false` aborts the sequence if a phase never finishes, so a stuck
  vacuum doesn't fall through into the mop phase. Raise the `timeout` values to fit your home.
- Confirm the battery attribute on your vacuum entity — most report `battery_level`, but
  check Developer Tools if the `wait_template` never releases.

**Caveats:**

- **The `enabled`/selected flag persists — a run does not clear it.** The example re-cleans
  the *same* rooms, so re-enabling them for phase 2 is harmless. If a later phase cleans a
  **different** set of rooms, first turn the previous phase's rooms **off**
  (`homeassistant.turn_off` on their `switch.<vac>_<room>_selected_for_cleaning`, or
  `update_room_fields` with `enabled: false`) so they don't run again.
- `start_selected_rooms` needs the vacuum docked/idle. After a charge break it will be
  docked, so phase 2 starts cleanly — but a phase that doesn't return to the dock first
  should be gated on `states('vacuum.alfred') in ['docked','idle']`.
