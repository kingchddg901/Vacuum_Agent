"""Maintenance remaining sensor — per-component.

Computes ``interval - (current_usage_hours - reset_snapshot)``. Reads
the user-configured interval override from
``data["maintenance"][vacuum][component]["interval_hours"]`` (same slot
the set_maintenance_interval service writes to and the
EufyVacuumMaintenanceIntervalNumber entity writes to), falling back to
the adapter's declared default when no override exists.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity

from ..entity_helpers import build_vacuum_device_info


class EufyVacuumMaintenanceRemainingSensor(SensorEntity):
    """Remaining maintenance hours for one vacuum component.

    Computes: interval - (current_usage_hours - reset_snapshot).
    Reads usage_hours live from the source entity mapped in capabilities.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        manager: Any,
        vacuum_entity_id: str,
        component: str,
        label: str,
        icon: str,
        default_interval: float,
    ) -> None:
        """Initialize maintenance remaining sensor."""
        self._manager = manager
        self._vacuum_entity_id = vacuum_entity_id
        self._component = component
        self._default_interval = default_interval

        self._attr_name = f"{label} Maintenance Remaining"
        self._attr_unique_id = (
            f"{vacuum_entity_id.replace('.', '_')}_{component}_maintenance_remaining"
        )
        self._attr_icon = icon
        self._attr_device_info = build_vacuum_device_info(vacuum_entity_id)
        self._attr_native_unit_of_measurement = "h"
        self._attr_state_class = "measurement"
        self._attr_device_class = "duration"

    def _get_interval(self) -> float:
        """Return the current configured interval from storage."""
        maintenance = self._manager.data.get("maintenance", {})
        component_data = maintenance.get(self._vacuum_entity_id, {}).get(
            self._component, {}
        )
        raw = component_data.get("interval_hours")
        if raw is not None:
            try:
                return float(raw)
            except (TypeError, ValueError):
                pass
        return self._default_interval

    @property
    def native_value(self) -> float:
        """Return remaining hours."""
        interval = self._get_interval()
        result = self._manager.get_maintenance_remaining(
            vacuum_entity_id=self._vacuum_entity_id,
            component=self._component,
            interval_hours=interval,
        )
        return result["remaining_hours"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed maintenance state."""
        interval = self._get_interval()
        result = self._manager.get_maintenance_remaining(
            vacuum_entity_id=self._vacuum_entity_id,
            component=self._component,
            interval_hours=interval,
        )
        return {
            "component": self._component,
            "used_since_reset_hours": result["used_since_reset_hours"],
            "interval_hours": result["interval_hours"],
            "current_usage_hours": result["current_usage_hours"],
            "reset_at_usage_hours": result["reset_at_usage_hours"],
            "reset_at": result["reset_at"],
            "source_entity": result["source_entity"],
            "source_available": result["source_available"],
        }
