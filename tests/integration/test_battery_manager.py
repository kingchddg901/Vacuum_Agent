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
[BM-13] _has_active_job: true while a job is open; false once ended_at is set.
[BM-14] _is_charging: delegates to manager._is_charging; AttributeError → substring fallback.
[BM-15] _update_mid_job_rate_stat: rolling mean of mid-job recharge rates.
[BM-16] _lookup_vacuum_for_record: resolves the owning vacuum; unstored → "unknown".
[BM-17] _attach_post_job_charge_if_pending: links a post-job charge; gates on pending + link window.
[BM-18] start: wires listeners + samples; a state change routes a sample; stop unsubs.
[BM-19] _classify_session_kind: pending recharge within the link window → post_job.
[BM-20] _classify_session_kind: no/stale pending recharge → idle.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.battery.manager import BatteryHealthManager


_VAC = "vacuum.alfred"
_T0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
_FIXTURES = Path(__file__).parent.parent / "fixtures" / "battery"


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


def test_record_job_metrics_fan_and_water_buckets(bm):
    """[BM-4b] single fan_speed / water_level metrics populate the by_fan_speed
    and by_water_level aggregate buckets."""
    bm.record_job_metrics(vacuum_entity_id=_VAC, job_id="j2", metrics={
        "battery_used_pct": 15, "duration_min": 30, "area_m2": 20, "drain_per_min": 0.5,
        "is_single_fan_speed": True, "single_fan_speed": "Max",
        "is_single_water_level": True, "single_water_level": "High",
    })
    aggr = bm.get_record(_VAC)["job_aggregates"]
    assert aggr["by_fan_speed"]["Max"]["count"] == 1
    assert aggr["by_water_level"]["High"]["count"] == 1


def test_record_job_metrics_mid_recharge_skips_config_buckets(bm):
    """[BM-4c] a mid-job-recharge run's start−end drain nets out the recharge and understates
    the true discharge, so it stays OUT of the per-config drain buckets — but still records
    last_job + all_jobs (mirrors the is_single_* anti-bias gate)."""
    bm.record_job_metrics(vacuum_entity_id=_VAC, job_id="jr", metrics={
        "battery_used_pct": 50, "duration_min": 60, "area_m2": 30, "drain_per_min": 0.8,
        "is_single_clean_mode": True, "single_clean_mode": "vacuum_mop",
        "is_single_fan_speed": True, "single_fan_speed": "Turbo",
        "is_single_water_level": True, "single_water_level": "Low",
        "mid_job_recharge": True,
    })
    rec = bm.get_record(_VAC)
    assert rec["last_job"]["job_id"] == "jr" and rec["last_job"]["mid_job_recharge"] is True
    assert rec["job_aggregates"]["all_jobs"]["count"] == 1            # all_jobs still records it
    assert "vacuum_mop" not in rec["job_aggregates"].get("by_clean_mode", {})  # config buckets skipped
    assert "Turbo" not in rec["job_aggregates"].get("by_fan_speed", {})
    assert "Low" not in rec["job_aggregates"].get("by_water_level", {})


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


async def test_qualifying_charge_revives_health_against_anchored_baseline(bm):
    """[BM-11b] REAL-DATA regression: replay the rare 17→100% qualifying deep-charge
    captured live on 2026-06-20 (tests/fixtures/battery/) through the manager, with the
    per-install baseline ALREADY anchored (the 2026-06-08 anchor). A fresh qualifying
    session must REVIVE health_pct relative to that anchor (~117.6 — this cell charges
    faster than the anchor session did, so >100%). This is the only real-data coverage of
    the CC/CV → health math, which is otherwise tested only on synthetic charges.

    The trace took a freak chain to capture (dead job → freeze → recharge cycling drained
    it to 9%, then a deliberate deep charge) — kept as a fixture so the math stays pinned."""
    fx = json.loads((_FIXTURES / "alfred_qualifying_charge_2026-06-20.json").read_text(encoding="utf-8"))
    ha = fx["health_after"]

    # Pre-anchor the per-install baseline (the 2026-06-08 deep charge already set it).
    rec = bm.ensure_record(_VAC)
    rec["baseline"]["cc_min_per_pct"] = ha["baseline_cc_min_per_pct"]
    rec["baseline"]["cv_min_per_pct"] = ha["baseline_cv_min_per_pct"]
    rec["baseline"]["session_count"] = 1
    rec["baseline"]["anchored_at"] = ha["baseline_anchored_at"]

    # Replay the real per-tick curve: discharge → recharge cycling → the deep 17→100 charge.
    for s in fx["samples"]:
        t = datetime.fromisoformat(str(s["ts"]).replace("Z", "+00:00"))
        bm._process_sample(
            vacuum_entity_id=_VAC, battery_level=int(s["battery_level"]),
            charging=bool(s["charging"]), ts=t,
        )

    stats = bm.get_record(_VAC)["stats"]
    # health REVIVED (was blank live) and reads relative to the anchor.
    assert stats["health_pct"] is not None
    assert stats["health_pct"] == pytest.approx(ha["health_pct"], abs=2.0)
    assert stats["cc_charge_speed_pct"] == pytest.approx(ha["cc_charge_speed_pct"], abs=2.0)
    assert stats["cv_charge_speed_pct"] == pytest.approx(ha["cv_charge_speed_pct"], abs=2.0)
    # the baseline anchor is UNCHANGED (per-install — a later session doesn't re-anchor).
    assert rec["baseline"]["cc_min_per_pct"] == ha["baseline_cc_min_per_pct"]
    # a real qualifying session (start≤50, end≥90, full) landed in the history.
    qual = [h for h in bm.get_record(_VAC)["session_history_recent"]
            if (h.get("start_battery") or 99) <= 50 and (h.get("end_battery") or 0) >= 90]
    assert qual and qual[-1]["ended_reason"] == "full"


