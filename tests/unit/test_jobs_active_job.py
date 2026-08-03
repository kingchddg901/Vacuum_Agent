"""Unit tests for jobs/active_job.py — pure module helpers + ActiveJobTracker
pure methods (constructed with a mock manager, no hass access).

Coverage targets
----------------
[AJ-1]  _safe_int: sentinels/None → default; float-string truncates.
[AJ-2]  _safe_float: sentinels/None → default.
[AJ-3]  _normalize_path_block_action: valid action kept, else event_only.
[AJ-4]  _normalize_pause_timeout_minutes: negative clamped to 0.
[AJ-5]  _default_active_job_state: shape, str map_id, idle status.
[AJ-6]  _derive_active_job_current_room_id: first uncompleted resolved room.
[AJ-7]  _derive_active_job_current_room_id: skips completed, falls to queue ids.
[AJ-8]  _derive_active_job_current_room_id: all completed → None.
[AJ-9]  _normalize_active_job: fills defaults + normalizes policy fields.
[AJ-10] _normalize_active_job: derives current_room_id when absent.
[AJ-11] _normalize_active_job: current_room_started_at defaults to started_at.
[AJ-12] _normalize_active_job: non-dict input → defaulted dict.
[AJ-13] _compute_current_room_elapsed_minutes: plain elapsed.
[AJ-14] _compute_current_room_elapsed_minutes: subtracts live pause when paused.
[AJ-15] _compute_current_room_elapsed_minutes: bad timestamps → 0.0.
[AJ-16] _room_name_from_active_job: resolved-room match.
[AJ-17] _room_name_from_active_job: queue-room fallback.
[AJ-18] _room_name_from_active_job: None/negative/no-match → None.
[AJ-19] _timing_completion_threshold_minutes: high confidence → tight slack.
[AJ-20] _timing_completion_threshold_minutes: low confidence + few samples → wider slack.
[AJ-21] _live_transition_config: no adapter block → distinct copy of defaults.
[AJ-22] _live_transition_config: adapter block overrides every key; rollover_kinds → stripped tuple.
[AJ-23] _live_transition_config: all-empty rollover_kinds → default tuple; unset keys stay default.
[AJ-24] detect_run_anomalies: running_long suppressed for an unlearned room (issue #40).
[AJ-25] detect_run_anomalies: running_long still fires for a learned room (AJ-24 control).
[AJ-26] poll_stranded_started_job: Eufy strand stamps first tick, reaps only past grace.
[AJ-27] poll_stranded_started_job: task_status == completion value → no stamp, None.
[AJ-28] poll_stranded_started_job: a stamped strand that resumes clears the stamp.
[AJ-29] poll_stranded_started_job: Roborock strand (docked, not 'charging', job_active off) reaps.
[AJ-30] poll_stranded_started_job: Roborock recharge (job_active ON) → no stamp, None.
[AJ-31] poll_stranded_started_job: a paused job is left to the pause-timeout reaper.
[AJ-32] _compute_current_room_elapsed_minutes: subtracts a CLOSED non-cleaning span.
[AJ-33] _compute_current_room_elapsed_minutes: subtracts the OPEN non-cleaning interval live.
[AJ-34] _compute_current_room_elapsed_minutes: pause + non-cleaning are additive, floored at 0.
[AJ-35] _compute_current_room_elapsed_minutes: absent fields → pre-accumulator behaviour.
[AJ-36] _accumulate_current_room_noncleaning: opens an interval on a non-cleaning state.
[AJ-37] _accumulate_current_room_noncleaning: returning→docked keeps the ORIGINAL start.
[AJ-38] _accumulate_current_room_noncleaning: closing folds the span into the total.
[AJ-39] _accumulate_current_room_noncleaning: FAILS OPEN — a dropout closes the interval.
[AJ-40] _accumulate_current_room_noncleaning: no-op (no persist) while cleaning.
[AJ-41] _accumulate_current_room_noncleaning: an unmeasurable interval still closes.
[AJ-42] reopen_current_room_noncleaning: docked at the stamp → interval opens (dispatch window).
[AJ-43] reopen_current_room_noncleaning: cleaning at the stamp → nothing opened.
[AJ-44] reopen_current_room_noncleaning: unreadable live state opens nothing.
[AJ-45] reopen_current_room_noncleaning: no start stamp → nothing opened.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests._factories import spec_manager

from custom_components.eufy_vacuum.adapters.registry import clear_registry, register_adapter_config
from custom_components.eufy_vacuum.jobs.active_job import (
    ActiveJobTracker,
    _normalize_path_block_action,
    _normalize_pause_timeout_minutes,
    _safe_float,
    _safe_int,
)


@pytest.fixture
def tracker() -> ActiveJobTracker:
    """An ActiveJobTracker whose manager is a mock — pure methods never touch it."""
    return ActiveJobTracker(spec_manager())


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (5, 5), ("3.9", 3), (None, 0), ("", 0), ("unknown", 0), ("unavailable", 0), ("x", 0),
])
def test_safe_int(value, expected):
    """[AJ-1]"""
    assert _safe_int(value) == expected


def test_safe_int_default():
    """[AJ-1]"""
    assert _safe_int(None, 7) == 7


@pytest.mark.parametrize("value,expected", [
    (3.5, 3.5), (4, 4.0), (None, 0.0), ("", 0.0), ("unavailable", 0.0),
])
def test_safe_float(value, expected):
    """[AJ-2]"""
    assert _safe_float(value) == pytest.approx(expected)


@pytest.mark.parametrize("value,expected", [
    ("pause_and_event", "pause_and_event"),
    ("cancel_and_event", "cancel_and_event"),
    ("event_only", "event_only"),
    ("garbage", "event_only"),
    (None, "event_only"),
])
def test_normalize_path_block_action(value, expected):
    """[AJ-3]"""
    assert _normalize_path_block_action(value) == expected


@pytest.mark.parametrize("value,expected", [(5, 5), (-3, 0), ("10", 10), (None, 0)])
def test_normalize_pause_timeout(value, expected):
    """[AJ-4]"""
    assert _normalize_pause_timeout_minutes(value) == expected


# ---------------------------------------------------------------------------
# _default_active_job_state
# ---------------------------------------------------------------------------

def test_default_active_job_state(tracker):
    """[AJ-5]"""
    state = tracker._default_active_job_state(vacuum_entity_id="vacuum.alfred", map_id=6)
    assert state["vacuum_entity_id"] == "vacuum.alfred"
    assert state["map_id"] == "6"  # coerced to str
    assert state["status"] == "idle"
    assert state["payload"] == {"map_id": "6", "rooms": []}
    assert state["completed_room_ids"] == []
    assert state["path_block_action"] == "event_only"


# ---------------------------------------------------------------------------
# _derive_active_job_current_room_id
# ---------------------------------------------------------------------------

def test_derive_current_room_first_uncompleted(tracker):
    """[AJ-6]"""
    job = {
        "completed_room_ids": [1],
        "resolved_rooms": [{"room_id": 1}, {"room_id": 2}, {"room_id": 3}],
    }
    assert tracker._derive_active_job_current_room_id(job) == 2


def test_derive_current_room_queue_fallback(tracker):
    """[AJ-7] no resolved rooms → uses queue_room_ids, skipping completed."""
    job = {"completed_room_ids": [4], "resolved_rooms": [], "queue_room_ids": [4, 5]}
    assert tracker._derive_active_job_current_room_id(job) == 5


def test_derive_current_room_all_done(tracker):
    """[AJ-8]"""
    job = {"completed_room_ids": [1, 2], "resolved_rooms": [{"room_id": 1}, {"room_id": 2}]}
    assert tracker._derive_active_job_current_room_id(job) is None


# ---------------------------------------------------------------------------
# _normalize_active_job
# ---------------------------------------------------------------------------

def test_normalize_fills_defaults(tracker):
    """[AJ-9]"""
    out = tracker._normalize_active_job({"path_block_action": "bogus", "pause_timeout_minutes": -5})
    assert out["queue_room_ids"] == []
    assert out["status"] == "idle"
    assert out["path_block_action"] == "event_only"
    assert out["pause_timeout_minutes"] == 0


def test_normalize_derives_current_room(tracker):
    """[AJ-10]"""
    out = tracker._normalize_active_job({
        "completed_room_ids": [1],
        "resolved_rooms": [{"room_id": 1}, {"room_id": 2}],
    })
    assert out["current_room_id"] == 2


def test_normalize_current_started_defaults_to_started(tracker):
    """[AJ-11]"""
    out = tracker._normalize_active_job({"started_at": "2026-01-01T09:00:00+00:00"})
    assert out["current_room_started_at"] == "2026-01-01T09:00:00+00:00"


def test_normalize_non_dict_input(tracker):
    """[AJ-12]"""
    out = tracker._normalize_active_job("not-a-dict")  # type: ignore[arg-type]
    assert out["status"] == "idle"
    assert out["resolved_rooms"] == []


# ---------------------------------------------------------------------------
# _compute_current_room_elapsed_minutes
# ---------------------------------------------------------------------------

def test_compute_elapsed_plain(tracker):
    """[AJ-13] 10 minutes elapsed, no pauses."""
    job = {"current_room_started_at": "2026-01-01T10:00:00+00:00", "status": "cleaning"}
    result = tracker._compute_current_room_elapsed_minutes(
        active_job=job, now="2026-01-01T10:10:00+00:00")
    assert result == pytest.approx(10.0)


def test_compute_elapsed_subtracts_live_pause(tracker):
    """[AJ-14] paused 5 min ago while status==paused → 10 - 5 = 5."""
    job = {
        "current_room_started_at": "2026-01-01T10:00:00+00:00",
        "status": "paused",
        "paused_at": "2026-01-01T10:05:00+00:00",
    }
    result = tracker._compute_current_room_elapsed_minutes(
        active_job=job, now="2026-01-01T10:10:00+00:00")
    assert result == pytest.approx(5.0)


def test_compute_elapsed_bad_timestamps(tracker):
    """[AJ-15]"""
    job = {"current_room_started_at": "", "status": "cleaning"}
    assert tracker._compute_current_room_elapsed_minutes(
        active_job=job, now="not-a-date") == 0.0


# ---------------------------------------------------------------------------
# current-room non-cleaning accumulator
# ---------------------------------------------------------------------------

def _live_tracker(vacuum_state: str | None) -> ActiveJobTracker:
    """A tracker whose hass reports one fixed vacuum state.

    Deliberately NOT a bare MagicMock for the state read: a MagicMock would
    answer whatever the caller asked, and `getattr(mock, "state")` returns a
    truthy MagicMock that stringifies to something no vocabulary contains — so
    every 'is it docked?' assertion would pass for the wrong reason.
    """
    manager = spec_manager()
    manager.hass.states.get.return_value = (
        None if vacuum_state is None else SimpleNamespace(state=vacuum_state)
    )
    return ActiveJobTracker(manager)


def test_compute_elapsed_subtracts_closed_noncleaning(tracker):
    """[AJ-32] a finished non-cleaning span is removed from the room's clock."""
    job = {
        "current_room_started_at": "2026-01-01T10:00:00+00:00",
        "status": "started",
        "current_room_noncleaning_seconds": 180,
    }
    assert tracker._compute_current_room_elapsed_minutes(
        active_job=job, now="2026-01-01T10:10:00+00:00") == pytest.approx(7.0)


