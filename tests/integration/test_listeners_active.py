"""Tests for the active (job-driving) branches of the listener modules.

The existing listener tests cover registration + no-op ticks. These cover the
real work each listener does when a job IS active: pause-timeout auto-cancel,
job-progress snapshot ticking, path-blocker actions, and lifecycle
auto-finalization. Driven with a mock manager wired at DATA_RUNTIME plus timer
firing (async_fire_time_changed) / state-change events.

Coverage targets (high-priority: state-machine branches, user-visible behavior)
--------------------------------------------------------------------------------
[PT-1]  pause_timeout: elapsed report → cancel + EVENT_JOB_FINISHED + save.
[PT-2]  pause_timeout: no report → no cancel.
[PT-3]  pause_timeout: cancel returns not-cancelled → no event, no save.
[PT-4]  pause_timeout: auto-cancel that stranded rooms → also EVENT_RUN_INCOMPLETE.
[PT-5]  pause_timeout: auto-cancel with no missed rooms → JOB_FINISHED only.
[ST-1]  pause_timeout: stranded-run reaper that stranded rooms → JOB_FINISHED + RUN_INCOMPLETE.
[JP-1]  job_progress: active job → snapshot + EVENT_JOB_PROGRESS_TICK.
[JP-2]  job_progress: inactive status → skipped.
[JP-3]  job_progress: snapshot raises → swallowed, no event.
[PB-1]  path_blockers: pause_and_event → pause + EVENT_PATH_BLOCKED.
[PB-2]  path_blockers: cancel_and_event → cancel + JOB_FINISHED + PATH_BLOCKED.
[PB-3]  path_blockers: event_only → just EVENT_PATH_BLOCKED.
[PB-4]  path_blockers: pause_and_event + already-paused job → action_taken=already_paused, no pause call.
[PB-5]  path_blockers: cancel_and_event + cancel returns not-cancelled → action_taken=cancel_failed, no JOB_FINISHED.
[PB-6]  path_blockers: cancel_and_event that stranded rooms → also EVENT_RUN_INCOMPLETE.
[LC-1]  lifecycle: completion signals met → finalize + JOB_FINISHED + save.
[LC-2]  lifecycle: signals not met → observed recorded, no finalize/event.
[LC-3]  lifecycle: finalized MOP job → post-job water amendment registered.
[LC-4]  lifecycle: batch instant-complete fix — a require_job_active_clear brand
        (Roborock) does NOT arm has_observed (so can't finalize) while the
        job-active binary is OFF at the dock, even with active_job_running + stale
        completion signals.
[LC-5]  lifecycle: the same brand DOES arm has_observed once the job-active binary
        is ON (the dispatch took) — a genuine batch run stays finalize-eligible.
[LC-6]  lifecycle: mid-job recharge guard — a require_job_active_clear brand reporting
        the completion task_status while the job-active binary is still ON (recharge
        dock) is NOT finalized; once the binary clears (true finish) it finalizes.
[LC-7]  lifecycle: on finalize, the finally block commits the mapping tracker's job on
        the executor (tracker.end_job) so in-job position samples reach room bounds.
[LC-8]  lifecycle: dock_status entering a mop-wash trigger state during an active job
        routes a mid-job mop-wash observation to the manager.
[LIFE-3] lifecycle: wash detector delegates to the shared edge helper -- old_state=None
        (first sighting / HA restart) is not an edge; an adapter declaring no
        dock_events.triggers.last_mop_wash gets no detection at all (no hardcoded
        Eufy-literal fallback).
[LC-9]  lifecycle: recharge guard treats an 'unavailable' job-active binary as still
        active — a cloud blip mid-recharge does NOT finalize (avoids a truncated sample).
[LC-10] lifecycle: PARITY — recharge-end driven through the real listener + real
        manager/ActiveJobTracker matches the direct-call contract (AJI-13).
"""

from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

import homeassistant.util.dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.const import (
    DATA_RUNTIME,
    DOMAIN,
    EVENT_JOB_FINISHED,
    EVENT_JOB_PROGRESS_TICK,
    EVENT_PATH_BLOCKED,
    EVENT_RUN_INCOMPLETE,
)
from custom_components.eufy_vacuum.listeners import (
    job_progress,
    lifecycle,
    path_blockers,
    pause_timeout,
)


_VAC = "vacuum.alfred"
_MAP = "1"


def _mgr(hass):
    """Wire a fresh mock manager at DATA_RUNTIME with the common defaults."""
    m = MagicMock()
    m.async_save = AsyncMock()
    m.get_known_vacuum_ids.return_value = [_VAC]
    m.get_known_map_ids.return_value = [_MAP]
    # Atomic jobs never advance a phase — the completion hook awaits this and
    # finalizes when it returns False.
    m.maybe_advance_phase = AsyncMock(return_value=False)
    # Lifecycle probes external/app-started runs before internal job finalization.
    # Most tests in this file exercise internal jobs, so keep that branch inert.
    m.maybe_handle_external_run = AsyncMock(return_value=False)
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = m
    return m


def _collect(hass, event_type):
    events = []
    hass.bus.async_listen(event_type, lambda e: events.append(e))
    return events


# ---------------------------------------------------------------------------
# pause_timeout
# ---------------------------------------------------------------------------

async def test_pause_timeout_cancels(hass):
    """[PT-1]"""
    m = _mgr(hass)
    m.get_paused_job_timeout_report.return_value = {
        "forced_lifecycle_state": "cancelled", "forced_lifecycle_message": "Paused too long",
        "cancel_reason": "pause_timeout", "pause_timeout_minutes": 30}
    m.async_cancel_active_job = AsyncMock(return_value={
        "cancelled": True, "finalize_result": {"job_id": "j1"}})
    finished = _collect(hass, EVENT_JOB_FINISHED)
    pause_timeout.register(hass)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1, seconds=5))
    await hass.async_block_till_done()
    pause_timeout.remove(hass)
    assert len(finished) == 1
    m.async_cancel_active_job.assert_awaited_once()
    m.async_save.assert_awaited()


