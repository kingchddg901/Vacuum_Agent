"""Integration tests for jobs/active_job.py — ActiveJobTracker methods that
read/write the core manager (data + hass). Driven by the `manager` fixture
with a seeded active job; no real robot-position entities required.

Coverage targets
----------------
[AJI-1]  get_active_job returns a normalized idle default when none is stored.
[AJI-46] record_counter_sample refuses a torn bucket and a job with no counters at all,
         and the "no counters" test is an AND not an OR -- one counter is enough.
[AJI-47] external runs: the settings-select snapshot is deduped per flip and its ring
         is trimmed, and a save that raises does not lose the sample.
[AJI-48] record_pose_sample refuses a map with no job, and RECORDS a docked tick whose
         current_room is None -- the parked-dock exclusion depends on those existing.
[AJI-49] _snapshot_settings_selects skips every select it cannot read and applies
         value_map only where one is declared.
[AJI-50] _access_graph_path steps over a torn room row and an unusable id, and answers
         [] for a source room the graph does not contain.
[AJI-51] seed_counter_baseline: an unreadable clean clock degrades to None through the
         caller's own guard, an unreadable area through the converter's, and only BOTH
         being None refuses the baseline.
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
[AJI-37] _timing_completion_threshold_minutes: the 2-or-3-sample bracket adds 0.5 slack (between the <=1 +1.0 and well-sampled 0.0).
[AJI-38] async_cancel_active_job: a sequenced job gets _cancel_in_flight set before return_to_base (stops the watchdog re-dispatching during cancel).
[AJI-35] _job_status_summary: status string covers each lifecycle/outcome branch.
[AJI-36] _job_status_summary: a started job names the current room from resolved_rooms.
[AJI-40] non-cleaning accumulator: the VACUUM entity's transitions open/close it.
[AJI-41] non-cleaning accumulator: other watched entities do not drive it.
[AJI-42] non-cleaning accumulator: a dropout closes it despite the history filter.
[AJI-43] record_completed_room: reopens the non-cleaning window for the next room.
[AJI-44] a phased job on a NON-native adapter reaches timing rollover (40cbaac, behavioural).
[AJI-45] a mid-room service trip no longer completes a room on docked wall time.
"""

from __future__ import annotations

from tests._factories import spec_tracker

import pytest

from custom_components.eufy_vacuum.const import DOMAIN
from custom_components.eufy_vacuum.jobs.active_job import (
    ActiveJobTracker,
    _MAX_COUNTER_SAMPLES,
)


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
# current-room non-cleaning accumulator (wiring)
# ---------------------------------------------------------------------------

def _eufy_like_adapter() -> None:
    """Register a NON-native adapter for _VAC — native_transition_source stays
    False, as on Eufy, so the rollover under test takes the timing/counter path."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {"adapter_id": "eufy_test", "source": "code"})


def test_accumulator_driven_by_the_vacuum_entity(tracker, manager):
    """[AJI-40] the vacuum's own transitions open and close the interval."""
    _seed(manager, current_room_started_at="2026-01-01T10:00:00+00:00")
    tracker.record_active_job_transition(
        vacuum_entity_id=_VAC, map_id=_MAP, entity_id=_VAC,
        from_state="cleaning", to_state="returning",
        changed_at="2026-01-01T10:01:00+00:00")
    job = tracker.get_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert job["current_room_noncleaning_since"] == "2026-01-01T10:01:00+00:00"

    tracker.record_active_job_transition(
        vacuum_entity_id=_VAC, map_id=_MAP, entity_id=_VAC,
        from_state="docked", to_state="cleaning",
        changed_at="2026-01-01T10:04:00+00:00")
    job = tracker.get_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert job["current_room_noncleaning_seconds"] == 180
    assert job["current_room_noncleaning_since"] is None


def test_accumulator_ignores_other_watched_entities(tracker, manager):
    """[AJI-41] the lifecycle listener fires for dock_status/task_status too, and
    those carry their own vocabularies — 'returning to wash' on task_status is not
    the vacuum entity's HA-standard state and must not drive this."""
    _seed(manager, current_room_started_at="2026-01-01T10:00:00+00:00")
    tracker.record_active_job_transition(
        vacuum_entity_id=_VAC, map_id=_MAP, entity_id="sensor.alfred_task_status",
        from_state="cleaning", to_state="returning",
        changed_at="2026-01-01T10:01:00+00:00")
    job = tracker.get_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert job.get("current_room_noncleaning_since") is None


def test_accumulator_closes_on_unavailable_despite_the_history_filter(tracker, manager):
    """[AJI-42] a transition into 'unavailable' is dropped from the history list
    (empty/duplicate filter), but it must still close the interval — which is why
    the accumulator runs BEFORE that filter and persists on its own.
    """
    _seed(manager, current_room_started_at="2026-01-01T10:00:00+00:00",
          current_room_noncleaning_since="2026-01-01T10:01:00+00:00")
    tracker.record_active_job_transition(
        vacuum_entity_id=_VAC, map_id=_MAP, entity_id=_VAC,
        from_state="returning", to_state="",
        changed_at="2026-01-01T10:02:00+00:00")
    job = manager.data["active_jobs"][_VAC][_MAP]
    assert job["current_room_noncleaning_since"] is None, (
        "the interval stayed open behind the history filter — it would subtract "
        "for as long as the dropout lasts and stall the room"
    )
    assert job["current_room_noncleaning_seconds"] == 60