def test_compute_elapsed_subtracts_open_noncleaning(tracker):
    """[AJ-33] an interval still OPEN is subtracted live, exactly like a live pause.

    Without this the room's clock would keep running for the whole mop-wash trip
    and only stop being wrong once the robot came back.
    """
    job = {
        "current_room_started_at": "2026-01-01T10:00:00+00:00",
        "status": "started",
        "current_room_noncleaning_since": "2026-01-01T10:06:00+00:00",
    }
    assert tracker._compute_current_room_elapsed_minutes(
        active_job=job, now="2026-01-01T10:10:00+00:00") == pytest.approx(6.0)


def test_compute_elapsed_pause_and_noncleaning_both_subtract(tracker):
    """[AJ-34] the two exclusions are additive, and the result floors at 0 rather
    than going negative when they exceed the window."""
    job = {
        "current_room_started_at": "2026-01-01T10:00:00+00:00",
        "status": "started",
        "current_room_paused_seconds": 120,
        "current_room_noncleaning_seconds": 120,
    }
    assert tracker._compute_current_room_elapsed_minutes(
        active_job=job, now="2026-01-01T10:10:00+00:00") == pytest.approx(6.0)

    job["current_room_noncleaning_seconds"] = 100_000
    assert tracker._compute_current_room_elapsed_minutes(
        active_job=job, now="2026-01-01T10:10:00+00:00") == 0.0


def test_compute_elapsed_unchanged_when_fields_absent(tracker):
    """[AJ-35] a job dict predating these fields reads exactly as it did before."""
    job = {"current_room_started_at": "2026-01-01T10:00:00+00:00", "status": "started"}
    assert tracker._compute_current_room_elapsed_minutes(
        active_job=job, now="2026-01-01T10:10:00+00:00") == pytest.approx(10.0)


def test_accumulator_opens_on_non_cleaning(tracker):
    """[AJ-36]"""
    job = {}
    changed = tracker._accumulate_current_room_noncleaning(
        vacuum_entity_id="vacuum.alfred", active_job=job,
        to_state="returning", changed_at="2026-01-01T10:05:00+00:00")
    assert changed is True
    assert job["current_room_noncleaning_since"] == "2026-01-01T10:05:00+00:00"


def test_accumulator_does_not_restamp_within_a_span(tracker):
    """[AJ-37] returning -> docked is ONE absence from the floor.

    Re-stamping on the second transition would silently discard the drive back
    to the dock — the longest part of the span.
    """
    job = {"current_room_noncleaning_since": "2026-01-01T10:05:00+00:00"}
    changed = tracker._accumulate_current_room_noncleaning(
        vacuum_entity_id="vacuum.alfred", active_job=job,
        to_state="docked", changed_at="2026-01-01T10:06:00+00:00")
    assert changed is False
    assert job["current_room_noncleaning_since"] == "2026-01-01T10:05:00+00:00"


def test_accumulator_closes_and_totals(tracker):
    """[AJ-38] back to cleaning → the span lands in the total and the interval closes."""
    job = {
        "current_room_noncleaning_since": "2026-01-01T10:05:00+00:00",
        "current_room_noncleaning_seconds": 60,
    }
    changed = tracker._accumulate_current_room_noncleaning(
        vacuum_entity_id="vacuum.alfred", active_job=job,
        to_state="cleaning", changed_at="2026-01-01T10:08:00+00:00")
    assert changed is True
    assert job["current_room_noncleaning_seconds"] == 240  # 60 + 180
    assert job["current_room_noncleaning_since"] is None


@pytest.mark.parametrize("dropout", ["unavailable", "unknown", ""])
def test_accumulator_closes_on_dropout(tracker, dropout):
    """[AJ-39] FAIL OPEN. A dropout must CLOSE the interval, not leave it running.

    An interval left open through an unresolved dropout subtracts unboundedly:
    elapsed never reaches the threshold and the room never advances. Losing the
    dropout's own seconds is the bounded, correct trade.
    """
    job = {"current_room_noncleaning_since": "2026-01-01T10:05:00+00:00"}
    changed = tracker._accumulate_current_room_noncleaning(
        vacuum_entity_id="vacuum.alfred", active_job=job,
        to_state=dropout, changed_at="2026-01-01T10:06:00+00:00")
    assert changed is True
    assert job["current_room_noncleaning_since"] is None
    assert job["current_room_noncleaning_seconds"] == 60


