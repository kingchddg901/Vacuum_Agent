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
[AJI-14] pause_active_job: started → paused; non-started is a no-op.
[AJI-15] resume_active_job: adds the paused wall-clock delta to the running total.
[AJI-16] resume_active_job: a started (non-paused) job is returned unchanged.
[AJI-17] record_completed_room: dedups, advances current room, caps the list.
[AJI-18] record_completed_room: idle job → nothing recorded.
[AJI-19] mark_active_job_finalized: finalize_result unpacked into a compact summary.
[AJI-20] mark_active_job_finalized: None result still finalizes, no summary.
[AJI-21] async_cancel_active_job: idle job → cancelled False, no_active_job.
[AJI-22] async_cancel_active_job: terminal state reached → confirmed cancel + finalize.
[AJI-23] async_cancel_active_job: no terminal state in window → finalize anyway, confirmed False.
[AJI-24] mop-wash: unparseable last-wash timestamp falls through debounce and still counts.
[AJI-25] async_pause_active_job: nothing started → paused False, no_started_job, no service call.
[AJI-26] async_pause_active_job: started job → vacuum.pause dispatched + job paused.
[AJI-27] async_resume_active_job: non-paused job → resumed False, no_paused_job, no service call.
[AJI-28] async_resume_active_job: paused job → vacuum.start dispatched + job started.
[AJI-29] get_paused_job_timeout_report: started (non-paused) job → None.
[AJI-30] get_paused_job_timeout_report: paused with 0-minute timeout opts out → None.
[AJI-31] get_paused_job_timeout_report: paused but under the limit → None.
[AJI-32] get_paused_job_timeout_report: paused beyond the limit → populated escalation report.
[AJI-33] get_paused_job_timeout_report: unparseable paused_at → None (no crash).
[AJI-34] _timing_completion_threshold_minutes: lower confidence → larger overrun slack; sample-count + drift bonuses, capped.
[AJI-35] _timing_completion_threshold_minutes: the 2-or-3-sample bracket adds 0.5 slack (between the <=1 +1.0 and well-sampled 0.0).
[AJI-35] _job_status_summary: status string covers each lifecycle/outcome branch.
[AJI-36] _job_status_summary: a started job names the current room from resolved_rooms.
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
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "eufy_test", "source": "code",
        "dock_events": {"debounce_seconds": {"last_mop_wash": 60}},
    })
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


def test_mop_wash_malformed_timestamp_counts(tracker, manager):
    """[AJI-24] an unparseable last-wash timestamp falls through the debounce
    (except branch) and still counts the wash rather than crashing."""
    _seed(manager, observed_mop_wash_last_at="not-a-timestamp",
          observed_mop_wash_count=0)
    job = tracker.update_active_job_mop_wash_observation(
        vacuum_entity_id=_VAC, map_id=_MAP,
        observed_at="2026-01-01T09:00:00+00:00")
    assert job["observed_mop_wash_count"] == 1


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


@pytest.mark.parametrize("bad_paused_at", ["", "not-a-timestamp"])
def test_resume_missing_paused_at_skips_accumulation(tracker, manager, bad_paused_at):
    """[AJI-16b] a paused job whose paused_at is empty/unparseable still resumes
    (status→started, paused_at cleared) but the unparseable timestamp is NOT
    turned into a bogus pause delta — the prior accumulated totals are preserved
    rather than corrupted. Traverses the 1317->1325 no-accumulation arc."""
    _seed(
        manager, status="paused",
        paused_at=bad_paused_at,
        paused_duration_seconds=10,
        current_room_paused_seconds=5,
    )
    job = tracker.resume_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP,
        resumed_at="2026-01-01T09:00:30+00:00")
    # lifecycle transition still completes
    assert job["status"] == "started"
    assert job["paused_at"] is None
    # no parseable paused_at → no delta accumulated; prior totals preserved
    assert job["paused_duration_seconds"] == 10
    assert job["current_room_paused_seconds"] == 5


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


