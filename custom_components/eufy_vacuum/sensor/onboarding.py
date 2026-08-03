"""Onboarding state sensor — per-vacuum onboarding status across all maps.

State = 'complete' | 'floor_type_needed' | 'rooms_needed' (worst-case
across all known maps). Per-map detail in attributes so the card can
guide the user through whichever step is incomplete.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory

from ..entity_helpers import build_vacuum_device_info


class EufyVacuumOnboardingSensor(SensorEntity):
    """Exposes onboarding status across all maps for one vacuum.

    State   = 'complete' | 'floor_type_needed' | 'rooms_needed'
              (worst-case status across all known maps)
    Attributes expose per-map detail so the card can guide the user.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "onboarding_state"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:clipboard-check-outline"

    def __init__(
        self,
        *,
        manager: Any,
        vacuum_entity_id: str,
    ) -> None:
        """Initialize onboarding sensor."""
        self._manager = manager
        self._vacuum_entity_id = vacuum_entity_id

        self._attr_unique_id = (
            f"{vacuum_entity_id.replace('.', '_')}_onboarding_state"
        )
        self._attr_device_info = build_vacuum_device_info(vacuum_entity_id)
        # ONB-5: native_value AND extra_state_attributes each independently called
        # get_rooms_onboarding_summary — HA reads both properties per state-write cycle,
        # so it ran twice for no reason. Cache once per poll (mirrors
        # sensor/maintenance.py's EufyVacuumMaintenanceRemainingSensor).
        self._cached_summary: dict[str, Any] = {}

    async def async_added_to_hass(self) -> None:
        """Warm the summary cache before the first state write."""
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        """Fetch the onboarding summary once and cache it for this update cycle."""
        self._cached_summary = self._manager.get_rooms_onboarding_summary(
            vacuum_entity_id=self._vacuum_entity_id,
        )

    async def async_update(self) -> None:
        """Poll: refresh the cached summary."""
        self._refresh_summary()

    @property
    def native_value(self) -> str:
        """Return the worst-case status across all maps (rooms_needed > floor_type_needed > complete)."""
        summary = self._cached_summary
        maps = summary.get("maps", [])
        # DR-ONB-3: an empty maps collection is not vacuously complete --
        # both scan loops below fall through on an empty list. Mirrors
        # setup/status.py's non-empty-collection guard: no map imported yet
        # means rooms genuinely need to be set up.
        if not maps:
            return "rooms_needed"
        for map_state in maps:
            if map_state.get("status") == "rooms_needed":
                return "rooms_needed"
        for map_state in maps:
            if map_state.get("status") == "floor_type_needed":
                return "floor_type_needed"
        return "complete"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return per-map onboarding detail."""
        summary = self._cached_summary
        return {
            "all_complete": summary.get("all_complete", False),
            "vacuum_entity_id": self._vacuum_entity_id,
            "maps": summary.get("maps", []),
        }
