# Error Tracker — Developer Reference

> **Scope:** Complete implementation reference for `core/error_tracker.py`. Every constant, buffer, edge-detection rule, and lifecycle hook is derived directly from the source. A developer should be able to re-implement the error tracker from this document alone.

---

## 1. Overview

The error tracker observes vacuum error signals in real time and latches them into three per-device buffers so the learning system can harvest a meaningful error payload at job-end. It does **not** expose HA entities or fire events directly — it is an internal accumulator consumed by `learning/job_finalizer.py`.

**Design goals:**

- Detect rising and falling error edges across three channels simultaneously.
- Tolerate firmware timing gaps — some devices emit the state-change DPS before the error-message DPS, so a 5-second grace window defers finalization.
- Never lose an error that arrives during a run, even if the message arrives after the error state clears.
- Remain brand-agnostic: all entity IDs and sentinel strings are read from the adapter registry.

**Module:** `custom_components/eufy_vacuum/core/error_tracker.py`

---

## 2. Constants

| Constant | Value | Purpose |
|---|---|---|
| `_ERROR_MESSAGE_GRACE_SECONDS` | `5` | Seconds to wait after a secondary-channel error fires before finalizing as "Unknown error" if no message has arrived |
| `_RECENT_ERRORS_LIMIT` | `50` | Maximum entries retained in the `recent_errors` rolling buffer per device |
| `_LATCH_ERRORS_LIMIT` | `50` | Maximum entries retained in the `active_run_error` latch per device |

---

## 3. Storage Layout

All state lives at `data["error_tracker"][vacuum_entity_id]`. The outer key is the vacuum entity ID string (`"vacuum.alfred"`). The inner dict has three keys:

```
data["error_tracker"]["vacuum.alfred"] = {
    "active_run_error":  [...],   # errors latched during the current run
    "last_device_error": [...],   # most recent error per device (persists across jobs)
    "recent_errors":     [...],   # rolling window of all observed errors
}
```

Each buffer contains error record dicts. All three share the same record shape (see §4).

The tracker initializes the storage path lazily — `start()` creates the per-device dict for each vacuum ID if it does not already exist.

---

## 4. Error Record Shape

When an error is finalized and written to a buffer, the record contains:

| Field | Type | Description |
|---|---|---|
| `vacuum_entity_id` | str | Which vacuum the error belongs to |
| `job_id` | str \| None | Active job ID at time of error (None if no job was active) |
| `error_message` | str | Human-readable error string (primary channel) or `"Unknown error during run"` if grace expired |
| `error_code` | int \| None | Numeric error code from vacuum state attributes; attribute keys tried in order: `error_code`, `code`, `errorCode` — first non-zero int wins |
| `vacuum_state` | str | `vacuum.state` value at time of finalization |
| `task_status` | str | `task_status` entity state at time of finalization |
| `timestamp` | str | ISO-8601 timestamp of finalization |
| `source` | str | `"error_message"` (primary) or `"secondary_channel"` |

---

## 5. Three Error Channels

The tracker watches three independent signals simultaneously:

### 5.1 Primary Channel — `error_message` sensor

Entity ID read from `adapters.registry.get_adapter_value(vacuum_entity_id, "entities", "error_message")`.

A rising error edge on the primary channel fires when the sensor state transitions **out of** the "not_error" sentinel set into any other non-empty value.

**Not-error sentinel set:** `frozenset({"", "unknown", "unavailable"})` merged with any brand-specific sentinels declared under `vocabulary.not_error_sentinels` in the adapter config. The generic sentinel set is always included regardless of what the adapter declares.

### 5.2 Secondary Channel A — `vacuum.state`

The main vacuum entity. An error is detected when `state.state == "error"` (exact string, lowercase).

### 5.3 Secondary Channel B — `task_status` sensor

Entity ID read from adapter config `entities.task_status`.

An error is detected when `task_status.state == "error"` (exact string, lowercase). This channel mirrors the vacuum state channel — the Eufy firmware flips both simultaneously on hardware fault conditions.

### 5.4 Secondary Error Predicate