# ---------------------------------------------------------------------------
# async_pause_active_job / async_resume_active_job — service-driven wrappers
# ---------------------------------------------------------------------------

def _register_vacuum(hass, service) -> list:
    calls = []

    async def _handler(call):
        calls.append(call)

    hass.services.async_register("vacuum", service, _handler)
    return calls


async def test_async_pause_no_started_job(tracker, manager):
    """[AJI-25] nothing started → paused False, no_started_job, no service call."""
    out = await tracker.async_pause_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["paused"] is False
    assert out["reason"] == "no_started_job"


async def test_async_pause_calls_service(tracker, manager, hass):
    """[AJI-26] a started job → vacuum.pause dispatched + job marked paused."""
    _seed(manager)
    calls = _register_vacuum(hass, "pause")
    out = await tracker.async_pause_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["paused"] is True
    assert out["reason"] == "paused"
    assert len(calls) == 1
    assert calls[0].data["entity_id"] == _VAC
    assert out["active_job"]["status"] == "paused"


async def test_async_resume_no_paused_job(tracker, manager):
    """[AJI-27] a non-paused job → resumed False, no_paused_job, no service call."""
    _seed(manager)  # status started, not paused
    out = await tracker.async_resume_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["resumed"] is False
    assert out["reason"] == "no_paused_job"


async def test_async_resume_calls_service(tracker, manager, hass):
    """[AJI-28] a paused job → vacuum.start dispatched + job marked started."""
    _seed(manager, status="paused", paused_at="2026-01-01T09:00:00+00:00")
    calls = _register_vacuum(hass, "start")
    out = await tracker.async_resume_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["resumed"] is True
    assert out["reason"] == "resumed"
    assert len(calls) == 1
    assert out["active_job"]["status"] == "started"


# ---------------------------------------------------------------------------
# get_paused_job_timeout_report — paused-job timeout escalation
# ---------------------------------------------------------------------------

def test_timeout_report_not_paused(tracker, manager):
    """[AJI-29] a started (non-paused) job has no timeout report."""
    _seed(manager)
    assert tracker.get_paused_job_timeout_report(
        vacuum_entity_id=_VAC, map_id=_MAP) is None


def test_timeout_report_disabled_when_zero(tracker, manager):
    """[AJI-30] a paused job with a 0-minute timeout opts out → None."""
    _seed(manager, status="paused", paused_at="2026-01-01T09:00:00+00:00",
          pause_timeout_minutes=0)
    assert tracker.get_paused_job_timeout_report(
        vacuum_entity_id=_VAC, map_id=_MAP) is None


def test_timeout_report_under_limit(tracker, manager):
    """[AJI-31] paused but not yet over the limit → None."""
    _seed(manager, status="paused", paused_at="2026-01-01T09:00:00+00:00",
          pause_timeout_minutes=30)
    out = tracker.get_paused_job_timeout_report(
        vacuum_entity_id=_VAC, map_id=_MAP, now="2026-01-01T09:10:00+00:00")
    assert out is None


def test_timeout_report_exceeded(tracker, manager):
    """[AJI-32] paused beyond the limit → a populated escalation report."""
    _seed(manager, status="paused", job_id="j9",
          paused_at="2026-01-01T09:00:00+00:00", pause_timeout_minutes=30)
    out = tracker.get_paused_job_timeout_report(
        vacuum_entity_id=_VAC, map_id=_MAP, now="2026-01-01T10:00:00+00:00")
    assert out is not None
    assert out["cancel_reason"] == "pause_timeout"
    assert out["forced_lifecycle_state"] == "pause_timeout_cancelled"
    assert out["pause_timeout_minutes"] == 30
    assert out["paused_elapsed_seconds"] == 3600
    assert out["job_id"] == "j9"


