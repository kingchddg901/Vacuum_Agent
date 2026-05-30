# Maintenance Manager — Developer Reference

> **Scope:** Complete implementation reference for `maintenance/manager.py`. Every method, formula, constant, adapter dependency, and storage path is derived directly from the source. A developer should be able to re-implement the maintenance manager from this document alone.

---

## 1. Overview

The maintenance manager tracks two parallel data sources that together describe the replacement and cleaning health of a vacuum's consumable components:

1. **Upstream replacement sensors** — percentage-remaining sensors exposed by the upstream integration (e.g. robovac_mqtt). The adapter declares these via the `maintenance_components` block in its config. These reflect the firmware's own tracking.

2. **Integration maintenance intervals** — usage-hour counters maintained by the integration itself, tracking elapsed hours since the last user-confirmed reset. These parallel the upstream sensors and provide an independent check that survives firmware resets.

Both sources feed into the **upkeep snapshot** — a composite view consumed by the panel's maintenance tab and by the learning system when it computes job health context.

**Module:** `custom_components/eufy_vacuum/maintenance/manager.py`

---

## 2. Module-Level Pure Helpers

These are exported at module level and usable without a manager instance.

### 2.1 `maintenance_status`

```python
maintenance_status(*, remaining_hours: float, interval_hours: float) -> str
```

Converts usage-hours tracking to a status bucket.

```
ratio = remaining_hours / interval_hours   (safe: returns "good" if interval_hours == 0)

if ratio <= 0:    → "replace_now"
if ratio <= 0.15: → "replace_soon"
if ratio <= 0.30: → "warning"
else:             → "good"
```

### 2.2 `replacement_status`

```python
replacement_status(*, state_value: str | float | None) -> str
```

Converts an upstream percentage-remaining sensor state to a status bucket.

```
pct = float(state_value)   (returns "good" if parse fails or value is None)

if pct <= 5:  → "replace_now"
if pct <= 15: → "replace_soon"
if pct <= 30: → "warning"
else:         → "good"
```

---

## 3. Storage Layout

Integration-managed maintenance intervals are stored at:

```
data["maintenance"][vacuum_entity_id][component_id] = {
    "reset_at_usage_hours": float,   # vacuum usage hours at last reset
    "reset_at":             str,     # ISO timestamp of last reset
    "interval_hours":       float,   # optional user override of adapter default
}
```

`data["maintenance"]` is created lazily. Missing keys default to "never reset" (treated as zero hours since reset in computations).

---

## 4. Adapter Config Dependencies

### 4.1 `maintenance_components` block

Each entry in `adapter_config["maintenance_components"]` defines one trackable component:

| Field | Type | Description |
|---|---|---|
| `sensor_suffix` | str \| None | Suffix used to derive the upstream sensor entity ID (e.g. `"brush_life"`) |
| `proxy_for` | str \| None | If set, this component is an alias for another — shares sensor state |
| `default_interval_hours` | float | Factory-default cleaning/replacement interval |
| `max_interval_hours` | float | Maximum allowed interval override |
| `label` | str | Display name shown in panel |
| `icon` | str | MDI icon name |

### 4.2 `upkeep_catalog` block

```python
adapter_config["upkeep_catalog"] = {
    "model_names":          dict,   # model_code → display_name
    "model_guide_families": dict,   # model_code → guide_family_key
    "guide_family_names":   dict,   # guide_family_key → display_name
    "guide_library":        dict,   # guide_family_key → {component_id → upkeep_guide_dict}
}
```

The upkeep guide library maps per-model-family maintenance schedules (cleaning procedures, photos, replacement tips). It is read by `get_upkeep_snapshot()` but not mutated by the manager.

---

## 5. Manager Methods

### 5.1 `get_upkeep_snapshot`

```python
manager.get_upkeep_snapshot(vacuum_entity_id: str) -> dict
```

Returns a composite snapshot used by the panel's maintenance tab:

