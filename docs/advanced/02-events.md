# 02 — HA Events Reference

The integration fires events on the Home Assistant event bus at specific points in a cleaning job's lifecycle. You can listen to any of these events in an automation using the `event` trigger platform. All payloads are plain dictionaries — no custom objects to unwrap.

This page explains **when** each event fires and **why** you would listen for it. For the exhaustive machine-derived list — every event, every payload key, which fire sites write it, and where each one lives in source — see the generated [Event Reference](../dev/reference/EVENTS.md). It is regenerated from the fire sites themselves and CI fails if it falls behind, so where the two disagree on a *fact*, that one is right.

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
| `reason_detail` | `str \| null` | Human-readable lifecycle message, e.g. `"pause_timeout"`. On the auto-finalize paths (lifecycle/pause-timeout/path-blocker) it falls back to the `status` string when no lifecycle message is present, so a clean completion reports `"completed"` rather than `null` there. Only the `eufy_vacuum.finalize_learning_job` service path uses the lifecycle message alone and yields `null` for clean completions. |
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

Fires when the integration determines the robot has begun cleaning a new room. There are several firing sites, distinguished by `source`:

- `source: "job_start"` — fired immediately after a job is started, for the first room in the queue
- `source: "counter_plateau"` — fired when the live cleaned-area counter plateaus, signalling the robot has moved on to the next room (the primary live-rollover path for Eufy)
- `source: "timing_rollover"` — fired when the previous room's timing threshold is exceeded and the integration advances to the next room in the queue
- `source: "bounds_exit_early"` — fired when a confident coordinate signal advances to the next room before the timing threshold is reached
- `source: "native_signal"` — the Roborock native current-room rollover path: the device reports the live room directly, suppressing the counter/timing rollover for that job

### Payload fields

| Field | Type | Description |
|---|---|---|
| `vacuum_entity_id` | `str` | Entity ID of the vacuum |
| `map_id` | `str` | Map ID the job is running on |
| `job_id` | `str` | Job identifier |
| `room_id` | `str` | Room ID as a string |
| `room_name` | `str` | Human-readable room name |
| `started_at` | `str \| null` | ISO 8601 timestamp of when the room started |
| `source` | `str` | One of `"job_start"`, `"counter_plateau"`, `"timing_rollover"`, `"bounds_exit_early"`, or `"native_signal"` |
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

Fires when the integration marks a room complete and advances to the next one. This is the same `_maybe_roll_current_room_by_timing` path that also fires `eufy_vacuum_room_started` for the following room. The rollover happens because the live cleaned-area counter plateaued (`source: "counter_plateau"`, the primary live path for Eufy), because the room's timing threshold was exceeded (`source: "timing_rollover"`), or because the device reported the live room directly via the Roborock native current-room rollover (`source: "native_signal"`, which suppresses the counter/timing rollover for that job). A legacy `source: "bounds_exit_early"` value still exists in the finalize code but is **dormant** — the coordinate-based fast-rollover producer that once set it (`MappingTracker._signal_fast_rollover`) was removed with the mapping split, so it no longer fires in current builds.

### Payload fields

| Field | Type | Description |
|---|---|---|
| `vacuum_entity_id` | `str` | Entity ID of the vacuum |
| `map_id` | `str` | Map ID the job is running on |
| `job_id` | `str \| null` | Job identifier |
| `room_id` | `str` | ID of the room that was just completed |
| `room_name` | `str` | Human-readable name of the completed room |
| `completed_at` | `str` | ISO 8601 timestamp of completion |
| `source` | `str` | One of `"counter_plateau"`, `"timing_rollover"`, `"bounds_exit_early"`, or `"native_signal"` |
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
[30 — External Runs](../dev/30-external-runs.md).

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

Fires from the **mapping tracker** when the device's **native current-room** signal indicates the robot has left a room — confirmed through a confidence/dwell debounce (`CONFIDENCE_THRESHOLD = 0.85` in `mapping/tracker.py`) — and carries that room's dwell duration. This is distinct from the timing-rollover path that fires `eufy_vacuum_room_finished`. It requires the adapter to expose the native current-room signal (the `active_cleaning_target` entity); the earlier coordinate/boundary-box mechanism — and its `robot_position_x` / `robot_position_y` requirement — was removed with the mapping split.

Because it is driven by the device's own current-room signal rather than learned timing, it can fire for rooms the learning system has no history for, and it fires independently of whether the room was part of the current queue.

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

