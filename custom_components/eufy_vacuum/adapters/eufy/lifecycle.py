"""
SUPERSEDED IN FULL — DO NOT PORT THIS FILE. All three functions below are
callerless in production, and this docstring used to instruct a porter to
reimplement them and preserve their return shapes exactly "because the framework
lifecycle listener depends on them". It does not. Corrected 2026-08-23.

THE LIVE PATH is ``listeners/_common.py::completed_finalize_signals``, which reads
entity ids from the REGISTERED ADAPTER CONFIG. Its shape has already diverged from
the one documented below, so a porter who faithfully preserved this contract would
implement the wrong dict for a function nothing calls.

WORSE FOR A LIVE INSTALL, not just for a porter: this version re-derives entity ids
by f-string from the object id, which bypasses both user entity overrides and the
entity rescue. Anything wired to it would silently ignore a user's override on an
install where the rescue was the reason the entity resolved at all.

ROBOROCK IS THE PROOF: it ships no counterpart. Written after the generic path
existed, it never needed one.

WHY THE FILE IS STILL HERE rather than deleted: that is a removal decision with its
own tests attached, and the sibling banner in ``adapters/eufy/vocabulary.py`` records
the hazard of letting a reachability sweep make it — there, live tables sit beside
dead functions in one file. Here the whole file is the dead half, so deletion is
simpler; it is still not a thing to do in passing. What this banner buys immediately
is that nobody ports it or wires it back.

Eufy-specific lifecycle signal functions for the job lifecycle watcher.

Translated Eufy/robovac_mqtt entity naming conventions and state
vocabulary into the signals the framework lifecycle listener consumes.

_get_lifecycle_watch_entities() — returned the HA entity IDs to watch.
_completed_finalize_signals()   — read current entity states and returned
                                  completion signal booleans.
_active_cleaning_target_cleared() — classified the active cleaning target
                                    state as cleared or active.

The return shapes recorded below are kept as the historical record of what this
file did, NOT as a contract to implement against.

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
