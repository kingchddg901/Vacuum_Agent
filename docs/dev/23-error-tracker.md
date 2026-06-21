# Error Tracker — Developer Reference

> **Scope:** Complete implementation reference for `core/error_tracker.py`. Every constant, buffer, edge-detection rule, and lifecycle hook is derived directly from the source. A developer should be able to re-implement the error tracker from this document alone.

---

## 1. Overview

The error tracker observes vacuum error signals in real time and latches them into three per-device fields (two single-value latches plus one ring buffer — see §3) so the learning system can harvest a meaningful error payload at job-end. It is consumed by `learning/job_finalizer.py` at job-end **and** surfaced through three HA entities (`sensor.<obj>_active_run_error`, `sensor.<obj>_last_device_error`, `binary_sensor.<obj>_active_run_has_error`) that subscribe via `add_update_listener`.

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

All state lives at `data["error_tracker"][vacuum_entity_id]`. The outer key is the vacuum entity ID string (`"vacuum.alfred"`). The inner record dict has three keys, **two of which are single values and one of which is a list**:

```
data["error_tracker"]["vacuum.alfred"] = {
    "active_run_error":  {...} | None,   # single latch for the current run, or None
    "last_device_error": {...} | None,   # single most-recent-error dict, or None
    "recent_errors":     [...],          # rolling ring buffer of error dicts
}
```

`active_run_error` and `last_device_error` are each initialized to `None` (not a list). They hold a single dict when populated. `recent_errors` is the only list. The three values have **different shapes** — see §4.

The tracker initializes the per-device record lazily — `_ensure_record()` (called from `start()`, the read accessors, and every edge handler) creates the per-device dict with the three default keys (`None`, `None`, `[]`) if it does not already exist, and back-fills any missing key on an existing record.

---

## 4. Record Shapes

The three values in a per-device record have distinct shapes.

### 4.1 `active_run_error` — the run latch

A single latch dict (or `None`). Formed on the first rising edge while a job is active, extended on subsequent rising edges, and nulled out on harvest. Fields:

| Field | Type | Description |
|---|---|---|
| `active_job_id` | str | Job ID in flight when the latch first formed |
| `first_seen_at` | str | ISO-8601 timestamp of the first rising edge |
| `last_seen_at` | str | ISO-8601 timestamp of the most recent rising or falling edge |
| `first_seen_job_elapsed_seconds` | int | Seconds into the job when the first error fired |
| `error_count` | int | Number of rising edges accumulated into this latch |
| `current_message` | str | Latest error message (`""` after recovery) |
| `current_code` | int \| None | Latest numeric error code (`None` after recovery) |
| `errored_room_id` | str \| None | `current_room_id` of the active job at first error |
| `recovered` | bool | `True` once the message clears mid-run; flips back to `False` on a fresh rising edge |
| `errors` | list[dict] | Per-edge sub-records, capped at `_LATCH_ERRORS_LIMIT` (see §4.4) |

**Per-edge entry inside `errors[]`:**

| Field | Type | Description |
|---|---|---|
| `message` | str | Error string for this edge |
| `code` | int \| None | Numeric code for this edge |
| `captured_at` | str | ISO-8601 timestamp |
| `job_elapsed_seconds` | int | Seconds into the job at this edge |
| `room_id` | str \| None | Active-job room at this edge |
| `recovered_at` | str \| None | ISO-8601 timestamp stamped when this edge recovers (else `None`) |

### 4.2 `last_device_error` — most recent error

A single dict (or `None`), overwritten on every rising edge regardless of run context:

| Field | Type | Description |
|---|---|---|
| `message` | str | Human-readable error string |
| `code` | int \| None | Numeric error code (see §4.4 for extraction) |
| `captured_at` | str | ISO-8601 timestamp |
| `vacuum_state_at_capture` | str \| None | `vacuum.state` value at capture |
| `was_during_active_run` | bool | True if a job was in flight |
| `active_job_id_at_capture` | str \| None | Job ID at capture, if any |

### 4.3 `recent_errors` — ring buffer entry

