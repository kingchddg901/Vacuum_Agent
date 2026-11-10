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
[LE-24] _is_stats_stale: a fresh rebuild is not stale.
[LE-25] _is_stats_stale: exactly at the threshold is NOT stale (the gate is `>`).
[LE-26] _is_stats_stale: one day past the threshold IS stale.
        LE-25/LE-26 are a PAIR -- together they fence _STALE_THRESHOLD_DAYS in
        both directions, which one test on either side cannot do.
[LE-27] _is_stats_stale: absent/empty stats read as stale, not fresh.
[LE-28] _is_stats_stale: an unparseable `rebuilt_at` fails SAFE (stale).
[LE-29] _is_stats_stale: honours `room_stats_data` instead of reading the store.
[LE-30] estimate(): all FOUR transit tiers in one job, each a distinct number -- the
        room_baselines/ingress index (tier 2) had never been built at all.
[LE-31] estimate(): a job-stats read that RAISES costs the global tier and nothing else.
[LE-32] _find_room_match: passes 3, 4 and 5 each WIN a contest against the rungs
        below them -- which is the only way to pin a rung, since the function returns
        no rung indicator and a broken rung hands its entry down intact.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from custom_components.eufy_vacuum.learning.estimator import (
    _TRANSITION_PER_ROOM,
    LearningEstimator,
    _breakpoint_for_score,
    _compute_overhead,
    _confidence_result,
    _bucket_ratio,
    _find_room_match,
    _learning_velocity,
    _lookup_transit_minutes,
    _measured_setting_ratio,
    _normalize_wash_frequency_mode,
    _relaxed_setting_scale,
    _score_room_confidence,
)
from custom_components.eufy_vacuum.timestamp_utils import utc_now


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
    # RP-036/EST-1: the dead band between medium's labeled 0.79 max and
    # high's 0.80 min — previously matched NEITHER closed interval and fell
    # through to a hardcoded LOW. Every other case above/below is unchanged
    # by the fix (see test_breakpoint_for_score_out_of_range_returns_nearest
    # for the fallthrough itself).
    (0.795, "medium"),
    (0.80, "high"),
    (1.00, "high"),
])
def test_breakpoint_for_score(score, expected_key):
    """[LE-1] Scores map to the correct breakpoint key."""
    bp = _breakpoint_for_score(score)
    assert bp["key"] == expected_key


def test_breakpoint_for_score_out_of_range_returns_nearest():
    """RP-036/EST-1: the fallthrough (only reachable for a score outside
    [0.0, 1.0] — both real scoring paths clamp before calling this) computes
    a genuine nearest-bucket-by-distance result, not a hardcoded LOW."""
    assert _breakpoint_for_score(-5.0)["key"] == "low"


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
    # No ceiling supplied (the default) — reachability is assumed True,
    # exactly the pre-RP-036 behavior this call site relied on.
    assert velocity["high_reachable"] is True


def test_learning_velocity_no_ceiling_defaults_reachable():
    """RP-036/EST-5: omitting ceiling_score (2-arg call, the pre-fix call
    shape) preserves the old unconditional-promise behavior exactly —
    backward compatible for any caller that hasn't been updated to supply one."""
    velocity = _learning_velocity(10, 0.85)
    assert velocity["high_reachable"] is True
    assert velocity["runs_to_high"] == 0


def test_learning_velocity_unreachable_ceiling_nulls_runs_to_high():
    """RP-036/EST-5: a realistic variance profile — sample bonus saturated
    (10 samples) but a ceiling capped below HIGH by nonzero variance — must
    not promise runs_to_high will ever arrive. _SAMPLES_FOR_HIGH (10) says
    "0 more runs" here; that promise is exactly what this guards against."""
    velocity = _learning_velocity(10, 0.55, ceiling_score=0.55)
    assert velocity["high_reachable"] is False
    assert velocity["runs_to_high"] is None
    assert velocity["achievable_ceiling_tier"] == "medium"


def test_learning_velocity_reachable_ceiling_keeps_runs_to_high():
    """RP-036/EST-5: a ceiling AT or ABOVE the HIGH threshold reports
    reachable and leaves runs_to_high as the normal countdown — the fix
    only withholds the promise when it is actually false."""
    velocity = _learning_velocity(0, 0.55, ceiling_score=0.80)
    assert velocity["high_reachable"] is True
    assert velocity["runs_to_high"] is not None
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


def test_find_room_match_edge_split():
    """Exact match respects edge_mopping; each edge variant returns its own stat."""
    stats = [
        _make_stat(edge_mopping=True, avg_minutes=12.0),
        _make_stat(edge_mopping=False, avg_minutes=8.0),
    ]
    on, on_mm = _find_room_match(
        room_stats=stats, map_id=1, slug="kitchen", clean_mode="vacuum",
        clean_passes=1, is_carpet=False, clean_intensity="standard", edge_mopping=True,
    )
    off, off_mm = _find_room_match(
        room_stats=stats, map_id=1, slug="kitchen", clean_mode="vacuum",
        clean_passes=1, is_carpet=False, clean_intensity="standard", edge_mopping=False,
    )
    assert on["avg_minutes"] == 12.0 and on_mm is False
    assert off["avg_minutes"] == 8.0 and off_mm is False


def test_find_room_match_relaxed_pass_prefers_highest_sample_count():
    """RP-036/EST-6: a relaxed pass (here, ignore-intensity) with more than
    one structural match deterministically prefers the highest sample_count,
    not whichever happened to iterate first."""
    stats = [
        _make_stat(clean_intensity="deep", sample_count=2, avg_minutes=9.0),
        _make_stat(clean_intensity="quiet", sample_count=40, avg_minutes=7.5),
    ]
    match, mismatch = _find_room_match(
        room_stats=stats, map_id=1, slug="kitchen", clean_mode="vacuum",
        clean_passes=1, is_carpet=False, clean_intensity="standard",
    )
    assert mismatch is True
    assert match["sample_count"] == 40
    assert match["avg_minutes"] == 7.5


def test_find_room_match_intensity_helper_handles_none():
    """RP-036/EST-3: the matcher's intensity comparison is routed through
    the shared canonical helper, so an explicit clean_intensity=None on a
    room_stats entry normalizes to "standard" like an absent key would,
    rather than a literal "none" string that could never match a real query."""
    stats = [_make_stat(clean_intensity=None)]
    match, mismatch = _find_room_match(
        room_stats=stats, map_id=1, slug="kitchen", clean_mode="vacuum",
        clean_passes=1, is_carpet=False, clean_intensity="standard",
    )
    assert match is not None
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


