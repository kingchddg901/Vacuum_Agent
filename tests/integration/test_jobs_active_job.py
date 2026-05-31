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
"""

from __future__ import annotations

import pytest

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
