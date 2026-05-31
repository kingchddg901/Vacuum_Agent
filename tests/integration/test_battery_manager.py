"""Integration tests for battery/manager.py — BatteryHealthManager.

Constructed against the real `manager` fixture (provides .data storage + hass).
The cycle/rate/session/health math is driven by calling _process_sample with
crafted sample sequences; record management is exercised directly.

Coverage targets
----------------
[BM-1]  ensure_record: creates a new record; repairs missing keys on old ones.
[BM-2]  add_update_listener + _notify fires; unsub removes.
[BM-3]  rebaseline clears the baseline anchor; unknown vacuum → False.
[BM-4]  record_job_metrics: last_job + all_jobs aggregate + single-bucket; non-dict no-op.
[BM-5]  _update_aggregate_bucket: count + rolling means.
[BM-6]  _process_sample: drain accumulates into cumulative_drain_pct / cycles.
[BM-7]  _process_sample: a delta above MAX_DELTA_PCT is rejected (no drain).
[BM-8]  _process_sample: overall / low-zone / high-zone charge rates.
[BM-9]  _process_sample: session open → accumulate → close (history append).
[BM-10] _process_sample: session closes "full" at 100%.
[BM-11] _process_sample: a 50→90 charge anchors the baseline + sets health_pct.
[BM-12] _process_sample: out-of-range battery level is ignored.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.eufy_vacuum.battery.manager import BatteryHealthManager


_VAC = "vacuum.alfred"
_T0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def bm(hass, manager) -> BatteryHealthManager:
    return BatteryHealthManager(hass, runtime_manager=manager)


def _feed(bm, samples: list[tuple[int, bool, float]]) -> None:
    """Feed (battery_level, charging, dt_seconds) samples in order."""
    t = _T0
    for level, charging, dt in samples:
        t = t + timedelta(seconds=dt)
        bm._process_sample(vacuum_entity_id=_VAC, battery_level=level, charging=charging, ts=t)


# ---------------------------------------------------------------------------
# Record management
# ---------------------------------------------------------------------------

def test_ensure_record(bm):
    """[BM-1]"""
    rec = bm.ensure_record(_VAC)
    assert "stats" in rec and "baseline" in rec
    # repair: drop a key, re-ensure restores it
    del rec["stats"]
    rec2 = bm.ensure_record(_VAC)
    assert "stats" in rec2


def test_update_listener(bm):
    """[BM-2]"""
    seen: list[str] = []
    unsub = bm.add_update_listener(lambda v: seen.append(v))
    bm._notify(_VAC)
    assert seen == [_VAC]
    unsub()
    bm._notify(_VAC)
    assert seen == [_VAC]  # no further calls


def test_rebaseline(bm):
    """[BM-3]"""
    rec = bm.ensure_record(_VAC)
    rec["baseline"]["cc_min_per_pct"] = 1.0
    rec["baseline"]["cv_min_per_pct"] = 1.0
    assert bm.rebaseline(_VAC) is True
    assert rec["baseline"]["cc_min_per_pct"] is None
    assert bm.rebaseline("vacuum.unknown") is False


def test_record_job_metrics(bm):
    """[BM-4]"""
    bm.record_job_metrics(vacuum_entity_id=_VAC, job_id="j1", metrics={
        "battery_used_pct": 20, "duration_min": 40, "area_m2": 25,
        "drain_per_min": 0.5, "is_single_clean_mode": True, "single_clean_mode": "vacuum",
    })
    rec = bm.get_record(_VAC)
    assert rec["last_job"]["job_id"] == "j1"
    assert rec["job_aggregates"]["all_jobs"]["count"] == 1
    assert rec["job_aggregates"]["by_clean_mode"]["vacuum"]["count"] == 1
    assert _VAC in bm._pending_post_job
    # non-dict → no-op (last_job unchanged)
    bm.record_job_metrics(vacuum_entity_id=_VAC, metrics=None)  # type: ignore[arg-type]
    assert rec["last_job"]["job_id"] == "j1"


def test_update_aggregate_bucket(bm):
    """[BM-5]"""
    bucket: dict = {}
    BatteryHealthManager._update_aggregate_bucket(
        bucket, {"battery_used_pct": 20, "duration_min": 40, "area_m2": 10})
    assert bucket["count"] == 1
    assert bucket["drain_per_min_mean"] == pytest.approx(0.5)   # 20/40
    assert bucket["drain_per_m2_mean"] == pytest.approx(2.0)    # 20/10


# ---------------------------------------------------------------------------
# Sample pipeline
# ---------------------------------------------------------------------------

async def test_cycle_counting(bm):
    """[BM-6]"""
    _feed(bm, [(80, False, 0), (78, False, 60), (76, False, 60)])
    rec = bm.get_record(_VAC)
    assert rec["cumulative_drain_pct"] == pytest.approx(4.0)
    assert rec["cycles"] == pytest.approx(0.04)


async def test_max_delta_guard(bm):
    """[BM-7]"""
    _feed(bm, [(80, False, 0), (10, False, 60)])  # delta -70, rejected
    rec = bm.get_record(_VAC)
    assert rec["cumulative_drain_pct"] == pytest.approx(0.0)


async def test_charge_rates(bm):
    """[BM-8]"""
    _feed(bm, [(50, True, 0), (52, True, 60)])          # mid zone
    assert bm.get_record(_VAC)["stats"]["rate_overall_per_min"] == pytest.approx(2.0)
    _feed(bm, [(80, True, 600), (82, True, 60)])         # high zone (>= 80)
    assert bm.get_record(_VAC)["stats"]["rate_high_zone_per_min"] == pytest.approx(2.0)
    _feed(bm, [(27, True, 600), (29, True, 60)])         # low zone (<= 29)
    assert bm.get_record(_VAC)["stats"]["rate_low_zone_per_min"] == pytest.approx(2.0)


async def test_session_open_accumulate_close(bm):
    """[BM-9]"""
    _feed(bm, [(50, False, 0), (52, True, 60), (54, True, 60), (54, False, 60)])
    rec = bm.get_record(_VAC)
    assert rec["current_session"] is None
    history = rec["session_history_recent"]
    assert len(history) == 1
    assert history[-1]["end_battery"] == 54


async def test_session_closes_full(bm):
    """[BM-10]"""
    _feed(bm, [(98, False, 0), (99, True, 60), (100, True, 60)])
    rec = bm.get_record(_VAC)
    assert rec["session_history_recent"][-1]["ended_reason"] == "full"


async def test_health_anchors_on_full_charge(bm):
    """[BM-11] a 50→90 charge spanning CC + CV regions anchors the baseline."""
    samples = [(48, False, 0), (50, True, 60)]
    lvl = 50
    while lvl < 90:
        lvl += 2
        samples.append((lvl, True, 60))
    samples.append((90, False, 60))  # close
    _feed(bm, samples)

    rec = bm.get_record(_VAC)
    assert rec["baseline"]["cc_min_per_pct"] is not None
    assert rec["baseline"]["cv_min_per_pct"] is not None
    # first qualifying session anchors the baseline → current == baseline → 100%
    assert rec["stats"]["health_pct"] == pytest.approx(100.0)


async def test_out_of_range_ignored(bm):
    """[BM-12]"""
    _feed(bm, [(150, False, 0), (-5, False, 60)])
    rec = bm.get_record(_VAC)
    assert rec.get("last_battery_level") is None