def test_record_completed_room_reopens_the_window(tracker, manager):
    """[AJI-43] the accumulated total belongs to the room that just ended."""
    _seed(manager,
          resolved_rooms=[{"room_id": 1}, {"room_id": 2}],
          queue_room_ids=[1, 2],
          current_room_id=1,
          current_room_started_at="2026-01-01T10:00:00+00:00",
          current_room_noncleaning_seconds=240,
          current_room_noncleaning_since="2026-01-01T10:03:00+00:00")
    job = tracker.record_completed_room(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1,
        completed_at="2026-01-01T10:05:00+00:00")
    assert job["current_room_id"] == 2
    assert job["current_room_noncleaning_seconds"] == 0
    # hass has no state for _VAC in this test, so the live read fails open.
    assert job["current_room_noncleaning_since"] is None


# ---------------------------------------------------------------------------
# The re-enabled Eufy phased rollover (40cbaac) — behaviour, not source shape
# ---------------------------------------------------------------------------

def _two_room_timeline() -> list[dict]:
    """Two unlearned rooms → timing threshold 2.75 min each."""
    return [{"room_id": 1, "minutes": 1.0}, {"room_id": 2, "minutes": 1.0}]


def test_phased_job_on_a_non_native_adapter_does_roll(tracker, manager):
    """[AJI-44] A phased job DOES reach timing rollover now.

    This is the behavioural half of 40cbaac's structural tests: an Eufy room_group
    phase holds both rooms in ONE dispatch, so without this the queue would sit on
    room 1 for the whole phase. Non-native adapter → timing path, not native.
    """
    _eufy_like_adapter()
    _seed(manager,
          phases=[{"phase_type": "room_group",
                   "resolved_rooms": [{"room_id": 1}, {"room_id": 2}]}],
          current_phase_index=0,
          resolved_rooms=[{"room_id": 1, "name": "Entryway"},
                          {"room_id": 2, "name": "Home Office"}],
          queue_room_ids=[1, 2],
          current_room_id=1,
          current_room_started_at="2026-01-01T10:00:00+00:00")
    job = manager.data["active_jobs"][_VAC][_MAP]

    out = tracker._maybe_roll_current_room_by_timing(
        vacuum_entity_id=_VAC, map_id=_MAP, active_job=job,
        raw_timeline=_two_room_timeline(),
        current_room_id=1,
        current_room_elapsed_minutes=3.0,   # > the 2.75 unlearned threshold
        completed_room_ids=[])
    assert out["completed_room_ids"] == [1]
    assert out["current_room_id"] == 2
    assert out["completed_rooms"][0]["source"] == "timing_rollover"


def test_a_mid_room_service_trip_does_not_produce_a_phantom(tracker, manager):
    """[AJI-45] The accumulator's reason to exist, end to end.

    Room 1 starts at 10:00. At 10:01 the robot leaves the floor for a mop wash and
    is back cleaning at 10:04. At 10:05 the wall clock reads 5.0 min — past the
    2.75 threshold — but only 2.0 of those minutes were cleaning, so the room must
    NOT be completed. The control below is the same instant with the accumulator
    fields absent, which is what shipped before this change.
    """
    _eufy_like_adapter()
    _seed(manager,
          phases=[{"phase_type": "room_group",
                   "resolved_rooms": [{"room_id": 1}, {"room_id": 2}]}],
          current_phase_index=0,
          resolved_rooms=[{"room_id": 1}, {"room_id": 2}],
          queue_room_ids=[1, 2],
          current_room_id=1,
          current_room_started_at="2026-01-01T10:00:00+00:00")

    for entity, frm, to, when in (
        (_VAC, "cleaning", "returning", "2026-01-01T10:01:00+00:00"),
        (_VAC, "returning", "docked", "2026-01-01T10:02:00+00:00"),
        (_VAC, "docked", "cleaning", "2026-01-01T10:04:00+00:00"),
    ):
        tracker.record_active_job_transition(
            vacuum_entity_id=_VAC, map_id=_MAP, entity_id=entity,
            from_state=frm, to_state=to, changed_at=when)

    job = tracker.get_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert job["current_room_noncleaning_seconds"] == 180

    elapsed = tracker._compute_current_room_elapsed_minutes(
        active_job=job, now="2026-01-01T10:05:00+00:00")
    assert elapsed == pytest.approx(2.0)

    out = tracker._maybe_roll_current_room_by_timing(
        vacuum_entity_id=_VAC, map_id=_MAP, active_job=job,
        raw_timeline=_two_room_timeline(),
        current_room_id=1,
        current_room_elapsed_minutes=elapsed,
        completed_room_ids=[])
    assert out["completed_room_ids"] == [], (
        "room 1 was completed on wall time it spent at the dock"
    )

    # CONTROL: the identical moment measured the pre-accumulator way.
    naive = dict(job)
    naive.pop("current_room_noncleaning_seconds", None)
    naive.pop("current_room_noncleaning_since", None)
    assert tracker._compute_current_room_elapsed_minutes(
        active_job=naive, now="2026-01-01T10:05:00+00:00") == pytest.approx(5.0)


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

