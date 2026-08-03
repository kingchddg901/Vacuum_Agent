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
from ..learning.manager import finalize_result_succeeded
from ._common import (
    completed_finalize_signals,
    completion_secondary_satisfied,
    get_adapter_value,
    get_adapter_vocab,
    get_lifecycle_watch_entities,
    is_dock_trigger_edge,
    is_job_active,
    job_finished_event_data,
)

_LOGGER = logging.getLogger(__name__)

_JOB_LIFECYCLE_UNSUBS = "_job_lifecycle_unsubs"
# RP-039/RF-16: mirrors core/manager.py's _background_tasks pattern — every
# spawned _process() task is tracked here and cancelled in remove(hass), which
# previously only cancelled the state-change-event unsub, never the in-flight
# task itself.
_JOB_LIFECYCLE_TASKS = "_job_lifecycle_tasks"

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

    tasks: set = domain_data.pop(_JOB_LIFECYCLE_TASKS, set())
    for task in tasks:
        if not task.done():
            task.cancel()


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

                    # RP-012/RF-31 (A4-AJ-1/TRK-2): resolve a mid-job recharge that
                    # has ENDED first (this tick can observe a charging state that
                    # differs from the tick that started the observed_mid_job_recharge
                    # flag), then evaluate whether a NEW recharge is starting.
                    manager_local.resolve_mid_job_recharge_resumed(
                        vacuum_entity_id=vacuum_entity_id,
                        map_id=map_id,
                    )
                    manager_local.update_active_job_recharge_observation(
                        vacuum_entity_id=vacuum_entity_id,
                        map_id=map_id,
                    )

                    # LIFE-3 (RP-038/RF-30): delegates edge detection to the
                    # SAME is_dock_trigger_edge helper dock_events.py's own
                    # _handle_dock_event uses, instead of hand-rolling a
                    # weaker inline check here. old_state/new_state above are
                    # already raw HA state strings (or None) via getattr on
                    # the event's state objects -- exactly what the helper
                    # expects. No hardcoded Eufy-literal vocabulary fallback
                    # either: dock_events.triggers.last_mop_wash is
                    # adapter-driven only (matches dock/manager.py's own
                    # get_dock_action_status doctrine) -- an adapter that
                    # declares no vocabulary gets no wash detection, rather
                    # than silently inheriting Eufy's "washing"/"washing
                    # mop". Eufy's own adapter DOES declare this trigger set
                    # (adapters/eufy/adapter.py), so live Eufy detection is
                    # unaffected.
                    _adapter_cfg = get_adapter_config(vacuum_entity_id) or {}
                    _dock_status_entity = _adapter_cfg.get("entities", {}).get("dock_status")
                    if _dock_status_entity and entity_id == _dock_status_entity:
                        _wash_triggers = frozenset(
                            str(s).strip().lower()
                            for s in _adapter_cfg.get("dock_events", {})
                                                  .get("triggers", {})
                                                  .get("last_mop_wash", [])
                        )
                        if is_dock_trigger_edge(old_state, new_state, _wash_triggers):
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
                            # TRK-7: start_job is plain in-memory dict bookkeeping today
                            # (confidence-state reset + an _active_job entry) — no disk
                            # I/O. The comment this replaces named
                            # _load_samples_from_disk/_delete_samples_tmp_file as the
                            # reason for executor dispatch; neither exists anywhere in
                            # this codebase (grep-confirmed), and start_job's own body
                            # never touches the filesystem, so a plain synchronous call
                            # is correct — the executor hop was pure overhead.
                            tracker.start_job(
                                vacuum_entity_id=vacuum_entity_id,
                                map_id=str(map_id),
                                rooms=job_rooms,
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
                    if should_finalize_completed and is_job_active(
                        hass, vacuum_entity_id, unavailable_is_active=True
                    ):
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

                    # RP-010/RF-06: a cancel in flight owns finalization for this
                    # job. Its own return-to-base dock can otherwise read as
                    # completion here — the cancel path releases
                    # _phase_dispatch_pending before its terminal-confirm poll
                    # completes, by design, which would let this listener race the
                    # cancel's own finalize.
                    if should_finalize_completed and active_job.get("_cancel_in_flight"):
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
                    finalize_raised = False
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
                        finalize_raised = True
                        _LOGGER.exception(
                            "Failed to auto-finalize job for %s map %s",
                            vacuum_entity_id,
                            map_id,
                        )

                    # RP-002/RF-01: a refusal dict ({"finalized": False, "reason": ...})
                    # is not a success — branch on finalize_result_succeeded, not on
                    # "finalize_result is not None" (a refusal dict is also not None).
                    # On refusal, the ENTRANT THAT ACTUALLY SUCCEEDED (this one, earlier,
                    # or concurrently) owns end_job / mark_active_job_finalized / the
                    # event — running them again here would be exactly A2-LIFE-1's
                    # all-null duplicate event.
                    if finalize_result_succeeded(finalize_result):
                        # RP-012/RF-31 (TRK-1): mark_active_job_finalized now
                        # releases the mapping tracker's hold itself (the
                        # terminal chokepoint every path reaches) -- no separate
                        # call needed here. It also may flush a room_completed
                        # (TRK-4), which fires an HA event and so must run ON
                        # THE LOOP, not from an executor thread (the old
                        # rationale for wrapping this call no longer holds).
                        manager_local.mark_active_job_finalized(
                            vacuum_entity_id=vacuum_entity_id,
                            map_id=map_id,
                            finalize_result=finalize_result,
                        )
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
                    elif finalize_raised:
                        # A genuine error (not a refusal shape) — mark_active_job_finalized
                        # (TRK-1) ends the tracker job too, so the active_job record and
                        # the tracker's hold can never be stranded regardless of the failure.
                        manager_local.mark_active_job_finalized(
                            vacuum_entity_id=vacuum_entity_id,
                            map_id=map_id,
                            finalize_result=None,
                        )
                        any_changes = True
                    else:
                        _LOGGER.debug(
                            "Auto-finalize refused for %s map %s: %s",
                            vacuum_entity_id,
                            map_id,
                            (finalize_result or {}).get("reason"),
                        )

            if any_changes:
                await manager_local.async_save()

        # RP-039/RF-16: track the spawned task so remove(hass) can cancel an
        # in-flight _process() on unload — previously only the state-change-event
        # unsub below was cancelled, leaving this task to keep running (and
        # possibly finalize a job / write manager state) against a torn-down hass.
        _task = hass.async_create_task(_process())
        _tasks: set = hass.data.setdefault(DOMAIN, {}).setdefault(_JOB_LIFECYCLE_TASKS, set())
        _tasks.add(_task)
        _task.add_done_callback(_tasks.discard)

    unsub = async_track_state_change_event(
        hass,
        list(watched_entities),
        _handle_lifecycle_change,
    )

    domain_data[_JOB_LIFECYCLE_UNSUBS] = [unsub]
