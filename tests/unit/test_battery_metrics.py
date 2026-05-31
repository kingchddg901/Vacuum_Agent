"""Unit tests for battery/job_metrics — pure Python, no HA dependency."""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.battery.job_metrics import (
    _binary_share,
    _bucket_key,
    _bucketed_share,
    _positive_float,
    _prorate_weights,
    _safe_drain,
    compute_job_battery_metrics,
)


# ---------------------------------------------------------------------------
# _safe_drain
# ---------------------------------------------------------------------------

def test_safe_drain_normal():
    assert _safe_drain(80, 68) == 12


def test_safe_drain_full_discharge():
    assert _safe_drain(100, 0) == 100


def test_safe_drain_no_drain():
    assert _safe_drain(50, 50) == 0


def test_safe_drain_negative_returns_none():
    """End > start means battery charged mid-job — not a valid drain reading."""
    assert _safe_drain(50, 80) is None


def test_safe_drain_none_start():
    assert _safe_drain(None, 50) is None


def test_safe_drain_none_end():
    assert _safe_drain(80, None) is None


def test_safe_drain_string_integers():
    assert _safe_drain("80", "68") == 12


def test_safe_drain_non_numeric():
    assert _safe_drain("high", 50) is None


# ---------------------------------------------------------------------------
# _positive_float
# ---------------------------------------------------------------------------

def test_positive_float_normal():
    assert _positive_float(3.5) == pytest.approx(3.5)


def test_positive_float_zero_returns_none():
    assert _positive_float(0) is None
    assert _positive_float(0.0) is None


def test_positive_float_negative_returns_none():
    assert _positive_float(-1.0) is None


def test_positive_float_none_returns_none():
    assert _positive_float(None) is None


def test_positive_float_string():
    assert _positive_float("5.5") == pytest.approx(5.5)


def test_positive_float_non_numeric_string():
    assert _positive_float("abc") is None


# ---------------------------------------------------------------------------
# _bucket_key
# ---------------------------------------------------------------------------

def test_bucket_key_none_is_unknown():
    assert _bucket_key(None) == "unknown"


def test_bucket_key_empty_string_is_unknown():
    assert _bucket_key("") == "unknown"
    assert _bucket_key("   ") == "unknown"


def test_bucket_key_lowercases():
    assert _bucket_key("Vacuum") == "vacuum"
    assert _bucket_key("VACUUM_MOP") == "vacuum_mop"


def test_bucket_key_passes_through_already_lower():
    assert _bucket_key("standard") == "standard"


# ---------------------------------------------------------------------------
# _prorate_weights
# ---------------------------------------------------------------------------

def test_prorate_weights_empty_rooms():
    weights, label = _prorate_weights([])
    assert weights == []
    assert label == "none"


def test_prorate_weights_equal_when_no_estimates():
    rooms = [{}, {}, {}]
    weights, label = _prorate_weights(rooms)
    assert label == "room_count"
    assert len(weights) == 3
    assert sum(weights) == pytest.approx(1.0)
    assert weights[0] == pytest.approx(1 / 3)


def test_prorate_weights_by_estimated_minutes():
    rooms = [
        {"estimated_minutes": 20.0},
        {"estimated_minutes": 30.0},
        {"estimated_minutes": 50.0},
    ]
    weights, label = _prorate_weights(rooms)
    assert label == "estimated_minutes"
    assert len(weights) == 3
    assert sum(weights) == pytest.approx(1.0)
    assert weights[0] == pytest.approx(0.2)
    assert weights[1] == pytest.approx(0.3)
    assert weights[2] == pytest.approx(0.5)


def test_prorate_weights_partial_estimates_still_proportional():
    """A room with zero estimate contributes 0 weight when others have estimates."""
    rooms = [{"estimated_minutes": 10}, {"estimated_minutes": 0}]
    weights, label = _prorate_weights(rooms)
    assert label == "estimated_minutes"
    assert weights[0] == pytest.approx(1.0)
    assert weights[1] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# _binary_share
# ---------------------------------------------------------------------------

