"""Phase 8 integration tests — services/job_control.py write path.

Coverage targets
----------------
[JCW-1]  clear_active_job on a vacuum with no active job does not raise.
[JCW-2]  clear_active_job on a vacuum with no active job succeeds for both maps.
[JCW-4]  action handlers succeed → delegate result + async_save.
[JCW-5]  action handlers wrap a manager exception in HomeAssistantError.
[JCW-6]  cancel_active_job cancelled=True → fires EVENT_JOB_FINISHED.
[JCW-7]  cancel_active_job cancelled=False → no event, still saves.
[JCW-8]  clear_active_job manager raises → HomeAssistantError.
[JCW-9]  cancel_active_job manager raises → HomeAssistantError.
[JCW-10] cancel_active_job that stranded rooms → also fires EVENT_RUN_INCOMPLETE.
[JCW-11] cancel_active_job with no missed rooms → JOB_FINISHED only.

The device-I/O action handlers (start/pause/resume/cancel) are driven through
the module-level _handle_* coroutines with a mock manager rather than the
physical service-call path.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.exceptions import HomeAssistantError

from tests._factories import spec_manager

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.const import (
    DATA_RUNTIME,
    DOMAIN,
    EVENT_JOB_FINISHED,
    EVENT_RUN_INCOMPLETE,
)
from custom_components.eufy_vacuum.core.manager import _INFLIGHT_LIFECYCLE_STATES
from custom_components.eufy_vacuum.services.job_control import (
    _handle_cancel_active_job,
    _handle_clear_active_job,
    _handle_pause_active_job,
    _handle_resume_active_job,
    _handle_start_run_profile,
    _handle_start_selected_rooms,
    _handle_start_zone_clean,
)

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"

_LIFECYCLE_ADAPTER = {
    "adapter_id": "test",
    "source": "test",
    "entities": {
        "task_status": "sensor.alfred_task_status",
        "dock_status": "sensor.alfred_dock_status",
        "active_map": "sensor.alfred_active_map",
        "active_cleaning_target": "sensor.alfred_active_cleaning_target",
    },
}


async def _setup_vacuum(hass, manager) -> None:
    """Seed a vacuum with an adapter and all lifecycle entity states."""
    setup_map(manager, _VAC, _MAP, count=2)
    register_adapter_config(_VAC, _LIFECYCLE_ADAPTER)
    hass.states.async_set("sensor.alfred_task_status", "idle")
    hass.states.async_set("sensor.alfred_dock_status", "idle")
    hass.states.async_set("sensor.alfred_active_map", _MAP)
    hass.states.async_set("sensor.alfred_active_cleaning_target", "")
    await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# [JCW-1] clear_active_job — no active job
# ---------------------------------------------------------------------------

async def test_clear_active_job_no_active_job_does_not_raise(hass, manager_with_services):
    """[JCW-1] clear_active_job completes without raising when no job is active."""
    await _setup_vacuum(hass, manager_with_services)
    # Should not raise — clear_active_job is a no-op when no job is tracked.
    await hass.services.async_call(
        DOMAIN,
        "clear_active_job",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )


@pytest.mark.parametrize("service,method,extra", [
    ("start_selected_rooms", "start_selected_rooms", {}),
    ("start_run_profile", "start_run_profile", {"profile_id": "p"}),
    ("pause_active_job", "async_pause_active_job", {}),
    ("resume_active_job", "async_resume_active_job", {}),
    ("cancel_active_job", "async_cancel_active_job", {}),
])
async def test_job_control_dispatch_wiring(hass, manager_with_services, monkeypatch, service, method, extra):
    """[JCW-1b] each registered job-control service dispatches through its closure
    to the matching manager method — verifies the service-name→handler wiring for
    the robot-command services (plumbing can be mis-wired)."""
    await _setup_vacuum(hass, manager_with_services)
    spy = AsyncMock(return_value={"started": True})
    monkeypatch.setattr(manager_with_services, method, spy)
    await hass.services.async_call(
        DOMAIN, service, {"vacuum_entity_id": _VAC, "map_id": _MAP, **extra}, blocking=True)
    assert spy.await_count == 1


async def test_clear_active_job_is_idempotent(hass, manager_with_services):
    """[JCW-2] Calling clear_active_job twice does not raise on the second call."""
    await _setup_vacuum(hass, manager_with_services)
    await hass.services.async_call(
        DOMAIN,
        "clear_active_job",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "clear_active_job",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )


# ---------------------------------------------------------------------------
# [JCW-4] — [JCW-8] action handlers (direct-handler, mock manager)
# ---------------------------------------------------------------------------

class _Call:
    def __init__(self, data):
        self.data = data


@pytest.fixture
def jc(hass):
    """(hass, mock_manager) with the manager wired at DATA_RUNTIME."""
    mgr = spec_manager()
    mgr.async_save = AsyncMock()
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = mgr
    return hass, mgr


def _call(**extra):
    return _Call({"vacuum_entity_id": _VAC, "map_id": _MAP, **extra})


# ---------------------------------------------------------------------------
# RP-010/RF-06 (JOB-2): start_zone_clean must not stack a second dispatch
# ---------------------------------------------------------------------------

# DERIVED, never hand-copied. The previous version of this list was four literal
# strings typed out beside a production frozenset of the same four strings, fed
# into a MagicMock. Fixture and implementation agreed with each other, and NEITHER
# was ever compared against the real producer -- which is how a guard that never
# fired during a real run passed a parametrized test for every reason it accepts.
_INFLIGHT_REASONS = sorted(_INFLIGHT_LIFECYCLE_STATES | {"job_paused"})


@pytest.mark.parametrize("reason", _INFLIGHT_REASONS)
async def test_zone_clean_refuses_when_job_in_progress(jc, reason):
    """[JCW-12] a job already running/paused/being-serviced must not let a zone
    clean stack a second dispatch on top of it. Refuses Q9-shaped (flags, not a
    raised exception) for every in-flight reason the manager can report."""
    hass, mgr = jc
    # `.return_value` on the SPEC'd attribute, not a bare MagicMock assignment:
    # spec_manager() is autospec'd from the real manager, so this also proves
    # get_job_inflight_state exists there with this signature. A bare mock would
    # happily stand in for a method that had been renamed out from under it --
    # which is the same class of blindness that hid this bug in the first place.
    mgr.get_job_inflight_state.return_value = {
        "in_flight": True, "reason": reason, "message": "busy"}
    mgr.dispatch_zone_clean.return_value = {"success": True}

    result = await _handle_start_zone_clean(
        hass, _call(zones=[[0, 0, 1, 1]])
    )

    assert result == {
        "success": False,
        "reason": "job_in_progress",
        "start_status_reason": reason,
        "message": "busy",
    }
    mgr.dispatch_zone_clean.assert_not_awaited()


async def test_zone_clean_ignores_room_queue_readiness(jc):
    """[JCW-13] ROOM-QUEUE readiness (onboarding, no target map, nothing selected)
    never applied to a zones-based dispatch and must not newly block it. The zone
    path asks the in-flight question ONLY, so a not-in-flight answer dispatches
    however unready the room queue is."""
    hass, mgr = jc
    mgr.get_job_inflight_state.return_value = {
        "in_flight": False, "reason": "", "message": ""}
    mgr.get_start_status.return_value = {
        "blocked": True, "reason": "onboarding_required", "message": "x"}
    mgr.dispatch_zone_clean.return_value = {"success": True, "zones_dispatched": 1}

    result = await _handle_start_zone_clean(
        hass, _call(zones=[[0, 0, 1, 1]])
    )

    mgr.dispatch_zone_clean.assert_awaited_once()
    assert result == {"success": True, "zones_dispatched": 1}
    # The refusal ladder is not consulted at all any more: it answers a different
    # question, and reading its message as a control signal is what broke this.
    mgr.get_start_status.assert_not_called()


async def test_inflight_state_sees_a_started_job_that_start_status_reports_as_empty(
    manager,
):
    """[JCW-15] THE REGRESSION. Drives the REAL producer, no MagicMock anywhere.

    A tracked run is in flight the moment its record says `started`. The old guard
    could not see that, because it read `get_start_status`'s refusal STRING, and
    `start_selected_rooms` clears the room selection right after dispatching --
    so during a run the ladder answers `no_rooms_selected` (queue readiness) from
    above every lifecycle branch, and `active_job_running` is nearly unreachable.

    Both halves are asserted together deliberately. The first pins the shadowing
    that made the old approach unsound, so nobody "fixes" it back to reading the
    reason string; the second is the guarantee the zone-clean guard now rests on.
    """
    manager.data.setdefault("active_jobs", {})[_VAC] = {
        _MAP: {"status": "started", "map_id": _MAP, "vacuum_entity_id": _VAC}
    }

    # The old signal, still shadowed -- this is the bug, pinned.
    start_status = manager.get_start_status(vacuum_entity_id=_VAC, map_id=_MAP)
    assert start_status.get("reason") != "active_job_running"

    # The new signal, which asks the question it actually means.
    inflight = manager.get_job_inflight_state(vacuum_entity_id=_VAC, map_id=_MAP)
    assert inflight["in_flight"] is True
    assert inflight["reason"] == "active_job_running"


async def test_inflight_state_is_false_with_no_job(manager):
    """[JCW-16] the other direction: no active job and an idle vacuum is not in
    flight, so a zone clean is never refused on a quiet system."""
    inflight = manager.get_job_inflight_state(vacuum_entity_id=_VAC, map_id=_MAP)
    assert inflight["in_flight"] is False
    assert inflight["reason"] == ""


async def test_zone_clean_proceeds_when_ready(jc):
    """[JCW-14] sanity: nothing in flight dispatches normally -- the documented
    no-tracking/fire-and-forget semantics are unchanged."""
    hass, mgr = jc
    mgr.get_job_inflight_state.return_value = {
        "in_flight": False, "reason": "", "message": ""}
    mgr.dispatch_zone_clean.return_value = {"success": True, "zones_dispatched": 1}

    result = await _handle_start_zone_clean(
        hass, _call(zones=[[0, 0, 1, 1]])
    )

    mgr.dispatch_zone_clean.assert_awaited_once()
    assert result["success"] is True


# Async action handler ↔ manager method ↔ error prefix.
_ASYNC_ACTIONS = [
    (_handle_start_selected_rooms, "start_selected_rooms", "Failed to start cleaning"),
    (_handle_start_run_profile, "start_run_profile", "Failed to start run profile"),
    (_handle_pause_active_job, "async_pause_active_job", "Failed to pause job"),
    (_handle_resume_active_job, "async_resume_active_job", "Failed to resume job"),
]


@pytest.mark.parametrize("handler,method,_prefix", _ASYNC_ACTIONS)
async def test_action_success_saves(jc, handler, method, _prefix):
    """[JCW-4] handler delegates to the manager then persists."""
    hass, mgr = jc
    setattr(mgr, method, AsyncMock(return_value={"ok": True}))
    extra = {"profile_id": "p1"} if method == "start_run_profile" else {}
    await handler(hass, _call(**extra))
    getattr(mgr, method).assert_awaited_once()
    mgr.async_save.assert_awaited_once()


@pytest.mark.parametrize("handler,method,prefix", _ASYNC_ACTIONS)
async def test_action_manager_raises(jc, handler, method, prefix):
    """[JCW-5]"""
    hass, mgr = jc
    setattr(mgr, method, AsyncMock(side_effect=RuntimeError("boom")))
    extra = {"profile_id": "p1"} if method == "start_run_profile" else {}
    with pytest.raises(HomeAssistantError, match=prefix):
        await handler(hass, _call(**extra))


async def test_cancel_fires_job_finished(jc):
    """[JCW-6] a real cancellation fires EVENT_JOB_FINISHED then saves."""
    hass, mgr = jc
    mgr.async_cancel_active_job = AsyncMock(return_value={
        "cancelled": True,
        "finalize_result": {"job_id": "j1", "completed_job": {
            "outcome": {"status": "cancelled"}, "job": {"room_count": 2}}},
    })
    events = []
    hass.bus.async_listen(EVENT_JOB_FINISHED, lambda e: events.append(e))
    out = await _handle_cancel_active_job(hass, _call())
    await hass.async_block_till_done()
    assert out["cancelled"] is True
    assert len(events) == 1
    assert events[0].data["vacuum_entity_id"] == _VAC
    assert events[0].data["status"] == "cancelled"
    mgr.async_save.assert_awaited_once()


async def test_cancel_no_finalize_no_event(jc):
    """[JCW-7] cancelled=False → no event fired, but state still saved."""
    hass, mgr = jc
    mgr.async_cancel_active_job = AsyncMock(return_value={"cancelled": False})
    events = []
    hass.bus.async_listen(EVENT_JOB_FINISHED, lambda e: events.append(e))
    await _handle_cancel_active_job(hass, _call())
    await hass.async_block_till_done()
    assert events == []
    mgr.async_save.assert_awaited_once()


async def test_cancel_stranded_rooms_fires_run_incomplete(jc):
    """[JCW-10] A manual cancel that stranded rooms fires EVENT_RUN_INCOMPLETE
    alongside EVENT_JOB_FINISHED, so an automation's retry_missed_rooms trigger
    fires the same as on the finalize_learning_job service path."""
    hass, mgr = jc
    mgr.async_cancel_active_job = AsyncMock(return_value={
        "cancelled": True,
        "finalize_result": {
            "job_id": "j1",
            "completed_job": {"outcome": {"status": "cancelled"},
                              "job": {"room_count": 2}},
            "incomplete_run_log": {
                "job_id": "j1", "outcome_status": "cancelled",
                "missed_room_ids": [2, 3],
                "missed_rooms": [{"room_id": 2, "name": "Kitchen"},
                                 {"room_id": 3, "name": "Den"}]},
        },
    })
    finished = []
    incomplete = []
    hass.bus.async_listen(EVENT_JOB_FINISHED, lambda e: finished.append(e))
    hass.bus.async_listen(EVENT_RUN_INCOMPLETE, lambda e: incomplete.append(e))
    await _handle_cancel_active_job(hass, _call())
    await hass.async_block_till_done()
    assert len(finished) == 1
    assert len(incomplete) == 1
    data = incomplete[0].data
    assert data["vacuum_entity_id"] == _VAC
    assert data["outcome_status"] == "cancelled"
    assert data["missed_room_ids"] == [2, 3]
    assert "map_id" not in data


async def test_cancel_no_missed_rooms_no_run_incomplete(jc):
    """[JCW-11] A manual cancel with no stranded rooms fires only EVENT_JOB_FINISHED."""
    hass, mgr = jc
    mgr.async_cancel_active_job = AsyncMock(return_value={
        "cancelled": True,
        "finalize_result": {"job_id": "j1", "completed_job": {
            "outcome": {"status": "cancelled"}, "job": {"room_count": 2}}},
    })
    finished = []
    incomplete = []
    hass.bus.async_listen(EVENT_JOB_FINISHED, lambda e: finished.append(e))
    hass.bus.async_listen(EVENT_RUN_INCOMPLETE, lambda e: incomplete.append(e))
    await _handle_cancel_active_job(hass, _call())
    await hass.async_block_till_done()
    assert len(finished) == 1
    assert incomplete == []


async def test_clear_active_job_manager_raises(jc):
    """[JCW-8]"""
    hass, mgr = jc
    mgr.clear_active_job = MagicMock(side_effect=ValueError("bad"))
    with pytest.raises(HomeAssistantError, match="Failed to clear active job"):
        await _handle_clear_active_job(hass, _call())


async def test_cancel_manager_raises(jc):
    """[JCW-9] cancel manager exception → wrapped HomeAssistantError."""
    hass, mgr = jc
    mgr.async_cancel_active_job = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(HomeAssistantError, match="Failed to cancel job"):
        await _handle_cancel_active_job(hass, _call())
