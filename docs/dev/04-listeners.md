# 04 — Listeners Package

> **Scope:** Complete implementation reference for `listeners/`. Every module's register/remove surface, event triggers, vocabulary dependencies, timers, and side effects are derived directly from the source. A developer should be able to re-implement the listeners package from this document alone.

---

## 1. Overview

The `listeners/` package contains eight listener modules that register HA event and state-change subscriptions at integration load time: `lifecycle`, `dock_events`, `path_blockers`, `pause_timeout`, `job_progress`, `job_metrics`, `discovery`, and `pose_sampler`. (`_common.py` is a shared helper module, not a listener — see §2.) Each listener module has a consistent two-function public surface:

```python
register(hass: HomeAssistant) -> None
remove(hass: HomeAssistant) -> None
```

There is no `manager` parameter — each module resolves the manager from
`hass.data[DOMAIN][DATA_RUNTIME]` itself. Unsubscribe callables are stored under
a module-specific key in `hass.data[DOMAIN]` (or in module-level dicts).
`remove()` cancels all subscriptions registered by that module.

All listeners are wired from `__init__.py` `async_setup_entry` (each module's
`register(hass)`) and torn down from `async_unload_entry` (each module's
`remove(hass)`).

---

## 2. Shared Helpers (`_common.py`)

`listeners/_common.py` provides utilities used across multiple listener modules.

### 2.1 Adapter vocabulary helpers

```python
get_adapter_vocab(vacuum_entity_id, section, key, fallback) -> frozenset
```
Reads a list/set value from the adapter config and returns it as a `frozenset`. Returns the fallback frozenset if the key is missing or the value is empty.

```python
get_adapter_value(vacuum_entity_id, *path, fallback) -> Any
```
Traverses nested adapter config dicts by the given key path. Returns fallback on any missing key or type error.

### 2.2 Entity watch helpers

```python
get_lifecycle_watch_entities(vacuum_entity_id: str) -> list[str]
```
Returns the full list of entities the lifecycle listener watches for one vacuum:
- `vacuum_entity_id` itself
- `entities.task_status`
- `entities.dock_status`
- `entities.active_cleaning_target`
- `entities.active_map`

```python
is_job_active(hass, vacuum_entity_id, *, unavailable_is_active=False) -> bool
```
The job-active binary probe. Returns `True` when the adapter declares `entities.job_active` and that binary sensor currently reads `"on"`; returns `False` for brands that don't declare it (e.g. Eufy), making every caller a no-op for them. When `unavailable_is_active=True`, an existing-but-`unavailable`/`unknown` entity counts as active (used by the recharge-resume guard so a transient cloud blip during a mid-job recharge dock doesn't finalize early). Used for the recharge-resume completion guard and strict-order completion gating (§3.4).

```python
completed_finalize_signals(hass, vacuum_entity_id) -> dict
```
Reads current state for all lifecycle-watch entities and returns a snapshot dict used in completion checks.

```python
completion_secondary_satisfied(vacuum_entity_id, completion_signals, clear_sentinels) -> bool
```
The adapter-driven secondary-clear check used in the completion gate (§3.4). When the brand declares `completion.require_job_active_clear` (Roborock), the sentinel check is bypassed (returns `True`) — the job-active binary clearing is the completion signal instead, enforced separately by `is_job_active`. Otherwise (default, Eufy) it requires the snapshot's `active_target` to read one of `clear_sentinels`.

### 2.3 Event payload builder

```python
job_finished_event_data(
    *,
    vacuum_entity_id: str,
    map_id: str,
    finalize_result: dict,
) -> dict
```
Builds the consistent payload dict fired with every `eufy_vacuum_job_finished` event.

---

## 3. Lifecycle Listener (`lifecycle.py`)

Watches all lifecycle-watch entities across all managed vacuums. Drives job start/completion detection.

**Module:** `listeners/lifecycle.py`

### 3.1 Constants