def test_estimator_estimate_learned_match(tmp_path, monkeypatch):
    """[LE-19b] when _find_room_match returns a learned match, the breakdown entry
    is source='learned' using the matched stats (the learned branch + room_key /
    drift_ratio lookup)."""
    from custom_components.eufy_vacuum.learning import estimator as _est

    estimator = _est.LearningEstimator(_make_hass(tmp_path))
    monkeypatch.setattr(_est, "_find_room_match", lambda **kw: (
        {"avg_minutes": 12.5, "avg_battery_used": 6.0,
         "sample_count": 8, "minutes_stddev": 1.2}, False))
    rooms = [{"slug": "kitchen", "clean_mode": "vacuum", "clean_passes": 1,
              "clean_intensity": "standard", "carpet": False, "name": "Kitchen", "room_id": 1}]
    result = estimator.estimate(
        vacuum_entity_id="vacuum.alfred", map_id="1", ordered_rooms=rooms)
    assert result["breakdown"][0]["source"] == "learned"


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


def test_reanchor_remaining_eta_anchored_to_now_across_a_pause(tmp_path):
    """RP-036/ACC-2: room A finished on schedule, then the job sat paused for
    10 real minutes before this reanchor call. job_eta_at must land in the
    future relative to "now" (reanchor_at), not silently slide into the past
    by staying anchored to job_start_dt + the naive total."""
    from custom_components.eufy_vacuum.timestamp_utils import parse_timestamp
    estimator = LearningEstimator(_make_hass(tmp_path))
    original = {
        "room_timeline": [
            {"room_id": 1, "slug": "a", "minutes": 5.0, "battery": 1.0,
             "estimated_transit_minutes_before": 0.0,
             "completed": False, "current": False, "remaining": True},
            {"room_id": 2, "slug": "b", "minutes": 5.0, "battery": 1.0,
             "estimated_transit_minutes_before": 0.0,
             "completed": False, "current": False, "remaining": True},
        ],
        "started_at": "2026-01-01T09:00:00+00:00",
        "overhead_minutes": 0.0,
        "vacuum_entity_id": "vacuum.alfred",
    }
    result = estimator.reanchor_timeline(
        original_estimate=original,
        completed_rooms=[{"room_id": 1, "actual_duration_minutes": 5.0}],
        reanchor_at="2026-01-01T09:15:00+00:00",
    )
    now_dt = parse_timestamp("2026-01-01T09:15:00+00:00")
    eta_dt = parse_timestamp(result["job_eta_at"])
    assert eta_dt > now_dt


def test_reanchor_remaining_room_readds_own_transit_leg(tmp_path):
    """RP-036/ACC-3: a remaining room's own transit-before leg is re-added
    to its ETA contribution, not dropped."""
    estimator = LearningEstimator(_make_hass(tmp_path))
    original = {
        "room_timeline": [
            {"room_id": 1, "slug": "a", "minutes": 5.0, "battery": 1.0,
             "estimated_transit_minutes_before": 0.0,
             "completed": False, "current": False, "remaining": True},
            {"room_id": 2, "slug": "b", "minutes": 5.0, "battery": 1.0,
             "estimated_transit_minutes_before": 2.0,
             "completed": False, "current": False, "remaining": True},
        ],
        "started_at": "2026-01-01T09:00:00+00:00",
        "overhead_minutes": 2.0,
        "vacuum_entity_id": "vacuum.alfred",
    }
    result = estimator.reanchor_timeline(
        original_estimate=original,
        completed_rooms=[{"room_id": 1, "actual_duration_minutes": 5.0}],
        reanchor_at="2026-01-01T09:00:00+00:00",
    )
    room_b = next(r for r in result["room_timeline"] if r["room_id"] == 2)
    assert room_b["eta_minutes_from_start"] == 12.0   # 5 actual + 2 transit + 5 minutes


def test_reanchor_skipped_room_resolves_all_completed(tmp_path):
    """RP-036/ACC-4: a skipped room is resolved, not perpetually remaining —
    all_completed can become True on a run with a skipped room."""
    estimator = LearningEstimator(_make_hass(tmp_path))
    original = {
        "room_timeline": [
            {"room_id": 1, "slug": "a", "minutes": 5.0, "battery": 1.0,
             "completed": False, "current": False, "remaining": True},
            {"room_id": 2, "slug": "b", "minutes": 5.0, "battery": 1.0,
             "completed": False, "current": False, "remaining": True},
        ],
        "started_at": "2026-01-01T09:00:00+00:00",
        "overhead_minutes": 0.0,
        "vacuum_entity_id": "vacuum.alfred",
    }
    result = estimator.reanchor_timeline(
        original_estimate=original,
        completed_rooms=[{"room_id": 1, "actual_duration_minutes": 5.0}],
        reanchor_at="2026-01-01T09:05:00+00:00",
        skipped_room_ids=[2],
    )
    room_b = next(r for r in result["room_timeline"] if r["room_id"] == 2)
    assert room_b["skipped"] is True
    assert room_b["remaining"] is False
    assert room_b["current"] is False
    assert result["rooms_skipped"] == 1
    assert result["all_completed"] is True


def test_reanchor_null_slug_rooms_do_not_collide(tmp_path):
    """RP-036/ACC-5: an explicit {"slug": None} must not fall through to the
    literal string "none" — two unrelated null-slug rooms must not both
    match a single completion event keyed on a None slug."""
    estimator = LearningEstimator(_make_hass(tmp_path))
    original = {
        "room_timeline": [
            {"room_id": -1, "slug": None, "minutes": 5.0, "battery": 1.0,
             "completed": False, "current": False, "remaining": True},
            {"room_id": -1, "slug": None, "minutes": 5.0, "battery": 1.0,
             "completed": False, "current": False, "remaining": True},
        ],
        "started_at": "2026-01-01T09:00:00+00:00",
        "overhead_minutes": 0.0,
        "vacuum_entity_id": "vacuum.alfred",
    }
    result = estimator.reanchor_timeline(
        original_estimate=original,
        completed_rooms=[{"slug": None, "actual_duration_minutes": 5.0}],
        reanchor_at="2026-01-01T09:05:00+00:00",
    )
    assert result["rooms_completed"] == 0


# ---------------------------------------------------------------------------
# RP-036/ACC-6 / ACC-7 — record_estimate_accuracy / _drift_ratio_for_room
# ---------------------------------------------------------------------------

def test_record_estimate_accuracy_prefers_exact_over_allocated(tmp_path):
    """RP-036/ACC-6: once at least one exact (single-room) sample exists for
    a room, the drift mean is computed from exact samples only — an
    allocated (multi-room split) sample must not dilute it."""
    from custom_components.eufy_vacuum.learning.utils import _room_key
    estimator = LearningEstimator(_make_hass(tmp_path))
    sink: dict = {}
    estimator.record_estimate_accuracy(
        vacuum_entity_id="vacuum.alfred",
        room_actuals=[{
            "slug": "kitchen", "clean_mode": "vacuum", "clean_passes": 1,
            "is_carpet": False, "clean_intensity": "standard", "map_id": 1,
            "estimated_minutes": 10.0, "actual_minutes": 20.0,
            "single_room": False,
        }],
        stats_sink=sink,
    )
    estimator.record_estimate_accuracy(
        vacuum_entity_id="vacuum.alfred",
        room_actuals=[{
            "slug": "kitchen", "clean_mode": "vacuum", "clean_passes": 1,
            "is_carpet": False, "clean_intensity": "standard", "map_id": 1,
            "estimated_minutes": 10.0, "actual_minutes": 11.0,
            "single_room": True,
        }],
        stats_sink=sink,
    )
    room_key = _room_key(1, "kitchen", "vacuum", 1, False, "standard", False)
    assert sink["rooms"][room_key]["mean_abs_pct_error"] == pytest.approx(0.10)