async def test_pause_timeout_no_report(hass):
    """[PT-2]"""
    m = _mgr(hass)
    m.get_paused_job_timeout_report.return_value = None
    m.async_cancel_active_job = AsyncMock()
    pause_timeout.register(hass)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1, seconds=5))
    await hass.async_block_till_done()
    pause_timeout.remove(hass)
    m.async_cancel_active_job.assert_not_awaited()


async def test_pause_timeout_cancel_fails(hass):
    """[PT-3]"""
    m = _mgr(hass)
    m.get_paused_job_timeout_report.return_value = {
        "forced_lifecycle_state": "cancelled", "forced_lifecycle_message": "x",
        "cancel_reason": "pause_timeout", "pause_timeout_minutes": 30}
    m.async_cancel_active_job = AsyncMock(return_value={"cancelled": False})
    finished = _collect(hass, EVENT_JOB_FINISHED)
    pause_timeout.register(hass)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1, seconds=5))
    await hass.async_block_till_done()
    pause_timeout.remove(hass)
    assert finished == []
    m.async_save.assert_not_awaited()


_INCOMPLETE_LOG = {
    "job_id": "j1",
    "outcome_status": "cancelled",
    "missed_room_ids": [2, 3],
    "missed_rooms": [
        {"room_id": 2, "name": "Kitchen"},
        {"room_id": 3, "name": "Den"},
    ],
}


async def test_pause_timeout_fires_run_incomplete(hass):
    """[PT-4] An involuntary auto-cancel that stranded rooms fires EVENT_RUN_INCOMPLETE
    (payload mirrors the finalize_learning_job service path) in addition to
    EVENT_JOB_FINISHED, so an automation's retry_missed_rooms trigger fires."""
    m = _mgr(hass)
    m.get_paused_job_timeout_report.return_value = {
        "forced_lifecycle_state": "pause_timeout_cancelled",
        "forced_lifecycle_message": "Paused too long",
        "cancel_reason": "pause_timeout", "pause_timeout_minutes": 30}
    m.async_cancel_active_job = AsyncMock(return_value={
        "cancelled": True,
        "finalize_result": {"job_id": "j1", "incomplete_run_log": _INCOMPLETE_LOG}})
    finished = _collect(hass, EVENT_JOB_FINISHED)
    incomplete = _collect(hass, EVENT_RUN_INCOMPLETE)
    pause_timeout.register(hass)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1, seconds=5))
    await hass.async_block_till_done()
    pause_timeout.remove(hass)
    assert len(finished) == 1
    assert len(incomplete) == 1
    data = incomplete[0].data
    assert data["vacuum_entity_id"] == _VAC
    assert data["job_id"] == "j1"
    assert data["outcome_status"] == "cancelled"
    assert data["missed_room_ids"] == [2, 3]
    assert data["missed_rooms"] == _INCOMPLETE_LOG["missed_rooms"]
    # Mirrors the service-path payload: no map_id key.
    assert "map_id" not in data


async def test_pause_timeout_no_missed_rooms_no_run_incomplete(hass):
    """[PT-5] An auto-cancel with no stranded rooms fires only EVENT_JOB_FINISHED —
    no incomplete_run_log means no EVENT_RUN_INCOMPLETE."""
    m = _mgr(hass)
    m.get_paused_job_timeout_report.return_value = {
        "forced_lifecycle_state": "pause_timeout_cancelled",
        "forced_lifecycle_message": "Paused too long",
        "cancel_reason": "pause_timeout", "pause_timeout_minutes": 30}
    m.async_cancel_active_job = AsyncMock(return_value={
        "cancelled": True, "finalize_result": {"job_id": "j1"}})
    finished = _collect(hass, EVENT_JOB_FINISHED)
    incomplete = _collect(hass, EVENT_RUN_INCOMPLETE)
    pause_timeout.register(hass)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1, seconds=5))
    await hass.async_block_till_done()
    pause_timeout.remove(hass)
    assert len(finished) == 1
    assert incomplete == []


async def test_stranded_reaper_fires_run_incomplete(hass):
    """[ST-1] The stranded-run reaper finalizing an interrupted run that stranded
    rooms fires EVENT_JOB_FINISHED + EVENT_RUN_INCOMPLETE (the user's 'if it
    strands it is incomplete' case)."""
    m = _mgr(hass)
    # No paused job — exercise only the stranded branch.
    m.get_paused_job_timeout_report.return_value = None
    m.poll_stranded_started_job.return_value = {
        "stranded_since": "2026-01-01T09:00:00+00:00"}
    m.async_finalize_stranded_job = AsyncMock(return_value={
        "finalized": True,
        "finalize_result": {"job_id": "j9", "incomplete_run_log": {
            "job_id": "j9", "outcome_status": "interrupted",
            "missed_room_ids": [5],
            "missed_rooms": [{"room_id": 5, "name": "Hall"}]}}})
    finished = _collect(hass, EVENT_JOB_FINISHED)
    incomplete = _collect(hass, EVENT_RUN_INCOMPLETE)
    pause_timeout.register(hass)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1, seconds=5))
    await hass.async_block_till_done()
    pause_timeout.remove(hass)
    m.async_finalize_stranded_job.assert_awaited_once()
    assert len(finished) == 1
    assert len(incomplete) == 1
    data = incomplete[0].data
    assert data["vacuum_entity_id"] == _VAC
    assert data["job_id"] == "j9"
    assert data["outcome_status"] == "interrupted"
    assert data["missed_room_ids"] == [5]


# ---------------------------------------------------------------------------
# job_progress
# ---------------------------------------------------------------------------

async def test_job_progress_ticks(hass):
    """[JP-1]"""
    m = _mgr(hass)
    m.get_active_job.return_value = {"status": "started"}
    m.get_job_progress_snapshot.return_value = {}
    ticks = _collect(hass, EVENT_JOB_PROGRESS_TICK)
    job_progress.register(hass)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done()
    job_progress.remove(hass)
    assert len(ticks) == 1
    m.get_job_progress_snapshot.assert_called_once()


