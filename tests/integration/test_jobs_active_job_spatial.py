"""Integration tests for jobs/active_job.py — the spatial / transition-room
pipeline: robot-position reads, bounds checks, timing rollover, and charging.

Driven by the `manager` fixture. The capability lookup is stubbed so
_get_robot_position's entity-resolution + state-read logic is exercised without
the full detection stack; the rollover paths use a seeded active job.

Coverage targets
----------------
[AJS-1]  _get_robot_position: reads x/y sensors; None on missing/non-numeric.
[AJS-2]  _robot_outside_room_bounds: inside → False, outside → True, no manager → None.
[AJS-3]  _detect_transition_room_from_position: None guards.
[AJS-4]  _maybe_roll_current_room_by_timing: slow-room rollover fires EVENT_ROOM_FINISHED.
[AJS-5]  _maybe_roll_current_room_by_timing: fast-room (_pending_fast_rollover) fires.
[AJS-6]  _maybe_roll_current_room_by_timing: not-started / last-room → no-op.
[AJS-7]  _is_low_battery_return_state delegates to the adapter impl.
[AJS-8]  _is_charging returns a bool.
[AJS-9]  _maybe_roll_current_room_by_timing: flat-area transit hop rolls room live (transit-aware) below the timing threshold.
[AJS-10] _maybe_roll_current_room_by_timing: live_transition.enabled=False falls back to legacy → transit hop does not roll (kill-switch).
[AJS-11] _maybe_roll_current_room_by_timing: wash plateau rolls live (baseline, unchanged from legacy).
[AJS-12] _maybe_roll_current_room_by_timing: short flat-area pass-turn blip is not a boundary → no roll.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from custom_components.eufy_vacuum.const import DOMAIN
from custom_components.eufy_vacuum.jobs.active_job import (
    ActiveJobTracker,
    _LIVE_TRANSITION_DEFAULTS,
)
from custom_components.eufy_vacuum.mapping.manager import MappingManager


_VAC = "vacuum.alfred"
_MAP = "6"
_EVENT_ROOM_FINISHED = "eufy_vacuum_room_finished"


@pytest.fixture
def tracker(manager) -> ActiveJobTracker:
    return ActiveJobTracker(manager)


def _stub_caps(manager, monkeypatch, *, x="sensor.alfred_x", y="sensor.alfred_y"):
    monkeypatch.setattr(
        manager, "get_vacuum_capabilities",
        lambda **kw: {"entities": {"robot_position_x": x, "robot_position_y": y}})


# ---------------------------------------------------------------------------
# _get_robot_position
# ---------------------------------------------------------------------------

def test_get_robot_position(hass, tracker, manager, monkeypatch):
    """[AJS-1]"""
    _stub_caps(manager, monkeypatch)
    hass.states.async_set("sensor.alfred_x", "10")
    hass.states.async_set("sensor.alfred_y", "20")
    assert tracker._get_robot_position(_VAC) == (10.0, 20.0)


def test_get_robot_position_non_numeric(hass, tracker, manager, monkeypatch):
    """[AJS-1]"""
    _stub_caps(manager, monkeypatch)
    hass.states.async_set("sensor.alfred_x", "unknown")
    hass.states.async_set("sensor.alfred_y", "20")
    assert tracker._get_robot_position(_VAC) is None


def test_get_robot_position_missing_entity(tracker, manager, monkeypatch):
    """[AJS-1]"""
    monkeypatch.setattr(manager, "get_vacuum_capabilities", lambda **kw: {"entities": {}})
    assert tracker._get_robot_position(_VAC) is None


# ---------------------------------------------------------------------------
# _robot_outside_room_bounds
# ---------------------------------------------------------------------------

def test_robot_outside_room_bounds(hass, tracker, manager, monkeypatch):
    """[AJS-2]"""
    mm = MappingManager(hass)
    mm.update_room_bounds(
        vacuum_entity_id=_VAC, map_id=_MAP,
        samples=[(0.0, 0.0), (20.0, 20.0)], rooms={"3": {"is_transition": False}})
    hass.data[DOMAIN]["mapping_manager"] = mm

    monkeypatch.setattr(tracker, "_get_robot_position", lambda v: (10.0, 10.0))
    assert tracker._robot_outside_room_bounds(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=3) is False

    monkeypatch.setattr(tracker, "_get_robot_position", lambda v: (5000.0, 5000.0))
    assert tracker._robot_outside_room_bounds(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=3) is True


def test_robot_outside_no_manager(tracker, monkeypatch):
    """[AJS-2] no mapping manager registered → None."""
    monkeypatch.setattr(tracker, "_get_robot_position", lambda v: (10.0, 10.0))
    assert tracker._robot_outside_room_bounds(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=3) is None


# ---------------------------------------------------------------------------
# _detect_transition_room_from_position
# ---------------------------------------------------------------------------

def test_detect_transition_none_guards(tracker, monkeypatch):
    """[AJS-3]"""
    assert tracker._detect_transition_room_from_position(
        vacuum_entity_id=_VAC, map_id=_MAP, from_room_id=None, to_room_id=2) is None
    monkeypatch.setattr(tracker, "_get_robot_position", lambda v: None)
    assert tracker._detect_transition_room_from_position(
        vacuum_entity_id=_VAC, map_id=_MAP, from_room_id=1, to_room_id=2) is None


# room 1 → room 2 → room 3 access-graph chain
_GRAPH = {"rooms": {
    "1": {"room_id": 1, "grants_access_to": [2]},
    "2": {"room_id": 2, "grants_access_to": [3]},
    "3": {"room_id": 3, "grants_access_to": []},
}}


def test_detect_transition_positive(hass, tracker, manager, monkeypatch):
    """[AJS-3] robot sits in the intermediate transition room (2) on the 1→3 path."""
    monkeypatch.setattr(tracker, "_get_robot_position", lambda v: (10.0, 10.0))
    monkeypatch.setattr(manager, "get_managed_rooms", lambda **kw: _GRAPH)

    mm = MappingManager(hass)
    mm.update_room_bounds(
        vacuum_entity_id=_VAC, map_id="trans",
        samples=[(0.0, 0.0), (20.0, 20.0)], rooms={"2": {"is_transition": False}})
    hass.data[DOMAIN]["mapping_manager"] = mm

    result = tracker._detect_transition_room_from_position(
        vacuum_entity_id=_VAC, map_id="trans", from_room_id=1, to_room_id=3)
    assert result == 2


def test_detect_transition_direct_adjacent(tracker, manager, monkeypatch):
    """[AJS-3] directly adjacent rooms → no intermediate → None."""
    monkeypatch.setattr(tracker, "_get_robot_position", lambda v: (10.0, 10.0))
    monkeypatch.setattr(manager, "get_managed_rooms",
                        lambda **kw: {"rooms": {"1": {"room_id": 1, "grants_access_to": [3]},
                                                "3": {"room_id": 3, "grants_access_to": []}}})
    assert tracker._detect_transition_room_from_position(
        vacuum_entity_id=_VAC, map_id=_MAP, from_room_id=1, to_room_id=3) is None


def test_detect_transition_no_bounds(hass, tracker, manager, monkeypatch):
    """[AJS-3] a path exists but the transition room has no learned bounds → None."""
    monkeypatch.setattr(tracker, "_get_robot_position", lambda v: (10.0, 10.0))
    monkeypatch.setattr(manager, "get_managed_rooms", lambda **kw: _GRAPH)
    hass.data[DOMAIN]["mapping_manager"] = MappingManager(hass)  # empty, no bounds
    assert tracker._detect_transition_room_from_position(
        vacuum_entity_id=_VAC, map_id="nobounds", from_room_id=1, to_room_id=3) is None


# ---------------------------------------------------------------------------
# _maybe_roll_current_room_by_timing
# ---------------------------------------------------------------------------

def _active_job(**extra) -> dict:
    return {
        "status": "started", "job_id": "j1", "current_room_id": 1,
        "resolved_rooms": [{"room_id": 1, "name": "Kitchen"}, {"room_id": 2, "name": "Bath"}],
        "queue_room_ids": [1, 2], "queue_rooms": [{"room_id": 1}, {"room_id": 2}],
        "completed_room_ids": [], **extra,
    }


_TIMELINE = [
    {"room_id": 1, "minutes": 5.0, "confidence_score": 0.5},
    {"room_id": 2, "minutes": 5.0, "confidence_score": 0.5},
]


def _seed_job(manager, job) -> dict:
    """Store the job so record_completed_room (which reads manager.data) sees it."""
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = job
    return job


async def test_maybe_roll_slow_path(hass, tracker, manager):
    """[AJS-4] elapsed >> threshold, bounds unavailable → timing_rollover fires."""
    events: list = []
    hass.bus.async_listen(_EVENT_ROOM_FINISHED, lambda e: events.append(e.data))
    job = _seed_job(manager, _active_job())
    result = tracker._maybe_roll_current_room_by_timing(
        vacuum_entity_id=_VAC, map_id=_MAP, active_job=job,
        raw_timeline=_TIMELINE, current_room_id=1,
        current_room_elapsed_minutes=100.0, completed_room_ids=[])
    await hass.async_block_till_done()
    assert 1 in result.get("completed_room_ids", [])
    assert any(d["source"] == "timing_rollover" for d in events)


async def test_maybe_roll_fast_path(hass, tracker, manager):
    """[AJS-5] below threshold + a pending fast-rollover signal → bounds_exit_early."""
    events: list = []
    hass.bus.async_listen(_EVENT_ROOM_FINISHED, lambda e: events.append(e.data))
    job = _seed_job(manager, _active_job(_pending_fast_rollover={"room_id": 1}))
    result = tracker._maybe_roll_current_room_by_timing(
        vacuum_entity_id=_VAC, map_id=_MAP, active_job=job,
        raw_timeline=_TIMELINE, current_room_id=1,
        current_room_elapsed_minutes=2.0, completed_room_ids=[])
    await hass.async_block_till_done()
    assert any(d["source"] == "bounds_exit_early" for d in events)
    assert "_pending_fast_rollover" not in result


def test_maybe_roll_noop(tracker):
    """[AJS-6] not started, or current room is the last unresolved → unchanged."""
    not_started = tracker._maybe_roll_current_room_by_timing(
        vacuum_entity_id=_VAC, map_id=_MAP, active_job=_active_job(status="idle"),
        raw_timeline=_TIMELINE, current_room_id=1,
        current_room_elapsed_minutes=100.0, completed_room_ids=[])
    assert not_started.get("completed_room_ids") == []

    last = tracker._maybe_roll_current_room_by_timing(
        vacuum_entity_id=_VAC, map_id=_MAP, active_job=_active_job(current_room_id=2),
        raw_timeline=_TIMELINE, current_room_id=2,
        current_room_elapsed_minutes=100.0, completed_room_ids=[])
    assert last.get("completed_room_ids") == []


# ---------------------------------------------------------------------------
# _maybe_roll_current_room_by_timing — counter-transition (live) rollover
# ---------------------------------------------------------------------------

_CB = datetime(2026, 6, 8, 12, 0, 0)


def _cs(sec: int, ct: float, ca: float) -> dict:
    return {"t": _CB + timedelta(seconds=sec), "cleaning_time": ct, "cleaning_area": ca, "battery": 100}


# room 1 (area->3), a 70 s flat-area transit hop, room 2 (area still lagging flat)
_TRANSIT_SAMPLES = [
    _cs(0, 0, 0), _cs(30, 30, 1), _cs(60, 60, 2), _cs(90, 90, 3),
    _cs(160, 120, 3),
    _cs(190, 150, 3), _cs(220, 180, 3),
]
# room 1, a 310 s wash plateau, room 2
_WASH_SAMPLES = [
    _cs(0, 0, 0), _cs(30, 30, 1), _cs(60, 60, 2), _cs(90, 90, 3),
    _cs(400, 120, 4), _cs(430, 150, 6),
]


async def test_counter_transit_rolls_live(hass, tracker, manager):
    """[AJS-9] A 60-90 s flat-area transit hop now rolls the room live (transit-aware),
    where the legacy wash/area_jump-only path would not. elapsed is below the timing
    threshold, so the roll is attributable to the counter signal."""
    events: list = []
    hass.bus.async_listen(_EVENT_ROOM_FINISHED, lambda e: events.append(e.data))
    job = _seed_job(manager, _active_job(counter_samples=_TRANSIT_SAMPLES))
    result = tracker._maybe_roll_current_room_by_timing(
        vacuum_entity_id=_VAC, map_id=_MAP, active_job=job,
        raw_timeline=_TIMELINE, current_room_id=1,
        current_room_elapsed_minutes=2.0, completed_room_ids=[])
    await hass.async_block_till_done()
    assert 1 in result.get("completed_room_ids", [])
    assert any(d["source"] == "counter_plateau" for d in events)


async def test_counter_transit_killswitch_no_roll(hass, tracker, manager, monkeypatch):
    """[AJS-10] live_transition.enabled=False falls back to the legacy segmentation, so
    the transit hop does NOT roll (no transit band) — proves the gate + kill-switch."""
    monkeypatch.setattr(
        tracker, "_live_transition_config",
        lambda v: {**_LIVE_TRANSITION_DEFAULTS, "enabled": False},
    )
    job = _seed_job(manager, _active_job(counter_samples=_TRANSIT_SAMPLES))
    result = tracker._maybe_roll_current_room_by_timing(
        vacuum_entity_id=_VAC, map_id=_MAP, active_job=job,
        raw_timeline=_TIMELINE, current_room_id=1,
        current_room_elapsed_minutes=2.0, completed_room_ids=[])
    assert result.get("completed_room_ids", []) == []


async def test_counter_wash_rolls_live(hass, tracker, manager):
    """[AJS-11] Baseline: a wash plateau rolls live (unchanged from the legacy path)."""
    events: list = []
    hass.bus.async_listen(_EVENT_ROOM_FINISHED, lambda e: events.append(e.data))
    job = _seed_job(manager, _active_job(counter_samples=_WASH_SAMPLES))
    result = tracker._maybe_roll_current_room_by_timing(
        vacuum_entity_id=_VAC, map_id=_MAP, active_job=job,
        raw_timeline=_TIMELINE, current_room_id=1,
        current_room_elapsed_minutes=2.0, completed_room_ids=[])
    await hass.async_block_till_done()
    assert 1 in result.get("completed_room_ids", [])
    assert any(d["source"] == "counter_plateau" for d in events)


async def test_counter_multipass_does_not_overroll(hass, tracker, manager):
    """[AJS-12] A short flat-area pass-turn (weak blip) is not a boundary — no roll."""
    samples = [
        _cs(0, 0, 0), _cs(30, 30, 1), _cs(60, 60, 2), _cs(90, 90, 3),
        _cs(130, 120, 3), _cs(160, 150, 3), _cs(190, 180, 3),
    ]
    job = _seed_job(manager, _active_job(counter_samples=samples))
    result = tracker._maybe_roll_current_room_by_timing(
        vacuum_entity_id=_VAC, map_id=_MAP, active_job=job,
        raw_timeline=_TIMELINE, current_room_id=1,
        current_room_elapsed_minutes=2.0, completed_room_ids=[])
    assert result.get("completed_room_ids", []) == []


# ---------------------------------------------------------------------------
# charging helpers
# ---------------------------------------------------------------------------

def test_is_low_battery_return_state(tracker):
    """[AJS-7] delegates to the adapter impl (smoke over explicit args)."""
    result = tracker._is_low_battery_return_state(
        vacuum_entity_id=_VAC,
        current_battery=15, vacuum_state="returning", task_status="recharge")
    assert isinstance(result, bool)


def test_is_charging(tracker):
    """[AJS-8]"""
    assert isinstance(tracker._is_charging(_VAC), bool)
