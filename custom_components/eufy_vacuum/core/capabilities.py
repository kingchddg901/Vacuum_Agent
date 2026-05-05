"""Capability detection for Eufy Vacuum Manager."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


MAINTENANCE_COMPONENTS: dict[str, dict] = {
    "filter": {
        "sensor_suffix": "filter",
        "default_interval_hours": 20.0,
        "label": "Filter",
        "icon": "mdi:air-filter",
    },
    "sensor": {
        "sensor_suffix": "sensor",
        "default_interval_hours": 60.0,
        "label": "Sensor",
        "icon": "mdi:eye-outline",
    },
    "side_brush": {
        "sensor_suffix": "side_brush",
        "default_interval_hours": 30.0,
        "label": "Side Brush",
        "icon": "mdi:broom",
    },
    "rolling_brush": {
        "sensor_suffix": "rolling_brush",
        "default_interval_hours": 30.0,
        "label": "Rolling Brush",
        "icon": "mdi:broom",
    },
    "mopping_cloth": {
        "sensor_suffix": "mopping_cloth",
        "default_interval_hours": 20.0,
        "label": "Mopping Cloth",
        "icon": "mdi:water",
    },
    "cleaning_tray": {
        "sensor_suffix": "cleaning_tray",
        "default_interval_hours": 30.0,
        "label": "Cleaning Tray",
        "icon": "mdi:wiper",
    },
    "swivel_wheel": {
        "sensor_suffix": None,
        "default_interval_hours": 60.0,
        "label": "Swivel Wheel",
        "icon": "mdi:rotate-360",
    },
}


MODEL_FAMILY_HINTS: dict[str, str] = {
    "x10": "x10",
    "x8": "x8",
    "l60": "l60",
    "l50": "l50",
    "g50": "g50",
    "g40": "g40",
    "lr30": "lr30",
}

MODEL_CODE_FAMILIES: dict[str, str] = {
    "T2351": "x10",
    "T2320": "x10",
    "T2261": "x8",
    "T2262": "x8",
    "T2266": "x8",
    "T2276": "x8",
    "T2267": "l60",
    "T2268": "l60",
    "T2277": "l60",
    "T2278": "l60",
    "T2280": "c20",
    "T2080": "s1",
    "T2071": "s1",
    "T2210": "g50",
    "T2255": "g40",
    "T2256": "g40",
    "T2192": "lr30",
    "T2193": "lr30",
    "T2181": "lr30",
    "T2194": "lr30",
    "T2182": "lr30",
}


# ----------------------------------------------------------------------
# Entity lookup helpers
# ----------------------------------------------------------------------


def _state_exists(hass: HomeAssistant, entity_id: str) -> bool:
    """Return True if entity currently has a state in HA."""
    return hass.states.get(entity_id) is not None


def _registry_entry_exists(hass: HomeAssistant, entity_id: str) -> bool:
    """Return True if entity exists in registry, even if disabled."""
    registry = er.async_get(hass)
    return registry.async_get(entity_id) is not None


def _detect_model_family(detected_model: str | None) -> str:
    """Infer model family from detected model text."""
    raw = str(detected_model or "").strip()
    if raw in MODEL_CODE_FAMILIES:
        return MODEL_CODE_FAMILIES[raw]

    text = raw.lower()

    for needle, family in MODEL_FAMILY_HINTS.items():
        if needle in text:
            return family

    return "generic"


def _find_existing_entity(
    hass: HomeAssistant,
    candidates: list[str],
) -> str | None:
    """Return first candidate that currently has a state."""
    for entity_id in candidates:
        if _state_exists(hass, entity_id):
            return entity_id
    return None


def _find_registered_entity(
    hass: HomeAssistant,
    candidates: list[str],
) -> str | None:
    """Return first candidate that exists in the entity registry."""
    for entity_id in candidates:
        if _registry_entry_exists(hass, entity_id):
            return entity_id
    return None


def _find_registry_entity_by_tokens(
    hass: HomeAssistant,
    *,
    domain: str,
    object_id_prefix: str,
    required_tokens: list[str],
) -> str | None:
    """Find a registry entity by prefix + token match.

    This is used for entities whose exact suffix may differ between versions
    or may be disabled by default.
    """
    registry = er.async_get(hass)
    prefix = f"{domain}.{object_id_prefix}".lower()

    for entry in registry.entities.values():
        entity_id = str(entry.entity_id).lower()

        if not entity_id.startswith(prefix):
            continue

        if all(token in entity_id for token in required_tokens):
            return entry.entity_id

    return None


# ----------------------------------------------------------------------
# Maintenance source detection
# ----------------------------------------------------------------------


def _detect_maintenance_sources(
    hass: HomeAssistant,
    *,
    object_id: str,
) -> dict[str, str | None]:
    """Return a component -> source entity_id map for maintenance tracking.

    Swivel wheel uses filter_remaining as preferred proxy, falling back
    to swivel_wheel_remaining if filter is unavailable.
    """
    sources: dict[str, str | None] = {}

    filter_entity = f"sensor.{object_id}_filter_remaining"
    filter_available = _state_exists(hass, filter_entity) or _registry_entry_exists(
        hass, filter_entity
    )

    for component, meta in MAINTENANCE_COMPONENTS.items():
        suffix = meta["sensor_suffix"]

        if component == "swivel_wheel":
            if filter_available:
                sources[component] = filter_entity
            else:
                swivel_own = f"sensor.{object_id}_swivel_wheel_remaining"
                if _state_exists(hass, swivel_own) or _registry_entry_exists(
                    hass, swivel_own
                ):
                    sources[component] = swivel_own
                else:
                    sources[component] = None
            continue

        candidate = f"sensor.{object_id}_{suffix}_remaining"
        if _state_exists(hass, candidate) or _registry_entry_exists(hass, candidate):
            sources[component] = candidate
        else:
            sources[component] = None

    return sources


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def detect_capabilities(
    hass: HomeAssistant,
    *,
    vacuum_entity_id: str,
    detected_model: str | None = None,
) -> dict[str, Any]:
    """Detect and return a capability map for one vacuum.

    "support" flags indicate the entity exists in the registry or the model
    supports the feature; "available" flags indicate the entity is currently
    present in the state machine and usable now.
    """
    object_id = vacuum_entity_id.split(".", 1)[1]
    vacuum_state = hass.states.get(vacuum_entity_id)

    supported_features = 0
    if vacuum_state is not None:
        supported_features = int(vacuum_state.attributes.get("supported_features", 0))

    model_family = _detect_model_family(detected_model)

    task_status_candidates = [f"sensor.{object_id}_task_status"]
    work_mode_candidates = [f"sensor.{object_id}_work_mode"]
    dock_status_candidates = [f"sensor.{object_id}_dock_status"]
    active_map_candidates = [f"sensor.{object_id}_active_map"]
    active_cleaning_target_candidates = [f"sensor.{object_id}_active_cleaning_target"]
    cleaning_area_candidates = [f"sensor.{object_id}_cleaning_area"]
    cleaning_time_candidates = [f"sensor.{object_id}_cleaning_time"]
    water_level_candidates = [f"sensor.{object_id}_water_level"]
    robot_position_x_candidates = [f"sensor.{object_id}_robot_position_x_raw"]
    robot_position_y_candidates = [f"sensor.{object_id}_robot_position_y_raw"]

    task_status_entity = _find_existing_entity(hass, task_status_candidates)
    work_mode_entity = _find_existing_entity(hass, work_mode_candidates)
    dock_status_entity = _find_existing_entity(hass, dock_status_candidates)
    active_map_entity = _find_existing_entity(hass, active_map_candidates)
    active_cleaning_target_entity = _find_existing_entity(hass, active_cleaning_target_candidates)
    cleaning_area_entity = _find_existing_entity(hass, cleaning_area_candidates)
    cleaning_time_entity = _find_existing_entity(hass, cleaning_time_candidates)
    water_level_entity = _find_existing_entity(hass, water_level_candidates)

    task_status_registered = _find_registered_entity(hass, task_status_candidates)
    work_mode_registered = _find_registered_entity(hass, work_mode_candidates)
    dock_status_registered = _find_registered_entity(hass, dock_status_candidates)
    active_map_registered = _find_registered_entity(hass, active_map_candidates)
    active_cleaning_target_registered = _find_registered_entity(hass, active_cleaning_target_candidates)
    cleaning_area_registered = _find_registered_entity(hass, cleaning_area_candidates)
    cleaning_time_registered = _find_registered_entity(hass, cleaning_time_candidates)
    water_level_registered = _find_registered_entity(hass, water_level_candidates)
    robot_position_x_entity = _find_existing_entity(hass, robot_position_x_candidates)
    robot_position_y_entity = _find_existing_entity(hass, robot_position_y_candidates)
    robot_position_x_registered = _find_registered_entity(hass, robot_position_x_candidates)
    robot_position_y_registered = _find_registered_entity(hass, robot_position_y_candidates)

    maintenance_sources = _detect_maintenance_sources(hass, object_id=object_id)

    robot_position_x_entity_id = robot_position_x_entity or robot_position_x_registered
    robot_position_y_entity_id = robot_position_y_entity or robot_position_y_registered

    supports_rooms = bool(active_map_registered or active_map_entity)
    supports_segments = supports_rooms
    supports_active_map = bool(active_map_registered or active_map_entity)
    supports_active_cleaning_target = bool(
        active_cleaning_target_registered or active_cleaning_target_entity
    )
    supports_task_status = bool(task_status_registered or task_status_entity)
    supports_work_mode = bool(work_mode_registered or work_mode_entity)
    supports_dock_status = bool(dock_status_registered or dock_status_entity)
    supports_cleaning_stats = bool(
        cleaning_area_registered
        or cleaning_time_registered
        or cleaning_area_entity
        or cleaning_time_entity
    )
    supports_station_water = bool(water_level_registered or water_level_entity)

    supports_robot_position = bool(robot_position_x_entity_id and robot_position_y_entity_id)
    robot_position_available = bool(robot_position_x_entity and robot_position_y_entity)

    # Mop feature presence: model-family is the primary signal, but water_level entity
    # existence is an entity-based fallback for unrecognised models that still expose
    # a station water sensor via eufy-clean.
    supports_mop_features = model_family in {"x10", "x8", "l60", "l50"} or bool(
        water_level_registered or water_level_entity
    )

    # Dock action buttons: model-family is the primary signal.  If the model resolves
    # to "generic" (eufy-clean returned an unrecognised string or nothing), fall back
    # to checking whether the upstream button entity actually exists in the registry or
    # state machine.  This prevents a legitimate X10/X8 user from seeing dock actions
    # disabled solely because the model code was not in MODEL_CODE_FAMILIES.
    _wash_mop_entity_present = any(
        _state_exists(hass, e) or _registry_entry_exists(hass, e)
        for e in (f"button.{object_id}_wash_mop", f"button.{object_id}_mop_wash")
    )
    _dry_mop_entity_present = any(
        _state_exists(hass, e) or _registry_entry_exists(hass, e)
        for e in (f"button.{object_id}_dry_mop", f"button.{object_id}_mop_dry")
    )
    _empty_dust_entity_present = any(
        _state_exists(hass, e) or _registry_entry_exists(hass, e)
        for e in (f"button.{object_id}_empty_dust", f"button.{object_id}_empty_dust_bin")
    )

    supports_mop_wash   = model_family in {"x10", "x8"} or _wash_mop_entity_present
    supports_mop_dry    = model_family in {"x10", "x8"} or _dry_mop_entity_present
    supports_empty_dust = model_family in {"x10", "x8", "l60", "l50"} or _empty_dust_entity_present

    # Path control and edge mopping are payload fields sent to the vacuum, not button
    # entities — there is nothing in the entity registry to probe as a fallback.
    # These remain model-family-only.  A user on an unrecognised model that supports
    # these features should add their model code to MODEL_CODE_FAMILIES.
    supports_path_control = model_family in {"x10", "x8"}
    supports_water_control = supports_mop_features
    supports_edge_mopping = model_family in {"x10", "x8"}
    supports_passes = True
    supports_custom_room_config = True
    supports_room_clean = True

    _task_state = hass.states.get(task_status_entity) if task_status_entity else None
    task_status_value = _task_state.state if _task_state else None
    _dock_state = hass.states.get(dock_status_entity) if dock_status_entity else None
    dock_status_value = _dock_state.state if _dock_state else None

    robot_position_status = "available" if robot_position_available else ("registered" if supports_robot_position else "inactive")
    robot_position_message = (
        "Position tracking active." if robot_position_available
        else ("Position entities registered but not yet in state machine." if supports_robot_position
              else "Robot position entities not found.")
    )

    return {
        "vacuum_entity_id": vacuum_entity_id,
        "detected_model": detected_model,
        "model_family": model_family,
        "supported_features": supported_features,
        "supports_room_clean": supports_room_clean,
        "supports_custom_room_config": supports_custom_room_config,
        "supports_rooms": supports_rooms,
        "supports_segments": supports_segments,
        "supports_active_map": supports_active_map,
        "active_map_available": bool(active_map_entity),
        "supports_active_cleaning_target": supports_active_cleaning_target,
        "active_cleaning_target_available": bool(active_cleaning_target_entity),
        "supports_task_status": supports_task_status,
        "task_status_available": bool(task_status_entity),
        "supports_work_mode": supports_work_mode,
        "work_mode_available": bool(work_mode_entity),
        "supports_dock_status": supports_dock_status,
        "dock_status_available": bool(dock_status_entity),
        "supports_cleaning_stats": supports_cleaning_stats,
        "cleaning_stats_available": bool(cleaning_area_entity or cleaning_time_entity),
        "supports_station_water": supports_station_water,
        "station_water_available": bool(water_level_entity),
        "supports_robot_position": supports_robot_position,
        "robot_position_available": robot_position_available,
        "robot_position_status": robot_position_status,
        "robot_position_message": robot_position_message,
        "supports_mop_features": supports_mop_features,
        "supports_mop_wash": supports_mop_wash,
        "supports_mop_dry": supports_mop_dry,
        "supports_empty_dust": supports_empty_dust,
        "supports_path_control": supports_path_control,
        "supports_water_control": supports_water_control,
        "supports_edge_mopping": supports_edge_mopping,
        "supports_passes": supports_passes,
        "entities": {
            "task_status": task_status_entity or task_status_registered,
            "work_mode": work_mode_entity or work_mode_registered,
            "dock_status": dock_status_entity or dock_status_registered,
            "active_map": active_map_entity or active_map_registered,
            "active_cleaning_target": active_cleaning_target_entity or active_cleaning_target_registered,
            "cleaning_area": cleaning_area_entity or cleaning_area_registered,
            "cleaning_time": cleaning_time_entity or cleaning_time_registered,
            "water_level": water_level_entity or water_level_registered,
            "robot_position_x": robot_position_x_entity_id,
            "robot_position_y": robot_position_y_entity_id,
        },
        "sources": {
            "rooms_count": 0,
            "segments_count": 0,
            "dock_status_value": dock_status_value,
            "task_status_value": task_status_value,
        },
        "maintenance_sources": maintenance_sources,
    }
