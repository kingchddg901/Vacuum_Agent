# Adapter System — Developer Reference

> **Scope:** Complete implementation reference for the adapter subsystem: `adapters/registry.py` (AdapterCoordinator + shim functions), `adapters/config_schema.py` (ADAPTER_CONFIG_SCHEMA), `adapters/config_loader.py` (stored adapter loading), and `adapters/eufy/adapter.py` (Eufy reference implementation). Every registry pattern, schema block, and config-loading path is derived directly from the source.

---

## 1. Overview

The adapter system is the **brand abstraction layer**. Every piece of brand-specific knowledge — entity naming, vocabulary, completion signals, dispatch templates, discovery config, maintenance component definitions — lives in an adapter config dict registered with the adapter registry. The framework never hard-codes brand names or entity ID patterns.

**Module roles:**

| Module | Role |
|---|---|
| `adapters/registry.py` | Stores registered configs; provides both class-based (new) and shim (legacy) access surfaces |
| `adapters/config_schema.py` | `ADAPTER_CONFIG_SCHEMA` — the authoritative definition of every valid adapter field |
| `adapters/config_loader.py` | Loads stored adapter configs from integration storage at startup |
| `adapters/eufy/adapter.py` | Assembles and registers the Eufy X10 Pro Omni adapter — the reference implementation |

---

## 2. Registry (`registry.py`)

### 2.1 AdapterCoordinator

`AdapterCoordinator` is instantiated once per config entry in `EufyVacuumManager.__init__()`. It sets itself as the module-level `_active_coordinator` pointer on creation, enabling the legacy shim functions to route through it.

```python
coordinator = AdapterCoordinator()   # sets _active_coordinator
coordinator.register_adapter_config(vacuum_entity_id, config)
coordinator.get_adapter_config(vacuum_entity_id) -> dict | None
coordinator.get_all_adapter_configs() -> dict[str, dict]
coordinator.unregister_adapter_config(vacuum_entity_id) -> bool
coordinator.get_adapter_value(vacuum_entity_id, *path, fallback=None) -> Any
coordinator.shutdown()               # clears _active_coordinator
```

The coordinator owns its own `_registry: dict[str, dict]` dict, separate from the module-level `_REGISTRY` fallback.

### 2.2 Validation

`register_adapter_config()` calls `_validate_adapter()` before storing:

```python
_validate_adapter(vacuum_entity_id, config) -> None  # raises ValueError on error
```

Current validation: if `mapping.segmenter_engine` is present and not `None`, it must match a key in `mapping.segmenter_engines._SEGMENTER_ENGINES`. Unknown engine names are rejected at registration time. Additional validation is expected to be added as the schema stabilizes.

### 2.3 Legacy shim functions (module level)

For backward compatibility, module-level functions route to `_active_coordinator` if set, otherwise fall back to the module-level `_REGISTRY` dict (used in tests and pre-coordinator paths):

```python
register_adapter_config(vacuum_entity_id, config)
get_adapter_config(vacuum_entity_id) -> dict | None
get_all_adapter_configs() -> dict[str, dict]
unregister_adapter_config(vacuum_entity_id) -> bool
clear_registry() -> None
get_adapter_value(vacuum_entity_id, *path, fallback=None) -> Any
```

`get_adapter_value(*path)` does nested dict traversal: each path segment indexes one level deeper. Returns `fallback` on any `KeyError` or `TypeError`.

---

## 3. Config Schema (`config_schema.py`)

`ADAPTER_CONFIG_SCHEMA` is a single dict defining all valid top-level blocks. The 17 top-level keys:

