"""Job-progress ticker — 5-second snapshot refresh during active jobs.

Ticks ``get_job_progress_snapshot`` for every vacuum/map with an active
job. This keeps stall detection and bounds-exit derivation firing during
cleaning periods that have no vacuum-state transitions — e.g. a
bounds-exit wait where the vacuum reports "cleaning" continuously and
the entity-state lifecycle listener never fires.

Without this, ``get_job_progress_snapshot`` would only run when the
dashboard polled it, which meant ``EVENT_STALL_DETECTED`` (fired as a
side effect from inside the snapshot) silently failed for users who
weren't actively looking at the panel. Moving the cadence to the
backend makes stall-driven automations reliable regardless of UI state,
and lets the card drop its bounds-exit polling.

After each tick we fire ``EVENT_JOB_PROGRESS_TICK`` so the dashboard
can refresh its snapshot if it's open. Cost per tick: one method call
and one event per active vacuum/map; negligible.

Public surface:
    register(hass: HomeAssistant) -> None
    remove(hass: HomeAssistant) -> None
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from ..const import DATA_RUNTIME, DOMAIN, EVENT_JOB_PROGRESS_TICK
from ..core.manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)

_JOB_PROGRESS_UNSUBS = "_job_progress_unsubs"


def remove(hass: HomeAssistant) -> None:
    """Tear down the job-progress ticker."""
    domain_data = hass.data.get(DOMAIN, {})
    unsubs: list[Callable[[], None]] = domain_data.pop(_JOB_PROGRESS_UNSUBS, [])
    for unsub in unsubs:
        try:
            unsub()
        except Exception:  # pragma: no cover
            pass


def register(hass: HomeAssistant) -> None:
    """Tick the job-progress snapshot every 5 s while jobs are active."""
    remove(hass)

    domain_data = hass.data.setdefault(DOMAIN, {})
    manager: EufyVacuumManager | None = domain_data.get(DATA_RUNTIME)
    if manager is None:
        return

    @callback
    def _handle_job_progress_tick(_now) -> None:
        for vacuum_entity_id in manager.get_known_vacuum_ids():
            for map_id in manager.get_known_map_ids(vacuum_entity_id):
                map_id_str = str(map_id)
                if map_id_str.strip().lower() == "unknown":
                    continue

                active_job = manager.get_active_job(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=map_id_str,
                )
                if active_job.get("status") not in {"started", "paused"}:
                    continue

                # Lever B: during a CONTIGUOUS run, keep the brand's live current-room/map
                # fresh so the per-room rollover + live fan track the adapter's interval, not
                # the device's slower native map cadence. Strict-order runs (which advance one
                # room per dispatched PHASE via the watchdog, docking between rooms) are
                # excluded — they already get a free refresh on each state flip. No-op unless
                # the adapter declares dispatch.live_room_refresh; per-vacuum rate-limited and
                # local-gated inside the manager helper.
                if not active_job.get("phases"):
                    try:
                        manager.maybe_pulse_live_room_refresh(vacuum_entity_id)
                    except Exception:  # pragma: no cover - never break the tick
                        _LOGGER.exception(
                            "eufy_vacuum: live-room refresh pulse scheduling failed for %s",
                            vacuum_entity_id,
                        )

                try:
                    manager.get_job_progress_snapshot(
                        vacuum_entity_id=vacuum_entity_id,
                        map_id=map_id_str,
                    )
                except Exception:
                    _LOGGER.exception(
                        "eufy_vacuum: job-progress tick failed for %s/%s",
                        vacuum_entity_id,
                        map_id_str,
                    )
                    continue

                hass.bus.async_fire(
                    EVENT_JOB_PROGRESS_TICK,
                    {
                        "vacuum_entity_id": vacuum_entity_id,
                        "map_id": map_id_str,
                    },
                )

    unsub = async_track_time_interval(
        hass,
        _handle_job_progress_tick,
        timedelta(seconds=5),
    )
    domain_data[_JOB_PROGRESS_UNSUBS] = [unsub]
