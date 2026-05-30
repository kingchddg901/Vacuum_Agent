"""Onboarding state sensor — per-vacuum onboarding status across all maps.

State = 'complete' | 'floor_type_needed' | 'rooms_needed' (worst-case
across all known maps). Per-map detail in attributes so the card can
guide the user through whichever step is incomplete.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity

from ..entity_helpers import build_vacuum_device_info


class EufyVacuumOnboardingSensor(SensorEntity):
    """Exposes onboarding status across all maps for one vacuum.

    State   = 'complete' | 'floor_type_needed' | 'rooms_needed'
              (worst-case status across all known maps)
    Attributes expose per-map detail so the card can guide the user.
    """

    _attr_has_entity_name = True
    _attr_name = "Onboarding State"
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

    def _get_summary(self) -> dict[str, Any]:
        """Return the onboarding summary dict from the manager."""
        return self._manager.get_rooms_onboarding_summary(
            vacuum_entity_id=self._vacuum_entity_id,
        )

    @property
    def native_value(self) -> str:
        """Return the worst-case status across all maps (rooms_needed > floor_type_needed > complete)."""
        summary = self._get_summary()
        for map_state in summary.get("maps", []):
            if map_state.get("status") == "rooms_needed":
                return "rooms_needed"
        for map_state in summary.get("maps", []):
            if map_state.get("status") == "floor_type_needed":
                return "floor_type_needed"
        return "complete"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return per-map onboarding detail."""
        summary = self._get_summary()
        return {
            "all_complete": summary.get("all_complete", False),
            "vacuum_entity_id": self._vacuum_entity_id,
            "maps": summary.get("maps", []),
        }
