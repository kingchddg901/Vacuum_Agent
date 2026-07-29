# 14 — Dock Manager

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

Full capability→action gate map (§6 step 1): `wash_mop → supports_mop_wash`, `dry_mop` **and** `stop_dry_mop → supports_mop_dry`, `empty_dust → supports_empty_dust`.

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

If no named candidate is found, the `token_sets` for the action are tried
(`_find_button_entity_by_tokens`, `core/manager.py:902-917`): the manager scans
**registry entities whose id starts with `button.{object_id}_`** (this vacuum only,
lowercased) — **not** all `button.*` — and an entity matches a token set when
**every token is a case-insensitive substring of the full entity_id string**
(`all(tok in entity_id …)`), **not** a split-on-`_` word membership. This path reads
the **registry only** — the state machine is not consulted (unlike §5.1). This handles
brands with dynamic entity naming. Eufy declares both `entity_suffixes` and `token_sets`
for every dock action.

> **Substring match caveat (code-flag CS-1).** Because it is a raw substring test over the whole id (which includes the object_id), a token like `"dry"` could match inside an unrelated word or the object_id itself (object_id `dryer` → `button.dryer_…` contains `"dry"`). Split-on-`_` membership — which this doc *used to* describe — would be safer. Low blast radius (named candidates almost always resolve first), but it is a doc-vs-code disagreement worth a decision: switch the code to word membership, or keep the substring behavior documented here.

---

### 5.3 `get_dock_action_entities` — capability-gate-independent resolution

```python
manager.get_dock_action_entities(*, vacuum_entity_id: str) -> dict
# → {"wash_mop": str|None, "dry_mop": str|None, "stop_dry_mop": str|None, "empty_dust": str|None}
```

Resolves each action's button entity (via the §5.1/§5.2 discovery) **independent of the capability gate** — so diagnostics can report the physically-present controls even on a `generic`-detected model whose `supports_*` flags are off. Consumed by `diagnostics.py`; exposed via the `core/manager.py` delegator.

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
    "vacuum_entity_id":       str,
    "map_id":                 str,
    "docked":                 bool,
    "dock_status":            str | None,   # RAW lifecycle.get("dock_status") — NOT normalized
    "dock_status_label":      str | None,   # _display_label(dock_status): "_"→" ", title-cased, None-safe
    "lifecycle_state":        str | None,
    "lifecycle_state_label":  str | None,   # _display_label(lifecycle_state)
    "lifecycle_message":      str | None,   # lifecycle.get("message") passthrough
    "active_job_status":      str | None,
    "active_job_status_label": str | None,  # _display_label(active_job_status)
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
strings from `adapter_config["dock_events"]["triggers"]`. There is **no brand fallback**:
an adapter that omits a trigger key gets an empty set for that check (no detection) rather
than inheriting Eufy's vocabulary. The sets the Eufy adapter declares (in
`adapters/eufy/vocabulary.py`):

| Trigger key | Used to check | Eufy-declared set |
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

Exact return shapes (`map_id` is `str(map_id)`; `dock_status`/`lifecycle_state` copied from the status call):

```python
# blocked (allowed False) — 9 keys:
{"vacuum_entity_id", "map_id", "action", "performed": False, "allowed": False,
 "reason", "message", "dock_status", "lifecycle_state"}

# success — 10 keys:
{"vacuum_entity_id", "map_id", "action", "performed": True, "allowed": True,
 "reason": "performed", "message": "Dock action sent.", "entity_id",
 "dock_status", "lifecycle_state"}
```

---

### 7.1 Service layer (host contract)

The manager methods require `map_id` (keyword-only, no default), but the **service** wrappers make it optional and auto-resolve it:

- `get_dock_action_status` (schema `VACUUM_MAP_SCHEMA`) and the four dispatch services (schema `JOB_CONTROL_SCHEMA`, which **is** `VACUUM_MAP_SCHEMA`) take `map_id` as `vol.Optional`; the handlers call with `**resolved_call_data(hass, call)`, which fills a missing/blank `map_id` from the active-map entity (falling through to the method's own error if unresolvable).
- `set_dock_event_count` is the exception — its schema has **no** `map_id`.
- A blocked dispatch is wrapped into a raised **`ServiceValidationError`** (not just a `performed:False` dict) at the service layer.
- All six dock services are `supports_response=True`.

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
    "last_dust_empty":  ["dust emptying", "emptying dust", "emptying dust bin"],
    "last_dry_start":   ["drying", "drying mop", "drying pads", "mop drying"],
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

Keyword-only. Overwrites a counter to a specific value (clamped `max(int(count), 0)`; `old_count` read via `_safe_int(..., 0)`) and returns a result dict: success `{updated: True, event_type, old_count, new_count}`, or `{updated: False, error}` for an unknown `event_type`. Used by the panel's maintenance tab to let users correct miscounted events (e.g. if the dock cycled before the integration was loaded).

---

## 9. Integration Points

| Caller | Method | When |
|---|---|---|
| `listeners/dock_events.py` | `record_dock_event()` | On dock_status state change matching trigger vocabulary |
| Panel dock-action service | `async_wash_mop()` / `async_dry_mop()` / `async_stop_dry_mop()` / `async_empty_dust()` | User presses dock action button |
| Panel dock status API | `get_dock_action_status()` | On panel render |
| Panel maintenance tab | `set_dock_event_count()` | User corrects counter |
| `maintenance/manager.py` | `get_dock_events()` (public accessor) | `get_upkeep_snapshot()` |
| `sensor/dock_event.py` (`EufyVacuumDockEventSensor`) | `get_dock_events()` | State = `max()` of the three `last_*` timestamps + `last_*`/`last_dry_duration` attributes |
| `learning/manager.py` | `get_dock_events()` | Metrics summary |
| `diagnostics.py` | `get_dock_action_entities()` | Diagnostics report (capability-gate-independent, §5.3) |

> **See also:** [13-maintenance-manager](13-maintenance-manager.md) §7 for how dock event counts are consumed to compute maintenance remaining hours; [22-adapter-config-reference](22-adapter-config-reference.md) §vocabulary for the `dock_status` state strings that trigger event detection.
