# Dock Manager — Developer Reference

> **Scope:** Complete implementation reference for `dock/manager.py`. Every constant, gating rule, entity discovery strategy, event recording path, and public method is derived directly from the source. A developer should be able to re-implement the dock manager from this document alone.

---

## 1. Overview

The dock manager controls **manual dock-station actions** (wash mop, dry mop, empty dust bin) and **records dock cycle events** (automatic washes, empties, and dry runs). It acts as the integration's gatekeeper between the panel and dock entity services, enforcing safety rules before any action is dispatched.

**Module:** `custom_components/eufy_vacuum/dock/manager.py`

---

## 2. Constants

| Constant | Value | Description |
|---|---|---|
| `_DOCK_EVENT_DEBOUNCE_SECONDS` | `{"last_mop_wash": 60}` | Per-event-type minimum seconds between recorded events. Only `last_mop_wash` is currently debounced. |

---

## 3. Storage Layout

Dock event state lives at `data["dock_events"][vacuum_entity_id]`:

```python
data["dock_events"]["vacuum.alfred"] = {
    "mop_wash_count":   int,       # total mop washes recorded
    "dust_empty_count": int,       # total dust empties recorded
    "dry_start_count":  int,       # total dry cycles recorded
    "last_mop_wash":    str | None,  # ISO timestamp of last mop wash
    "last_dust_empty":  str | None,  # ISO timestamp of last dust empty
    "last_dry_start":   str | None,  # ISO timestamp of last dry start
}
```

All fields default to `0` (counters) or `None` (timestamps) when absent.

---

## 4. Supported Dock Actions

Three actions are gated and dispatchable:

| Action key | Dock entity button | Event counter key |
|---|---|---|
| `wash_mop` | `button.{object_id}_wash_mop` or `button.{object_id}_mop_wash` | `mop_wash_count` |
| `dry_mop` | `button.{object_id}_dry_mop` or `button.{object_id}_mop_dry` | n/a (no counter) |
| `empty_dust` | `button.{object_id}_empty_dust` or `button.{object_id}_empty_dust_bin` | `dust_empty_count` |

---

## 5. Entity Discovery

The manager tries two strategies in order to find the button entity for each action:

### 5.1 Named candidates

Tries a fixed list of candidate entity IDs derived from `object_id` (the vacuum entity ID's object portion, e.g. `"alfred"`):

```
button.{object_id}_{primary_suffix}
button.{object_id}_{alternate_suffix}
```

First candidate found in the HA entity registry wins.

### 5.2 Token fallback — `_find_button_entity_by_tokens`

If no named candidate is found, scans all `button.*` entities in the registry and matches against required token sets from the adapter's `capabilities` block. A candidate entity ID is split on `_` and the resulting token set must be a superset of the required tokens.

The token sets for each action come from the adapter config `vocabulary` block (not shown in the Eufy adapter because Eufy uses named candidates exclusively). This fallback exists for brands that use dynamic entity naming conventions.

---

## 6. Action Gating

`get_dock_action_status()` evaluates all dock actions and returns per-action availability. The gating check runs in this order (first failing check wins):

1. **unsupported** — adapter capability flag `supports_{action}` is False.
2. **missing entity** — no button entity found via discovery.
3. **job_active** — a cleaning job is currently in progress (`active_job` has lifecycle observed).
4. **not_docked** — vacuum is not in the docked state (reads from `dock_status` via adapter entities).
5. **action-specific state check** — for `dry_mop`: dock must not already be drying (state in `drying_states`). For `wash_mop`: dock must not already be washing (state in active wash vocabulary).
6. **dock_busy** — dock is in a `hard_service_states` state that blocks all manual actions.

If all checks pass, the action is `allowed = True`.

### 6.1 `get_dock_action_status` return shape

```python
manager.get_dock_action_status(vacuum_entity_id: str) -> dict
```

```python
{
    "wash_mop": {
        "supported":  bool,
        "entity_id":  str | None,
        "allowed":    bool,
        "reason":     str,     # e.g. "not_docked", "job_active", "allowed"
        "message":    str,     # human-readable explanation
    },
    "dry_mop":    { ... },
    "empty_dust": { ... },
}
```

### 6.2 Vocabulary sets used

Read from `adapter_config["vocabulary"]`:

| Key | Used to check |
|---|---|
| `hard_service_states` | Dock states that block all manual actions |
| `drying_states` | Dock states that block `dry_mop` (already drying) |

---

## 7. Action Dispatch

```python
await manager.dispatch_dock_action(
    hass: HomeAssistant,
    vacuum_entity_id: str,
    action: str,  # "wash_mop" | "dry_mop" | "empty_dust"
) -> dict
```

1. Calls `get_dock_action_status()` and checks `allowed`.
2. If not allowed, returns an error result with the blocking reason.
3. If allowed, calls `hass.services.async_call("button", "press", {"entity_id": button_entity_id})`.
4. Returns a success result with `entity_id` dispatched to.

---

## 8. Dock Event Recording

### 8.1 `record_dock_event`

```python
manager.record_dock_event(
    vacuum_entity_id: str,
    event_type: str,     # "last_mop_wash" | "last_dust_empty" | "last_dry_start"
    dry_duration: float | None = None,
) -> None
```

Called by `listeners/dock_events.py` when the dock status transitions through a trigger state. Behavior:

1. **Debounce check** — if `event_type` is in `_DOCK_EVENT_DEBOUNCE_SECONDS`, checks that at least `debounce_seconds` have elapsed since the last recorded event of this type. If the window has not elapsed, the call is a no-op.
2. Writes ISO timestamp to the `last_{event_type}` field.
3. Increments the matching counter (`mop_wash_count`, `dust_empty_count`, or `dry_start_count`).

### 8.2 Trigger detection

`listeners/dock_events.py` reads the trigger vocabulary for each event type from:

```python
adapter_config["dock_events"]["triggers"] = {
    "last_mop_wash":    ["washing", "washing mop"],
    "last_dust_empty":  ["recycling waste water"],
    "last_dry_start":   ["drying"],
}
```

When dock_status state matches a trigger string, the listener calls `record_dock_event` with the corresponding event type.

For `last_dry_start`, the listener also reads the dry duration from the entity at `adapter_config["entities"]["dry_duration"]` and passes it to `record_dock_event`.

### 8.3 `set_dock_event_count`

```python
manager.set_dock_event_count(
    vacuum_entity_id: str,
    event_type: str,
    count: int,
) -> None
```

Overwrites a counter to a specific value. Used by the panel's maintenance tab to let users correct miscounted events (e.g. if the dock cycled before the integration was loaded).

---

## 9. Integration Points

| Caller | Method | When |
|---|---|---|
| `listeners/dock_events.py` | `record_dock_event()` | On dock_status state change matching trigger vocabulary |
| Panel dock-action service | `dispatch_dock_action()` | User presses dock action button |
| Panel dock status API | `get_dock_action_status()` | On panel render |
| Panel maintenance tab | `set_dock_event_count()` | User corrects counter |
| `maintenance/manager.py` | reads `data["dock_events"]` directly | `get_upkeep_snapshot()` |