| Block | Description |
|---|---|
| `adapter_id` | str — unique brand identifier |
| `source` | `"code"` or `"stored"` |
| `display_name` | Human-readable adapter name |
| `entities` | Entity ID map (17 entity keys) |
| `vocabulary` | State string sets and card dropdown options |
| `completion` | Completion signal configuration |
| `charging` | Charging detection configuration |
| `error_tracking` | Error channel configuration |
| `dock_events` | Dock event recording configuration |
| `post_job_wash_amendment` | Post-job mop-wash amendment configuration |
| `discovery` | Room discovery source and cadence |
| `setup` | Adapter-specific setup step list |
| `dispatch` | Room-clean command template and field mapping |
| `mapping` | Map segmenter engine selection and tuning |
| `capabilities` | Detected capability flags |
| `maintenance_components` | Consumable component definitions |
| `upkeep_catalog` | Per-model upkeep guide library |
| `water_model_configs` | Tank capacity and water usage constants |

### 3.1 `entities` block (17 keys)

| Key | Domain | Description |
|---|---|---|
| `task_status` | sensor | Vacuum task/operation state |
| `dock_status` | sensor | Dock station state |
| `active_map` | sensor | Currently active map ID |
| `active_cleaning_target` | sensor | Room(s) currently being cleaned |
| `cleaning_time` | sensor | Total cleaning duration in seconds |
| `cleaning_area` | sensor | Total area cleaned in m² |
| `battery` | sensor | Battery percentage |
| `error_message` | sensor | Current error message |
| `charging` | binary_sensor | Is the vacuum currently charging? |
| `wash_frequency_mode` | select | Mop wash frequency mode |
| `wash_frequency_value_time` | number | Mop wash frequency value (minutes) |
| `dry_duration` | select | Mop dry duration setting |
| `water_level` | sensor or select | Station water level |
| `robot_position_x` | sensor | X coordinate (vacuum space) |
| `robot_position_y` | sensor | Y coordinate (vacuum space) |
| `work_mode` | sensor | Current work/drive mode |
| `cleaning_intensity` | select | Suction/cleaning intensity |

### 3.2 `vocabulary` block

State string sets (all normalized to lowercase before matching unless noted):

| Key | Type | Description |
|---|---|---|
| `hard_service_states` | list[str] | Dock states that block manual actions |
| `drying_states` | list[str] | Dock states that indicate active drying |
| `active_run_task_states` | list[str] | Task states that count as "active run" |
| `not_error_sentinels` | list[str] | error_message values that mean "no error" |
| `blocked_work_mode_states` | list[str] | Work modes that block queue-engine jobs |
| `blocked_task_status_states` | list[str] | Task status values that block queue-engine jobs |
| `blocked_dock_status_states` | list[str] | Dock status values that block queue-engine jobs |
| `cancel_service_exclusion_states` | list[str] | Task status values that explain early return as service (not cancel) |
| `water_level_aliases` | dict[str, str] | Brand display strings → canonical water level keys |
| `wash_frequency_mode_aliases` | dict[str, str] | Brand display strings → canonical frequency keys |
| `clean_mode_options` | list[{value, label}] | Card dropdown options for clean mode |
| `fan_speed_options` | list[{value, label}] | Card dropdown options for fan speed |
| `water_level_options` | list[{value, label}] | Card dropdown options for water level |
| `clean_intensity_options` | list[{value, label}] | Card dropdown options for clean intensity |

### 3.3 `dispatch` block

Controls how room-clean commands are assembled:

| Field | Eufy value | Description |
|---|---|---|
| `template` | `"eufy_room_clean"` | Which payload template to use |
| `service_domain` | `"vacuum"` | HA service domain |
| `service_name` | `"send_command"` | HA service name |
| `command` | `"room_clean"` | Command string within the service call |
| `map_id_field` | `"map_id"` | Top-level payload field for map ID |
| `map_id_type` | `"int"` | Cast map_id to this type before sending |
| `room_id_field` | `"id"` | Per-room field for room ID |
| `clean_passes_field` | `"clean_times"` | Per-room field for clean passes |
| `rooms_field` | `"rooms"` | Top-level payload field for rooms array |
| `room_fields` | dict | Per-room field renames and value_map transforms |