async def test_job_progress_skips_inactive(hass):
    """[JP-2]"""
    m = _mgr(hass)
    m.get_active_job.return_value = {"status": "idle"}
    ticks = _collect(hass, EVENT_JOB_PROGRESS_TICK)
    job_progress.register(hass)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done()
    job_progress.remove(hass)
    assert ticks == []
    m.get_job_progress_snapshot.assert_not_called()


async def test_job_progress_snapshot_raises(hass):
    """[JP-3] snapshot exception is swallowed; no tick event."""
    m = _mgr(hass)
    m.get_active_job.return_value = {"status": "started"}
    m.get_job_progress_snapshot.side_effect = RuntimeError("boom")
    ticks = _collect(hass, EVENT_JOB_PROGRESS_TICK)
    job_progress.register(hass)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done()
    job_progress.remove(hass)
    assert ticks == []


# ---------------------------------------------------------------------------
# path_blockers
# ---------------------------------------------------------------------------

def _wire_path_blocker(hass, *, path_block_action, job_status="started"):
    m = _mgr(hass)
    m._normalized_managed_rooms_with_automation.return_value = {
        "1": {"rules": [{"kind": "blocker", "enabled": True,
                         "entity_id": "binary_sensor.win"}]}}
    m.get_active_job.return_value = {
        "path_block_action": path_block_action, "status": job_status}
    m.get_runtime_path_block_report.return_value = {"affected_remaining_room_ids": [2]}
    # RP-008 step 4: the cancel path re-checks the triggering rule with a KNOWN
    # state before acting. These tests drive binary_sensor.win to a real "on",
    # so the production evaluator would return (matched=True, known=True) —
    # model exactly that (a bare MagicMock unpacks as an empty iterator).
    m.access_graph._room_rule_matches_known.return_value = (True, True)
    return m


async def test_path_blocker_pause(hass):
    """[PB-1]"""
    m = _wire_path_blocker(hass, path_block_action="pause_and_event")
    m.async_pause_active_job = AsyncMock(return_value={"paused": True})
    blocked = _collect(hass, EVENT_PATH_BLOCKED)
    hass.states.async_set("binary_sensor.win", "off")
    path_blockers.register(hass)
    hass.states.async_set("binary_sensor.win", "on")
    await hass.async_block_till_done()
    path_blockers.remove(hass)
    assert len(blocked) == 1
    assert blocked[0].data["action_taken"] == "paused"
    m.async_pause_active_job.assert_awaited_once()
    m.async_save.assert_awaited()


async def test_path_blocker_cancel(hass):
    """[PB-2]"""
    m = _wire_path_blocker(hass, path_block_action="cancel_and_event")
    m.async_cancel_active_job = AsyncMock(return_value={
        "cancelled": True, "finalize_result": {"job_id": "j1"}})
    blocked = _collect(hass, EVENT_PATH_BLOCKED)
    finished = _collect(hass, EVENT_JOB_FINISHED)
    hass.states.async_set("binary_sensor.win", "off")
    path_blockers.register(hass)
    hass.states.async_set("binary_sensor.win", "on")
    await hass.async_block_till_done()
    path_blockers.remove(hass)
    assert blocked[0].data["action_taken"] == "cancelled"
    assert len(finished) == 1
    m.async_cancel_active_job.assert_awaited_once()


async def test_path_blocker_event_only(hass):
    """[PB-3]"""
    m = _wire_path_blocker(hass, path_block_action="event_only")
    blocked = _collect(hass, EVENT_PATH_BLOCKED)
    hass.states.async_set("binary_sensor.win", "off")
    path_blockers.register(hass)
    hass.states.async_set("binary_sensor.win", "on")
    await hass.async_block_till_done()
    path_blockers.remove(hass)
    assert blocked[0].data["action_taken"] == "event_only"


async def test_path_blocker_pause_already_paused(hass):
    """[PB-4] pause_and_event on an already-paused job short-circuits.

    Protects the idempotent path-block contract (path_blockers.py:138-139):
    when the active job is already 'paused', the listener reports
    action_taken='already_paused' on EVENT_PATH_BLOCKED and does NOT issue a
    redundant async_pause_active_job call.
    """
    m = _wire_path_blocker(
        hass, path_block_action="pause_and_event", job_status="paused")
    m.async_pause_active_job = AsyncMock(return_value={"paused": True})
    blocked = _collect(hass, EVENT_PATH_BLOCKED)
    hass.states.async_set("binary_sensor.win", "off")
    path_blockers.register(hass)
    hass.states.async_set("binary_sensor.win", "on")
    await hass.async_block_till_done()
    path_blockers.remove(hass)
    assert len(blocked) == 1
    assert blocked[0].data["action_taken"] == "already_paused"
    # no redundant pause issued, and no action_result attached for the no-op
    m.async_pause_active_job.assert_not_awaited()
    assert "action_result" not in blocked[0].data


async def test_path_blocker_cancel_fails(hass):
    """[PB-5] cancel_and_event when cancel reports not-cancelled.

    Protects the cancel-failure outcome contract (path_blockers.py:151-162):
    when async_cancel_active_job returns {'cancelled': False}, the listener
    reports action_taken='cancel_failed' on EVENT_PATH_BLOCKED and does NOT
    fire EVENT_JOB_FINISHED (mirrors the [PT-3] pause-timeout failure path).
    """
    m = _wire_path_blocker(hass, path_block_action="cancel_and_event")
    m.async_cancel_active_job = AsyncMock(return_value={"cancelled": False})
    blocked = _collect(hass, EVENT_PATH_BLOCKED)
    finished = _collect(hass, EVENT_JOB_FINISHED)
    hass.states.async_set("binary_sensor.win", "off")
    path_blockers.register(hass)
    hass.states.async_set("binary_sensor.win", "on")
    await hass.async_block_till_done()
    path_blockers.remove(hass)
    assert len(blocked) == 1
    assert blocked[0].data["action_taken"] == "cancel_failed"
    assert finished == []
    m.async_cancel_active_job.assert_awaited_once()