def test_accumulator_noop_while_cleaning(tracker):
    """[AJ-40] cleaning -> cleaning with nothing open changes nothing (so the
    caller does not persist on every unrelated tick)."""
    job = {}
    assert tracker._accumulate_current_room_noncleaning(
        vacuum_entity_id="vacuum.alfred", active_job=job,
        to_state="cleaning", changed_at="2026-01-01T10:06:00+00:00") is False
    assert job == {}


def test_accumulator_unparseable_timestamp_still_closes(tracker):
    """[AJ-41] an interval we cannot measure must not stay open and keep
    subtracting live time."""
    job = {"current_room_noncleaning_since": "not-a-date"}
    assert tracker._accumulate_current_room_noncleaning(
        vacuum_entity_id="vacuum.alfred", active_job=job,
        to_state="cleaning", changed_at="2026-01-01T10:06:00+00:00") is True
    assert job["current_room_noncleaning_since"] is None


def test_reopen_seeds_open_interval_when_docked():
    """[AJ-42] THE dispatch-window fix: the stamp is made while the robot is on
    the dock, so the interval opens at the stamp and undock + transit is not
    charged to room one."""
    tracker = _live_tracker("docked")
    job = {"current_room_noncleaning_seconds": 900}
    tracker.reopen_current_room_noncleaning(
        vacuum_entity_id="vacuum.alfred", active_job=job,
        started_at="2026-01-01T10:00:00+00:00")
    assert job["current_room_noncleaning_seconds"] == 0
    assert job["current_room_noncleaning_since"] == "2026-01-01T10:00:00+00:00"


def test_reopen_leaves_closed_when_already_cleaning():
    """[AJ-43] a rollover mid-run must not invent a non-cleaning span."""
    tracker = _live_tracker("cleaning")
    job = {"current_room_noncleaning_seconds": 900,
           "current_room_noncleaning_since": "2026-01-01T09:00:00+00:00"}
    tracker.reopen_current_room_noncleaning(
        vacuum_entity_id="vacuum.alfred", active_job=job,
        started_at="2026-01-01T10:00:00+00:00")
    assert job["current_room_noncleaning_seconds"] == 0
    assert job["current_room_noncleaning_since"] is None


@pytest.mark.parametrize("live", [None, "unknown", "unavailable"])
def test_reopen_fails_open_on_unreadable_state(live):
    """[AJ-44] an unreadable live state opens nothing — same direction as the
    predicate itself."""
    tracker = _live_tracker(live)
    job = {}
    tracker.reopen_current_room_noncleaning(
        vacuum_entity_id="vacuum.alfred", active_job=job,
        started_at="2026-01-01T10:00:00+00:00")
    assert job["current_room_noncleaning_since"] is None


def test_reopen_without_a_start_stamp_opens_nothing():
    """[AJ-45] the final room's completion clears current_room_started_at; an
    interval anchored to None would be unmeasurable."""
    tracker = _live_tracker("docked")
    job = {}
    tracker.reopen_current_room_noncleaning(
        vacuum_entity_id="vacuum.alfred", active_job=job, started_at=None)
    assert job["current_room_noncleaning_since"] is None


# ---------------------------------------------------------------------------
# _room_name_from_active_job
# ---------------------------------------------------------------------------

def test_room_name_resolved_match(tracker):
    """[AJ-16]"""
    job = {"resolved_rooms": [{"room_id": 2, "name": "Kitchen"}]}
    assert tracker._room_name_from_active_job(job, 2) == "Kitchen"


def test_room_name_queue_fallback(tracker):
    """[AJ-17]"""
    job = {"resolved_rooms": [], "queue_rooms": [{"room_id": 3, "slug": "bath"}]}
    assert tracker._room_name_from_active_job(job, 3) == "bath"


@pytest.mark.parametrize("room_id", [None, -1, 99])
def test_room_name_no_match(tracker, room_id):
    """[AJ-18]"""
    job = {"resolved_rooms": [{"room_id": 2, "name": "Kitchen"}]}
    assert tracker._room_name_from_active_job(job, room_id) is None


# ---------------------------------------------------------------------------
# _timing_completion_threshold_minutes
# ---------------------------------------------------------------------------

def test_timing_threshold_high_confidence(tracker):
    """[AJ-19] high confidence + many samples → minimal slack (0.75)."""
    room = {"minutes": 10.0, "confidence_score": 0.9, "sample_count": 5}
    assert tracker._timing_completion_threshold_minutes(room) == pytest.approx(10.75)


def test_timing_threshold_low_confidence_few_samples(tracker):
    """[AJ-20] low confidence + single sample → wider slack."""
    room = {"minutes": 10.0, "confidence_score": 0.3, "sample_count": 1}
    # overrun 0.22 → slack max(0.75, 2.2)=2.2; sample<=1 +1.0 → 3.2; cap 4.0
    assert tracker._timing_completion_threshold_minutes(room) == pytest.approx(13.2)


# ---------------------------------------------------------------------------
# detect_run_anomalies
# ---------------------------------------------------------------------------

def test_detect_run_anomalies_disabled_for_path_optimized_order():
    """A path-optimizing adapter can jump ahead of queue order without implying
    skipped rooms or a stall in the current room."""
    clear_registry()
    register_adapter_config("vacuum.alfred", {
        "adapter_id": "roborock",
        "source": "test",
        "capabilities": {"honors_clean_order": False},
    })
    manager = spec_manager()
    manager.data = {"active_jobs": {}}
    tracker = ActiveJobTracker(manager)
    active_job = {
        "status": "started",
        "queue_room_ids": [1, 2],
        "resolved_rooms": [{"room_id": 1, "name": "Kitchen"}, {"room_id": 2, "name": "Hall"}],
    }

    result = tracker.detect_run_anomalies(
        vacuum_entity_id="vacuum.alfred",
        map_id="6",
        active_job=active_job,
        raw_timeline=[
            {"room_id": 1, "minutes": 1.0, "confidence_score": 0.9, "sample_count": 3},
            {"room_id": 2, "minutes": 1.0, "confidence_score": 0.9, "sample_count": 3},
        ],
        current_room_id=2,
        current_room_elapsed_minutes=10.0,
        completed_room_ids=[],
        awaiting_bounds_exit=True,
    )

    assert result["stall_detected"] is False
    assert result["running_long"] is False
    assert result["skipped_room_ids"] == []
    manager.hass.bus.async_fire.assert_not_called()


def _order_honoring_tracker() -> ActiveJobTracker:
    """A tracker whose adapter honors clean order (so the running_long tier runs)."""
    clear_registry()
    register_adapter_config("vacuum.alfred", {
        "adapter_id": "eufy", "source": "test",
        "capabilities": {"honors_clean_order": True},
    })
    manager = spec_manager()
    manager.data = {"active_jobs": {}}
    return ActiveJobTracker(manager)


def test_running_long_suppressed_for_unlearned_room():
    """[AJ-24] An unlearned room (source='default', sample_count=0) uses the ~6-min
    default estimate, so running_long must NOT fire on it — otherwise every normal
    new-setup room reads 'may be stuck' (issue #40). elapsed 13 min would land in the
    ~1.5x band of the ~8-min unlearned threshold; the gate suppresses it."""
    tracker = _order_honoring_tracker()
    active_job = {"status": "started", "queue_room_ids": [1],
                  "resolved_rooms": [{"room_id": 1, "name": "Kitchen"}], "counter_samples": []}
    result = tracker.detect_run_anomalies(
        vacuum_entity_id="vacuum.alfred", map_id="6", active_job=active_job,
        raw_timeline=[{"room_id": 1, "minutes": 6.0, "confidence_score": 0.2,
                       "sample_count": 0, "source": "default"}],
        current_room_id=1,
        current_room_elapsed_minutes=13.0,
        completed_room_ids=[],
        awaiting_bounds_exit=False,  # isolate running_long from the bounds-gated stall
    )
    assert result["running_long"] is False
    assert result["stall_detected"] is False


