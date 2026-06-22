# 13 — Maintenance Manager

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
if interval_hours <= 0:        → "unknown"   (cannot compute a ratio)

ratio = remaining_hours / interval_hours

if remaining_hours <= 0: → "replace_now"
if ratio <= 0.1:         → "replace_soon"
if ratio <= 0.25:        → "warning"
else:                    → "good"
```

### 2.2 `replacement_status`

```python
replacement_status(*, state_value: str | float | None) -> str
```

Converts an upstream percentage-remaining sensor state to a status bucket.

```
pct = float(state_value)   (returns "unknown" if parse fails or value is None)

if pct <= 5:  → "replace_now"
if pct <= 15: → "replace_soon"
if pct <= 30: → "warning"
else:         → "good"
```

---

## 3. Storage Layout

Integration-managed maintenance intervals are stored at:

```
data["maintenance"][vacuum_entity_id][component] = {
    "reset_at_usage_hours": float,   # vacuum usage hours at last reset
    "reset_at":             str,     # ISO timestamp of last reset
    "interval_hours":       float,   # optional user override of adapter default (see note)
}
```

`data["maintenance"]` is created lazily. Missing keys default to "never reset" (treated as zero hours since reset in computations).

`reset_maintenance()` writes **only** `reset_at_usage_hours` and `reset_at` — it does not write `interval_hours`. The optional `interval_hours` override key is written elsewhere (by `set_maintenance_interval` and the `EufyVacuumMaintenanceIntervalNumber` entity). `get_upkeep_snapshot()` reads that override key here when present, falling back to the adapter-declared `default_interval_hours` when it is absent or uncoercible (see §6).

---

## 4. Adapter Config Dependencies

### 4.1 `maintenance_components` block

Each entry in `adapter_config["maintenance_components"]` defines one trackable component:

| Field | Type | Description |
|---|---|---|
| `sensor_suffix` | str \| None | Full suffix appended to `sensor.{object_id}_` to form the counter entity ID (e.g. `"filter_remaining"` → `sensor.{object_id}_filter_remaining`). `None` when the component sources via `proxy_for`. |
| `proxy_for` | str \| None | If set, this component sources from that component's sensor when present, falling back to its own `sensor_suffix` |
| `reset_button` | dict \| None | Resolves the component's reset button: `entity_suffixes` (appended to `button.{object_id}_`) tried first, then `token_sets` as all-tokens-must-match registry fallbacks. A `token_sets` match is additionally rejected if its resolved `entity_id` contains the substring `"maintenance"` (see note below). Absent → no reset button. |
| `default_interval_hours` | float | Factory-default cleaning/replacement interval |
| `max_interval_hours` | float | Maximum allowed interval override |
| `label` | str | Display name shown in panel |
| `icon` | str | MDI icon name |

> **`token_sets` `"maintenance"` exclusion guard.** `_get_replacement_reset_entity()` resolves the **upstream** reset button. After trying `entity_suffixes`, it falls back to `token_sets` (all required tokens must match an entity in the registry). A token-matched button is accepted **only if** its `entity_id` does **not** contain the substring `"maintenance"` (`"maintenance" not in entity_id.lower()`). This guard exists so the integration's own `number.{object_id}_{component}_maintenance_interval` interval-override entities (`translation_key: "maintenance_interval"`) are never mis-resolved as the upstream counter-reset button. `entity_suffixes` matches are not subject to this guard.

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
manager.get_upkeep_snapshot(*, vacuum_entity_id: str) -> dict
```

Keyword-only. Returns a composite snapshot used by the panel's maintenance tab:

```python
{
    "replacement_items": [
        {
            "component":    str,
            "label":        str,
            "status":       str,        # "unknown" | "replace_now" | "replace_soon" | "warning" | "good"
            "remaining_percent": float | None,
            "entity_id":    str | None,
            # ... plus remaining_value, remaining_hours, usage_hours,
            #     total_life_hours, reset metadata, guide, etc.
        },
        ...
    ],
    "maintenance_items": [
        {
            "component":         str,
            "label":             str,
            "status":            str,
            "remaining_hours":   float,
            "interval_hours":    float,
            "reset_at":          str | None,
            # ... plus used_since_reset_hours, current_usage_hours,
            #     default/max_interval_hours, guide, etc.
        },
        ...
    ],
    "attention_count":          int,    # count of items in warning/replace_soon/replace_now
    "highest_priority_status":  str,    # worst status across all items
    "station_water":            str | None,   # flat: raw station water state value
    "station_water_label":      str | None,   # flat: "NN%" or display label
    "station_water_entity":     str | None,
    "dock_events": {
        "last_mop_wash":     str | None,  # ISO timestamp
        "last_dust_empty":   str | None,
        "last_dry_start":    str | None,
        "last_dry_duration": str | None,
        "mop_wash_count":    int,
        "dust_empty_count":  int,
        "dry_start_count":   int,
    },
    # ... plus vacuum_entity_id, dock_status[_label/_entity],
    #     model_meta, attention_summary, updated_at.
}
```

