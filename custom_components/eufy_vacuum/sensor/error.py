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
        translation_key: str,
        unique_suffix: str,
    ) -> None:
        self._tracker = tracker
        self._vacuum_entity_id = vacuum_entity_id
        self._attr_translation_key = translation_key
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
    """Active-run error latch as a clean three-value enum.

    State values
    ~~~~~~~~~~~~
    - ``"none"``      — no error latch for this vacuum (no active run, or
                        active run with no errors yet, or latch cleared after
                        job end).  Use ``sensor.<obj>_active_job`` to tell
                        which sub-case applies.
    - ``"active"``    — an error is currently active (``current_message``
                        is non-empty).
    - ``"recovered"`` — an error fired during the run but the device recovered
                        mid-run; the latch is held until the job ends so the
                        panel can show what happened.  Automatically cleared on
                        ``EVENT_JOB_FINISHED`` (wired in ``sensor/__init__.py``).

    The actual error message and the full latch snapshot live in
    ``extra_state_attributes`` rather than in the state string.  Automations
    should pattern-match on the three-value enum and read ``message`` from
    attributes when they need the text.

    The companion ``binary_sensor.<obj>_active_run_has_error`` tracks only the
    rising/falling edge and does not expose the message — use this sensor when
    you need the message or the recovered state.
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
            translation_key="active_run_error",
            unique_suffix="active_run_error",
        )

    @property
    def native_value(self) -> str:
        latch = self._tracker.get_active_run_latch(self._vacuum_entity_id)
        if not isinstance(latch, dict):
            return "none"
        if latch.get("current_message"):
            return "active"
        # Only "recovered" when at least one error actually fired this run.
        # An empty/initialised latch (no errors list) must not read as recovered.
        if latch.get("errors"):
            return "recovered"
        return "none"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        latch = self._tracker.get_active_run_latch(self._vacuum_entity_id)
        if not isinstance(latch, dict):
            return {}
        attrs = dict(latch)
        # Surface the most recent error message as a top-level ``message``
        # attribute so consumers don't have to dig into the ``errors`` list.
        if not attrs.get("current_message"):
            entries = latch.get("errors") or []
            if entries:
                last = entries[-1]
                if isinstance(last, dict):
                    attrs["message"] = last.get("message")
        else:
            attrs["message"] = attrs["current_message"]
        return attrs


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
            translation_key="last_device_error",
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
