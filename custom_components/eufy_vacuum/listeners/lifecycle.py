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
    completion_secondary_satisfied,
    get_adapter_value,
    get_adapter_vocab,
    get_lifecycle_watch_entities,
    is_job_active,
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
                # App-started (external) runs have no dispatched job, so they fall
                # through the per-map internal loop below. Detect + capture them
                # first (open a status="external" slot, or finalize to a pending
                # record when the robot returns home).
                try:
                    if await manager_local.maybe_handle_external_run(
                        vacuum_entity_id=vacuum_entity_id
                    ):
                        any_changes = True
                except Exception:  # pragma: no cover - best-effort external capture
                    _LOGGER.exception(
                        "External-run handling failed for %s", vacuum_entity_id
                    )

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

                    # Arm the "job genuinely started moving" flag — but for a brand
                    # whose active_cleaning_target is NOT a reliable idle sentinel
                    # (Roborock current_room reverts to the DOCK ROOM name when
                    # parked, so evaluate_job_lifecycle reads "active_job_running" the
                    # instant the job exists), additionally require the job-active
                    # binary to be ON before trusting it. Without this a BATCH job
                    # created while the device still shows the previous run's stale
                    # charging + cleared job-active would arm the flag at t=0 and the
                    # completion gate below would finalize it in ~1s (a 0-duration
                    # run). Brands that declare completion.require_job_active_clear are
                    # exactly the ones with the unreliable target; Eufy declares
                    # neither so this is a no-op there. Strict-order has its own
                    # _phase_dispatch_pending guard — this closes the batch gap.
                    # Invariant: a brand that sets require_job_active_clear must also
                    # declare entities.job_active (true for Roborock) — otherwise
                    # is_job_active is always False and the flag would never arm.
                    # A genuine run arms it mid-clean (binary ON) and it persists
                    # True through completion (binary OFF), so finalize still fires.
                    _needs_active_proof = bool(get_adapter_value(
                        vacuum_entity_id, "completion", "require_job_active_clear",
                        fallback=False,
                    ))
                    if lifecycle_state in _ACTIVE_LIFECYCLE_STATES and (
                        not _needs_active_proof or is_job_active(hass, vacuum_entity_id)
                    ):
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

                    # Successful completion: task_status==Completed + secondary
                    # requirement met. The secondary is either the active_target
                    # reading a clear sentinel (Eufy) OR — for brands whose
                    # active_target reverts to the dock room and never sentinels
                    # (Roborock current_room) — the job-active binary clearing,
                    # enforced by the is_job_active guard just below
                    # (completion.require_job_active_clear). has_observed_active_lifecycle
                    # guards against stale pre-run dock states triggering finalization
                    # before the job started moving. vacuum_docked is NOT required —
                    # the vacuum may still be returning when these signals fire, and
                    # requiring docked was stranding active_job records.
                    should_finalize_completed = bool(
                        str(completion_signals.get("task_status", "")).strip().lower()
                        == str(_completion_task_status).strip().lower()
                        and completion_secondary_satisfied(
                            vacuum_entity_id, completion_signals, _clear_sentinels
                        )
                        and active_job.get("has_observed_active_lifecycle", False)
                    )

                    # Recharge-resume guard: a brand may dock + report
                    # task_status=charging MID-job to recharge, then resume. When the
                    # adapter declares a job-active signal (entities.job_active — a
                    # binary sensor that stays ON through the recharge dock and clears
                    # only at the true finish), suppress finalization while it is on so
                    # the resumed half stays the same job. No-op for brands without
                    # entities.job_active (e.g. Eufy). Confirmed on a Roborock S6 trace:
                    # cleaning stayed ON through a 19% recharge dock + resume, off only
                    # at completion (count incremented).
                    if should_finalize_completed and is_job_active(hass, vacuum_entity_id):
                        should_finalize_completed = False

                    # Strict-order dispatch guard: a just-advanced sequenced phase
                    # has NOT been confirmed cleaning yet — the watchdog
                    # (_run_advanced_phase) is still in its settle/dispatch/verify
                    # window. Until it confirms the device started THIS room (which
                    # clears _phase_dispatch_pending), the lingering completion
                    # signals from the room that JUST finished must not finalize the
                    # new phase: a Roborock sits docked+charging between phases —
                    # precisely its completion signal — so without this the prior
                    # room's dock finalizes the next room before it ever starts.
                    # No-op for non-sequenced jobs (the flag is only set on a phase
                    # advance, queue_engine.advance_active_job_phase).
                    if should_finalize_completed and active_job.get("_phase_dispatch_pending"):
                        should_finalize_completed = False

                    if not should_finalize_completed:
                        continue

                    # Sequenced job model: a completed phase advances to the next
                    # phase (re-dispatch) instead of finalizing. Atomic jobs —
                    # every adapter today — return False here and finalize as
                    # before. Each phase finalizes only when it is the last.
                    if await manager_local.maybe_advance_phase(
                        vacuum_entity_id=vacuum_entity_id,
                        map_id=map_id,
                    ):
                        any_changes = True
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
                    except Exception:  # pragma: no cover - best-effort auto-finalize
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
