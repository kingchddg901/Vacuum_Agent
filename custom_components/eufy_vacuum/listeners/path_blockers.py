"""Path-blocker listeners — react to blocker entity state changes during
active jobs.

Watches every blocker rule's trigger entity across all managed rooms.
When one fires during an active job, builds a runtime path-block report
and applies the job's configured `path_block_action` (event_only,
pause_and_event, cancel_and_event). Re-registers itself whenever room
configuration changes via a manager callback.

Public surface:
    register(hass: HomeAssistant) -> None
    remove(hass: HomeAssistant) -> None
"""

# System invariants that bind in this file. Declared and explained elsewhere
# (docs/dev/00b-invariants.md); `scripts/doc_anchor.py --show <TOKEN>` from here.
# The findings under each are the FAILURES THAT PRODUCED the rule -- history, with
# the packet that OWNS them. They are not a to-do list; see OPEN-FIX-CHECKLIST.
#
# A packet id here is the ledger's ATTRIBUTION, not a verification that the fix
# landed in THIS file. Measured 2026-08-18 (.claude/notes/_audit_closure_claims.py):
# 35 of 60 claims name a packet whose commits -- full git footprint, not just the
# ledger's list -- never touched the file the claim sits in. Two were then read and
# both were still LIVE: DQ-Q-7 (queue_engine) and A5-PP-RP-8 (this pattern, in both
# copies). These blocks were written 2026-08-17 by transcribing the ledger, so they
# inherited its mis-attributions into source -- where prose at the site reads as
# authority. Verify before citing one as closed.
#   IN5TNKMD  `jobs/phase_runner.py#IN5TNKMD`
#       A6-GUARD-2 (closed RP-050): path_blockers spawns unbounded concurrent `_process` tasks; a second blocker event
#              inside the 30s cancel-confirm window double-cancels and the loser deterministically


from __future__ import annotations

import logging
from collections.abc import Callable

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from ..const import (
    DATA_RUNTIME,
    DOMAIN,
    EVENT_JOB_FINISHED,
    EVENT_PATH_BLOCKED,
    EVENT_RUN_INCOMPLETE,
)
from ..core.manager import EufyVacuumManager
from ._common import job_finished_event_data, run_incomplete_event_data

_LOGGER = logging.getLogger(__name__)

_PATH_BLOCKER_UNSUBS = "_path_blocker_unsubs"
_PATH_BLOCKER_ROOM_CALLBACK = "_path_blocker_room_callback"
#: RP-008 (A6-GUARD-2): per-run single-flight for _process — a burst of blocker
#: edges used to spawn one unbounded task per event. One evaluation runs; one
#: re-check is queued behind it; further arrivals coalesce into that re-check.
_PATH_BLOCKER_INFLIGHT = "_path_blocker_inflight"


def remove(hass: HomeAssistant) -> None:
    """Remove runtime path-block listeners and room-update callback."""
    domain_data = hass.data.get(DOMAIN, {})
    manager: EufyVacuumManager | None = domain_data.get(DATA_RUNTIME)

    room_callback = domain_data.pop(_PATH_BLOCKER_ROOM_CALLBACK, None)
    if manager is not None and room_callback is not None:
        try:
            manager.unregister_room_update_callback(room_callback)
        except Exception:  # pragma: no cover - best-effort teardown
            _LOGGER.exception("Failed to unregister path blocker room callback")

    unsubs: list[Callable[[], None]] = domain_data.pop(_PATH_BLOCKER_UNSUBS, [])
    for unsub in unsubs:
        try:
            unsub()
        except Exception:  # pragma: no cover - best-effort teardown
            _LOGGER.exception("Failed to remove path blocker listener")


