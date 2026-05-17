"""
Eufy-specific lifecycle signal functions for the job lifecycle watcher.

Translates Eufy/robovac_mqtt entity naming conventions and state
vocabulary into the signals the framework lifecycle listener consumes.

_get_lifecycle_watch_entities() — returns the HA entity IDs to watch.
_completed_finalize_signals()   — reads current entity states and returns
                                  completion signal booleans.
_active_cleaning_target_cleared() — classifies the active cleaning target
                                    state as cleared or active.

A port to a different brand replaces these three functions with
equivalents that read from that brand's entity surface. The return
shapes must be preserved exactly — the framework lifecycle listener
depends on them.

Return shape of _get_lifecycle_watch_entities():
    list[str] — full HA entity IDs to pass to
                async_track_state_change_event()

Return shape of _completed_finalize_signals():
    {
        "vacuum_state":   str,
        "task_status":    str,
        "dock_status":    str,
        "active_target":  str,
        "task_completed": bool,  # True when job finished successfully
        "target_cleared": bool,  # True when no active cleaning target
        "vacuum_docked":  bool,  # True when vacuum is at dock
    }

Return shape of _active_cleaning_target_cleared():
    bool
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .entities import build_entity_id, SUFFIX_TASK_STATUS, SUFFIX_DOCK_STATUS
from .entities import SUFFIX_ACTIVE_CLEANING_TARGET, SUFFIX_ACTIVE_MAP
from .entities import DOMAIN_SENSOR


def _get_lifecycle_watch_entities(vacuum_entity_id: str) -> list[str]:
    """Return entity ids that should trigger lifecycle reevaluation."""
    return [
        vacuum_entity_id,
        build_entity_id(vacuum_entity_id, SUFFIX_TASK_STATUS),
        build_entity_id(vacuum_entity_id, SUFFIX_DOCK_STATUS),
        build_entity_id(vacuum_entity_id, SUFFIX_ACTIVE_CLEANING_TARGET),
        build_entity_id(vacuum_entity_id, SUFFIX_ACTIVE_MAP),
    ]


def _get_entity_state_lower(hass: HomeAssistant, entity_id: str) -> str:
    """Return one entity state as a normalized lowercase string."""
    state_obj = hass.states.get(entity_id)
    if state_obj is None or state_obj.state is None:
        return ""
    return str(state_obj.state).strip().lower()


def _active_cleaning_target_cleared(value: str) -> bool:
    """Return whether the active cleaning target should be treated as cleared."""
    return value in {"", "unknown", "unavailable", "none", "null"}


def _completed_finalize_signals(hass: HomeAssistant, vacuum_entity_id: str) -> dict[str, object]:
    """Return the current strong completion signals for one vacuum."""
    object_id = vacuum_entity_id.split(".", 1)[1]
    vacuum_state = _get_entity_state_lower(hass, vacuum_entity_id)
    task_status = _get_entity_state_lower(hass, f"sensor.{object_id}_task_status")
    dock_status = _get_entity_state_lower(hass, f"sensor.{object_id}_dock_status")
    active_target = _get_entity_state_lower(hass, f"sensor.{object_id}_active_cleaning_target")

    return {
        "vacuum_state": vacuum_state,
        "task_status": task_status,
        "dock_status": dock_status,
        "active_target": active_target,
        "task_completed": task_status == "completed",
        "target_cleared": _active_cleaning_target_cleared(active_target),
        "vacuum_docked": vacuum_state == "docked",
    }