```python
{
    "replacement_items": [
        {
            "component_id": str,
            "label":        str,
            "icon":         str,
            "status":       str,        # "replace_now" | "replace_soon" | "warning" | "good"
            "pct_remaining": float | None,
            "sensor_entity_id": str | None,
        },
        ...
    ],
    "maintenance_items": [
        {
            "component_id":      str,
            "label":             str,
            "icon":              str,
            "status":            str,
            "remaining_hours":   float,
            "interval_hours":    float,
            "reset_at":          str | None,
            "reset_at_usage_hours": float | None,
        },
        ...
    ],
    "attention_count":          int,    # count of items not in "good" status
    "highest_priority_status":  str,    # worst status across all items
    "dock_events": {
        "mop_wash_count":   int,
        "dust_empty_count": int,
        "dry_start_count":  int,
        "last_mop_wash":    str | None,  # ISO timestamp
        "last_dust_empty":  str | None,
        "last_dry_start":   str | None,
    },
    "station_water": {
        "pct":    float | None,
        "status": str,
    },
}
```

**Status priority order** (for `highest_priority_status`): `"replace_now"` > `"replace_soon"` > `"warning"` > `"good"`.

### 5.2 `get_maintenance_remaining`

```python
manager.get_maintenance_remaining(
    vacuum_entity_id: str,
    component_id: str,
) -> float
```

Computes remaining integration-tracked hours:

```
interval_hours = data["maintenance"][vacuum][component].get("interval_hours")
                 or adapter default_interval_hours

reset_usage    = data["maintenance"][vacuum][component].get("reset_at_usage_hours", 0.0)
current_usage  = current vacuum usage_hours (from vacuum state attributes)

used_since_reset = max(current_usage - reset_usage, 0.0)
remaining        = max(interval_hours - used_since_reset, 0.0)
```

Returns `0.0` if no reset record exists (treated as fully elapsed).

### 5.3 `reset_maintenance`

```python
manager.reset_maintenance(
    vacuum_entity_id: str,
    component_id: str,
) -> None
```

Records a reset event:

```python
data["maintenance"][vacuum][component_id] = {
    "reset_at_usage_hours": current_usage_hours,  # from vacuum.attributes
    "reset_at": iso_now(),
}
```

Does **not** overwrite an existing `interval_hours` override — that field is preserved.

### 5.4 `set_interval_override`

```python
manager.set_interval_override(
    vacuum_entity_id: str,
    component_id: str,
    interval_hours: float,
) -> None
```

Stores a user-specified interval. Clamped to `[1.0, max_interval_hours]` where `max_interval_hours` is read from the adapter component definition. Writes to `data["maintenance"][vacuum][component_id]["interval_hours"]`. Persists alongside any existing reset record.

### 5.5 `get_component_catalog`

```python
manager.get_component_catalog(vacuum_entity_id: str) -> dict
```

Returns the adapter's full component definition dict for all maintenance components registered for the vacuum. Read-only — does not modify storage.

---

## 6. Interval Override Precedence

When computing remaining hours, the effective interval is chosen as:

```
stored_override = data["maintenance"][vacuum][component].get("interval_hours")
if stored_override is not None:
    interval_hours = stored_override
else:
    interval_hours = adapter["maintenance_components"][component]["default_interval_hours"]
```

The stored override takes **complete precedence** over the adapter default. The adapter's `max_interval_hours` is only enforced at write time (`set_interval_override`), not at read time.

---

## 7. Dock Events Integration

`get_upkeep_snapshot()` includes dock event counts and timestamps sourced from `DockManager.get_dock_events()`. The maintenance manager reads but never writes dock event state — DockManager owns that data (see `docs/dev/dock-manager.md`).

---

## 8. Integration Points

| Caller | Method | When |
|---|---|---|
| Panel maintenance tab | `get_upkeep_snapshot(vacuum_entity_id)` | On load / refresh |
| Panel reset action | `reset_maintenance(vacuum_entity_id, component_id)` | User presses reset |
| Panel interval override | `set_interval_override(vacuum_entity_id, component_id, hours)` | User saves interval |
| Learning job finalizer | `get_component_catalog(vacuum_entity_id)` | Job health context |
