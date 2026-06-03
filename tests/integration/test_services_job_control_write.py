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

The device-I/O action handlers (start/pause/resume/cancel) are driven through
the module-level _handle_* coroutines with a mock manager rather than the
physical service-call path.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.exceptions import HomeAssistantError

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.const import (
    DATA_RUNTIME,
    DOMAIN,
    EVENT_JOB_FINISHED,
)
from custom_components.eufy_vacuum.services.job_control import (
    _handle_cancel_active_job,
    _handle_clear_active_job,
    _handle_pause_active_job,
    _handle_resume_active_job,
    _handle_start_run_profile,
    _handle_start_selected_rooms,
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
    mgr = MagicMock()
    mgr.async_save = AsyncMock()
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = mgr
    return hass, mgr


def _call(**extra):
    return _Call({"vacuum_entity_id": _VAC, "map_id": _MAP, **extra})


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
