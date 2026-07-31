# 23 — Error Tracker

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

**Persistence.** Every mutation (rising/falling edge, harvest, acknowledge) calls
`_persist_and_notify`, which schedules a save via
`hass.loop.call_soon_threadsafe(hass.async_create_task, manager.async_save())` — deliberately
thread-safe because the sync finalize/harvest path runs on a worker thread. The persisted surface
is `manager.data["error_tracker"]` (the 3-key record above); the grace timers (`_grace_cancels`),
the listener list, and `_vacuum_entities` are **runtime-only** and lost on restart (so a mid-error
restart drops the pending grace window).

---

## 4. Record Shapes

The three values in a per-device record have distinct shapes.

### 4.1 `active_run_error` — the run latch

A single latch dict (or `None`). Formed on the first rising edge **while a run is in
flight**, extended on subsequent rising edges, and cleared at commit.

"In flight" here is `run_is_in_flight` (`jobs/active_job.py`), **not**
`dispatched_job_is_in_flight`: the tracker's question is about the robot, not the queue,
so an **app-started (external) run latches too**. Those runs carry no `job_id` — one is
assigned at graduate time — so the latch's `active_job_id` is legitimately `None` for
them, and `_finalize_external_run` peeks the latch onto the pending record instead of the
dispatched finalizer doing it. See [03-data-model](03-data-model.md) §5a / §9b.

| Field | Type | Description |
|---|---|---|
| `active_job_id` | str \| None | Job ID in flight when the latch first formed; `None` for an external run |
| `first_seen_at` | str | ISO-8601 timestamp of the first rising edge |
| `last_seen_at` | str | ISO-8601 timestamp of the most recent rising or falling edge |
| `first_seen_job_elapsed_seconds` | int | Seconds into the run when the first error fired (`_job_elapsed_seconds`: clamped ≥ 0; **0** when there is no run in flight or `started_at` is missing/unparseable; a tz-naive `started_at` is read as UTC rather than raising) |
| `error_count` | int | Number of rising edges accumulated into this latch |
| `current_message` | str | Latest error message (`""` after recovery) |
| `current_code` | int \| None | Latest numeric error code (`None` after recovery) |
| `errored_room_id` | str \| None | `current_room_id` of the active job at first error |
| `recovered` | bool | `True` once the message clears mid-run; flips back to `False` on a fresh rising edge |
| `errors` | list[dict] | Per-edge sub-records (shape below), capped at `_LATCH_ERRORS_LIMIT` (50) |

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

A rising error edge on the primary channel fires on **any** state-change event whose **new**
value is an error string (not in the not-error set) — **regardless of the old value**. There is
no `not was_error` guard, so error→error message changes and attribute-only re-emissions (which
`async_track_state_change_event` also delivers) each re-fire a rising edge. So `error_count` /
`errors[]` count error **observations**, not strictly not_error→error transitions.

**Not-error sentinel set:** the adapter's `vocabulary.not_error_sentinels` (each entry
`.strip().lower()`'d) **replaces** the generic set entirely — there is **no merge**.
`_NOT_ERROR = {"", "unknown", "unavailable"}` is used **only** when no adapter/vocabulary is
registered. So each adapter must re-include the generic HA sentinels itself (Eufy declares
`{"", "unknown", "unavailable", "none", "normal"}`; Roborock `{"", "unknown", "unavailable",
"none"}`) — an adapter that omits them would make an empty/`unknown` state read as a real error.
Incoming values are also `.strip().lower()`'d before the comparison (`_is_error_value`).

### 5.2 Secondary Channel A — `vacuum.state`

The main vacuum entity. An error is detected when `str(state.state or "").strip().lower() == "error"`.

### 5.3 Secondary Channel B — `task_status` sensor

Entity ID read from adapter config `entities.task_status`.

An error is detected when the lowercased state equals the adapter's
`error_tracking.task_status_error_value` (both shipped brands declare `"error"`). **The `.lower()`
is load-bearing:** `task_status` emits the **capitalized** `"Error"` on fault, so a
case-sensitive compare would silently miss this channel. This channel mirrors the vacuum-state
channel — the Eufy firmware flips both simultaneously on hardware fault.

### 5.4 Secondary Error Predicate

