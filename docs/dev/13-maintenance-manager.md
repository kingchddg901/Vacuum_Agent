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

Converts **percent of total service life remaining** to a status bucket. The input is **not** the raw upstream sensor state — `get_upkeep_snapshot` derives it as `round(max(min(remaining_hours / total_life_hours * 100, 100), 0), 2)` (clamped 0–100, 2 dp; `manager.py:412-416`). Percent-based (not absolute hours) so a short-life part isn't pinned to "warning" — the issue #38 refactor a fresh part at 100% always reads "good".

```
if remaining_percent is None: → "unknown"   (no total_life to divide by; also uncoercible → "unknown")

pct = float(remaining_percent)

if pct <= 5:  → "replace_now"
if pct <= 10: → "replace_soon"
if pct <= 15: → "warning"
else:         → "good"
```

### 2.3 `_hours_summary` (the overdue-consumable guard)

```python
_hours_summary(value: Any, suffix: str) -> str | None
```

Builds the `remaining_summary` / `usage_summary` strings (`"<hours label> <suffix>"`). It guards the **result** of `_hours_text`, not the input: `_hours_text` returns `None` not only for `None` input but also for **negative** numbers and non-numerics. The four snapshot call sites used to read `_hours_text(v) + " suffix" if v is not None else None` — an **overdue consumable reports negative remaining hours**, passed the `is not None` guard, and landed on `None + str` → `TypeError` that took out `get_upkeep_snapshot` entirely (and with it `get_dashboard_snapshot`'s whole data source; found in a Roborock Q5 user's diagnostics, issue #46 thread — `upkeep_snapshot_error: TypeError(...)`). Now: no hours label → the summary is `None`, never a crash. (`manager.py:103-124`.)

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

`reset_maintenance()` writes `reset_at_usage_hours` and `reset_at`, and **preserves** an existing `interval_hours` override (it never *creates* one). The `interval_hours` override key is written by `set_maintenance_interval` and the `EufyVacuumMaintenanceIntervalNumber` entity. `get_upkeep_snapshot()` reads that override key here when present, falling back to the adapter-declared `default_interval_hours` when it is absent or uncoercible (see §6).

---

## 4. Adapter Config Dependencies

### 4.1 `maintenance_components` block

Each entry in `adapter_config["maintenance_components"]` defines one trackable component:

| Field | Type | Description |
|---|---|---|
| `sensor_suffix` | str \| None | Full suffix appended to `sensor.{object_id}_` to form the counter entity ID (e.g. `"filter_remaining"` → `sensor.{object_id}_filter_remaining`). May be `None`, **or present alongside `proxy_for`** as the fallback source (e.g. `swivel_wheel` has both). |
| `proxy_for` | str \| None | If set, this component prefers that component's sensor when present, **falling back to its own `sensor_suffix`** (`core/capabilities.py::_detect_maintenance_sources`: `_resolve(proxy.sensor_suffix) or own`) |
| `maintenance_only` | bool | (absent → `False`) Suppresses the component's **Replacement** row entirely and excludes it from the attention roll-up; subject to the family gate (§4.3) |
| `reset_button` | dict \| None | Resolves the component's reset button: `entity_suffixes` (appended to `button.{object_id}_`) tried first, then `token_sets` as all-tokens-must-match fallbacks. Since 2.1.0-beta.2 the token search looks at the vacuum's **device and config entry** siblings first (accepting only an unambiguous single match) before the original registry-wide `button.{object_id}_` prefix scan — see the note below. A `token_sets` match is additionally rejected if its resolved `entity_id` contains the substring `"maintenance"`. Absent → no reset button. |
| `default_interval_hours` | float | Factory-default cleaning/replacement interval |
| `max_interval_hours` | float | Maximum allowed interval override |
| `label` | str | Display name shown in panel |
| `icon` | str | MDI icon name |

> **`token_sets` resolution, and why the `"maintenance"` guard exists.**
> `_get_replacement_reset_entity()` resolves the **upstream** reset button. After
> trying `entity_suffixes` it falls back to `token_sets` (all required tokens must
> match), and that fallback used to scope itself by `button.{object_id}_` — the SAME
> derived name it exists to rescue, so on an install whose entities are not named
> after the vacuum both halves failed together and the reset buttons were simply
> absent. Since 2.1.0-beta.2 it asks the vacuum's **device then config-entry**
> siblings first, accepting a match only when exactly one qualifies (token matching
> is loose — all tokens appearing anywhere in the id — so a widened scope without an
> abstention rule would make a WRONG bind likelier, not rarer). The registry-wide
> prefix scan is kept after it, because an integration that names a button correctly
> while attaching it to neither scope is found by name and by nothing else.
>
> A token-matched button is accepted **only if** its `entity_id` does not contain
> `"maintenance"`, so the integration's OWN `button.{object_id}_{component}_maintenance`
> reset entities are never mis-resolved as the upstream counter-reset. That guard is a
> substring hack compensating for the prefix scan's scope: on a live install the only
> `button.alfred_*` match for `swivel_wheel` is Vacuum Agent's own button, because
> eufy-clean exposes no swivel-wheel reset at all. The sibling path needs no such
> filter — our entities live on our own service device and config entry, which neither
> scope reaches — but the prefix fallback still does. `entity_suffixes` matches are not
> subject to the guard.

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

`guide_translations` is `UPKEEP_GUIDE_TRANSLATIONS` (assembled by `adapters/eufy/upkeep_guides_i18n/__init__.py` from one `<lang>.py` module per language — 17 language modules; English is the base with no module of its own), structured as `[lang][guide_family][component]`. `_get_upkeep_item_guide` (`manager.py:224-285`, translation overlay `249-262`) selects the entry by HA instance language (`self._guide_language()`) and overlays the localized `steps` / `notes` / `clean_frequency` / `replace_frequency` onto the English `guide_library` base **per field** — any absent field (or an unharvested component/language) falls back to English.

### 4.3 Component render gating (`maintenance_only` + the family gate)

Not every declared component yields both rows (or any row). Two gates (`manager.py:367, 375-381, 462-463, 551-555`):

- **`maintenance_only` suppresses the Replacement row.** `if not maintenance_only: replacement_items.append(...)` — a `maintenance_only` component never produces a replacement item, and its (absent) replacement status is excluded from the attention roll-up.
- **The family gate can suppress the Maintenance row too.** A `maintenance_only` component with **no** `sensor_suffix` is `continue`-skipped entirely **unless** the resolved model's guide-family documents it — the four-condition gate `_guide_family and maintenance_only and not sensor_suffix and component not in _family_guide_components`. Consequences: when **no** family resolves (unknown model) everything shows; a **sensor-backed** component is never gated. This is what makes dock/station cleanables appear on station models and hide on a dockless robot.

### 4.4 Brand dependence

> The two-source model is **Eufy-specific**. The `usage_hours` / `total_life_hours` sensor-attribute contract is Eufy's. On **Roborock**, the life-tracked `*_time_left` sensors are **device-owned countdowns** exposing **neither** attribute, so: every replacement row resolves `total_life_hours=None → remaining_percent=None → replacement_status = "unknown"` (the raw remaining hours still surface as `remaining_value`/`remaining_hours`), and the integration-maintenance row never decrements (`usage_hours` missing → `current_usage=0.0` → `remaining=interval` always). `default_interval_hours`/`max_interval_hours` are advisory for Roborock — the device, not the framework interval, drives the real countdown, and the device resets itself when its own reset button is pressed. The former `remaining_is_state` flag (declared to gate a parallel device-countdown model, "Wave 1b") was **removed 2026-07-30** — it was `True` on only 4 of the 12 components, projected (with a `False` default) onto all 12 in the registered config, with zero readers (closes code-flag CS-2 by pruning; re-add it *with* its consumer if Wave 1b ships).

---

## 5. Manager Methods

### 5.1 `get_upkeep_snapshot`

```python
manager.get_upkeep_snapshot(*, vacuum_entity_id: str) -> dict
```

Keyword-only. Capabilities are fetched once via the **read-only** `get_vacuum_capabilities_snapshot` (RF-33 — this collector is on both `diagnostics.py`'s and `get_dashboard_snapshot`'s path, and detection is primed elsewhere well before this runs) and threaded into every `get_maintenance_remaining` call so the per-component loop never re-opens the non-inert `get_vacuum_capabilities(refresh=False)` path. Returns a composite snapshot used by the panel's maintenance tab:

```python
{
    "replacement_items": [   # 25 keys each (manager.py:422-461):
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
            "available": bool,      # upstream sensor state present
            "can_reset": bool,
            # the four reset_* keys are None when no reset button resolved:
            "reset_kind": "upstream" | None, "reset_kind_label": str | None,
            "reset_service": "button.press" | None,   # replacement resets via a device button
            "reset_service_data": dict | None,
            "remaining_summary": str | None,   # "NN% remaining" or _hours_summary(...); None when overdue/no label (§2.3)
            "usage_summary": str | None,
            "guide": dict,          # see §5.1 guide shape below
        },
        ...
    ],
    "maintenance_items": [   # 26 keys each (manager.py:502-548):
        {
            "component": str, "component_label": str, "label": str,
            "kind": str, "kind_label": str, "source": str,
            "status": str, "status_label": str,
            "remaining_hours": float,       # 2 dp
            "remaining_percent": float | None,   # None when interval_hours <= 0 (guide-only/dock cleanables)
            "interval_hours": float, "default_interval_hours": float, "max_interval_hours": float,
            "used_since_reset_hours": float,   # 2 dp
            "current_usage_hours": float,      # 2 dp
            "reset_at": str | None,
            "entity_id": str | None,           # the source sensor
            "available": bool,                 # source_available from get_maintenance_remaining
            "can_reset": True, "reset_kind": "integration", "reset_kind_label": "Integration",
            "reset_service": f"{DOMAIN}.reset_maintenance",   # maintenance resets via the service
            "reset_service_data": dict,
            "remaining_summary": str | None, "usage_summary": str | None,
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
    "attention_summary":        str,      # "N upkeep item(s) need attention." / "No upkeep items need attention."
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
    capabilities: dict | None = None,
) -> dict
```

Keyword-only. The effective `interval_hours` is supplied by the **caller** (e.g.
`get_upkeep_snapshot`, which resolves the override-vs-default precedence — see §6);
this method does not read the override itself. `capabilities` lets a caller that
already fetched the capabilities dict (the snapshot, via the read-only
`get_vacuum_capabilities_snapshot`) pass it through; omitted (the sensor entity
and service call sites), the method falls back to
`get_vacuum_capabilities(refresh=False)` — self-heal detection is *wanted* there,
since a maintenance sensor's poll may be the first thing to run for a
freshly-added vacuum. Computes remaining integration-tracked hours:

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

The entry is rebuilt with the fresh `reset_at_usage_hours` + `reset_at`, but a prior `interval_hours` override is **carried forward** (`if existing.get("interval_hours") is not None`) — a reset re-snapshots the usage baseline without discarding the user's custom interval (this was code-flag CS-1, fixed + regression-tested MNT-7b). Returns a result dict (`reset: True` on success, or `reset: False` with a `reason` of `"no_source_entity"`, `"source_unavailable"`, or `"invalid_usage_hours"` on failure).

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

> **The adapter's `max_interval_hours` is NOT enforced at the backend service write path** (code-flag CS-3, narrowed). The `set_maintenance_interval` service enforces only `vol.Range(min=0.0)` — **no max** (a direct call can persist e.g. 99999), then rounds to 1 dp; its docstring admits "the service trusts its caller" (card-side validation). The `EufyVacuumMaintenanceIntervalNumber` entity clamps `min` to the framework constant `MAINTENANCE_INTERVAL_MIN = 1.0`, step `0.5`, and — since EP-3 — its **max is the component's own declared `max_interval_hours`** (`meta.get("max_interval_hours", MAINTENANCE_INTERVAL_MAX)`, falling back to the framework `MAINTENANCE_INTERVAL_MAX = 500.0`; `number.py:25-27, 65`), so a component whose ceiling exceeds 500 (e.g. Eufy's `sensor`: 720) can be *restored* via set_value, not just read.

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
| `EufyVacuumMaintenanceIntervalNumber` (`number.py`) | reads/writes `["interval_hours"]` (native range 1.0 – component `max_interval_hours` (fallback 500.0), step 0.5; written value rounded to 1 dp) | Number entity set |
| `EufyVacuumMaintenanceRemainingSensor` (`sensor/maintenance.py`) | reads via `get_maintenance_remaining` (override-vs-default fallback) | Sensor state |

> **See also:** [22-adapter-config-reference](22-adapter-config-reference.md) §maintenance_components for the adapter config that declares component IDs, default intervals, and labels consumed here; [14-dock-manager](14-dock-manager.md) §8 for dock event recording that feeds `get_upkeep_snapshot()`.