def _pose_at(seconds_ago: float, room: int | None) -> dict:
    from datetime import datetime, timedelta, timezone
    return {
        "t": (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat(),
        "current_room": room,
    }


def test_pose_veto_survives_a_boundary_flicker(tracker):
    """live:ROOM-FLICKER-1, with the run's real numbers. A double-pass profile sweeps
    perpendicular to the shared wall, so it crosses repeatedly: excursions of 2 s, 2 s
    and 12 s against dwells of 94 s and 162 s. The robot is in Entryway (8); a 2 s dip
    into Home Office (9) must not let timing concede the room."""
    job = {"pose_samples": [
        _pose_at(18, 8), _pose_at(16, 8), _pose_at(14, 9), _pose_at(12, 9),   # 2 s excursion
        _pose_at(10, 8), _pose_at(8, 8), _pose_at(6, 8), _pose_at(4, 8), _pose_at(2, 8),
    ]}
    assert tracker._pose_says_still_in_room(job, 8) is True


def test_pose_veto_releases_after_a_genuine_departure(tracker):
    """Absent for the WHOLE dwell window — a real exit, so timing may advance. One
    window late is the deliberate cost of not conceding a room on a 2 s blip."""
    job = {"pose_samples": [
        _pose_at(60, 8), _pose_at(40, 8),
        _pose_at(18, 9), _pose_at(12, 9), _pose_at(6, 9), _pose_at(1, 9),
    ]}
    assert tracker._pose_says_still_in_room(job, 8) is False


def test_pose_veto_fails_open(tracker):
    """No pose, no timestamps, or a buffer that stopped arriving must all behave exactly
    as before the guard existed. A veto that can permanently stall the queue would be
    worse than the flicker it prevents."""
    assert tracker._pose_says_still_in_room({}, 8) is False
    assert tracker._pose_says_still_in_room({"pose_samples": []}, 8) is False
    assert tracker._pose_says_still_in_room({"pose_samples": [{"t": "nonsense"}]}, 8) is False
    assert tracker._pose_says_still_in_room({"pose_samples": [_pose_at(2, 8)]}, None) is False
    # sampler died 10 minutes ago, robot still nominally "in" room 8
    stale = {"pose_samples": [_pose_at(700, 8), _pose_at(620, 8)]}
    assert tracker._pose_says_still_in_room(stale, 8) is False


def test_pose_veto_ignores_docked_ticks(tracker):
    """current_room=None means docked / off-raster — it says nothing about which room,
    so it must neither hold the veto open nor release it."""
    job = {"pose_samples": [_pose_at(18, 8), _pose_at(12, None), _pose_at(6, None), _pose_at(2, None)]}
    assert tracker._pose_says_still_in_room(job, 8) is True     # room 8 still inside the window
    job2 = {"pose_samples": [_pose_at(18, None), _pose_at(12, None), _pose_at(2, None)]}
    assert tracker._pose_says_still_in_room(job2, 8) is False   # nothing says it is here


def test_seed_counter_baseline_records_the_floor(hass, tracker, monkeypatch):
    """live:PHASE-ATTR-1 (first-phase half). Counter samples only land when a counter
    CHANGES, so the opening phase had no floor and its first increment was credited to
    nothing — kitchen measured 90 s / 1 m² against a recorder-verified 120 s / 2 m².
    Seeding at job start measures the floor instead of guessing it."""
    monkeypatch.setattr(
        "custom_components.eufy_vacuum.jobs.active_job._get_adapter_config",
        lambda _v: {"entities": {"cleaning_time": "sensor.ct", "cleaning_area": "sensor.ca"}},
    )
    hass.states.async_set("sensor.ct", "120", {"unit_of_measurement": "s"})
    hass.states.async_set("sensor.ca", "2", {"unit_of_measurement": "m²"})
    job = {"status": "started", "counter_samples": []}

    assert tracker.seed_counter_baseline(
        vacuum_entity_id=_VAC, active_job=job, observed_at="2026-01-01T09:00:00+00:00") is True
    assert job["last_cleaning_time_seconds"] == 120
    assert job["last_cleaning_area_m2"] == 2.0
    assert len(job["counter_samples"]) == 1
    assert job["counter_samples"][0]["cleaning_time"] == 120
    assert job["counter_samples"][0]["cleaning_area"] == 2.0


def test_seed_counter_baseline_normalizes_imperial_area(hass, tracker, monkeypatch):
    """An imperial HA presents Eufy's cleaning_area in ft². The baseline has to be in the
    SAME canonical m² the running samples use, or the very first delta is a unit error —
    which is why this reuses cleaning_area_to_m2 instead of reading the raw state."""
    monkeypatch.setattr(
        "custom_components.eufy_vacuum.jobs.active_job._get_adapter_config",
        lambda _v: {"entities": {"cleaning_time": "sensor.ct", "cleaning_area": "sensor.ca"}},
    )
    hass.states.async_set("sensor.ct", "60", {"unit_of_measurement": "s"})
    hass.states.async_set("sensor.ca", "21.53", {"unit_of_measurement": "ft²"})
    job = {"status": "started", "counter_samples": []}

    tracker.seed_counter_baseline(vacuum_entity_id=_VAC, active_job=job)
    assert job["last_cleaning_area_m2"] == pytest.approx(2.0, abs=0.01)


def test_seed_counter_baseline_no_counters_is_a_noop(hass, tracker, monkeypatch):
    """An adapter that declares no counters (or whose sensors are unreadable) must not get
    a fabricated zero floor — that is the live:AUDIT2-ZEROCOERCE shape, and a zero baseline
    would re-credit a stale cumulative reading to the first room."""
    monkeypatch.setattr(
        "custom_components.eufy_vacuum.jobs.active_job._get_adapter_config",
        lambda _v: {"entities": {}},
    )
    job = {"status": "started", "counter_samples": []}
    assert tracker.seed_counter_baseline(vacuum_entity_id=_VAC, active_job=job) is False
    assert job["counter_samples"] == []
    assert "last_cleaning_time_seconds" not in job

    monkeypatch.setattr(
        "custom_components.eufy_vacuum.jobs.active_job._get_adapter_config",
        lambda _v: {"entities": {"cleaning_time": "sensor.ct", "cleaning_area": "sensor.ca"}},
    )
    hass.states.async_set("sensor.ct", "unavailable")
    hass.states.async_set("sensor.ca", "unknown")
    assert tracker.seed_counter_baseline(vacuum_entity_id=_VAC, active_job=job) is False
    assert job["counter_samples"] == []


def test_recharge_low_battery_sets_pending(tracker, manager, monkeypatch):
    """[AJI-11] low-battery return arms pending; not charging yet → returns."""
    _seed(manager)
    monkeypatch.setattr(tracker, "_is_low_battery_return_state", lambda **kw: True)
    monkeypatch.setattr(tracker, "_is_charging", lambda v: False)
    result = tracker.update_active_job_recharge_observation(
        vacuum_entity_id=_VAC, map_id=_MAP, observed_at="2026-01-01T09:05:00+00:00")
    assert result["pending_mid_job_recharge_return"] is True


def test_recharge_starts_and_pauses(hass, tracker, manager, monkeypatch):
    """[AJI-12] pending + charging + not yet observed → recharge begins, sampling pauses.

    live:RECHARGE-FLAG-2 CHANGED THE COUNT'S TIMING. Starting to charge at the dock
    does not prove the trip was a recharge — the end-of-job return looks identical to
    is_low_battery_return_state whenever the run happens to finish under the battery
    threshold. The count therefore moved to resolve_mid_job_recharge_resumed, where
    the robot going back to work proves it. Here it must still be 0."""
    _seed(manager)
    monkeypatch.setattr(tracker, "_is_low_battery_return_state", lambda **kw: True)
    monkeypatch.setattr(tracker, "_is_charging", lambda v: True)
    fake_tracker = spec_tracker()
    hass.data[DOMAIN]["mapping_tracker"] = fake_tracker

    result = tracker.update_active_job_recharge_observation(
        vacuum_entity_id=_VAC, map_id=_MAP, observed_at="2026-01-01T09:05:00+00:00")
    assert result["observed_mid_job_recharge"] is True
    assert result["observed_mid_job_recharge_count"] == 0        # not yet proved
    assert result["pending_mid_job_recharge_return"] is False
    fake_tracker.pause_sampling.assert_called_once_with(_VAC)


def test_terminal_dock_does_not_count_as_a_recharge(hass, tracker, manager, monkeypatch):
    """live:RECHARGE-FLAG-2. A run that ENDS at low battery returns to dock and charges,
    which satisfies is_low_battery_return_state in full — its generic arm is only
    `returning` + battery <= threshold, and the battery gate exists to exclude a
    FULL-battery return_to_base, not a job that simply finished while low.

    Alfred finished its last room at 17% against a threshold of 20 and recorded
    count=2 for one real recharge (job_2026-08-05T05-33-49). Without a resume there
    must be no count at all."""
    _seed(manager)
    monkeypatch.setattr(tracker, "_is_low_battery_return_state", lambda **kw: True)
    monkeypatch.setattr(tracker, "_is_charging", lambda v: True)
    hass.data[DOMAIN]["mapping_tracker"] = spec_tracker()

    result = tracker.update_active_job_recharge_observation(
        vacuum_entity_id=_VAC, map_id=_MAP, observed_at="2026-01-01T09:05:00+00:00")
    # The job finalizes here, still charging: resolve_mid_job_recharge_resumed never runs.
    assert result["observed_mid_job_recharge_count"] == 0
    assert result["recharge_seconds_accumulated"] == 0           # count and accum agree


def test_recharge_count_and_accumulator_agree_by_construction(hass, tracker, manager, monkeypatch):
    """live:RECHARGE-FLAG-2. Both are written by the SAME resume, so they cannot drift.
    Their disagreement (count=2, accum=one recharge's worth) is what exposed the bug."""
    _seed(
        manager,
        pending_mid_job_recharge_return=True,
        observed_mid_job_recharge=True,
        observed_mid_job_recharge_started_at="2026-01-01T09:00:00+00:00",
        observed_mid_job_recharge_count=0,
        recharge_seconds_accumulated=0,
    )
    monkeypatch.setattr(tracker, "_is_charging", lambda _v: False)
    hass.data[DOMAIN]["mapping_tracker"] = spec_tracker()

    result = tracker.resolve_mid_job_recharge_resumed(
        vacuum_entity_id=_VAC, map_id=_MAP, observed_at="2026-01-01T09:05:00+00:00")
    assert result["observed_mid_job_recharge_count"] == 1
    assert result["recharge_seconds_accumulated"] == 300
    assert result["observed_mid_job_recharge"] is False


def test_recharge_ends_accumulates(hass, tracker, manager, monkeypatch):
    """[AJI-13] SUPERSEDED (RP-012/RF-31, A4-AJ-1/TRK-2). An in-progress recharge
    that has ended accumulates seconds + resumes sampling. This used to drive
    BOTH the start-check and the end-check through ONE call to
    update_active_job_recharge_observation (a two-value _is_charging
    side_effect) -- but that "end" branch was UNREACHABLE: the SAME
    synchronous call's top-level "if not is_charging: return" already proved
    charging True before the branch could run, so it could never observe
    False. Recharge-end is now its own method, resolve_mid_job_recharge_resumed
    -- called separately (by the lifecycle listener, on a LATER tick) once
    charging has genuinely ended, which is what this now exercises directly."""
    _seed(
        manager,
        pending_mid_job_recharge_return=True,
        observed_mid_job_recharge=True,
        observed_mid_job_recharge_started_at="2026-01-01T09:00:00+00:00",
        recharge_seconds_accumulated=0,
    )
    monkeypatch.setattr(tracker, "_is_charging", lambda _v: False)
    fake_tracker = spec_tracker()
    hass.data[DOMAIN]["mapping_tracker"] = fake_tracker

    result = tracker.resolve_mid_job_recharge_resumed(
        vacuum_entity_id=_VAC, map_id=_MAP, observed_at="2026-01-01T09:05:00+00:00")
    assert result["observed_mid_job_recharge"] is False
    assert result["recharge_seconds_accumulated"] == 300  # 5 min
    fake_tracker.resume_sampling.assert_called_once_with(_VAC)


def test_recharge_observation_alone_no_longer_detects_end(hass, tracker, manager, monkeypatch):
    """[AJI-13b] RP-012/RF-31: update_active_job_recharge_observation alone is
    now a stable no-op once charging has stopped (its own top-level "not
    charging" guard returns early) -- it can no longer close out a recharge by
    itself. Locks in the new two-method contract so the dead branch doesn't
    quietly get reintroduced."""
    _seed(
        manager,
        pending_mid_job_recharge_return=True,
        observed_mid_job_recharge=True,
        observed_mid_job_recharge_started_at="2026-01-01T09:00:00+00:00",
        recharge_seconds_accumulated=0,
    )
    monkeypatch.setattr(tracker, "_is_charging", lambda _v: False)

    result = tracker.update_active_job_recharge_observation(
        vacuum_entity_id=_VAC, map_id=_MAP, observed_at="2026-01-01T09:05:00+00:00")
    assert result["observed_mid_job_recharge"] is True
    assert result["recharge_seconds_accumulated"] == 0


def test_resolve_recharge_resumed_skips_commanded_dock_phase(hass, tracker, manager, monkeypatch):
    """[AJI-13c] RP-012(d): a job parked on a charge_wait phase owns its own
    dock -- resolve_mid_job_recharge_resumed must not accrue an unplanned
    recharge for it, even if observed_mid_job_recharge carried over from a
    prior phase. Ported from update_active_job_recharge_observation's
    is_dock_polled_phase guard (same condition, same reasoning)."""
    _seed(
        manager,
        phases=[{"phase_type": "charge_wait"}],
        current_phase_index=0,
        pending_mid_job_recharge_return=True,
        observed_mid_job_recharge=True,
        observed_mid_job_recharge_started_at="2026-01-01T09:00:00+00:00",
        recharge_seconds_accumulated=0,
    )
    monkeypatch.setattr(tracker, "_is_charging", lambda _v: False)
    fake_tracker = spec_tracker()
    hass.data[DOMAIN]["mapping_tracker"] = fake_tracker

    result = tracker.resolve_mid_job_recharge_resumed(
        vacuum_entity_id=_VAC, map_id=_MAP, observed_at="2026-01-01T09:05:00+00:00")
    assert result["recharge_seconds_accumulated"] == 0
    assert result["observed_mid_job_recharge"] is True   # untouched -- guard returned early
    fake_tracker.resume_sampling.assert_not_called()


def test_resolve_recharge_resumed_still_accrues_on_room_group_phase(hass, tracker, manager, monkeypatch):
    """[AJI-13d] control for AJI-13c: the SAME job shape on a room_group phase
    (not dock-polled) still accrues normally -- the guard is phase-type scoped,
    not a blanket suppression."""
    _seed(
        manager,
        phases=[{"phase_type": "room_group"}],
        current_phase_index=0,
        pending_mid_job_recharge_return=True,
        observed_mid_job_recharge=True,
        observed_mid_job_recharge_started_at="2026-01-01T09:00:00+00:00",
        recharge_seconds_accumulated=0,
    )
    monkeypatch.setattr(tracker, "_is_charging", lambda _v: False)
    fake_tracker = spec_tracker()
    hass.data[DOMAIN]["mapping_tracker"] = fake_tracker

    result = tracker.resolve_mid_job_recharge_resumed(
        vacuum_entity_id=_VAC, map_id=_MAP, observed_at="2026-01-01T09:05:00+00:00")
    assert result["recharge_seconds_accumulated"] == 300
    assert result["observed_mid_job_recharge"] is False
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


def test_mark_finalized_ends_mapping_tracker_job(hass, tracker, manager):
    """[AJI-41] RP-012/RF-31 (TRK-1): mark_active_job_finalized -- the terminal
    chokepoint every path reaches (cancel, strand, success) -- releases the
    mapping tracker's hold on this job. Cancel/strand never went through the
    lifecycle finalize path's own finally block, so before this the tracker
    was stuck holding a cancelled/stranded job's state for the NEXT run."""
    _seed(manager)
    fake_tracker = spec_tracker()
    hass.data[DOMAIN]["mapping_tracker"] = fake_tracker

    tracker.mark_active_job_finalized(
        vacuum_entity_id=_VAC, map_id=_MAP, finalize_result=None)

    fake_tracker.end_job.assert_called_once_with(vacuum_entity_id=_VAC)


def test_mark_finalized_no_tracker_registered_does_not_raise(hass, tracker, manager):
    """[AJI-42] no mapping_tracker registered (e.g. no position entities
    configured) -- mark_active_job_finalized must still complete normally."""
    _seed(manager)
    hass.data[DOMAIN].pop("mapping_tracker", None)
    job = tracker.mark_active_job_finalized(
        vacuum_entity_id=_VAC, map_id=_MAP, finalize_result=None)
    assert job["finalized"] is True


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


async def test_cancel_sets_cancel_in_flight_before_rtb(tracker, manager, hass, monkeypatch):
    """[AJI-38] cancelling a SEQUENCED job sets _cancel_in_flight on the stored record
    BEFORE return_to_base, so the per-phase watchdog (which guards on it) stops before it
    can re-dispatch app_segment_clean during the cancel window.

    SUPERSEDED (RP-010/RF-06, Q9 taxonomy authored packet): this docstring used to
    claim "atomic jobs never get it" -- that was true before RP-010, when the flag
    was written only inside `if active_job.get("phases")`. RP-010 makes the write
    universal because the flag now doubles as async_cancel_active_job's
    single-flight latch (a second cancel arriving mid-confirm-window used to
    re-run the whole body and null finalize_summary) -- atomic jobs need the
    latch exactly as much as phased ones. See test_cancel_sets_cancel_in_flight_
    for_atomic_job below for the companion case."""
    monkeypatch.setattr(type(tracker), "_CANCEL_CONFIRM_TIMEOUT_S", 1)
    monkeypatch.setattr(type(tracker), "_CANCEL_POLL_INTERVAL_S", 0.01)
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "phases": [{"resolved_rooms": [{"room_id": 1}], "payload": {"segments": [1]}, "room_count": 1},
                   {"resolved_rooms": [{"room_id": 2}], "payload": {"segments": [2]}, "room_count": 1}],
        "current_phase_index": 0, "resolved_rooms": [{"room_id": 1}],
        "current_room_id": 1, "_phase_dispatch_pending": True,
        "job_id": "j1", "started_at": "2026-01-01T00:00:00+00:00",
    }
    flag_at_rtb = {}

    async def _rtb(call):
        flag_at_rtb["value"] = manager.data["active_jobs"][_VAC][_MAP].get("_cancel_in_flight")

    hass.services.async_register("vacuum", "return_to_base", _rtb)
    hass.states.async_set(_VAC, "docked")   # terminal on the first poll

    await tracker.async_cancel_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert flag_at_rtb["value"] is True   # set BEFORE return_to_base fired


