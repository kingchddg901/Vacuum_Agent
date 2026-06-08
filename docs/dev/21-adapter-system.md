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
coordinator = AdapterCoordinator(hass, entry)   # sets _active_coordinator
coordinator.register_adapter_config(vacuum_entity_id, config)
coordinator.get_adapter_config(vacuum_entity_id) -> dict | None
coordinator.get_all_adapter_configs() -> dict[str, dict]
coordinator.unregister_adapter_config(vacuum_entity_id) -> None
coordinator.get_adapter_value(vacuum_entity_id, *path, fallback=None) -> Any
coordinator.shutdown()               # clears _active_coordinator
```

The coordinator owns its own `_registry: dict[str, dict]` dict, separate from the module-level `_REGISTRY` fallback.

### 2.2 Validation

`register_adapter_config()` calls `_validate_adapter()` before storing:

```python
_validate_adapter(config: dict) -> list[str]   # returns a list of issue strings
```

`_validate_adapter()` returns a list of human-readable issue strings (empty = valid); it does **not** raise. `register_adapter_config()` logs every returned issue as a `warning` and then stores the config anyway — validation issues are advisory, not blocking. The one hard failure is a structurally unusable config: if `config` is not a dict, `register_adapter_config()` raises `TypeError` (and `_validate_adapter()` returns the single issue `"adapter config must be a dict"`).

Current checks:

- **`mapping` block** (when present): must be a dict; `mapping.segmenter_engine` is required and must resolve to a known engine (`known_engine_names()` in `mapping/segmenter_engines.py`); `mapping.segmenter_tuning` must pass the resolved engine's own `validate_tuning()`.
- **`job_segmenter` block** (when present): must be a dict; `job_segmenter.engine` is required and must resolve to a known job/run segmenter engine (`known_job_engine_names()` in `learning/job_segmenter_engines.py`); `job_segmenter.tuning` must pass the resolved engine's own `validate_tuning()`. This mirrors the `mapping` check (deferred import). Note this is the **counter/run** segmenter seam, distinct from the **map** segmenter `mapping` block above (see §2.4).
- **`room_profiles` block** (when present): must be a dict; `room_profiles.default_profile` (when set) must be a string, and each of `builtins`, `custom_template`, `legacy_aliases`, `floor_type_water_defaults`, `floor_type_fan_defaults`, `normalize_defaults` (when set) must be a dict. The framework merges this block over the in-code defaults per key (`resolve_profile_catalog()`), so a partial block is fine — this rule only catches a malformed declaration.
- **`dispatch.template`** (when present): must resolve to a registered dispatch engine (`known_dispatch_templates()` in `queue/dispatch_engines.py`). A schema-valid template with no registered engine yet is flagged rather than silently falling back to the Eufy shape.

Additional validation is expected to be added as the schema stabilizes.

### 2.3 Legacy shim functions (module level)

For backward compatibility, module-level functions route to `_active_coordinator` if set, otherwise fall back to the module-level `_REGISTRY` dict (used in tests and pre-coordinator paths):

```python
register_adapter_config(vacuum_entity_id, config)
get_adapter_config(vacuum_entity_id) -> dict | None
get_all_adapter_configs() -> dict[str, dict]
unregister_adapter_config(vacuum_entity_id) -> None
clear_registry() -> None
get_adapter_value(vacuum_entity_id, *path, fallback=None) -> Any
```

`get_adapter_value(*path)` does nested dict traversal: each path segment indexes one level deeper. Returns `fallback` on any `KeyError` or `TypeError`.

### 2.4 Pluggable engine seams

Three brand-specific subsystems are pluggable behind the **same seam shape**: a `Protocol`, a module-level registry dict, a `get_*()` resolver with a fallback, a `known_*()` enumerator for the validator, an adapter config block that names the engine, and a `_validate_adapter` rule. The adapter declares *which* engine; the framework owns *resolution and the cross-engine contract*. This is how a second brand swaps brand-specific behavior without touching the framework call sites.

| Seam | Module | Protocol | Registry / resolver | Adapter block | Fallback | `select`-style framework function |
|---|---|---|---|---|---|---|
| **Map segmenter** | `mapping/segmenter_engines.py` | `MapSegmenter` | `_SEGMENTER_ENGINES` / `get_segmenter_engine()` | `mapping` (`segmenter_engine` + `segmenter_tuning`) | `noop_fallback` (empty result) | — |
| **Dispatch engine** | `queue/dispatch_engines.py` | `DispatchEngine` | `_DISPATCH_ENGINES` / `get_dispatch_engine()` | `dispatch` (`template` + field map) | `eufy_room_clean` | — |
| **Job/run segmenter** | `learning/job_segmenter_engines.py` | `JobSegmenter` | `_JOB_SEGMENTER_ENGINES` / `get_job_segmenter_engine()` | `job_segmenter` (`engine` + `tuning`) | `eufy_counter_v1` | `counter_segmentation.select_active` |

**Two segmenters, different jobs — do not conflate them.** The **map** segmenter (`eufy_cv_v1`, the Eufy CV pipeline in `adapters/eufy/segmentor.py`) turns a *map image* into polygonal room overlays. The **job/run** segmenter (`eufy_counter_v1`) turns a *counter-sample stream* (`cleaning_time` / `cleaning_area`) into ordered per-room boundaries within a single run — no geometry. They are independent seams with independent registries.

**Job-segmenter specifics** (`learning/job_segmenter_engines.py`):

- **Eufy fallback, not noop.** Unlike the map seam (whose `get_segmenter_engine()` falls back to `noop_fallback`), `get_job_segmenter_engine()` falls back to the **Eufy** engine (`_FALLBACK_JOB_ENGINE = "eufy_counter_v1"`) for an absent/unknown name — same policy as the dispatch seam. The framework's historical no-adapter default is Eufy counter segmentation, and live rollover + learned history must keep working byte-for-byte; a noop fallback would silently stop live rollover. `NoopJobSegmenter` (`"noop_job_fallback"`) stays registered for a future brand with no segmentable signal, but it is **not** the fallback.
- **`select_active` stays a framework function, not on the engine.** The job pipeline is three stages — `find_candidates → select_active → build_segments`. The engine owns the two *brand-specific* stages (`find_candidates`, `build_segments`) plus the legacy one-shot composition `segment_legacy`. `select_active` is pure ranking/filtering over the candidate *shape* (`kind`/`confident`/`strength`/`id`), so it is brand-agnostic and stays a direct framework import (`counter_segmentation.select_active`) — the external-review wizard's count/toggle re-selection logic is then uniform across brands.
- **Cross-engine contract.** The `JobBoundaryCandidate` and `JobSegment` `TypedDict`s are the canonical shape every engine emits (the exact field union the counter primitives already produce). `EufyCounterSegmenter` delegates verbatim to the `counter_segmentation` primitives, and its `DEFAULT_TUNING` (`gap_delayed_s` 35, `gap_transit_s` 60, `gap_plateau_s` 90, `area_jump_m2` 2.0, `cadence_s` 30) is defined *by reference* to that module's constants, so the Eufy path can't drift.
- **The Eufy `kind` vocabulary** (`"wash_plateau"` / `"transit"` / `"area_jump"` / `"weak"`) is produced by `find_candidates` and referenced at the Eufy-specific call sites (live `rollover_kinds`, the legacy `{"wash_plateau","area_jump"}` filter). A future brand supplies its own engine *and* its own kind literals at those sites — the documented extension point; no kind indirection is built into the seam.

---

## 3. Config Schema (`config_schema.py`)

`ADAPTER_CONFIG_SCHEMA` is a single dict defining all valid top-level blocks. The 20 top-level keys:

| Block | Description |
|---|---|
| `adapter_id` | str — unique brand identifier |
| `source` | `"code"` or `"config"` |
| `display_name` | Human-readable adapter name |
| `brand` | Short brand/app name the card uses in copy (generic phrasing when absent) |
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
| `capabilities` | Detected capability flags |
| `external_mid_run_statuses` | `task_status` strings = robot docked mid-run and will resume (holds the external run open instead of closing at the dock) |
| `settings_selects` | Global select entities for recovering per-room settings on external (app-started) runs — canonical key → `{entity_id, value_map}` |
| `maintenance_components` | Consumable component definitions |
| `upkeep_catalog` | Per-model upkeep guide library |
| `water_model_configs` | Tank capacity and water usage constants |

> **Note:** the 20 keys above are the complete set in `ADAPTER_CONFIG_SCHEMA`.
> Several blocks the Eufy adapter actually declares are **not** in the schema
> dict — `mapping`, `job_segmenter`, `live_transition`, and `room_profiles`. The
> schema walker iterates the *schema's* keys, so extra blocks are simply ignored
> by the schema (declaring them there is a deferred follow-up). `_validate_adapter()`
> nonetheless validates `mapping`, `job_segmenter`, and `room_profiles`
> opportunistically *when present* (see §2.2 and §2.4); `live_transition` carries
> only live-rollover orchestration knobs and has no validation rule yet. The Eufy
> CV map segmenter lives in `adapters/eufy/segmentor.py`; the Eufy counter/run
> segmenter engine is `eufy_counter_v1` in `learning/job_segmenter_engines.py`.

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
5. Build the full `config` dict from all sub-modules: `entities.py`, `buttons.py`, `vocabulary.py`, `maintenance_components.py`, `upkeep_catalog.py`, `upkeep_guides.py`, `water_config.py`, `constants.py`.
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
| `adapters/eufy/buttons.py` | `DOCK_ACTION_CANDIDATES`, `DOCK_ACTION_TOKENS`, `RESET_CANDIDATES`, `RESET_TOKENS` — dock-action and maintenance-reset button entity-resolution candidates / token-sets |
| `adapters/eufy/discovery.py` | `get_active_map_id()`, `discover_rooms_for_vacuum()` — Eufy room-discovery helpers |
| `adapters/eufy/lifecycle.py` | `_get_lifecycle_watch_entities()`, `_completed_finalize_signals()`, `_active_cleaning_target_cleared()` — translate Eufy entity naming + state vocabulary into the framework lifecycle listener's signals |
| `adapters/eufy/segmentor.py` | `detect_room_segments()` — Eufy CV map-segmentation pipeline (the brand's *map* segmenter, `eufy_cv_v1`; distinct from the counter/run segmenter `eufy_counter_v1` in `learning/job_segmenter_engines.py` — see §2.4) |

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
4. Pick the two segmenter engines (see §2.4). Declare `mapping.segmenter_engine` (or `noop_fallback` if the brand yields no map image) and `job_segmenter.engine` (or `noop_job_fallback` if the brand emits no per-room run signal). For Eufy these are `eufy_cv_v1` and `eufy_counter_v1`; a brand whose boundary detection differs registers its own engine in the relevant registry and names it here. Optionally declare `room_profiles` to override the framework's default profile vocabulary (an absent block uses the in-code defaults verbatim).
5. Register via `register_adapter_config(vacuum_entity_id, config)` at startup.
6. The adapter's `setup.steps` declaration controls which setup-wizard screens the user sees (see `setup/drift.py`).

See the [porting guide](../contributing/porting-guide.md) for the complete porting walkthrough.