def test_record_estimate_accuracy_falls_back_to_flat_mean_without_exact(tmp_path):
    """RP-036/ACC-6: with no exact sample yet, the mean stays the flat
    unweighted average over all (allocated) samples — unchanged behavior."""
    from custom_components.eufy_vacuum.learning.utils import _room_key
    estimator = LearningEstimator(_make_hass(tmp_path))
    sink: dict = {}
    estimator.record_estimate_accuracy(
        vacuum_entity_id="vacuum.alfred",
        room_actuals=[{
            "slug": "kitchen", "clean_mode": "vacuum", "clean_passes": 1,
            "is_carpet": False, "clean_intensity": "standard", "map_id": 1,
            "estimated_minutes": 10.0, "actual_minutes": 20.0,
            "single_room": False,
        }],
        stats_sink=sink,
    )
    room_key = _room_key(1, "kitchen", "vacuum", 1, False, "standard", False)
    assert sink["rooms"][room_key]["mean_abs_pct_error"] == pytest.approx(1.0)


def test_drift_ratio_for_room_tolerates_list_shaped_rooms(tmp_path):
    """RP-036/ACC-7: an older/external payload with "rooms" stored as a list
    (not a dict keyed by room_key) must not crash — mirrors manager.py's own
    isinstance-branch tolerance for the same shape."""
    from custom_components.eufy_vacuum.learning.utils import _room_key
    estimator = LearningEstimator(_make_hass(tmp_path))
    accuracy_stats = {"rooms": [{"slug": "kitchen", "mean_abs_pct_error": 0.5}]}
    room_key = _room_key(1, "kitchen", "vacuum", 1, False, "standard", False)
    drift = estimator._drift_ratio_for_room(
        accuracy_stats=accuracy_stats, room_key=room_key,
    )
    assert drift == 0.0


def test_record_estimate_accuracy_tolerates_list_shaped_rooms(tmp_path):
    """RP-036/ACC-7: record_estimate_accuracy's own read of an existing
    list-shaped "rooms" must normalize to a fresh dict rather than crashing
    on the by-key write below it."""
    estimator = LearningEstimator(_make_hass(tmp_path))
    sink: dict = {"rooms": [{"slug": "stale"}]}
    result = estimator.record_estimate_accuracy(
        vacuum_entity_id="vacuum.alfred",
        room_actuals=[{
            "slug": "kitchen", "clean_mode": "vacuum", "clean_passes": 1,
            "is_carpet": False, "clean_intensity": "standard", "map_id": 1,
            "estimated_minutes": 10.0, "actual_minutes": 11.0,
            "single_room": True,
        }],
        stats_sink=sink,
    )
    assert result["rooms_recorded"] == 1
    assert isinstance(sink["rooms"], dict)


# ---------------------------------------------------------------------------
# _lookup_transit_minutes — fallback chain
# ---------------------------------------------------------------------------

def test_lookup_transit_per_pair():
    """Tier 1: exact from->to edge -> learned_pairs."""
    transit_index = {(6, 1, 2): {"sample_count": 3, "transit_minutes_mean": 2.0}}
    minutes, source = _lookup_transit_minutes(
        transit_index=transit_index, ingress_index={}, global_inter_room_minutes=None,
        map_id=6, from_room_id=1, to_room_id=2, to_slug="bath")
    assert source == "learned_pairs"
    assert minutes == 2.0


def test_lookup_transit_ingress_fallback():
    """Tier 2: no edge but ingress for the room -> learned_room."""
    ingress_index = {(6, "bath"): {"sample_count": 2, "avg_minutes": 1.5}}
    minutes, source = _lookup_transit_minutes(
        transit_index={}, ingress_index=ingress_index, global_inter_room_minutes=None,
        map_id=6, from_room_id=9, to_room_id=2, to_slug="bath")
    assert source == "learned_room"
    assert minutes == 1.5


def test_lookup_transit_global_fallback():
    """Tier 3: no edge/ingress but a global -> learned_global."""
    minutes, source = _lookup_transit_minutes(
        transit_index={}, ingress_index={}, global_inter_room_minutes=0.9,
        map_id=6, from_room_id=1, to_room_id=2, to_slug="bath")
    assert source == "learned_global"
    assert minutes == 0.9


def test_lookup_transit_default_constant():
    """Tier 4: nothing learned -> the _TRANSITION_PER_ROOM constant."""
    minutes, source = _lookup_transit_minutes(
        transit_index={}, ingress_index={}, global_inter_room_minutes=None,
        map_id=6, from_room_id=1, to_room_id=2, to_slug="bath")
    assert source == "default"
    assert minutes == _TRANSITION_PER_ROOM


def test_lookup_transit_zero_sample_edge_skipped():
    """An edge with 0 samples is ignored -> falls through to default."""
    transit_index = {(6, 1, 2): {"sample_count": 0, "transit_minutes_mean": 5.0}}
    minutes, source = _lookup_transit_minutes(
        transit_index=transit_index, ingress_index={}, global_inter_room_minutes=None,
        map_id=6, from_room_id=1, to_room_id=2, to_slug="bath")
    assert source == "default"


# ---------------------------------------------------------------------------
# estimate() — transit folds into the timeline + overhead
# ---------------------------------------------------------------------------

def _two_rooms() -> list[dict]:
    return [
        {"slug": "kitchen", "clean_mode": "vacuum", "clean_passes": 1,
         "clean_intensity": "standard", "carpet": False, "name": "Kitchen", "room_id": 1},
        {"slug": "bath", "clean_mode": "vacuum", "clean_passes": 1,
         "clean_intensity": "standard", "carpet": False, "name": "Bath", "room_id": 2},
    ]


def test_estimate_folds_learned_transit(tmp_path, monkeypatch):
    """Per-pair transit folds into the timeline + overhead; transition_source is
    learned_pairs and Sum(per-room transit) == overhead.transition_minutes."""
    estimator = LearningEstimator(_make_hass(tmp_path))
    monkeypatch.setattr(estimator.store, "load_room_stats", lambda **kw: {
        "room_stats": [],
        "room_baselines": [],
        "access_graph_edges": [
            {"map_id": 1, "from_room_id": 1, "to_room_id": 2,
             "sample_count": 3, "transit_minutes_mean": 2.0},
        ],
        "rebuilt_at": "2026-01-01T00:00:00+00:00",
    })
    monkeypatch.setattr(estimator.store, "load_job_stats", lambda **kw: {})
    result = estimator.estimate(
        vacuum_entity_id="vacuum.alfred", map_id="1", ordered_rooms=_two_rooms())
    tl = result["room_timeline"]
    assert tl[0]["estimated_transit_minutes_before"] == 0.0   # entry leg in startup
    assert tl[1]["estimated_transit_minutes_before"] == 2.0   # learned kitchen->bath
    assert tl[1]["transit_source"] == "learned_pairs"
    assert result["overhead"]["transition_source"] == "learned_pairs"
    assert result["overhead"]["transition_minutes"] == 2.0
    total = sum(r["estimated_transit_minutes_before"] for r in tl)
    assert total == result["overhead"]["transition_minutes"]


