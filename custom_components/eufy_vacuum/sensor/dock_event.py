"""Dock event sensor — wash / dust empty / dry timestamps.

State = the most recent dock event timestamp across all types. Individual
event timestamps and the last dry duration are exposed as attributes so
the card can read each one independently.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity

from ..entity_helpers import build_entity_name


class EufyVacuumDockEventSensor(SensorEntity):
    """Sensor exposing dock event timestamps (wash, dust empty, dry).

    State = timestamp of the most recent dock event of any type.
    All individual event timestamps and the last dry duration are
    exposed as attributes so the card can read each one independently.
    """

    def __init__(
        self,
        *,
        manager: Any,
        vacuum_entity_id: str,
    ) -> None:
        """Initialize dock event sensor."""
        self._manager = manager
        self._vacuum_entity_id = vacuum_entity_id

        self._attr_name = build_entity_name(vacuum_entity_id, "Dock Events")
        self._attr_unique_id = (
            f"{vacuum_entity_id.replace('.', '_')}_dock_events"
        )
        self._attr_icon = "mdi:dock-window"

    def _get_events(self) -> dict[str, str | None]:
        """Return stored dock events for this vacuum."""
        return self._manager.get_dock_events(
            vacuum_entity_id=self._vacuum_entity_id,
        )

    @property
    def native_value(self) -> str | None:
        """Return the most recent dock event timestamp across all types."""
        events = self._get_events()
        timestamps = [
            v
            for k, v in events.items()
            if k in {"last_mop_wash", "last_dust_empty", "last_dry_start"}
            and v is not None
        ]
        return max(timestamps) if timestamps else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return all dock event timestamps and dry duration."""
        events = self._get_events()
        return {
            "last_mop_wash": events.get("last_mop_wash"),
            "last_dust_empty": events.get("last_dust_empty"),
            "last_dry_start": events.get("last_dry_start"),
            "last_dry_duration": events.get("last_dry_duration"),
            "vacuum_entity_id": self._vacuum_entity_id,
        }
