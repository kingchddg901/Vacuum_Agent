"""Active-job lifecycle sensor — per-(vacuum, map) integration-owned job state.

State values: ``none`` / ``started`` / ``paused`` / ``cancelled`` / ``finalized``

The sensor reflects what the eufy_vacuum integration knows about the current
job, not the device-reported state.  It is the first-class HA representation
of the internal active-job state machine and is the intended input for the
lifecycle state sensor (which will become a pure function of HA entity states
once this sensor and the refined error sensor are wired in).

Update triggers:
- ``ActiveJobTracker.add_update_listener`` — fires on pause, resume, finalize,
  and clear (all internal status transitions the tracker owns).
- ``EVENT_ROOM_STARTED`` — proxy for job start; fired by the manager immediately
  after writing the new active-job record to storage, so the sensor will always
  read a consistent ``started`` status when it reacts.
- ``EVENT_JOB_FINISHED`` — redundant finalization safety-net.
- 5-minute periodic safety-net tick — guards against any write path that does
  not yet fire the tracker callback.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval

from ..const import DOMAIN, EVENT_JOB_FINISHED, EVENT_ROOM_STARTED
from ..entity_helpers import build_vacuum_device_info


class EufyVacuumActiveJobSensor(SensorEntity):
    """Integration-owned job state for one vacuum/map pair.

    State values
    ~~~~~~~~~~~~
    - ``none``      — no active job on record (idle or cleared after finalization)
    - ``started``   — job is actively running
    - ``paused``    — job is paused (vacuum waiting for resume or cancel)
    - ``cancelled`` — job ended via cancel / return_to_base
    - ``finalized`` — job ended normally (completed, interrupted, or failed)

    Attributes carry the full active-job snapshot for consumers that need
    details (job_id, room list, timing, wash/recharge counts, etc.).
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "active_job"
    _attr_icon = "mdi:robot-vacuum"

    def __init__(
        self,
        *,
        manager: Any,
        vacuum_entity_id: str,
        map_id: str,
    ) -> None:
        self._manager = manager
        self._vacuum_entity_id = vacuum_entity_id
        self._map_id = str(map_id)
        object_id = vacuum_entity_id.split(".", 1)[-1]
        unique_suffix = f"active_job_{self._map_id}"
        self._attr_unique_id = (
            f"{vacuum_entity_id.replace('.', '_')}_{unique_suffix}"
        )
        self._attr_suggested_object_id = f"{object_id}_{unique_suffix}"
        self._attr_device_info = build_vacuum_device_info(vacuum_entity_id)
        self._unsub_tracker: Any = None
        self._unsub_room_started: Any = None
        self._unsub_job_finished: Any = None
        self._unsub_safety_net: Any = None

    # ------------------------------------------------------------------
    # HA lifecycle
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Subscribe to all update sources."""
        self._unsub_tracker = self._manager.active_job.add_update_listener(
            self._on_active_job_update
        )
        self._unsub_room_started = self.hass.bus.async_listen(
            EVENT_ROOM_STARTED, self._on_room_started
        )
        self._unsub_job_finished = self.hass.bus.async_listen(
            EVENT_JOB_FINISHED, self._on_job_finished
        )
        self._unsub_safety_net = async_track_time_interval(
            self.hass,
            self._on_safety_net_tick,
            timedelta(minutes=5),
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe cleanly on removal."""
        for attr in (
            "_unsub_tracker",
            "_unsub_room_started",
            "_unsub_job_finished",
            "_unsub_safety_net",
        ):
            unsub = getattr(self, attr, None)
            if unsub is not None:
                try:
                    unsub()
                except Exception:  # pragma: no cover - defensive
                    pass
                setattr(self, attr, None)

    # ------------------------------------------------------------------
    # Update callbacks
    # ------------------------------------------------------------------

    def _on_active_job_update(self, vacuum_entity_id: str, map_id: str) -> None:
        """Receive a tracker callback and schedule a state write on the event loop.

        The tracker may fire from any synchronisation context, so route through
        ``call_soon_threadsafe`` exactly as ``_ErrorTrackerSensorBase`` does.
        """
        if vacuum_entity_id != self._vacuum_entity_id:
            return
        if str(map_id) != self._map_id:
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

    @callback
    def _on_room_started(self, event) -> None:
        """Handle EVENT_ROOM_STARTED — proxy for job start.

        The manager fires this immediately after writing the active-job record
        to storage, so the job status is already ``started`` when this fires.
        """
        data = event.data if isinstance(event.data, dict) else {}
        if str(data.get("vacuum_entity_id", "")) != self._vacuum_entity_id:
            return
        if str(data.get("map_id", "")) != self._map_id:
            return
        try:
            self.async_write_ha_state()
        except Exception:  # pragma: no cover - defensive
            pass

    @callback
    def _on_job_finished(self, event) -> None:
        """Handle EVENT_JOB_FINISHED — safety-net for finalization."""
        data = event.data if isinstance(event.data, dict) else {}
        if str(data.get("vacuum_entity_id", "")) != self._vacuum_entity_id:
            return
        if str(data.get("map_id", "")) != self._map_id:
            return
        try:
            self.async_write_ha_state()
        except Exception:  # pragma: no cover - defensive
            pass

    @callback
    def _on_safety_net_tick(self, _now) -> None:
        """Periodic safety-net — re-reads storage every 5 minutes to stay in sync."""
        try:
            self.async_write_ha_state()
        except Exception:  # pragma: no cover - defensive
            pass

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def native_value(self) -> str:
        """Map internal job status to a clean five-value enum."""
        job = self._manager.get_active_job(
            vacuum_entity_id=self._vacuum_entity_id,
            map_id=self._map_id,
        )
        status = str(job.get("status", "idle")).strip().lower()
        if status == "started":
            return "started"
        if status == "paused":
            return "paused"
        if status == "completed":
            finalize_status = str(
                (job.get("finalize_summary") or {}).get("status", "")
            ).strip().lower()
            return "cancelled" if finalize_status == "cancelled" else "finalized"
        return "none"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Full active-job snapshot for consumers that need details."""
        job = self._manager.get_active_job(
            vacuum_entity_id=self._vacuum_entity_id,
            map_id=self._map_id,
        )
        finalize_summary = job.get("finalize_summary") or {}
        return {
            "job_id": job.get("job_id"),
            "map_id": job.get("map_id"),
            "started_at": job.get("started_at"),
            "finalized_at": job.get("finalized_at"),
            "room_count": job.get("room_count"),
            "queue_room_ids": job.get("queue_room_ids"),
            "completed_room_ids": job.get("completed_room_ids"),
            "current_room_id": job.get("current_room_id"),
            "paused_at": job.get("paused_at"),
            "paused_duration_seconds": job.get("paused_duration_seconds"),
            "battery_start": job.get("battery_start"),
            "mid_job_recharge_count": job.get("observed_mid_job_recharge_count"),
            "mop_wash_count": job.get("observed_mop_wash_count"),
            "finalize_status": finalize_summary.get("status"),
            "used_for_learning": finalize_summary.get("used_for_learning"),
        }