`station_water` is exposed as **flat keys** (`station_water`, `station_water_label`, `station_water_entity`) — not a `{pct, status}` sub-dict.

**Status priority order** (for `highest_priority_status`): `"replace_now"` > `"replace_soon"` > `"warning"` > `"good"` > `"unknown"`.

### 5.2 `get_maintenance_remaining`

```python
manager.get_maintenance_remaining(
    *,
    vacuum_entity_id: str,
    component: str,
    interval_hours: float,
) -> dict
```

Keyword-only. The effective `interval_hours` is supplied by the **caller** (e.g.
`get_upkeep_snapshot`, which resolves the override-vs-default precedence — see §6);
this method does not read the override itself. Computes remaining integration-tracked hours:

```
reset_usage    = data["maintenance"][vacuum][component].get("reset_at_usage_hours", 0.0)
current_usage  = source sensor usage_hours attribute (0.0 if unavailable)

used_since_reset = max(current_usage - reset_usage, 0.0)
remaining        = max(interval_hours - used_since_reset, 0.0)
```

Returns a **dict**:

```python
{
    "vacuum_entity_id":      str,
    "component":             str,
    "remaining_hours":       float,        # rounded to 2 dp
    "used_since_reset_hours": float,
    "interval_hours":        float,        # echoed back unchanged
    "current_usage_hours":   float,
    "reset_at_usage_hours":  float,
    "reset_at":              str | None,
    "source_entity":         str | None,
    "source_available":      bool,
}
```

When no reset record exists, `reset_at_usage_hours` defaults to `0.0` (so all current usage counts as elapsed).

### 5.3 `reset_maintenance`

```python
manager.reset_maintenance(
    *,
    vacuum_entity_id: str,
    component: str,
) -> dict
```

Keyword-only. Snapshots the source sensor's current `usage_hours` as the new reset point and **replaces** the component's stored entry with exactly:

```python
data["maintenance"][vacuum][component] = {
    "reset_at_usage_hours": usage_hours,   # from source sensor attributes
    "reset_at": iso_now(),
}
```

Because the entry is replaced wholesale, this write does **not** carry over any prior `interval_hours` override key. Returns a result dict (`reset: True` on success, or `reset: False` with a `reason` of `"no_source_entity"`, `"source_unavailable"`, or `"invalid_usage_hours"` on failure).

### 5.4 `get_maintenance_state`

```python
manager.get_maintenance_state(*, vacuum_entity_id: str) -> dict
```

Keyword-only. Returns the per-component maintenance reset snapshot dict for one vacuum
(`data["maintenance"][vacuum_entity_id]`), creating the lazy `data["maintenance"]` and
per-vacuum sub-dict if absent. This is the read/init accessor used by `reset_maintenance`
and `get_maintenance_remaining`.

---

## 6. Interval Override Precedence

`get_upkeep_snapshot()` resolves the effective interval before calling
`get_maintenance_remaining()` (which itself just takes the resolved value):

```
stored_override = data["maintenance"][vacuum][component].get("interval_hours")
try:
    interval_hours = float(stored_override) if stored_override is not None
                     else default_interval_hours
except (TypeError, ValueError):
    interval_hours = default_interval_hours   # uncoercible override → fall back
```

where `default_interval_hours` comes from `adapter["maintenance_components"][component]`.
A coercible stored override takes **complete precedence** over the adapter default;
an absent or uncoercible override falls back to the default. The adapter's
`max_interval_hours` is surfaced in the snapshot for the card's interval editor and is
enforced at write time (by `set_maintenance_interval` / the interval number entity),
not at read time.

---

## 7. Dock Events Integration

`get_upkeep_snapshot()` includes dock event counts and timestamps sourced from `DockManager.get_dock_events()`. The maintenance manager reads but never writes dock event state — DockManager owns that data (see [14-dock-manager.md](14-dock-manager.md)).

> **See also:** [14-dock-manager](14-dock-manager.md) §8 for the dock event recording pipeline (`record_dock_event`, trigger detection, `set_dock_event_count`) that produces the counts read here.

---

## 8. Integration Points

| Caller | Method | When |
|---|---|---|
| Panel maintenance tab | `get_upkeep_snapshot(vacuum_entity_id=...)` | On load / refresh |
| Panel reset action | `reset_maintenance(vacuum_entity_id=..., component=...)` | User presses reset |
| Reset / remaining flow | `get_maintenance_state(vacuum_entity_id=...)` | Read/init reset snapshots |

> **See also:** [22-adapter-config-reference](22-adapter-config-reference.md) §maintenance_components for the adapter config that declares component IDs, default intervals, and labels consumed here; [14-dock-manager](14-dock-manager.md) §8 for dock event recording that feeds `get_upkeep_snapshot()`.