async def test_cancel_sets_cancel_in_flight_for_atomic_job(tracker, manager, hass, monkeypatch):
    """[AJI-39] RP-010/RF-06: an ATOMIC job (no phases) also gets _cancel_in_flight
    set before return_to_base -- the flag is now universal because it is also the
    single-flight latch, and an atomic job needs single-flight protection exactly
    like a phased one."""
    monkeypatch.setattr(type(tracker), "_CANCEL_CONFIRM_TIMEOUT_S", 1)
    monkeypatch.setattr(type(tracker), "_CANCEL_POLL_INTERVAL_S", 0.01)
    _seed(manager, queue_room_ids=[1])
    assert "phases" not in manager.data["active_jobs"][_VAC][_MAP]
    flag_at_rtb = {}

    async def _rtb(call):
        flag_at_rtb["value"] = manager.data["active_jobs"][_VAC][_MAP].get("_cancel_in_flight")

    hass.services.async_register("vacuum", "return_to_base", _rtb)
    hass.states.async_set(_VAC, "docked")

    await tracker.async_cancel_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert flag_at_rtb["value"] is True


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
    """[AJI-37] the 2-or-3-sample bracket adds exactly 0.5 min of slack — between the
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


# ---------------------------------------------------------------------------
# [AJI-46]..[AJI-49] the live observation buffers (doc 43).
#
# These are JOB-SCOPED: doc 43 §2 notes the buffer "lives until the next run on the same
# map overwrites it, and it never reaches the finalized record", so anything a recorder
# declines to record is gone the moment the run ends.
# ---------------------------------------------------------------------------

def test_aji46_the_counter_recorder_refuses_a_torn_bucket_and_an_empty_job(tracker,
                                                                          manager):
    """[AJI-46] Two refusals, and the second is an AND rather than an OR.

    THE CONTROL CARRIES ONLY ONE COUNTER, deliberately. The guard is
    `if ct is None and ca is None`, so a job with a clean clock but no area reading --
    which is every adapter that declares `cleaning_time` and not `cleaning_area` -- must
    still be sampled. Loosening the guard to `or` reddens the control and nothing else,
    which is the precise half this fixture exists to catch.

    `False` IS BOTH REFUSALS' ANSWER, so each is paired with the buffer: a refusal must
    leave `counter_samples` absent or empty, and the control must leave exactly one
    sample in it. The boolean alone would pass against a recorder that always refused.
    """
    # an in-flight job that has never had a counter pushed into it
    _seed(manager)
    assert tracker.record_counter_sample(vacuum_entity_id=_VAC) is False
    job = manager.data["active_jobs"][_VAC][_MAP]
    assert not job.get("counter_samples"), (
        "a job with no counter readings had a sample recorded anyway"
    )

    # the control: ONE counter is enough
    job["last_cleaning_time_seconds"] = 120
    assert tracker.record_counter_sample(vacuum_entity_id=_VAC) is True
    assert len(job["counter_samples"]) == 1

    # the torn per-vacuum bucket LAST, because it replaces the bucket everything above
    # needs -- `.get(vacuum_entity_id, {})` returns whatever storage holds
    manager.data["active_jobs"][_VAC] = "not-a-dict"
    assert tracker.record_counter_sample(vacuum_entity_id=_VAC) is False


def test_aji47_external_settings_samples_are_deduped_trimmed_and_save_safe(
    tracker, manager, monkeypatch
):
    """[AJI-47] The per-room settings mirror, which only external runs have.

    The code calls these selects "our only window into what the app set per room", and
    it records one entry PER FLIP rather than per tick -- a counter sample arrives on
    every counter change, so an undeduped buffer would be thousands of identical rows
    and the real flips would rotate out of the cap.

    THREE CALLS, THREE DIFFERENT ANSWERS, which is what separates dedup from "records
    nothing" and from "records everything": same settings twice must leave ONE entry,
    and a changed value must add a second. One call could not tell those apart.

    THE RING TRIM IS SEEDED AT THE CAP rather than driven to it, because the cap is
    2000 and the claim is about the boundary, not about the loop. With 2000 already
    present a single new flip must leave 2000, not 2001.

    THE SAVE IS MADE TO RAISE at the end: the recorder wraps `async_create_task` in a
    bare `except` because losing the sample would be worse than losing the save -- the
    buffer is in-memory either way and the next save picks it up. So the assertion is
    that it still returns True and still appended.
    """
    _seed(manager, status="external", last_cleaning_time_seconds=60)
    job = manager.data["active_jobs"][_VAC][_MAP]

    settings = {"clean_mode": "vacuum"}
    monkeypatch.setattr(tracker, "_snapshot_settings_selects", lambda _v: dict(settings))

    assert tracker.record_counter_sample(vacuum_entity_id=_VAC) is True
    assert [e["settings"] for e in job["settings_samples"]] == [{"clean_mode": "vacuum"}]

    job["last_cleaning_time_seconds"] = 61
    assert tracker.record_counter_sample(vacuum_entity_id=_VAC) is True
    assert len(job["settings_samples"]) == 1, (
        "an unchanged settings read was recorded again -- one entry per FLIP"
    )

    settings["clean_mode"] = "mop"
    job["last_cleaning_time_seconds"] = 62
    assert tracker.record_counter_sample(vacuum_entity_id=_VAC) is True
    assert [e["settings"]["clean_mode"] for e in job["settings_samples"]] == [
        "vacuum", "mop"
    ]

    # the ring, seeded at the cap
    job["settings_samples"] = [
        {"t": "2026-01-01T09:00:00+00:00", "settings": {"clean_mode": "vacuum"}}
        for _ in range(_MAX_COUNTER_SAMPLES)
    ]
    settings["clean_mode"] = "vacuum_and_mop"
    job["last_cleaning_time_seconds"] = 63
    assert tracker.record_counter_sample(vacuum_entity_id=_VAC) is True
    assert len(job["settings_samples"]) == _MAX_COUNTER_SAMPLES, (
        "the settings ring grew past its cap"
    )
    assert job["settings_samples"][-1]["settings"]["clean_mode"] == "vacuum_and_mop"

    # a save that raises must not cost the sample
    def _boom(coro, *args, **kwargs):
        # close the coroutine we are refusing to schedule, or the suite logs
        # "coroutine 'async_save' was never awaited" on every run
        getattr(coro, "close", lambda: None)()
        raise RuntimeError("the loop is gone")

    monkeypatch.setattr(manager.hass, "async_create_task", _boom)
    before = len(job["counter_samples"])
    job["last_cleaning_time_seconds"] = 64
    assert tracker.record_counter_sample(vacuum_entity_id=_VAC) is True, (
        "a failed save was reported as a failed sample"
    )
    assert len(job["counter_samples"]) == before + 1


def test_aji48_the_pose_recorder_refuses_an_unknown_map_but_records_a_docked_tick(
    tracker, manager
):
    """[AJI-48] One refusal, and one thing that must NOT be refused.

    The docstring states the half that matters: `current_room` is None "while docked /
    off-raster -- those ticks ARE recorded (the parked-dock exclusion depends on `None`
    runs existing)". So a reader optimising away the None ticks would not lose detail,
    it would break an exclusion that depends on their presence.

    THE PAIR IS A REFUSAL AND A RECORD over the same tracker: an unknown map id answers
    False and writes nothing, while a None-room tick on the seeded map answers True and
    appends a sample whose `current_room` is None. Asserting only the refusal would pass
    against a recorder that refused everything.
    """
    _seed(manager)

    assert tracker.record_pose_sample(
        vacuum_entity_id=_VAC, map_id="no-such-map", current_room=1,
        anchor=[0.5, 0.5], cleaning_area=1.0,
    ) is False

    assert tracker.record_pose_sample(
        vacuum_entity_id=_VAC, map_id=_MAP, current_room=None,
        anchor=None, cleaning_area=None,
    ) is True
    samples = manager.data["active_jobs"][_VAC][_MAP]["pose_samples"]
    assert len(samples) == 1 and samples[0]["current_room"] is None, (
        "a docked tick was dropped -- the parked-dock exclusion needs it"
    )


def test_aji49_the_settings_snapshot_skips_every_select_it_cannot_read(tracker, manager):
    """[AJI-49] Five declared selects, two readable, and a value_map on one of them.

    This is read off the ADAPTER, so each shape is something a brand can declare or a
    provider can fail to supply: a spec that is not a dict at all, a spec with no
    entity_id, and an entity whose state is one of HA's absence spellings. Recording
    any of them would put a junk value into the only record of what the app chose.

    THE EXPECTATION IS THE EXACT DICT. A membership check would not notice an extra
    junk key, and extra keys are precisely what the three skips prevent. `value_map` is
    declared on one select and not the other, so the output distinguishes a mapped
    value from a raw one -- applying the map everywhere, or nowhere, moves exactly one
    of the two.

    The not-a-dict `settings_selects` case is asserted separately because it returns
    before any select is read.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

    register_adapter_config(_VAC, {
        "adapter_id": "aji49", "source": "code",
        "settings_selects": {
            "clean_mode": {"entity_id": "select.alfred_mode",
                           "value_map": {"sweep": "vacuum"}},
            "fan_speed": {"entity_id": "select.alfred_fan"},
            "torn_spec": "not-a-dict",
            "no_entity": {"value_map": {"a": "b"}},
            "unavailable": {"entity_id": "select.alfred_missing"},
        },
    })
    manager.hass.states.async_set("select.alfred_mode", "sweep")
    manager.hass.states.async_set("select.alfred_fan", "Max")
    manager.hass.states.async_set("select.alfred_missing", "unavailable")

    assert tracker._snapshot_settings_selects(_VAC) == {
        "clean_mode": "vacuum",      # value_map applied
        "fan_speed": "Max",          # no value_map -> raw state kept
    }

    register_adapter_config(_VAC, {
        "adapter_id": "aji49b", "source": "code",
        "settings_selects": ["clean_mode"],
    })
    assert tracker._snapshot_settings_selects(_VAC) == {}