async def test_path_blocker_cancel_fires_run_incomplete(hass):
    """[PB-6] A rule-driven cancel_and_event that stranded rooms fires
    EVENT_RUN_INCOMPLETE alongside EVENT_JOB_FINISHED + EVENT_PATH_BLOCKED."""
    m = _wire_path_blocker(hass, path_block_action="cancel_and_event")
    m.async_cancel_active_job = AsyncMock(return_value={
        "cancelled": True,
        "finalize_result": {"job_id": "j1", "incomplete_run_log": {
            "job_id": "j1", "outcome_status": "cancelled",
            "missed_room_ids": [2],
            "missed_rooms": [{"room_id": 2, "name": "Kitchen"}]}}})
    blocked = _collect(hass, EVENT_PATH_BLOCKED)
    finished = _collect(hass, EVENT_JOB_FINISHED)
    incomplete = _collect(hass, EVENT_RUN_INCOMPLETE)
    hass.states.async_set("binary_sensor.win", "off")
    path_blockers.register(hass)
    hass.states.async_set("binary_sensor.win", "on")
    await hass.async_block_till_done()
    path_blockers.remove(hass)
    assert blocked[0].data["action_taken"] == "cancelled"
    assert len(finished) == 1
    assert len(incomplete) == 1
    data = incomplete[0].data
    assert data["vacuum_entity_id"] == _VAC
    assert data["outcome_status"] == "cancelled"
    assert data["missed_room_ids"] == [2]


# ---------------------------------------------------------------------------
# lifecycle auto-finalization
# ---------------------------------------------------------------------------

_LC_ADAPTER = {
    "adapter_id": "t", "source": "t",
    "entities": {
        "task_status": "sensor.alfred_task",
        "dock_status": "sensor.alfred_dock",
        "active_cleaning_target": "sensor.alfred_target",
        "active_map": "sensor.alfred_map",
    },
    # LIFE-3 (RP-038): the inline wash detector is adapter-driven only, no
    # hardcoded vocabulary fallback -- declared explicitly here (mirrors
    # Eufy's real adapter.py) so [LC-8] keeps validating real routing
    # behavior via declaration instead of an implicit brand fallback.
    "dock_events": {
        "triggers": {"last_mop_wash": ["washing", "washing mop"]},
    },
}


def _wire_lifecycle(hass):
    register_adapter_config(_VAC, _LC_ADAPTER)
    m = _mgr(hass)
    m.get_active_job.return_value = {
        "status": "started", "has_observed_active_lifecycle": True,
        "queue_room_ids": []}
    m.get_lifecycle_state.return_value = {"lifecycle_state": "active_job_running"}
    m.get_managed_rooms.return_value = {"rooms": {}}
    return m


async def test_lifecycle_finalizes(hass):
    """[LC-1] completion signals met → finalize + JOB_FINISHED + save."""
    m = _wire_lifecycle(hass)
    m.finalize_learning_for_active_job = AsyncMock(return_value={
        "job_id": "j1", "job_path": None,
        "completed_job": {"resolved_rooms": [{"clean_mode": "vacuum"}]}})
    finished = _collect(hass, EVENT_JOB_FINISHED)
    # pre-run states: target already cleared, only task_status not yet complete,
    # so a single task change is the lone completion trigger (one _process pass).
    hass.states.async_set(_VAC, "cleaning")
    hass.states.async_set("sensor.alfred_task", "cleaning")
    hass.states.async_set("sensor.alfred_target", "")
    hass.states.async_set("sensor.alfred_dock", "idle")
    hass.states.async_set("sensor.alfred_map", "6")
    lifecycle.register(hass)
    # single transition into completion: task flips to completed
    hass.states.async_set("sensor.alfred_task", "completed")
    await hass.async_block_till_done()
    lifecycle.remove(hass)
    assert len(finished) == 1
    m.finalize_learning_for_active_job.assert_awaited()
    m.mark_active_job_finalized.assert_called()
    m.async_save.assert_awaited()


async def test_lifecycle_refusal_fires_no_event(hass):
    """[LC-10] RP-002/RF-01. A refusal dict ({"finalized": False, "reason": ...}) is
    NOT a success -- it must not fire EVENT_JOB_FINISHED, mark the slot finalized, or
    run the mapping tracker's end_job (the pass that actually succeeded owns those).
    Before RP-002, "finalize_result is not None" treated a refusal exactly like a
    success -- A2-LIFE-1's all-null duplicate event."""
    m = _wire_lifecycle(hass)
    m.finalize_learning_for_active_job = AsyncMock(return_value={
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "finalized": False, "reason": "already_finalized"})
    tracker = MagicMock()
    hass.data[DOMAIN]["mapping_tracker"] = tracker
    finished = _collect(hass, EVENT_JOB_FINISHED)
    hass.states.async_set(_VAC, "cleaning")
    hass.states.async_set("sensor.alfred_task", "cleaning")
    hass.states.async_set("sensor.alfred_target", "")
    hass.states.async_set("sensor.alfred_dock", "idle")
    hass.states.async_set("sensor.alfred_map", "6")
    lifecycle.register(hass)
    hass.states.async_set("sensor.alfred_task", "completed")
    await hass.async_block_till_done()
    lifecycle.remove(hass)
    assert finished == [], "a refusal fired EVENT_JOB_FINISHED"
    m.mark_active_job_finalized.assert_not_called()
    tracker.end_job.assert_not_called()


async def test_lifecycle_suppressed_during_cancel(hass):
    """[LC-11] RP-010/RF-06 (CAN-3). A cancel's own return-to-base dock must not
    read as job completion here -- the completion gate suppresses when
    _cancel_in_flight is set, so this listener never races the cancel path's
    own finalize (which owns finalization for a cancelling job)."""
    m = _wire_lifecycle(hass)
    m.get_active_job.return_value = {
        "status": "started", "has_observed_active_lifecycle": True,
        "queue_room_ids": [], "_cancel_in_flight": True,
    }
    m.finalize_learning_for_active_job = AsyncMock()
    finished = _collect(hass, EVENT_JOB_FINISHED)
    hass.states.async_set(_VAC, "cleaning")
    hass.states.async_set("sensor.alfred_task", "cleaning")
    hass.states.async_set("sensor.alfred_target", "")
    hass.states.async_set("sensor.alfred_dock", "idle")
    hass.states.async_set("sensor.alfred_map", "6")
    lifecycle.register(hass)
    hass.states.async_set("sensor.alfred_task", "completed")
    await hass.async_block_till_done()
    lifecycle.remove(hass)
    assert finished == []
    m.finalize_learning_for_active_job.assert_not_awaited()