def test_estimate_default_transit_backward_compat(tmp_path, monkeypatch):
    """No learned transit -> constant per boundary, transition_source=default."""
    estimator = LearningEstimator(_make_hass(tmp_path))
    monkeypatch.setattr(estimator.store, "load_room_stats", lambda **kw: None)
    monkeypatch.setattr(estimator.store, "load_job_stats", lambda **kw: None)
    result = estimator.estimate(
        vacuum_entity_id="vacuum.alfred", map_id="1", ordered_rooms=_two_rooms())
    assert result["overhead"]["transition_source"] == "default"
    assert result["overhead"]["transition_minutes"] == _TRANSITION_PER_ROOM  # 1 boundary
    assert result["room_timeline"][0]["estimated_transit_minutes_before"] == 0.0


def test_estimate_single_room_no_transit(tmp_path, monkeypatch):
    """Single-room job -> no boundaries, transition_source=default, transit=0."""
    estimator = LearningEstimator(_make_hass(tmp_path))
    monkeypatch.setattr(estimator.store, "load_room_stats", lambda **kw: None)
    monkeypatch.setattr(estimator.store, "load_job_stats", lambda **kw: None)
    rooms = [{"slug": "kitchen", "clean_mode": "vacuum", "clean_passes": 1,
              "clean_intensity": "standard", "carpet": False, "name": "Kitchen", "room_id": 1}]
    result = estimator.estimate(
        vacuum_entity_id="vacuum.alfred", map_id="1", ordered_rooms=rooms)
    assert result["overhead"]["transition_minutes"] == 0.0
    assert result["overhead"]["transition_source"] == "default"


def test_estimate_surfaces_area_and_uses_timing_sample_count(tmp_path, monkeypatch):
    """A learned match's avg_area_m2 surfaces as estimated_area_m2, and the gated
    timing_sample_count (not the raw sample_count) drives confidence/velocity —
    since avg_minutes is computed from the area-gated samples (Wave 3)."""
    from custom_components.eufy_vacuum.learning import estimator as _est
    estimator = _est.LearningEstimator(_make_hass(tmp_path))
    monkeypatch.setattr(_est, "_find_room_match", lambda **kw: (
        {"avg_minutes": 8.0, "avg_battery_used": 2.0, "sample_count": 10,
         "timing_sample_count": 6, "minutes_stddev": 0.5, "avg_area_m2": 6.0}, False))
    rooms = [{"slug": "kitchen", "clean_mode": "vacuum", "clean_passes": 1,
              "clean_intensity": "standard", "carpet": False, "name": "Kitchen", "room_id": 1}]
    result = estimator.estimate(
        vacuum_entity_id="vacuum.alfred", map_id="1", ordered_rooms=rooms)
    entry = result["room_timeline"][0]
    assert entry["source"] == "learned"
    assert entry["estimated_area_m2"] == 6.0
    assert entry["sample_count"] == 6   # timing_sample_count, not the raw 10


def test_estimate_clamps_to_own_historical_band(tmp_path, monkeypatch):
    """RP-036/EST-4: a matched room's avg_minutes outside its own
    minutes_min/minutes_max band gets clamped to the nearest edge, and
    confidence is capped — never shows a number the room's own history
    didn't actually produce."""
    from custom_components.eufy_vacuum.learning import estimator as _est
    estimator = _est.LearningEstimator(_make_hass(tmp_path))
    monkeypatch.setattr(_est, "_find_room_match", lambda **kw: (
        {"avg_minutes": 50.0, "minutes_min": 5.0, "minutes_max": 10.0,
         "avg_battery_used": 2.0, "sample_count": 5, "timing_sample_count": 5,
         "minutes_stddev": 1.0, "avg_area_m2": 5.0}, False))
    rooms = [{"slug": "kitchen", "clean_mode": "vacuum", "clean_passes": 1,
              "clean_intensity": "standard", "carpet": False, "name": "Kitchen", "room_id": 1}]
    result = estimator.estimate(
        vacuum_entity_id="vacuum.alfred", map_id="1", ordered_rooms=rooms)
    entry = result["room_timeline"][0]
    assert entry["minutes"] == 10.0
    assert entry["band_capped"] is True
    assert entry["confidence_score"] <= 0.79


def test_estimate_within_band_not_capped(tmp_path, monkeypatch):
    """RP-036/EST-4: a room whose avg_minutes is within its own band is left
    untouched — band_capped only fires on an actual out-of-band mean."""
    from custom_components.eufy_vacuum.learning import estimator as _est
    estimator = _est.LearningEstimator(_make_hass(tmp_path))
    monkeypatch.setattr(_est, "_find_room_match", lambda **kw: (
        {"avg_minutes": 8.0, "minutes_min": 5.0, "minutes_max": 10.0,
         "avg_battery_used": 2.0, "sample_count": 5, "timing_sample_count": 5,
         "minutes_stddev": 1.0, "avg_area_m2": 5.0}, False))
    rooms = [{"slug": "kitchen", "clean_mode": "vacuum", "clean_passes": 1,
              "clean_intensity": "standard", "carpet": False, "name": "Kitchen", "room_id": 1}]
    result = estimator.estimate(
        vacuum_entity_id="vacuum.alfred", map_id="1", ordered_rooms=rooms)
    entry = result["room_timeline"][0]
    assert entry["minutes"] == 8.0
    assert entry["band_capped"] is False


def test_estimate_high_reachable_false_for_capped_variance(tmp_path, monkeypatch):
    """RP-036/EST-5: a learned match whose sample bonus is already saturated
    but whose variance alone caps confidence below HIGH must not promise
    runs_to_high — the estimate() call site actually wires the ceiling
    projection into learning_velocity."""
    from custom_components.eufy_vacuum.learning import estimator as _est
    estimator = _est.LearningEstimator(_make_hass(tmp_path))
    monkeypatch.setattr(_est, "_find_room_match", lambda **kw: (
        {"avg_minutes": 10.0, "minutes_min": 2.0, "minutes_max": 18.0,
         "avg_battery_used": 2.0, "sample_count": 10, "timing_sample_count": 10,
         "minutes_stddev": 5.0, "avg_area_m2": 5.0}, False))
    rooms = [{"slug": "kitchen", "clean_mode": "vacuum", "clean_passes": 1,
              "clean_intensity": "standard", "carpet": False, "name": "Kitchen", "room_id": 1}]
    result = estimator.estimate(
        vacuum_entity_id="vacuum.alfred", map_id="1", ordered_rooms=rooms)
    velocity = result["room_timeline"][0]["learning_velocity"]
    assert velocity["high_reachable"] is False
    assert velocity["runs_to_high"] is None


