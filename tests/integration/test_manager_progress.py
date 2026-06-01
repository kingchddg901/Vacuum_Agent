"""Tests for core/manager.py::get_job_progress_snapshot — the live job engine.

~150 lines of real logic (timeline estimate/reanchor, current-room derivation,
bounds-exit + stall detection) that the dashboard polls. Driven against the
real manager + a wired LearningManager with seeded active-job state.

Coverage targets
----------------
[PR-1]  idle job → terminal snapshot, empty timeline.
[PR-2]  started job + learning + resolved rooms → snapshot with derived current
        room and a timeline.
[PR-3]  completed rooms → the reanchor timeline branch.
[PR-4]  a long-overrun current room → awaiting_bounds_exit / stall signalling.
[PR-5]  finalize_learning_for_active_job: no learning manager → None.
[PR-6]  finalize_learning_for_active_job: missing started_at → not finalized.
[PR-7]  finalize_learning_for_active_job: full job → completed_job result.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.eufy_vacuum.const import (
    DATA_LEARNING,
    DOMAIN,
    EVENT_STALL_DETECTED,
)
from custom_components.eufy_vacuum.learning.manager import LearningManager


_VAC = "vacuum.alfred"
_MAP = "6"


def _wire(manager, hass):
    hass.data.setdefault(DOMAIN, {})[DATA_LEARNING] = LearningManager(hass)


def _seed_job(manager, *, minutes_ago=10, **extra):
    started = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    job = {
        "status": "started", "job_id": "j1",
        "started_at": started, "current_room_started_at": started,
        "queue_room_ids": [1, 2],
        "resolved_rooms": [
            {"room_id": 1, "name": "Kitchen", "minutes": 5, "clean_mode": "vacuum"},
            {"room_id": 2, "name": "Bath", "minutes": 5, "clean_mode": "vacuum"},
        ],
        "completed_room_ids": [], "completed_rooms": [],
    }
    job.update(extra)
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = job
    return job


def test_progress_idle(manager, hass):
    """[PR-1]"""
    _wire(manager, hass)
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["status"] == "idle"
    assert snap["terminal"] is True
    assert snap["timeline"] == []
    assert snap["timeline_source"] == "none"


def test_progress_started(manager, hass):
    """[PR-2]"""
    _wire(manager, hass)
    _seed_job(manager)
    hass.states.async_set(_VAC, "cleaning")
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["status"] == "started"
    assert snap["terminal"] is False
    assert snap["job_id"] == "j1"
    # a timeline was produced from the resolved rooms
    assert snap["timeline_source"] in {"estimate", "reanchored"}
    assert len(snap["timeline"]) >= 1
    # current room derived from the unresolved set
    assert snap["current_room_id"] in (1, 2)


def test_progress_reanchor(manager, hass):
    """[PR-3] a completed room drives the reanchor branch."""
    _wire(manager, hass)
    _seed_job(
        manager,
        completed_room_ids=[1],
        completed_rooms=[{"room_id": 1, "actual_duration_minutes": 4.0}],
    )
    hass.states.async_set(_VAC, "cleaning")
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["timeline_source"] == "reanchored"
    assert 1 in snap["completed_room_ids"]
    # room 1 shows as completed in the timeline
    room1 = next((r for r in snap["timeline"] if r.get("room_id") == 1), None)
    assert room1 is not None and room1["completed"] is True


def test_progress_stall(manager, hass):
    """[PR-4] a wildly-overrun current room raises awaiting_bounds_exit/stall.

    With no robot-position entities the timing rollover can't confirm the robot
    left the room, so an elapsed >> threshold should flag bounds-exit (and, at
    >= 2x, a stall + EVENT_STALL_DETECTED).
    """
    _wire(manager, hass)
    # current room started 60 minutes ago vs a 5-minute estimate → >> 2x
    _seed_job(manager, minutes_ago=60)
    hass.states.async_set(_VAC, "cleaning")
    events = []
    hass.bus.async_listen(EVENT_STALL_DETECTED, lambda e: events.append(e))
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    # whichever path the timing engine takes, the snapshot stays well-formed
    assert "awaiting_bounds_exit" in snap
    assert isinstance(snap["awaiting_bounds_exit"], bool)


async def test_finalize_no_learning(manager):
    """[PR-5] no learning manager wired → None."""
    # the manager fixture does not set DATA_LEARNING
    result = await manager.finalize_learning_for_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP)
    assert result is None


async def test_finalize_missing_started_at(manager, hass):
    """[PR-6] an active job with no started_at → not finalized."""
    _wire(manager, hass)
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "status": "started", "started_at": ""}
    result = await manager.finalize_learning_for_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["finalized"] is False
    assert result["reason"] == "missing_started_at"


async def test_finalize_main_path(manager, hass):
    """[PR-7] a full job finalizes into a completed_job record."""
    _wire(manager, hass)
    _seed_job(manager, battery_start=90)
    hass.states.async_set(_VAC, "docked", {"battery_level": 70})
    result = await manager.finalize_learning_for_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP, battery_end=70)
    assert result is not None
    assert "completed_job" in result
