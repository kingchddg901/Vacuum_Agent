# Capability flags (generated)

Generated from `custom_components/eufy_vacuum/core/capabilities.py` (`KNOWN_CAPABILITY_HINTS`, `detect_capabilities`), `custom_components/eufy_vacuum/adapters/config_schema.py` (`ADAPTER_CONFIG_SCHEMA['capabilities']`) and `custom_components/eufy_vacuum/adapters/registry.py` (`_validate_adapter`).

## Three namespaces, one vocabulary

| Namespace | Enumerated by | Size | Validated at registration | Consumed by |
|---|---|--:|---|---|
| `capabilities` config block | `ADAPTER_CONFIG_SCHEMA['capabilities']['fields']` | 21 | yes - the schema walker checks types and rejects unknown keys | `custom_components/eufy_vacuum/adapters/registry.py`, `custom_components/eufy_vacuum/core/manager.py`, `custom_components/eufy_vacuum/dispatch/manager.py`, `custom_components/eufy_vacuum/jobs/active_job.py`, `custom_components/eufy_vacuum/room_entities.py` |
| `capability_hints` config block | `KNOWN_CAPABILITY_HINTS` (a different file) | 13 | yes - `_validate_adapter` rejects any key outside that frozenset | `detect_capabilities()` |
| `detect_capabilities()` return | the return dict literal | 42 keys, 22 of them `supports_*` | n/a (output, not input) | the per-vacuum capability payload |

The `capabilities` block is fully enumerated in the schema and is never read by `detect_capabilities()`. The `capability_hints` block is the opposite: the schema declares it as a bare `dict` with no `fields`, so the schema walker cannot see inside it; `_validate_adapter` checks it instead, against a frozenset that lives in `custom_components/eufy_vacuum/core/capabilities.py`. The two share key names and are different dictionaries with different consumers.

## Config-declarable vs detected-only

| Flag | `capabilities` block | hintable | in detection output | hint rule |
|---|---|---|---|---|
| `has_attribute_rooms` | no | yes | no | permissive |
| `honors_clean_order` | yes | no | no | - |
| `position_lock_reliable` | yes | no | no | - |
| `rooms_unique_per_job` | yes | no | no | - |
| `supports_active_cleaning_target` | no | no | yes | - |
| `supports_active_map` | no | no | yes | - |
| `supports_cleaning_stats` | no | no | yes | - |
| `supports_custom_room_config` | no | yes | yes | authoritative |
| `supports_dock_status` | no | no | yes | - |
| `supports_edge_mopping` | yes | yes | yes | authoritative |
| `supports_empty_dust` | yes | yes | yes | permissive |
| `supports_goto` | yes | yes | yes | authoritative |
| `supports_mop_dry` | yes | yes | yes | permissive |
| `supports_mop_features` | yes | yes | yes | permissive |
| `supports_mop_wash` | yes | yes | yes | permissive |
| `supports_passes` | no | yes | yes | authoritative |
| `supports_path_control` | yes | yes | yes | permissive |
| `supports_robot_position` | yes | no | yes | - |
| `supports_room_clean` | no | yes | yes | authoritative |
| `supports_room_profiles` | yes | no | no | - |
| `supports_rooms` | no | no | yes | - |
| `supports_segments` | no | no | yes | - |
| `supports_station_water` | yes | no | yes | - |
| `supports_task_status` | no | no | yes | - |
| `supports_water_control` | yes | yes | yes | authoritative |
| `supports_work_mode` | no | no | yes | - |
| `supports_zone_clean` | yes | yes | yes | authoritative |
| `supports_zone_repeat` | yes | no | no | - |
| `zone_max` | yes | no | no | - |
| `zone_max_area_m2` | yes | no | no | - |
| `zone_max_side_m` | yes | no | no | - |
| `zone_min_area_m2` | yes | no | no | - |
| `zone_min_side_m` | yes | no | no | - |