def test_estimate_default_room_velocity_ceiling_unaffected(tmp_path):
    """RP-036/EST-5: a "default" (no match at all) room has no variance data
    to judge reachability by — accumulating samples IS its real path to
    HIGH, so the ceiling gate must not apply to it (unaffected by this fix)."""
    estimator = LearningEstimator(_make_hass(tmp_path))
    rooms = [{"slug": "kitchen", "clean_mode": "vacuum", "clean_passes": 1,
              "clean_intensity": "standard", "carpet": False, "name": "Kitchen", "room_id": 1}]
    result = estimator.estimate(
        vacuum_entity_id="vacuum.alfred", map_id="1", ordered_rooms=rooms)
    velocity = result["room_timeline"][0]["learning_velocity"]
    assert velocity["high_reachable"] is True
    assert velocity["runs_to_high"] > 0


# ---------------------------------------------------------------------------
# Relaxed-setting scaling — clean_times is DOMINANT for room time (Chris, 2026-08-05)
#
# _find_room_match keeps clean_passes longest, but when it finally relaxes it
# returns another pass count's avg_minutes verbatim. A 2-pass room matched on
# 1-pass history estimated at roughly HALF its real time — which is the same
# number the live rollover threshold uses, so it also struck rooms out early.
# ---------------------------------------------------------------------------


def _baseline(slug, *, map_id=1, passes=None, edge=None):
    base = {"map_id": map_id, "room_slug": slug}
    if passes:
        base["by_clean_times"] = {
            key: {"sample_count": n, "avg_minutes": mins}
            for key, (n, mins) in passes.items()
        }
    if edge:
        base["by_edge_mopping"] = {
            key: {"sample_count": n, "avg_minutes": mins}
            for key, (n, mins) in edge.items()
        }
    return base


def test_bucket_ratio_needs_real_samples_on_both_sides():
    """An unmeasured ratio must be None, never a confident 1.0."""
    thin = {"1": {"sample_count": 1, "avg_minutes": 2.0}, "2": {"sample_count": 4, "avg_minutes": 4.0}}
    assert _bucket_ratio(thin, 2, 1) is None
    zero = {"1": {"sample_count": 4, "avg_minutes": 0.0}, "2": {"sample_count": 4, "avg_minutes": 4.0}}
    assert _bucket_ratio(zero, 2, 1) is None
    assert _bucket_ratio(None, 2, 1) is None
    assert _bucket_ratio({"1": {"sample_count": 4, "avg_minutes": 2.0}}, 2, 1) is None

    good = {"1": {"sample_count": 4, "avg_minutes": 2.0}, "2": {"sample_count": 3, "avg_minutes": 4.6}}
    assert _bucket_ratio(good, 2, 1) == pytest.approx(2.3)


def test_bucket_ratio_clamps_an_absurd_ratio():
    """A partial run or a stalled counter can produce a wild ratio; that is an artefact,
    not a setting effect."""
    wild = {"1": {"sample_count": 4, "avg_minutes": 0.1}, "2": {"sample_count": 4, "avg_minutes": 40.0}}
    assert _bucket_ratio(wild, 2, 1) == 4.0


def test_measured_ratio_prefers_the_rooms_own_history():
    """A setting's effect is partly a property of the room — a cluttered room loses more
    to a second pass than an open one — so its own measurement wins."""
    baselines = [
        _baseline("kitchen", passes={"1": (4, 2.0), "2": (4, 5.0)}),      # this room: 2.5x
        _baseline("office", passes={"1": (4, 2.0), "2": (4, 4.0)}),       # others: 2.0x
        _baseline("hall", passes={"1": (4, 3.0), "2": (4, 6.0)}),
    ]
    assert _measured_setting_ratio(baselines, "by_clean_times", 2, 1, 1, "kitchen") == 2.5
    # A room with no bucket of its own falls back to the MEDIAN across rooms that have
    # one — ratios here are 2.5 / 2.0 / 2.0, so the median is 2.0 and kitchen's outlier
    # does not drag it. That is the point of median over mean.
    assert _measured_setting_ratio(baselines, "by_clean_times", 2, 1, 1, "den") == 2.0


def test_measured_ratio_is_none_when_nothing_measured_it():
    assert _measured_setting_ratio([], "by_clean_times", 2, 1, 1, "kitchen") is None
    assert _measured_setting_ratio(
        [_baseline("kitchen")], "by_clean_times", 2, 1, 1, "kitchen") is None


def test_relaxed_scale_is_identity_when_settings_match():
    assert _relaxed_setting_scale(
        baselines=[], map_id=1, slug="kitchen",
        want_passes=2, got_passes=2, want_edge=True, got_edge=True) == 1.0


def test_relaxed_scale_uses_the_linear_prior_with_no_history():
    """THE CASE THAT BIT. Two passes requested, only single-pass history: the estimate was
    used verbatim, so a room that takes ~4 min estimated at ~2. A pass is another full
    sweep of the same floor, so N passes is about N times the work."""
    assert _relaxed_setting_scale(
        baselines=[], map_id=1, slug="kitchen",
        want_passes=2, got_passes=1, want_edge=False, got_edge=False) == 2.0
    # and the inverse direction, so a 1-pass request off 2-pass history is halved
    assert _relaxed_setting_scale(
        baselines=[], map_id=1, slug="kitchen",
        want_passes=1, got_passes=2, want_edge=False, got_edge=False) == 0.5


def test_measurement_beats_the_prior():
    """The prior is a placeholder for a number this house can actually measure."""
    baselines = [_baseline("kitchen", passes={"1": (4, 2.0), "2": (4, 4.6)})]
    assert _relaxed_setting_scale(
        baselines=baselines, map_id=1, slug="kitchen",
        want_passes=2, got_passes=1, want_edge=False, got_edge=False) == pytest.approx(2.3)


def test_edge_mopping_gets_no_prior():
    """A perimeter pass is ADDITIVE, not proportional, and nothing in the model says how
    long this room's perimeter takes — so unmeasured, it must leave the estimate alone."""
    assert _relaxed_setting_scale(
        baselines=[], map_id=1, slug="kitchen",
        want_passes=1, got_passes=1, want_edge=True, got_edge=False) == 1.0

    measured = [_baseline("kitchen", edge={"off": (4, 2.0), "on": (4, 2.6)})]
    assert _relaxed_setting_scale(
        baselines=measured, map_id=1, slug="kitchen",
        want_passes=1, got_passes=1, want_edge=True, got_edge=False) == pytest.approx(1.3)


def test_pass_and_edge_scales_compose():
    baselines = [_baseline("kitchen", edge={"off": (4, 2.0), "on": (4, 3.0)})]
    # 2x from the pass prior, 1.5x from the measured edge ratio
    assert _relaxed_setting_scale(
        baselines=baselines, map_id=1, slug="kitchen",
        want_passes=2, got_passes=1, want_edge=True, got_edge=False) == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# ISSUE #48 — the mop-wash projection must not depend on how mop is spelled
# ---------------------------------------------------------------------------