async def test_lifecycle_no_finalize_when_incomplete(hass):
    """[LC-2] active lifecycle observed but completion not met → no finalize."""
    m = _wire_lifecycle(hass)
    m.finalize_learning_for_active_job = AsyncMock()
    finished = _collect(hass, EVENT_JOB_FINISHED)
    hass.states.async_set(_VAC, "cleaning")
    hass.states.async_set("sensor.alfred_task", "cleaning")
    hass.states.async_set("sensor.alfred_target", "kitchen")
    hass.states.async_set("sensor.alfred_dock", "idle")
    hass.states.async_set("sensor.alfred_map", "6")
    lifecycle.register(hass)
    # a watched entity changes but the job is still running (not completed)
    hass.states.async_set("sensor.alfred_dock", "washing")
    await hass.async_block_till_done()
    lifecycle.remove(hass)
    assert finished == []
    m.finalize_learning_for_active_job.assert_not_awaited()
    m.record_active_lifecycle_observed.assert_called()


_LC_AMENDMENT_ADAPTER = {
    "adapter_id": "t", "source": "t",
    "entities": {
        "task_status": "sensor.alfred_task",
        "dock_status": "sensor.alfred_dock",
        "active_cleaning_target": "sensor.alfred_target",
        "active_map": "sensor.alfred_map",
    },
    # Required by water_amendment.py:96-107 — without trigger_states/commit_state,
    # register_post_job_water_amendment discards the job_id and the observable
    # effect ("j1" in _water_amendment_jobs) never appears.
    "post_job_wash_amendment": {
        "trigger_states": ["washing"],
        "commit_state": "drying",
    },
}


async def test_lifecycle_registers_water_amendment_for_mop_job(hass, tmp_path):
    """[LC-3] finalized MOP job → post-job water amendment registered.

    Mirrors [LC-1] but takes the POSITIVE branch of the gate at lifecycle.py:319
    (_has_mop and _job_path and _job_id and _amendment_enabled): resolved_rooms
    declares clean_mode="mop" and finalize returns a real job_path, so the
    listener calls _register_post_job_water_amendment. Observable surface is the
    same one [WA-2] asserts: the job_id lands in DOMAIN["_water_amendment_jobs"].
    """
    register_adapter_config(_VAC, _LC_AMENDMENT_ADAPTER)
    m = _mgr(hass)
    m.get_active_job.return_value = {
        "status": "started", "has_observed_active_lifecycle": True,
        "queue_room_ids": []}
    m.get_lifecycle_state.return_value = {"lifecycle_state": "active_job_running"}
    m.get_managed_rooms.return_value = {"rooms": {}}
    # real completed-job file on disk (mirrors _write_job in test_core_water_amendment)
    job = {"job_id": "j1", "water": {"station_clean_water_percent": 80.0,
                                     "actual_mop_wash_count": 0}}
    path = tmp_path / "job_j1.json"
    path.write_text(json.dumps(job), encoding="utf-8")
    m.finalize_learning_for_active_job = AsyncMock(return_value={
        "job_id": "j1", "job_path": str(path),
        "completed_job": {"resolved_rooms": [{"clean_mode": "mop"}],
                          "water": {"station_clean_water_percent": 80.0,
                                    "actual_mop_wash_count": 0}}})
    finished = _collect(hass, EVENT_JOB_FINISHED)
    # pre-run states identical to [LC-1]: target cleared, task not yet complete.
    hass.states.async_set(_VAC, "cleaning")
    hass.states.async_set("sensor.alfred_task", "cleaning")
    hass.states.async_set("sensor.alfred_target", "")
    hass.states.async_set("sensor.alfred_dock", "idle")
    hass.states.async_set("sensor.alfred_map", "6")
    lifecycle.register(hass)
    # single completion transition: task flips to completed → finalize + amendment
    hass.states.async_set("sensor.alfred_task", "completed")
    await hass.async_block_till_done()
    lifecycle.remove(hass)
    assert len(finished) == 1
    m.finalize_learning_for_active_job.assert_awaited()
    # the gate fired _register_post_job_water_amendment for the mop job
    assert "j1" in hass.data[DOMAIN]["_water_amendment_jobs"]
    # commit to cancel the pending 180s amendment timeout (avoid lingering-timer
    # teardown noise) — same pattern as [WA-2].
    hass.states.async_set("sensor.alfred_dock", "drying")
    await hass.async_block_till_done()


# Roborock-shaped: active_cleaning_target (current_room) reverts to the dock room
# name, never a clear sentinel, so finalize is gated on the job-active binary
# clearing (completion.require_job_active_clear). That same flag is what arms the
# batch instant-complete guard at the has_observed set-point.
_LC_ROBOROCK_ADAPTER = {
    "adapter_id": "rb", "source": "t",
    "entities": {
        "task_status": "sensor.alfred_task",
        "dock_status": "sensor.alfred_dock",
        "active_cleaning_target": "sensor.alfred_target",
        "active_map": "sensor.alfred_map",
        "job_active": "binary_sensor.alfred_cleaning",
    },
    "completion": {
        "task_status_value": "charging",
        "require_job_active_clear": True,
    },
}


