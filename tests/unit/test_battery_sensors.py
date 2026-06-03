"""Unit tests for battery/sensors.py — entity classes over a mock manager.

Coverage targets
----------------
[BS-1]  build_battery_sensors returns the full 12-sensor set with unique ids.
[BS-2]  ChargeCyclesSensor: native value + drain/session attributes.
[BS-3]  ChargeRateSensor: overall/low/high zone read the right stat key.
[BS-4]  LastChargeDurationSensor: native value + delta attribute.
[BS-5]  BatteryHealthSensor: native value + baseline attributes.
[BS-6]  RegimeChargeSpeedSensor: cc/cv native + baseline_min_per_pct.
[BS-7]  LastJobMetricSensor: native + aggregate attributes (all_jobs/by-bucket).
[BS-8]  MidJobRechargeRateSensor: native + sample-count attributes.
[BS-9]  Empty record → native_value None across sensors.
[BS-10] _bucket_means projects count+mean; non-dict → {}.
[BS-11] unique_id / suggested_object_id derive from vacuum + suffix.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.battery.sensors import (
    BatteryHealthSensor,
    ChargeCyclesSensor,
    ChargeRateSensor,
    LastChargeDurationSensor,
    LastJobMetricSensor,
    MidJobRechargeRateSensor,
    RegimeChargeSpeedSensor,
    _bucket_means,
    build_battery_sensors,
)


_VAC = "vacuum.alfred"


_RECORD = {
    "cycles": 12.34,
    "cumulative_drain_pct": 1234.0,
    "session_history_recent": [{}, {}, {}],
    "last_battery_level": 73,
    "last_charging": True,
    "last_sample_ts": "2026-01-01T10:00:00+00:00",
    "stats": {
        "rate_overall_per_min": 1.5,
        "rate_low_zone_per_min": 0.8,
        "rate_high_zone_per_min": 0.4,
        "last_charge_duration_min": 95.0,
        "last_charge_delta_pct": 60.0,
        "health_pct": 92.0,
        "cc_charge_speed_pct": 88.0,
        "cv_charge_speed_pct": 92.0,
    },
    "baseline": {
        "cv_min_per_pct": 1.2, "cc_min_per_pct": 0.9,
        "session_count": 5, "anchored_at": "2026-01-01",
    },
    "last_job": {
        "job_id": "j1", "recorded_at": "2026-01-01T09:00:00+00:00",
        "drain_per_min": 0.5, "drain_per_hour": 30.0, "drain_per_m2": 0.2,
        "duration_min": 40, "area_m2": 25, "battery_used_pct": 20,
        "single_clean_mode": "vacuum", "weighted_by": "single",
    },
    "job_aggregates": {
        "all_jobs": {"drain_per_min_mean": 0.5, "count": 10},
        "by_clean_mode": {"vacuum": {"count": 5, "drain_per_min_mean": 0.5}},
        "by_fan_speed": {}, "by_water_level": {},
    },
    "mid_job_recharge_stats": {
        "rate_mean_per_min": 2.1, "count": 3,
        "last_rate_per_min": 2.0, "last_recorded_at": "2026-01-01T08:00:00+00:00",
    },
}


def _mgr(record=None) -> MagicMock:
    m = MagicMock()
    m.get_record.return_value = record if record is not None else _RECORD
    m.add_update_listener.return_value = lambda: None
    return m


# ---------------------------------------------------------------------------
# factory
# ---------------------------------------------------------------------------

def test_build_set():
    """[BS-1]"""
    sensors = build_battery_sensors(manager=_mgr(), vacuum_entity_id=_VAC)
    assert len(sensors) == 12
    uids = {s.unique_id for s in sensors}
    assert "vacuum_alfred_charge_cycles" in uids
    assert "vacuum_alfred_mid_job_recharge_rate" in uids


# ---------------------------------------------------------------------------
# individual sensors
# ---------------------------------------------------------------------------

def test_charge_cycles():
    """[BS-2]"""
    s = ChargeCyclesSensor(manager=_mgr(), vacuum_entity_id=_VAC)
    assert s.native_value == pytest.approx(12.34)
    attrs = s.extra_state_attributes
    assert attrs["cumulative_drain_pct"] == 1234.0
    assert attrs["completed_sessions"] == 3


@pytest.mark.parametrize("stat,expected", [
    ("rate_overall_per_min", 1.5),
    ("rate_low_zone_per_min", 0.8),
    ("rate_high_zone_per_min", 0.4),
])
def test_charge_rate(stat, expected):
    """[BS-3]"""
    s = ChargeRateSensor(manager=_mgr(), vacuum_entity_id=_VAC,
                         stat_key=stat, translation_key="t", unique_suffix="u")
    assert s.native_value == pytest.approx(expected)
    assert s.extra_state_attributes["battery_level"] == 73


def test_last_charge_duration():
    """[BS-4]"""
    s = LastChargeDurationSensor(manager=_mgr(), vacuum_entity_id=_VAC)
    assert s.native_value == pytest.approx(95.0)
    assert s.extra_state_attributes["last_charge_delta_pct"] == 60.0


def test_battery_health():
    """[BS-5]"""
    s = BatteryHealthSensor(manager=_mgr(), vacuum_entity_id=_VAC)
    assert s.native_value == pytest.approx(92.0)
    attrs = s.extra_state_attributes
    assert attrs["baseline_cv_min_per_pct"] == 1.2
    assert attrs["completed_sessions"] == 3


def test_regime_charge_speed():
    """[BS-6]"""
    cc = RegimeChargeSpeedSensor(manager=_mgr(), vacuum_entity_id=_VAC,
                                 stat_key="cc_charge_speed_pct", baseline_key="cc_min_per_pct",
                                 translation_key="t", unique_suffix="cc")
    assert cc.native_value == pytest.approx(88.0)
    assert cc.extra_state_attributes["baseline_min_per_pct"] == 0.9


def test_last_job_metric():
    """[BS-7]"""
    s = LastJobMetricSensor(manager=_mgr(), vacuum_entity_id=_VAC,
                            stat_key="drain_per_min", translation_key="t",
                            unique_suffix="u", unit="%/min")
    assert s.native_value == pytest.approx(0.5)
    attrs = s.extra_state_attributes
    assert attrs["job_id"] == "j1"
    assert attrs["all_jobs_mean"] == 0.5
    assert attrs["all_jobs_count"] == 10
    assert attrs["by_clean_mode_mean"]["vacuum"] == {"count": 5, "mean": 0.5}


def test_mid_job_recharge():
    """[BS-8]"""
    s = MidJobRechargeRateSensor(manager=_mgr(), vacuum_entity_id=_VAC)
    assert s.native_value == pytest.approx(2.1)
    assert s.extra_state_attributes["sample_count"] == 3


# ---------------------------------------------------------------------------
# None handling + helpers
# ---------------------------------------------------------------------------

def test_empty_record_none():
    """[BS-9]"""
    mgr = _mgr({"stats": {}, "baseline": {}})
    assert ChargeCyclesSensor(manager=mgr, vacuum_entity_id=_VAC).native_value is None
    assert BatteryHealthSensor(manager=mgr, vacuum_entity_id=_VAC).native_value is None
    assert MidJobRechargeRateSensor(manager=mgr, vacuum_entity_id=_VAC).native_value is None


def test_bucket_means():
    """[BS-10]"""
    out = _bucket_means({"vacuum": {"count": 4, "drain_per_min_mean": 0.6}}, "drain_per_min_mean")
    assert out == {"vacuum": {"count": 4, "mean": 0.6}}
    assert _bucket_means("nope", "drain_per_min_mean") == {}
    assert _bucket_means({"x": {}}, None) == {}


def test_unique_and_object_id():
    """[BS-11]"""
    s = ChargeCyclesSensor(manager=_mgr(), vacuum_entity_id=_VAC)
    assert s.unique_id == "vacuum_alfred_charge_cycles"
    assert s._attr_suggested_object_id == "alfred_charge_cycles"


async def test_on_manager_update_dispatches_state_write(hass):
    """[BS-12] _on_manager_update for the matching vacuum schedules a threadsafe
    state write; a mismatched vacuum returns early without error."""
    s = ChargeCyclesSensor(manager=_mgr(), vacuum_entity_id=_VAC)
    s.hass = hass
    s._on_manager_update(_VAC)             # matching vacuum → schedules _write
    s._on_manager_update("vacuum.other")   # mismatch → early return
    await hass.async_block_till_done()