def _mop_rooms(spelling: str) -> list[dict]:
    return [
        {"slug": "kitchen", "clean_mode": spelling, "clean_passes": 1,
         "carpet": False, "name": "Kitchen", "room_id": 1},
        {"slug": "bath", "clean_mode": spelling, "clean_passes": 1,
         "carpet": False, "name": "Bath", "room_id": 2},
    ]


def test_mop_projection_identical_for_display_label_and_token(tmp_path):
    """[LE-48] The same all-mop job projects the same mop minutes either spelling.

    The accumulator asked `clean_mode in {"vacuum_mop", "mop"}` against a value
    lowercased but never canonicalized, so an all-mop job whose rooms are stored as
    "Vacuum and mop" accumulated NO projected mop minutes and reported a mop-wash
    overhead of 0.0 — the ETA short by the whole wash allowance.

    The file contradicted itself within six lines: the same variable goes straight
    into _find_room_match, whose predicate canonicalizes both sides, so the room
    matched its learned stats and got correct minutes while this said it was not a
    mop room at all.

    Differential rather than absolute: the projection depends on wash config and
    learned stats, and asserting a NUMBER here would pin those instead of the
    property under test. The non-vacuity guard below is what stops this passing
    because both sides are trivially zero.
    """
    estimator = LearningEstimator(_make_hass(tmp_path))
    common = {"vacuum_entity_id": "vacuum.alfred", "map_id": "1"}

    token = estimator.estimate(ordered_rooms=_mop_rooms("vacuum_mop"), **common)
    label = estimator.estimate(ordered_rooms=_mop_rooms("Vacuum and mop"), **common)
    vacuum = estimator.estimate(ordered_rooms=_mop_rooms("vacuum"), **common)

    token_mop = token["overhead"]["mop_wash"]["projected_mop_minutes"]
    label_mop = label["overhead"]["mop_wash"]["projected_mop_minutes"]
    vacuum_mop = vacuum["overhead"]["mop_wash"]["projected_mop_minutes"]

    # NON-VACUITY: a mop job must project SOME mop minutes, or the equality below
    # would hold at 0.0 == 0.0 and prove nothing.
    assert token_mop > 0, "the canonical spelling projected no mop minutes — test is vacuous"
    assert label_mop == token_mop, (
        f"display label projected {label_mop} vs {token_mop} for the token"
    )
    # And the opposite direction: a vacuum-only job must project none, so a fix that
    # simply treats everything as mop cannot pass.
    assert vacuum_mop == 0


# ---------------------------------------------------------------------------
# [LE-24]..[LE-29] _is_stats_stale -- four arms and a threshold, previously with
# ZERO tests of any kind. `grep -rn "_is_stats_stale\|_STALE_THRESHOLD_DAYS\|
# stats_stale" tests/` returned nothing before these.
#
# WHY IT MATTERS RATHER THAN JUST BEING UNCOVERED. This is the only thing that
# tells a user their learned data has gone old: the estimator's own module
# docstring says the "payload includes stats_stale=True so the card can warn the
# user", and `learning/manager.py` surfaces it in the dashboard snapshot. A gate
# that silently answered False would leave the warning permanently off; one that
# silently answered True would cry wolf on every fresh rebuild. Neither has a
# symptom anywhere else.
#
# AND IT WAS LIVE WHEN THESE WERE WRITTEN. Measured on the real box 2026-11-07:
# one vacuum's room_stats carried `rebuilt_at` 2026-10-11, i.e. 27 days -- three
# days short of the threshold, on an untested comparison.
#
# THE THRESHOLD IS FENCED IN BOTH DIRECTIONS, which is the point of LE-25/LE-26
# being a pair rather than one "it goes stale eventually" test. Raise
# _STALE_THRESHOLD_DAYS and LE-26 goes red; lower it and LE-25 does. A single
# test on either side pins nothing: the sweep that prompted this found nine
# thresholds whose tests held only one side, and this one had neither.
# ---------------------------------------------------------------------------


def _stats_rebuilt_days_ago(days: float) -> dict:
    """A room_stats payload whose rebuild stamp is `days` old.

    The stamp format is the one the REAL store writes -- `...Z`, as read off the
    live box -- not `datetime.isoformat()`'s `+00:00`. Both parse, and deriving the
    fixture from the producer rather than from what is convenient is the difference
    between testing the code and testing my memory of it.
    """
    stamp = (utc_now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"schema_version": 6, "rebuilt_at": stamp, "room_stats": []}


def test_is_stats_stale_fresh_rebuild_is_not_stale(tmp_path):
    """[LE-24] A rebuild from yesterday is not stale."""
    estimator = LearningEstimator(_make_hass(tmp_path))
    assert estimator._is_stats_stale(
        vacuum_entity_id="vacuum.alfred",
        room_stats_data=_stats_rebuilt_days_ago(1),
    ) is False


def test_is_stats_stale_at_the_threshold_is_not_yet_stale(tmp_path):
    """[LE-25] Exactly 30 days old is NOT stale -- the gate is `>`.

    THE 30 IS A LITERAL ON PURPOSE, and the first draft got this wrong. It read
    `_stats_rebuilt_days_ago(_STALE_THRESHOLD_DAYS)`, which moves the FIXTURE every
    time the constant moves -- so the test asserted only "the gate is `>` relative to
    whatever the constant happens to be" and could never notice the constant
    changing. Ablation proved it: raising the threshold to 31 and lowering it to 29
    both left the suite GREEN. That is the self-referential trap, the same shape as a
    unit test importing the table it is meant to be checking.

    A literal here is a FENCE, which is what a hardcoded shipped value in an
    ASSERTION is for: move _STALE_THRESHOLD_DAYS and this goes red, so the change has
    to be made deliberately. With [LE-26] it fences the number from both sides.

    `timedelta.days` truncates, so the few microseconds between building the stamp
    and the gate reading the clock cannot push 30 days over the line.
    """
    estimator = LearningEstimator(_make_hass(tmp_path))
    assert estimator._is_stats_stale(
        vacuum_entity_id="vacuum.alfred",
        room_stats_data=_stats_rebuilt_days_ago(30),
    ) is False


def test_is_stats_stale_one_day_past_the_threshold_is_stale(tmp_path):
    """[LE-26] 31 days old IS stale -- the upper half of the fence.

    Literal for the same reason as [LE-25]: derived from the constant it would move
    with it and pin nothing. Raise _STALE_THRESHOLD_DAYS and this is the test that
    fires.
    """
    estimator = LearningEstimator(_make_hass(tmp_path))
    assert estimator._is_stats_stale(
        vacuum_entity_id="vacuum.alfred",
        room_stats_data=_stats_rebuilt_days_ago(31),
    ) is True


def test_is_stats_stale_no_stats_at_all_is_stale(tmp_path):
    """[LE-27] Absent or empty stats are stale, not fresh.

    A new vacuum has nothing stored, and the honest answer is "you have no learned
    data", not "your learned data is current". `{}` and `None` take different
    branches -- the empty dict is caught by the falsy check, `None` triggers a store
    read -- so both are asserted rather than assumed equivalent.
    """
    estimator = LearningEstimator(_make_hass(tmp_path))
    assert estimator._is_stats_stale(
        vacuum_entity_id="vacuum.alfred", room_stats_data={}
    ) is True


