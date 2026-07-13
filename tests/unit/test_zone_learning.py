"""Unit tests for saved-zone learning (pure — no HA, no I/O).

[ZL-1]  collect_zone_observations pulls a SINGLE-zone phase's timing into one observation.
[ZL-2]  a MULTI-zone step is skipped (time isn't attributable to one zone_id).
[ZL-3]  non-zone phases, missing/zero-wall timings, and malformed input yield nothing.
[ZL-4]  update_learned_zone: first sample seeds avg=wall, count=1.
[ZL-5]  update_learned_zone: second sample is a running mean; count increments.
[ZL-6]  mop vs vacuum keep separate buckets; different zone_ids keep separate keys.
[ZL-7]  record_observations folds a batch and returns the applied count (0 on empty).
[ZL-8]  estimate_zone_seconds prefers the learned average once a sample exists.
[ZL-9]  estimate falls back to area x per-mode rate before any sample; none with neither.
[ZL-10] estimate is clamped to a sane band (a wild area/sample can't run away).
"""

from __future__ import annotations

from custom_components.eufy_vacuum.learning import zone_learning as zl


_NOW = "2026-07-13T08:00:00+00:00"


def _zone_phase(zone_ids, *, wall, mode="mop", area=0.5):
    return {
        "phase_type": "zone",
        "zone_ids": list(zone_ids),
        "zone_timing": {
            "zone_ids": list(zone_ids),
            "clean_mode": mode,
            "wall_seconds": wall,
            "area_m2": area,
        },
    }


def test_collect_single_zone_observation():
    """[ZL-1]"""
    job = {"phases": [
        {"phase_type": "room_group"},
        _zone_phase(["z1"], wall=270, mode="mop", area=0.5),
    ]}
    obs = zl.collect_zone_observations(job)
    assert obs == [{"zone_id": "z1", "clean_mode": "mop", "wall_seconds": 270, "area_m2": 0.5}]


def test_collect_skips_multi_zone_step():
    """[ZL-2] a step cleaning two zones at once can't attribute time to one zone_id."""
    job = {"phases": [_zone_phase(["z1", "z2"], wall=400)]}
    assert zl.collect_zone_observations(job) == []


def test_collect_ignores_noise():
    """[ZL-3]"""
    assert zl.collect_zone_observations(None) == []
    assert zl.collect_zone_observations({"phases": "nope"}) == []
    # zero / missing wall, and non-zone phases, all drop
    job = {"phases": [
        {"phase_type": "charge_wait"},
        _zone_phase(["z1"], wall=0),
        {"phase_type": "zone", "zone_ids": ["z9"]},          # no zone_timing
    ]}
    assert zl.collect_zone_observations(job) == []


def test_update_first_sample_seeds():
    """[ZL-4]"""
    store = zl.update_learned_zone(
        {}, zone_id="z1", clean_mode="mop", wall_seconds=270, area_m2=0.5, now_iso=_NOW
    )
    b = store["z1"]["mop"]
    assert b["avg_wall_seconds"] == 270 and b["sample_count"] == 1
    assert b["last_wall_seconds"] == 270 and b["last_area_m2"] == 0.5


def test_update_second_sample_is_running_mean():
    """[ZL-5]"""
    store = zl.update_learned_zone(
        {}, zone_id="z1", clean_mode="mop", wall_seconds=200, area_m2=0.5, now_iso=_NOW
    )
    store = zl.update_learned_zone(
        store, zone_id="z1", clean_mode="mop", wall_seconds=300, area_m2=0.5, now_iso=_NOW
    )
    b = store["z1"]["mop"]
    assert b["avg_wall_seconds"] == 250 and b["sample_count"] == 2


def test_modes_and_zones_stay_separate():
    """[ZL-6]"""
    store = zl.update_learned_zone(
        {}, zone_id="z1", clean_mode="mop", wall_seconds=300, area_m2=0.5, now_iso=_NOW
    )
    store = zl.update_learned_zone(
        store, zone_id="z1", clean_mode="vacuum", wall_seconds=60, area_m2=0.5, now_iso=_NOW
    )
    store = zl.update_learned_zone(
        store, zone_id="z2", clean_mode="mop", wall_seconds=120, area_m2=0.3, now_iso=_NOW
    )
    assert store["z1"]["mop"]["avg_wall_seconds"] == 300
    assert store["z1"]["vacuum"]["avg_wall_seconds"] == 60
    assert store["z2"]["mop"]["avg_wall_seconds"] == 120


def test_record_observations_batch_and_empty():
    """[ZL-7]"""
    obs = [
        {"zone_id": "z1", "clean_mode": "mop", "wall_seconds": 270, "area_m2": 0.5},
        {"zone_id": "z2", "clean_mode": "vacuum", "wall_seconds": 40, "area_m2": 0.3},
    ]
    store, applied = zl.record_observations({}, obs, now_iso=_NOW)
    assert applied == 2 and set(store) == {"z1", "z2"}
    store2, applied2 = zl.record_observations(store, [], now_iso=_NOW)
    assert applied2 == 0 and store2 is store


def test_estimate_prefers_learned():
    """[ZL-8] a learned average wins over the area fallback the moment a sample exists."""
    store, _ = zl.record_observations(
        {}, [{"zone_id": "z1", "clean_mode": "mop", "wall_seconds": 285, "area_m2": 0.5}],
        now_iso=_NOW,
    )
    est = zl.estimate_zone_seconds(store, zone_id="z1", clean_mode="mop", area_m2=0.5)
    assert est["source"] == "learned" and est["seconds"] == 285 and est["sample_count"] == 1


def test_estimate_area_fallback_then_none():
    """[ZL-9]"""
    fb = zl.estimate_zone_seconds({}, zone_id="z1", clean_mode="vacuum", area_m2=2.0)
    assert fb["source"] == "area_fallback" and fb["seconds"] == 120  # 2.0 * 60
    none = zl.estimate_zone_seconds({}, zone_id="z1", clean_mode="vacuum", area_m2=None)
    assert none["source"] == "none" and none["seconds"] == 0


def test_estimate_is_clamped():
    """[ZL-10] a huge area can't produce an hours-long ETA; a tiny one can't go sub-floor."""
    hi = zl.estimate_zone_seconds({}, zone_id="z", clean_mode="mop", area_m2=10_000.0)
    assert hi["seconds"] == 3600
    lo = zl.estimate_zone_seconds({}, zone_id="z", clean_mode="vacuum", area_m2=0.0001)
    assert lo["seconds"] == 30