def test_running_long_fires_for_learned_room():
    """[AJ-25] Control for AJ-24: a LEARNED room with the same overrun still fires
    running_long — the #40 gate only silences the unlearned case. Threshold 10.75;
    elapsed 17 sits in the 1.5x..2x band."""
    tracker = _order_honoring_tracker()
    active_job = {"status": "started", "queue_room_ids": [1],
                  "resolved_rooms": [{"room_id": 1, "name": "Kitchen"}], "counter_samples": []}
    result = tracker.detect_run_anomalies(
        vacuum_entity_id="vacuum.alfred", map_id="6", active_job=active_job,
        raw_timeline=[{"room_id": 1, "minutes": 10.0, "confidence_score": 0.9,
                       "sample_count": 5, "source": "learned"}],
        current_room_id=1,
        current_room_elapsed_minutes=17.0,
        completed_room_ids=[],
        awaiting_bounds_exit=False,
    )
    assert result["running_long"] is True


# ---------------------------------------------------------------------------
# record_counter_sample (counter-plateau capture buffer)
# ---------------------------------------------------------------------------

def _tracker_with_job(job: dict) -> ActiveJobTracker:
    mgr = spec_manager()
    mgr.data = {"active_jobs": {"vacuum.alfred": {"6": job}}}
    return ActiveJobTracker(mgr)


def test_record_counter_sample_buffers_last_seen():
    """record_counter_sample snapshots the last-seen cleaning_time / area / battery
    into the in-flight job's counter_samples (the input to segment_counters)."""
    job = {
        "status": "started",
        "started_at": "2026-01-01T09:00:00+00:00",
        "last_cleaning_time_seconds": 30,
        "last_cleaning_area_m2": 1.0,
        "last_battery_percent": 99,
    }
    tracker = _tracker_with_job(job)
    assert tracker.record_counter_sample(vacuum_entity_id="vacuum.alfred") is True
    samples = job["counter_samples"]
    assert len(samples) == 1
    assert samples[0]["cleaning_time"] == 30
    assert samples[0]["cleaning_area"] == 1.0
    assert samples[0]["battery"] == 99


def test_record_counter_sample_skips_finalized_job():
    """RP-013e: status is the authoritative in-flight signal, not started_at/
    ended_at (nothing ever writes ended_at, so that predicate stayed true
    forever after a run). A job left in the SHAPE mark_active_job_finalized
    leaves it -- status "completed", started_at intact, ended_at absent --
    is correctly excluded on status alone."""
    job = {
        "status": "completed",
        "finalized": True,
        "started_at": "2026-01-01T09:00:00+00:00",
        "last_cleaning_time_seconds": 30,
        "last_cleaning_area_m2": 1.0,
    }
    tracker = _tracker_with_job(job)
    assert tracker.record_counter_sample(vacuum_entity_id="vacuum.alfred") is False
    assert job.get("counter_samples", []) == []


def test_record_counter_sample_external_status_is_in_flight():
    """RP-013e: run_is_in_flight (not dispatched_job_is_in_flight) is the
    correct predicate here specifically because it includes "external" --
    an app-started run is exactly what these recorders must capture."""
    job = {
        "status": "external",
        "started_at": "2026-01-01T09:00:00+00:00",
        "last_cleaning_time_seconds": 30,
        "last_cleaning_area_m2": 1.0,
    }
    tracker = _tracker_with_job(job)
    assert tracker.record_counter_sample(vacuum_entity_id="vacuum.alfred") is True
    assert len(job["counter_samples"]) == 1


def test_record_counter_sample_scoped_not_fanned_out():
    """RP-013e/REC-1+REC-4: a FINISHED job sitting in one map bucket must not
    absorb a sample meant for the live run in a different bucket -- the old
    started_at-and-not-ended_at guard fanned every write into every bucket."""
    mgr = spec_manager()
    finished = {
        "status": "completed", "finalized": True,
        "started_at": "2026-01-01T08:00:00+00:00",
        "last_cleaning_time_seconds": 999, "last_cleaning_area_m2": 40.0,
    }
    live = {
        "status": "started", "started_at": "2026-01-01T09:00:00+00:00",
        "last_cleaning_time_seconds": 30, "last_cleaning_area_m2": 1.0,
    }
    mgr.data = {"active_jobs": {"vacuum.alfred": {"6": finished, "7": live}}}
    tracker = ActiveJobTracker(mgr)

    assert tracker.record_counter_sample(vacuum_entity_id="vacuum.alfred") is True
    assert finished.get("counter_samples", []) == []
    assert len(live["counter_samples"]) == 1


def test_record_active_job_sensor_value_scoped_not_fanned_out():
    """RP-013e/REC-1+REC-4: the OTHER recorder gets the same scoping."""
    mgr = spec_manager()
    finished = {
        "status": "completed", "finalized": True,
        "started_at": "2026-01-01T08:00:00+00:00",
        "last_cleaning_time_seconds": 999,
    }
    live = {"status": "started", "started_at": "2026-01-01T09:00:00+00:00"}
    mgr.data = {"active_jobs": {"vacuum.alfred": {"6": finished, "7": live}}}
    tracker = ActiveJobTracker(mgr)

    assert tracker.record_active_job_sensor_value(
        vacuum_entity_id="vacuum.alfred", key="last_cleaning_time_seconds", value=55
    ) is True
    assert finished["last_cleaning_time_seconds"] == 999
    assert live["last_cleaning_time_seconds"] == 55


def test_select_in_flight_bucket_multiple_prefers_resolve_active_map_id():
    """RP-013e: when more than one bucket is (unusually) in flight, the one
    matching resolve_active_map_id wins over the newest started_at -- a
    stale slot must never win just by being newer."""
    mgr = spec_manager()
    mgr.resolve_active_map_id.return_value = "6"
    older_but_active_map = {
        "status": "started", "job_id": "job_a",
        "started_at": "2026-01-01T08:00:00+00:00",
    }
    newer_but_stale_map = {
        "status": "started", "job_id": "job_b",
        "started_at": "2026-01-01T09:00:00+00:00",
    }
    mgr.data = {"active_jobs": {"vacuum.alfred": {
        "6": older_but_active_map, "7": newer_but_stale_map,
    }}}
    tracker = ActiveJobTracker(mgr)

    chosen = tracker._select_in_flight_bucket(
        vacuum_entity_id="vacuum.alfred",
        per_map=mgr.data["active_jobs"]["vacuum.alfred"],
    )
    assert chosen is not None
    assert chosen[0] == "6"
    assert chosen[1] is older_but_active_map


def test_select_in_flight_bucket_multiple_falls_back_to_newest_started_at():
    """No resolve_active_map_id match -> the newest started_at wins, and the
    choice is WARNed once per job (not once per call)."""
    mgr = spec_manager()
    mgr.resolve_active_map_id.return_value = None
    older = {"status": "started", "job_id": "job_a", "started_at": "2026-01-01T08:00:00+00:00"}
    newer = {"status": "started", "job_id": "job_b", "started_at": "2026-01-01T09:00:00+00:00"}
    mgr.data = {"active_jobs": {"vacuum.alfred": {"6": older, "7": newer}}}
    tracker = ActiveJobTracker(mgr)
    per_map = mgr.data["active_jobs"]["vacuum.alfred"]

    chosen = tracker._select_in_flight_bucket(vacuum_entity_id="vacuum.alfred", per_map=per_map)
    assert chosen[0] == "7" and chosen[1] is newer
    assert ("vacuum.alfred", "job_b") in tracker._multi_in_flight_warned

    # A second call for the SAME job must not re-warn (dedup already recorded).
    warned_before = set(tracker._multi_in_flight_warned)
    tracker._select_in_flight_bucket(vacuum_entity_id="vacuum.alfred", per_map=per_map)
    assert tracker._multi_in_flight_warned == warned_before


