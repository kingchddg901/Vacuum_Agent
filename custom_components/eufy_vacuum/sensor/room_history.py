"""Per-room cleaning history sensor.

State = timestamp of the room's last completed cleaning. Attributes
expose per-mode timestamps and time-since metrics so automations and
the card can reason about freshness per room.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity

from ..room_entities import EufyVacuumRoomEntity


class EufyVacuumRoomCleaningHistorySensor(EufyVacuumRoomEntity, SensorEntity):
    """Per-room cleaning history sensor for automation and rules."""

    _attr_icon = "mdi:history"
    _attr_should_poll = False

    def __init__(
        self,
        *,
        coordinator_key: str,
        vacuum_entity_id: str,
        map_id: str,
        room_id: int,
        room_data: dict[str, Any],
    ) -> None:
        """Initialize room history sensor."""
        super().__init__(
            coordinator_key=coordinator_key,
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            room_id=room_id,
            room_data=room_data,
            label="Cleaning History",
            unique_suffix="cleaning_history",
        )

    def _get_history(self) -> dict[str, Any]:
        """Return current room cleaning history from the manager."""
        return self.manager.get_room_cleaning_history(
            vacuum_entity_id=self._vacuum_entity_id,
            map_id=self._map_id,
            room_id=self._room_id,
        )

    @property
    def native_value(self) -> str | None:
        """Return the timestamp of the last completed cleaning for this room."""
        return self._get_history().get("last_cleaned_at")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return room history fields useful for HA automations and rules."""
        history = self._get_history()
        return {
            **super().extra_state_attributes,
            "last_cleaned_at": history.get("last_cleaned_at"),
            "last_vacuumed_at": history.get("last_vacuumed_at"),
            "last_mopped_at": history.get("last_mopped_at"),
            "hours_since_last_vacuum": history.get("hours_since_last_vacuum"),
            "hours_since_last_mop": history.get("hours_since_last_mop"),
            "last_job_mode": history.get("last_job_mode"),
        }