async def test_lifecycle_batch_no_instant_finalize_at_dock(hass):
    """[LC-4] batch instant-complete-at-start fix. A Roborock-shaped brand whose
    active_cleaning_target reads the DOCK room at start makes evaluate_job_lifecycle
    return 'active_job_running' the instant the job exists. Pre-fix that armed
    has_observed_active_lifecycle, and the device's STALE charging + cleared
    job-active (from the previous run) finalized the brand-new job in ~1s. Now the
    flag is NOT armed while the job-active binary is OFF, so no finalize fires."""
    register_adapter_config(_VAC, _LC_ROBOROCK_ADAPTER)
    m = _mgr(hass)
    job = {"status": "started", "has_observed_active_lifecycle": False,
           "queue_room_ids": []}
    m.get_active_job.return_value = job
    m.get_lifecycle_state.return_value = {"lifecycle_state": "active_job_running"}
    m.get_managed_rooms.return_value = {"rooms": {}}
    m.finalize_learning_for_active_job = AsyncMock()
    finished = _collect(hass, EVENT_JOB_FINISHED)
    # parked from the previous run: job-active binary OFF, current_room = dock room
    # (non-empty, never a sentinel), task about to settle to its stale 'charging'.
    hass.states.async_set(_VAC, "docked")
    hass.states.async_set("sensor.alfred_task", "idle")
    hass.states.async_set("sensor.alfred_target", "Dining Room")
    hass.states.async_set("sensor.alfred_dock", "idle")
    hass.states.async_set("sensor.alfred_map", "6")
    hass.states.async_set("binary_sensor.alfred_cleaning", "off")
    lifecycle.register(hass)
    # the device's task settling to its stale completion value triggers a pass
    hass.states.async_set("sensor.alfred_task", "charging")
    await hass.async_block_till_done()
    lifecycle.remove(hass)
    assert finished == []                                    # no instant finalize
    m.finalize_learning_for_active_job.assert_not_awaited()
    m.record_active_lifecycle_observed.assert_not_called()   # flag NOT armed (binary off)
    assert job["has_observed_active_lifecycle"] is False


async def test_lifecycle_batch_arms_when_job_active_on(hass):
    """[LC-5] the same brand DOES arm has_observed once the job-active binary is ON
    (the dispatch took / device genuinely cleaning), so a real batch run stays
    finalize-eligible. No finalize here because task_status is the active 'cleaning',
    not the completion 'charging'."""
    register_adapter_config(_VAC, _LC_ROBOROCK_ADAPTER)
    m = _mgr(hass)
    m.get_active_job.return_value = {"status": "started",
                                     "has_observed_active_lifecycle": False,
                                     "queue_room_ids": []}
    m.get_lifecycle_state.return_value = {"lifecycle_state": "active_job_running"}
    m.get_managed_rooms.return_value = {"rooms": {}}
    m.finalize_learning_for_active_job = AsyncMock()
    finished = _collect(hass, EVENT_JOB_FINISHED)
    hass.states.async_set(_VAC, "cleaning")
    hass.states.async_set("sensor.alfred_task", "idle")
    hass.states.async_set("sensor.alfred_target", "Kitchen")
    hass.states.async_set("sensor.alfred_dock", "idle")
    hass.states.async_set("sensor.alfred_map", "6")
    hass.states.async_set("binary_sensor.alfred_cleaning", "on")   # dispatch took
    lifecycle.register(hass)
    hass.states.async_set("sensor.alfred_task", "cleaning")         # genuinely cleaning
    await hass.async_block_till_done()
    lifecycle.remove(hass)
    assert finished == []                                # task not 'charging' -> no finalize
    m.record_active_lifecycle_observed.assert_called()   # flag armed (binary on)


async def test_lifecycle_recharge_suppresses_finalize_until_binary_clears(hass):
    """[LC-6] mid-job recharge guard. A require_job_active_clear brand can dock and
    report the completion task_status (charging) MID-job to recharge, then resume. The
    completion gate is otherwise fully satisfied (task==charging, secondary bypassed for
    this brand, has_observed armed) — only the is_job_active guard suppresses finalize
    while the job-active binary is still ON. Once the binary clears at the true finish,
    the same signals finalize. Without the guard a recharge dock would end the job."""
    register_adapter_config(_VAC, _LC_ROBOROCK_ADAPTER)
    m = _mgr(hass)
    m.get_active_job.return_value = {
        "status": "started", "has_observed_active_lifecycle": True, "queue_room_ids": []}
    m.get_lifecycle_state.return_value = {"lifecycle_state": "active_job_running"}
    m.get_managed_rooms.return_value = {"rooms": {}}
    m.finalize_learning_for_active_job = AsyncMock(return_value={
        "job_id": "j1", "job_path": None,
        "completed_job": {"resolved_rooms": [{"clean_mode": "vacuum"}]}})
    finished = _collect(hass, EVENT_JOB_FINISHED)
    # mid-job recharge dock: completion-shaped task, but job-active binary still ON
    hass.states.async_set(_VAC, "docked")
    hass.states.async_set("sensor.alfred_task", "cleaning")
    hass.states.async_set("sensor.alfred_target", "Dining Room")
    hass.states.async_set("sensor.alfred_dock", "idle")
    hass.states.async_set("sensor.alfred_map", "6")
    hass.states.async_set("binary_sensor.alfred_cleaning", "on")   # still active -> recharge
    lifecycle.register(hass)
    try:
        # task settles to the completion value while recharging -> gate satisfied but suppressed
        hass.states.async_set("sensor.alfred_task", "charging")
        await hass.async_block_till_done()
        assert finished == []                                # recharge -> NOT finalized
        m.finalize_learning_for_active_job.assert_not_awaited()
        # device truly finishes: binary clears while task is still at the completion
        # value, so the same watched signal set now finalizes (guard no longer fires).
        hass.states.async_set("binary_sensor.alfred_cleaning", "off")
        await hass.async_block_till_done()
        assert len(finished) == 1
        m.finalize_learning_for_active_job.assert_awaited()
    finally:
        lifecycle.remove(hass)