# ---------------------------------------------------------------------------
# record_pose_sample (W5b external pose buffer for room attribution)
# ---------------------------------------------------------------------------

def _external_job() -> dict:
    return {"status": "external", "started_at": "2026-01-01T09:00:00+00:00"}


def test_record_pose_sample_buffers_external():
    job = _external_job()
    tracker = _tracker_with_job(job)
    assert tracker.record_pose_sample(
        vacuum_entity_id="vacuum.alfred", map_id="6",
        current_room=5, anchor=[0.1, 0.2], cleaning_area=2.0,
    ) is True
    s = job["pose_samples"]
    assert len(s) == 1
    assert s[0]["current_room"] == 5 and s[0]["anchor"] == [0.1, 0.2] and s[0]["cleaning_area"] == 2.0


def test_record_pose_sample_records_none_current_room():
    """None current_room (docked / off-raster) is recorded, not dropped — the parked-dock
    exclusion depends on None runs existing."""
    job = _external_job()
    tracker = _tracker_with_job(job)
    assert tracker.record_pose_sample(
        vacuum_entity_id="vacuum.alfred", map_id="6",
        current_room=None, anchor=None, cleaning_area=2.0,
    ) is True
    assert job["pose_samples"][0]["current_room"] is None


def test_record_pose_sample_buffers_dispatched_run():
    """A DISPATCHED (started) run now buffers pose too — the atomic finalize reconciles its
    positional room identity against the native current_room (reconcile_dispatched_identity)."""
    job = {"status": "started", "started_at": "2026-01-01T09:00:00+00:00"}
    tracker = _tracker_with_job(job)
    assert tracker.record_pose_sample(
        vacuum_entity_id="vacuum.alfred", map_id="6",
        current_room=5, anchor=[0.1, 0.2], cleaning_area=2.0,
    ) is True
    assert job["pose_samples"][0]["current_room"] == 5


def test_record_pose_sample_skips_idle_run():
    """A run that is neither external nor started (e.g. idle / paused between phases) buffers
    nothing — only active EXTERNAL or dispatched runs are sampled."""
    job = {"status": "idle", "started_at": "2026-01-01T09:00:00+00:00"}
    tracker = _tracker_with_job(job)
    assert tracker.record_pose_sample(
        vacuum_entity_id="vacuum.alfred", map_id="6",
        current_room=5, anchor=[0.1, 0.2], cleaning_area=2.0,
    ) is False
    assert job.get("pose_samples", []) == []


def test_record_pose_sample_skips_finalized():
    job = {"status": "external", "started_at": "2026-01-01T09:00:00+00:00",
           "ended_at": "2026-01-01T09:30:00+00:00"}
    tracker = _tracker_with_job(job)
    assert tracker.record_pose_sample(
        vacuum_entity_id="vacuum.alfred", map_id="6",
        current_room=5, anchor=None, cleaning_area=None,
    ) is False


def test_record_pose_sample_caps_buffer():
    from custom_components.eufy_vacuum.jobs.active_job import _MAX_POSE_SAMPLES
    job = _external_job()
    tracker = _tracker_with_job(job)
    for i in range(_MAX_POSE_SAMPLES + 25):
        tracker.record_pose_sample(
            vacuum_entity_id="vacuum.alfred", map_id="6",
            current_room=i, anchor=None, cleaning_area=None,
        )
    s = job["pose_samples"]
    assert len(s) == _MAX_POSE_SAMPLES
    assert s[-1]["current_room"] == _MAX_POSE_SAMPLES + 24  # del-oldest: newest survive


def test_pose_sample_is_static():
    """The stall predicate (external-run robustness Item 1): static == same current_room AND
    anchor within epsilon (or both None) AND cleaning_area not advancing."""
    from custom_components.eufy_vacuum.jobs.active_job import _pose_sample_is_static
    base = {"current_room": 5, "anchor": [10.0, 10.0], "cleaning_area": 4.0}
    assert _pose_sample_is_static(base, dict(base)) is True                      # identical
    assert _pose_sample_is_static(base, {**base, "anchor": [10.5, 9.5]}) is True  # jitter < eps
    assert _pose_sample_is_static(base, {**base, "anchor": [20.0, 10.0]}) is False  # moved
    assert _pose_sample_is_static(base, {**base, "current_room": 6}) is False     # room changed
    assert _pose_sample_is_static(base, {**base, "cleaning_area": 5.0}) is False  # area climbing = cleaning
    none_a = {"current_room": None, "anchor": None, "cleaning_area": None}
    assert _pose_sample_is_static(none_a, dict(none_a)) is True                   # both None (docked/native)
    assert _pose_sample_is_static(base, {**base, "anchor": None}) is False        # one None = transition


def test_record_pose_sample_coalesces_static_freeze():
    """A frozen-but-present robot reporting the SAME static pose every tick coalesces its tail
    into one marker once static past the threshold — so it can't flood the buffer."""
    from custom_components.eufy_vacuum.jobs.active_job import (
        _MAX_POSE_SAMPLES, _POSE_STALL_COALESCE_TICKS,
    )
    job = _external_job()
    tracker = _tracker_with_job(job)
    for i in range(5000):  # a multi-hour freeze, well past both the threshold and the 3000 cap
        tracker.record_pose_sample(
            vacuum_entity_id="vacuum.alfred", map_id="6",
            current_room=5, anchor=[10.0, 10.0], cleaning_area=4.0, observed_at=f"t{i}",
        )
    s = job["pose_samples"]
    assert len(s) <= _POSE_STALL_COALESCE_TICKS + 1  # bounded, not 5000 / the cap
    assert len(s) < _MAX_POSE_SAMPLES
    assert s[-1]["t"] == "t4999"                     # marker bumped to the latest tick
    assert s[-1]["current_room"] == 5


def test_record_pose_sample_freeze_preserves_early_real_data():
    """The load-bearing Item 1 fix: a long freeze must NOT rotate the run's real early cleaning
    samples out of the 3000-cap (the evidence-run failure that starved attribution)."""
    job = _external_job()
    tracker = _tracker_with_job(job)
    for i in range(30):  # a real early clean — moving anchor + climbing area
        tracker.record_pose_sample(
            vacuum_entity_id="vacuum.alfred", map_id="6",
            current_room=1, anchor=[float(i), 0.0], cleaning_area=float(i), observed_at=f"clean{i}",
        )
    for i in range(5000):  # then a frozen tail far exceeding the cap
        tracker.record_pose_sample(
            vacuum_entity_id="vacuum.alfred", map_id="6",
            current_room=2, anchor=[99.0, 99.0], cleaning_area=30.0, observed_at=f"freeze{i}",
        )
    s = job["pose_samples"]
    clean_samples = [x for x in s if x["current_room"] == 1]
    assert len(clean_samples) == 30                  # all real cleaning samples survive
    assert clean_samples[0]["anchor"] == [0.0, 0.0]  # the earliest one, not evicted


def test_record_pose_sample_cleaning_area_progress_not_coalesced():
    """A slow-but-cleaning robot (anchor barely moving, cleaning_area climbing) is NEVER
    coalesced — cleaning_area is the robust clean-vs-stall separator."""
    from custom_components.eufy_vacuum.jobs.active_job import _POSE_STALL_COALESCE_TICKS
    job = _external_job()
    tracker = _tracker_with_job(job)
    n = _POSE_STALL_COALESCE_TICKS + 30
    for i in range(n):
        tracker.record_pose_sample(
            vacuum_entity_id="vacuum.alfred", map_id="6",
            current_room=5, anchor=[10.0, 10.0], cleaning_area=float(i), observed_at=f"c{i}",
        )
    assert len(job["pose_samples"]) == n  # area climbs each tick => never static => all recorded


