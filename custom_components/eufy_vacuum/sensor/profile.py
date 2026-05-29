"""Available cleaning profiles sensor.

Reports how many cleaning profiles are available for a vacuum, given
its detected capabilities, and exposes profile metadata as attributes.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity

from ..entity_helpers import build_entity_name
from ..profiles.room_profiles import get_available_profiles


class EufyVacuumProfileSensor(SensorEntity):
    """Sensor reporting the count and details of available cleaning profiles for a vacuum."""

    def __init__(
        self,
        *,
        manager,
        vacuum_entity_id: str,
        capabilities: dict[str, Any],
    ) -> None:
        """Initialize sensor."""
        self._manager = manager
        self._vacuum_entity_id = vacuum_entity_id
        self._capabilities = capabilities

        self._attr_name = build_entity_name(
            vacuum_entity_id,
            "Available Profiles",
        )
        self._attr_unique_id = f"{vacuum_entity_id}_available_profiles"

    @property
    def native_value(self) -> str:
        """Return the number of available profiles as a string."""
        profiles = self._get_profiles()
        return str(len(profiles))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return profile names, labels, and capability flags."""
        profiles = self._get_profiles()

        return {
            "profile_count": len(profiles),
            "profiles": profiles,
            "profile_labels": {
                key: value.get("label", key)
                for key, value in profiles.items()
            },
            "supports_mop_features": self._capabilities.get("supports_mop_features", False),
            "supports_water_control": self._capabilities.get("supports_water_control", False),
            "capability_filtered": True,
        }

    def _get_profiles(self) -> dict[str, Any]:
        """Return profiles filtered by this vacuum's capabilities."""
        stored_profiles = self._manager.data.get("profiles", {}).get("room_profiles", {})

        return get_available_profiles(
            capabilities=self._capabilities,
            stored_profiles=stored_profiles,
        )
