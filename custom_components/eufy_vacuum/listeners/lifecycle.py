"""Lifecycle listeners — auto-finalize completed jobs.

Watches the vacuum entity + adapter-declared lifecycle entities
(task_status, dock_status, active_cleaning_target, active_map).
On state transitions, evaluates whether an active job has completed
and, if so, fires the finalization path. Also records mid-job
observations (recharge counts, mop-wash observations) and registers
the post-job water amendment for mop jobs.

Public surface:
    register(hass: HomeAssistant) -> None
    remove(hass: HomeAssistant) -> None
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from ..adapters.registry import get_adapter_config
from ..const import DATA_RUNTIME, DOMAIN, EVENT_JOB_FINISHED
from ..core.manager import EufyVacuumManager
from ..core.water_amendment import (
    register_post_job_water_amendment as _register_post_job_water_amendment,
)
from ._common import (
    completed_finalize_signals,
    get_adapter_value,
    get_adapter_vocab,
    get_lifecycle_watch_entities,
    job_finished_event_data,
)

_LOGGER = logging.getLogger(__name__)

_JOB_LIFECYCLE_UNSUBS = "_job_lifecycle_unsubs"

# Lifecycle states that confirm the job has genuinely started moving.
# A job is not eligible for auto-finalization until at least one of these
# has been observed, preventing stale pre-run dock states (e.g. dock_drying)
# from instantly completing the job. Values must match evaluate_job_lifecycle().
_ACTIVE_LIFECYCLE_STATES: set[str] = {
    "active_job_running",  # vacuum is actively cleaning
    "mid_job_service",     # dock is servicing mid-job (wash/empty/recycle)
}

# Generic completion fallbacks. Used by get_adapter_value when the adapter
# registry is absent. The task_status value is the normalized "job done"
# string; the clear sentinels are standard HA empty/unavailable states.
_DEFAULT_COMPLETION_TASK_STATUS = "completed"
_DEFAULT_CLEAR_SENTINELS: frozenset[str] = frozenset(
    {"", "unknown", "unavailable", "none", "null"}
)


def remove(hass: HomeAssistant) -> None:
    """Remove lifecycle listeners."""
    domain_data = hass.data.get(DOMAIN, {})
    unsubs: list[Callable[[], None]] = domain_data.pop(_JOB_LIFECYCLE_UNSUBS, [])

    for unsub in unsubs:
        try:
            unsub()
        except Exception:  # pragma: no cover - best-effort teardown
            _LOGGER.exception("Failed to remove lifecycle listener")


def register(hass: HomeAssistant) -> None:
    """Register listeners that auto-finalize completed jobs."""
    remove(hass)

    domain_data = hass.data.get(DOMAIN, {})
    manager: EufyVacuumManager | None = domain_data.get(DATA_RUNTIME)
    if manager is None:
        return

    watched_entities: set[str] = set()
    for vacuum_entity_id in manager.get_known_vacuum_ids():
        watched_entities.update(get_lifecycle_watch_entities(vacuum_entity_id))

    if not watched_entities:
        domain_data[_JOB_LIFECYCLE_UNSUBS] = []
        return

    @callback
    def _handle_lifecycle_change(event: Event) -> None:
        """Process lifecycle-triggering entity change."""
        entity_id = str(event.data.get("entity_id", ""))
        old_state_obj = event.data.get("old_state")
        new_state_obj = event.data.get("new_state")
        old_state = getattr(old_state_obj, "state", None)
        new_state = getattr(new_state_obj, "state", None)

        manager_local: EufyVacuumManager | None = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager_local is None:
            return

        matched_vacuum_ids: list[str] = []
        for vacuum_entity_id in manager_local.get_known_vacuum_ids():
            if entity_id in get_lifecycle_watch_entities(vacuum_entity_id):
                matched_vacuum_ids.append(vacuum_entity_id)

        if not matched_vacuum_ids:
            return

        async def _process() -> None:
            """Evaluate and auto-finalize any jobs whose lifecycle has ended."""
            any_changes = False

            for vacuum_entity_id in matched_vacuum_ids:
                for map_id in manager_local.get_known_map_ids(vacuum_entity_id):
                    active_job = manager_local.get_active_job(
                        vacuum_entity_id=vacuum_entity_id,
                        map_id=map_id,
                    )

                    if active_job.get("status") not in {"started", "paused"}:
                        continue

                    manager_local.record_active_job_transition(
                        vacuum_entity_id=vacuum_entity_id,
                        map_id=map_id,
                        entity_id=entity_id,
                        from_state=old_state,
                        to_state=new_state,
                    )

                    lifecycle = manager_local.get_lifecycle_state(
                        vacuum_entity_id=vacuum_entity_id,
                        map_id=map_id,
                        # Vocabulary params omitted — manager reads them from the
                        # adapter registry directly, with brand-specific fallbacks.
                    )

                    manager_local.update_active_job_recharge_observation(
                        vacuum_entity_id=vacuum_entity_id,
                        map_id=map_id,
                    )

                    _adapter_cfg = get_adapter_config(vacuum_entity_id) or {}
                    _dock_status_entity = _adapter_cfg.get("entities", {}).get("dock_status")
                    if _dock_status_entity and entity_id == _dock_status_entity:
                        _new_state_n = str(new_state or "").strip().lower()
                        _wash_triggers = frozenset(
                            str(s).strip().lower()
                            for s in _adapter_cfg.get("dock_events", {})
                                                  .get("triggers", {})
                                                  .get("last_mop_wash", [])
                        ) or frozenset({"washing", "washing mop"})
                        if _new_state_n in _wash_triggers:
                            manager_local.update_active_job_mop_wash_observation(
                                vacuum_entity_id=vacuum_entity_id,
                                map_id=map_id,
                            )

                    lifecycle_state = str(lifecycle.get("lifecycle_state", "")).strip().lower()

                    if lifecycle_state in _ACTIVE_LIFECYCLE_STATES:
                        # Delegate the flag + write-back to the manager so it owns the mutation.
                        # Also update the local copy so the completion check below sees it.
                        manager_local.record_active_lifecycle_observed(
                            vacuum_entity_id=vacuum_entity_id,
                            map_id=map_id,
                        )
                        active_job["has_observed_active_lifecycle"] = True
                        any_changes = True
                        tracker = hass.data.get(DOMAIN, {}).get("mapping_tracker")
                        if tracker is not None and vacuum_entity_id not in tracker._active_job:
                            all_rooms = manager_local.get_managed_rooms(
                                vacuum_entity_id=vacuum_entity_id,
                                map_id=str(map_id),
                            ).get("rooms", {})
                            # Only include rooms active in this job so single-room
                            # jobs always use the unconditional single-room path.
                            active_ids = {
                                str(r) for r in active_job.get("queue_room_ids", [])
                            }
                            job_rooms = (
                                {k: v for k, v in all_rooms.items() if k in active_ids}
                                if active_ids else all_rooms
                            )
                            # WHY: start_job is sync and performs disk I/O
                                # (`_load_samples_from_disk` / `_delete_samples_tmp_file`).
                                # Run it on the executor to avoid both the
                                # not-awaitable TypeError and the blocking-I/O warning.
                            await hass.async_add_executor_job(
                                functools.partial(
                                    tracker.start_job,
                                    vacuum_entity_id=vacuum_entity_id,
                                    map_id=str(map_id),
                                    rooms=job_rooms,
                                )
                            )

                    _completion_task_status = get_adapter_value(
                        vacuum_entity_id,
                        "completion", "task_status_value",
                        fallback=_DEFAULT_COMPLETION_TASK_STATUS,
                    )
                    _clear_sentinels = get_adapter_vocab(
                        vacuum_entity_id,
                        "completion", "secondary_clear_sentinels",
                        _DEFAULT_CLEAR_SENTINELS,
                    )

                    completion_signals = completed_finalize_signals(hass, vacuum_entity_id)

                    # Successful completion: task_status==Completed + target cleared.
                    # has_observed_active_lifecycle guards against stale pre-run dock
                    # states (e.g. dock_drying) triggering finalization before the job
                    # actually started moving. vacuum_docked is NOT required here —
                    # the vacuum may still be returning when these two signals fire,
                    # and requiring docked was stranding active_job records.
                    should_finalize_completed = bool(
                        str(completion_signals.get("task_status", "")).strip().lower()
                        == str(_completion_task_status).strip().lower()
                        and str(completion_signals.get("active_target", "")).strip().lower()
                        in _clear_sentinels
                        and active_job.get("has_observed_active_lifecycle", False)
                    )

                    if not should_finalize_completed:
                        continue

                    finalize_result = None
                    try:
                        finalize_result = await manager_local.finalize_learning_for_active_job(
                            vacuum_entity_id=vacuum_entity_id,
                            map_id=map_id,
                            rebuild_stats=True,
                            rebuild_csv=False,
                        )
                        _LOGGER.debug(
                            "Auto-finalized job for %s map %s: %s",
                            vacuum_entity_id,
                            map_id,
                            finalize_result,
                        )
                    except Exception:
                        _LOGGER.exception(
                            "Failed to auto-finalize job for %s map %s",
                            vacuum_entity_id,
                            map_id,
                        )
                    finally:
                        tracker = hass.data.get(DOMAIN, {}).get("mapping_tracker")
                        if tracker is not None:
                            # WHY: end_job is sync and performs disk I/O
                            # (update_room_bounds, _append_raw_samples,
                            # _load_map_data). Run on executor.
                            await hass.async_add_executor_job(
                                functools.partial(
                                    tracker.end_job,
                                    vacuum_entity_id=vacuum_entity_id,
                                )
                            )

                    # Always clear the active_job record so it can never be stranded
                    # as status:started regardless of whether finalization succeeded.
                    # Delegates ownership of finalization write-back to the manager.
                    manager_local.mark_active_job_finalized(
                        vacuum_entity_id=vacuum_entity_id,
                        map_id=map_id,
                        finalize_result=finalize_result,
                    )
                    if finalize_result is not None:
                        hass.bus.async_fire(
                            EVENT_JOB_FINISHED,
                            job_finished_event_data(
                                vacuum_entity_id=vacuum_entity_id,
                                map_id=map_id,
                                finalize_result=finalize_result,
                            ),
                        )
                        # Register post-job water amendment for mop jobs.
                        # Some docks wash the mop ~2s after docking, after finalization.
                        _completed = finalize_result.get("completed_job") or {}
                        _job_path = finalize_result.get("job_path")
                        _job_id = finalize_result.get("job_id")
                        _has_mop = any(
                            "mop" in str(r.get("clean_mode", "")).lower()
                            for r in _completed.get("resolved_rooms", [])
                            if isinstance(r, dict)
                        )
                        _amendment_enabled = get_adapter_value(
                            vacuum_entity_id,
                            "post_job_wash_amendment", "enabled",
                            fallback=True,  # amendment: enabled by default
                        )
                        if _has_mop and _job_path and _job_id and _amendment_enabled:
                            _water = _completed.get("water") or {}
                            _debounce = get_adapter_value(
                                vacuum_entity_id,
                                "post_job_wash_amendment", "debounce_seconds",
                                fallback=60.0,  # seconds; adapter config is authoritative
                            )
                            _timeout = get_adapter_value(
                                vacuum_entity_id,
                                "post_job_wash_amendment", "timeout_seconds",
                                fallback=180,  # seconds; adapter config is authoritative
                            )
                            _register_post_job_water_amendment(
                                hass,
                                vacuum_entity_id=vacuum_entity_id,
                                job_id=_job_id,
                                job_path=_job_path,
                                water_start_percent=float(
                                    _water.get("station_clean_water_percent") or 0
                                ),
                                mop_wash_count_at_finalization=int(
                                    _water.get("actual_mop_wash_count") or 0
                                ),
                                debounce_seconds=_debounce,
                                timeout_seconds=_timeout,
                            )
                    any_changes = True

            if any_changes:
                await manager_local.async_save()

        hass.async_create_task(_process())

    unsub = async_track_state_change_event(
        hass,
        list(watched_entities),
        _handle_lifecycle_change,
    )

    domain_data[_JOB_LIFECYCLE_UNSUBS] = [unsub]
