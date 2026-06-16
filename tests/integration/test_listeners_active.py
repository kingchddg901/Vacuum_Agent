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
[JP-1]  job_progress: active job → snapshot + EVENT_JOB_PROGRESS_TICK.
[JP-2]  job_progress: inactive status → skipped.
[JP-3]  job_progress: snapshot raises → swallowed, no event.
[PB-1]  path_blockers: pause_and_event → pause + EVENT_PATH_BLOCKED.
[PB-2]  path_blockers: cancel_and_event → cancel + JOB_FINISHED + PATH_BLOCKED.
[PB-3]  path_blockers: event_only → just EVENT_PATH_BLOCKED.
[PB-4]  path_blockers: pause_and_event + already-paused job → action_taken=already_paused, no pause call.
[PB-5]  path_blockers: cancel_and_event + cancel returns not-cancelled → action_taken=cancel_failed, no JOB_FINISHED.
[LC-1]  lifecycle: completion signals met → finalize + JOB_FINISHED + save.
[LC-2]  lifecycle: signals not met → observed recorded, no finalize/event.
[LC-3]  lifecycle: finalized MOP job → post-job water amendment registered.
[LC-4]  lifecycle: batch instant-complete fix — a require_job_active_clear brand
        (Roborock) does NOT arm has_observed (so can't finalize) while the
        job-active binary is OFF at the dock, even with active_job_running + stale
        completion signals.
[LC-5]  lifecycle: the same brand DOES arm has_observed once the job-active binary
        is ON (the dispatch took) — a genuine batch run stays finalize-eligible.
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
