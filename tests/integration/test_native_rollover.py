"""Tests for native current_room rollover (Wave 3).

Roborock reports the live room directly (sensor.{id}_current_room, a NAME). The
framework follows that signal — filtered to the job's target rooms, matched by
name slug, order-agnostic — instead of Eufy's counter-plateau heuristic. Driven
by ActiveJobTracker._maybe_roll_current_room_by_native_signal, gated by the
adapter's live_transition.native_transition_source (Eufy defaults False).

Coverage targets
----------------
[NR-1] transit room (not a job target) -> ignored, no advance.
[NR-2] sentinel ("unknown") -> ignored.
[NR-3] first signal == the queue guess -> confirmed, no completion, no dup event.
[NR-4] first signal != the guess (device started elsewhere) -> adopt, complete NOTHING.
[NR-5] move to a new target -> previous confirmed target completed, current set directly.
[NR-6] same target again -> no-op (idempotent across the 5s tick).
[NR-7] a target already completed -> ignored (no re-advance; rooms_unique_per_job).
[NR-8] config gate: native_transition_source True for Roborock, default False otherwise.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import (
    clear_registry,
    register_adapter_config,
)
from custom_components.eufy_vacuum.jobs.active_job import ActiveJobTracker


_VAC = "vacuum.ivy"
_MAP = "Main floor"
_SIGNAL = "sensor.ivy_current_room"

# (room_id, name, slug)
_QUEUE = [
    (16, "KITCHEN", "kitchen"),
    (17, "Dining Room", "dining_room"),
    (20, "Heidi & Chris", "heidi_and_chris"),
]


@pytest.fixture
def tracker(manager) -> ActiveJobTracker:
    return ActiveJobTracker(manager)


def _register(native: bool = True):
    clear_registry()
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "entities": {"active_cleaning_target": _SIGNAL},
        "live_transition": {"enabled": True, "native_transition_source": native},
    })


def _seed(manager, *, current, completed=None, native_confirmed=None):
    job = {
        "status": "started", "vacuum_entity_id": _VAC, "map_id": _MAP,
        "job_id": "job1", "started_at": "2026-01-01T09:00:00+00:00",
        "queue_room_ids": [r[0] for r in _QUEUE],
        "resolved_rooms": [{"room_id": r[0], "name": r[1], "slug": r[2]} for r in _QUEUE],
        "completed_room_ids": list(completed or []),
        "current_room_id": current,
        "current_room_started_at": "2026-01-01T09:00:00+00:00",
    }
    if native_confirmed is not None:
        job["_native_current_room_id"] = native_confirmed
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = job
    return job


async def _roll(tracker, manager, job, signal_name):
    manager.hass.states.async_set(_SIGNAL, signal_name)
    await manager.hass.async_block_till_done()
    result = tracker._maybe_roll_current_room_by_native_signal(
        vacuum_entity_id=_VAC, map_id=_MAP, active_job=job,
        current_room_id=job.get("current_room_id"),
        current_room_elapsed_minutes=5.0,
    )
    await manager.hass.async_block_till_done()
    return result


async def test_transit_room_ignored(tracker, manager):
    """[NR-1] a name not among the job targets does not advance."""
    _register()
    job = _seed(manager, current=16, native_confirmed=16)
    result = await _roll(tracker, manager, job, "LIVINGROOM")  # not a target
    assert result["current_room_id"] == 16
    assert result["completed_room_ids"] == []


async def test_sentinel_ignored(tracker, manager):
    """[NR-2]"""
    _register()
    job = _seed(manager, current=16, native_confirmed=16)
    result = await _roll(tracker, manager, job, "unknown")
    assert result["current_room_id"] == 16


async def test_first_signal_matches_guess(tracker, manager):
    """[NR-3] device started with the queue-first room -> confirm only."""
    _register()
    job = _seed(manager, current=16)  # no native_confirmed yet
    result = await _roll(tracker, manager, job, "KITCHEN")  # == current guess (16)
    assert result["current_room_id"] == 16
    assert result["_native_current_room_id"] == 16
    assert result["completed_room_ids"] == []  # nothing completed


async def test_first_signal_differs_from_guess(tracker, manager):
    """[NR-4] device started elsewhere -> adopt the real room, complete NOTHING
    (the queue-first guess was never cleaned)."""
    _register()
    job = _seed(manager, current=16)  # guess = 16
    result = await _roll(tracker, manager, job, "Dining Room")  # device started in 17
    assert result["current_room_id"] == 17
    assert result["_native_current_room_id"] == 17
    assert result["completed_room_ids"] == []  # 16 NOT phantom-completed


async def test_move_to_new_target_completes_previous(tracker, manager):
    """[NR-5] signal moves off the confirmed target -> that target completes,
    current set directly to the new one (order-agnostic)."""
    _register()
    job = _seed(manager, current=16, native_confirmed=16)
    result = await _roll(tracker, manager, job, "Heidi & Chris")  # jump to 20
    assert result["completed_room_ids"] == [16]
    assert result["current_room_id"] == 20
    assert result["_native_current_room_id"] == 20


async def test_same_target_noop(tracker, manager):
    """[NR-6] re-reading the same room (5s tick on a 30s signal) does nothing."""
    _register()
    job = _seed(manager, current=17, native_confirmed=17, completed=[16])
    result = await _roll(tracker, manager, job, "Dining Room")  # still 17
    assert result["current_room_id"] == 17
    assert result["completed_room_ids"] == [16]


async def test_already_completed_target_ignored(tracker, manager):
    """[NR-7] a signal for an already-finished room never re-advances."""
    _register()
    job = _seed(manager, current=17, native_confirmed=17, completed=[16])
    result = await _roll(tracker, manager, job, "KITCHEN")  # 16, already done
    assert result["current_room_id"] == 17
    assert result["completed_room_ids"] == [16]


def test_config_gate(manager):
    """[NR-8] the native flag is on for Roborock and defaults off otherwise."""
    tracker = ActiveJobTracker(manager)
    _register(native=True)
    assert tracker._live_transition_config(_VAC)["native_transition_source"] is True
    _register(native=False)
    assert tracker._live_transition_config(_VAC)["native_transition_source"] is False
    # No live_transition block at all -> default False (Eufy path).
    clear_registry()
    register_adapter_config(_VAC, {"adapter_id": "eufy", "source": "code", "entities": {}})
    assert tracker._live_transition_config(_VAC)["native_transition_source"] is False
