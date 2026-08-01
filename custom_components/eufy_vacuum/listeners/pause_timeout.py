"""Stale-job reaper — a lightweight 1-minute ticker over every managed vacuum's
active job. Two independent reaps, each firing the standard EVENT_JOB_FINISHED —
and, when the involuntarily-ended run left rooms uncleaned, also EVENT_RUN_INCOMPLETE
(mirroring the finalize_learning_job service path) so an automation's
`retry_missed_rooms` trigger fires for a reaped run just as it does for a service
finalize:

1. Paused-timeout: a job paused past its configured timeout is cancelled.
2. Stranded-`started` (FN-1): a dispatched run that ended without hitting its
   brand's completion terminal (power loss, HA restart mid-run, a stuck-then-docked
   run, an app-cancel that never emitted the terminal status) is finalized as
   `interrupted` once it has sat ended-but-unfinalized past a grace window — so it
   becomes a Restore-able record instead of stranding (which would mask a later
   external run and let a later terminal signal mis-attribute the stale slot).

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

from ..const import DATA_RUNTIME, DOMAIN, EVENT_JOB_FINISHED, EVENT_RUN_INCOMPLETE
from ..core.manager import EufyVacuumManager
from ._common import job_finished_event_data, run_incomplete_event_data

_LOGGER = logging.getLogger(__name__)

_PAUSE_TIMEOUT_UNSUBS = "_pause_timeout_unsubs"


def remove(hass: HomeAssistant) -> None:
    """Remove the paused-job timeout watchdog."""
    domain_data = hass.data.get(DOMAIN, {})
    unsubs: list[Callable[[], None]] = domain_data.pop(_PAUSE_TIMEOUT_UNSUBS, [])
    for unsub in unsubs:
        try:
            unsub()
        except Exception:  # pragma: no cover - best-effort teardown
            _LOGGER.exception("Failed to remove pause-timeout listener")


async def _reap_one_slot(
    hass: HomeAssistant,
    manager_local: EufyVacuumManager,
    vacuum_entity_id: str,
    map_id: str,
) -> bool:
    """Run both reaps for one (vacuum, map) slot; return whether anything
    changed. Isolated in its own try/except by the caller (RP-011/RF-07,
    STR-2/GUARD-4) so one slot's exception cannot kill the whole tick."""
    any_changes = False
    # 1) Paused-timeout reap — cancel a job paused past its limit.
    timeout_report = manager_local.get_paused_job_timeout_report(
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id,
    )
    if isinstance(timeout_report, dict):
        result = await manager_local.async_cancel_active_job(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            forced_lifecycle_state=timeout_report["forced_lifecycle_state"],
            forced_lifecycle_message=timeout_report["forced_lifecycle_message"],
            cancel_reason=timeout_report["cancel_reason"],
        )
        if bool(result.get("cancelled")):
            hass.bus.async_fire(
                EVENT_JOB_FINISHED,
                job_finished_event_data(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=map_id,
                    finalize_result=result.get("finalize_result"),
                ),
            )
            # An auto-cancel is involuntary: if it stranded rooms,
            # fire EVENT_RUN_INCOMPLETE too so retry_missed_rooms can act.
            run_incomplete = run_incomplete_event_data(
                vacuum_entity_id=vacuum_entity_id,
                finalize_result=result.get("finalize_result"),
            )
            if run_incomplete is not None:
                hass.bus.async_fire(EVENT_RUN_INCOMPLETE, run_incomplete)
            any_changes = True
            _LOGGER.debug(
                "Auto-cancelled paused job for %s map %s after %s minute timeout",
                vacuum_entity_id,
                map_id,
                timeout_report.get("pause_timeout_minutes"),
            )

    # 2) Stranded-`started` reap — a dispatched run that ended without
    # hitting its brand's completion terminal (FN-1). Independent of the
    # paused check (a stranded run is never paused). poll_* stamps/clears
    # stranded_since and only returns a report once it is past the grace.
    stranded_report = manager_local.poll_stranded_started_job(
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id,
    )
    if isinstance(stranded_report, dict):
        result = await manager_local.async_finalize_stranded_job(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            ended_at=stranded_report.get("stranded_since"),
        )
        if bool(result.get("finalized")):
            hass.bus.async_fire(
                EVENT_JOB_FINISHED,
                job_finished_event_data(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=map_id,
                    finalize_result=result.get("finalize_result"),
                ),
            )
            # A stranded run ended involuntarily: if it left rooms
            # uncleaned, fire EVENT_RUN_INCOMPLETE too (this is the
            # user's "if it strands it is incomplete" case) so
            # retry_missed_rooms can act.
            run_incomplete = run_incomplete_event_data(
                vacuum_entity_id=vacuum_entity_id,
                finalize_result=result.get("finalize_result"),
            )
            if run_incomplete is not None:
                hass.bus.async_fire(EVENT_RUN_INCOMPLETE, run_incomplete)
            any_changes = True
            _LOGGER.info(
                "Auto-finalized STRANDED job for %s map %s as interrupted "
                "(no completion signal since %s)",
                vacuum_entity_id,
                map_id,
                stranded_report.get("stranded_since"),
            )
    return any_changes


def register(hass: HomeAssistant) -> None:
    """Cancel paused jobs that exceed their configured timeout."""
    remove(hass)

    domain_data = hass.data.get(DOMAIN, {})
    manager: EufyVacuumManager | None = domain_data.get(DATA_RUNTIME)
    if manager is None:
        return

    # RP-011/RF-07 (GUARD-4): a mutable box (not a plain closure variable) so
    # both the callback and the spawned _process task, across every future
    # tick, share the SAME in-flight flag.
    _tick_state = {"in_flight": False}

    @callback
    def _handle_pause_timeout_tick(_now) -> None:
        """Check paused jobs on a lightweight timer."""
        manager_local: EufyVacuumManager | None = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager_local is None:
            return
        if _tick_state["in_flight"]:
            # A slow tick (many vacuums/maps, or a blocking reap) must not
            # overlap with the next tick's own pass over the same slots.
            _LOGGER.debug("pause_timeout: previous tick still running — skipping this tick")
            return

        async def _process() -> None:
            _tick_state["in_flight"] = True
            try:
                any_changes = False
                for vacuum_entity_id in manager_local.get_known_vacuum_ids():
                    for map_id in manager_local.get_known_map_ids(vacuum_entity_id):
                        if str(map_id).strip().lower() == "unknown":
                            continue
                        # RP-011/RF-07 (STR-2): one slot's exception must not kill
                        # the whole tick — every later slot would then never be
                        # processed, this tick or any other.
                        try:
                            if await _reap_one_slot(hass, manager_local, vacuum_entity_id, map_id):
                                any_changes = True
                        except Exception:
                            _LOGGER.exception(
                                "pause_timeout: reap failed for %s map %s — "
                                "continuing to the next slot",
                                vacuum_entity_id, map_id,
                            )

                if any_changes:
                    await manager_local.async_save()
            finally:
                _tick_state["in_flight"] = False

        hass.async_create_task(_process())

    unsub = async_track_time_interval(
        hass,
        _handle_pause_timeout_tick,
        timedelta(minutes=1),
    )
    domain_data[_PAUSE_TIMEOUT_UNSUBS] = [unsub]