async def test_lifecycle_finalize_calls_mark_active_job_finalized(hass):
    """[LC-7] SUPERSEDED (RP-012/RF-31, TRK-1). The finally block used to run the
    mapping tracker's end_job directly, on the executor, so position samples
    gathered during the job are flushed to room bounds. mark_active_job_finalized
    (the terminal chokepoint every path reaches -- cancel, strand, success) now
    releases the tracker's hold itself, and does so ON THE LOOP: TRK-4 may fire
    an HA event (a flushed room_completed), which is unsafe from an executor
    thread -- the old rationale for wrapping this call no longer holds. This
    mock-manager test can't exercise mark_active_job_finalized's OWN internals
    (see test_mark_finalized_ends_mapping_tracker_job in test_jobs_active_job.py
    for that, against the real method); it verifies the call still reaches that
    chokepoint on a successful finalize."""
    m = _wire_lifecycle(hass)
    m.finalize_learning_for_active_job = AsyncMock(return_value={
        "job_id": "j1", "job_path": None,
        "completed_job": {"resolved_rooms": [{"clean_mode": "vacuum"}]}})
    tracker = MagicMock()
    hass.data[DOMAIN]["mapping_tracker"] = tracker
    finished = _collect(hass, EVENT_JOB_FINISHED)
    hass.states.async_set(_VAC, "cleaning")
    hass.states.async_set("sensor.alfred_task", "cleaning")
    hass.states.async_set("sensor.alfred_target", "")
    hass.states.async_set("sensor.alfred_dock", "idle")
    hass.states.async_set("sensor.alfred_map", "6")
    lifecycle.register(hass)
    hass.states.async_set("sensor.alfred_task", "completed")
    await hass.async_block_till_done()
    lifecycle.remove(hass)
    assert len(finished) == 1
    m.mark_active_job_finalized.assert_called_once()


async def test_lifecycle_records_mop_wash_on_dock_wash_state(hass):
    """[LC-8] when the dock_status sensor transitions to an adapter-declared mop-wash
    trigger state ('washing' / 'washing mop' here, per _LC_ADAPTER) during an active
    job, the listener routes a mid-job mop-wash observation to the manager — the hook
    that feeds post-job water amendment. A regression in the entity guard or trigger
    set would silently stop counting washes."""
    m = _wire_lifecycle(hass)
    hass.states.async_set(_VAC, "cleaning")
    hass.states.async_set("sensor.alfred_task", "cleaning")
    hass.states.async_set("sensor.alfred_target", "kitchen")
    hass.states.async_set("sensor.alfred_dock", "idle")
    hass.states.async_set("sensor.alfred_map", "6")
    lifecycle.register(hass)
    try:
        hass.states.async_set("sensor.alfred_dock", "washing")   # dock enters a wash state
        await hass.async_block_till_done()
        m.update_active_job_mop_wash_observation.assert_called_once_with(
            vacuum_entity_id=_VAC, map_id=_MAP)
    finally:
        lifecycle.remove(hass)


async def test_lifecycle_wash_observation_ignores_first_sighting_after_restart(hass):
    """[LIFE-3] the inline wash detector delegates its edge test to the SAME
    is_dock_trigger_edge helper dock_events.py's own _handle_dock_event uses
    (listeners/_common.py): a dock_status entity with no prior known state
    (old_state=None — HA restart mid-wash, or genuinely the first-ever
    reading) must not be treated as a fresh transition INTO the wash
    trigger. Pre-fix, the bare new-state check had no old_state guard at
    all (not even an old==new dedup) and would have fired here."""
    m = _wire_lifecycle(hass)
    hass.states.async_set(_VAC, "cleaning")
    hass.states.async_set("sensor.alfred_task", "cleaning")
    hass.states.async_set("sensor.alfred_target", "kitchen")
    # sensor.alfred_dock deliberately left unset — its first-ever reading
    # arrives AFTER registration, so old_state=None on that transition.
    hass.states.async_set("sensor.alfred_map", "6")
    lifecycle.register(hass)
    try:
        hass.states.async_set("sensor.alfred_dock", "washing")
        await hass.async_block_till_done()
        m.update_active_job_mop_wash_observation.assert_not_called()
    finally:
        lifecycle.remove(hass)


async def test_lifecycle_wash_observation_no_adapter_vocab_no_fallback(hass):
    """[LIFE-3 vocab] RP-025's deferred half, closed here: an adapter that
    declares no dock_events.triggers.last_mop_wash gets NO wash-observation
    detection at all — no silent inheritance of Eufy's own hardcoded
    'washing'/'washing mop' vocabulary (matches dock/manager.py's own
    get_dock_action_status doctrine: adapter-driven only, no brand
    fallback). Eufy's real adapter.py DOES declare this trigger set, so
    live Eufy detection is unaffected — this proves an adapter that omits
    it no longer silently borrows Eufy's vocabulary."""
    _adapter_no_vocab = {
        "adapter_id": "t_no_vocab", "source": "t",
        "entities": {
            "task_status": "sensor.alfred_task",
            "dock_status": "sensor.alfred_dock",
            "active_cleaning_target": "sensor.alfred_target",
            "active_map": "sensor.alfred_map",
        },
        # Deliberately no "dock_events" block at all.
    }
    register_adapter_config(_VAC, _adapter_no_vocab)
    m = _mgr(hass)
    m.get_active_job.return_value = {
        "status": "started", "has_observed_active_lifecycle": True,
        "queue_room_ids": []}
    m.get_lifecycle_state.return_value = {"lifecycle_state": "active_job_running"}
    m.get_managed_rooms.return_value = {"rooms": {}}
    hass.states.async_set(_VAC, "cleaning")
    hass.states.async_set("sensor.alfred_task", "cleaning")
    hass.states.async_set("sensor.alfred_target", "kitchen")
    hass.states.async_set("sensor.alfred_dock", "idle")
    hass.states.async_set("sensor.alfred_map", "6")
    lifecycle.register(hass)
    try:
        hass.states.async_set("sensor.alfred_dock", "washing")
        await hass.async_block_till_done()
        m.update_active_job_mop_wash_observation.assert_not_called()
    finally:
        lifecycle.remove(hass)