- **Detected-only (8)** - emitted by `detect_capabilities()`, declarable in neither config namespace: `supports_active_cleaning_target`, `supports_active_map`, `supports_cleaning_stats`, `supports_dock_status`, `supports_rooms`, `supports_segments`, `supports_task_status`, `supports_work_mode`.
- **Config-block-only (10)** - declarable in the `capabilities` block, never emitted by detection and not a valid hint: `honors_clean_order`, `position_lock_reliable`, `rooms_unique_per_job`, `supports_room_profiles`, `supports_zone_repeat`, `zone_max`, `zone_max_area_m2`, `zone_max_side_m`, `zone_min_area_m2`, `zone_min_side_m`.
- **In both config namespaces (9)**: `supports_edge_mopping`, `supports_empty_dust`, `supports_goto`, `supports_mop_dry`, `supports_mop_features`, `supports_mop_wash`, `supports_path_control`, `supports_water_control`, `supports_zone_clean`.
- **Hint-only (4)** - a valid `capability_hints` key with no `capabilities` block counterpart: `has_attribute_rooms`, `supports_custom_room_config`, `supports_passes`, `supports_room_clean`.

## How each detected flag is derived

`permissive` = hint OR entity presence (`True` from either source is enough). `authoritative` = `_hint_wins`: an explicit hint overrides the derived default, so a brand can declare a categorical `False`. `-` = no hint is consulted.

| Flag | Hint rule | Derivation |
|---|---|---|
| `supports_active_cleaning_target` | - | `bool(active_cleaning_target_registered or active_cleaning_target_entity)` |
| `supports_active_map` | - | `bool(active_map_registered or active_map_entity)` |
| `supports_cleaning_stats` | - | `bool(cleaning_area_registered or cleaning_time_registered or cleaning_area_entity or cleaning_time_entity)` |
| `supports_custom_room_config` | authoritative | `hint if declared, else True` |
| `supports_dock_status` | - | `bool(dock_status_registered or dock_status_entity)` |
| `supports_edge_mopping` | authoritative | `hint if declared, else True` |
| `supports_empty_dust` | permissive | `bool(_hints.get('supports_empty_dust')) or _empty_dust_entity_present` |
| `supports_goto` | authoritative | `hint if declared, else False` |
| `supports_mop_dry` | permissive | `bool(_hints.get('supports_mop_dry')) or _dry_mop_entity_present` |
| `supports_mop_features` | permissive | `bool(_hints.get('supports_mop_features')) or bool(water_level_registered or water_level_entity)` |
| `supports_mop_wash` | permissive | `bool(_hints.get('supports_mop_wash')) or _wash_mop_entity_present` |
| `supports_passes` | authoritative | `hint if declared, else True` |
| `supports_path_control` | permissive | `bool(_hints.get('supports_path_control')) or _cleaning_intensity_present` |
| `supports_robot_position` | - | `bool(robot_position_x_entity_id and robot_position_y_entity_id)` |
| `supports_room_clean` | authoritative | `hint if declared, else True` |
| `supports_rooms` | - | `bool(active_map_registered or active_map_entity or _has_attribute_rooms)` |
| `supports_segments` | - | `supports_rooms` |
| `supports_station_water` | - | `bool(water_level_registered or water_level_entity)` |
| `supports_task_status` | - | `bool(task_status_registered or task_status_entity)` |
| `supports_water_control` | authoritative | `hint if declared, else supports_mop_features` |
| `supports_work_mode` | - | `bool(work_mode_registered or work_mode_entity)` |
| `supports_zone_clean` | authoritative | `hint if declared, else True` |

10 of the 22 `supports_*` flags consult no hint at all: `supports_active_cleaning_target`, `supports_active_map`, `supports_cleaning_stats`, `supports_dock_status`, `supports_robot_position`, `supports_rooms`, `supports_segments`, `supports_station_water`, `supports_task_status`, `supports_work_mode`.

## `supports_*` vs `*_available`

Detect and return a capability map for one vacuum.

When adapter inputs are provided, entity probing uses the supplied
candidate lists and model-based hints. When absent (no registered
adapter), returns a minimal capability set derived from the vacuum
entity alone.

"support" flags indicate the entity exists in the registry or the
model supports the feature; "available" flags indicate the entity is
currently in the state machine and usable now.

| Flag | Value |
|---|---|
| `active_cleaning_target_available` | `bool(active_cleaning_target_entity)` |
| `active_map_available` | `bool(active_map_entity)` |
| `cleaning_stats_available` | `bool(cleaning_area_entity or cleaning_time_entity)` |
| `dock_status_available` | `bool(dock_status_entity)` |
| `robot_position_available` | `robot_position_available` |
| `station_water_available` | `bool(water_level_entity)` |
| `task_status_available` | `bool(task_status_entity)` |
| `work_mode_available` | `bool(work_mode_entity)` |