```python
def _is_in_secondary_error(self, vacuum_entity_id) -> bool:   # instance method
    vac = self._hass.states.get(vacuum_entity_id)
    if vac is not None and str(vac.state or "").strip().lower() == "error":
        return True
    ts_entity = self._vacuum_entities[vacuum_entity_id].get("task_status")
    ts = self._hass.states.get(ts_entity) if ts_entity else None
    return ts is not None and str(ts.state or "").strip().lower() == "error"
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

```python
tracker.unregister_vacuum(vacuum_entity_id: str) -> None
```
Per-vacuum teardown when a single managed vacuum is removed — unsubs that vacuum's listeners,
cancels its grace timer, and drops it from the lookup maps. **In-memory only**: the *persisted*
`error_tracker` record is dropped separately by `EufyVacuumManager.remove_vacuum_record` (both are
called from `__init__.py` on device removal).

### 7.2 Harvest

```python
tracker.harvest_active_run(vacuum_entity_id: str, job_id: str | None) -> dict | None
```
Returns the single `active_run_error` latch dict for the given vacuum and nulls it out (sets it back to `None`). Returns `None` if no latch was formed. A mismatched `job_id` is logged at debug and the latch is returned anyway — losing history is worse than attaching it to the wrong job. (The debug log fires only when **both** the latch's `active_job_id` and the passed `job_id` are non-`None` and differ.)

**Injection + payload contract.** The finalizer does **not** import the tracker.
`learning/manager.py::_make_error_source(hass)` builds a closure
`error_source(vacuum_entity_id, job_id) -> tracker.harvest_active_run(...)` and injects it into
`LearningJobFinalizer(error_source=…)`; the finalizer calls `self._error_source(...)` (the §9.3
host contract in [10](10-learning-system.md)). The harvested latch is folded into the completed
job's `outcome` under four keys: `had_errors` (bool, `error_count > 0`), `error_count` (int),
`errors` (the **full latch dict verbatim**), `total_error_seconds` (int). `total_error_seconds` is
derived from the latch's `errors[]` — each treated as a half-open `[captured_at, recovered_at)`
interval (an open interval is closed by the next edge's `captured_at`, else the job's `ended_at`;
overlaps merged) — then **subtracted from `cleaning_time_seconds`** (clamped ≥ 0) so a recoverable
run isn't penalised for transient faults. This is why `errors[].captured_at` / `recovered_at` (and
the `recovered_at: None` semantics) are load-bearing.

### 7.3 Acknowledge

```python
tracker.acknowledge(vacuum_entity_id: str, *, scope: str = "both") -> bool
```
Clears one or both single-value latches for a vacuum. `scope` is **keyword-only**. Returns `True` if a record existed for the vacuum, `False` otherwise. Invoked via the `eufy_vacuum.acknowledge_error` service (see below) — there is no panel/frontend caller.

| `scope` value | Effect |
|---|---|
| `"active_run"` | Clears `active_run_error` — or **marks** it, if a run is in flight (below) |
| `"last_device"` | Clears only `last_device_error` |
| `"both"` (default) | Both of the above |

**Acknowledging mid-run MARKS rather than deletes.** When `run_is_in_flight` is true, the
`active_run` scope sets `acknowledged: True`, blanks `current_message` and sets
`recovered: True` instead of nulling the latch. The natural order of operations makes this
the common case, not an edge one: the robot gets stuck, the user goes and frees it, then
clears the alert — which is *why* they went. Deleting the latch there destroyed the
evidence the finalizer needs, and the run then finalized with `had_errors: False`.

The second-order effect was worse than the missing history: `had_errors` is an explicit
exemption in the idle-wall guard, and being stuck is exactly what produces a large
wall-vs-cleaning gap — so losing the flag stripped the exemption, held the run from
learning with blocker `extreme_idle_wall`, and reported "unexplained idle" for a run whose
explanation the user had just personally handled.

Acknowledging is a UI intent ("I've dealt with it"), not a claim that the error never
occurred. The entities already render a recovered/blank latch as nothing to show, so
marking satisfies the intent while the finalizer still gets its evidence; the
post-finalize auto-clear then collects it. With no run in flight there is nothing to
preserve and the latch clears outright, exactly as before.

This applies to **external runs too** — both this check and `_lookup_active_job` ask
`run_is_in_flight`, so they cannot drift apart.

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
| `get_active_run_latch` | A **deep copy** of the `active_run_error` latch, or `None` |
| `get_last_device_latch` | A **deep copy** of the `last_device_error` dict, or `None` |
| `recent_errors` | A copy of the `recent_errors` list, tail-trimmed to the last `limit` entries when `limit` is a non-negative int (`limit` keyword-only; `None` = all). **Edge:** `limit=0` returns **all** entries (`items[-0:]` is `items[:]`) — reachable only via this direct accessor; the `get_recent_errors` service enforces `limit ≥ 1`. |

`sensor/error.py` calls `get_active_run_latch` and `get_last_device_latch` directly to drive
the error sensors.

**The two latch accessors deep-copy, and that is load-bearing.** Every caller is a
presentation surface that hands what it gets to something which KEEPS it — the sensors'
`extra_state_attributes`, the binary_sensor, the lifecycle snapshot served to the card.
Home Assistant wraps a State's attributes in a `ReadOnlyDict` but does **not** copy the
nested values, so returning the live latch made the `errors` entries inside an
already-written State the same dicts the tracker went on to mutate: `_record_falling_edge`
stamps `recovered_at` in place, reaching back into a State written minutes earlier and
making history report the fault as already recovered at a time when it was not. A shallow
`dict(latch)` at the call site does not help — the nesting is where the sharing lives.

`peek_active_run` deep-copies for the same reason and says so; these accessors are the
other half of that guarantee, so nothing hands out the live object. `get_record` is
deliberately **not** copied — it is the internal mutation seam the tracker itself writes
through, not a presentation accessor.

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
| `vocabulary.not_error_sentinels` | Brand-specific non-error strings that **replace** the generic set (no merge) — each adapter must re-include `""` / `"unknown"` / `"unavailable"` itself |
| `error_tracking.unknown_error_message` | Placeholder text used on grace expiry (default: `"Unknown error during run"`) |
| `error_tracking.task_status_error_value` | Value of the **`task_status`** channel that counts as an error (default: `"error"`) |
| `error_tracking.grace_window_seconds` | Late-arrival grace duration (default: the module constant `_ERROR_MESSAGE_GRACE_SECONDS = 5`) |
| `error_tracking.error_code_attribute_names` | Ordered attribute names searched for the numeric code (default: `("error_code", "code", "errorCode")`) |

Every `error_tracking` read goes through the module-level `_error_tracking_cfg()` helper, which
returns `{}` for an unregistered adapter or a missing block; each caller then applies its own
documented default. The helper never raises, so the tracker degrades gracefully when adapter
config is incomplete.

Two comparisons are deliberately **not** adapter-configurable:

- **`vacuum.<obj>` state `== "error"`** — that is Home Assistant's own `VacuumActivity` value, not
  brand vocabulary. A brand does not get to rename it. (The `task_status` channel beside it *is*
  brand vocabulary and *is* configurable — see the table above.)
- **`grace_window_seconds` of `0`** is honoured (fire on the next event-loop tick) rather than
  treated as "unset", so the read tests for `None` instead of falsiness.

---

## 10. Integration Points

| Caller | Method called | When |
|---|---|---|
| `__init__.py` `async_setup_entry` | `ErrorTracker(...)` + `tracker.start(vacuum_entity_ids)` | Integration load |
| `__init__.py` `async_unload_entry` | `tracker.stop()` | Integration unload |
| `learning/job_finalizer.py` (via injected `error_source`, wired in `learning/manager.py`) | `tracker.harvest_active_run(vacuum_entity_id, job_id)` | Job finalization — folds the latch into `outcome.errors` / `had_errors` / `error_count` / `total_error_seconds` (§7.2) |
| `sensor/error.py` entities | `tracker.get_active_run_latch(...)` / `tracker.get_last_device_latch(...)` | Entity state read |
| `binary_sensor.py` (`ActiveRunHasErrorBinarySensor`) | `tracker.get_active_run_latch(...)` | Entity state read (`is_on` = `error_count > 0`, sticky through `recovered`) |
| `__init__.py` (device removal) | `tracker.unregister_vacuum(...)` + `manager.remove_vacuum_record(...)` | A managed vacuum's device is deleted |
| `eufy_vacuum.acknowledge_error` service (`services/errors.py`) | `tracker.acknowledge(vacuum_entity_id, scope=...)` | User action |
| `eufy_vacuum.get_recent_errors` service (`services/errors.py`) | `tracker.recent_errors(vacuum_entity_id, limit=...)` | User / debugging query |
