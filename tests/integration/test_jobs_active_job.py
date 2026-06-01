"""Integration tests for jobs/active_job.py — ActiveJobTracker methods that
read/write the core manager (data + hass). Driven by the `manager` fixture
with a seeded active job; no real robot-position entities required.

Coverage targets
----------------
[AJI-1]  get_active_job returns a normalized idle default when none is stored.
[AJI-2]  update_active_job_mop_wash_observation: counts + 60s debounce.
[AJI-3]  update_active_job_mop_wash_observation: idle job → no-op.
[AJI-4]  record_active_job_transition: appends; ignores same-state / empty.
[AJI-5]  record_active_job_transition: history capped at 12.
[AJI-6]  record_active_lifecycle_observed: sets the auto-finalize flag.
[AJI-7]  record_active_job_sensor_value: writes to in-flight jobs; False when none.
[AJI-8]  add_update_listener + _notify fires the callback.
[AJI-9]  update_active_job_recharge_observation: idle job → returned unchanged.
[AJI-10] update_active_job_recharge_observation: started job persists + returns.
[AJI-11] recharge: low-battery return sets pending; not charging → returns.
[AJI-12] recharge: pending + charging + not observed → starts recharge, pauses sampling.
[AJI-13] recharge: in-progress recharge that ends accumulates seconds, resumes sampling.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.const import DOMAIN
from custom_components.eufy_vacuum.jobs.active_job import ActiveJobTracker


_VAC = "vacuum.alfred"
_MAP = "6"


@pytest.fixture
def tracker(manager) -> ActiveJobTracker:
    return ActiveJobTracker(manager)


def _seed(manager, **extra) -> None:
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "status": "started",
        "vacuum_entity_id": _VAC,
        "map_id": _MAP,
        "started_at": "2026-01-01T09:00:00+00:00",
        **extra,
    }


# ---------------------------------------------------------------------------
# get_active_job
# ---------------------------------------------------------------------------

def test_get_active_job_default(tracker):
    """[AJI-1]"""
    job = tracker.get_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert job["status"] == "idle"
    assert job["resolved_rooms"] == []


# ---------------------------------------------------------------------------
# mop-wash observation
# ---------------------------------------------------------------------------

def test_mop_wash_count_and_debounce(tracker, manager):
    """[AJI-2]"""
    _seed(manager)
    tracker.update_active_job_mop_wash_observation(
        vacuum_entity_id=_VAC, map_id=_MAP, observed_at="2026-01-01T09:00:00+00:00")
    # within 60s → debounced, no increment
    tracker.update_active_job_mop_wash_observation(
        vacuum_entity_id=_VAC, map_id=_MAP, observed_at="2026-01-01T09:00:30+00:00")
    job = tracker.get_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert job["observed_mop_wash_count"] == 1
    # past the debounce → counts
    tracker.update_active_job_mop_wash_observation(
        vacuum_entity_id=_VAC, map_id=_MAP, observed_at="2026-01-01T09:02:00+00:00")
    job = tracker.get_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert job["observed_mop_wash_count"] == 2


def test_mop_wash_idle_noop(tracker, manager):
    """[AJI-3] no active job → status idle → returns without counting."""
    result = tracker.update_active_job_mop_wash_observation(
        vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["observed_mop_wash_count"] == 0


# ---------------------------------------------------------------------------
# transitions
# ---------------------------------------------------------------------------

def test_record_transition(tracker, manager):
    """[AJI-4]"""
    _seed(manager)
    tracker.record_active_job_transition(
        vacuum_entity_id=_VAC, map_id=_MAP, entity_id="sensor.t",
        from_state="cleaning", to_state="returning")
    # same-state ignored
    tracker.record_active_job_transition(
        vacuum_entity_id=_VAC, map_id=_MAP, entity_id="sensor.t",
        from_state="returning", to_state="returning")
    # empty to_state ignored
    tracker.record_active_job_transition(
        vacuum_entity_id=_VAC, map_id=_MAP, entity_id="sensor.t",
        from_state="returning", to_state="")
    job = tracker.get_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert len(job["state_transitions"]) == 1
    assert job["state_transitions"][0]["to_state"] == "returning"


def test_record_transition_caps_at_12(tracker, manager):
    """[AJI-5]"""
    _seed(manager)
    for i in range(15):
        tracker.record_active_job_transition(
            vacuum_entity_id=_VAC, map_id=_MAP, entity_id="sensor.t",
            from_state=f"s{i}", to_state=f"s{i + 1}")
    job = tracker.get_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert len(job["state_transitions"]) == 12


# ---------------------------------------------------------------------------
# lifecycle flag + sensor values
# ---------------------------------------------------------------------------

def test_record_lifecycle_observed(tracker, manager):
    """[AJI-6]"""
    _seed(manager)
    tracker.record_active_lifecycle_observed(vacuum_entity_id=_VAC, map_id=_MAP)
    assert manager.data["active_jobs"][_VAC][_MAP]["has_observed_active_lifecycle"] is True


def test_record_sensor_value(tracker, manager):
    """[AJI-7]"""
    _seed(manager)
    ok = tracker.record_active_job_sensor_value(
        vacuum_entity_id=_VAC, key="last_cleaning_time_seconds", value=1200)
    assert ok is True
    assert manager.data["active_jobs"][_VAC][_MAP]["last_cleaning_time_seconds"] == 1200
    # no active job for a different vacuum
    assert tracker.record_active_job_sensor_value(
        vacuum_entity_id="vacuum.other", key="x", value=1) is False


# ---------------------------------------------------------------------------
# listeners
# ---------------------------------------------------------------------------

def test_update_listener_notify(tracker):
    """[AJI-8]"""
    received: list[tuple[str, str]] = []
    tracker.add_update_listener(lambda v, m: received.append((v, m)))
    tracker._notify(_VAC, _MAP)
    assert received == [(_VAC, _MAP)]


# ---------------------------------------------------------------------------
# recharge observation
# ---------------------------------------------------------------------------

def test_recharge_idle_noop(tracker):
    """[AJI-9]"""
    result = tracker.update_active_job_recharge_observation(
        vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["status"] == "idle"


def test_recharge_started_persists(tracker, manager):
    """[AJI-10] a started job is processed and written back (no entities required)."""
    _seed(manager)
    result = tracker.update_active_job_recharge_observation(
        vacuum_entity_id=_VAC, map_id=_MAP, observed_at="2026-01-01T09:05:00+00:00")
    assert result["status"] == "started"
    assert _MAP in manager.data["active_jobs"][_VAC]


# ---------------------------------------------------------------------------
# recharge state machine
# ---------------------------------------------------------------------------

def test_recharge_low_battery_sets_pending(tracker, manager, monkeypatch):
    """[AJI-11] low-battery return arms pending; not charging yet → returns."""
    _seed(manager)
    monkeypatch.setattr(tracker, "_is_low_battery_return_state", lambda **kw: True)
    monkeypatch.setattr(tracker, "_is_charging", lambda v: False)
    result = tracker.update_active_job_recharge_observation(
        vacuum_entity_id=_VAC, map_id=_MAP, observed_at="2026-01-01T09:05:00+00:00")
    assert result["pending_mid_job_recharge_return"] is True


def test_recharge_starts_and_pauses(hass, tracker, manager, monkeypatch):
    """[AJI-12] pending + charging + not yet observed → recharge begins, sampling pauses."""
    _seed(manager)
    monkeypatch.setattr(tracker, "_is_low_battery_return_state", lambda **kw: True)
    monkeypatch.setattr(tracker, "_is_charging", lambda v: True)
    fake_tracker = MagicMock()
    hass.data[DOMAIN]["mapping_tracker"] = fake_tracker

    result = tracker.update_active_job_recharge_observation(
        vacuum_entity_id=_VAC, map_id=_MAP, observed_at="2026-01-01T09:05:00+00:00")
    assert result["observed_mid_job_recharge"] is True
    assert result["observed_mid_job_recharge_count"] == 1
    assert result["pending_mid_job_recharge_return"] is False
    fake_tracker.pause_sampling.assert_called_once_with(_VAC)


def test_recharge_ends_accumulates(hass, tracker, manager, monkeypatch):
    """[AJI-13] an in-progress recharge that has ended accumulates seconds + resumes."""
    _seed(
        manager,
        pending_mid_job_recharge_return=True,
        observed_mid_job_recharge=True,
        observed_mid_job_recharge_started_at="2026-01-01T09:00:00+00:00",
        recharge_seconds_accumulated=0,
    )
    monkeypatch.setattr(tracker, "_is_low_battery_return_state", lambda **kw: False)
    # First charging check (gate) True; second (recharge-ended check) False.
    monkeypatch.setattr(tracker, "_is_charging", MagicMock(side_effect=[True, False]))
    fake_tracker = MagicMock()
    hass.data[DOMAIN]["mapping_tracker"] = fake_tracker

    result = tracker.update_active_job_recharge_observation(
        vacuum_entity_id=_VAC, map_id=_MAP, observed_at="2026-01-01T09:05:00+00:00")
    assert result["observed_mid_job_recharge"] is False
    assert result["recharge_seconds_accumulated"] == 300  # 5 min
    fake_tracker.resume_sampling.assert_called_once_with(_VAC)


# ---------------------------------------------------------------------------
# pause / resume
# ---------------------------------------------------------------------------

def test_pause_active_job(tracker, manager):
    """[AJI-14] started → paused; non-started is a no-op."""
    _seed(manager)
    job = tracker.pause_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP, paused_at="2026-01-01T09:10:00+00:00")
    assert job["status"] == "paused"
    assert job["paused_at"] == "2026-01-01T09:10:00+00:00"
    # already paused → not "started" → returns unchanged (still paused)
    again = tracker.pause_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert again["status"] == "paused"
    assert again["paused_at"] == "2026-01-01T09:10:00+00:00"


def test_resume_accumulates_paused_seconds(tracker, manager):
    """[AJI-15] resume adds the paused wall-clock delta to the running total."""
    _seed(
        manager, status="paused",
        paused_at="2026-01-01T09:00:00+00:00",
        paused_duration_seconds=10,
        current_room_paused_seconds=5,
    )
    job = tracker.resume_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP,
        resumed_at="2026-01-01T09:00:30+00:00")
    assert job["status"] == "started"
    assert job["paused_at"] is None
    # prior 10s + 30s paused delta
    assert job["paused_duration_seconds"] == 40
    # prior 5s + 30s delta
    assert job["current_room_paused_seconds"] == 35


def test_resume_non_paused_noop(tracker, manager):
    """[AJI-16] resume on a started job returns it unchanged."""
    _seed(manager)
    job = tracker.resume_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert job["status"] == "started"
    assert "paused_duration_seconds" not in job or job["paused_duration_seconds"] == 0


# ---------------------------------------------------------------------------
# completed-room recording
# ---------------------------------------------------------------------------

def test_record_completed_room_dedup_and_advance(tracker, manager):
    """[AJI-17] completing a room dedups, advances current room, caps the list."""
    _seed(manager, queue_room_ids=[1, 2, 3])
    tracker.record_completed_room(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1, room_name="Kitchen")
    # duplicate completion of room 1 → still one entry
    tracker.record_completed_room(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1, room_name="Kitchen")
    job = tracker.get_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert job["completed_room_ids"] == [1]
    assert len([r for r in job["completed_rooms"] if r["room_id"] == 1]) == 1
    # next pending room becomes current
    assert job["current_room_id"] == 2


def test_record_completed_room_idle_noop(tracker, manager):
    """[AJI-18] no active job (idle) → nothing recorded."""
    job = tracker.record_completed_room(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1)
    assert job.get("completed_room_ids", []) == []


# ---------------------------------------------------------------------------
# finalization summary extraction
# ---------------------------------------------------------------------------

def test_mark_finalized_with_result(tracker, manager):
    """[AJI-19] finalize_result is unpacked into a compact summary."""
    _seed(manager)
    finalize_result = {
        "job_id": "j1", "job_path": "/x/j1.json",
        "completed_job": {
            "finalized_at": "2026-01-01T10:00:00+00:00",
            "outcome": {
                "used_for_learning": True, "sanity_passed": True,
                "sanity_flags": ["ok"], "learning_blockers": [],
                "status": "completed"},
        },
    }
    job = tracker.mark_active_job_finalized(
        vacuum_entity_id=_VAC, map_id=_MAP, finalize_result=finalize_result)
    assert job["status"] == "completed"
    assert job["finalized"] is True
    assert job["finalized_at"] == "2026-01-01T10:00:00+00:00"
    s = job["finalize_summary"]
    assert s["job_id"] == "j1"
    assert s["used_for_learning"] is True
    assert s["status"] == "completed"


def test_mark_finalized_without_result(tracker, manager):
    """[AJI-20] None finalize_result still marks finalized, no summary."""
    _seed(manager)
    job = tracker.mark_active_job_finalized(
        vacuum_entity_id=_VAC, map_id=_MAP, finalize_result=None)
    assert job["finalized"] is True
    assert job["finalized_at"] is None
    assert "finalize_summary" not in job


# ---------------------------------------------------------------------------
# async_cancel_active_job — return-to-base + terminal-state polling
# ---------------------------------------------------------------------------

def _register_rtb(hass) -> list:
    calls = []

    async def _handler(call):
        calls.append(call)

    hass.services.async_register("vacuum", "return_to_base", _handler)
    return calls


async def test_cancel_no_active_job(tracker):
    """[AJI-21] idle job → cancelled False, no_active_job."""
    out = await tracker.async_cancel_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["cancelled"] is False
    assert out["reason"] == "no_active_job"


async def test_cancel_confirmed(tracker, manager, hass, monkeypatch):
    """[AJI-22] device reaches a terminal state → confirmed cancel + finalize."""
    monkeypatch.setattr(type(tracker), "_CANCEL_CONFIRM_TIMEOUT_S", 1)
    monkeypatch.setattr(type(tracker), "_CANCEL_POLL_INTERVAL_S", 0.01)
    _seed(manager, queue_room_ids=[1])
    hass.states.async_set(_VAC, "docked")   # terminal on the first poll
    calls = _register_rtb(hass)

    out = await tracker.async_cancel_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["cancelled"] is True
    assert out["confirmed"] is True
    assert len(calls) == 1
    # active job marked finalized
    assert manager.data["active_jobs"][_VAC][_MAP]["finalized"] is True


async def test_cancel_timeout(tracker, manager, hass, monkeypatch):
    """[AJI-23] no terminal state within the window → finalize anyway, confirmed False."""
    monkeypatch.setattr(type(tracker), "_CANCEL_CONFIRM_TIMEOUT_S", 0.05)
    monkeypatch.setattr(type(tracker), "_CANCEL_POLL_INTERVAL_S", 0.01)
    _seed(manager, queue_room_ids=[1])
    hass.states.async_set(_VAC, "cleaning")  # never reaches docked/idle
    _register_rtb(hass)

    out = await tracker.async_cancel_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["cancelled"] is True
    assert out["confirmed"] is False