def test_timeout_report_unparseable_timestamp(tracker, manager):
    """[AJI-33] a paused job whose paused_at can't be parsed → None (no crash)."""
    _seed(manager, status="paused", paused_at="not-a-timestamp",
          pause_timeout_minutes=30)
    assert tracker.get_paused_job_timeout_report(
        vacuum_entity_id=_VAC, map_id=_MAP, now="2026-01-01T10:00:00+00:00") is None


# ---------------------------------------------------------------------------
# _timing_completion_threshold_minutes — overrun-slack tiers (pure)
# ---------------------------------------------------------------------------

def test_timing_threshold_confidence_tiers(tracker):
    """[AJI-34] lower confidence → a larger overrun slack (monotonic), and the
    sample-count + drift bonuses push the threshold up further."""
    def thr(**room):
        base = {"minutes": 10, "sample_count": 10}
        base.update(room)
        return tracker._timing_completion_threshold_minutes(base)

    high = thr(confidence_score=0.9)
    mid = thr(confidence_score=0.7)
    low = thr(confidence_score=0.5)
    poor = thr(confidence_score=0.1)
    # overrun_ratio grows as confidence drops → threshold grows
    assert high < mid < low < poor
    # all thresholds exceed the raw estimate (slack is always added)
    assert high > 10
    # a low sample count adds extra slack vs a well-sampled room
    assert thr(confidence_score=0.9, sample_count=1) > thr(confidence_score=0.9, sample_count=10)
    # an accuracy drift adds slack on top
    assert thr(confidence_score=0.9, accuracy_drift_ratio=0.8) > high
    # the total slack is capped (never exceeds est + max(4, est*0.35))
    assert thr(confidence_score=0.0, sample_count=0, accuracy_drift_ratio=5.0) <= 10 + 4.0


def test_timing_threshold_sample_count_bracket(tracker):
    """[AJI-35] the 2-or-3-sample bracket adds exactly 0.5 min of slack — between the
    <=1-sample +1.0 and the well-sampled +0.0. This governs rollover timing for rooms
    still early in learning; a regression would prematurely roll a 2-3 sample room."""
    def thr(sample_count):
        return tracker._timing_completion_threshold_minutes(
            {"minutes": 10, "confidence_score": 0.9, "sample_count": sample_count})
    base = thr(10)                  # well-sampled: no sample-count slack
    assert thr(2) == base + 0.5     # the elif sample_count <= 3 bracket
    assert thr(3) == base + 0.5
    assert thr(1) == base + 1.0     # the <=1 bracket adds more (ordering sanity)


# ---------------------------------------------------------------------------
# _job_status_summary — card-facing status string
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("active_job,lifecycle,expected", [
    ({"status": "paused"}, {}, "Job paused"),
    ({"status": "started"}, {}, "Cleaning in progress"),
    ({"status": "completed", "finalize_summary": {"status": "cancelled"}}, {}, "Job cancelled"),
    ({"status": "completed", "finalize_summary": {"status": "failed"}}, {}, "Job failed"),
    ({"status": "completed", "finalize_summary": {"status": "interrupted"}}, {}, "Job interrupted"),
    ({"status": "completed"}, {}, "Job completed"),
    ({"status": "idle"}, {"lifecycle_state": "ready"}, "Ready to start"),
    ({"status": "idle"}, {"lifecycle_state": "dock_drying"}, "Dock drying"),
    ({"status": "idle"}, {"lifecycle_state": "other", "message": ""}, "Idle"),
])
def test_job_status_summary(tracker, active_job, lifecycle, expected):
    """[AJI-35] the status string covers each lifecycle/outcome branch."""
    assert tracker._job_status_summary(
        active_job=active_job, lifecycle_state=lifecycle) == expected


def test_job_status_summary_names_room(tracker):
    """[AJI-36] a started job names the current room from resolved_rooms."""
    active_job = {
        "status": "started", "current_room_id": 1,
        "resolved_rooms": [{"room_id": 1, "name": "Kitchen"}],
    }
    out = tracker._job_status_summary(
        active_job=active_job, progress_snapshot={"current_room_id": 1})
    assert out == "Cleaning Kitchen"