# ---------------------------------------------------------------------------
# External-run capture (W6.2): status="external" slot + setting-select snapshot
# ---------------------------------------------------------------------------

def test_start_external_capture_opens_external_slot():
    """start_external_capture seeds an in-flight slot with status='external'."""
    mgr = spec_manager()
    mgr.data = {}
    tracker = ActiveJobTracker(mgr)
    slot = tracker.start_external_capture(vacuum_entity_id="vacuum.alfred", map_id="6")
    assert slot["status"] == "external"
    assert slot["started_at"]
    assert mgr.data["active_jobs"]["vacuum.alfred"]["6"]["status"] == "external"


def test_snapshot_settings_selects_maps_and_skips(monkeypatch):
    """value_map normalizes the raw clean_mode string; unmapped selects keep their
    raw value; entries with no entity_id or an unavailable state are skipped."""
    from custom_components.eufy_vacuum.jobs import active_job as _aj
    monkeypatch.setattr(_aj, "_get_adapter_config", lambda v: {
        "settings_selects": {
            "clean_mode": {
                "entity_id": "select.alfred_cleaning_mode",
                "value_map": {"vacuum and mop": "vacuum_mop"},
            },
            "fan_speed": {"entity_id": "select.alfred_suction_level", "value_map": None},
            "absent": {"entity_id": None, "value_map": None},
        }
    })
    states = {
        "select.alfred_cleaning_mode": MagicMock(state="Vacuum and mop"),
        "select.alfred_suction_level": MagicMock(state="Turbo"),
    }
    mgr = spec_manager()
    mgr.hass.states.get = lambda eid: states.get(eid)
    out = ActiveJobTracker(mgr)._snapshot_settings_selects("vacuum.alfred")
    assert out == {"clean_mode": "vacuum_mop", "fan_speed": "Turbo"}


def test_record_counter_sample_captures_settings_for_external(monkeypatch):
    """An external slot also buffers a deduped settings timeline; a repeat with the
    same settings does not append a second entry (one per flip)."""
    from custom_components.eufy_vacuum.jobs import active_job as _aj
    monkeypatch.setattr(_aj, "_get_adapter_config", lambda v: {
        "settings_selects": {
            "clean_mode": {"entity_id": "select.alfred_cleaning_mode", "value_map": None},
        }
    })
    job = {
        "status": "external",
        "started_at": "2026-01-01T09:00:00+00:00",
        "last_cleaning_time_seconds": 30,
        "last_cleaning_area_m2": 1.0,
        "last_battery_percent": 99,
    }
    mgr = spec_manager()
    mgr.data = {"active_jobs": {"vacuum.alfred": {"6": job}}}
    mgr.hass.states.get = lambda eid: MagicMock(state="Vacuum")
    tracker = ActiveJobTracker(mgr)
    assert tracker.record_counter_sample(vacuum_entity_id="vacuum.alfred") is True
    assert job["counter_samples"][0]["cleaning_time"] == 30
    assert job["settings_samples"] == [
        {"t": job["settings_samples"][0]["t"], "settings": {"clean_mode": "Vacuum"}}
    ]
    tracker.record_counter_sample(vacuum_entity_id="vacuum.alfred")
    assert len(job["counter_samples"]) == 2        # counters always append
    assert len(job["settings_samples"]) == 1       # settings deduped (no flip)


def test_record_counter_sample_no_settings_for_internal():
    """Internal (status='started') jobs never buffer settings_samples."""
    job = {
        "status": "started",
        "started_at": "2026-01-01T09:00:00+00:00",
        "last_cleaning_time_seconds": 30,
        "last_cleaning_area_m2": 1.0,
    }
    tracker = _tracker_with_job(job)
    assert tracker.record_counter_sample(vacuum_entity_id="vacuum.alfred") is True
    assert job.get("settings_samples", []) == []


# ---------------------------------------------------------------------------
# _position_lock_reliable (capability-gated geometry — the adapter's call)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Live room rollover by counter-plateau (W5b)
# ---------------------------------------------------------------------------

def _csample(sec: int, ct: float, ca: float) -> dict:
    from datetime import datetime, timedelta
    t = datetime(2026, 1, 1, 9, 0, 0) + timedelta(seconds=sec)
    return {"t": t.isoformat(), "cleaning_time": ct, "cleaning_area": ca}


def _rollover_job(counter_samples: list[dict]) -> dict:
    return {
        "status": "started",
        "started_at": "2026-01-01T09:00:00",
        "current_room_id": 1,
        "current_room_started_at": "2026-01-01T09:00:00",
        "completed_room_ids": [],
        "completed_rooms": [],
        "queue_room_ids": [1, 2],
        "resolved_rooms": [{"room_id": 1, "name": "Kitchen"}, {"room_id": 2, "name": "Bath"}],
        "counter_samples": counter_samples,
    }


def test_live_rollover_by_counter_plateau():
    """A completed counter segment beyond recorded completions rolls the room live
    via the plateau path (ahead of the timing threshold), source=counter_plateau."""
    samples = [
        _csample(0, 0, 0), _csample(30, 30, 1), _csample(60, 60, 2),   # room 1
        _csample(400, 90, 4),                                          # room 2 started (gap > 90)
    ]
    job = _rollover_job(samples)
    tracker = _tracker_with_job(job)
    raw_timeline = [{"room_id": 1, "confidence_score": 0.5}, {"room_id": 2}]
    updated = tracker._maybe_roll_current_room_by_timing(
        vacuum_entity_id="vacuum.alfred", map_id="6", active_job=job,
        raw_timeline=raw_timeline, current_room_id=1,
        current_room_elapsed_minutes=4.0, completed_room_ids=[],
    )
    assert updated["completed_room_ids"] == [1]
    assert updated["current_room_id"] == 2
    sources = [
        c.args[1].get("source")
        for c in tracker._manager.hass.bus.async_fire.call_args_list
        if len(c.args) >= 2 and isinstance(c.args[1], dict)
    ]
    assert "counter_plateau" in sources


def test_live_no_rollover_when_room_in_progress():
    """A single in-progress segment (no completed boundary) + sub-threshold elapsed
    → no rollover."""
    samples = [_csample(0, 0, 0), _csample(30, 30, 1), _csample(60, 60, 2)]  # room 1 only
    job = _rollover_job(samples)
    tracker = _tracker_with_job(job)
    raw_timeline = [
        {"room_id": 1, "minutes": 10.0, "confidence_score": 0.9, "sample_count": 5},
        {"room_id": 2},
    ]
    updated = tracker._maybe_roll_current_room_by_timing(
        vacuum_entity_id="vacuum.alfred", map_id="6", active_job=job,
        raw_timeline=raw_timeline, current_room_id=1,
        current_room_elapsed_minutes=1.0, completed_room_ids=[],
    )
    assert updated["completed_room_ids"] == []
    assert updated["current_room_id"] == 1


# ---------------------------------------------------------------------------
# _live_transition_config (live-rollover orchestration — adapter-override merge)
# ---------------------------------------------------------------------------

def test_live_transition_config_defaults_passthrough(tracker, monkeypatch):
    """[AJ-21] No adapter `live_transition` block → a *copy* of the defaults.

    The returned dict equals _LIVE_TRANSITION_DEFAULTS but must be a distinct
    object: mutating the return must not corrupt the shared module constant.
    """
    from custom_components.eufy_vacuum.jobs import active_job as _aj
    from custom_components.eufy_vacuum.jobs.active_job import _LIVE_TRANSITION_DEFAULTS

    monkeypatch.setattr(_aj, "_get_adapter_config", lambda v: {})
    cfg = tracker._live_transition_config("vacuum.alfred")
    assert cfg == _LIVE_TRANSITION_DEFAULTS
    assert cfg is not _LIVE_TRANSITION_DEFAULTS  # distinct object
    cfg["enabled"] = "tampered"
    assert _LIVE_TRANSITION_DEFAULTS["enabled"] is True  # constant untouched