Fires on a fixed 5-second interval from the job-progress listener (`listeners/job_progress.py`) for every managed vacuum/map that has a run in flight — active-job status `started`, `paused`, or `external` (an app-started run being captured) — and stops once the job is finalized. On each tick the listener recomputes the job progress snapshot (the same path that can fire `eufy_vacuum_stall_detected`) and then emits this event so dashboards and automations can refresh on a heartbeat rather than polling a service.

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

**There are THREE independent triggers, not one.** All three fire this same event, and a
`trigger` field says which noticed — so a consumer can word the notification for what
actually happened, and [stall capture](#eufy_vacuum_stall_captured) stays a single
subscriber.

| `trigger` | noticed by | means |
|---|---|---|
| `"timing"` | `ActiveJobTracker.detect_run_anomalies` (`jobs/active_job.py`) | the robot has been in one room far longer than that room's learned estimate |
| `"error"` | `apply_stuck_watch_tick` (`core/manager.py`) | the device itself reported a fault that has not recovered — the robot is telling you it is stuck |
| `"area"` | `apply_stuck_watch_tick` (`core/manager.py`) | the robot is still running but has **stopped covering floor** — cleaned area barely moved over a whole window |

The `error` and `area` triggers ride the same 5-second progress tick as the timing one
(`listeners/job_progress.py`), so all three share one cadence contract.

**Their dedup guarantees are NOT the same** — this matters if you automate on the event:

- **`timing`** — at most **once per room per job** (`_stall_notified_room_ids` on the
  active job).
- **`error`** — **edge-triggered**: fires when an error episode OPENS and not again until
  it closes and re-opens. A fault that persists for an hour fires once.
- **`area`** — fires once per window; the window is then **restarted**, so a robot that
  keeps making no progress fires again after each further window.

**The `area` and `error` limits are framework defaults, deliberately not per-brand**
(`jobs/stuck_watch.py`): `window_minutes` **15.0**, `min_progress_m2` **2.0**,
`max_unreadable_fraction` **0.5**. An adapter may override them with a `stuck_watch`
block, and neither shipped adapter does — a value defaulted only on Eufy would be
inherited by every other brand as somebody else's number.

The `error` trigger deliberately treats **every** un-recovered fault as stuck rather than
matching a list of known-stuck codes, and it fires even when the code is `None` (the Eufy
path for a trapped robot leaves the message empty). A brand may silence specific codes via
`error_tracking.stuck_silence_codes` — an opt-out list, not an opt-in one.

---

The **timing** trigger specifically fires from `ActiveJobTracker.detect_run_anomalies`
(in `jobs/active_job.py`). The anomaly fields (`stall_detected`, `elapsed_minutes`, `expected_minutes`, `stall_ratio`) are recomputed fresh on **every** call to this method — including a pure `get_job_progress_snapshot()` read triggered by a card poll — but the event fire and the per-room dedup bookkeeping only happen when the caller passes `emit=True`. The **only** caller that does is `EufyVacuumManager.apply_job_progress_tick`, invoked once per vacuum/map by the 5-second [`eufy_vacuum_job_progress_tick`](#eufy_vacuum_job_progress_tick) ticker — a card polling `get_job_progress_snapshot` directly sees the same computed fields but fires nothing and persists no dedup state.

The event fires when all of the following are true:

1. ~~The vacuum's adapter honors dispatched clean order.~~ **No longer a condition for a stall** — `26c4b2d7` removed that gate, so `eufy_vacuum_stall_detected` fires on path-optimizing brands (Roborock) too. `adapter_honors_clean_order` still gates the `running_long` and `skipped` anomalies, which are queue-order arithmetic; it is a static per-adapter capability declaration (`capabilities.honors_clean_order` in the adapter config) — a job's `strict_order` flag does not change it. The whole stall/`running_long` branch below is skipped for an adapter that doesn't honor order — such a run never fires this event.
2. The integration is already in `current_room_overdue` state for the current room — meaning the room's timing threshold was met but it has not yet rolled over (no counter plateau or native-signal completion has advanced past it)
3. The robot has been in the room for **at least the stall ratio × the learned timing threshold** for that room — the ratio comes from the adapter's `anomaly.stall_ratio`, default **2.0×**

On a **grouped** phase (multiple rooms dispatched together as one phase, with no per-room rollover), the threshold in condition 3 is the **sum** of the group members' individual learned thresholds rather than just the current room's — a group's first room stays "current" for the whole phase, so comparing it against a single-room threshold would false-positive by an order of magnitude. Members with no timing entry contribute nothing to the sum.

The tracker records which rooms have already triggered the TIMING trigger per job via `_stall_notified_room_ids` on the active job, so **the timing trigger fires at most once per room per job** regardless of how many ticks occur while it stays stalled.

This event does **not** require learned timing data — an unlearned room still gets a timeline entry via the ~6-minute default estimate (`source: "default"`), and the threshold calculation runs the same either way. The stall check is skipped only when the current room (or, for a grouped phase, every member of the group) has no timeline entry at all — i.e. it isn't part of the active job's resolved rooms.

The maintainer-only [`eufy_vacuum.dev_inject_stall`](03-services.md#dev_inject_stall) service fires this same event synthetically, marked with `injected: true`. It is not part of the supported surface and should never be called on a run whose records matter — see the service's own warning.

[Stall capture](#eufy_vacuum_stall_captured) subscribes to this event and, when armed, renders a picture of the stalled room and fires `eufy_vacuum_stall_captured` with the file path.

### Payload fields

| Field | Type | Description |
|---|---|---|
| `vacuum_entity_id` | `str` | Entity ID of the vacuum |
| `map_id` | `str` | Map ID the job is running on |
| `room_id` | `int` | ID of the stalled room (integer, not a string) |
| `room_name` | `str` | Human-readable name of the stalled room |
| `trigger` | `str` | Which watcher noticed: `"timing"`, `"error"` or `"area"`. **The remaining fields depend on this** — a consumer must branch on it rather than assume the timing shape. |
| **— `trigger: "timing"` only —** | | |
| `elapsed_minutes` | `float` | How long the robot has been in the room, rounded to 1 decimal place |
| `expected_minutes` | `float` | The learned timing threshold for the room, rounded to 1 decimal place. On a grouped phase this is the **sum** of the group members' thresholds, not one room's — see above. |
| `stall_ratio` | `float` | `elapsed_minutes / expected_minutes`, rounded to 2 decimal places — always >= the configured stall ratio (default 2.0) when this event fires |
| **— `trigger: "error"` only —** | | |
| `error_code` | `str \| None` | The device's fault code on the open episode. **May be `None`** — the Eufy path for a trapped robot records no code, and that case still fires. |
| `error_message` | `str \| None` | The device's fault message, likewise possibly empty. |
| **— `trigger: "area"` only —** | | |
| `window_minutes` | `float` | Length of the measuring window that elapsed with no progress (default 15.0). |
| `progress_m2` | `float` | Cleaned area gained across that window, 2 dp — the number that fell short. |
| `min_progress_m2` | `float` | The floor it had to clear (default 2.0). |
| **— all triggers —** | | |
| `injected` | `bool` | Present **only** on a synthetic stall fired by the maintainer-only `eufy_vacuum.dev_inject_stall` service, where it is `true`. A real detection omits the key entirely, and an injected one carries `null` for `elapsed_minutes`, `expected_minutes`, and `stall_ratio` — there is no real timing behind it. Guard on `trigger.event.data.injected is not defined` if an automation must ignore synthetic stalls. |

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

> **Soft tier — `running_long`.** Below the 2× stall there is a softer "this room is taking a while" band that does **not** fire its own event. The `get_job_progress_snapshot` response (and each `eufy_vacuum_job_progress_tick`) carries `running_long` (bool), `running_long_room_id` (int \| null), and `running_long_ratio` (float \| null). It is set when the current room has run between `running_long_ratio` (default **1.5×**, from the adapter's `anomaly` block) and `stall_ratio` (default **2.0×**) of its learned threshold **with no pending counter transition** — i.e. genuinely lingering rather than mid-roll. It is disjoint from the stall event by band, so a room is at most one of `running_long` or stalled at a time. Poll the snapshot to surface it; there is no event-bus trigger for the soft tier.

---

## eufy_vacuum_stall_captured

### When it fires

Fires after a **stall capture** has been rendered and written to disk. Stall capture is an opt-in consumer of [`eufy_vacuum_stall_detected`](#eufy_vacuum_stall_detected): when a stall is detected the integration renders the room the robot stopped in — the room's own shape, the robot's position, and the ±30 s pose trail around the stall instant — writes it as a PNG, raises a persistent notification, and then fires this event carrying the file path.

It fires only when **all** of the following hold:

1. Capture is **armed** for that vacuum via [`eufy_vacuum.set_stall_capture`](03-services.md#set_stall_capture). Absent means off — a feature that writes pictures of your home is never inherited by an upgrade.
2. The vacuum has usable map render data (the room-id raster and its decode parameters).
3. The stalled room has cells to draw and Pillow is installed. When either is missing there is no picture and no event — the absence is silent by design, not an error.

The detector itself is unaffected by the switch: `eufy_vacuum_stall_detected` and the card's run-anomaly reporting fire either way. Arming only adds this consumer. That also means "notification but no photo" points at the capture, not the detection.

### Where the image lands

`<config>/eufy_vacuum/learning/<vacuum>/stall/<map_id>.png` — beside the rest of that vacuum's learning data, using the vacuum's object ID (`vacuum.alfred` → `alfred`) and a sanitised map ID.

It is deliberately **not** written under `www/`. That directory is served at `/local/` without authentication, so putting it there would publish a cropped floor plan of your home at a fetchable URL on every stall. The consequence for automations: there is no `/local/` URL for the image — use a notifier that accepts a filesystem path (see the [stall-photo recipe](04-automation-examples.md#10-send-the-stall-photo-to-your-phone)).

There is **one file per (vacuum, map)**, overwritten on each capture — no accumulation and nothing to prune, and the path is stable enough to hard-code. The write is atomic (temp file plus rename), so an automation that reads the moment the event arrives never sees half a PNG.

### Payload fields

| Field | Type | Description |
|---|---|---|
| `vacuum_entity_id` | `str` | Entity ID of the vacuum |
| `map_id` | `str` | Map ID the job is running on, as a string |
| `room_id` | `int` | ID of the stalled room, forwarded unchanged from `eufy_vacuum_stall_detected` |
| `room_name` | `str` | Human-readable name of the stalled room |
| `image_path` | `str` | Absolute path to the PNG just written. Provided so an automation never has to reconstruct the storage layout by hand. |
| `message` | `str` | The same one-line text as the persistent notification, e.g. `Alfred likely stalled in Kitchen on map 6`. "Likely" is deliberate — the detector is an elapsed-versus-estimate ratio, not proof the robot is stuck. |

### Example trigger

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_stall_captured
    event_data:
      vacuum_entity_id: "vacuum.alfred"
```

**Practical use:** forward the picture to your phone so you can see *where* the robot stopped without opening Home Assistant. See [Automation Examples §10](04-automation-examples.md#10-send-the-stall-photo-to-your-phone) for a working automation.

---

## eufy_vacuum_room_skipped

### When it fires

Fires when the **live job queue advances past a queued room that was never cleaned** — a non-sequential advance. The integration computes this in `ActiveJobTracker.detect_run_anomalies` (in `jobs/active_job.py`), invoked by `get_job_progress_snapshot()`, as the conservative "skipped" set: any room positioned strictly **before** the current room in queue order that is not in `completed_room_ids`.

For Eufy this is **almost never** observed: Eufy's sequential counter rollover keeps `completed_room_ids` a contiguous prefix of the queue, so there is no room "left behind" to attribute. The hook exists for position-reliable brands or transition-detection paths that can legitimately jump forward, and to future-proof the queue model. There is no false-positive heuristic — if the skip can't be proven from the queue order, the event does not fire.

> The reliable, post-run signal for rooms that ended up uncleaned remains [`eufy_vacuum_run_incomplete`](#eufy_vacuum_run_incomplete), derived at finalization. `eufy_vacuum_room_skipped` is the *live, mid-run* counterpart and is intentionally conservative.

The integration tracks which rooms have already fired this event per job via `_skipped_notified_room_ids` on the active job, so **it fires at most once per room per job** regardless of how many snapshot polls occur.

### Payload fields

| Field | Type | Description |
|---|---|---|
| `vacuum_entity_id` | `str` | Entity ID of the vacuum |
| `map_id` | `str` | Map ID the job is running on, as a string |
| `job_id` | `str \| null` | Job identifier |
| `room_id` | `int` | ID of the skipped room (integer, not a string) |
| `room_name` | `str` | Human-readable name of the skipped room, or `"Room {id}"` if unknown |
| `completed_room_ids` | `list[int]` | Room IDs completed in this job at the time of the skip |

### Example trigger

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_room_skipped
    event_data:
      vacuum_entity_id: "vacuum.alfred"
```

**Practical use:** Get a live heads-up that a room was passed over mid-run, rather than waiting for the post-run `eufy_vacuum_run_incomplete` summary. Note this is rare for Eufy — most "missed room" automations should still key off `eufy_vacuum_run_incomplete`.

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_room_skipped
    event_data:
      vacuum_entity_id: "vacuum.alfred"
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "Alfred skipped a room"
      message: "Passed over {{ trigger.event.data.room_name }} mid-run"
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

---

## eufy_vacuum_boundary_saved

### When it fires

**Never, in current builds.** The event name is still defined (`EVENT_BOUNDARY_SAVED` in `mapping/tracker.py`), but no code in the repo fires it — the room-boundary derivation mechanism that once produced it was removed with the mapping split. It is listed here only so you do not build an automation on it: an automation triggered on this event will never run.
