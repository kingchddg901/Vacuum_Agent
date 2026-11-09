"""Unit tests for battery/sensors.py — entity classes over a mock manager.

Coverage targets
----------------
[BS-1]  build_battery_sensors returns the full 12-sensor set with unique ids.
[BS-2]  ChargeCyclesSensor: native value + drain/session attributes.
[BS-3]  ChargeRateSensor: overall/low/high zone read the right stat key.
[BS-4]  LastChargeDurationSensor: native value + delta attribute.
[BS-5]  BatteryHealthSensor: native value + baseline attributes.
[BS-5b] BatteryHealthSensor: native value clamps to 100%; uncapped_pct attr keeps raw.
[BS-6]  RegimeChargeSpeedSensor: cc/cv native + baseline_min_per_pct.
[BS-7]  LastJobMetricSensor: native + aggregate attributes (all_jobs/by-bucket).
[BS-8]  MidJobRechargeRateSensor: native + sample-count attributes.
[BS-9]  Empty record → native_value None across sensors.
[BS-10] _bucket_means projects count+mean; a non-dict mapping AND a non-dict member
        bucket are both declined — the member half was untested until 2026-11-09.
[BS-11] unique_id / suggested_object_id derive from vacuum + suffix.
[BS-12] _on_manager_update schedules a threadsafe state write on match; mismatch returns early.
[BS-13] LastJobMetricSensor: a corrupt `job_aggregates` or `all_jobs` degrades the
        mean/count pair to None instead of raising inside the property. The
        forgotten sibling of _bucket_means' own isinstance checks ([BS-10]). RNFT127G.
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
    # W2: SANCTIONED bare stub. The subject is the battery SENSOR entity being
    # driven against a deliberately partial manager (docs/testing/04-patterns).
    # Not handed into non-entity production code, so spec_manager is the wrong
    # tool here — it would add ceremony without adding a check.
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
    assert attrs["uncapped_pct"] == pytest.approx(92.0)


def test_battery_health_capped_at_100():
    """[BS-5b] Health clamps to 100% (never 'healthier than new'); the raw
    value survives on uncapped_pct (and on the _cv_charge_speed sensor)."""
    mgr = _mgr({
        "stats": {"health_pct": 117.6, "cv_charge_speed_pct": 117.6},
        "baseline": {"cv_min_per_pct": 1.2},
        "session_history_recent": [],
    })
    s = BatteryHealthSensor(manager=mgr, vacuum_entity_id=_VAC)
    assert s.native_value == pytest.approx(100.0)
    assert s.extra_state_attributes["uncapped_pct"] == pytest.approx(117.6)


def test_regime_charge_speed():
    """[BS-6]"""
    cc = RegimeChargeSpeedSensor(manager=_mgr(), vacuum_entity_id=_VAC,
                                 stat_key="cc_charge_speed_pct", baseline_key="cc_min_per_pct",
                                 translation_key="t", unique_suffix="cc")
    assert cc.native_value == pytest.approx(88.0)
    assert cc.extra_state_attributes["baseline_min_per_pct"] == 0.9


def test_bs_6b_rejected_pct_reaches_the_sensor(monkeypatch):
    """[BS-6b] B17: a rejected regime reading is surfaced as an attribute.

    BatteryHealthManager preserves cc_/cv_charge_speed_rejected_pct explicitly
    ("kept so the failure is diagnosable"). Before B17 (2026-08-24) that value
    was diagnosable only from `.storage` — the sensor exposed baseline_* and
    nothing else, so a user seeing native_value=None had no way to tell "still
    building the baseline" from "your last few reads landed outside the
    25-150% window and were rejected". Same defect on cv.
    """
    record = dict(_RECORD)
    record["stats"] = dict(record["stats"], cc_charge_speed_rejected_pct=180.0,
                                            cv_charge_speed_rejected_pct=None)
    mgr = _mgr(record)
    cc = RegimeChargeSpeedSensor(manager=mgr, vacuum_entity_id=_VAC,
                                 stat_key="cc_charge_speed_pct", baseline_key="cc_min_per_pct",
                                 translation_key="t", unique_suffix="cc")
    cv = RegimeChargeSpeedSensor(manager=mgr, vacuum_entity_id=_VAC,
                                 stat_key="cv_charge_speed_pct", baseline_key="cv_min_per_pct",
                                 translation_key="t", unique_suffix="cv")
    assert cc.extra_state_attributes["rejected_pct"] == 180.0
    assert cv.extra_state_attributes["rejected_pct"] is None, (
        "cv sensor read cc's rejected_pct — the exact substitution the sibling "
        "key naming was designed to prevent"
    )


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
    # B4: the C17 repair applied to `all_jobs` too. This bucket has no samples_*
    # field, so the honest denominator is unknown. Stated as unknown, never
    # borrowed from `count` (which would be the exact substitution C17 stops).
    assert attrs["all_jobs_samples"] is None, (
        "a pre-C17 all_jobs bucket must publish an UNKNOWN denominator, "
        "never fall back to all_jobs_count"
    )
    # C17: samples is None here because the fixture bucket predates the split and
    # carries no samples_duration. Unknown, stated as unknown.
    assert attrs["by_clean_mode_mean"]["vacuum"] == {
        "count": 5,
        "mean": 0.5,
        "samples": None,
    }


def test_bs_7b_all_jobs_samples_reads_its_own_denominator():
    """[BS-7b] B4: `all_jobs_samples` reads the field that matches THIS mean.

    The by_* buckets got this via `_MEAN_SAMPLE_FIELD` twenty lines away; the
    all_jobs row was written without it and was still the row the on-file comment
    named as the symptom ("Jobs: 10, mean over 6"). Assert on the specific
    substitution that would slip through — a per-m2 mean must NOT read samples_duration.
    """
    record = dict(_RECORD)
    # A bucket that has BOTH sample fields present, with different values, so
    # the assertion is that the RIGHT one is read.
    record["job_aggregates"] = {
        "all_jobs": {
            "drain_per_m2_mean": 3.333,
            "count": 10,
            "samples_area": 6,
            "samples_duration": 9,
        },
        "by_clean_mode": {}, "by_fan_speed": {}, "by_water_level": {},
    }
    mgr = _mgr(record)
    s = LastJobMetricSensor(manager=mgr, vacuum_entity_id=_VAC,
                            stat_key="drain_per_m2", translation_key="t",
                            unique_suffix="u", unit="%/m2")
    attrs = s.extra_state_attributes
    assert attrs["all_jobs_mean"] == 3.333
    assert attrs["all_jobs_count"] == 10
    # The per-m2 mean is denominated by samples_area (6), not samples_duration (9)
    # or count (10). Getting either wrong reproduces the exact defect C17 exists
    # to stop, one row further up than the by_* buckets it already fixed.
    assert attrs["all_jobs_samples"] == 6, (
        f"all_jobs_samples read the wrong field: got {attrs['all_jobs_samples']}"
    )


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
    """[BS-10] The projection carries the mean AND the denominator it used.

    C17: ``count`` is every job in the bucket; a mean is computed only over the jobs
    that carried both of its inputs. Publishing the two side by side without
    ``samples`` is what let the card show "3.333 %/m2 — Jobs: 10" for a mean taken
    over six.
    """
    out = _bucket_means(
        {"vacuum": {"count": 4, "drain_per_min_mean": 0.6, "samples_duration": 3}},
        "drain_per_min_mean",
    )
    assert out == {"vacuum": {"count": 4, "mean": 0.6, "samples": 3}}, (
        "the mean must publish the sample size it was computed over, not only the "
        "bucket count — 4 jobs recorded, 3 of them carried a duration"
    )

    # Each mean must read ITS OWN denominator, not whichever one is present.
    bucket = {"count": 9, "drain_per_m2_mean": 2.0, "samples_duration": 9, "samples_area": 6}
    assert _bucket_means({"v": bucket}, "drain_per_m2_mean")["v"]["samples"] == 6, (
        "the per-m2 mean reported the DURATION sample count — the exact substitution "
        "C17 exists to stop"
    )

    # A bucket written before C17 has no samples_* keys. It must say so rather than
    # borrow `count`, which is the number that was wrong in the first place.
    legacy = _bucket_means({"v": {"count": 10, "drain_per_m2_mean": 3.333}}, "drain_per_m2_mean")
    assert legacy["v"]["samples"] is None, (
        "a pre-C17 bucket must report an UNKNOWN denominator, never fall back to count"
    )

    assert _bucket_means("nope", "drain_per_min_mean") == {}
    assert _bucket_means({"x": {}}, None) == {}

    # ...and a non-dict MEMBER inside a valid mapping is SKIPPED, not dereferenced.
    # HALF THIS GUARD WAS ASSERTED BY ABSENCE until 2026-11-09: the line above pins the
    # MAPPING level, and ablating the per-member `if not isinstance(b, dict): continue`
    # reddened NOTHING in the suite. Found by sweeping every copy of RNFT127G rather
    # than by a gate -- and this is the copy the register names as the one that already
    # had it right, so "correct" meant correct in the code and untested in half.
    # The junk member comes FIRST so `continue` is distinguishable from `break`, and a
    # real member follows so the expected value is not the empty fallback.
    mixed = _bucket_means(
        {
            "junk": "not a dict",
            "vacuum": {"count": 2, "drain_per_min_mean": 0.4, "samples_duration": 2},
        },
        "drain_per_min_mean",
    )
    assert mixed == {"vacuum": {"count": 2, "mean": 0.4, "samples": 2}}, (
        "a corrupt member bucket either crashed the projection or took the healthy "
        "sibling after it down with it"
    )


def test_unique_and_object_id():
    """[BS-11] EP-6: _attr_suggested_object_id is no longer set (matches every
    other has_entity_name entity in this codebase) — unique_id alone drives
    entity_id assignment."""
    s = ChargeCyclesSensor(manager=_mgr(), vacuum_entity_id=_VAC)
    assert s.unique_id == "vacuum_alfred_charge_cycles"
    # HA's Entity base class only defines _attr_suggested_object_id when a
    # subclass actually assigns it -- unset here means the attribute is
    # absent entirely, not merely None.
    assert getattr(s, "_attr_suggested_object_id", None) is None


async def test_on_manager_update_dispatches_state_write(hass):
    """[BS-12] _on_manager_update for the matching vacuum schedules a threadsafe
    state write; a mismatched vacuum returns early without writing.

    The write itself is stubbed on the instance — an entity that was never added to
    hass cannot really write state, and the subject here is the SCHEDULING, not the
    write. Both directions are asserted: without the mismatch arm a deleted guard
    would pass, and without the match arm a deleted call_soon_threadsafe (every
    battery sensor silently freezing in HA) would pass.
    """
    s = ChargeCyclesSensor(manager=_mgr(), vacuum_entity_id=_VAC)
    s.hass = hass
    writes: list[str] = []
    s.async_write_ha_state = lambda: writes.append("write")

    s._on_manager_update(_VAC)             # matching vacuum → schedules _write
    # DEFERRED, not inline: the manager notifies from whatever thread triggered the
    # sample (the job finalizer runs in an executor), so the write must be handed to
    # the loop rather than called on the notifying thread.
    assert writes == [], "the state write ran inline instead of being scheduled"
    await hass.async_block_till_done()
    assert writes == ["write"], "the matching vacuum's update scheduled no state write"

    s._on_manager_update("vacuum.other")   # mismatch → early return
    await hass.async_block_till_done()
    assert writes == ["write"], "another vacuum's update wrote this entity's state"


def test_bs13_corrupt_aggregates_do_not_break_the_attribute_set():
    """[BS-13] `LastJobMetricSensor` reads both aggregate levels by ISINSTANCE.

    The twin of [BAM-16], and the worse of the two: this is a SENSOR PROPERTY, so the
    AttributeError surfaced as the entity's whole attribute set disappearing with an
    error in the log, not as a one-off migration failure.

    IT WAS THE FORGOTTEN SIBLING OF A CORRECT COPY IN THIS SAME FILE. `_bucket_means`,
    about a hundred lines below, declines a non-dict mapping AND a non-dict member
    bucket. The `all_jobs` read three lines above its call site used `x or {}` at both
    levels, which substitutes a dict for a FALSY value and passes a truthy non-dict
    through to `.get`. Recorded as RNFT127G.

    A FIRST DRAFT OF THIS DOCSTRING SAID `[BS-10]` "has always pinned that", and the
    ablation sweep measured it FALSE: only the MAPPING half was pinned, and the
    per-member check reddened nothing until [BS-10] gained a case for it in this same
    commit. Worth leaving on the record, because a confident sentence about what
    another test covers is exactly the kind of claim that reads as verification.

    BOTH LEVELS ARE DRIVEN because nothing upstream of this property checks either:
    `_record()` returns the persisted battery record as-is.

    `last_job` IS DELIBERATELY INTACT IN EVERY CASE. It is the source of ten of the
    twelve attributes, so asserting those survive is what distinguishes "the aggregate
    read degraded gracefully" from "the property returned a mostly-empty dict". The
    mean/count pair degrading to None is the narrow claim; the rest of the set carrying
    on is what makes it a graceful degradation rather than a silent loss.
    """
    last = {"job_id": "j9", "drain_per_min": 0.5, "duration_min": 12.0}

    for aggregates in ("junk", ["junk"], {"all_jobs": "corrupt"},
                       {"all_jobs": ["corrupt"]}):
        s = LastJobMetricSensor(
            manager=_mgr({"last_job": last, "job_aggregates": aggregates}),
            vacuum_entity_id=_VAC, stat_key="drain_per_min",
            translation_key="t", unique_suffix="u", unit="%/min",
        )
        attrs = s.extra_state_attributes

        assert attrs["all_jobs_mean"] is None, f"aggregates={aggregates!r}"
        assert attrs["all_jobs_count"] is None
        # The ten attributes that come from `last_job` are untouched.
        assert attrs["job_id"] == "j9"
        assert attrs["duration_min"] == 12.0
        assert s.native_value == pytest.approx(0.5)