| Constant | Value | Description |
|---|---|---|
| `_ACTIVE_LIFECYCLE_STATES` | `{"active_job_running", "mid_job_service"}` | lifecycle_state values (from evaluate_job_lifecycle) that count as "active lifecycle observed" |
| `_DEFAULT_COMPLETION_TASK_STATUS` | `"completed"` | Default task_status string signalling job done |
| `_DEFAULT_CLEAR_SENTINELS` | `frozenset({"", "unknown", "unavailable", "none", "null"})` | Default active_cleaning_target values that indicate target cleared |

### 3.2 What it watches

`async_track_state_change_event` on every entity returned by `get_lifecycle_watch_entities()` for every managed vacuum.

### 3.3 Processing pipeline

On each state change, the `_process()` coroutine runs:

1. `record_active_job_transition(vacuum_entity_id, new_state)` — records state machine transitions.
2. `update_active_job_recharge_observation(vacuum_entity_id)` — tracks mid-job recharge events.
3. If dock entity changed: check for mop-wash trigger, call `update_active_job_mop_wash_observation()` if applicable.
4. `record_active_lifecycle_observed(vacuum_entity_id)` — sets `has_observed_active_lifecycle = True` when task_status enters an active lifecycle state. For brands declaring `completion.require_job_active_clear`, arming additionally requires `is_job_active(hass, vacuum_entity_id)` (strict `"on"`, so an indeterminate binary at start can't arm the flag).
5. Completion check.

### 3.4 Completion check

Job is considered complete when **all three** conditions hold simultaneously:

```
task_status   == completion_task_status_value  (from adapter "completion.task_status_value" or "completed")
active_target in clear_sentinels               (from adapter "completion.secondary_clear_sentinels")
has_observed_active_lifecycle == True          (set when task_status entered an active lifecycle state)
```

Even when all three hold, finalization is then suppressed by two guards:

- **Recharge-resume guard.** If `is_job_active(hass, vacuum_entity_id, unavailable_is_active=True)` is `True`, finalization is skipped. A brand may dock and report `task_status=charging` mid-job to recharge, then resume; while the job-active binary stays on (or transiently `unavailable`/`unknown`), the resumed half stays the same job. No-op for brands without `entities.job_active` (e.g. Eufy).
- **Strict-order dispatch guard.** If the active job has `_phase_dispatch_pending` set (a just-advanced sequenced phase whose watchdog hasn't yet confirmed the device started the new room), finalization is skipped so the prior room's lingering completion signals don't finalize the next phase before it starts. No-op for non-sequenced jobs.

A sequenced (multi-phase) job that passes both guards does **not** finalize: `manager.maybe_advance_phase()` advances to the next phase (re-dispatch) and returns `True`, skipping finalization. Atomic jobs — every adapter today — return `False` and fall through to the finalization steps below; each phase finalizes only when it is the last.

On completion:
1. `finalize_learning_for_active_job(vacuum_entity_id)` — awaited directly (async).
2. `mark_active_job_finalized(vacuum_entity_id)` — closes the active job slot.
3. Fires `eufy_vacuum_job_finished` event with payload from `job_finished_event_data()`.
4. If job was a mop job: `register_post_job_water_amendment()` — wires the water amendment watcher.

### 3.5 MappingTracker integration

- On first active lifecycle observation: `MappingTracker.start_job()` called via executor (starts position recording).
- On job finalization: `MappingTracker.end_job()` called via executor (stops recording).

---

> **External-run detection.** Before the per-map internal loop, the lifecycle
> listener calls `manager.maybe_handle_external_run()` — a vacuum cleaning with
> no dispatched job is an app-started run, opened as a `status="external"`
> capture slot and finalized to a pending review record when it docks. See
> [28-external-run-ingestion](28-external-run-ingestion.md).

## 4. Dock Events Listener (`dock_events.py`)

Watches dock status entities and records dock cycle events via `DockManager`.

**Module:** `listeners/dock_events.py`

Builds `watched: dict[str, str]` mapping dock_entity_id → vacuum_entity_id for all managed vacuums.

On dock_status state change:
1. Reads `dock_events.triggers` from adapter config.
2. Normalizes the new state (`.strip().lower()`).
3. For each `event_type` in the triggers dict: if normalized state matches any trigger string, call `DockManager.record_dock_event(vacuum_entity_id, event_type, dry_duration)`.
4. For `last_dry_start` events: reads dry duration from the entity at `adapter_config["entities"]["dry_duration"]`.

---

## 5. Path Blockers Listener (`path_blockers.py`)

Watches binary sensors configured as path blockers for rooms and fires `eufy_vacuum_path_blocked` events.

**Module:** `listeners/path_blockers.py`

Builds `watch_map: dict[str, list[tuple[str, str]]]` mapping entity_id → [(vacuum_entity_id, map_id)]. Re-registers itself via `register_room_update_callback` whenever rooms change, so newly added blocker sensors are picked up without an integration restart.

On watched entity state change to `"on"`:
1. Reads the `path_block_action` for the active job. Values:
   - `"event_only"` (default): fires `eufy_vacuum_path_blocked` only.
   - `"pause_and_event"`: pauses the job and fires the event.
   - `"cancel_and_event"`: cancels the job, fires `eufy_vacuum_job_finished`, then fires `eufy_vacuum_path_blocked`.

---

## 6. Pause Timeout Watchdog (`pause_timeout.py`)

Cancels jobs that have been paused longer than the configured timeout.

**Module:** `listeners/pause_timeout.py`

**Timer:** `async_track_time_interval` fires every **1 minute**.

On each tick:
1. Calls `get_paused_job_timeout_report()` for each managed (vacuum, map) pair.
2. If a report is returned (timeout exceeded): calls `async_cancel_active_job()` and fires `eufy_vacuum_job_finished`.

Returns `None` from `get_paused_job_timeout_report()` when no timeout has been exceeded — the common case on every tick.

---

## 7. Job Progress Ticker (`job_progress.py`)

Pushes periodic progress snapshots for active jobs.

**Module:** `listeners/job_progress.py`

**Timer:** `async_track_time_interval` fires every **5 seconds**.

On each tick:
- Only processes vacuums with active jobs in `{"started", "paused"}` status.
- For **non-phased (contiguous) active jobs only**, calls `manager.maybe_pulse_live_room_refresh(vacuum_entity_id)` (Lever B) *before* the snapshot, keeping the brand's live current-room/map fresh so per-room rollover + live fan track the adapter's interval rather than the device's slower native map cadence. Strict-order phased runs (those carrying `phases`, which advance one room per dispatched phase and dock between rooms) are excluded — they already get a free refresh on each state flip. The pulse is a no-op unless the adapter declares `dispatch.live_room_refresh`; per-vacuum rate-limiting and local-gating live inside the `live_refresh` subsystem (`LiveRoomRefreshManager` in `live_refresh/manager.py`, reached via the `maybe_pulse_live_room_refresh` manager delegator).
- Calls `get_job_progress_snapshot()` — drives stall detection and bounds-exit derivation.
- Fires `eufy_vacuum_job_progress_tick` event with the snapshot for each active (vacuum, map).

---

## 8. Job Metrics Listener (`job_metrics.py`)

Tracks cleaning time, cleaning area, and station water during active jobs.

**Module:** `listeners/job_metrics.py`

Watches three entities per vacuum (sourced from adapter `entities` block):

| Entity key | Active-job field written |
|---|---|
| `cleaning_time` | `last_cleaning_time_seconds` (int) |
| `cleaning_area` | `last_cleaning_area_m2` (float) |
| `entities.water_level` or station water entity | `last_station_water_percent` (float) |

On state change: validates the new value is numeric, converts to the target type, and calls `record_active_job_sensor_value(vacuum_entity_id, key, value)`.

---

## 9. Discovery Listener (`discovery.py`)

Triggers room discovery on lifecycle events and periodic intervals.

**Module:** `listeners/discovery.py`

**Trigger types** (from adapter config `discovery.auto_refresh_on`):

| Trigger | HA event / condition |
|---|---|
| `"vacuum_docked"` | dock_status transitions to a docked-vocabulary state |
| `"active_map_changed"` | active_map entity state changes |
| `"config_entry_reload"` | integration startup (fires once on `register()`) |

**Optional periodic refresh:** `async_track_time_interval` fires every `discovery.auto_refresh_interval_seconds` seconds (default: 6 hours / 21,600 seconds). Only registered if the adapter declares a non-zero interval.

On trigger: calls `run_discovery_pass(hass, manager, vacuum_entity_id)` from `setup/drift.py`.

Uses `_make_run_pass(vid)` closure-binding pattern to avoid late-binding bugs in loop registration.

---

## 10. Pose Sampler (`pose_sampler.py`)

Records the per-tick robot pose time-series during an **external** (app-started) run, for room auto-attribution (W5b). It is the production version of the throwaway `debug_log_live_room` probe.

**Module:** `listeners/pose_sampler.py`

**Timer:** `async_track_time_interval`. The period is the **smallest declared `room_attribution.tuning.interval_s` across all configured vacuums** (one ticker samples them all). The value is resolved from the adapter — never hardcoded: adapter `room_attribution.tuning.interval_s` → else the resolved engine's `DEFAULT_TUNING['interval_s']` → else a last-resort `_FALLBACK_INTERVAL_S` of 2 s. No adapter declaring `room_attribution` ⇒ no ticker is registered at all.

**Gating** (a vacuum is skipped this tick unless all hold):
- **External runs only.** Only `(vacuum, map)` pairs whose active job has `status == "external"` are sampled — dispatched runs already know their rooms.
- **Live-pose-capable vacuums only.** The vacuum's adapter must declare `map_state_source.live_pose`; without it `current_room` is always `None` and sampling is pointless.
- **Live pose present this tick.** `manager.async_get_map_live_pose()` must return `present` — otherwise the tick is skipped rather than polluting the buffer with `None`.

On each qualifying tick it reads the declared `entities.cleaning_area` value and records one sample via `manager.record_pose_sample(...)` (`current_room`, `anchor`, `cleaning_area`, `heading`). While the robot is parked/docked — detected primarily from the MQTT `task_status` not being one of the adapter's `vocabulary.active_run_task_states` (more reliable than eufy-clean's pose `robot_docked` flag), with the pose flag as a fallback — `current_room` and `anchor` are nulled so a dock-sitting tick is not mis-attributed to the dock's room.

**Capture-only / inert** — nothing consumes `pose_samples` yet; the engine wiring is W5c.

---

## 11. Module Summary

| Module | Trigger type | Period | Primary side effect |
|---|---|---|---|
| `lifecycle.py` | State change (lifecycle entities) | — | Job start/finish detection, learning finalization, event fire |
| `dock_events.py` | State change (dock entities) | — | Dock cycle recording via DockManager |
| `path_blockers.py` | State change (binary sensors) | — | `eufy_vacuum_path_blocked` event, optional pause/cancel |
| `pause_timeout.py` | Time interval | 1 min | Cancel timed-out paused jobs |
| `job_progress.py` | Time interval | 5 sec | `eufy_vacuum_job_progress_tick` event (+ Lever B live-room refresh pulse on contiguous runs) |
| `job_metrics.py` | State change (metric entities) | — | Record cleaning time/area/water into active job |
| `discovery.py` | State change + time interval | 6 hr | Run discovery pass, update drift history |
| `pose_sampler.py` | Time interval | min adapter `room_attribution.interval_s` (fallback 2 s) | Record per-tick pose sample into the external run slot (`record_pose_sample`), external-run/live-pose-gated |
