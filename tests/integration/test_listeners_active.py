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
[LC-1]  lifecycle: completion signals met → finalize + JOB_FINISHED + save.
[LC-2]  lifecycle: signals not met → observed recorded, no finalize/event.
"""

from __future__ import annotations

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
