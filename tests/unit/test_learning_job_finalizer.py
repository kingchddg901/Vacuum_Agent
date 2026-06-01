"""Unit tests for learning/job_finalizer.py — pure-function helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.learning.job_finalizer import (
    LearningJobFinalizer,
    _apply_water_actuals,
    _compute_total_error_seconds,
    _parse_iso_to_utc,
)


@pytest.fixture
def finalizer(tmp_path):
    hass = MagicMock()
    hass.config.config_dir = str(tmp_path)
    return LearningJobFinalizer(hass)


# ---------------------------------------------------------------------------
# _parse_iso_to_utc
# ---------------------------------------------------------------------------

def test_parse_iso_utc_zulu():
    dt = _parse_iso_to_utc("2026-01-01T10:00:00Z")
    assert dt is not None
    assert dt.year == 2026
    assert dt.tzinfo is not None


def test_parse_iso_utc_offset():
    dt = _parse_iso_to_utc("2026-01-01T10:00:00+00:00")
    assert dt is not None
    assert dt.minute == 0


def test_parse_iso_utc_none_returns_none():
    assert _parse_iso_to_utc(None) is None


def test_parse_iso_utc_empty_string_returns_none():
    assert _parse_iso_to_utc("") is None


def test_parse_iso_utc_non_string_returns_none():
    assert _parse_iso_to_utc(12345) is None


def test_parse_iso_utc_garbage_returns_none():
    assert _parse_iso_to_utc("not-a-date") is None


# ---------------------------------------------------------------------------
# _compute_total_error_seconds
# ---------------------------------------------------------------------------

def test_error_seconds_no_latch():
    assert _compute_total_error_seconds(None, job_ended_at=None) == 0


def test_error_seconds_empty_errors():
    latch = {"errors": []}
    assert _compute_total_error_seconds(latch, job_ended_at=None) == 0


def test_error_seconds_single_resolved_interval():
    latch = {
        "errors": [
            {
                "captured_at": "2026-01-01T10:00:00Z",
                "recovered_at": "2026-01-01T10:00:30Z",
            }
        ]
    }
    result = _compute_total_error_seconds(latch, job_ended_at="2026-01-01T10:05:00Z")
    assert result == 30


def test_error_seconds_unresolved_bounded_by_job_end():
    latch = {
        "errors": [
            {"captured_at": "2026-01-01T10:00:00Z"}  # no recovered_at
        ]
    }
    result = _compute_total_error_seconds(latch, job_ended_at="2026-01-01T10:01:00Z")
    assert result == 60


def test_error_seconds_unresolved_bounded_by_next_entry():
    latch = {
        "errors": [
            {"captured_at": "2026-01-01T10:00:00Z"},             # no recovered_at
            {"captured_at": "2026-01-01T10:00:20Z", "recovered_at": "2026-01-01T10:00:40Z"},
        ]
    }
    # First entry ends at second entry's captured_at (T+20s), second entry is 20s
    result = _compute_total_error_seconds(latch, job_ended_at="2026-01-01T10:05:00Z")
    assert result == 40  # 20 + 20


def test_error_seconds_two_separate_intervals():
    latch = {
        "errors": [
            {"captured_at": "2026-01-01T10:00:00Z", "recovered_at": "2026-01-01T10:00:10Z"},
            {"captured_at": "2026-01-01T10:01:00Z", "recovered_at": "2026-01-01T10:01:20Z"},
        ]
    }
    result = _compute_total_error_seconds(latch, job_ended_at="2026-01-01T10:05:00Z")
    assert result == 30  # 10 + 20


def test_error_seconds_merges_overlapping_intervals():
    latch = {
        "errors": [
            {"captured_at": "2026-01-01T10:00:00Z", "recovered_at": "2026-01-01T10:00:30Z"},
            {"captured_at": "2026-01-01T10:00:20Z", "recovered_at": "2026-01-01T10:00:40Z"},
        ]
    }
    # Merged: 00:00 → 00:40 = 40s
    result = _compute_total_error_seconds(latch, job_ended_at="2026-01-01T10:05:00Z")
    assert result == 40


def test_error_seconds_zero_duration_interval_skipped():
    """end <= start intervals are dropped."""
    latch = {
        "errors": [
            {"captured_at": "2026-01-01T10:00:00Z", "recovered_at": "2026-01-01T10:00:00Z"},
        ]
    }
    assert _compute_total_error_seconds(latch, job_ended_at="2026-01-01T10:05:00Z") == 0


def test_error_seconds_non_dict_latch():
    assert _compute_total_error_seconds("not_a_dict", job_ended_at=None) == 0


def test_error_seconds_malformed_entry_skipped():
    latch = {
        "errors": [
            "not a dict",
            {"captured_at": "2026-01-01T10:00:00Z", "recovered_at": "2026-01-01T10:00:05Z"},
        ]
    }
    result = _compute_total_error_seconds(latch, job_ended_at="2026-01-01T10:05:00Z")
    assert result == 5


# ---------------------------------------------------------------------------
# _apply_water_actuals
# ---------------------------------------------------------------------------

def _job_with_water(**overrides) -> dict:
    water = {
        "station_clean_water_percent": 80.0,
        "actual_end_station_clean_water_percent": None,
        "dock_clean_tank_capacity_ml": 3000,
        "dock_wash_overhead_ml_per_cycle": 50.0,
        "wash_cycle_count": 2,
        "estimated_total_dock_clean_water_used_ml": 450.0,
    }
    water.update(overrides)
    return {"water": water}


def test_apply_water_actuals_computes_total():
    job = _job_with_water()
    # start=80%, end=65%, capacity=3000ml → used = (80-65)/100 * 3000 = 450ml
    _apply_water_actuals(completed_job=job, end_percent=65.0, observed_mop_wash_count=2)
    water = job["water"]
    assert water["actual_dock_water_used_ml"] == pytest.approx(450.0)
    assert water["actual_end_station_clean_water_percent"] == 65.0
    assert water["actual_mop_wash_count"] == 2


def test_apply_water_actuals_splits_wash_overhead():
    job = _job_with_water()
    # 2 washes * 50ml/wash = 100ml overhead → floor = 450 - 100 = 350ml
    _apply_water_actuals(completed_job=job, end_percent=65.0, observed_mop_wash_count=2)
    water = job["water"]
    assert water["actual_mop_wash_water_ml"] == pytest.approx(100.0)
    assert water["actual_floor_water_ml"] == pytest.approx(350.0)


def test_apply_water_actuals_none_end_percent_nulls_fields():
    job = _job_with_water()
    _apply_water_actuals(completed_job=job, end_percent=None, observed_mop_wash_count=0)
    water = job["water"]
    assert water["actual_dock_water_used_ml"] is None
    assert water["actual_floor_water_ml"] is None


def test_apply_water_actuals_unexpected_wash_cycles():
    job = _job_with_water()
    # wash_cycle_count=2 in water, but observed=3 → unexpected
    _apply_water_actuals(completed_job=job, end_percent=65.0, observed_mop_wash_count=3)
    assert job["water"]["unexpected_wash_cycles"] is True


def test_apply_water_actuals_expected_wash_cycles():
    job = _job_with_water()
    _apply_water_actuals(completed_job=job, end_percent=65.0, observed_mop_wash_count=2)
    assert job["water"]["unexpected_wash_cycles"] is False


def test_apply_water_actuals_no_water_section_noop():
    """No water key → function returns without error."""
    job = {"outcome": {"status": "completed"}}
    _apply_water_actuals(completed_job=job, end_percent=60.0, observed_mop_wash_count=0)
    # No water key added
    assert "water" not in job


def test_apply_water_actuals_delta_computed():
    """actual_vs_estimated_delta_ml = actual_total - estimated."""
    job = _job_with_water()  # estimated = 450ml
    _apply_water_actuals(completed_job=job, end_percent=65.0, observed_mop_wash_count=2)
    # actual=450ml, estimated=450ml → delta=0
    assert job["water"]["actual_vs_estimated_delta_ml"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# _apply_snapshot_estimates_to_completed_job — start-of-run estimate enrichment
# ---------------------------------------------------------------------------

def test_apply_snapshot_estimates_matches_by_id_and_slug(finalizer):
    """[JF-1] resolved rooms gain estimate fields from the snapshot timeline,
    matched first by room_id then by slug; unmatched rooms pass through."""
    snapshot = {"planned_job_estimate": {"room_timeline": [
        {"room_id": 1, "minutes": 5.0, "battery": 8.0,
         "confidence_score": 0.9, "confidence_label": "high", "source": "learned"},
        {"slug": "bath", "minutes": 3.0, "battery": 4.0},
    ]}}
    completed_job = {"resolved_rooms": [
        {"room_id": 1, "name": "Kitchen"},          # matches by id
        {"room_id": 7, "slug": "bath"},             # id miss → slug match
        {"room_id": 9, "name": "Hall"},             # no match → passthrough
    ]}
    finalizer._apply_snapshot_estimates_to_completed_job(
        completed_job=completed_job, snapshot=snapshot)
    rooms = {r.get("room_id"): r for r in completed_job["resolved_rooms"]}
    assert rooms[1]["estimated_minutes"] == 5.0
    assert rooms[1]["estimate_confidence_label"] == "high"
    assert rooms[7]["estimated_minutes"] == 3.0
    assert "estimated_minutes" not in rooms[9]


def test_apply_snapshot_estimates_guards(finalizer):
    """[JF-2] missing/empty snapshot or timeline → completed_job untouched."""
    job = {"resolved_rooms": [{"room_id": 1}]}
    finalizer._apply_snapshot_estimates_to_completed_job(completed_job=job, snapshot=None)
    finalizer._apply_snapshot_estimates_to_completed_job(
        completed_job=job, snapshot={"planned_job_estimate": {"room_timeline": []}})
    assert "estimated_minutes" not in job["resolved_rooms"][0]


# ---------------------------------------------------------------------------
# _detect_cancel_likely_run — learning-estimate path (1195-1218)
# ---------------------------------------------------------------------------

_VAC = "vacuum.alfred"


def _cancel_state(returning_offset_min, paused_secs=0.0):
    start = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    ret = start + timedelta(minutes=returning_offset_min)
    return {
        "resolved_rooms": [{"room_id": 1, "name": "Kitchen"}],
        "paused_duration_seconds": paused_secs,
        "state_transitions": [
            {"entity_id": "sensor.alfred_task_status",
             "from_state": "cleaning", "to_state": "returning",
             "changed_at": ret.isoformat()},
        ],
    }, start.isoformat(), ret.isoformat()


def test_detect_cancel_short_run_is_likely(finalizer):
    """[JF-3] past the floor (2 min cleaned), a run far under the learned estimate
    is flagged early_return_likely_cancelled."""
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"task_status": "sensor.alfred_task_status"},
    })
    state, started, ended = _cancel_state(returning_offset_min=2)
    learning = MagicMock()
    learning.estimate_from_manager.return_value = {"room_timeline": [{"minutes": 10.0}]}
    manager = MagicMock()
    manager._get_learning_manager.return_value = learning

    out = finalizer._detect_cancel_likely_run(
        manager=manager, vacuum_entity_id=_VAC, map_id="6",
        battery_start=90, started_at=started, ended_at=ended,
        active_job_state=state)
    # 2 min actual >= 1.5 floor, but << 10 min estimate (short_threshold 4.0)
    assert out["cancel_likely"] is True
    assert out["reason"] == "early_return_likely_cancelled"


def test_detect_cancel_estimate_error_then_long_enough(finalizer):
    """[JF-4] when the learning estimate raises, expected falls to 0 → a 1.0 min
    floor; a 2-min run clears it → duration_not_short (not a cancel)."""
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"task_status": "sensor.alfred_task_status"},
    })
    state, started, ended = _cancel_state(returning_offset_min=2)
    learning = MagicMock()
    learning.estimate_from_manager.side_effect = RuntimeError("boom")
    manager = MagicMock()
    manager._get_learning_manager.return_value = learning

    out = finalizer._detect_cancel_likely_run(
        manager=manager, vacuum_entity_id=_VAC, map_id="6",
        battery_start=90, started_at=started, ended_at=ended,
        active_job_state=state)
    assert out["cancel_likely"] is False
    assert out["reason"] == "duration_not_short"