async def test_out_of_range_ignored(bm):
    """[BM-12]"""
    _feed(bm, [(150, False, 0), (-5, False, 60)])
    rec = bm.get_record(_VAC)
    assert rec.get("last_battery_level") is None


# ---------------------------------------------------------------------------
# active-job / charging classification
# ---------------------------------------------------------------------------

def test_has_active_job(bm, manager):
    """[BM-13]"""
    assert bm._has_active_job(_VAC) is False
    manager.data["active_jobs"] = {_VAC: {"6": {"started_at": "t", "ended_at": None}}}
    assert bm._has_active_job(_VAC) is True
    manager.data["active_jobs"][_VAC]["6"]["ended_at"] = "t2"
    assert bm._has_active_job(_VAC) is False


def test_is_charging_delegates_and_fallback(bm, manager, hass, monkeypatch):
    """[BM-14] delegates to manager._is_charging; AttributeError → substring fallback."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"charging": "binary_sensor.alfred_charging"}})
    hass.states.async_set("binary_sensor.alfred_charging", "on")
    assert bm._is_charging(_VAC) is True
    # fallback: manager._is_charging raises → substring check on vacuum state
    monkeypatch.setattr(manager, "_is_charging",
                        MagicMock(side_effect=AttributeError))
    hass.states.async_set(_VAC, "charging")
    assert bm._is_charging(_VAC) is True
    hass.states.async_set(_VAC, "docked")
    assert bm._is_charging(_VAC) is False


# ---------------------------------------------------------------------------
# stat helpers
# ---------------------------------------------------------------------------

def test_update_mid_job_rate_stat(bm):
    """[BM-15] rolling mean of mid-job recharge rates."""
    rec = {}
    bm._update_mid_job_rate_stat(rec, 2.0)
    bm._update_mid_job_rate_stat(rec, 4.0)
    s = rec["mid_job_recharge_stats"]
    assert s["count"] == 2
    assert s["rate_mean_per_min"] == pytest.approx(3.0)
    assert s["last_rate_per_min"] == pytest.approx(4.0)


def test_lookup_vacuum_for_record(bm):
    """[BM-16]"""
    rec = bm.ensure_record(_VAC)
    assert bm._lookup_vacuum_for_record(rec) == _VAC
    assert bm._lookup_vacuum_for_record({"not": "stored"}) == "unknown"


# ---------------------------------------------------------------------------
# post-job charge linking
# ---------------------------------------------------------------------------

def test_attach_post_job_charge(bm):
    """[BM-17] a charge session that opens shortly after a job links to it."""
    rec = bm.ensure_record(_VAC)
    rec["last_job"] = {"job_id": "j1"}
    bm._pending_post_job[_VAC] = {"recorded_ts": _T0, "job_id": "j1"}
    summary = {
        "start_ts": (_T0 + timedelta(minutes=5)).isoformat(),
        "end_ts": (_T0 + timedelta(minutes=65)).isoformat(),
        "duration_min": 60, "delta_pct": 40, "avg_rate_per_min": 0.67,
    }
    bm._attach_post_job_charge_if_pending(vacuum_entity_id=_VAC, session_summary=summary)
    assert rec["last_job"]["post_job_charge"]["job_id"] == "j1"
    assert _VAC not in bm._pending_post_job


def test_attach_post_job_charge_gates(bm):
    """[BM-17] no pending → no-op; beyond the link window → dropped, no attach."""
    bm._attach_post_job_charge_if_pending(
        vacuum_entity_id=_VAC, session_summary={"start_ts": _T0.isoformat()})
    rec = bm.ensure_record(_VAC)
    rec["last_job"] = {"job_id": "j1"}
    # session opens 5 hours later (> POST_JOB_CHARGE_LINK_HOURS=4) → dropped
    bm._pending_post_job[_VAC] = {"recorded_ts": _T0, "job_id": "j1"}
    bm._attach_post_job_charge_if_pending(
        vacuum_entity_id=_VAC,
        session_summary={"start_ts": (_T0 + timedelta(hours=5)).isoformat()})
    assert "post_job_charge" not in rec["last_job"]
    assert _VAC not in bm._pending_post_job


# ---------------------------------------------------------------------------
# HA wiring
# ---------------------------------------------------------------------------

async def test_wire_and_state_event(bm, hass):
    """[BM-18] start wires listeners + samples; a state change routes a sample."""
    hass.states.async_set("sensor.alfred_battery", "80")
    bm.start([_VAC])
    assert _VAC in bm._vacuum_unsubs
    hass.states.async_set("sensor.alfred_battery", "79")
    await hass.async_block_till_done()
    # an unrelated entity is ignored
    bm._on_state_event(MagicMock(data={"entity_id": "sensor.other"}))
    bm.stop()
    assert bm._vacuum_unsubs == {}


# ---------------------------------------------------------------------------
# _classify_session_kind — charge-session context tag
# ---------------------------------------------------------------------------

def test_classify_session_post_job_window(bm):
    """[BM-19] a pending post-job recharge recorded within the link window → post_job."""
    bm._pending_post_job[_VAC] = {"recorded_ts": datetime.now(timezone.utc)}
    assert bm._classify_session_kind(_VAC) == "post_job"


def test_classify_session_idle_when_stale_or_absent(bm):
    """[BM-20] no pending recharge, or one older than the window → idle."""
    assert bm._classify_session_kind(_VAC) == "idle"
    bm._pending_post_job[_VAC] = {
        "recorded_ts": datetime.now(timezone.utc) - timedelta(hours=5),
    }
    assert bm._classify_session_kind(_VAC) == "idle"
