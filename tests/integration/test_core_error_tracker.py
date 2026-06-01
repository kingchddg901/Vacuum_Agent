"""Tests for core/error_tracker.py — active-run error latch tracker.

Drives ErrorTracker with a MagicMock manager (``.data`` dict + AsyncMock
``async_save``) and the real ``hass`` fixture for the state machine, listeners,
and loop. Edge handling, latch shaping, harvest, acknowledge, and the
secondary-channel grace window are all exercised against crafted records.

Coverage targets
----------------
[ET-1]  module helpers: _is_error_value, _get_not_error_set, _safe_int, _job_elapsed.
[ET-2]  _ensure_record defaults + recent_errors limit slicing.
[ET-3]  rising edge with active job → forms latch + last_device + ring buffer.
[ET-4]  rising edge without active job → last_device only, no active latch.
[ET-5]  second rising edge extends the latch (error_count++, recovered reset).
[ET-6]  falling edge marks recovered + stamps recovered_at.
[ET-7]  harvest_active_run returns + clears latch; None when empty.
[ET-8]  acknowledge scopes (active_run / last_device / both) + missing record.
[ET-9]  _read_error_code_attr reads code attr, treats 0 as None.
[ET-10] _handle_error_message_change rising then falling via the public seam.
[ET-11] start/_wire_vacuum wires listeners; stop tears them down.
[ET-12] secondary-channel grace: schedule on vacuum=error, generic latch on expiry.
[ET-13] _persist_and_notify schedules async_save + fires update listeners.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

import homeassistant.util.dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.core import error_tracker as et
from custom_components.eufy_vacuum.core.error_tracker import ErrorTracker


_VAC = "vacuum.alfred"


@pytest.fixture
def tracker(hass):
    """Return (ErrorTracker, mock_manager) with a real hass + AsyncMock save."""
    mgr = MagicMock()
    mgr.data = {}
    mgr.async_save = AsyncMock()
    return ErrorTracker(hass, runtime_manager=mgr), mgr


def _seed_active_job(mgr, *, job_id="j1", room_id=3, started_minutes_ago=2):
    started = (datetime.now(timezone.utc)
               - timedelta(minutes=started_minutes_ago)).isoformat()
    mgr.data["active_jobs"] = {
        _VAC: {"6": {"job_id": job_id, "started_at": started,
                     "current_room_id": room_id}}}


# ---------------------------------------------------------------------------
# module helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (None, False), ("", False), ("unknown", False), ("unavailable", False),
    ("Stuck", True), ("E70", True), ("  ", False),
])
def test_is_error_value(value, expected):
    """[ET-1]"""
    assert et._is_error_value(value) is expected


def test_get_not_error_set_and_safe_int():
    """[ET-1]"""
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "vocabulary": {"not_error_sentinels": ["NONE", "Normal", ""]},
    })
    s = et._get_not_error_set(_VAC)
    assert "none" in s and "normal" in s
    # unregistered → generic fallback
    assert et._get_not_error_set("vacuum.unknown") == et._NOT_ERROR
    assert et._safe_int("5") == 5
    assert et._safe_int("x") is None
    assert et._safe_int(None) is None


def test_job_elapsed_seconds():
    """[ET-1]"""
    assert et._job_elapsed_seconds(None) == 0
    assert et._job_elapsed_seconds({"started_at": "not-a-date"}) == 0
    started = (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat()
    assert et._job_elapsed_seconds({"started_at": started}) >= 85


# ---------------------------------------------------------------------------
# record access
# ---------------------------------------------------------------------------

def test_ensure_record_and_recent_limit(tracker):
    """[ET-2]"""
    t, mgr = tracker
    rec = t.get_record(_VAC)
    assert rec == {"active_run_error": None, "last_device_error": None,
                   "recent_errors": []}
    rec["recent_errors"] = [{"message": f"e{i}"} for i in range(5)]
    assert len(t.recent_errors(_VAC)) == 5
    assert len(t.recent_errors(_VAC, limit=2)) == 2
    assert t.recent_errors(_VAC, limit=2)[-1]["message"] == "e4"


# ---------------------------------------------------------------------------
# rising / falling edges
# ---------------------------------------------------------------------------

async def test_rising_edge_with_active_job(tracker, hass):
    """[ET-3]"""
    t, mgr = tracker
    _seed_active_job(mgr)
    hass.states.async_set(_VAC, "error")
    t._record_rising_edge(_VAC, message="Stuck", code=5, attribute_code=None)
    await hass.async_block_till_done()

    rec = t.get_record(_VAC)
    assert rec["last_device_error"]["message"] == "Stuck"
    assert rec["last_device_error"]["was_during_active_run"] is True
    assert len(rec["recent_errors"]) == 1
    latch = rec["active_run_error"]
    assert latch["active_job_id"] == "j1"
    assert latch["error_count"] == 1
    assert latch["errored_room_id"] == "3"
    assert latch["current_message"] == "Stuck"
    mgr.async_save.assert_awaited()


async def test_rising_edge_without_active_job(tracker, hass):
    """[ET-4] no job in flight → last_device + ring, but no active-run latch."""
    t, mgr = tracker
    t._record_rising_edge(_VAC, message="E70", code=70, attribute_code=None)
    await hass.async_block_till_done()
    rec = t.get_record(_VAC)
    assert rec["last_device_error"]["message"] == "E70"
    assert rec["active_run_error"] is None
    assert rec["last_device_error"]["was_during_active_run"] is False


async def test_second_rising_edge_extends_latch(tracker, hass):
    """[ET-5]"""
    t, mgr = tracker
    _seed_active_job(mgr)
    t._record_rising_edge(_VAC, message="Stuck", code=5, attribute_code=None)
    t._record_falling_edge(_VAC)  # recovered=True
    t._record_rising_edge(_VAC, message="Cliff", code=6, attribute_code=None)
    await hass.async_block_till_done()
    latch = t.get_record(_VAC)["active_run_error"]
    assert latch["error_count"] == 2
    assert latch["current_message"] == "Cliff"
    assert latch["recovered"] is False
    assert len(latch["errors"]) == 2


async def test_falling_edge_marks_recovered(tracker, hass):
    """[ET-6]"""
    t, mgr = tracker
    _seed_active_job(mgr)
    t._record_rising_edge(_VAC, message="Stuck", code=5, attribute_code=None)
    t._record_falling_edge(_VAC)
    await hass.async_block_till_done()
    latch = t.get_record(_VAC)["active_run_error"]
    assert latch["recovered"] is True
    assert latch["current_message"] == ""
    assert latch["errors"][-1]["recovered_at"] is not None
    # no-op when there's no latch
    t2, _ = tracker
    other = "vacuum.none"
    t._record_falling_edge(other)
    assert t.get_record(other)["active_run_error"] is None


# ---------------------------------------------------------------------------
# harvest + acknowledge
# ---------------------------------------------------------------------------

async def test_harvest_active_run(tracker, hass):
    """[ET-7]"""
    t, mgr = tracker
    _seed_active_job(mgr)
    t._record_rising_edge(_VAC, message="Stuck", code=5, attribute_code=None)
    harvested = t.harvest_active_run(_VAC, "j1")
    await hass.async_block_till_done()
    assert harvested["active_job_id"] == "j1"
    assert t.get_record(_VAC)["active_run_error"] is None
    # nothing to harvest now
    assert t.harvest_active_run(_VAC, "j1") is None


async def test_acknowledge_scopes(tracker, hass):
    """[ET-8]"""
    t, mgr = tracker
    # missing record → False
    assert t.acknowledge("vacuum.ghost") is False
    _seed_active_job(mgr)
    t._record_rising_edge(_VAC, message="Stuck", code=5, attribute_code=None)
    # scope=last_device clears only last_device
    assert t.acknowledge(_VAC, scope="last_device") is True
    rec = t.get_record(_VAC)
    assert rec["last_device_error"] is None
    assert rec["active_run_error"] is not None
    # scope=both clears the rest
    t.acknowledge(_VAC, scope="both")
    assert t.get_record(_VAC)["active_run_error"] is None


# ---------------------------------------------------------------------------
# code attribute + message-change seam
# ---------------------------------------------------------------------------

def test_read_error_code_attr(tracker, hass):
    """[ET-9] code from attrs; 0 treated as 'no code'."""
    t, mgr = tracker
    t._vacuum_entities[_VAC] = {"error_message": "sensor.alfred_err",
                                "task_status": None}
    hass.states.async_set("sensor.alfred_err", "Stuck", {"error_code": 70})
    assert t._read_error_code_attr(_VAC) == 70
    hass.states.async_set("sensor.alfred_err", "Stuck", {"error_code": 0})
    assert t._read_error_code_attr(_VAC) is None
    hass.states.async_set("sensor.alfred_err", "Stuck", {})
    assert t._read_error_code_attr(_VAC) is None


async def test_handle_error_message_change(tracker, hass):
    """[ET-10] rising then falling through the message-change handler."""
    t, mgr = tracker
    _seed_active_job(mgr)
    t._vacuum_entities[_VAC] = {"error_message": "sensor.alfred_err",
                                "task_status": None}
    t._handle_error_message_change(_VAC, "unknown", "Stuck")
    await hass.async_block_till_done()
    assert t.get_record(_VAC)["active_run_error"]["current_message"] == "Stuck"
    t._handle_error_message_change(_VAC, "Stuck", "")
    await hass.async_block_till_done()
    assert t.get_record(_VAC)["active_run_error"]["recovered"] is True


# ---------------------------------------------------------------------------
# wiring + grace window
# ---------------------------------------------------------------------------

def test_start_wires_and_stop_clears(tracker, hass):
    """[ET-11]"""
    t, mgr = tracker
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"error_message": "sensor.alfred_err",
                     "task_status": "sensor.alfred_task"},
    })
    t.start([_VAC])
    assert _VAC in t._vacuum_unsubs
    assert t._source_to_vacuum["sensor.alfred_err"] == _VAC
    assert t._source_to_vacuum["sensor.alfred_task"] == _VAC
    # idempotent re-wire
    t.start([_VAC])
    t.stop()
    assert t._vacuum_unsubs == {}
    assert t._source_to_vacuum == {}


async def test_secondary_grace_schedule_and_expiry(tracker, hass):
    """[ET-12] vacuum=error + no message schedules grace; expiry latches generic."""
    t, mgr = tracker
    _seed_active_job(mgr)
    t._vacuum_entities[_VAC] = {"error_message": "sensor.alfred_err",
                                "task_status": None}
    hass.states.async_set(_VAC, "error")
    hass.states.async_set("sensor.alfred_err", "unknown")
    t._handle_secondary_error_signal(_VAC)
    assert _VAC in t._grace_cancels
    # let the real 5s grace timer fire → _on_grace_expired latches generic
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done()
    latch = t.get_record(_VAC)["active_run_error"]
    assert latch is not None
    assert latch["current_message"] == "Unknown error during run"


# ---------------------------------------------------------------------------
# persist + notify
# ---------------------------------------------------------------------------

async def test_wired_event_routing(tracker, hass):
    """[ET-11] full wired path: a real error_message state change → rising latch."""
    t, mgr = tracker
    _seed_active_job(mgr)
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"error_message": "sensor.alfred_err",
                     "task_status": "sensor.alfred_task"},
    })
    hass.states.async_set("sensor.alfred_err", "normal")
    hass.states.async_set(_VAC, "cleaning")
    t.start([_VAC])
    # rising edge through the real listener
    hass.states.async_set("sensor.alfred_err", "Stuck")
    await hass.async_block_till_done()
    assert t.get_record(_VAC)["active_run_error"]["current_message"] == "Stuck"
    t.stop()


def test_secondary_error_via_task_status(tracker, hass):
    """[ET-14] task_status in 'error' counts as a secondary error channel."""
    t, mgr = tracker
    t._vacuum_entities[_VAC] = {"error_message": "sensor.alfred_err",
                                "task_status": "sensor.alfred_task"}
    hass.states.async_set(_VAC, "docked")          # vacuum NOT in error
    hass.states.async_set("sensor.alfred_task", "error")  # but task_status is
    assert t._is_in_secondary_error(_VAC) is True
    # both channels clear → no secondary error
    hass.states.async_set("sensor.alfred_task", "cleaning")
    assert t._is_in_secondary_error(_VAC) is False


async def test_secondary_clear_emits_falling_edge(tracker, hass):
    """[ET-12] secondary channels clear with empty message → falling edge fires."""
    t, mgr = tracker
    _seed_active_job(mgr)
    t._vacuum_entities[_VAC] = {"error_message": "sensor.alfred_err",
                                "task_status": None}
    # form an unrecovered latch first
    t._record_rising_edge(_VAC, message="Stuck", code=5, attribute_code=None)
    await hass.async_block_till_done()
    # vacuum no longer in error + message empty → falling edge via secondary path
    hass.states.async_set(_VAC, "docked")
    hass.states.async_set("sensor.alfred_err", "")
    t._handle_secondary_error_signal(_VAC)
    await hass.async_block_till_done()
    assert t.get_record(_VAC)["active_run_error"]["recovered"] is True


async def test_persist_and_notify(tracker, hass):
    """[ET-13]"""
    t, mgr = tracker
    seen: list[str] = []
    unsub = t.add_update_listener(lambda vid: seen.append(vid))
    t._persist_and_notify(_VAC)
    await hass.async_block_till_done()
    assert seen == [_VAC]
    mgr.async_save.assert_awaited()
    # unsub stops further notifications
    unsub()
    t._persist_and_notify(_VAC)
    await hass.async_block_till_done()
    assert seen == [_VAC]
