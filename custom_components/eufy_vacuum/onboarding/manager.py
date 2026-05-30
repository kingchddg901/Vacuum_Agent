"""OnboardingManager — per-map room-discovery and floor-type confirmation state.

Owns:
- data["onboarding"] sub-tree (get/set helpers).
- get_onboarding_state: computes completeness from stored flags + live map data.
- mark_rooms_discovered: stamps rooms_discovered = True for one map.
- confirm_floor_type: records one room's floor type as user-confirmed.
- check_for_new_rooms: detects new segments in the vacuum entity attributes.
- get_rooms_onboarding_summary: aggregates onboarding state across all maps.
- reset_onboarding: clears onboarding state for one map.

Receives data (the integration root data dict) and hass (HomeAssistant instance).
Does not need a reference to the parent EufyVacuumManager.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class OnboardingManager:
    """Owns room-discovery and floor-type onboarding state per vacuum/map."""

    def __init__(
        self,
        data: dict[str, Any],
        hass: HomeAssistant,
    ) -> None:
        """Initialise with the integration root data dict and hass instance.

        Args:
            data: Integration root data dict — reads/writes data["onboarding"].
            hass: HomeAssistant instance (to read vacuum entity attributes).
        """
        self._data = data
        self._hass = hass
        self._data.setdefault("onboarding", {})

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_onboarding_data(self) -> dict:
        """Return root onboarding dict."""
        self._data.setdefault("onboarding", {})
        return self._data["onboarding"]

    def _get_map_onboarding(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict:
        """Return onboarding state for one vacuum/map, creating defaults if absent."""
        ob = self._get_onboarding_data()
        ob.setdefault(vacuum_entity_id, {})
        ob[vacuum_entity_id].setdefault(
            str(map_id),
            {
                "rooms_discovered": False,
                "floor_types_confirmed": {},
                "room_count_at_last_check": 0,
                "discovery_notified": False,
                "rebuild_notified": False,
            },
        )
        return ob[vacuum_entity_id][str(map_id)]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_onboarding_state(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return full onboarding status for one vacuum/map."""
        map_ob = self._get_map_onboarding(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

        map_bucket = (
            self._data.get("maps", {})
            .get(vacuum_entity_id, {})
            .get(str(map_id), {})
        )
        rooms = map_bucket.get("rooms", {})

        confirmed = map_ob.get("floor_types_confirmed", {})
        enabled_rooms_needing_floor_type: list[str] = []

        for room_id_key, room_data in rooms.items():
            if not room_data.get("enabled", False):
                continue
            if not confirmed.get(str(room_id_key), False):
                enabled_rooms_needing_floor_type.append(str(room_id_key))

        rooms_discovered = bool(map_ob.get("rooms_discovered", False)) and len(rooms) > 0
        floor_types_complete = len(enabled_rooms_needing_floor_type) == 0
        onboarding_complete = rooms_discovered and floor_types_complete

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "rooms_discovered": rooms_discovered,
            "room_count": len(rooms),
            "floor_types_complete": floor_types_complete,
            "onboarding_complete": onboarding_complete,
            "enabled_rooms_needing_floor_type": enabled_rooms_needing_floor_type,
            "status": (
                "complete" if onboarding_complete
                else "floor_type_needed" if rooms_discovered
                else "rooms_needed"
            ),
        }

    def mark_rooms_discovered(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> None:
        """Mark rooms as discovered for one map."""
        map_ob = self._get_map_onboarding(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        map_ob["rooms_discovered"] = True

        rooms = (
            self._data.get("maps", {})
            .get(vacuum_entity_id, {})
            .get(str(map_id), {})
            .get("rooms", {})
        )
        map_ob["room_count_at_last_check"] = len(rooms)

    def confirm_floor_type(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        room_id: str,
    ) -> None:
        """Mark a room's floor type as explicitly confirmed by the user."""
        map_ob = self._get_map_onboarding(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        map_ob.setdefault("floor_types_confirmed", {})
        map_ob["floor_types_confirmed"][str(room_id)] = True

    def check_for_new_rooms(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> bool:
        """Return True if room count has grown since last check."""
        map_ob = self._get_map_onboarding(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

        vacuum_state = self._hass.states.get(vacuum_entity_id)
        if vacuum_state is None:
            return False

        segments = vacuum_state.attributes.get("segments")
        if not isinstance(segments, list):
            return False

        current_count = len(segments)
        last_count = int(map_ob.get("room_count_at_last_check", 0))

        return current_count > last_count

    def get_rooms_onboarding_summary(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any]:
        """Return onboarding status across all known maps for one vacuum."""
        maps = self._data.get("maps", {}).get(vacuum_entity_id, {})
        summaries = []
        any_incomplete = False

        for map_id in maps.keys():
            state = self.get_onboarding_state(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
            )
            summaries.append(state)
            if not state["onboarding_complete"]:
                any_incomplete = True

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "all_complete": not any_incomplete,
            "maps": summaries,
        }

    def reset_onboarding(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Clear onboarding state for one map, forcing re-check on next evaluation."""
        ob = self._get_onboarding_data()
        ob.setdefault(vacuum_entity_id, {})
        ob[vacuum_entity_id][str(map_id)] = {
            "rooms_discovered": False,
            "floor_types_confirmed": {},
            "room_count_at_last_check": 0,
            "discovery_notified": False,
            "rebuild_notified": False,
        }
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "reset": True,
        }
