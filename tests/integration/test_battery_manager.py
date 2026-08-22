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
[BM-21] compute_time_to_target_pct: learned baselines (CC sub-80 + CV taper >=80).
[BM-22] compute_time_to_target_pct: at/above target → 0 minutes.
[BM-23] compute_time_to_target_pct: cold-start (no baseline/rates) → None (wall-clock).
[BM-24] compute_time_to_target_pct: zone-rate fallback (%/min) when no baseline.
[BM-25] compute_time_to_target_pct: CV-only span needs only the CV baseline.
[BM-26] RP-043: THIS session's own zone rate outranks the never-re-anchored baseline.
[BM-27] RP-044: an open session with no sample of its own SKIPS the cross-session
        stats tier (they are the previous charge's leftovers) — with the no-session
        control that proves the stats tier is otherwise legitimate, and the partial
        case proving the two spans resolve independently.
[BM-28] RP-042: an unreadable (None) battery is a GAP — no anchor advance, no drain,
        and nothing reaches the session ring that feeds health_pct.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.battery.manager import (
    REGIME_PCT_MAX,
    REGIME_PCT_MIN,
    BatteryHealthManager,
)


def _iso_now() -> str:
    """A timestamp inside the regime guard's CURRENT_WINDOW_DAYS lookback."""
    return datetime.now(timezone.utc).isoformat()


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
# compute_time_to_target_pct (charge-step Wave 2 ETA)
# ---------------------------------------------------------------------------

def _seed_charge(bm, *, cc=None, cv=None, low=None, high=None, overall=None):
    rec = bm.ensure_record(_VAC)
    rec["baseline"]["cc_min_per_pct"] = cc
    rec["baseline"]["cv_min_per_pct"] = cv
    rec["stats"]["rate_low_zone_per_min"] = low
    rec["stats"]["rate_high_zone_per_min"] = high
    rec["stats"]["rate_overall_per_min"] = overall


def test_charge_eta_from_baseline(bm):
    """[BM-21] sub-80 span uses cc_min_per_pct, >=80 span uses the CV taper."""
    _seed_charge(bm, cc=1.0, cv=3.0)
    # 60->80 = 20pp * 1.0 + 80->95 = 15pp * 3.0 = 20 + 45
    assert bm.compute_time_to_target_pct(vacuum_entity_id=_VAC, current_pct=60, target_pct=95) \
        == {"minutes": 65.0, "source": "baseline"}


def test_charge_eta_already_charged(bm):
    """[BM-22]"""
    _seed_charge(bm, cc=1.0, cv=3.0)
    assert bm.compute_time_to_target_pct(vacuum_entity_id=_VAC, current_pct=96, target_pct=95) \
        == {"minutes": 0.0, "source": "already_charged"}


def test_charge_eta_cold_start_is_none(bm):
    """[BM-23] no baseline and no rates -> None (caller shows wall-clock, not a fake ETA)."""
    _seed_charge(bm)  # all None
    assert bm.compute_time_to_target_pct(vacuum_entity_id=_VAC, current_pct=50, target_pct=95) \
        == {"minutes": None, "source": None}


def test_charge_eta_zone_rate_fallback(bm):
    """[BM-24] no baseline but zone rates present -> minutes from %/min rates."""
    _seed_charge(bm, low=2.0, high=0.5)
    # 20pp / 2.0 + 15pp / 0.5 = 10 + 30
    assert bm.compute_time_to_target_pct(vacuum_entity_id=_VAC, current_pct=60, target_pct=95) \
        == {"minutes": 40.0, "source": "zone_rate"}


def test_charge_eta_cv_only_span_needs_only_cv_baseline(bm):
    """[BM-25] already in the CV zone: cc baseline is irrelevant (cc_span=0)."""
    _seed_charge(bm, cc=None, cv=3.0)
    assert bm.compute_time_to_target_pct(vacuum_entity_id=_VAC, current_pct=85, target_pct=95) \
        == {"minutes": 30.0, "source": "baseline"}


def _open_session(bm, *, low_sum=None, low_n=0, high_sum=None, high_n=0) -> dict:
    """Open a charging session, optionally with its OWN zone-rate samples already
    accumulated (what _process_sample fills in during a live charge)."""
    rec = bm.ensure_record(_VAC)
    session: dict = {"started_at": _T0.isoformat(), "start_battery": 60}
    if low_n:
        session["low_zone_rate_sum"] = low_sum
        session["low_zone_rate_samples"] = low_n
    if high_n:
        session["high_zone_rate_sum"] = high_sum
        session["high_zone_rate_samples"] = high_n
    rec["current_session"] = session
    return session


def test_charge_eta_prefers_this_sessions_own_rate_over_the_baseline(bm):
    """[BM-26] RP-043's inversion, which is the whole point of the packet.

    The learned baseline is anchored ONCE and never re-anchors — Alfred's is from
    2026-06-08 — so preferring it meant every ETA since divided by a two-month-old
    rate. A rate this session actually observed wins, even though a baseline exists.
    """
    _seed_charge(bm, cc=1.0, cv=3.0)
    _open_session(bm, low_sum=4.0, low_n=2, high_sum=1.0, high_n=2)  # 2.0 and 0.5 %/min
    # 20pp / 2.0 + 15pp / 0.5 = 10 + 30 — the baseline's 65.0 must NOT win.
    assert bm.compute_time_to_target_pct(vacuum_entity_id=_VAC, current_pct=60, target_pct=95) \
        == {"minutes": 40.0, "source": "zone_rate"}


def test_charge_eta_open_session_without_its_own_sample_skips_stale_stats(bm):
    """[BM-27] RP-044's cold-start contract — the subtlest branch in the precedence.

    A session is open but has not yet produced a sample for this zone. The
    cross-session `stats.rate_*_zone_per_min` still holds the PREVIOUS charge's
    number, and quietly dividing by it is what made the first paint of a charge
    "well off" on live hardware. That tier must be skipped entirely, falling to the
    baseline rather than a leftover.
    """
    _seed_charge(bm, cc=1.0, cv=3.0, low=2.0, high=0.5)
    _open_session(bm)  # open, but no zone samples of its own yet

    out = bm.compute_time_to_target_pct(
        vacuum_entity_id=_VAC, current_pct=60, target_pct=95)
    assert out == {"minutes": 65.0, "source": "baseline"}, (
        "the ETA divided by the previous session's carried-over zone rate "
        "(40.0/zone_rate) instead of skipping that tier"
    )


def test_charge_eta_no_open_session_may_use_cross_session_stats(bm):
    """[BM-27] The control for the test above: with NO session open there is no
    'this charge' to be stale against, so the cross-session rate is legitimate and
    still outranks the frozen baseline."""
    _seed_charge(bm, cc=1.0, cv=3.0, low=2.0, high=0.5)
    assert bm.get_record(_VAC).get("current_session") is None
    assert bm.compute_time_to_target_pct(vacuum_entity_id=_VAC, current_pct=60, target_pct=95) \
        == {"minutes": 40.0, "source": "zone_rate"}


def test_charge_eta_partial_session_samples_skip_only_the_unsampled_zone(bm):
    """[BM-27] The two spans resolve INDEPENDENTLY. A session that has sampled the
    low zone but not yet the high zone must use its own low rate and the baseline
    for the high — not one policy for the whole span."""
    _seed_charge(bm, cc=1.0, cv=3.0, low=99.0, high=99.0)  # stats deliberately absurd
    _open_session(bm, low_sum=4.0, low_n=2)                # own low rate = 2.0 %/min
    # low: 20pp / 2.0 = 10 (own sample) ; high: 15pp * 3.0 = 45 (baseline, stats skipped)
    out = bm.compute_time_to_target_pct(
        vacuum_entity_id=_VAC, current_pct=60, target_pct=95)
    assert out["minutes"] == 55.0, out


async def test_unreadable_battery_is_a_gap_not_a_sample(bm):
    """[BM-28] RP-042. `None` means the sensor dropped out, and a dropout is not a
    flat pack. It must not advance the anchor, accumulate drain, or reach the
    session ring — the ring feeds health_pct, and an unguarded raw value there is
    the shared cause behind RP-042 and RP-045.
    """
    _feed(bm, [(80, True, 0), (82, True, 60)])
    rec = bm.get_record(_VAC)
    before_level = rec.get("last_battery_level")
    before_drain = rec.get("cumulative_drain_pct")
    before_session = dict(rec.get("current_session") or {})

    bm._process_sample(
        vacuum_entity_id=_VAC, battery_level=None, charging=True,
        ts=_T0 + timedelta(seconds=120))

    rec = bm.get_record(_VAC)
    assert rec.get("last_battery_level") == before_level, "the anchor moved on a gap"
    assert rec.get("cumulative_drain_pct") == before_drain
    assert dict(rec.get("current_session") or {}) == before_session, (
        "an unreadable reading reached the session ring"
    )


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

def test_a_job_without_area_does_not_move_the_per_m2_mean(bm):
    """[BM-5b] C17 — a ratio's numerator and denominator must count the same jobs.

    THE FAILURE THIS REPRODUCES. Ten cleans. Six report an area; on four the
    finalizer's area read comes back null because it loses the same finalize-time
    race job_finalizer.py documents for cleaning_time. No learning-blocker stops
    those four being recorded, so all ten fold into the bucket.

    Before the fix a single drain_pct_sum fed every mean: 200 / 60 = 3.333 %/m2,
    against an honest 120 / 60 = 2.0 over the six jobs that were actually measured.
    67% high, and worse the more area-less runs land.

    THE ZERO-GUARD DID NOT PREVENT THIS AND CANNOT. `if a_sum > 0 else None` fires
    only when NO job in the bucket carried an area; one measured job is enough for
    the division to proceed over mismatched populations. That is why this test feeds
    a MIXTURE rather than an all-null bucket — an all-null bucket is the one case the
    old code got right.
    """
    bucket: dict = {}
    for _ in range(6):
        BatteryHealthManager._update_aggregate_bucket(
            bucket, {"battery_used_pct": 20, "duration_min": 40, "area_m2": 10})
    for _ in range(4):
        BatteryHealthManager._update_aggregate_bucket(
            bucket, {"battery_used_pct": 20, "duration_min": 40, "area_m2": None})

    assert bucket["count"] == 10
    assert bucket["samples_area"] == 6, (
        "samples_area must be the jobs that carried an area, not every job"
    )
    assert bucket["samples_duration"] == 10

    assert bucket["drain_per_m2_mean"] == pytest.approx(2.0), (
        f"per-m2 mean is {bucket['drain_per_m2_mean']} — the four area-less jobs put "
        "their drain in the numerator while contributing nothing to the denominator. "
        "3.333 is 200/60: drain from ten jobs over area from six."
    )
    # The per-MINUTE mean is unaffected by the same jobs — all ten had a duration.
    assert bucket["drain_per_min_mean"] == pytest.approx(0.5)


def test_a_job_without_duration_does_not_move_the_per_minute_mean(bm):
    """[BM-5c] C17, the mirror. One numerator served THREE denominators, so the
    substitution ran both ways: a job with area but no duration inflated the
    per-minute mean exactly as an area-less job inflated the per-m2 one. Without
    this, [BM-5b] passes against a fix that only partnered the area half.
    """
    bucket: dict = {}
    for _ in range(6):
        BatteryHealthManager._update_aggregate_bucket(
            bucket, {"battery_used_pct": 20, "duration_min": 40, "area_m2": 10})
    for _ in range(4):
        BatteryHealthManager._update_aggregate_bucket(
            bucket, {"battery_used_pct": 20, "duration_min": None, "area_m2": 10})

    assert bucket["samples_duration"] == 6
    assert bucket["samples_area"] == 10
    assert bucket["drain_per_min_mean"] == pytest.approx(0.5), (
        f"per-minute mean is {bucket['drain_per_min_mean']} — 200/240 = 0.833 is drain "
        "from ten jobs over duration from six"
    )
    assert bucket["drain_per_hour_mean"] == pytest.approx(30.0)
    assert bucket["drain_per_m2_mean"] == pytest.approx(2.0)

def test_a_job_without_drain_does_not_deflate_the_means(bm):
    """[BM-5d] C17, the THIRD direction -- and the one the first fix missed.

    [BM-5b] and [BM-5c] both supply a drain and vary the other field, so both pass
    against a fix that partners only the NUMERATORS. They cannot see a job that
    carries a duration and NO drain: that grew duration_min_sum while
    drain_pct_sum_for_duration stayed put, so the mean came out LOW -- the exact
    mirror of the original defect, which came out high.

    Six jobs at 20% over 40 min, plus four that recorded time but no battery read.
    Honest: 120/240 = 0.5. Numerator-only fix: 120/400 = 0.3, 40% low, and worse the
    more drain-less runs land.

    A drain-less job is the SAME finalize-time race that produces the area-less and
    duration-less jobs in the two tests above; nothing blocks it being recorded.
    """
    bucket: dict = {}
    for _ in range(6):
        BatteryHealthManager._update_aggregate_bucket(
            bucket, {"battery_used_pct": 20, "duration_min": 40, "area_m2": 10})
    for _ in range(4):
        BatteryHealthManager._update_aggregate_bucket(
            bucket, {"battery_used_pct": None, "duration_min": 40, "area_m2": 10})

    assert bucket["count"] == 10
    assert bucket["samples_duration"] == 6, (
        "samples_duration must be the jobs that carried BOTH a drain and a duration"
    )
    assert bucket["samples_area"] == 6

    assert bucket["drain_per_min_mean"] == pytest.approx(0.5), (
        f"per-minute mean is {bucket['drain_per_min_mean']} -- the four drain-less jobs "
        "put their duration in the denominator while contributing nothing to the "
        "numerator. 0.3 is 120/400: drain from six jobs over duration from ten."
    )
    assert bucket["drain_per_m2_mean"] == pytest.approx(2.0), (
        f"per-m2 mean is {bucket['drain_per_m2_mean']} -- same defect on the area side"
    )
    assert bucket["drain_per_hour_mean"] == pytest.approx(30.0)


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
    """[BM-8]

    Each zone block below is an independent 2-sample charge check, and
    _feed() restarts its own clock at _T0 every call -- so the record's
    last-sample anchor is cleared between blocks. Since DR-BAT-2 (RP-040
    closing batch), an out-of-order sample no longer rewinds the anchor, so
    without this reset the high/low-zone blocks' first sample would read as
    out-of-order against the mid-zone block's anchor and be silently
    dropped instead of independently exercising each zone.
    """
    _feed(bm, [(50, True, 0), (52, True, 60)])          # mid zone
    assert bm.get_record(_VAC)["stats"]["rate_overall_per_min"] == pytest.approx(2.0)

    rec = bm.get_record(_VAC)
    rec["last_battery_level"] = None
    rec["last_sample_ts"] = None
    _feed(bm, [(80, True, 600), (82, True, 60)])         # high zone (>= 80)
    assert bm.get_record(_VAC)["stats"]["rate_high_zone_per_min"] == pytest.approx(2.0)

    rec["last_battery_level"] = None
    rec["last_sample_ts"] = None
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
    """[BM-13] In-flight is decided by STATUS, not by ended_at.

    This test previously drove the transition by setting ``ended_at`` — a write production
    NEVER performs. ``mark_active_job_finalized`` sets status="completed"/finalized=True and
    leaves ``started_at`` in place; no code path writes ``ended_at`` onto an active-job
    record. So the old assertion encoded a contract that does not exist, and the real
    behaviour (a finished job reading as in-flight forever) went unnoticed.
    """
    assert bm._has_active_job(_VAC) is False

    manager.data["active_jobs"] = {_VAC: {"6": {"started_at": "t", "status": "started"}}}
    assert bm._has_active_job(_VAC) is True

    manager.data["active_jobs"][_VAC]["6"]["status"] = "paused"
    assert bm._has_active_job(_VAC) is True, "a paused run is still in flight"

    # How a run ACTUALLY ends: mark_active_job_finalized sets these and leaves started_at.
    manager.data["active_jobs"][_VAC]["6"].update({"status": "completed", "finalized": True})
    assert bm._has_active_job(_VAC) is False, "a finalized job still read as in-flight"


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


def test_rebuild_job_aggregates_recomputes_from_scratch(bm):
    """[BM-4d] Wave 3b: the drain aggregates become REPAIRABLE.

    job_aggregates is an incremental read-modify-write store outside the learning rebuild,
    so a bad sample (a duplicate finalize, or a run that should have been excluded) sat in
    the drain means permanently — and per-config buckets are narrow enough that it may never
    dilute. The rebuild recomputes from EMPTY; folding onto the existing aggregates would
    preserve exactly what it exists to remove.
    """
    # Poison the store the way a duplicate finalize would.
    bm.record_job_metrics(vacuum_entity_id=_VAC, job_id="dupe", metrics={
        "battery_used_pct": 99, "duration_min": 1, "area_m2": 1,
        "drain_per_min": 99.0, "is_single_clean_mode": True, "single_clean_mode": "vacuum",
    })
    bm.record_job_metrics(vacuum_entity_id=_VAC, job_id="dupe", metrics={
        "battery_used_pct": 99, "duration_min": 1, "area_m2": 1,
        "drain_per_min": 99.0, "is_single_clean_mode": True, "single_clean_mode": "vacuum",
    })
    assert bm.get_record(_VAC)["job_aggregates"]["all_jobs"]["count"] == 2

    archive = [
        {"battery_used_pct": 20, "duration_min": 40, "area_m2": 25, "drain_per_min": 0.5,
         "is_single_clean_mode": True, "single_clean_mode": "vacuum"},
        {"battery_used_pct": 10, "duration_min": 20, "area_m2": 12, "drain_per_min": 0.5,
         "is_single_clean_mode": True, "single_clean_mode": "vacuum"},
        # mid-job recharge -> all_jobs only, must stay OUT of the per-config bucket
        {"battery_used_pct": 30, "duration_min": 60, "area_m2": 30, "drain_per_min": 0.5,
         "is_single_clean_mode": True, "single_clean_mode": "vacuum", "mid_job_recharge": True},
    ]
    applied = bm.rebuild_job_aggregates(vacuum_entity_id=_VAC, metrics_list=archive)

    assert applied == 3
    aggr = bm.get_record(_VAC)["job_aggregates"]
    assert aggr["all_jobs"]["count"] == 3, "the poisoned duplicate survived the rebuild"
    assert aggr["by_clean_mode"]["vacuum"]["count"] == 2, "mid-recharge run leaked into a config bucket"


def test_rebuild_job_aggregates_leaves_last_job_and_charge_linkage_alone(bm):
    """[BM-4e] A rebuild must NOT replay point-in-time state. last_job and the pending
    post-job-charge linkage describe the MOST RECENT run, not derived history — replaying
    them would leave a stale post_job_charge slot for the next real charge to link into."""
    bm.record_job_metrics(vacuum_entity_id=_VAC, job_id="real_last", metrics={
        "battery_used_pct": 20, "duration_min": 40, "area_m2": 25, "drain_per_min": 0.5,
    })
    bm._pending_post_job.pop(_VAC, None)  # simulate it already being consumed

    bm.rebuild_job_aggregates(vacuum_entity_id=_VAC, metrics_list=[
        {"battery_used_pct": 5, "duration_min": 10, "area_m2": 5, "drain_per_min": 0.5},
    ])

    assert bm.get_record(_VAC)["last_job"]["job_id"] == "real_last", "the rebuild overwrote last_job"
    assert _VAC not in bm._pending_post_job, "the rebuild re-armed the post-job-charge linkage"


# ---------------------------------------------------------------------------
# live:BATT-CV-1 — the regime-speed plausibility guard.
#
# `baseline / current * 100` is a RATIO and nothing bounded it: a regime measured
# across a very small window drives `current` toward zero and the quotient
# explodes. Observed on Alfred 2026-08-05 — the FIRST time these fields ever held
# a value — as cv 868.7 against cc 118.4. CV is the taper phase, where charging
# SLOWS, so a CV figure seven times the CC one is backwards from the physics.
# ---------------------------------------------------------------------------


def test_regime_pct_accepts_a_plausible_ratio(bm):
    """A healthy pack matching its anchor, and a genuinely tired one, both pass. The
    floor is deliberately generous — rejecting a grim reading would hide exactly the
    degradation this proxy exists to show."""
    sessions = [{"cv_min_per_pct": 1.0, "end_ts": _iso_now()}]
    assert bm._compute_regime_pct(sessions, 1.0, "cv_min_per_pct") == (100.0, None)

    tired = [{"cv_min_per_pct": 2.5, "end_ts": _iso_now()}]
    value, rejected = bm._compute_regime_pct(tired, 1.0, "cv_min_per_pct")
    assert value == 40.0 and rejected is None


def test_regime_pct_rejects_the_impossible_ratio_and_keeps_it(bm):
    """The observed failure. A tiny `current` inflates the ratio without limit; the
    value must not be published, and must not vanish either — a rejection that leaves
    no trace makes "reads unknown" indistinguishable from "never computed"."""
    sessions = [{"cv_min_per_pct": 0.115, "end_ts": _iso_now()}]
    value, rejected = bm._compute_regime_pct(sessions, 1.0, "cv_min_per_pct")
    assert value is None
    assert rejected is not None and rejected > REGIME_PCT_MAX


def test_regime_pct_rejects_below_the_floor(bm):
    sessions = [{"cv_min_per_pct": 100.0, "end_ts": _iso_now()}]
    value, rejected = bm._compute_regime_pct(sessions, 1.0, "cv_min_per_pct")
    assert value is None and rejected is not None and rejected < REGIME_PCT_MIN


def test_regime_pct_no_data_is_not_a_rejection(bm):
    """No baseline / no sessions returns (None, None) — nothing was computed, so
    nothing was thrown away. Keeping those cases distinct is the whole point."""
    assert bm._compute_regime_pct([], None, "cv_min_per_pct") == (None, None)
    assert bm._compute_regime_pct([], 1.0, "cv_min_per_pct") == (None, None)
    assert bm._compute_regime_pct(
        [{"cv_min_per_pct": 0.0, "end_ts": _iso_now()}], 1.0, "cv_min_per_pct"
    ) == (None, None)