def test_live_transition_config_full_override(tracker, monkeypatch):
    """[AJ-22] Adapter block overrides every key: bool-coerces enabled /
    native_transition_source and converts a list of rollover_kinds into a
    whitespace-stripped tuple."""
    from custom_components.eufy_vacuum.jobs import active_job as _aj

    monkeypatch.setattr(_aj, "_get_adapter_config", lambda v: {
        "live_transition": {
            "enabled": False,
            "native_transition_source": True,
            "rollover_kinds": ["transit", " wash_plateau "],
        }
    })
    cfg = tracker._live_transition_config("vacuum.alfred")
    assert cfg == {
        "enabled": False,
        "native_transition_source": True,
        "rollover_kinds": ("transit", "wash_plateau"),
    }


def test_live_transition_config_blank_rollover_kinds_falls_back(tracker, monkeypatch):
    """[AJ-23] rollover_kinds that strip to all-empty → the after-clean empty
    guard keeps the default tuple; enabled / native_transition_source unspecified
    stay at their defaults."""
    from custom_components.eufy_vacuum.jobs import active_job as _aj
    from custom_components.eufy_vacuum.jobs.active_job import _LIVE_TRANSITION_DEFAULTS

    monkeypatch.setattr(_aj, "_get_adapter_config", lambda v: {
        "live_transition": {"rollover_kinds": ["", "   "]}
    })
    cfg = tracker._live_transition_config("vacuum.alfred")
    assert cfg["rollover_kinds"] == _LIVE_TRANSITION_DEFAULTS["rollover_kinds"]
    assert cfg["enabled"] == _LIVE_TRANSITION_DEFAULTS["enabled"]
    assert cfg["native_transition_source"] == _LIVE_TRANSITION_DEFAULTS["native_transition_source"]


# ---------------------------------------------------------------------------
# poll_stranded_started_job (the FN-1 reaper detection + grace)
# ---------------------------------------------------------------------------

_EUFY_CFG = {
    "adapter_id": "eufy", "source": "test", "brand": "eufy",
    "entities": {
        "task_status": "sensor.alfred_task_status",
        "dock_status": "sensor.alfred_dock_status",
        "active_cleaning_target": "sensor.alfred_active_cleaning_target",
    },
    "completion": {
        "task_status_value": "completed",
        "secondary_clear_sentinels": ["", "unknown", "unavailable", "none", "null"],
    },
    "external_mid_run_statuses": ["Returning to Charge", "Washing Mop"],
}

_ROBO_CFG = {
    "adapter_id": "roborock", "source": "test", "brand": "roborock",
    "entities": {
        "task_status": "sensor.ivy_status",
        "dock_status": "sensor.ivy_dock_status",
        "active_cleaning_target": "sensor.ivy_current_room",
        "job_active": "binary_sensor.ivy_job_active",
    },
    "completion": {"task_status_value": "charging", "require_job_active_clear": True},
}


def _poll_tracker(cfg, vac, states, active_job) -> ActiveJobTracker:
    clear_registry()
    register_adapter_config(vac, cfg)
    manager = spec_manager()
    manager.data = {"active_jobs": {vac: {"main": active_job}}}
    manager.hass.states.get.side_effect = (
        lambda eid: SimpleNamespace(state=states[eid]) if eid in states else None
    )
    return ActiveJobTracker(manager)


def _stamp(tracker, vac):
    return tracker._manager.data["active_jobs"][vac]["main"].get("stranded_since")


def test_poll_stranded_eufy_stamps_then_reaps():
    """[AJ-26] Eufy: docked, target cleared, task_status never 'completed', armed —
    the first tick stamps stranded_since; a report comes only once past the grace."""
    vac = "vacuum.alfred"
    tracker = _poll_tracker(_EUFY_CFG, vac, {
        vac: "docked",
        "sensor.alfred_task_status": "charging",          # NOT 'completed'
        "sensor.alfred_active_cleaning_target": "none",   # cleared sentinel
    }, {"status": "started", "has_observed_active_lifecycle": True, "job_id": "j1"})

    assert tracker.poll_stranded_started_job(vacuum_entity_id=vac, map_id="main",
                                             now="2026-07-11T10:00:00Z") is None
    assert _stamp(tracker, vac) == "2026-07-11T10:00:00Z"
    # within the 5-min grace → still no report
    assert tracker.poll_stranded_started_job(vacuum_entity_id=vac, map_id="main",
                                             now="2026-07-11T10:04:00Z") is None
    report = tracker.poll_stranded_started_job(vacuum_entity_id=vac, map_id="main",
                                               now="2026-07-11T10:06:00Z")
    assert report is not None
    assert report["cancel_reason"] == "stranded_no_completion"
    assert report["stranded_since"] == "2026-07-11T10:00:00Z"
    assert report["job_id"] == "j1"


def test_poll_not_stranded_when_completed():
    """[AJ-27] task_status == the brand's completion value → normal gate owns it."""
    vac = "vacuum.alfred"
    tracker = _poll_tracker(_EUFY_CFG, vac, {
        vac: "docked",
        "sensor.alfred_task_status": "completed",
        "sensor.alfred_active_cleaning_target": "none",
    }, {"status": "started", "has_observed_active_lifecycle": True})
    assert tracker.poll_stranded_started_job(vacuum_entity_id=vac, map_id="main",
                                             now="2026-07-11T10:00:00Z") is None
    assert _stamp(tracker, vac) is None


def test_poll_clears_stamp_on_resume():
    """[AJ-28] a stamped strand that then resumes (vacuum cleaning) drops the stamp."""
    vac = "vacuum.alfred"
    states = {
        vac: "docked",
        "sensor.alfred_task_status": "charging",
        "sensor.alfred_active_cleaning_target": "none",
    }
    tracker = _poll_tracker(_EUFY_CFG, vac, states,
                            {"status": "started", "has_observed_active_lifecycle": True})
    tracker.poll_stranded_started_job(vacuum_entity_id=vac, map_id="main",
                                      now="2026-07-11T10:00:00Z")
    assert _stamp(tracker, vac) == "2026-07-11T10:00:00Z"
    # robot resumes cleaning → no longer docked → strand clears
    states[vac] = "cleaning"
    states["sensor.alfred_task_status"] = "cleaning"
    assert tracker.poll_stranded_started_job(vacuum_entity_id=vac, map_id="main",
                                             now="2026-07-11T10:01:00Z") is None
    assert _stamp(tracker, vac) is None


def test_poll_stranded_roborock_reaps():
    """[AJ-29] Roborock: docked, status 'idle' (not the 'charging' completion value),
    job_active off, require_job_active_clear makes the secondary True → reaps."""
    vac = "vacuum.ivy"
    tracker = _poll_tracker(_ROBO_CFG, vac, {
        vac: "docked",
        "sensor.ivy_status": "idle",
        "sensor.ivy_current_room": "Kitchen",   # reverts to a room name, never a sentinel
        "binary_sensor.ivy_job_active": "off",
    }, {"status": "started", "has_observed_active_lifecycle": True, "job_id": "r1"})

    assert tracker.poll_stranded_started_job(vacuum_entity_id=vac, map_id="main",
                                             now="2026-07-11T10:00:00Z") is None
    report = tracker.poll_stranded_started_job(vacuum_entity_id=vac, map_id="main",
                                               now="2026-07-11T10:06:00Z")
    assert report is not None and report["cancel_reason"] == "stranded_no_completion"