**`room_fields` entry:**
```python
{
    "fan_speed": {
        "field_name": "fan_speed",   # target field name in the API payload
        "value_map":  None,          # None = pass-through; dict = rename values
    }
}
```

**Built-in dispatch templates:**

| Template | Brand | Payload shape |
|---|---|---|
| `eufy_room_clean` | Eufy | `{map_id, rooms: [{id, clean_times, fan_speed, ...}]}` |
| `roborock_segment_clean` | Roborock | Segment-ID based |
| `dreame_room_clean` | Dreame | Dreame-specific |
| `generic_room_ids` | Any | Room ID list only |

### 3.4 `maintenance_components` block

Dict keyed by component_id. Each entry:

| Field | Type | Description |
|---|---|---|
| `sensor_suffix` | str \| None | Suffix used to build the upstream sensor entity ID |
| `proxy_for` | str \| None | If set, this component aliases another component's sensor |
| `default_interval_hours` | float | Factory replacement interval |
| `max_interval_hours` | float | Maximum allowed user-override interval |
| `label` | str | Display name |
| `icon` | str | MDI icon |

### 3.5 `capabilities` block

Boolean flags set by `detect_capabilities()` at adapter registration time:

| Flag | Description |
|---|---|
| `supports_mop_features` | Vacuum has mop hardware |
| `supports_water_control` | Water level can be programmatically set |
| `supports_path_control` | Cleaning path type can be set |
| `supports_edge_mopping` | Edge mopping setting is available |
| `supports_mop_wash` | Dock can auto-wash the mop |
| `supports_mop_dry` | Dock can auto-dry the mop |
| `supports_empty_dust` | Dock can auto-empty the dustbin |
| `supports_robot_position` | Position X/Y sensors are present |
| `supports_station_water` | Station water level sensor is present |

> **See also:** [22-adapter-config-reference](22-adapter-config-reference.md) for the complete field-by-field documentation of every block (`entities`, `vocabulary`, `dispatch`, `maintenance_components`, `capabilities`, and all sub-schemas).

---

## 4. Config Loader (`config_loader.py`)

### 4.1 Startup loading

```python
load_stored_adapter_configs(hass, data) -> int
```

Called from `async_setup_entry` **before** code adapter registration. Reads `data["adapters"]` — a dict of `{vacuum_entity_id: config_dict}` stored by the UI wizard — and calls `register_adapter_config()` for each. Returns the count of successfully registered configs.

Code adapters registered afterward **overwrite** stored configs for the same vacuum entity ID. This means code adapters always take precedence.

### 4.2 Save / delete / read

```python
save_adapter_config(data, vacuum_entity_id, config) -> None
```
Writes to `data["adapters"][vacuum_entity_id]`. Caller must call `manager.async_save()` and `register_adapter_config()` separately.

```python
delete_adapter_config(data, vacuum_entity_id) -> bool
```
Removes from `data["adapters"]`. Returns `True` if removed, `False` if not present. Caller handles save.

```python
get_stored_adapter_config(data, vacuum_entity_id) -> dict | None
```
Read-only. Returns stored config or `None`.

---

## 5. Eufy Adapter (`adapters/eufy/adapter.py`)

The Eufy adapter is the **reference implementation** of `ADAPTER_CONFIG_SCHEMA`. Every field maps to a measured or observed value.

### 5.1 Entry point

```python
register_eufy_adapter_for_vacuum(hass, vacuum_entity_id) -> None
```

Called once per managed vacuum at startup from `async_setup_entry`. Idempotent — re-calling overwrites the previous registration.

### 5.2 Assembly steps