def register(hass: HomeAssistant) -> None:
    """Watch blocker entities during active jobs and fire path-blocked events."""
    remove(hass)

    domain_data = hass.data.get(DOMAIN, {})
    manager: EufyVacuumManager | None = domain_data.get(DATA_RUNTIME)
    if manager is None:
        return

    watch_map: dict[str, list[tuple[str, str]]] = {}
    for vacuum_entity_id in manager.get_known_vacuum_ids():
        for map_id in manager.get_known_map_ids(vacuum_entity_id):
            if str(map_id).strip().lower() == "unknown":
                continue
            managed_rooms = manager._normalized_managed_rooms_with_automation(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
            )
            for room in managed_rooms.values():
                if not isinstance(room, dict):
                    continue
                for rule in room.get("rules", []):
                    if not isinstance(rule, dict) or not bool(rule.get("enabled", True)):
                        continue
                    if str(rule.get("kind", "")).strip().lower() != "blocker":
                        continue
                    entity_id = str(rule.get("entity_id", "")).strip()
                    if not entity_id:
                        continue
                    targets = watch_map.setdefault(entity_id, [])
                    target = (vacuum_entity_id, str(map_id))
                    if target not in targets:
                        targets.append(target)

    @callback
    def _handle_room_update(*, vacuum_entity_id: str, map_id: str) -> None:
        """Rebuild watchers whenever room automation config changes."""
        register(hass)

    manager.register_room_update_callback(_handle_room_update)
    domain_data[_PATH_BLOCKER_ROOM_CALLBACK] = _handle_room_update

    if not watch_map:
        domain_data[_PATH_BLOCKER_UNSUBS] = []
        return

    @callback
    def _handle_path_blocker_change(event: Event) -> None:
        """Re-evaluate active path accessibility after blocker state changes."""
        entity_id = str(event.data.get("entity_id", "")).strip()
        old_state_obj = event.data.get("old_state")
        new_state_obj = event.data.get("new_state")
        old_state = getattr(old_state_obj, "state", None)
        new_state = getattr(new_state_obj, "state", None)

        if not entity_id or entity_id not in watch_map:
            return
        if new_state_obj is None or old_state == new_state:
            return
        # RP-008 step 3: a transition into or out of a dropout sentinel is not a
        # fact about the world — it must not trigger RULE evaluation (GUARD-1: a
        # dying door-sensor battery cancelled a live run). Still logged so the
        # dropout is diagnosable.
        # anchor: INFJXSM4  indeterminate is not a value - it satisfies no predicate
        _sentinels = {"unavailable", "unknown", "none", ""}
        if (str(old_state).strip().lower() in _sentinels
                or str(new_state).strip().lower() in _sentinels):
            _LOGGER.debug(
                "path_blockers: ignoring %s transition %s -> %s for rule "
                "evaluation (indeterminate side)",
                entity_id, old_state, new_state,
            )
            return

        manager_local: EufyVacuumManager | None = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager_local is None:
            return

        async def _process() -> None:
            any_changes = False
            for vacuum_entity_id, map_id in watch_map.get(entity_id, []):
                active_job = manager_local.get_active_job(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=map_id,
                )
                report = manager_local.get_runtime_path_block_report(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=map_id,
                    trigger_entity_id=entity_id,
                    trigger_entity_state=new_state,
                )
                if not isinstance(report, dict):
                    continue

                path_block_action = str(active_job.get("path_block_action", "event_only")).strip().lower() or "event_only"
                action_taken = "event_only"
                action_result: dict | None = None

                if path_block_action == "pause_and_event":
                    if str(active_job.get("status", "")).strip().lower() == "paused":
                        action_taken = "already_paused"
                    else:
                        action_result = await manager_local.async_pause_active_job(
                            vacuum_entity_id=vacuum_entity_id,
                            map_id=map_id,
                        )
                        action_taken = "paused" if bool((action_result or {}).get("paused")) else "pause_failed"
                elif path_block_action == "cancel_and_event":
                    # RP-008 step 4 (defense in depth): before the IRREVERSIBLE
                    # action, re-check that the triggering rule still matches with
                    # a KNOWN state — the report was computed from a snapshot, and
                    # the sensor may have dropped out (or cleared) since.
                    _still_matches = False
                    for _room in manager_local._normalized_managed_rooms_with_automation(
                        vacuum_entity_id=vacuum_entity_id, map_id=map_id
                    ).values():
                        if not isinstance(_room, dict):
                            continue
                        for _rule in _room.get("rules", []):
                            if (isinstance(_rule, dict)
                                    and str(_rule.get("entity_id", "")).strip() == entity_id
                                    and bool(_rule.get("enabled", True))):
                                _m, _k = manager_local.access_graph._room_rule_matches_known(_rule)
                                if _m and _k:
                                    _still_matches = True
                                    break
                        if _still_matches:
                            break
                    if not _still_matches:
                        _LOGGER.warning(
                            "path_blockers: cancel for %s map %s suppressed — the "
                            "triggering rule on %s no longer matches with a known "
                            "state at action time",
                            vacuum_entity_id, map_id, entity_id,
                        )
                        report["path_block_action"] = path_block_action
                        report["action_taken"] = "cancel_suppressed_recheck"
                        hass.bus.async_fire(EVENT_PATH_BLOCKED, report)
                        any_changes = True
                        continue
                    action_result = await manager_local.async_cancel_active_job(
                        vacuum_entity_id=vacuum_entity_id,
                        map_id=map_id,
                    )
                    action_taken = "cancelled" if bool((action_result or {}).get("cancelled")) else "cancel_failed"
                    if bool((action_result or {}).get("cancelled")):
                        hass.bus.async_fire(
                            EVENT_JOB_FINISHED,
                            job_finished_event_data(
                                vacuum_entity_id=vacuum_entity_id,
                                map_id=map_id,
                                finalize_result=(action_result or {}).get("finalize_result"),
                            ),
                        )
                        # A rule-driven cancel is involuntary: if it stranded rooms,
                        # fire EVENT_RUN_INCOMPLETE too so retry_missed_rooms can act.
                        run_incomplete = run_incomplete_event_data(
                            vacuum_entity_id=vacuum_entity_id,
                            finalize_result=(action_result or {}).get("finalize_result"),
                        )
                        if run_incomplete is not None:
                            hass.bus.async_fire(EVENT_RUN_INCOMPLETE, run_incomplete)

                report["path_block_action"] = path_block_action
                report["action_taken"] = action_taken
                if action_result is not None:
                    report["action_result"] = action_result
                hass.bus.async_fire(EVENT_PATH_BLOCKED, report)
                any_changes = True
                _LOGGER.debug(
                    "Runtime path blocked for %s map %s via %s (%s): %s",
                    vacuum_entity_id,
                    map_id,
                    entity_id,
                    action_taken,
                    report.get("affected_remaining_room_ids"),
                )

            if any_changes:
                await manager_local.async_save()

        # RP-008 (GUARD-2): single concurrent evaluation with a queued re-check.
        inflight = hass.data.setdefault(DOMAIN, {}).setdefault(
            _PATH_BLOCKER_INFLIGHT, {"running": False, "rerun": False}
        )

        async def _process_single_flight() -> None:
            if inflight["running"]:
                inflight["rerun"] = True   # coalesce: one re-check after the current
                return
            inflight["running"] = True
            try:
                await _process()
                while inflight["rerun"]:
                    inflight["rerun"] = False
                    await _process()
            finally:
                inflight["running"] = False

        hass.async_create_task(_process_single_flight())

    unsub = async_track_state_change_event(
        hass,
        list(watch_map.keys()),
        _handle_path_blocker_change,
    )
    domain_data[_PATH_BLOCKER_UNSUBS] = [unsub]
