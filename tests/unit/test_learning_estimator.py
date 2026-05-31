"""Unit tests for learning/estimator.py — pure compute helpers + LearningEstimator.

Coverage targets
----------------
[LE-1]  _breakpoint_for_score maps score ranges to correct breakpoint keys.
[LE-2]  _confidence_result clamps and returns full confidence dict.
[LE-3]  _score_room_confidence: learned base + sample bonus raises score.
[LE-4]  _score_room_confidence: variance penalty lowers score.
[LE-5]  _score_room_confidence: intensity mismatch applies penalty.
[LE-6]  _score_room_confidence: accuracy drift applies penalty.
[LE-7]  _score_room_confidence: default source uses 0.20 base.
[LE-8]  _learning_velocity returns 0 for tiers already reached.
[LE-9]  _learning_velocity returns positive runs_to_high for new vacuum.
[LE-10] _compute_overhead: startup + transition + return are always present.
[LE-11] _compute_overhead: mop wash cycles scale with projected_mop_minutes.
[LE-12] _compute_overhead: non-by_time mode yields 0 wash cycles.
[LE-13] _normalize_wash_frequency_mode: alias lookup works.
[LE-14] _normalize_wash_frequency_mode: empty/None → 'unknown'.
[LE-15] _find_room_match: exact match returned with intensity_mismatch=False.
[LE-16] _find_room_match: falls back to ignore-intensity pass.
[LE-17] _find_room_match: no match returns (None, False).
[LE-18] LearningEstimator.estimate: empty ordered_rooms returns error payload.
[LE-19] LearningEstimator.estimate: default-only rooms returns full result dict.
[LE-20] LearningEstimator.next_room: returns first non-completed room.
[LE-21] LearningEstimator.next_room: returns None when all rooms completed.
[LE-22] LearningEstimator.reanchor_timeline: completed rooms update offsets.
[LE-23] LearningEstimator.reanchor_timeline: remaining rooms marked current/remaining.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.eufy_vacuum.learning.estimator import (
    LearningEstimator,
    _breakpoint_for_score,
    _compute_overhead,
    _confidence_result,
    _find_room_match,
    _learning_velocity,
    _normalize_wash_frequency_mode,
    _score_room_confidence,
)


# ---------------------------------------------------------------------------
# [LE-1] _breakpoint_for_score
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("score,expected_key", [
    (0.00, "low"),
    (0.30, "low"),
    (0.49, "low"),
    (0.50, "medium"),
    (0.65, "medium"),
    (0.79, "medium"),
    (0.80, "high"),
    (1.00, "high"),
])
def test_breakpoint_for_score(score, expected_key):
    """[LE-1] Scores map to the correct breakpoint key."""
    bp = _breakpoint_for_score(score)
    assert bp["key"] == expected_key


# ---------------------------------------------------------------------------
# [LE-2] _confidence_result
# ---------------------------------------------------------------------------

def test_confidence_result_structure():
    """[LE-2] Returns full confidence dict with all required keys."""
    result = _confidence_result(0.75)
    assert "confidence_score" in result
    assert "confidence_label" in result
    assert "confidence_breakpoint" in result


def test_confidence_result_clamps_above_one():
    """[LE-2] Scores above 1.0 are clamped to 1.0."""
    result = _confidence_result(1.5)
    assert result["confidence_score"] == 1.0


def test_confidence_result_clamps_below_zero():
    """[LE-2] Scores below 0.0 are clamped to 0.0."""
    result = _confidence_result(-0.5)
    assert result["confidence_score"] == 0.0


# ---------------------------------------------------------------------------
# [LE-3] / [LE-4] / [LE-5] / [LE-6] / [LE-7] _score_room_confidence
# ---------------------------------------------------------------------------

def test_score_learned_base_above_default():
    """[LE-3] Learned source with 0 samples scores higher than default."""
    learned = _score_room_confidence(
        source="learned", sample_count=0, avg_minutes=10.0, minutes_stddev=0.0
    )
    default = _score_room_confidence(
        source="default", sample_count=0, avg_minutes=10.0, minutes_stddev=0.0
    )
    assert learned > default


def test_score_sample_bonus_raises_score():
    """[LE-3] More samples produce a higher score."""
    few = _score_room_confidence(
        source="learned", sample_count=1, avg_minutes=10.0, minutes_stddev=0.0
    )
    many = _score_room_confidence(
        source="learned", sample_count=10, avg_minutes=10.0, minutes_stddev=0.0
    )
    assert many > few


def test_score_variance_penalty_applied():
    """[LE-4] High stddev lowers score relative to low stddev."""
    low_var = _score_room_confidence(
        source="learned", sample_count=5, avg_minutes=10.0, minutes_stddev=0.1
    )
    high_var = _score_room_confidence(
        source="learned", sample_count=5, avg_minutes=10.0, minutes_stddev=8.0
    )
    assert low_var > high_var


def test_score_intensity_mismatch_penalty():
    """[LE-5] intensity_mismatch=True lowers the score."""
    no_mismatch = _score_room_confidence(
        source="learned", sample_count=5, avg_minutes=10.0, minutes_stddev=0.5
    )
    with_mismatch = _score_room_confidence(
        source="learned", sample_count=5, avg_minutes=10.0, minutes_stddev=0.5,
        intensity_mismatch=True
    )
    assert no_mismatch > with_mismatch


def test_score_accuracy_drift_penalty():
    """[LE-6] Higher accuracy drift ratio lowers the score."""
    no_drift = _score_room_confidence(
        source="learned", sample_count=5, avg_minutes=10.0, minutes_stddev=0.5,
        accuracy_drift_ratio=0.0
    )
    high_drift = _score_room_confidence(
        source="learned", sample_count=5, avg_minutes=10.0, minutes_stddev=0.5,
        accuracy_drift_ratio=0.5
    )
    assert no_drift > high_drift


def test_score_default_source_low_base():
    """[LE-7] Default source produces score in 'low' confidence tier with no samples."""
    score = _score_room_confidence(
        source="default", sample_count=0, avg_minutes=10.0, minutes_stddev=0.0
    )
    bp = _breakpoint_for_score(score)
    assert bp["key"] == "low"


def test_score_clamped_to_zero_to_one():
    """[LE-7] Score never goes below 0 or above 1."""
    score = _score_room_confidence(
        source="default", sample_count=0, avg_minutes=10.0, minutes_stddev=20.0,
        intensity_mismatch=True, accuracy_drift_ratio=1.0
    )
    assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# [LE-8] / [LE-9] _learning_velocity
# ---------------------------------------------------------------------------

def test_learning_velocity_zero_when_already_high():
    """[LE-8] runs_to_high=0 when sample count already saturates the formula."""
    velocity = _learning_velocity(10, 0.85)
    assert velocity["runs_to_high"] == 0


def test_learning_velocity_positive_for_new_vacuum():
    """[LE-9] New vacuum (0 samples): already at medium (base=0.55 > 0.50 threshold),
    but still needs runs to reach high (base=0.55 < 0.80 threshold)."""
    velocity = _learning_velocity(0, 0.20)
    # _SAMPLES_FOR_MEDIUM = ceil((0.50-0.55)/0.25*10) = ceil(-2) = -2 → max(-2-0,0) = 0
    assert velocity["runs_to_medium"] == 0
    # _SAMPLES_FOR_HIGH = ceil((0.80-0.55)/0.25*10) = ceil(10) = 10 → max(10-0,0) = 10
    assert velocity["runs_to_high"] > 0


def test_learning_velocity_returns_current_tier():
    """[LE-9] current_tier reflects the supplied score."""
    velocity = _learning_velocity(0, 0.60)
    assert velocity["current_tier"] == "medium"


# ---------------------------------------------------------------------------
# [LE-10] / [LE-11] / [LE-12] _compute_overhead
# ---------------------------------------------------------------------------

def _default_mop_config(**overrides) -> dict:
    base = {
        "mode": "unknown",
        "interval_minutes": 20.0,
        "mode_available": False,
        "interval_available": False,
        "mode_entity_id": None,
        "interval_entity_id": None,
    }
    base.update(overrides)
    return base


def test_compute_overhead_always_has_startup_and_return():
    """[LE-10] startup and return overhead are always > 0."""
    result = _compute_overhead(
        room_count=2,
        room_minutes_total=20.0,
        total_battery_estimate=10.0,
        projected_mop_minutes=0.0,
        mop_wash_config=_default_mop_config(),
    )
    assert result["overhead"]["startup_minutes"] > 0
    assert result["overhead"]["return_minutes"] > 0


def test_compute_overhead_transitions_scale_with_rooms():
    """[LE-10] More rooms → more transition overhead."""
    r1 = _compute_overhead(
        room_count=2, room_minutes_total=20.0, total_battery_estimate=10.0,
        projected_mop_minutes=0.0, mop_wash_config=_default_mop_config(),
    )
    r3 = _compute_overhead(
        room_count=4, room_minutes_total=20.0, total_battery_estimate=10.0,
        projected_mop_minutes=0.0, mop_wash_config=_default_mop_config(),
    )
    assert r3["overhead"]["transition_minutes"] > r1["overhead"]["transition_minutes"]


def test_compute_overhead_mop_wash_cycles_by_time():
    """[LE-11] by_time mode with sufficient mop minutes produces wash cycles."""
    result = _compute_overhead(
        room_count=3,
        room_minutes_total=60.0,
        total_battery_estimate=20.0,
        projected_mop_minutes=45.0,
        mop_wash_config=_default_mop_config(mode="by_time", interval_minutes=20.0),
    )
    assert result["overhead"]["mop_wash"]["cycle_count"] >= 2


def test_compute_overhead_no_mop_wash_for_non_by_time():
    """[LE-12] Non-by_time mode yields 0 wash cycles."""
    result = _compute_overhead(
        room_count=2,
        room_minutes_total=30.0,
        total_battery_estimate=15.0,
        projected_mop_minutes=30.0,
        mop_wash_config=_default_mop_config(mode="by_room", interval_minutes=20.0),
    )
    assert result["overhead"]["mop_wash"]["cycle_count"] == 0


# ---------------------------------------------------------------------------
# [LE-13] / [LE-14] _normalize_wash_frequency_mode
# ---------------------------------------------------------------------------

def test_normalize_wash_frequency_mode_alias_lookup():
    """[LE-13] Alias dict maps brand display strings to canonical keys."""
    aliases = {"by room": "by_room", "by time": "by_time"}
    assert _normalize_wash_frequency_mode("By Room", aliases=aliases) == "by_room"
    assert _normalize_wash_frequency_mode("BY TIME", aliases=aliases) == "by_time"


def test_normalize_wash_frequency_mode_empty_returns_unknown():
    """[LE-14] Empty string and None both return 'unknown'."""
    assert _normalize_wash_frequency_mode("") == "unknown"
    assert _normalize_wash_frequency_mode(None) == "unknown"


def test_normalize_wash_frequency_mode_passthrough_without_alias():
    """[LE-13] Unknown value passes through (spaces → underscores)."""
    result = _normalize_wash_frequency_mode("after each clean", aliases={})
    assert result == "after_each_clean"


# ---------------------------------------------------------------------------
# [LE-15] / [LE-16] / [LE-17] _find_room_match
# ---------------------------------------------------------------------------

def _make_stat(**overrides) -> dict:
    base = {
        "map_id": 1,
        "room_slug": "kitchen",
        "effective_mode": "vacuum",
        "clean_times": 1,
        "is_carpet": False,
        "clean_intensity": "standard",
        "avg_minutes": 8.0,
        "avg_battery_used": 1.0,
        "sample_count": 5,
        "minutes_stddev": 0.5,
    }
    base.update(overrides)
    return base


def test_find_room_match_exact():
    """[LE-15] Exact match returned with intensity_mismatch=False."""
    stats = [_make_stat()]
    match, mismatch = _find_room_match(
        room_stats=stats, map_id=1, slug="kitchen",
        clean_mode="vacuum", clean_passes=1, is_carpet=False,
        clean_intensity="standard",
    )
    assert match is not None
    assert mismatch is False


def test_find_room_match_intensity_fallback():
    """[LE-16] When exact fails, match at different intensity returns intensity_mismatch=True."""
    stats = [_make_stat(clean_intensity="deep")]
    match, mismatch = _find_room_match(
        room_stats=stats, map_id=1, slug="kitchen",
        clean_mode="vacuum", clean_passes=1, is_carpet=False,
        clean_intensity="standard",
    )
    assert match is not None
    assert mismatch is True


def test_find_room_match_no_match():
    """[LE-17] No matching stat returns (None, False)."""
    stats = [_make_stat(room_slug="bedroom")]
    match, mismatch = _find_room_match(
        room_stats=stats, map_id=1, slug="kitchen",
        clean_mode="vacuum", clean_passes=1, is_carpet=False,
        clean_intensity="standard",
    )
    assert match is None
    assert mismatch is False


# ---------------------------------------------------------------------------
# [LE-18] / [LE-19] LearningEstimator.estimate
# ---------------------------------------------------------------------------

def _make_hass(tmp_path) -> MagicMock:
    hass = MagicMock()
    hass.config.config_dir = str(tmp_path)
    hass.states.get.return_value = None
    return hass


def test_estimator_estimate_empty_rooms_returns_error(tmp_path):
    """[LE-18] estimate() with no rooms returns error payload with error='no_payload'."""
    estimator = LearningEstimator(_make_hass(tmp_path))
    result = estimator.estimate(
        vacuum_entity_id="vacuum.alfred",
        map_id="1",
        ordered_rooms=[],
    )
    assert result["error"] == "no_payload"
    assert result["can_run_now"] is False


def test_estimator_estimate_default_rooms_full_result(tmp_path):
    """[LE-19] estimate() with rooms returns full result including all required keys."""
    estimator = LearningEstimator(_make_hass(tmp_path))
    rooms = [
        {"slug": "kitchen", "clean_mode": "vacuum", "clean_passes": 1,
         "clean_intensity": "standard", "carpet": False, "name": "Kitchen", "room_id": 1},
        {"slug": "living", "clean_mode": "vacuum", "clean_passes": 1,
         "clean_intensity": "standard", "carpet": False, "name": "Living", "room_id": 2},
    ]
    result = estimator.estimate(
        vacuum_entity_id="vacuum.alfred",
        map_id="1",
        ordered_rooms=rooms,
    )
    assert result["room_count"] == 2
    assert result["can_run_now"] is True
    assert "total_minutes" in result
    assert "breakdown" in result
    assert len(result["breakdown"]) == 2
    assert result["breakdown"][0]["source"] == "default"


# ---------------------------------------------------------------------------
# [LE-20] / [LE-21] LearningEstimator.next_room
# ---------------------------------------------------------------------------

def _make_estimate_with_timeline(rooms: list[dict]) -> dict:
    return {"room_timeline": rooms}


def test_next_room_returns_first_incomplete(tmp_path):
    """[LE-20] next_room returns the first non-completed room."""
    estimator = LearningEstimator(_make_hass(tmp_path))
    timeline = [
        {"room_id": 1, "completed": True, "room_name": "A"},
        {"room_id": 2, "completed": False, "room_name": "B", "slug": "b",
         "position": 2, "minutes": 8.0, "eta_at": "2024-01-01T12:00:00",
         "eta_minutes_from_start": 16.0, "confidence_score": 0.5,
         "confidence_label": "medium", "confidence_breakpoint": {}},
    ]
    result = estimator.next_room(reanchored_estimate=_make_estimate_with_timeline(timeline))
    assert result is not None
    assert result["room_id"] == 2


def test_next_room_returns_none_when_all_complete(tmp_path):
    """[LE-21] next_room returns None when all rooms are completed."""
    estimator = LearningEstimator(_make_hass(tmp_path))
    timeline = [
        {"room_id": 1, "completed": True},
        {"room_id": 2, "completed": True},
    ]
    result = estimator.next_room(reanchored_estimate=_make_estimate_with_timeline(timeline))
    assert result is None


# ---------------------------------------------------------------------------
# [LE-22] / [LE-23] LearningEstimator.reanchor_timeline
# ---------------------------------------------------------------------------

def _minimal_estimate(rooms: list[dict]) -> dict:
    return {
        "room_timeline": rooms,
        "started_at": "2024-01-01T12:00:00",
        "overhead_minutes": 5.0,
        "vacuum_entity_id": "vacuum.alfred",
    }


def test_reanchor_marks_completed_room(tmp_path):
    """[LE-22] Completed rooms get completed=True and actual_duration_minutes."""
    estimator = LearningEstimator(_make_hass(tmp_path))
    original = _minimal_estimate([
        {"room_id": 1, "slug": "kitchen", "minutes": 8.0, "battery": 1.0,
         "completed": False, "current": False, "remaining": True},
        {"room_id": 2, "slug": "living", "minutes": 10.0, "battery": 1.0,
         "completed": False, "current": False, "remaining": True},
    ])
    result = estimator.reanchor_timeline(
        original_estimate=original,
        completed_rooms=[{"room_id": 1, "actual_duration_minutes": 7.5}],
    )
    timeline = result["room_timeline"]
    assert timeline[0]["completed"] is True
    assert timeline[0]["actual_duration_minutes"] == 7.5
    assert timeline[1]["completed"] is False


def test_reanchor_first_unresolved_marked_current(tmp_path):
    """[LE-23] The first non-completed room is marked current=True."""
    estimator = LearningEstimator(_make_hass(tmp_path))
    original = _minimal_estimate([
        {"room_id": 1, "slug": "a", "minutes": 8.0, "battery": 1.0,
         "completed": False, "current": False, "remaining": True},
        {"room_id": 2, "slug": "b", "minutes": 10.0, "battery": 1.0,
         "completed": False, "current": False, "remaining": True},
    ])
    result = estimator.reanchor_timeline(
        original_estimate=original,
        completed_rooms=[],
    )
    timeline = result["room_timeline"]
    assert timeline[0]["current"] is True
    assert timeline[1]["current"] is False
    assert timeline[1]["remaining"] is True