def test_poll_not_stranded_roborock_recharge():
    """[AJ-30] Roborock mid-job recharge keeps job_active ON → not stranded."""
    vac = "vacuum.ivy"
    tracker = _poll_tracker(_ROBO_CFG, vac, {
        vac: "docked",
        "sensor.ivy_status": "idle",
        "sensor.ivy_current_room": "Kitchen",
        "binary_sensor.ivy_job_active": "on",    # still cleaning (recharge)
    }, {"status": "started", "has_observed_active_lifecycle": True})
    assert tracker.poll_stranded_started_job(vacuum_entity_id=vac, map_id="main",
                                             now="2026-07-11T10:00:00Z") is None
    assert _stamp(tracker, vac) is None


def test_poll_ignores_paused_job():
    """[AJ-31] a paused job is the pause-timeout reaper's; this never stamps it."""
    vac = "vacuum.alfred"
    tracker = _poll_tracker(_EUFY_CFG, vac, {
        vac: "docked",
        "sensor.alfred_task_status": "charging",
        "sensor.alfred_active_cleaning_target": "none",
    }, {"status": "paused", "has_observed_active_lifecycle": True})
    assert tracker.poll_stranded_started_job(vacuum_entity_id=vac, map_id="main",
                                             now="2026-07-11T10:00:00Z") is None
    assert _stamp(tracker, vac) is None


# --------------------------------------------------------------------------
# The live queue froze inside a multi-room phase (observed on hardware
# 2026-08-02: the card sat on Entryway at 99% while the robot was already
# cleaning Home Office).
# --------------------------------------------------------------------------


def _phased_job_with_samples():
    samples = (
        [{"t": f"2026-08-02T18:0{i}:00Z", "cleaning_area": i} for i in range(1, 9)]
        + [{"t": f"2026-08-02T18:1{i}:00Z", "cleaning_area": 8} for i in range(0, 2)]
        + [{"t": f"2026-08-02T18:2{i}:00Z", "cleaning_area": 8 + i} for i in range(0, 6)]
    )
    return samples, {
        "counter_samples": samples,
        "current_phase_index": 2,
        "phases": [
            {"phase_type": "room_group", "_timing_end_t": "2026-08-02T18:09:35Z"},
            {"phase_type": "wait", "_timing_end_t": "2026-08-02T18:11:40Z"},
            {"phase_type": "room_group"},
        ],
    }


def test_boundary_count_sees_only_the_current_phase_samples():
    """counter_samples accumulate across the whole run; completed_room_ids is RESET each
    phase. Comparing boundaries found in the whole-run stream against a per-phase
    completed count compares two different windows — and it fails in the direction that
    freezes the queue, because the whole-run stream cannot be segmented across a phase
    boundary (the dock trips break the segmenter's transit capture)."""
    from custom_components.eufy_vacuum.jobs.active_job import ActiveJobTracker

    tracker = ActiveJobTracker.__new__(ActiveJobTracker)
    samples, job = _phased_job_with_samples()
    sliced = tracker._current_phase_samples(job)

    assert len(sliced) == 6, "phase 2 must not see the run's 16 samples"
    assert all(s["t"] > "2026-08-02T18:11:40Z" for s in sliced)


def test_first_phase_and_atomic_jobs_keep_the_whole_buffer():
    """Phase 0's slice IS the buffer so far, and an atomic job has no phases at all —
    neither may change behaviour."""
    from custom_components.eufy_vacuum.jobs.active_job import ActiveJobTracker

    tracker = ActiveJobTracker.__new__(ActiveJobTracker)
    samples, job = _phased_job_with_samples()

    assert len(tracker._current_phase_samples({**job, "current_phase_index": 0})) == len(samples)
    assert len(tracker._current_phase_samples({"counter_samples": samples, "phases": None})) == len(samples)


# --------------------------------------------------------------------------
# A cancel MARKS the job; it must also stop the phase machine. Suspected after
# a live cancel appeared to re-fire (2026-08-02).
# --------------------------------------------------------------------------


def _live_phased_job():
    return {
        "vacuum_entity_id": "vacuum.alfred",
        "map_id": "12",
        "job_id": "job_x",
        "status": "started",
        "current_phase_index": 1,
        "phases": [
            {"phase_type": "room_group", "resolved_rooms": [{"room_id": 5}]},
            {"phase_type": "wait", "wait_minutes": 2, "resolved_rooms": []},
            {"phase_type": "room_group", "resolved_rooms": [{"room_id": 8}]},
        ],
    }


def _runner_over(job):
    from unittest.mock import MagicMock

    from custom_components.eufy_vacuum.jobs.phase_runner import PhaseRunner

    mgr = spec_manager()
    mgr.get_active_job = lambda **kw: job
    mgr.data = {"active_jobs": {"vacuum.alfred": {"12": job}}}
    return PhaseRunner(manager=mgr)


@pytest.mark.asyncio
async def test_a_finalized_job_cannot_advance_a_phase():
    """`_cancel_in_flight` only covers the cancel WHILE IT RUNS — finalizing clears it.
    Without a finalized/status check a late caller (a wait poller passing its deadline,
    the completion event from the cancel's own dock) advances the job and dispatches the
    next phase: the robot cleans again after you cancelled it."""
    job = _live_phased_job()
    job["status"] = "completed"
    job["finalized"] = True
    job["_cancel_in_flight"] = False          # cleared by mark_active_job_finalized
    runner = _runner_over(job)

    advanced = await runner.maybe_advance_phase(vacuum_entity_id="vacuum.alfred", map_id="12")

    assert advanced is False
    assert job["current_phase_index"] == 1, "a finalized job advanced a phase"


@pytest.mark.asyncio
async def test_a_paused_job_cannot_advance_a_phase():
    """Resume re-arms the phase; advancing underneath a pause would double-drive it."""
    job = _live_phased_job()
    job["status"] = "paused"
    runner = _runner_over(job)

    assert await runner.maybe_advance_phase(vacuum_entity_id="vacuum.alfred", map_id="12") is False
    assert job["current_phase_index"] == 1


# --------------------------------------------------------------------------
# The phases-guard belongs on the NATIVE branch, not the whole function.
# A phased run's clean phase is an ATOMIC JOB and must roll its rooms.
# --------------------------------------------------------------------------


def _rollover_src():
    from pathlib import Path

    import custom_components.eufy_vacuum.jobs.active_job as aj

    src = Path(aj.__file__).read_text(encoding="utf-8")
    start = src.index("def _maybe_roll_current_room_by_timing")
    end = src.index("def _maybe_roll_current_room_by_native_signal")
    return src[start:end]


def test_the_phases_guard_no_longer_blocks_the_whole_rollover():
    """It used to sit at the top of _maybe_roll_current_room_by_timing and return for ANY
    job with phases. On Eufy that suppressed paths which could never carry the failure it
    was written for — an Eufy room_group phase holds N rooms in ONE dispatch
    (EufyRoomCleanEngine ignores strict_order), so this was the sole reason rooms never
    advanced inside a group."""
    body = _rollover_src()
    guard = 'if active_job.get("phases"):'
    assert guard in body, "the guard vanished entirely — it must move, not disappear"

    native = body.index("native_transition_source")
    assert body.index(guard) > native, (
        "the phases guard is still ahead of the native branch, so it still blocks "
        "counter_plateau and timing_rollover for every phased job"
    )


def test_the_guard_still_protects_the_native_path():
    """108fe97's failure — a 0.55-min phantom completion at job start, source
    native_signal, on a Roborock S6 — lives entirely in the native branch. Roborock
    registers native_transition_source=True, so that path must stay guarded."""
    body = _rollover_src()
    native_idx = body.index("native_transition_source")
    tail = body[native_idx:]
    guard_idx = tail.index('if active_job.get("phases"):')
    call_idx = tail.index("_maybe_roll_current_room_by_native_signal")
    assert guard_idx < call_idx, (
        "the guard must precede the native rollover call, or the phantom returns"
    )
