"""Maintenance remaining sensor — per-component.

Computes ``interval - (current_usage_hours - reset_snapshot)``. Reads
the user-configured interval override from
``data["maintenance"][vacuum][component]["interval_hours"]`` (same slot
the set_maintenance_interval service writes to and the
EufyVacuumMaintenanceIntervalNumber entity writes to), falling back to
the adapter's declared default when no override exists.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity

from ..entity_helpers import build_vacuum_device_info

_LOGGER = logging.getLogger(__name__)


class EufyVacuumMaintenanceRemainingSensor(SensorEntity):
    """Remaining maintenance hours for one vacuum component.

    Computes: interval - (current_usage_hours - reset_snapshot).
    Reads usage_hours live from the source entity mapped in capabilities.
    Returns ``available = False`` (and ``native_value = None``) when the
    source entity is unavailable so stale hours are never silently reported.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "maintenance_remaining"

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
        self._label = label
        self._default_interval = default_interval

        self._attr_unique_id = (
            f"{vacuum_entity_id.replace('.', '_')}_{component}_maintenance_remaining"
        )
        self._attr_icon = icon
        self._attr_device_info = build_vacuum_device_info(vacuum_entity_id)
        self._attr_native_unit_of_measurement = "h"
        self._attr_state_class = "measurement"
        self._attr_device_class = "duration"
        self._attr_translation_placeholders = {"component": label}
        # Availability tracking — updated on each poll via async_update().
        # Start unavailable: the source entity (another integration's sensor)
        # may not be populated yet during the startup load race. Starting True
        # would make the first refresh look like a genuine available→unavailable
        # transition and log a spurious warning. We only warn once the source has
        # actually been seen available and then drops.
        self._attr_available = False
        self._cached_result: dict[str, Any] = {}

    async def async_added_to_hass(self) -> None:
        """Warm the result cache before the first state write."""
        self._refresh_cache()

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

    def _refresh_cache(self) -> None:
        """Fetch fresh data, update availability, and log transitions."""
        result = self._manager.get_maintenance_remaining(
            vacuum_entity_id=self._vacuum_entity_id,
            component=self._component,
            interval_hours=self._get_interval(),
        )
        now_available = bool(result.get("source_available", True))
        if self._attr_available and not now_available:
            _LOGGER.warning(
                "Maintenance sensor %s (%s): source entity unavailable",
                self._vacuum_entity_id,
                self._component,
            )
        elif not self._attr_available and now_available:
            _LOGGER.debug(  # pragma: no cover
                "Maintenance sensor %s (%s): source entity available again",
                self._vacuum_entity_id,
                self._component,
            )
        self._attr_available = now_available
        self._cached_result = result

    async def async_update(self) -> None:
        """Poll: refresh cached result and availability."""
        self._refresh_cache()

    @property
    def native_value(self) -> float | None:
        """Return remaining hours, or None when the source entity is unavailable."""
        if not self._attr_available:
            return None
        return self._cached_result.get("remaining_hours")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed maintenance state."""
        result = self._cached_result
        return {
            "component": self._component,
            "used_since_reset_hours": result.get("used_since_reset_hours"),
            "interval_hours": result.get("interval_hours"),
            "current_usage_hours": result.get("current_usage_hours"),
            "reset_at_usage_hours": result.get("reset_at_usage_hours"),
            "reset_at": result.get("reset_at"),
            "source_entity": result.get("source_entity"),
            "source_available": result.get("source_available"),
        }
