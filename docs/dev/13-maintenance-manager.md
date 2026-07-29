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
replacement_status(*, remaining_percent: float | None) -> str
```

Converts **percent of total service life remaining** to a status bucket. The input is **not** the raw upstream sensor state — `get_upkeep_snapshot` derives it as `round(max(min(remaining_hours / total_life_hours * 100, 100), 0), 2)` (clamped 0–100, 2 dp; `manager.py:381-385`). Percent-based (not absolute hours) so a short-life part isn't pinned to "warning" — the issue #38 refactor a fresh part at 100% always reads "good".

```
if remaining_percent is None: → "unknown"   (no total_life to divide by; also uncoercible → "unknown")

pct = float(remaining_percent)

if pct <= 5:  → "replace_now"
if pct <= 10: → "replace_soon"
if pct <= 15: → "warning"
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
| `sensor_suffix` | str \| None | Full suffix appended to `sensor.{object_id}_` to form the counter entity ID (e.g. `"filter_remaining"` → `sensor.{object_id}_filter_remaining`). May be `None`, **or present alongside `proxy_for`** as the fallback source (e.g. `swivel_wheel` has both). |
| `proxy_for` | str \| None | If set, this component prefers that component's sensor when present, **falling back to its own `sensor_suffix`** (`core/capabilities.py:138-145`: `_resolve(proxy.sensor_suffix) or own`) |
| `maintenance_only` | bool | (absent → `False`) Suppresses the component's **Replacement** row entirely and excludes it from the attention roll-up; subject to the family gate (§4.3) |
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
    "guide_translations":   dict,   # lang → guide_family_key → component_id → localized overlay
}
```

The upkeep guide library maps per-model-family maintenance schedules (cleaning procedures, photos, replacement tips). It is read by `get_upkeep_snapshot()` but not mutated by the manager.

`guide_translations` is `UPKEEP_GUIDE_TRANSLATIONS` (assembled by `adapters/eufy/upkeep_guides_i18n/__init__.py` from one `<lang>.py` module per language), structured as `[lang][guide_family][component]`. `_get_upkeep_item_guide` (`manager.py:200-261`, translation overlay `226-238`) selects the entry by HA instance language (`self._guide_language()`) and overlays the localized `steps` / `notes` / `clean_frequency` / `replace_frequency` onto the English `guide_library` base **per field** — any absent field (or an unharvested component/language) falls back to English.

### 4.3 Component render gating (`maintenance_only` + the family gate)

Not every declared component yields both rows (or any row). Two gates (`manager.py:336, 344-350, 435-436, 526-529`):

- **`maintenance_only` suppresses the Replacement row.** `if not maintenance_only: replacement_items.append(...)` — a `maintenance_only` component never produces a replacement item, and its (absent) replacement status is excluded from the attention roll-up.
- **The family gate can suppress the Maintenance row too.** A `maintenance_only` component with **no** `sensor_suffix` is `continue`-skipped entirely **unless** the resolved model's guide-family documents it — the four-condition gate `_guide_family and maintenance_only and not sensor_suffix and component not in _family_guide_components`. Consequences: when **no** family resolves (unknown model) everything shows; a **sensor-backed** component is never gated. This is what makes dock/station cleanables appear on station models and hide on a dockless robot.

### 4.4 Brand dependence

> The two-source model is **Eufy-specific**. The `usage_hours` / `total_life_hours` sensor-attribute contract is Eufy's. On **Roborock**, the life-tracked `*_time_left` sensors expose **neither** attribute, so: every replacement row resolves `total_life_hours=None → remaining_percent=None → replacement_status = "unknown"`, and the integration-maintenance row never decrements (`usage_hours` missing → `current_usage=0.0` → `remaining=interval` always). The Roborock catalog declares `remaining_is_state` to gate a parallel device-countdown model, but it is **declared-but-unconsumed** (no reader — "Wave 1b", code-flag CS-2), so Roborock maintenance rows are non-functional until it ships.

---

## 5. Manager Methods

### 5.1 `get_upkeep_snapshot`

```python
manager.get_upkeep_snapshot(*, vacuum_entity_id: str) -> dict
```

Keyword-only. Returns a composite snapshot used by the panel's maintenance tab:

```python
{
    "replacement_items": [   # 24 keys each (manager.py:391-434):
        {
            "component": str, "component_label": str, "label": str,
            "kind": str, "kind_label": str, "source": str,
            "status": str,          # "unknown"|"replace_now"|"replace_soon"|"warning"|"good"
            "status_label": str,
            "remaining_percent": float | None,   # % of total service life (§2.2)
            "remaining_value": ..., "remaining_hours": float | None,
            "remaining_unit": str, "usage_hours": float | None,
            "total_life_hours": float | None, "max_life_hours": float | None,  # dup of total_life_hours
            "entity_id": str | None,
            "can_reset": bool, "reset_kind": str, "reset_kind_label": str,
            "reset_service": "button.press",      # replacement resets via a device button
            "reset_service_data": dict,
            "remaining_summary": str, "usage_summary": str,
            "guide": dict,          # see §5.1 guide shape below
        },
        ...
    ],
    "maintenance_items": [   # 26 keys each (manager.py:474-522):
        {
            "component": str, "component_label": str, "label": str,
            "kind": str, "kind_label": str, "source": str,
            "status": str, "status_label": str,
            "remaining_hours": float,       # 2 dp
            "remaining_percent": float, "remaining_unit": str,
            "interval_hours": float, "default_interval_hours": float, "max_interval_hours": float,
            "used_since_reset_hours": float,   # 2 dp
            "current_usage_hours": float,      # 2 dp
            "reset_at": str | None, "reset_at_usage_hours": float,   # not rounded
            "can_reset": bool, "reset_kind": str, "reset_kind_label": str,
            "reset_service": f"{DOMAIN}.reset_maintenance",   # maintenance resets via the service
            "reset_service_data": dict,
            "remaining_summary": str, "usage_summary": str,
            "guide": dict,
        },
        ...
    ],
    "attention_count":          int,    # status OCCURRENCES in warning/replace_soon/replace_now
                                        #   (a component contributes up to 2: its maint + replace status)
    "highest_priority_status":  str,    # worst status across items; SEEDED "good" (rank unknown=0 < good=1),
                                        #   so an all-"unknown" device still reports "good"
    "highest_priority_status_label": str,   # _display_label of the above
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
    "device_totals": {                    # lifetime usage (v1.11.0+); the WHOLE dict is None
        "area_m2": float | None,          #   when all three fields are None (not a dict of Nones)
        "time_s":  float | None,          #   total cleaning time (seconds)
        "count":   int | None,            #   total cleaning jobs
    },
    "dock_firmware":            str | None,   # dock firmware version; None when unreported
    "vacuum_entity_id":         str,
    "dock_status":              str | None,
    "dock_status_label":        str | None,
    "dock_status_entity":       str | None,
    "model_meta":               dict,     # see below
    "attention_summary":        str,      # "N item(s) need attention" text
    "updated_at":               str,      # ISO
}
```

`model_meta` (`_get_upkeep_model_meta`, 7 keys) and each item's `guide` (`_get_upkeep_item_guide`):

```python
model_meta = {"code", "name", "source", "guide_family", "guide_family_name",
              "guide_available": bool, "supported_guide_components": list}

