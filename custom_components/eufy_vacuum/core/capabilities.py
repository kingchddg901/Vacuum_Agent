"""Generic vacuum capability detection for the ha_vacuum_manager framework.

Probes the HA state machine and entity registry for the entities declared
by the adapter, then combines adapter-supplied capability hints with entity
presence to produce a complete capability map.

No brand-specific knowledge lives here. All vacuum-specific inputs are
supplied by the caller (the adapter's registration function):

  entity_candidates — {key: [entity_id, ...]} — entity IDs to probe per
      capability slot. Each list is tried in order; first present wins.
      Standard keys: task_status, work_mode, dock_status, active_map,
      active_cleaning_target, cleaning_area, cleaning_time, water_level,
      robot_position_x, robot_position_y, wash_mop_button, dry_mop_button,
      empty_dust_button, cleaning_intensity.

  model_family — pre-computed model family string ('x10', 'generic', …).
      Used only for logging/return value; capability decisions use hints.

  capability_hints — {flag: bool} — model-based override flags. Each flag
      is OR-ed with entity presence: True from hints means the feature is
      supported even if the entity is absent; False (or absent) means fall
      back to entity presence detection.
      Standard flags: supports_mop_features, supports_mop_wash,
      supports_mop_dry, supports_empty_dust, supports_path_control.

  maintenance_components — {component_id: {sensor_suffix, …}} — the
      maintenance component catalog from the adapter. Passed through to
      _detect_maintenance_sources(). Absent → maintenance_sources empty.

A port to a different brand supplies its own entity_candidates and
capability_hints from its adapter registration function. The probing
logic is universal HA entity detection that works for any brand.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


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

    Used for entities whose exact suffix may differ between versions
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
    maintenance_components: dict[str, Any],
) -> dict[str, str | None]:
    """Return a component → source entity_id map for maintenance tracking.

    maintenance_components is the adapter's component catalog dict:
    {component_id: {sensor_suffix, proxy_for, label, icon, …}}.

    ``sensor_suffix`` is the full suffix appended to ``sensor.{object_id}_`` to
    form the counter entity ID — no brand naming is assumed here. A component
    with ``proxy_for`` set sources from that component's sensor when present,
    falling back to its own ``sensor_suffix`` (e.g. swivel_wheel -> filter).
    """

    def _resolve(suffix: Any) -> str | None:
        if not suffix:
            return None
        candidate = f"sensor.{object_id}_{suffix}"
        if _state_exists(hass, candidate) or _registry_entry_exists(hass, candidate):
            return candidate
        return None

    sources: dict[str, str | None] = {}
    for component, meta in maintenance_components.items():
        own = _resolve(meta.get("sensor_suffix"))
        proxy_id = meta.get("proxy_for")
        if proxy_id:
            proxy_meta = maintenance_components.get(proxy_id, {})
            sources[component] = _resolve(proxy_meta.get("sensor_suffix")) or own
        else:
            sources[component] = own

    return sources


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def detect_capabilities(
    hass: HomeAssistant,
    *,
    vacuum_entity_id: str,
    detected_model: str | None = None,
    # Adapter-supplied inputs — all optional for graceful degradation
    entity_candidates: dict[str, list[str]] | None = None,
    model_family: str | None = None,
    capability_hints: dict[str, bool] | None = None,
    maintenance_components: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Detect and return a capability map for one vacuum.

    When adapter inputs are provided, entity probing uses the supplied
    candidate lists and model-based hints. When absent (no registered
    adapter), returns a minimal capability set derived from the vacuum
    entity alone.

    "support" flags indicate the entity exists in the registry or the
    model supports the feature; "available" flags indicate the entity is
    currently in the state machine and usable now.
    """
    object_id = vacuum_entity_id.split(".", 1)[1]
    vacuum_state = hass.states.get(vacuum_entity_id)

    supported_features = 0
    if vacuum_state is not None:
        supported_features = int(vacuum_state.attributes.get("supported_features", 0))

    _cands = entity_candidates or {}
    _hints = capability_hints or {}

    def _find(key: str) -> str | None:
        return _find_existing_entity(hass, _cands.get(key, []))

    def _find_reg(key: str) -> str | None:
        return _find_registered_entity(hass, _cands.get(key, []))

    def _any_present(key: str) -> bool:
        return any(
            _state_exists(hass, e) or _registry_entry_exists(hass, e)
            for e in _cands.get(key, [])
        )

    # --- entity detection ---------------------------------------------------

    task_status_entity                = _find("task_status")
    work_mode_entity                  = _find("work_mode")
    dock_status_entity                = _find("dock_status")
    active_map_entity                 = _find("active_map")
    active_cleaning_target_entity     = _find("active_cleaning_target")
    cleaning_area_entity              = _find("cleaning_area")
    cleaning_time_entity              = _find("cleaning_time")
    water_level_entity                = _find("water_level")
    robot_position_x_entity           = _find("robot_position_x")
    robot_position_y_entity           = _find("robot_position_y")

    task_status_registered            = _find_reg("task_status")
    work_mode_registered              = _find_reg("work_mode")
    dock_status_registered            = _find_reg("dock_status")
    active_map_registered             = _find_reg("active_map")
    active_cleaning_target_registered = _find_reg("active_cleaning_target")
    cleaning_area_registered          = _find_reg("cleaning_area")
    cleaning_time_registered          = _find_reg("cleaning_time")
    water_level_registered            = _find_reg("water_level")
    robot_position_x_registered       = _find_reg("robot_position_x")
    robot_position_y_registered       = _find_reg("robot_position_y")

    # --- dock action button presence ----------------------------------------

    _wash_mop_entity_present      = _any_present("wash_mop_button")
    _dry_mop_entity_present       = _any_present("dry_mop_button")
    _empty_dust_entity_present    = _any_present("empty_dust_button")
    _cleaning_intensity_present   = _any_present("cleaning_intensity")

    # --- capability flags ---------------------------------------------------
    # Hints take precedence (model-confirmed support). Entity presence is the
    # fallback for unrecognised models that still expose the relevant entities.

    robot_position_x_entity_id = robot_position_x_entity or robot_position_x_registered
    robot_position_y_entity_id = robot_position_y_entity or robot_position_y_registered

    supports_rooms                  = bool(active_map_registered or active_map_entity)
    supports_segments               = supports_rooms
    supports_active_map             = bool(active_map_registered or active_map_entity)
    supports_active_cleaning_target = bool(
        active_cleaning_target_registered or active_cleaning_target_entity
    )
    supports_task_status    = bool(task_status_registered or task_status_entity)
    supports_work_mode      = bool(work_mode_registered or work_mode_entity)
    supports_dock_status    = bool(dock_status_registered or dock_status_entity)
    supports_cleaning_stats = bool(
        cleaning_area_registered or cleaning_time_registered
        or cleaning_area_entity or cleaning_time_entity
    )
    supports_station_water  = bool(water_level_registered or water_level_entity)
    supports_robot_position = bool(robot_position_x_entity_id and robot_position_y_entity_id)
    robot_position_available = bool(robot_position_x_entity and robot_position_y_entity)

    # Hint OR entity presence — True from either source is sufficient.
    supports_mop_features = bool(_hints.get("supports_mop_features")) or bool(
        water_level_registered or water_level_entity
    )
    supports_mop_wash     = bool(_hints.get("supports_mop_wash"))   or _wash_mop_entity_present
    supports_mop_dry      = bool(_hints.get("supports_mop_dry"))    or _dry_mop_entity_present
    supports_empty_dust   = bool(_hints.get("supports_empty_dust")) or _empty_dust_entity_present
    supports_path_control = bool(_hints.get("supports_path_control")) or _cleaning_intensity_present

    # An explicit adapter hint wins (the Roborock S6 declares supports_water_control
    # False because its mop/water is unsettable — SET_WATER_BOX/MOP_MODE are
    # RoborockUnsupportedFeature); otherwise derive it from mop support as before. Eufy
    # is unchanged (it passes no such hint, or passes True, so it falls through to
    # supports_mop_features=True either way).
    supports_water_control = (
        bool(_hints["supports_water_control"])
        if "supports_water_control" in _hints
        else supports_mop_features
    )
    supports_edge_mopping      = True
    supports_passes            = True
    supports_custom_room_config = True
    supports_room_clean        = True

    # --- maintenance sources ------------------------------------------------

    maintenance_sources: dict[str, str | None] = {}
    if maintenance_components:
        maintenance_sources = _detect_maintenance_sources(
            hass,
            object_id=object_id,
            maintenance_components=maintenance_components,
        )

    # --- live state values --------------------------------------------------

    _task_state = hass.states.get(task_status_entity) if task_status_entity else None
    task_status_value = _task_state.state if _task_state else None
    _dock_state = hass.states.get(dock_status_entity) if dock_status_entity else None
    dock_status_value = _dock_state.state if _dock_state else None

    robot_position_status = (
        "available" if robot_position_available
        else ("registered" if supports_robot_position else "inactive")
    )
    robot_position_message = (
        "Position tracking active." if robot_position_available
        else (
            "Position entities registered but not yet in state machine."
            if supports_robot_position
            else "Robot position entities not found."
        )
    )

    return {
        "vacuum_entity_id": vacuum_entity_id,
        "detected_model": detected_model,
        "model_family": model_family or "generic",
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
            "active_cleaning_target": (
                active_cleaning_target_entity or active_cleaning_target_registered
            ),
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