async def test_lifecycle_recharge_guard_suppresses_on_unavailable_binary(hass):
    """[LC-9] the recharge guard treats an 'unavailable'/'unknown' job-active binary as
    still active: a transient cloud blip during a mid-recharge dock must NOT finalize the
    job (which would record a truncated learning sample and orphan the resumed half).
    Mirrors LC-6 but the binary reads 'unavailable' rather than 'on'."""
    register_adapter_config(_VAC, _LC_ROBOROCK_ADAPTER)
    m = _mgr(hass)
    m.get_active_job.return_value = {
        "status": "started", "has_observed_active_lifecycle": True, "queue_room_ids": []}
    m.get_lifecycle_state.return_value = {"lifecycle_state": "active_job_running"}
    m.get_managed_rooms.return_value = {"rooms": {}}
    m.finalize_learning_for_active_job = AsyncMock()
    finished = _collect(hass, EVENT_JOB_FINISHED)
    hass.states.async_set(_VAC, "docked")
    hass.states.async_set("sensor.alfred_task", "cleaning")
    hass.states.async_set("sensor.alfred_target", "Dining Room")
    hass.states.async_set("sensor.alfred_dock", "idle")
    hass.states.async_set("sensor.alfred_map", "6")
    hass.states.async_set("binary_sensor.alfred_cleaning", "unavailable")  # cloud blip
    lifecycle.register(hass)
    try:
        hass.states.async_set("sensor.alfred_task", "charging")   # completion-shaped
        await hass.async_block_till_done()
        assert finished == []                                # blip mid-recharge -> NOT finalized
        m.finalize_learning_for_active_job.assert_not_awaited()
    finally:
        lifecycle.remove(hass)


async def test_lifecycle_recharge_resolution_matches_direct_call(hass, manager, monkeypatch):
    """[LC-10] RP-012/RF-31 parity check (required_behavior (2), Q14 closure): the
    recharge-end transition delivered through the REAL lifecycle listener must match
    the direct-call contract locked in by AJI-13
    (test_jobs_active_job.test_recharge_ends_accumulates). Unlike every other test in
    this file, this one wires the REAL manager/ActiveJobTracker at DATA_RUNTIME (not
    the MagicMock _mgr helper) so the actual delegator chain the listener calls —
    manager.resolve_mid_job_recharge_resumed -> ActiveJobTracker method — runs for
    real, proving production listeners deliver the equivalent transition rather than
    just proving the listener CALLS the right method name."""
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "status": "started",
        "vacuum_entity_id": _VAC,
        "map_id": _MAP,
        "started_at": "2026-01-01T09:00:00+00:00",
        "pending_mid_job_recharge_return": True,
        "observed_mid_job_recharge": True,
        "observed_mid_job_recharge_started_at": "2026-01-01T09:00:00+00:00",
        "recharge_seconds_accumulated": 0,
    }
    monkeypatch.setattr(manager.active_job, "_is_charging", lambda _v: False)
    monkeypatch.setattr(
        "custom_components.eufy_vacuum.jobs.active_job._iso_now",
        lambda: "2026-01-01T09:05:00+00:00",
    )
    fake_tracker = MagicMock()
    hass.data[DOMAIN]["mapping_tracker"] = fake_tracker

    lifecycle.register(hass)
    try:
        hass.states.async_set(_VAC, "docked")   # any watched entity -- ticks the listener
        await hass.async_block_till_done()
    finally:
        lifecycle.remove(hass)

    updated = manager.get_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert updated["observed_mid_job_recharge"] is False
    assert updated["recharge_seconds_accumulated"] == 300   # 5 min -- same as AJI-13
    fake_tracker.resume_sampling.assert_called_once_with(_VAC)


async def test_path_blocker_ignores_unavailable_transition(hass):
    """[PB-7] (RP-008 step 3) a transition INTO a dropout sentinel triggers no
    rule evaluation and no action — hold-previous by inaction: a clear room
    stays clear (no cancel), a blocked room's already-taken pause persists."""
    m = _wire_path_blocker(hass, path_block_action="cancel_and_event")
    m.async_cancel_active_job = AsyncMock(return_value={"cancelled": True})
    blocked = _collect(hass, EVENT_PATH_BLOCKED)
    hass.states.async_set("binary_sensor.win", "on")
    path_blockers.register(hass)
    hass.states.async_set("binary_sensor.win", "unavailable")   # battery died
    await hass.async_block_till_done()
    path_blockers.remove(hass)
    assert blocked == []
    m.async_cancel_active_job.assert_not_awaited()


async def test_path_blocker_recheck_suppresses_stale_cancel(hass):
    """[PB-8] (RP-008 step 4) the cancel path re-checks the triggering rule with
    a KNOWN state at action time; a rule that no longer matches suppresses the
    cancel and reports it."""
    m = _wire_path_blocker(hass, path_block_action="cancel_and_event")
    m.access_graph._room_rule_matches_known.return_value = (False, False)  # dropped out
    m.async_cancel_active_job = AsyncMock(return_value={"cancelled": True})
    blocked = _collect(hass, EVENT_PATH_BLOCKED)
    hass.states.async_set("binary_sensor.win", "off")
    path_blockers.register(hass)
    hass.states.async_set("binary_sensor.win", "on")
    await hass.async_block_till_done()
    path_blockers.remove(hass)
    m.async_cancel_active_job.assert_not_awaited()
    assert blocked[0].data["action_taken"] == "cancel_suppressed_recheck"


async def test_path_blocker_rapid_edges_single_cancel(hass):
    """[PB-9] (RP-008 / GUARD-2) two rapid genuine edges coalesce: one
    evaluation runs, one re-check queues behind it, and the job — already
    cancelled by the first — is not cancelled twice."""
    m = _wire_path_blocker(hass, path_block_action="cancel_and_event")
    # after the first cancel the job status flips — the re-check evaluation
    # must see the flipped status (this is what production does; a static
    # 'started' here would be a fixture asserting fiction)
    m.get_active_job.side_effect = [
        {"path_block_action": "cancel_and_event", "status": "started"},
        {"path_block_action": "cancel_and_event", "status": "completed"},
        {"path_block_action": "cancel_and_event", "status": "completed"},
    ]
    m.get_runtime_path_block_report.side_effect = [
        {"affected_remaining_room_ids": [2]},
        None,   # post-cancel evaluation: nothing actionable
        None,
    ]
    m.async_cancel_active_job = AsyncMock(return_value={
        "cancelled": True, "finalize_result": {"job_id": "j1"}})
    hass.states.async_set("binary_sensor.win", "off")
    path_blockers.register(hass)
    hass.states.async_set("binary_sensor.win", "on")      # edge 1
    hass.states.async_set("binary_sensor.win", "open")    # edge 2, rapid
    await hass.async_block_till_done()
    path_blockers.remove(hass)
    m.async_cancel_active_job.assert_awaited_once()
