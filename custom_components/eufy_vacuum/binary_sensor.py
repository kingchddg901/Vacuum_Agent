"""Binary sensor platform — currently surfaces active-run error flags.

Single entity per vacuum: ``binary_sensor.<object_id>_active_run_has_error``.
On = the ErrorTracker has a non-null active_run_error latch with at least
one error event. Off = no active job, or active job with no errors yet.

The state is driven by ErrorTracker update notifications; we subscribe via
``add_update_listener`` and route ``async_write_ha_state`` through
``call_soon_threadsafe`` for thread safety (notifications can fire from any
context the tracker happens to be on, mirroring BatteryHealthSensor).
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_ERROR_TRACKER, DOMAIN
from .core.error_tracker import ErrorTracker
from .entity_helpers import build_vacuum_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the active-run error binary sensor per known vacuum."""
    domain_data = hass.data.get(DOMAIN, {})
    manager = domain_data.get("runtime")
    tracker: ErrorTracker | None = domain_data.get(DATA_ERROR_TRACKER)
    if manager is None or tracker is None:
        return

    entities: list[BinarySensorEntity] = []
    for vacuum_entity_id in manager.get_known_vacuum_ids():
        entities.append(
            ActiveRunHasErrorBinarySensor(
                tracker=tracker,
                vacuum_entity_id=vacuum_entity_id,
            )
        )

    if entities:
        async_add_entities(entities)


class ActiveRunHasErrorBinarySensor(BinarySensorEntity):
    """``on`` when the active run has at least one observed error.

    Device class is ``problem`` so HA badges it accordingly. The flag is
    sticky for the duration of the run — even if the upstream message has
    cleared and the latch's ``recovered`` flag is True, the binary sensor
    stays on until the job ends and the latch is harvested.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "active_run_has_error"
    _attr_icon = "mdi:alert-circle"

    def __init__(
        self,
        *,
        tracker: ErrorTracker,
        vacuum_entity_id: str,
    ) -> None:
        self._tracker = tracker
        self._vacuum_entity_id = vacuum_entity_id
        suffix = "active_run_has_error"
        self._attr_unique_id = (
            f"{vacuum_entity_id.replace('.', '_')}_{suffix}"
        )
        object_id = vacuum_entity_id.split(".", 1)[-1]
        self._attr_suggested_object_id = f"{object_id}_{suffix}"
        self._attr_device_info = build_vacuum_device_info(vacuum_entity_id)
        self._unsub: Any = None

    async def async_added_to_hass(self) -> None:
        self._unsub = self._tracker.add_update_listener(self._on_tracker_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub is not None:
            try:
                self._unsub()
            except Exception:  # pragma: no cover
                pass
            self._unsub = None

    def _on_tracker_update(self, vacuum_entity_id: str) -> None:
        if vacuum_entity_id != self._vacuum_entity_id:
            return
        hass = getattr(self, "hass", None)
        if hass is None:
            return

        @callback
        def _write() -> None:
            try:
                self.async_write_ha_state()
            except Exception:  # pragma: no cover - defensive
                pass

        try:
            hass.loop.call_soon_threadsafe(_write)
        except Exception:  # pragma: no cover - defensive
            pass

    @property
    def is_on(self) -> bool:
        latch = self._tracker.get_active_run_latch(self._vacuum_entity_id)
        if not isinstance(latch, dict):
            return False
        return int(latch.get("error_count") or 0) > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        latch = self._tracker.get_active_run_latch(self._vacuum_entity_id)
        if not isinstance(latch, dict):
            return {
                "error_count": 0,
                "current_message": None,
                "recovered": False,
                "first_seen_at": None,
                "first_seen_job_elapsed_seconds": None,
                "errored_room_id": None,
                "active_job_id": None,
            }
        return {
            "error_count": latch.get("error_count"),
            "current_message": latch.get("current_message"),
            "recovered": bool(latch.get("recovered")),
            "first_seen_at": latch.get("first_seen_at"),
            "first_seen_job_elapsed_seconds": latch.get(
                "first_seen_job_elapsed_seconds"
            ),
            "errored_room_id": latch.get("errored_room_id"),
            "active_job_id": latch.get("active_job_id"),
        }