def test_binary_share_all_off():
    rooms = [{"edge_mopping": False}, {"edge_mopping": False}]
    weights = [0.5, 0.5]
    result = _binary_share(rooms, weights, key="edge_mopping")
    assert result["on_share"] == pytest.approx(0.0)
    assert result["off_share"] == pytest.approx(1.0)


def test_binary_share_all_on():
    rooms = [{"edge_mopping": True}, {"edge_mopping": True}]
    weights = [0.5, 0.5]
    result = _binary_share(rooms, weights, key="edge_mopping")
    assert result["on_share"] == pytest.approx(1.0)
    assert result["off_share"] == pytest.approx(0.0)


def test_binary_share_mixed():
    rooms = [{"edge_mopping": True}, {"edge_mopping": False}]
    weights = [0.4, 0.6]
    result = _binary_share(rooms, weights, key="edge_mopping")
    assert result["on_share"] == pytest.approx(0.4)
    assert result["off_share"] == pytest.approx(0.6)


def test_binary_share_sums_to_one():
    rooms = [{"edge_mopping": True}, {"edge_mopping": False}, {"edge_mopping": True}]
    weights = [0.2, 0.3, 0.5]
    result = _binary_share(rooms, weights, key="edge_mopping")
    assert result["on_share"] + result["off_share"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# _bucketed_share
# ---------------------------------------------------------------------------

def test_bucketed_share_empty_rooms():
    result = _bucketed_share([], [], area_m2=50.0, key="clean_mode")
    assert result == {}


def test_bucketed_share_single_bucket():
    rooms = [{"clean_mode": "vacuum"}, {"clean_mode": "vacuum"}]
    weights = [0.5, 0.5]
    result = _bucketed_share(rooms, weights, area_m2=40.0, key="clean_mode")
    assert len(result) == 1
    assert "vacuum" in result
    assert result["vacuum"]["share"] == pytest.approx(1.0)
    assert result["vacuum"]["rooms"] == 2
    assert result["vacuum"]["area_m2"] == pytest.approx(40.0)


def test_bucketed_share_two_buckets():
    rooms = [{"clean_mode": "vacuum"}, {"clean_mode": "vacuum_mop"}]
    weights = [0.6, 0.4]
    result = _bucketed_share(rooms, weights, area_m2=50.0, key="clean_mode")
    assert len(result) == 2
    assert result["vacuum"]["share"] == pytest.approx(0.6)
    assert result["vacuum_mop"]["share"] == pytest.approx(0.4)


def test_bucketed_share_none_value_becomes_unknown():
    rooms = [{"fan_speed": None}]
    weights = [1.0]
    result = _bucketed_share(rooms, weights, area_m2=None, key="fan_speed")
    assert "unknown" in result


# ---------------------------------------------------------------------------
# compute_job_battery_metrics — integration tests
# ---------------------------------------------------------------------------

def test_compute_metrics_complete_single_mode():
    rooms = [
        {"clean_mode": "vacuum", "fan_speed": "standard", "water_level": "off",
         "clean_passes": 1, "edge_mopping": False, "estimated_minutes": 15.0},
        {"clean_mode": "vacuum", "fan_speed": "standard", "water_level": "off",
         "clean_passes": 1, "edge_mopping": False, "estimated_minutes": 15.0},
    ]
    result = compute_job_battery_metrics(
        battery_start=80,
        battery_end=68,
        duration_minutes=30.0,
        cleaning_area_m2=60.0,
        resolved_rooms=rooms,
    )
    assert result["battery_used_pct"] == 12
    assert result["duration_min"] == pytest.approx(30.0)
    assert result["area_m2"] == pytest.approx(60.0)
    assert result["drain_per_min"] == pytest.approx(12 / 30, rel=1e-3)
    assert result["drain_per_hour"] == pytest.approx(12 / 30 * 60, rel=1e-3)
    assert result["drain_per_m2"] == pytest.approx(12 / 60, rel=1e-3)
    assert result["is_single_clean_mode"] is True
    assert result["single_clean_mode"] == "vacuum"
    assert result["weighted_by"] == "estimated_minutes"


def test_compute_metrics_no_rooms():
    result = compute_job_battery_metrics(
        battery_start=90,
        battery_end=75,
        duration_minutes=20.0,
        cleaning_area_m2=40.0,
        resolved_rooms=None,
    )
    assert result["battery_used_pct"] == 15
    assert result["weighted_by"] == "none"
    assert result["by_clean_mode"] == {}
    assert result["by_fan_speed"] == {}
    assert result["by_water_level"] == {}


def test_compute_metrics_all_inputs_none():
    result = compute_job_battery_metrics(
        battery_start=None,
        battery_end=None,
        duration_minutes=None,
        cleaning_area_m2=None,
        resolved_rooms=None,
    )
    assert result["battery_used_pct"] is None
    assert result["duration_min"] is None
    assert result["area_m2"] is None
    assert result["drain_per_min"] is None
    assert result["drain_per_hour"] is None
    assert result["drain_per_m2"] is None


def test_compute_metrics_mixed_modes():
    rooms = [
        {"clean_mode": "vacuum", "fan_speed": "max", "water_level": "off",
         "clean_passes": 1, "edge_mopping": False},
        {"clean_mode": "vacuum_mop", "fan_speed": "standard", "water_level": "high",
         "clean_passes": 2, "edge_mopping": True},
    ]
    result = compute_job_battery_metrics(
        battery_start=80,
        battery_end=60,
        duration_minutes=40.0,
        cleaning_area_m2=80.0,
        resolved_rooms=rooms,
    )
    assert result["is_single_clean_mode"] is False
    assert result["single_clean_mode"] is None
    assert result["is_single_fan_speed"] is False
    assert "vacuum" in result["by_clean_mode"]
    assert "vacuum_mop" in result["by_clean_mode"]
    # Edge mopping: 1 of 2 rooms has it; equal weights → 50/50
    assert result["edge_mopping"]["on_share"] == pytest.approx(0.5)
    assert result["edge_mopping"]["off_share"] == pytest.approx(0.5)


def test_compute_metrics_single_room():
    rooms = [
        {"clean_mode": "mop", "fan_speed": "quiet", "water_level": "medium",
         "clean_passes": 1, "edge_mopping": True},
    ]
    result = compute_job_battery_metrics(
        battery_start=100,
        battery_end=85,
        duration_minutes=25.0,
        cleaning_area_m2=30.0,
        resolved_rooms=rooms,
    )
    assert result["battery_used_pct"] == 15
    assert result["is_single_clean_mode"] is True
    assert result["single_clean_mode"] == "mop"
    assert result["is_single_water_level"] is True
    assert result["single_water_level"] == "medium"
    assert result["edge_mopping"]["on_share"] == pytest.approx(1.0)
    assert result["weighted_by"] == "room_count"


def test_compute_metrics_area_omitted_from_buckets_when_none():
    """When area_m2 is None, buckets should not contain area_m2 key."""
    rooms = [{"clean_mode": "vacuum", "fan_speed": "standard", "water_level": "off",
              "clean_passes": 1, "edge_mopping": False}]
    result = compute_job_battery_metrics(
        battery_start=80, battery_end=70,
        duration_minutes=15.0,
        cleaning_area_m2=None,
        resolved_rooms=rooms,
    )
    assert "area_m2" not in result["by_clean_mode"].get("vacuum", {})


def test_compute_metrics_passes_share_present():
    rooms = [
        {"clean_mode": "vacuum", "fan_speed": "standard", "water_level": "off",
         "clean_passes": 1, "edge_mopping": False},
        {"clean_mode": "vacuum", "fan_speed": "standard", "water_level": "off",
         "clean_passes": 2, "edge_mopping": False},
    ]
    result = compute_job_battery_metrics(
        battery_start=80, battery_end=60,
        duration_minutes=30.0, cleaning_area_m2=50.0,
        resolved_rooms=rooms,
    )
    assert "passes_share" in result
    assert "1" in result["passes_share"] or 1 in result["passes_share"]
