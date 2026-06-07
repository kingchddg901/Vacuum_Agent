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
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.jobs.active_job import (
    ActiveJobTracker,
    _apply_cleaning_time_sample,
    _close_open_cleaning_segment,
    _normalize_path_block_action,
    _normalize_pause_timeout_minutes,
    _safe_float,
    _safe_int,
)


@pytest.fixture
def tracker() -> ActiveJobTracker:
    """An ActiveJobTracker whose manager is a mock — pure methods never touch it."""
    return ActiveJobTracker(MagicMock())


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
# cleaning_time segmentation (transit capture) — pure module helpers
# ---------------------------------------------------------------------------

def _ts(minute: int) -> str:
    return f"2026-01-01T09:{minute:02d}:00+00:00"


def test_cleaning_time_segmentation_two_rooms():
    """[AJ-T1] reset/rise/plateau folds cleaning_time into one segment per room."""
    job = {"current_room_id": 1, "cleaning_time_segments": []}
    # Room 1: baseline 0, rise to 90 with a plateau, then reset.
    _apply_cleaning_time_sample(job, 0, _ts(0))    # baseline -> no segment yet
    assert job["cleaning_time_segments"] == []
    _apply_cleaning_time_sample(job, 30, _ts(1))   # first rise -> open seg1
    _apply_cleaning_time_sample(job, 60, _ts(2))
    _apply_cleaning_time_sample(job, 60, _ts(3))   # plateau -> no boundary
    _apply_cleaning_time_sample(job, 90, _ts(4))
    assert len(job["cleaning_time_segments"]) == 1
    seg1 = job["cleaning_time_segments"][0]
    assert seg1["room_id"] == 1
    assert seg1["first_value"] == 0 and seg1["peak_value"] == 90
    assert seg1["cleaning_start"] == _ts(1) and seg1["cleaning_end"] == _ts(4)
    assert seg1["open"] is True

    # Room boundary: reset closes seg1; advance current_room_id to 2.
    _apply_cleaning_time_sample(job, 0, _ts(8))    # reset -> close seg1
    assert job["cleaning_time_segments"][0]["open"] is False
    job["current_room_id"] = 2
    _apply_cleaning_time_sample(job, 30, _ts(9))   # rise -> open seg2
    _apply_cleaning_time_sample(job, 60, _ts(10))
    assert len(job["cleaning_time_segments"]) == 2
    seg2 = job["cleaning_time_segments"][1]
    assert seg2["room_id"] == 2
    assert seg2["first_value"] == 0 and seg2["peak_value"] == 60
    assert seg2["cleaning_start"] == _ts(9)


def test_cleaning_time_plateau_does_not_extend_end():
    """[AJ-T2] a plateau (no rise) leaves cleaning_end at the last rise."""
    job = {"current_room_id": 5, "cleaning_time_segments": []}
    _apply_cleaning_time_sample(job, 0, _ts(0))
    _apply_cleaning_time_sample(job, 30, _ts(1))
    _apply_cleaning_time_sample(job, 30, _ts(5))   # plateau (mop wash dwell)
    _apply_cleaning_time_sample(job, 30, _ts(9))   # plateau
    seg = job["cleaning_time_segments"][0]
    assert seg["cleaning_end"] == _ts(1)           # last rise, not the plateau


def test_cleaning_time_leading_stale_value_then_reset():
    """[AJ-T3] a stale prior value followed by a reset opens no segment until the
    first genuine rise (so the dock->room leg is never counted as cleaning)."""
    job = {"current_room_id": 1, "cleaning_time_segments": []}
    _apply_cleaning_time_sample(job, 540, _ts(0))  # stale baseline from prior job
    _apply_cleaning_time_sample(job, 0, _ts(1))    # reset -> still no segment
    assert job["cleaning_time_segments"] == []
    _apply_cleaning_time_sample(job, 30, _ts(2))   # first real rise
    assert len(job["cleaning_time_segments"]) == 1
    assert job["cleaning_time_segments"][0]["first_value"] == 0


def test_close_open_cleaning_segment_idempotent():
    """[AJ-T4] _close_open_cleaning_segment closes the open segment, then no-ops."""
    job = {"current_room_id": 1, "cleaning_time_segments": []}
    _apply_cleaning_time_sample(job, 0, _ts(0))
    _apply_cleaning_time_sample(job, 30, _ts(1))
    assert _close_open_cleaning_segment(job) is not None
    assert job["cleaning_time_segments"][0]["open"] is False
    assert _close_open_cleaning_segment(job) is None   # nothing open now