def test_aji50_the_access_graph_walk_steps_over_rows_it_cannot_use(tracker):
    """[AJI-50] The BFS's own room walk, and the answer for a source it never indexed.

    `managed_rooms` comes off stored map state, so a torn row and a row whose id will
    not resolve are both real shapes -- and the statement after each guard reads
    `room.get(...)` or indexes by the id.

    `[]` IS ALSO THE ANSWER FOR "DIRECTLY ADJACENT" AND FOR "NO PATH", which the
    docstring says explicitly, so the empty list is never asserted alone: the control
    is a real three-room chain whose middle room comes back. The torn row sits in the
    SAME payload as that chain, so a walk that gave up on it would lose the path and the
    control would redden -- that is the one arm here with a red.

    TWO OF THE THREE ARMS ARE UNOBSERVABLE, and the ablation is what established it
    rather than reading:

      - `if room_id <= 0: continue` -- a non-positive id only ever adds an UNREACHABLE
        key to `grants_map`. Nothing walks from it, so deleting the guard changes no
        answer this function can give. The `ghost` row is here to cross it, not to
        assert it.
      - `if from_room_id not in grants_map: return []` -- without it the BFS pops the
        lone start path, `grants_map.get(99, [])` is empty, the loop ends, and the
        function returns `[]` at the bottom. The same answer by a longer road, so the
        early return is an optimisation rather than a behaviour.

    Both were predicted to bite and came back DEAD. They are crossed and said to be
    crossed; the only claim this test carries a red for is the torn row.
    """
    rooms = {
        "rooms": {
            "1": {"room_id": 1, "grants_access_to": [2]},
            "2": {"room_id": 2, "grants_access_to": [1, 3]},
            "3": {"room_id": 3, "grants_access_to": [2]},
            "torn": "not-a-dict",
            "ghost": {"grants_access_to": [1]},      # no room_id, key not numeric
        }
    }

    assert tracker._access_graph_path(rooms, 1, 3) == [2], (
        "the walk lost the real chain -- a torn row took the path with it"
    )
    assert tracker._access_graph_path(rooms, 1, 2) == []        # directly adjacent
    assert tracker._access_graph_path(rooms, 99, 3) == [], (
        "a source room the graph never indexed must answer [], not raise"
    )