guide = {"source_model_code", "source_model_name", "source_guide_family", "source_guide_family_name",
         "available": bool,
         "maintenance": {"frequency", "steps", "notes", "available": bool},
         "replacement": {"frequency", "steps", "notes", "available": bool},
         "display_kind": str, "display": dict}
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

When no reset record exists, `reset_at_usage_hours` defaults to `0.0` (so all current usage counts as elapsed). Rounding: `remaining_hours`, `used_since_reset_hours`, and `current_usage_hours` are 2 dp; `reset_at_usage_hours` and `interval_hours` are echoed **raw** (not rounded).

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

Because the entry is replaced wholesale, this write does **not** carry over any prior `interval_hours` override key — a reset silently discards a user's interval override (code-flag CS-1). Returns a result dict (`reset: True` on success, or `reset: False` with a `reason` of `"no_source_entity"`, `"source_unavailable"`, or `"invalid_usage_hours"` on failure).

> **Persistence is triggered by the service/entity layer, not the manager.** `reset_maintenance` (and `get_maintenance_state`/`get_maintenance_remaining`, which `setdefault`-mutate) only touch the in-memory `data`. `async_save()` is called by the service handlers — `_handle_reset_maintenance` saves **only** when the result's `reset` is `True`, `_handle_set_maintenance_interval` always saves — and by the interval Number entity's `async_set_native_value`.

### 5.5 `set_maintenance_interval` (service)

```python
# service eufy_vacuum.set_maintenance_interval (supports_response=True)
#   schema: vacuum_entity_id: entity_id, component: string,
#           interval_hours: Coerce(float) + Range(min=0.0)   # NO max — see §6
#   rounds interval_hours to 1 dp, writes data["maintenance"][vacuum][component]["interval_hours"], async_saves
# → {"saved": bool, "vacuum_entity_id": str, "component": str, "interval_hours": float}
```

This (and the `EufyVacuumMaintenanceIntervalNumber` entity) is the writer of the `interval_hours` override key that §3/§6 read.

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
an absent or uncoercible override falls back to the default.

> **The adapter's `max_interval_hours` is NOT enforced at the backend write path** (code-flag CS-3). It is surfaced in the snapshot for **card-side** validation only. The `set_maintenance_interval` service enforces only `vol.Range(min=0.0)` — **no max** (a direct call can persist e.g. 99999), then rounds to 1 dp. The `EufyVacuumMaintenanceIntervalNumber` entity clamps to the **framework** constants `MAINTENANCE_INTERVAL_MIN = 1.0` / `MAINTENANCE_INTERVAL_MAX = 500.0` (`number.py:22-23`) — independent of the per-component `max_interval_hours`. The service docstring admits "the service trusts its caller."

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
| `set_maintenance_interval` service (§5.5) | writes `["interval_hours"]` override, `async_save`s | User edits an interval |
| `EufyVacuumMaintenanceIntervalNumber` (`number.py`) | reads/writes `["interval_hours"]` (clamp 1.0–500.0, 1 dp) | Number entity set |
| `EufyVacuumMaintenanceRemainingSensor` (`sensor/maintenance.py`) | reads via `get_maintenance_remaining` (override-vs-default fallback) | Sensor state |

> **See also:** [22-adapter-config-reference](22-adapter-config-reference.md) §maintenance_components for the adapter config that declares component IDs, default intervals, and labels consumed here; [14-dock-manager](14-dock-manager.md) §8 for dock event recording that feeds `get_upkeep_snapshot()`.