Each entry in the `recent_errors` list:

| Field | Type | Description |
|---|---|---|
| `message` | str | Human-readable error string |
| `code` | int \| None | Numeric error code |
| `captured_at` | str | ISO-8601 timestamp |
| `active_job_id` | str \| None | Job ID at capture, if any |
| `vacuum_state` | str \| None | `vacuum.state` value at capture |

### 4.4 Error-code extraction

Numeric codes are pulled from the entity's `extra_state_attributes` by `_read_error_code_attr()`. Attribute keys are tried in order — `error_code`, `code`, `errorCode` — across the `error_message` entity then the vacuum entity; the first non-zero int wins. A code of `0` is treated as "no code captured" (upstream uses `0` as the no-error sentinel), so it is recorded as `None`.

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

During the grace window the tracker waits for the `error_message` sensor to update with a real message. If the primary channel fires within the window, the grace timer is cancelled and the primary-channel message is used. If the window expires while the device is still in error state, the error is finalized with `error_message = "Unknown error during run"` and `code = None` (no `source` field is recorded).

The grace callback is stored per-vacuum and cancelled on rising primary-channel edge.

---

## 7. Public API

### 7.1 Lifecycle

```python
tracker.start(vacuum_entity_ids: Iterable[str]) -> None
```
Registers state-change listeners for all watched entities across all vacuum IDs. Initializes per-device storage if absent.

```python
tracker.stop() -> None
```
Unsubscribes all listeners and cancels any pending grace timers. The `ErrorTracker` is constructed and `.start()`ed in `__init__.py`'s `async_setup_entry`; `.stop()` is called from `async_unload_entry` (see §10).

### 7.2 Harvest

```python
tracker.harvest_active_run(vacuum_entity_id: str, job_id: str | None) -> dict | None
```
Returns the single `active_run_error` latch dict for the given vacuum and nulls it out (sets it back to `None`). Called by `learning/job_finalizer.py` at job-end so the completed job carries its error history. Returns `None` if no latch was formed. A mismatched `job_id` (the latch belongs to a previous, un-harvested job) is logged at debug and the latch is returned anyway — losing history is worse than attaching it to the wrong job.

### 7.3 Acknowledge

```python
tracker.acknowledge(vacuum_entity_id: str, *, scope: str = "both") -> bool
```
Clears one or both single-value latches for a vacuum. `scope` is **keyword-only**. Returns `True` if a record existed for the vacuum, `False` otherwise. Invoked via the `eufy_vacuum.acknowledge_error` service (see below) — there is no panel/frontend caller.

| `scope` value | Effect |
|---|---|
| `"active_run"` | Clears only `active_run_error` |
| `"last_device"` | Clears only `last_device_error` |
| `"both"` (default) | Clears both `active_run_error` and `last_device_error` (sets each to `None`) |

`recent_errors` is never cleared by `acknowledge` — it is a non-destructive rolling log.

This method is invoked by the registered HA service `eufy_vacuum.acknowledge_error` (`SERVICE_ACKNOWLEDGE_ERROR`; handled by `_handle_acknowledge_error` in `services/errors.py`, which calls `tracker.acknowledge`). The service takes `vacuum_entity_id` (required) and `scope` (optional select — `active_run` / `last_device` / `both`, default `both`), is registered with `supports_response=True`, and returns `{acknowledged, vacuum_entity_id, scope}`. There is no panel/frontend caller.

### 7.4 Update Listeners

```python
unsub = tracker.add_update_listener(cb: Callable[[str], None]) -> Callable[[], None]
```
Registers a callback fired whenever a vacuum's latch state changes (rising edge, falling edge, harvest, ack). The callback is invoked with a single argument — the `vacuum_entity_id` whose state changed — not with no arguments. Returns an unsubscribe callable.

### 7.5 Read Accessors

The tracker exposes four public read accessors. Each calls `_ensure_record()` first, so the per-device record (with default keys) is created if absent. These are what the HA `sensor`/`binary_sensor` entities read to populate `native_value` and `extra_state_attributes`.