def test_is_stats_stale_an_unreadable_stamp_is_stale(tmp_path):
    """[LE-28] A missing or unparseable `rebuilt_at` is stale.

    Fails SAFE, and that direction is the whole claim: a stamp nobody can read must
    not be treated as recent. Parametrised over the shapes `_parse_iso` returns None
    for, because "it handles a bad timestamp" is the kind of statement that holds for
    one shape and not the next.
    """
    estimator = LearningEstimator(_make_hass(tmp_path))
    for stamp in (None, "", "garbage", "not-a-date", "2026-13-45T99:99:99Z"):
        payload = {"schema_version": 6, "room_stats": []}
        if stamp is not None:
            payload["rebuilt_at"] = stamp
        assert estimator._is_stats_stale(
            vacuum_entity_id="vacuum.alfred", room_stats_data=payload
        ) is True, f"stamp {stamp!r} must read as stale"


def test_is_stats_stale_reads_the_store_only_when_not_handed_data(tmp_path):
    """[LE-29] Passing `room_stats_data` avoids the disk read; omitting it does one.

    The docstring makes this promise -- "Pass room_stats_data when it is already
    loaded to avoid a redundant disk read on the event loop" -- and nothing held it.
    A refactor that always loaded would be invisible: every other assertion here
    would still pass, because the loaded value and the passed value agree.

    Asserted in BOTH directions, because only the pair distinguishes "the parameter
    is honoured" from "the store happens to return the same thing".
    """
    estimator = LearningEstimator(_make_hass(tmp_path))
    fresh = _stats_rebuilt_days_ago(1)

    with patch.object(estimator.store, "load_room_stats") as loader:
        estimator._is_stats_stale(vacuum_entity_id="vacuum.alfred", room_stats_data=fresh)
        assert loader.call_count == 0, (
            "room_stats_data was supplied, so the store must not be read -- this "
            "function runs on the event loop"
        )

    with patch.object(estimator.store, "load_room_stats", return_value=fresh) as loader:
        assert estimator._is_stats_stale(vacuum_entity_id="vacuum.alfred") is False
        assert loader.call_count == 1
        assert loader.call_args.kwargs == {"vacuum_entity_id": "vacuum.alfred"}


# ---------------------------------------------------------------------------
# [LE-30] / [LE-31] the transit fallback chain, all four tiers at once.
#
# Doc 29 §5 and `_lookup_transit_minutes`' own docstring name four tiers, most
# specific first: learned_pairs (the exact from->to edge), learned_room (average
# transit INTO the room, from room_baselines), learned_global (job-level average per
# boundary) and default (the _TRANSITION_PER_ROOM constant). Tier 2 had never been
# built: every existing estimate() test passes `room_baselines: []`.
# ---------------------------------------------------------------------------

def _four_rooms() -> list[dict]:
    """kitchen -> bath -> hall -> den, so each boundary lands on a DIFFERENT tier."""
    return [
        {"slug": slug, "clean_mode": "vacuum", "clean_passes": 1,
         "clean_intensity": "standard", "carpet": False,
         "name": slug.title(), "room_id": rid}
        for rid, slug in ((1, "kitchen"), (2, "bath"), (3, "hall"), (4, "den"))
    ]


#: room_stats shaped as `stats_rebuilder` emits it. The ingress keys and their UNIT are
#: the producer's: `stats_rebuilder.py:842-846` spreads `_seconds_band(..., value_label=
#: "ingress_transit_seconds", count_key="ingress_sample_count")`, and `_seconds_band`
#: (:184-205) reduces SECONDS. 90.0 seconds is 1.5 minutes, which is the only reason
#: that number is not round -- it is the /60.0 at estimator.py:1044 being exercised for
#: the first time.
def _transit_room_stats() -> dict:
    return {
        "room_stats": [],
        "access_graph_edges": [
            None,                                     # a torn element, tolerated
            {"map_id": 1, "from_room_id": 1, "to_room_id": 2,
             "sample_count": 3, "transit_minutes_mean": 2.0},
        ],
        "room_baselines": [
            None,                                     # likewise
            {"map_id": 1, "room_slug": "hall",
             "ingress_sample_count": 4, "avg_ingress_transit_seconds": 90.0},
            {"map_id": 1, "room_slug": "den",         # measured, but not yet usably
             "ingress_sample_count": 0, "avg_ingress_transit_seconds": 600.0},
        ],
        "rebuilt_at": "2026-01-01T00:00:00+00:00",
    }


#: 2.4 minutes of inter-room overhead per job over an average of 3.0 rooms is 2 boundaries
#: a job, so the per-boundary global is 1.2. `avg_room_count` has to clear
#: `_MIN_BOUNDARIES_PER_JOB` (0.25) above 1.0 or the whole tier is refused.
_JOB_STATS = {
    "job_stats": {
        "avg_overhead_inter_room_minutes": 2.4,
        "overhead_inter_room_sample_count": 5,
        "avg_room_count": 3.0,
    }
}


def test_le30_all_four_transit_tiers_in_one_job(tmp_path, monkeypatch):
    """[LE-30] One job whose three boundaries resolve on three different tiers.

    THE FOUR NUMBERS ARE DELIBERATELY DISTINCT AND THE WHOLE LIST IS ASSERTED. Every
    tier here returns a float, and the default tier returns 0.75, so a single-boundary
    fixture asserting "1.5" could coincide with a fallback and prove nothing. With
    0.0 / 2.0 / 1.5 / 1.2 in one call, no two tiers can be confused and the assertion
    is not invariant under swapping any pair of them -- which is what rules out both
    the equals-the-fallback and the symmetric-under-the-mutation traps.

    POSITION IS WHAT MAKES THE INGRESS TIER DEPEND ON THE INDEX rather than merely
    execute it: the bath->hall leg has NO access_graph edge, so the ingress index is
    the only thing that can produce 1.5 for it. Skip the index and that leg reads the
    global 1.2 instead -- a different number, not a missing one.

    1.5 IS THE UNIT CONVERSION, not a round number chosen for looks. The producer
    stores seconds (`stats_rebuilder.py:842-846`), the index divides by 60
    (`estimator.py:1044`), and nothing had ever run that divide: at /1.0 the leg reads
    90.0 and this goes red.

    The two `None` elements are the tolerant-reader guards on both indices, reached
    because the learned stores are derived JSON on disk that doc 28 calls disposable
    precisely because a reader may meet a torn one. They come FIRST in each list, so a
    `break` in place of either `continue` loses the real entry behind it.

    THE ZERO-SAMPLE `den` BASELINE IS EXECUTED BUT NOT DEPENDED ON, and this test does
    not claim otherwise: the `ing_count <= 0` skip at estimator.py:1035 cannot be
    observed from here, because `_lookup_transit_minutes` independently requires
    `sample_count >= 1` (:536) and would reject the entry anyway. It is here to be the
    realistic shape of a room whose transits have not yet been captured, and its 600.0
    seconds would read as 10.0 minutes if BOTH guards were lost.

    `learned_mixed` falls out of the same input and is asserted because it is the
    job-level provenance a reader uses to judge the transition minutes: three distinct
    learned tiers in one job must not be reported as any single one of them.
    """
    estimator = LearningEstimator(_make_hass(tmp_path))
    monkeypatch.setattr(estimator.store, "load_room_stats", lambda **kw: _transit_room_stats())
    monkeypatch.setattr(estimator.store, "load_job_stats", lambda **kw: _JOB_STATS)

    result = estimator.estimate(
        vacuum_entity_id="vacuum.alfred", map_id="1", ordered_rooms=_four_rooms()
    )
    tl = result["room_timeline"]

    assert [r["transit_source"] for r in tl] == [
        "none", "learned_pairs", "learned_room", "learned_global"
    ]
    assert [r["estimated_transit_minutes_before"] for r in tl] == [0.0, 2.0, 1.5, 1.2]

    assert result["overhead"]["transition_source"] == "learned_mixed"
    assert result["overhead"]["transition_minutes"] == 4.7
    assert sum(r["estimated_transit_minutes_before"] for r in tl) == (
        result["overhead"]["transition_minutes"]
    )