1. Read `vacuum.attributes.detected_model` to determine `model_family` via `_detect_model_family()`.
2. Build `entity_candidates` dict (two naming-variant candidates per entity where robovac_mqtt uses different suffixes between versions).
3. Build `capability_hints` dict — model-based boolean hints for `detect_capabilities()`.
4. Call `detect_capabilities(hass, vacuum_entity_id, entity_candidates, model_family, capability_hints, maintenance_components)` — probes the HA entity registry and state machine; returns capability flags and resolved entity IDs.
5. Build the full `config` dict from all sub-modules: `entities.py`, `vocabulary.py`, `maintenance_components.py`, `upkeep_catalog.py`, `upkeep_guides.py`, `water_config.py`, `constants.py`.
6. Strip `None` values from the entities dict (absent entities degrade gracefully per the schema).
7. Call `register_adapter_config(vacuum_entity_id, config)`.

### 5.3 Eufy-specific sub-modules

| Module | Exported symbols |
|---|---|
| `adapters/eufy/const.py` | `ADAPTER_ID`, `STORAGE_KEY` |
| `adapters/eufy/constants.py` | `POST_JOB_AMENDMENT_MIN_WASH_INTERVAL_SECONDS`, `POST_JOB_AMENDMENT_TIMEOUT_SECONDS` |
| `adapters/eufy/entities.py` | `build_entity_id()`, all `SUFFIX_*` and `DOMAIN_*` constants |
| `adapters/eufy/vocabulary.py` | `HARD_SERVICE_STATES`, `DRYING_STATES`, `ACTIVE_RUN_TASK_STATES`, `HA_ACTIVE_VACUUM_STATES`, `DOCK_EVENT_TRIGGERS`, `WATER_LEVEL_ALIASES`, `WASH_FREQUENCY_MODE_ALIASES`, `NOT_ERROR_SENTINELS`, `CANCEL_SERVICE_EXCLUSION_STATES` |
| `adapters/eufy/maintenance_components.py` | `MAINTENANCE_COMPONENTS` |
| `adapters/eufy/model_catalog.py` | `detect_model_family()` |
| `adapters/eufy/upkeep_catalog.py` | `UPKEEP_GUIDE_FAMILY_NAMES`, `UPKEEP_MODEL_GUIDE_FAMILIES`, `UPKEEP_MODEL_NAMES` |
| `adapters/eufy/upkeep_guides.py` | `UPKEEP_GUIDE_LIBRARY` |
| `adapters/eufy/water_config.py` | `WATER_MODEL_CONFIGS` |

### 5.4 Entity ID construction

`build_entity_id(vacuum_entity_id, suffix, domain="sensor")` derives an entity ID using the `object_id_suffix` strategy:

```
object_id = vacuum_entity_id.split(".", 1)[1]   # e.g. "alfred"
entity_id = f"{domain}.{object_id}_{suffix}"    # e.g. "sensor.alfred_task_status"
```

---

## 6. Startup Registration Order

The two-phase registration order at `async_setup_entry` time:

```
1. load_stored_adapter_configs(hass, data)
   → registers any UI-wizard-built configs first

2. register_eufy_adapter_for_vacuum(hass, vacuum_entity_id)   [for each managed vacuum]
   → overwrites stored configs; code adapters always win
```

This order means: if a user built a custom adapter config via the UI wizard and then the Eufy code adapter is also registered, the code adapter takes precedence. The stored config is not deleted — it persists for reference and is used if the code adapter is removed.

---

## 7. Porting to a New Brand

To add a new brand adapter:

1. Create `adapters/{brand}/adapter.py` with a `register_{brand}_adapter_for_vacuum(hass, vacuum_entity_id)` function.
2. Build the config dict using `ADAPTER_CONFIG_SCHEMA` as the reference. Every framework-read field must be present; card-only fields (`vocabulary.clean_mode_options`, etc.) are optional.
3. Set `dispatch.template` to one of the four built-in templates, or add a new template to the dispatch engine.
4. Register via `register_adapter_config(vacuum_entity_id, config)` at startup.
5. The adapter's `setup.steps` declaration controls which setup-wizard screens the user sees (see `setup/drift.py`).

See the [porting guide](../contributing/porting-guide.md) for the complete porting walkthrough.