```python
tracker.get_record(vacuum_entity_id: str) -> dict
tracker.get_active_run_latch(vacuum_entity_id: str) -> dict | None
tracker.get_last_device_latch(vacuum_entity_id: str) -> dict | None
tracker.recent_errors(vacuum_entity_id: str, *, limit: int | None = None) -> list[dict]
```

| Accessor | Returns |
|---|---|
| `get_record` | The full per-device record dict (`active_run_error` / `last_device_error` / `recent_errors`) |
| `get_active_run_latch` | The `active_run_error` latch dict, or `None` |
| `get_last_device_latch` | The `last_device_error` dict, or `None` |
| `recent_errors` | A copy of the `recent_errors` list, tail-trimmed to the last `limit` entries when `limit` is a non-negative int (`limit` is keyword-only; `None` = all) |

`sensor/error.py` calls `get_active_run_latch` and `get_last_device_latch` directly to drive the error sensors.

### 7.6 Recent-Errors Service Accessor

```python
tracker.recent_errors(vacuum_entity_id: str, *, limit: int | None = None) -> list[dict]
```

Beyond driving the entities, `recent_errors` (see §7.5) backs a second registered HA service, `eufy_vacuum.get_recent_errors` (`SERVICE_GET_RECENT_ERRORS`; handled by `_handle_get_recent_errors` in `services/errors.py`). The service takes `vacuum_entity_id` (required) and `limit` (optional `number` selector, range 1–50, default 20, `mode: box`), is registered with `supports_response=True`, and returns `{vacuum_entity_id, errors, count}` where `errors` is the tail slice of the ring buffer (entry shape per §4.3).

---

## 8. Buffer Limits

- `active_run_error`: a single latch dict, not a list. The `_LATCH_ERRORS_LIMIT` (50) cap applies to the nested `errors[]` list **inside** the latch — oldest per-edge entries are dropped when that list exceeds 50. The latch itself is one dict per run.
- `last_device_error`: a single dict, replaced entirely on each write (single-value semantics, not a rolling list).
- `recent_errors`: a list capped at `_RECENT_ERRORS_LIMIT` (50). Oldest entries dropped when the limit is reached.

---

## 9. Adapter Registry Dependencies

The tracker reads the following from the adapter registry at runtime:

| Registry path | Used for |
|---|---|
| `entities.error_message` | Primary channel entity ID |
| `entities.task_status` | Secondary channel B entity ID |
| `vocabulary.not_error_sentinels` | Brand-specific non-error strings merged into the generic sentinel set |
| `error_tracking.unknown_error_message` | Placeholder text used on grace expiry (default: `"Unknown error during run"`) |

All lookups use `get_adapter_config()` with safe fallbacks — the tracker degrades gracefully if adapter config is incomplete. Note: the grace window duration is the hardcoded module constant `_ERROR_MESSAGE_GRACE_SECONDS = 5`, the secondary-channel error value is a hardcoded `== "error"` comparison, and the error-code attribute keys are a hardcoded tuple (`"error_code"`, `"code"`, `"errorCode"`) — these are **not** read from the adapter registry.

---

## 10. Integration Points

| Caller | Method called | When |
|---|---|---|
| `__init__.py` `async_setup_entry` | `ErrorTracker(...)` + `tracker.start(vacuum_entity_ids)` | Integration load |
| `__init__.py` `async_unload_entry` | `tracker.stop()` | Integration unload |
| `learning/job_finalizer.py` | `tracker.harvest_active_run(vacuum_entity_id, job_id)` | Job finalization |
| `sensor/error.py` entities | `tracker.get_active_run_latch(...)` / `tracker.get_last_device_latch(...)` | Entity state read |
| `eufy_vacuum.acknowledge_error` service (`services/errors.py`) | `tracker.acknowledge(vacuum_entity_id, scope=...)` | User action |
| `eufy_vacuum.get_recent_errors` service (`services/errors.py`) | `tracker.recent_errors(vacuum_entity_id, limit=...)` | User / debugging query |