## What the two shipped adapters declare

| Flag | eufy `capabilities` | roborock `capabilities` | dreame `capabilities` | eufy `capability_hints` | roborock `capability_hints` | dreame `capability_hints` |
|---|---|---|---|---|---|---|
| `has_attribute_rooms` | - | - | - | `has_attribute_rooms` | - | - |
| `honors_clean_order` | - | `False` | `True` | - | - | - |
| `position_lock_reliable` | `False` | `False` | - | - | - | - |
| `rooms_unique_per_job` | `True` | `False` | - | - | - | - |
| `supports_custom_room_config` | - | - | - | - | - | - |
| `supports_edge_mopping` | `caps.get('supports_edge_mopping', True)` | `False` | `False` | - | - | `False` |
| `supports_empty_dust` | `caps.get('supports_empty_dust', False)` | `False` | `caps.get('supports_empty_dust', station_collectable)` | `model_family in {'x10', 'x8', 'l60', 'l50'}` | - | `station_collectable` |
| `supports_goto` | - | - | `caps.get('supports_goto', False)` | - | - | `profile.get('has_path_control', False)` |
| `supports_mop_dry` | `caps.get('supports_mop_dry', False)` | `False` | `caps.get('supports_mop_dry', station_dryable)` | `model_family in {'x10', 'x8'}` | - | `station_dryable` |
| `supports_mop_features` | `caps.get('supports_mop_features', False)` | `caps.get('supports_mop_features', profile['has_mop'])` | `caps.get('supports_mop_features', profile['has_mop'])` | `model_family in {'x10', 'x8', 'l60', 'l50'}` | - | `profile['has_mop']` |
| `supports_mop_wash` | `caps.get('supports_mop_wash', False)` | `False` | `caps.get('supports_mop_wash', station_washable)` | `model_family in {'x10', 'x8'}` | - | `station_washable` |
| `supports_passes` | - | - | - | - | - | - |
| `supports_path_control` | `caps.get('supports_path_control', False)` | `profile.get('has_path_control', False)` | `profile.get('has_path_control', True)` | `model_family in {'x10', 'x8'}` | - | `profile.get('has_path_control', False)` |
| `supports_robot_position` | `caps.get('supports_robot_position', False)` | `caps.get('supports_robot_position', False)` | - | - | - | - |
| `supports_room_clean` | - | - | - | - | - | - |
| `supports_room_profiles` | - | `mop_settable` | - | - | - | - |
| `supports_station_water` | `caps.get('supports_station_water', False)` | `False` | - | - | - | - |
| `supports_water_control` | `caps.get('supports_water_control', False)` | `mop_settable` | `mop_settable` | - | - | - |
| `supports_zone_clean` | `caps.get('supports_zone_clean', True)` | `caps.get('supports_zone_clean', True)` | `caps.get('supports_zone_clean', False)` | - | - | `profile.get('supports_zone_clean', False)` |
| `supports_zone_repeat` | `False` | - | - | - | - | - |
| `zone_max` | `10` | `5` | `10` | - | - | - |
| `zone_max_area_m2` | - | `3.05` | - | - | - | - |
| `zone_max_side_m` | `10.0` | - | - | - | - | - |
| `zone_min_area_m2` | - | `0.0929` | - | - | - | - |
| `zone_min_side_m` | `0.5` | - | - | - | - | - |

## The hint contract

Every flag `capability_hints` may carry — the ONLY keys this module reads. A hint is a silent no-op if the key is not in this set: `_hints.get(name)` simply misses and the derived/default value stands. That makes a typo indistinguishable from an undeclared capability, which is the same silent-wrong-answer shape as the hardcoded `True` that `_hint_wins` exists to prevent — a brand declaring `supports_zone_cleen: False` would be ignored exactly as thoroughly as one declaring nothing. `registry._validate_adapter` checks adapter `capability_hints` against this set so the typo is caught at registration instead of at "why is this control showing?". Keep in sync with the `_hints` reads below; the contract test asserts it matches.

Valid hint keys: `has_attribute_rooms`, `supports_custom_room_config`, `supports_edge_mopping`, `supports_empty_dust`, `supports_goto`, `supports_mop_dry`, `supports_mop_features`, `supports_mop_wash`, `supports_passes`, `supports_path_control`, `supports_room_clean`, `supports_water_control`, `supports_zone_clean`.