def test_le31_a_failing_job_stats_read_costs_only_the_global_tier(tmp_path, monkeypatch):
    """[LE-31] `estimate()` runs on the event loop; `load_job_stats` touches disk.

    On this install that disk is an SMB share, so a read that raises is not exotic. The
    `except Exception` around it exists so the estimate DEGRADES -- the global tier is
    lost and the leg falls to the constant -- rather than the whole estimate failing.

    THE ASSERTION IS SCOPED, which is the whole claim: the den leg drops from 1.2 to
    the 0.75 constant, and the two legs that came from `room_stats` are UNCHANGED at
    2.0 and 1.5. "It did not raise" would be satisfied by an estimate that lost
    everything; naming the surviving legs is what separates degraded from broken.

    It is the asymmetric twin of [LE-30]: identical room_stats, identical rooms, one
    monkeypatch different. Narrowing the `except` to anything but Exception lets the
    RuntimeError escape and this errors out at teardown rather than failing -- which is
    why the harness counts ERROR as red too.
    """
    def _boom(**kwargs):
        raise RuntimeError("the learning share went away mid-estimate")

    estimator = LearningEstimator(_make_hass(tmp_path))
    monkeypatch.setattr(estimator.store, "load_room_stats", lambda **kw: _transit_room_stats())
    monkeypatch.setattr(estimator.store, "load_job_stats", _boom)

    tl = estimator.estimate(
        vacuum_entity_id="vacuum.alfred", map_id="1", ordered_rooms=_four_rooms()
    )["room_timeline"]

    assert [r["transit_source"] for r in tl] == [
        "none", "learned_pairs", "learned_room", "default"
    ]
    assert [r["estimated_transit_minutes_before"] for r in tl] == [
        0.0, 2.0, 1.5, _TRANSITION_PER_ROOM
    ]


# ---------------------------------------------------------------------------
# [LE-32] / [LE-33] the relaxation ladder below pass 2.
#
# Passes 1 and 2 are held by [LE-15]/[LE-16] and the tiebreak test. Passes 3, 4 and 5
# had never returned a match, so three fifths of the documented ladder was asserted by
# absence -- and the ORDER, which doc 29 §1 says is an effect-size ranking rather than
# an arbitrary sequence, was not asserted at all.
# ---------------------------------------------------------------------------

_QUERY = {
    "map_id": 1, "slug": "kitchen", "clean_mode": "vacuum",
    "clean_passes": 2, "is_carpet": True, "clean_intensity": "standard",
    "edge_mopping": True,
}

#: One stored entry per pass, each differing from the query on EXACTLY the dimension
#: that pass drops -- so each is unmatchable by every earlier pass.
_LADDER_ROWS = [
    ("pass3_ignores_carpet",
     {"clean_times": 2, "edge_mopping": True, "is_carpet": False}, 30.0),
    ("pass4_ignores_edge",
     {"clean_times": 2, "edge_mopping": False, "is_carpet": True}, 40.0),
    ("pass5_ignores_passes",
     {"clean_times": 1, "edge_mopping": True, "is_carpet": True}, 50.0),
]


@pytest.mark.parametrize(
    ("shelf", "winner", "rung"),
    [
        ((2, 1, 0), 30.0, "pass 3 (ignore carpet)"),
        ((2, 1), 40.0, "pass 4 (ignore edge_mopping)"),
        ((2,), 50.0, "pass 5 (ignore clean_passes)"),
    ],
    ids=["pass3_wins", "pass4_wins", "pass5_wins"],
)
def test_le32_each_relaxation_pass_wins_against_the_rungs_below_it(shelf, winner, rung):
    """[LE-32] Passes 3, 4 and 5, pinned by contest because nothing else can pin them.

    THE FIRST DRAFT OF THIS TEST WAS DEAD AND THE ABLATION SAID SO. It offered ONE
    crafted entry per pass and asserted the entry came back. `_find_room_match` returns
    `(match, mismatch)` and no rung indicator, so breaking pass 3 did not redden it --
    the same entry simply fell through to pass 4, which returned it with an identical
    `avg_minutes` and an identical `mismatch=True`. Only the pass-5 row reddened,
    because pass 5 has no rung beneath it to catch the fall. A fixture that one rung
    matches is found by whichever rung now carries that filter; it cannot say which.

    A CONTEST CAN. Each row offers a shelf of candidates and names the winner: with all
    three present pass 3 must win, with pass 3 withdrawn pass 4 must, and alone pass 5
    must. Each expected value is WRONG for the other two rows, so no permutation of the
    ladder satisfies all three -- which is what makes this an assertion about ORDER and
    not merely about membership. Doc 29 §1 says the order is an effect-size ranking and
    that "reordering this would silently make relaxed estimates worse without changing
    any threshold"; this is the test that would notice.

    SAMPLE COUNT IS HELD EQUAL ACROSS THE CANDIDATES on purpose. The relaxed passes
    break ties with `_best_by_sample_count`, so a shelf whose preferred entry also had
    the most samples could not distinguish "took the earlier pass" from "took the
    better-evidenced entry" -- the tiebreak would carry the test and the order would go
    unasserted.

    The shelf is handed over in REVERSE rung order (pass 5 first) so that a ladder
    which iterated the shelf rather than the rungs would answer 50.0 and go red.
    """
    candidates = [
        _make_stat(sample_count=5, avg_minutes=m, **o) for _, o, m in _LADDER_ROWS
    ]
    offered = [candidates[i] for i in shelf]

    match, mismatch = _find_room_match(room_stats=offered, **_QUERY)

    assert match is not None, "the ladder reached no rung at all"
    assert match["avg_minutes"] == winner, "%s should have won" % rung
    assert mismatch is True, "every pass below the first is a relaxed match"
