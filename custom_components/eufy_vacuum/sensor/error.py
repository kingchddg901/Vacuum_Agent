"""Error tracker sensors — active-run + last-device error surfaces.

Both sensors are backed by ErrorTracker and share a thin base class
that handles the subscribe/unsubscribe lifecycle and the
``call_soon_threadsafe`` routing of state writes (the tracker can fire
from any context). Companion ``binary_sensor.<obj>_active_run_has_error``
lives on the binary_sensor platform.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityCategory

from ..core.error_tracker import ErrorTracker
from ..entity_helpers import build_vacuum_device_info


class _ErrorTrackerSensorBase(SensorEntity):
    """Shared boilerplate for ErrorTracker-backed sensors.

    Subscribes to the tracker's update notifications and routes
    ``async_write_ha_state`` through ``call_soon_threadsafe`` so the sensor
    is callsafe regardless of which context the tracker fired from. Same
    pattern as the battery sensors' _BatteryBase.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        tracker: ErrorTracker,
        vacuum_entity_id: str,
        label: str,
        unique_suffix: str,
    ) -> None:
        self._tracker = tracker
        self._vacuum_entity_id = vacuum_entity_id
        self._attr_name = label  # device name prepended by HA
        self._attr_unique_id = (
            f"{vacuum_entity_id.replace('.', '_')}_{unique_suffix}"
        )
        object_id = vacuum_entity_id.split(".", 1)[-1]
        self._attr_suggested_object_id = f"{object_id}_{unique_suffix}"
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


class EufyVacuumActiveRunErrorSensor(_ErrorTrackerSensorBase):
    """Active-run error message + full latch context.

    State semantics:
    - ``"no_active_run"`` — no job in flight (latch can't form).
    - ``"no_error_this_run"`` — active job, no errors yet.
    - ``current_message`` — error currently active.
    - ``current_message`` (last seen) with ``recovered: True`` attribute —
      message cleared mid-run but the latch is sticky until job end.

    Attributes carry the full latch shape; consumers (the panel card,
    automations) read directly rather than rebuilding from state.
    """

    _attr_icon = "mdi:alert-circle-outline"

    def __init__(
        self,
        *,
        tracker: ErrorTracker,
        vacuum_entity_id: str,
    ) -> None:
        super().__init__(
            tracker=tracker,
            vacuum_entity_id=vacuum_entity_id,
            label="Active Run Error",
            unique_suffix="active_run_error",
        )

    @property
    def native_value(self) -> str:
        latch = self._tracker.get_active_run_latch(self._vacuum_entity_id)
        if not isinstance(latch, dict):
            # Distinguish "no run" from "run with no errors" so the card can
            # render differently. Latch only exists when an error has fired
            # during a run, so absence of latch could mean either — fall
            # back to the manager's active-jobs map to disambiguate.
            manager = self._tracker._manager  # type: ignore[attr-defined]
            active_jobs = manager.data.get("active_jobs", {})
            per_map = active_jobs.get(self._vacuum_entity_id, {})
            if isinstance(per_map, dict):
                for state in per_map.values():
                    if (
                        isinstance(state, dict)
                        and state.get("started_at")
                        and not state.get("ended_at")
                    ):
                        return "no_error_this_run"
            return "no_active_run"
        message = latch.get("current_message")
        if not message:
            # Recovered-sticky mode — latch exists but current_message is
            # blank. Fall back to the most recent error's message so the
            # state line still tells the user what happened.
            entries = latch.get("errors") or []
            if entries:
                last = entries[-1]
                message = (
                    last.get("message")
                    if isinstance(last, dict)
                    else None
                )
        return str(message or "no_error_this_run")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        latch = self._tracker.get_active_run_latch(self._vacuum_entity_id)
        if not isinstance(latch, dict):
            return {}
        return dict(latch)


class EufyVacuumLastDeviceErrorSensor(_ErrorTrackerSensorBase):
    """Most recent error observed on the device, regardless of run context.

    Persists across restarts. Cleared only by
    ``eufy_vacuum.acknowledge_error`` (scope=``last_device`` or ``both``).
    Useful for catching errors that fire while the vacuum is idle on the
    dock — those don't form an active-run latch but DO update this sensor.
    """

    _attr_icon = "mdi:history"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        *,
        tracker: ErrorTracker,
        vacuum_entity_id: str,
    ) -> None:
        super().__init__(
            tracker=tracker,
            vacuum_entity_id=vacuum_entity_id,
            label="Last Device Error",
            unique_suffix="last_device_error",
        )

    @property
    def native_value(self) -> str:
        latch = self._tracker.get_last_device_latch(self._vacuum_entity_id)
        if not isinstance(latch, dict):
            return "none"
        message = latch.get("message")
        return str(message) if message else "none"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        latch = self._tracker.get_last_device_latch(self._vacuum_entity_id)
        if not isinstance(latch, dict):
            return {}
        return dict(latch)
