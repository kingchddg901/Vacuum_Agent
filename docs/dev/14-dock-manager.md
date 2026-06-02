# Dock Manager — Developer Reference

> **Scope:** Complete implementation reference for `dock/manager.py`. Every constant, gating rule, entity discovery strategy, event recording path, and public method is derived directly from the source. A developer should be able to re-implement the dock manager from this document alone.

---

## 1. Overview

The dock manager controls **manual dock-station actions** (wash mop, dry mop, stop dry mop, empty dust bin) and **records dock cycle events** (automatic washes, empties, and dry runs). It acts as the integration's gatekeeper between the panel and dock entity services, enforcing safety rules before any action is dispatched.

**Module:** `custom_components/eufy_vacuum/dock/manager.py`

---

## 2. Debounce configuration

Per-event-type debounce is no longer a module constant — it's read from the
adapter's `dock_events.debounce_seconds` map (keyed by event type, e.g.
`{"last_mop_wash": 60}`). An absent key (or `0`) means no debounce. The Eufy
adapter sets `last_mop_wash: 60`; see `adapters/eufy/adapter.py`.

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
    "last_dry_duration": str | None, # duration string from last dry start
    # plus internal "{event_type}_last_counted_at" debounce bookkeeping keys
}
```

All fields default to `0` (counters) or `None` (timestamps) when absent.

---

## 4. Supported Dock Actions

Four actions are gated and dispatchable:

| Action key | Dock entity button | Event counter key |
|---|---|---|
| `wash_mop` | `button.{object_id}_wash_mop` or `button.{object_id}_mop_wash` | `mop_wash_count` |
| `dry_mop` | `button.{object_id}_dry_mop` or `button.{object_id}_mop_dry` | n/a (no counter) |
| `stop_dry_mop` | `button.{object_id}_stop_dry_mop` or `button.{object_id}_stop_mop_dry` | n/a (no counter) |
| `empty_dust` | `button.{object_id}_empty_dust` or `button.{object_id}_empty_dust_bin` | `dust_empty_count` |

Both `dry_mop` and `stop_dry_mop` are gated against the adapter capability flag `supports_mop_dry`.

---

## 5. Entity Discovery

Resolution is adapter-driven, read from `dock_events.action_buttons[action]`
(the Eufy adapter builds this from `adapters/eufy/buttons.py`). An action
absent from that map resolves to `None` (the action is reported unavailable).
The manager tries two strategies in order:

### 5.1 Named candidates — `entity_suffixes`

Each suffix is appended to `button.{object_id}_` (the vacuum entity ID's
object portion, e.g. `"alfred"`) and tried in order:

```
button.{object_id}_{entity_suffixes[0]}
button.{object_id}_{entity_suffixes[1]}
```

First candidate present in the HA state machine or entity registry wins.

### 5.2 Token fallback — `_find_button_entity_by_tokens`

If no named candidate is found, the `token_sets` for the action are tried:
the manager scans all `button.*` entities in the registry and matches each
token set (a candidate entity ID is split on `_` and must contain all tokens
in the set). This handles brands with dynamic entity naming. Eufy declares
both `entity_suffixes` and `token_sets` for every dock action.

---

## 6. Action Gating

`get_dock_action_status()` evaluates all dock actions and returns per-action availability. The default `reason` is `"ready"` (allowed). The gating check runs in this order (first failing check wins):

1. **`unsupported_feature`** — adapter capability flag `supports_{...}` is False.
2. **`missing_action_entity`** — no button entity found via discovery.
3. **`job_active`** — the tracked job is `started` or `paused`.
4. **`not_docked`** — vacuum state is not `docked`.
5. **action-specific state check** —
   - `wash_mop` → **`already_washing`** if `dock_status` is in the wash trigger set.
   - `dry_mop` → **`already_drying`** if `dock_status` is in the dry trigger set.
   - `stop_dry_mop` → **`not_drying`** if `dock_status` is **not** in the dry trigger set (stop is only useful while drying).
   - `empty_dust` → **`already_emptying`** if `dock_status` is in the empty trigger set.
6. **`dock_busy`** — for every action **except** `stop_dry_mop`, dock is in a `hard_service_states` state that blocks manual actions.

If all checks pass, `reason` stays `"ready"` and the action is `allowed = True`.

### 6.1 `get_dock_action_status` return shape

```python
manager.get_dock_action_status(*, vacuum_entity_id: str, map_id: str) -> dict
```

Keyword-only; **both** `vacuum_entity_id` and `map_id` are required (the gating consults
the lifecycle and active-job state for that map). Per-action results are nested under an
`"actions"` key:

```python
{
    "vacuum_entity_id":  str,
    "map_id":            str,
    "docked":            bool,
    "dock_status":       str | None,
    "lifecycle_state":   str | None,
    "active_job_status": str | None,
    "actions": {
        "wash_mop": {
            "supported":    bool,
            "entity_id":    str | None,
            "allowed":      bool,
            "reason":       str,        # e.g. "ready", "not_docked", "job_active"
            "reason_label": str | None,
            "message":      str,        # human-readable explanation
        },
        "dry_mop":      { ... },
        "stop_dry_mop": { ... },
        "empty_dust":   { ... },
    },
    "can_wash_mop":     bool,   # convenience mirror of actions[...]["allowed"]
    "can_dry_mop":      bool,
    "can_stop_dry_mop": bool,
    "can_empty_dust":   bool,
    "updated_at":       str,
}
```

### 6.2 Vocabulary / trigger sets used

The wash / dry / empty "already in progress" checks read **dock-event trigger** state
strings from `adapter_config["dock_events"]["triggers"]`, falling back to built-in
defaults when a trigger key is absent:

| Trigger key | Used to check | Built-in fallback |
|---|---|---|
| `last_mop_wash`  | `wash_mop` already washing | `{"washing", "washing mop"}` |
| `last_dry_start` | `dry_mop` already drying / `stop_dry_mop` not drying | `{"drying", "drying mop", "drying pads", "mop drying"}` |
| `last_dust_empty`| `empty_dust` already emptying | `{"emptying dust", "emptying dust bin", "dust emptying"}` |

Only the `dock_busy` check reads from `adapter_config["vocabulary"]`:

| `vocabulary` key | Used to check |
|---|---|
| `hard_service_states` | Dock states that block all manual actions except `stop_dry_mop` |

---

## 7. Action Dispatch

There is no single `dispatch_dock_action` entry point. Dispatch is exposed as four
keyword-only `async` methods, one per action, each delegating to the private
`_async_run_dock_action`:

```python
await manager.async_wash_mop(*, vacuum_entity_id: str, map_id: str) -> dict
await manager.async_dry_mop(*, vacuum_entity_id: str, map_id: str) -> dict
await manager.async_empty_dust(*, vacuum_entity_id: str, map_id: str) -> dict
await manager.async_stop_dry_mop(*, vacuum_entity_id: str, map_id: str) -> dict
```

None of them take a `hass` argument — the manager already holds its own `hass`
reference. The private runner:

```python
await manager._async_run_dock_action(*, vacuum_entity_id: str, map_id: str, action: str) -> dict
```

1. Calls `get_dock_action_status(vacuum_entity_id=..., map_id=...)` and reads
   `status["actions"][action]`.
2. If `allowed` is False, returns a result with `performed: False`, `allowed: False`,
   and the blocking `reason` / `message`.
3. If allowed, calls `hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)`.
4. Returns a result with `performed: True`, `reason: "performed"`, and the `entity_id`
   that was pressed.

---

## 8. Dock Event Recording

### 8.1 `record_dock_event`

```python
manager.record_dock_event(
    *,
    vacuum_entity_id: str,
    event_type: str,     # "last_mop_wash" | "last_dust_empty" | "last_dry_start"
    dry_duration: str | None = None,
) -> None
```

Called by `listeners/dock_events.py` when the dock status transitions through a trigger state. Behavior:

1. Always writes the current ISO timestamp to the `{event_type}` field.
2. **Debounce check** (counter only) — the cooldown for `event_type` is read from the adapter's `dock_events.debounce_seconds` map; the matching counter increment is skipped when less than that many seconds have elapsed since the last *counted* event of this type (absent key or `0` = no debounce). The timestamp from step 1 is still written regardless.
3. Increments the matching counter (`mop_wash_count`, `dust_empty_count`, or `dry_start_count`) when not debounced.
4. For `last_dry_start` with a non-`None` `dry_duration`, also stores it (as a string) at `last_dry_duration`.

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
    *,
    vacuum_entity_id: str,
    event_type: str,
    count: int,
) -> dict
```

Keyword-only. Overwrites a counter to a specific value (clamped to `>= 0`) and returns a
result dict (`updated: True` with `old_count`/`new_count`, or `updated: False` with an
`error` for an unknown `event_type`). Used by the panel's maintenance tab to let users correct miscounted events (e.g. if the dock cycled before the integration was loaded).

---

## 9. Integration Points

| Caller | Method | When |
|---|---|---|
| `listeners/dock_events.py` | `record_dock_event()` | On dock_status state change matching trigger vocabulary |
| Panel dock-action service | `async_wash_mop()` / `async_dry_mop()` / `async_stop_dry_mop()` / `async_empty_dust()` | User presses dock action button |
| Panel dock status API | `get_dock_action_status()` | On panel render |
| Panel maintenance tab | `set_dock_event_count()` | User corrects counter |
| `maintenance/manager.py` | reads `data["dock_events"]` directly | `get_upkeep_snapshot()` |

> **See also:** [13-maintenance-manager](13-maintenance-manager.md) §7 for how dock event counts are consumed to compute maintenance remaining hours; [22-adapter-config-reference](22-adapter-config-reference.md) §vocabulary for the `dock_status` state strings that trigger event detection.
