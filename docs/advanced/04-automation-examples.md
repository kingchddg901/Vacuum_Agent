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
| **Start a clean** | `start_selected_rooms`, `start_run_profile`, `apply_run_profile` |
| **Clean a zone** | `clean_saved_zone`, `clean_saved_zones` (named saved zones); `start_zone_clean` (free-form rectangles) |
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

---

## 8. Clean a Saved Zone on a Trigger

**What it does:** Fires a [saved zone](../user-guide/04a-zones.md) — a named region you drew
once ("under the table", "the litter corner", "the entryway") — as a one-off clean when
something happens. This is the automation form of tapping **Clean** on a saved zone: a
precise sub-room clean, no whole-room run.

Use `clean_saved_zone` for one zone, or `clean_saved_zones` for several at once (the device
cleans the whole set in a single run).

```yaml
automation:
  alias: "Vacuum — clean under the table after dinner"
  description: >
    Clean the 'under the table' saved zone every evening at 8 PM.
  trigger:
    - platform: time
      at: "20:00:00"
  condition:
    # Fire-and-forget zone cleans only run when their map is the ACTIVE map, and
    # need the vacuum free — gate on a docked/idle vacuum to avoid a refusal.
    - condition: state
      entity_id: vacuum.alfred
      state:
        - docked
        - idle
  action:
    - service: eufy_vacuum.clean_saved_zone
      data:
        vacuum_entity_id: vacuum.alfred
        map_id: "6"                 # the zone's map — must be the currently active map
        zone_id: zone_abc123        # the saved zone to clean
        clean_times: 1              # optional passes (defaults to the device default)
```

**Cleaning several zones at once** — swap the service and pass a list:

```yaml
    - service: eufy_vacuum.clean_saved_zones
      data:
        vacuum_entity_id: vacuum.alfred
        map_id: "6"
        zone_ids:
          - zone_abc123             # under the table
          - zone_def456             # the entryway
        clean_times: 1
```

**Finding your `map_id` and `zone_id`:** call `eufy_vacuum.get_vacuum_maps` with a
`response_variable` for the map ids; each saved zone's `zone_id` is shown in the card's
**Saved Zones** panel (and in the `get_map_segments` response). Per-brand caps apply to a
batch — Eufy up to 10 zones, Roborock up to 5.

**Customization points:**

- Any trigger works — a time, an `input_button`, a person leaving, a `binary_sensor` (a
  litter box, a rain sensor). The zone clean is just the action.
- `clean_times` is optional; omit it to use the device default, or raise it for a dirtier
  spot.
- To fold a zone into a *whole-room* run instead of firing it alone — "vacuum the kitchen,
  then hit the stove zone, then mop" — don't use these services; build a stepped run
  profile with a **zone step** and start it with `start_run_profile` (Recipe 3). See
  [Zones → Add a zone to a run](../user-guide/04a-zones.md#add-a-zone-to-a-run-a-zone-step).

**Caveats:**

- **Fire-and-forget.** These are not tracked as a room-queue job — there is no job record,
  no per-room learning, and no `eufy_vacuum_job_finished` event for the zone clean. (A
  zone run *inside* a stepped profile, by contrast, is tracked and learned.)
- **Active-map only.** A saved zone cleans only when its map is the vacuum's current active
  map; on a different map the service refuses. On a single-map home this is never an issue.
- The vacuum must be free to take the command — hence the docked/idle condition above.

---

## 9. Pre-Run Conditions

**Start *when*, not *charge first*.** The integration owns what happens *inside* a job — the sequencer runs a job's
room groups, charge/wait stops, and zone steps as one choreographed unit (Recipe 3). Home
Assistant owns *whether and when a job starts*. So the things you might picture as "steps
before the run" — *charge to full first, then run* · *only run off-peak* · *hold until
9 AM* — aren't internal steps at all. They're **conditions on your start automation**. That
keeps each job a clean, self-contained unit the learning system can trust, and puts the
"when" where it belongs: in HA's triggers and conditions, out in the open.

Three patterns cover almost every "before the run" wish:

| Wish | Express it as |
|---|---|
| **Run at / after a time** | a `time` trigger (or a `delay`) before the start call — Recipe 3 |
| **Only run once charged** | the vacuum is already docked and charging; **wait for the battery level**, then start — no internal "leading charge" needed, the dock does the charging and HA just waits |
| **Only run off-peak** | a `time` window (and/or battery) **condition** guarding the start |

```yaml
automation:
  alias: "Vacuum — overnight run, but only once charged and off-peak"
  description: >
    At 1 AM, wait until the battery is topped up, then start the full-house
    profile — but only during the off-peak window.
  trigger:
    - platform: time
      at: "01:00:00"
  condition:
    # Off-peak window guard (skip entirely outside it).
    - condition: time
      after: "00:00:00"
      before: "06:00:00"
  action:
    # "Charge first" is just waiting for the level — the vacuum charges on its
    # own dock; the automation holds until it's ready, then starts.
    - wait_template: "{{ state_attr('vacuum.alfred', 'battery_level') | int(0) >= 95 }}"
      timeout: "03:00:00"
      continue_on_timeout: false
    - service: eufy_vacuum.start_run_profile
      data:
        vacuum_entity_id: vacuum.alfred
        profile_id: full_house
        confirm_reduced_run: true
```

**Why not a "leading charge step" inside the job?** Because a charge *before* any cleaning
isn't choreography — it's a start pre-condition, and the vacuum already charges itself on
the dock. Modelling it as an internal step would bury a "when to start" decision inside the
job, where it can't see your automation's triggers and would muddy the job's timing. A
charge *between* two cleaning phases (vacuum → charge → mop) genuinely *is* intra-job
choreography — that one belongs to the sequencer, as a stepped run profile (Recipe 3) or as
native between-phase waits (Recipe 7).

**Customization points:**

- Swap the `wait_template` battery threshold to taste, or drop it if you don't care about
  the level.
- Replace the time window with any condition — an energy-price sensor, a "nobody home"
  presence check, a `sun` condition.
- `continue_on_timeout: false` means a vacuum that never reaches the level simply doesn't
  run, rather than starting under-charged.

**Caveats:**

- `wait_template` needs the battery attribute to actually change — confirm your vacuum
  reports `battery_level` (most do) in Developer Tools, or the wait will sit until timeout.
- Keep the `timeout` sane so a stuck automation eventually releases instead of hanging for
  a day.