def test_aji51_an_unreadable_counter_degrades_rather_than_raising(tracker, manager):
    """[AJI-51] The baseline's two conversions, each guarded on its own.

    This is the floor a run's first phase is measured from -- without it the first
    increment "arrives already-accrued and is credited to nothing: kitchen measured
    90 s / 1 m² against a recorder-verified 120 s / 2 m², on every run". So a garbage
    state on ONE counter must not cost the other, and the refusal is only when both
    come back None.

    THE MIDDLE CASE IS THE CLAIM. Both-garbage returning False and both-good returning
    True are satisfied by a single shared guard; the ONE-garbage case is what shows the
    two counters are independent, and the recorded sample is asserted to carry the
    readable one with the unreadable one as None.

    THE TWO COUNTERS REACH `None` BY DIFFERENT ROUTES, measured rather than assumed,
    and only one of them is this module's doing:

        cleaning_area_to_m2("not-a-number", "m2")         -> None
        _duration_state_to_seconds("not-a-number", "min") -> raises ValueError

    `cleaning_area_to_m2` catches `(TypeError, ValueError)` inside itself
    (learning/utils.py:59-62), so the caller's identical handler at active_job.py:2512
    can NEVER fire -- it is the outer of two copies of one handler and the inner one
    always wins. That line is recorded as a ceiling, not claimed here. The clean clock's
    converter does propagate, so the handler at :2504 is the one with a red: narrowing
    it to TypeError alone lets the ValueError escape and reddens this test.

    The states are real HA shapes -- a non-numeric string with a declared unit is what
    an adapter sees when firmware emits a placeholder.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

    register_adapter_config(_VAC, {
        "adapter_id": "aji51", "source": "code",
        "entities": {"cleaning_time": "sensor.alfred_ct",
                     "cleaning_area": "sensor.alfred_ca"},
    })

    # 1. both unreadable -> no baseline at all
    manager.hass.states.async_set("sensor.alfred_ct", "not-a-number",
                                  {"unit_of_measurement": "min"})
    manager.hass.states.async_set("sensor.alfred_ca", "not-a-number",
                                  {"unit_of_measurement": "m²"})
    job = {"status": "started", "vacuum_entity_id": _VAC, "map_id": _MAP}
    assert tracker.seed_counter_baseline(
        vacuum_entity_id=_VAC, active_job=job,
        observed_at="2026-01-01T09:00:00+00:00",
    ) is False
    assert not job.get("counter_samples"), (
        "a baseline was written from two unreadable counters"
    )

    # 2. ONE unreadable -> the other still lands, which is the independence claim
    manager.hass.states.async_set("sensor.alfred_ct", "2",
                                  {"unit_of_measurement": "min"})
    job2 = {"status": "started", "vacuum_entity_id": _VAC, "map_id": _MAP}
    assert tracker.seed_counter_baseline(
        vacuum_entity_id=_VAC, active_job=job2,
        observed_at="2026-01-01T09:00:00+00:00",
    ) is True, "an unreadable AREA cost the readable clean clock its baseline"
    sample = job2["counter_samples"][-1]
    assert sample["cleaning_time"] == 120, (
        "2 min should convert to 120 s; got %r" % (sample["cleaning_time"],)
    )
    # None from the CONVERTER's own guard, not from this module's -- see the docstring
    assert sample["cleaning_area"] is None

    # 3. both readable -> the control
    manager.hass.states.async_set("sensor.alfred_ca", "6",
                                  {"unit_of_measurement": "m²"})
    job3 = {"status": "started", "vacuum_entity_id": _VAC, "map_id": _MAP}
    assert tracker.seed_counter_baseline(
        vacuum_entity_id=_VAC, active_job=job3,
        observed_at="2026-01-01T09:00:00+00:00",
    ) is True
    sample3 = job3["counter_samples"][-1]
    assert sample3["cleaning_time"] == 120 and sample3["cleaning_area"] == 6.0