```python
def _is_in_secondary_error(hass, vacuum_entity_id) -> bool:
    vacuum_state = hass.states.get(vacuum_entity_id)
    task_state   = hass.states.get(task_status_entity_id)
    return (
        (vacuum_state and vacuum_state.state == "error")
        or (task_state and task_state.state == "error")
    )
```

Both checks are OR'd — either alone triggers secondary-channel error detection.

---

## 6. Grace Window

When a secondary-channel error is detected **before** the primary channel fires an error message, the tracker starts a 5-second countdown:

```python
async_call_later(hass, _ERROR_MESSAGE_GRACE_SECONDS, _on_grace_expired)
```

During the grace window the tracker waits for the `error_message` sensor to update with a real message. If the primary channel fires within the window, the grace timer is cancelled and the primary-channel message is used. If the window expires while the device is still in error state, the error is finalized with `error_message = "Unknown error during run"` and `source = "secondary_channel"`.

The grace callback is stored per-vacuum and cancelled on rising primary-channel edge.

---

## 7. Public API

### 7.1 Lifecycle

```python
tracker.start(vacuum_entity_ids: list[str]) -> None
```
Registers state-change listeners for all watched entities across all vacuum IDs. Initializes per-device storage if absent.

```python
tracker.stop() -> None
```
Unsubscribes all listeners and cancels any pending grace timers. Called from `EufyVacuumManager.async_will_remove_from_hass()`.

### 7.2 Harvest

```python
tracker.harvest_active_run(vacuum_entity_id: str, job_id: str) -> list[dict]
```
Returns the contents of `active_run_error` for the given vacuum and clears the buffer. Called by `learning/job_finalizer.py` at job-end to collect any errors that occurred during the job. Returns an empty list if no errors were latched.

### 7.3 Acknowledge

```python
tracker.acknowledge(vacuum_entity_id: str, scope: str = "both") -> None
```
Clears one or more error buffers for a vacuum. Used by the panel's "acknowledge errors" action.

| `scope` value | Effect |
|---|---|
| `"active_run"` | Clears only `active_run_error` |
| `"last_device"` | Clears only `last_device_error` |
| `"both"` (default) | Clears both `active_run_error` and `last_device_error` |

`recent_errors` is never cleared by `acknowledge` — it is a non-destructive rolling log.

### 7.4 Update Listeners

```python
unsub = tracker.add_update_listener(callback: Callable) -> Callable
```
Registers a callback invoked whenever the tracker writes a new error record to any buffer. The callback receives no arguments. Returns an unsubscribe callable.

---

## 8. Buffer Limits

All three buffers enforce maximum lengths on append:

- `active_run_error`: capped at `_LATCH_ERRORS_LIMIT` (50). Oldest entries dropped when limit is reached.
- `last_device_error`: replaced entirely on each write (single-entry semantics, not a rolling list).
- `recent_errors`: capped at `_RECENT_ERRORS_LIMIT` (50). Oldest entries dropped when limit is reached.

---

## 9. Adapter Registry Dependencies

The tracker reads the following from the adapter registry at runtime:

| Registry path | Used for |
|---|---|
| `entities.error_message` | Primary channel entity ID |
| `entities.task_status` | Secondary channel B entity ID |
| `vocabulary.not_error_sentinels` | Brand-specific non-error strings merged into the generic sentinel set |
| `error_tracking.task_status_error_value` | Task status string that triggers secondary channel (default: `"error"`) |
| `error_tracking.grace_window_seconds` | Grace window duration (default: `_ERROR_MESSAGE_GRACE_SECONDS = 5`) |
| `error_tracking.error_code_attribute_names` | Attribute key list for numeric error code extraction |

All lookups use `get_adapter_value()` with safe fallbacks — the tracker degrades gracefully if adapter config is incomplete.

---

## 10. Integration Points

| Caller | Method called | When |
|---|---|---|
| `EufyVacuumManager.async_setup()` | `tracker.start(vacuum_entity_ids)` | Integration load |
| `EufyVacuumManager.async_will_remove_from_hass()` | `tracker.stop()` | Integration unload |
| `learning/job_finalizer.py` | `tracker.harvest_active_run(vacuum_entity_id, job_id)` | Job finalization |
| Panel error-acknowledge service | `tracker.acknowledge(vacuum_entity_id, scope)` | User action |
