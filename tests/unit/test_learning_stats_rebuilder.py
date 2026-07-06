"""Unit tests for learning/stats_rebuilder.py — pure helpers + stats builders."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.learning.stats_rebuilder import (
    LearningStatsRebuilder,
    _canonical_clean_mode,
    _room_baseline_key,
    _room_key,
    _stddev,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rebuilder(tmp_path: Path) -> LearningStatsRebuilder:
    hass = MagicMock()
    hass.config.config_dir = str(tmp_path)
    return LearningStatsRebuilder(hass)


def _job(
    *,
    job_id: str = "j-001",
    started_at: str = "2026-01-01T09:00:00+00:00",
    ended_at: str = "2026-01-01T09:30:00+00:00",
    duration_minutes: float = 30.0,
    battery_used: float = 25.0,
    room_slugs: list[str] | None = None,
    map_id: int = 6,
    status: str = "completed",
    used_for_learning: bool = True,
    cleaning_area_m2: float | None = None,
    clean_times: int = 1,
    clean_mode: str = "vacuum",
    edge_mopping: bool = False,
    transitions: list[dict] | None = None,
    transit_capture_valid: bool = False,
    room_timings: list[dict] | None = None,
    overhead_observed: dict | None = None,
    cleaning_time_seconds: int | None = None,
) -> dict:
    if room_slugs is None:
        room_slugs = ["kitchen"]
    rooms = [
        {
            "slug": slug,
            "room_id": i + 1,
            "name": slug.title(),
            "clean_mode": clean_mode,
            "clean_intensity": "standard",
            "clean_times": clean_times,
            "is_carpet": False,
            "edge_mopping": edge_mopping,
        }
        for i, slug in enumerate(room_slugs)
    ]
    job_block: dict = {
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_minutes": duration_minutes,
        "room_count": len(rooms),
    }
    if cleaning_area_m2 is not None:
        job_block["cleaning_area_m2"] = cleaning_area_m2
    if cleaning_time_seconds is not None:
        job_block["cleaning_time_seconds"] = cleaning_time_seconds
    if transitions is not None:
        job_block["transitions"] = transitions
        job_block["transit_capture_valid"] = transit_capture_valid
    if room_timings is not None:
        job_block["room_timings"] = room_timings
        job_block["transit_capture_valid"] = transit_capture_valid
    if overhead_observed is not None:
        job_block["overhead_observed"] = overhead_observed
    return {
        "record_type": "completed_job",
        "job_id": job_id,
        "job": job_block,
        "battery": {
            "start": 85,
            "end": int(85 - battery_used),
            "used": battery_used,
        },
        "water": {},
        "job_profile": {
            "map_id": map_id,
            "room_count": len(rooms),
            "room_slugs": room_slugs,
            "rooms": rooms,
        },
        "outcome": {
            "status": status,
            "used_for_learning": used_for_learning,
        },
    }


# ---------------------------------------------------------------------------
# _room_key
# ---------------------------------------------------------------------------

def test_room_key_basic():
    key = _room_key(6, "kitchen", "vacuum", 1, False, "standard")
    assert key == "6::kitchen::vacuum::1::0::standard::0"


def test_room_key_carpet():
    key = _room_key(6, "bedroom", "vacuum", 1, True, "standard")
    assert key == "6::bedroom::vacuum::1::1::standard::0"


def test_room_key_double_pass():
    key = _room_key(6, "hallway", "vacuum", 2, False, "boost")
    assert key == "6::hallway::vacuum::2::0::boost::0"


def test_room_key_none_slug():
    key = _room_key(6, None, "vacuum", 1, False)
    # None slug → empty string
    assert key.startswith("6::::vacuum")


def test_room_key_default_clean_intensity():
    key = _room_key(6, "office", "vacuum", 1, False)  # no intensity arg
    assert key.endswith("::standard::0")  # edge-mopping defaults to off


def test_room_key_edge_mopping():
    on = _room_key(6, "kitchen", "vacuum_mop", 2, False, "standard", True)
    off = _room_key(6, "kitchen", "vacuum_mop", 2, False, "standard", False)
    assert on.endswith("::1")
    assert off.endswith("::0")
    assert on != off


# ---------------------------------------------------------------------------
# clean_mode canonicalization (internal "vacuum and mop" == external "vacuum_mop")
# ---------------------------------------------------------------------------

def test_canonical_clean_mode_folds_combined_vocab():
    for raw in ("vacuum and mop", "Vacuum and Mop", "vacuum & mop", "VACUUM+MOP", "vac & mop"):
        assert _canonical_clean_mode(raw) == "vacuum_mop"


def test_canonical_clean_mode_passes_through_simple_modes():
    assert _canonical_clean_mode("vacuum") == "vacuum"
    assert _canonical_clean_mode("Mop") == "mop"
    assert _canonical_clean_mode("vacuum_mop") == "vacuum_mop"


def test_canonical_clean_mode_preserves_unknown_and_empty():
    assert _canonical_clean_mode("sweep") == "sweep"   # brand-specific mode preserved
    assert _canonical_clean_mode("") == ""
    assert _canonical_clean_mode(None) == ""


def test_room_key_merges_internal_and_external_mode_vocab():
    # Internal job records store the display string ("vacuum and mop"); external
    # app-started runs use the canonical token ("vacuum_mop"). Identical physical
    # settings must collapse to ONE learning key so they share a bucket.
    internal = _room_key(6, "kitchen", "vacuum and mop", 2, False, "narrow", True)
    external = _room_key(6, "kitchen", "vacuum_mop", 2, False, "narrow", True)
    assert internal == external
    assert "::vacuum_mop::" in internal


# ---------------------------------------------------------------------------
# _room_baseline_key
# ---------------------------------------------------------------------------

def test_room_baseline_key():
    assert _room_baseline_key(6, "kitchen") == "6::kitchen"


def test_room_baseline_key_none_slug():
    assert _room_baseline_key(6, None) == "6::"


# ---------------------------------------------------------------------------
# _stddev
# ---------------------------------------------------------------------------

def test_stddev_zero_for_single_value():
    assert _stddev([5.0]) == 0.0


def test_stddev_zero_for_empty():
    assert _stddev([]) == 0.0


def test_stddev_known_population():
    # population stddev of [2, 4, 4, 4, 5, 5, 7, 9] = 2.0
    result = _stddev([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
    assert result == pytest.approx(2.0, abs=0.001)


def test_stddev_uniform_values():
    assert _stddev([10.0, 10.0, 10.0]) == 0.0


# ---------------------------------------------------------------------------
# build_job_stats_payload
# ---------------------------------------------------------------------------

def test_build_job_stats_empty_jobs(tmp_path):
    rebuilder = _make_rebuilder(tmp_path)
    payload = rebuilder.build_job_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=[]
    )
    stats = payload["job_stats"]
    assert stats["total_jobs"] == 0
    assert stats["avg_duration_minutes"] == 0.0


def test_build_job_stats_single_job(tmp_path):
    rebuilder = _make_rebuilder(tmp_path)
    jobs = [_job(duration_minutes=30.0, battery_used=25.0)]
    payload = rebuilder.build_job_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=jobs
    )
    stats = payload["job_stats"]
    assert stats["total_jobs"] == 1
    assert stats["avg_duration_minutes"] == 30.0
    assert stats["avg_battery_used"] == 25.0
    assert stats["min_duration_minutes"] == 30.0
    assert stats["max_duration_minutes"] == 30.0


def test_build_job_stats_multiple_jobs_averages(tmp_path):
    rebuilder = _make_rebuilder(tmp_path)
    jobs = [
        _job(job_id="j1", duration_minutes=20.0, battery_used=20.0),
        _job(job_id="j2", duration_minutes=40.0, battery_used=30.0),
    ]
    payload = rebuilder.build_job_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=jobs
    )
    stats = payload["job_stats"]
    assert stats["avg_duration_minutes"] == 30.0
    assert stats["avg_battery_used"] == 25.0
    assert stats["min_duration_minutes"] == 20.0
    assert stats["max_duration_minutes"] == 40.0


def test_build_job_stats_latest_job_at(tmp_path):
    rebuilder = _make_rebuilder(tmp_path)
    j1 = _job(job_id="j1", ended_at="2026-01-01T09:30:00+00:00")
    j2 = _job(job_id="j2", ended_at="2026-01-02T10:00:00+00:00")
    payload = rebuilder.build_job_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=[j1, j2]
    )
    assert payload["job_stats"]["latest_job_ended_at"] == "2026-01-02T10:00:00+00:00"


def test_build_job_stats_schema_version(tmp_path):
    rebuilder = _make_rebuilder(tmp_path)
    payload = rebuilder.build_job_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=[]
    )
    assert payload["schema_version"] == 4


# ---------------------------------------------------------------------------
# build_room_stats_payload
# ---------------------------------------------------------------------------

def test_build_room_stats_empty_jobs(tmp_path):
    rebuilder = _make_rebuilder(tmp_path)
    payload = rebuilder.build_room_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=[]
    )
    assert payload["room_stats"] == []
    assert payload["room_baselines"] == []


def test_build_room_stats_single_room(tmp_path):
    rebuilder = _make_rebuilder(tmp_path)
    jobs = [_job(duration_minutes=30.0, room_slugs=["kitchen"])]
    payload = rebuilder.build_room_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=jobs
    )
    assert len(payload["room_stats"]) == 1
    entry = payload["room_stats"][0]
    assert entry["room_slug"] == "kitchen"
    assert entry["sample_count"] == 1
    assert entry["avg_minutes"] == 30.0  # single room → full duration
    assert entry["minutes_stddev"] == 0.0  # single sample → 0 stddev


def test_build_room_stats_preserves_three_passes_roborock(tmp_path):
    """A 3-pass run (Roborock supports 1-3 passes) keeps clean_times=3 -- it is
    NOT clamped to 1 by the old Eufy-centric `not in (1, 2)` guard, which would
    have collapsed it into the 1-pass bucket AND desynced from utils._room_key
    (the estimator's lookup key, lower-bound-only)."""
    rebuilder = _make_rebuilder(tmp_path)
    jobs = [_job(room_slugs=["kitchen"], clean_times=3)]
    payload = rebuilder.build_room_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=jobs
    )
    assert payload["room_stats"][0]["clean_times"] == 3
    # the per-room baseline breaks the run out under the "3" pass bucket, not "1"
    assert "3" in payload["room_baselines"][0]["by_clean_times"]


def test_build_room_stats_two_rooms(tmp_path):
    rebuilder = _make_rebuilder(tmp_path)
    jobs = [_job(duration_minutes=60.0, room_slugs=["kitchen", "bedroom"])]
    payload = rebuilder.build_room_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=jobs
    )
    entries = {e["room_slug"]: e for e in payload["room_stats"]}
    assert "kitchen" in entries
    assert "bedroom" in entries
    # 60 min / 2 rooms = 30 per room
    assert entries["kitchen"]["avg_minutes"] == 30.0
    assert entries["bedroom"]["avg_minutes"] == 30.0


def test_build_room_stats_accumulates_samples(tmp_path):
    rebuilder = _make_rebuilder(tmp_path)
    jobs = [
        _job(job_id="j1", duration_minutes=20.0, room_slugs=["kitchen"]),
        _job(job_id="j2", duration_minutes=40.0, room_slugs=["kitchen"]),
    ]
    payload = rebuilder.build_room_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=jobs
    )
    entry = payload["room_stats"][0]
    assert entry["sample_count"] == 2
    assert entry["avg_minutes"] == 30.0  # (20+40)/2
    assert entry["minutes_min"] == 20.0
    assert entry["minutes_max"] == 40.0


def test_build_room_stats_merges_internal_and_external_mode_vocab(tmp_path):
    # Internal records store "vacuum and mop"; external app-started runs store the
    # canonical "vacuum_mop". With identical settings they must share ONE bucket
    # instead of splitting on the vocabulary artifact.
    rebuilder = _make_rebuilder(tmp_path)
    jobs = [
        _job(job_id="internal", clean_mode="vacuum and mop", duration_minutes=20.0),
        _job(job_id="external", clean_mode="vacuum_mop", duration_minutes=40.0),
    ]
    payload = rebuilder.build_room_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=jobs
    )
    kitchen = [e for e in payload["room_stats"] if e["room_slug"] == "kitchen"]
    assert len(kitchen) == 1  # merged, not split by mode vocabulary
    assert kitchen[0]["effective_mode"] == "vacuum_mop"
    assert kitchen[0]["sample_count"] == 2


def test_build_room_stats_baseline_accumulates_across_modes(tmp_path):
    """Room baselines aggregate across different modes for the same slug."""
    rebuilder = _make_rebuilder(tmp_path)
    j1 = _job(job_id="j1", room_slugs=["kitchen"])
    j2 = _job(job_id="j2", room_slugs=["kitchen"])
    # Change mode on second job
    j2["job_profile"]["rooms"][0]["clean_mode"] = "vacuum_mop"
    payload = rebuilder.build_room_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=[j1, j2]
    )
    assert len(payload["room_baselines"]) == 1
    assert payload["room_baselines"][0]["sample_count"] == 2


def test_build_room_stats_schema_version(tmp_path):
    rebuilder = _make_rebuilder(tmp_path)
    payload = rebuilder.build_room_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=[]
    )
    assert payload["schema_version"] == 6


def test_build_room_stats_area_single_room(tmp_path):
    """A single-room job's cleaning_area_m2 becomes the room's area sample."""
    rebuilder = _make_rebuilder(tmp_path)
    jobs = [_job(room_slugs=["kitchen"], cleaning_area_m2=4.0)]
    payload = rebuilder.build_room_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=jobs
    )
    entry = payload["room_stats"][0]
    assert entry["area_sample_count"] == 1
    assert entry["avg_area_m2"] == 4.0
    assert entry["area_m2_min"] == 4.0
    assert entry["area_m2_max"] == 4.0
    baseline = payload["room_baselines"][0]
    assert baseline["avg_area_m2"] == 4.0
    assert baseline["area_sample_count"] == 1


def test_build_room_stats_area_averages(tmp_path):
    """Area averages across single-room jobs for the same room."""
    rebuilder = _make_rebuilder(tmp_path)
    jobs = [
        _job(job_id="j1", room_slugs=["kitchen"], cleaning_area_m2=3.0),
        _job(job_id="j2", room_slugs=["kitchen"], cleaning_area_m2=5.0),
    ]
    payload = rebuilder.build_room_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=jobs
    )
    entry = payload["room_stats"][0]
    assert entry["area_sample_count"] == 2
    assert entry["avg_area_m2"] == 4.0
    assert entry["area_m2_min"] == 3.0
    assert entry["area_m2_max"] == 5.0


def test_build_room_stats_area_excludes_multiroom(tmp_path):
    """Multi-room jobs are excluded from area stats (no per-room area split)."""
    rebuilder = _make_rebuilder(tmp_path)
    jobs = [_job(room_slugs=["kitchen", "bedroom"], cleaning_area_m2=10.0)]
    payload = rebuilder.build_room_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=jobs
    )
    for entry in payload["room_stats"]:
        assert entry["area_sample_count"] == 0
        assert entry["avg_area_m2"] == 0.0
    for baseline in payload["room_baselines"]:
        assert baseline["area_sample_count"] == 0
        assert baseline["avg_area_m2"] == 0.0


def test_build_room_stats_area_absent_when_unrecorded(tmp_path):
    """A single-room job with no cleaning_area_m2 contributes no area sample."""
    rebuilder = _make_rebuilder(tmp_path)
    jobs = [_job(room_slugs=["kitchen"])]  # cleaning_area_m2 omitted
    payload = rebuilder.build_room_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=jobs
    )
    entry = payload["room_stats"][0]
    assert entry["area_sample_count"] == 0
    assert entry["avg_area_m2"] == 0.0


def test_build_room_stats_buckets_by_passes(tmp_path):
    """room_baselines breaks the average out by pass count, keeping the full mean."""
    rebuilder = _make_rebuilder(tmp_path)
    jobs = [
        _job(job_id="j1", room_slugs=["kitchen"], duration_minutes=10.0, clean_times=1),
        _job(job_id="j2", room_slugs=["kitchen"], duration_minutes=20.0, clean_times=2),
        _job(job_id="j3", room_slugs=["kitchen"], duration_minutes=22.0, clean_times=2),
    ]
    payload = rebuilder.build_room_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=jobs
    )
    baseline = payload["room_baselines"][0]
    assert baseline["avg_minutes"] == round((10.0 + 20.0 + 22.0) / 3, 2)  # full mean kept
    by_passes = baseline["by_clean_times"]
    assert by_passes["1"]["sample_count"] == 1
    assert by_passes["1"]["avg_minutes"] == 10.0
    assert by_passes["2"]["sample_count"] == 2
    assert by_passes["2"]["avg_minutes"] == 21.0
    # variance band on the bucket (population stddev of [20, 22] = 1.0)
    assert by_passes["2"]["minutes_min"] == 20.0
    assert by_passes["2"]["minutes_max"] == 22.0
    assert by_passes["2"]["minutes_stddev"] == 1.0


def test_build_room_stats_buckets_by_edge_mopping(tmp_path):
    """room_baselines breaks the average out by edge-mopping on/off."""
    rebuilder = _make_rebuilder(tmp_path)
    jobs = [
        _job(job_id="j1", room_slugs=["kitchen"], duration_minutes=8.0, edge_mopping=False),
        _job(job_id="j2", room_slugs=["kitchen"], duration_minutes=12.0, edge_mopping=True),
    ]
    payload = rebuilder.build_room_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=jobs
    )
    by_edge = payload["room_baselines"][0]["by_edge_mopping"]
    assert by_edge["off"]["sample_count"] == 1
    assert by_edge["off"]["avg_minutes"] == 8.0
    assert by_edge["on"]["sample_count"] == 1
    assert by_edge["on"]["avg_minutes"] == 12.0


def test_build_room_stats_edge_splits_exact_buckets(tmp_path):
    """Edge-on and edge-off runs of the same room+settings become separate exact entries."""
    rebuilder = _make_rebuilder(tmp_path)
    jobs = [
        _job(job_id="j1", room_slugs=["kitchen"], duration_minutes=8.0, clean_times=2, edge_mopping=False),
        _job(job_id="j2", room_slugs=["kitchen"], duration_minutes=12.0, clean_times=2, edge_mopping=True),
    ]
    payload = rebuilder.build_room_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=jobs
    )
    entries = payload["room_stats"]
    assert len(entries) == 2  # split by edge_mopping in the exact key
    by_edge = {bool(e["edge_mopping"]): e for e in entries}
    assert by_edge[False]["avg_minutes"] == 8.0
    assert by_edge[True]["avg_minutes"] == 12.0


# ---------------------------------------------------------------------------
# rebuild_all
# ---------------------------------------------------------------------------

def test_rebuild_all_creates_files(tmp_path):
    rebuilder = _make_rebuilder(tmp_path)
    # Seed two jobs into the store
    store = rebuilder.store
    for i in range(2):
        j = _job(job_id=f"j-{i:03}", duration_minutes=30.0)
        store.save_completed_job(
            vacuum_entity_id="vacuum.alfred", job_id=f"j-{i:03}", payload=j
        )
    result = rebuilder.rebuild_all(vacuum_entity_id="vacuum.alfred")
    assert result["job_files_found"] == 2
    assert result["learning_jobs_used"] == 2
    assert Path(result["job_stats_path"]).exists()
    assert Path(result["room_stats_path"]).exists()
    assert Path(result["jobs_index_path"]).exists()


def test_rebuild_all_excludes_cancelled_from_learning(tmp_path):
    rebuilder = _make_rebuilder(tmp_path)
    store = rebuilder.store
    good = _job(job_id="good", status="completed", used_for_learning=True)
    bad = _job(job_id="bad", status="cancelled", used_for_learning=False)
    store.save_completed_job(vacuum_entity_id="vacuum.alfred", job_id="good", payload=good)
    store.save_completed_job(vacuum_entity_id="vacuum.alfred", job_id="bad", payload=bad)
    result = rebuilder.rebuild_all(vacuum_entity_id="vacuum.alfred")
    assert result["job_files_found"] == 2
    assert result["learning_jobs_used"] == 1


def test_rebuild_all_with_csv(tmp_path):
    rebuilder = _make_rebuilder(tmp_path)
    store = rebuilder.store
    j = _job(job_id="j-001")
    store.save_completed_job(vacuum_entity_id="vacuum.alfred", job_id="j-001", payload=j)
    result = rebuilder.rebuild_all(vacuum_entity_id="vacuum.alfred", rebuild_csv=True)
    assert result["csv"] is not None
    assert result["csv"]["job_rows_written"] == 1


def test_derive_water_allocations_skips_bad_entries(tmp_path):
    """Per-room water allocation skips non-dict/no-slug entries, keeps valid ones."""
    rb = _make_rebuilder(tmp_path)
    job = {"water": {
        "estimated_robot_water_used_ml": 100.0,
        "estimated_dock_wash_water_used_ml": 20.0,
        "estimated_dock_refill_water_used_ml": 0.0,
        "rooms": [
            "not-a-dict",                                  # skipped
            {"estimated_robot_water_used_ml": 50.0},        # no slug → skipped
            {"slug": "Kitchen", "estimated_robot_water_used_ml": 60.0,
             "mop_active": True},
        ],
    }}
    rooms = [{"slug": "kitchen", "clean_mode": "vacuum_mop", "water_level": "high"}]
    per_room, _job_level = rb._derive_room_water_allocations(job=job, rooms=rooms)
    assert per_room["kitchen"]["robot_water_used_ml"] == pytest.approx(60.0)


def test_derive_water_allocations_robot_fallback(tmp_path):
    """No explicit per-room robot water → split the job total across mop rooms."""
    rb = _make_rebuilder(tmp_path)
    job = {"water": {"estimated_robot_water_used_ml": 100.0, "rooms": []}}
    rooms = [
        {"slug": "kitchen", "clean_mode": "vacuum_mop", "water_level": "high"},
        {"slug": "bath", "clean_mode": "vacuum_mop", "water_level": "low"},
    ]
    per_room, _job_level = rb._derive_room_water_allocations(job=job, rooms=rooms)
    assert per_room["kitchen"]["robot_water_used_ml"] == pytest.approx(50.0)
    assert per_room["bath"]["robot_water_used_ml"] == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# transit aggregation (transit_stats / access_graph_edges / ingress-egress)
# ---------------------------------------------------------------------------

def _transition(from_id=1, to_id=2, from_slug="kitchen", to_slug="bath", secs=120):
    return {"from_room_id": from_id, "to_room_id": to_id, "from_slug": from_slug,
            "to_slug": to_slug, "transit_seconds": secs}


def test_build_room_stats_transit_per_pair(tmp_path):
    """transit_stats + access_graph_edges aggregate per room-pair from valid captures."""
    rb = _make_rebuilder(tmp_path)
    jobs = [
        _job(job_id="j1", room_slugs=["kitchen", "bath"], duration_minutes=20.0,
             transit_capture_valid=True, transitions=[_transition(secs=120)]),
        _job(job_id="j2", room_slugs=["kitchen", "bath"], duration_minutes=20.0,
             transit_capture_valid=True, transitions=[_transition(secs=180)]),
    ]
    payload = rb.build_room_stats_payload(vacuum_entity_id="vacuum.alfred", jobs=jobs)
    assert len(payload["transit_stats"]) == 1
    ts = payload["transit_stats"][0]
    assert ts["from_room_id"] == 1 and ts["to_room_id"] == 2
    assert ts["sample_count"] == 2
    assert ts["avg_seconds"] == 150.0   # (120 + 180) / 2
    edge = payload["access_graph_edges"][0]
    assert edge["sample_count"] == 2
    assert edge["transit_minutes_mean"] == pytest.approx(2.5)   # 150s / 60


def test_build_room_stats_transit_excludes_invalid(tmp_path):
    """transit_capture_valid=False jobs contribute no transit aggregate."""
    rb = _make_rebuilder(tmp_path)
    jobs = [_job(job_id="j1", room_slugs=["kitchen", "bath"],
                 transit_capture_valid=False, transitions=[_transition()])]
    payload = rb.build_room_stats_payload(vacuum_entity_id="vacuum.alfred", jobs=jobs)
    assert payload["transit_stats"] == []
    assert payload["access_graph_edges"] == []


def test_build_room_stats_ingress_egress_baselines(tmp_path):
    """room_baselines carry ingress (into) + egress (out of) transit bands."""
    rb = _make_rebuilder(tmp_path)
    jobs = [_job(job_id="j1", room_slugs=["kitchen", "bath"],
                 transit_capture_valid=True, transitions=[_transition(secs=120)])]
    payload = rb.build_room_stats_payload(vacuum_entity_id="vacuum.alfred", jobs=jobs)
    baselines = {b["room_slug"]: b for b in payload["room_baselines"]}
    # bath is the destination -> ingress; kitchen is the origin -> egress
    assert baselines["bath"]["ingress_sample_count"] == 1
    assert baselines["bath"]["avg_ingress_transit_seconds"] == 120.0
    assert baselines["kitchen"]["egress_sample_count"] == 1
    assert baselines["kitchen"]["avg_egress_transit_seconds"] == 120.0


# ---------------------------------------------------------------------------
# overhead aggregation (job_stats)
# ---------------------------------------------------------------------------

def test_build_job_stats_overhead_from_block(tmp_path):
    """job_stats aggregates overhead_observed.total_overhead_minutes + components."""
    rb = _make_rebuilder(tmp_path)
    jobs = [
        _job(job_id="j1", duration_minutes=30.0,
             overhead_observed={"total_overhead_minutes": 10.0, "entry_minutes": 1.0,
                                "inter_room_minutes": 2.0, "return_minutes": 1.5,
                                "recharge_minutes": 0.0, "wash_minutes": None}),
        _job(job_id="j2", duration_minutes=30.0,
             overhead_observed={"total_overhead_minutes": 6.0, "entry_minutes": None,
                                "inter_room_minutes": None, "return_minutes": 1.0,
                                "recharge_minutes": 0.0, "wash_minutes": None}),
    ]
    stats = rb.build_job_stats_payload(vacuum_entity_id="vacuum.alfred", jobs=jobs)["job_stats"]
    assert stats["avg_overhead_minutes"] == 8.0   # (10 + 6) / 2
    assert stats["overhead_sample_count"] == 2
    # entry/inter_room present on only one job -> averaged over the present samples
    assert stats["avg_overhead_entry_minutes"] == 1.0
    assert stats["overhead_inter_room_sample_count"] == 1


def test_build_job_stats_overhead_derived_when_absent(tmp_path):
    """Historical jobs without overhead_observed get it derived from job fields."""
    rb = _make_rebuilder(tmp_path)
    # duration 30, cleaning 20 min -> overhead 10 (no overhead_observed block)
    jobs = [_job(job_id="j1", duration_minutes=30.0, cleaning_time_seconds=1200)]
    stats = rb.build_job_stats_payload(vacuum_entity_id="vacuum.alfred", jobs=jobs)["job_stats"]
    assert stats["avg_overhead_minutes"] == 10.0


# ---------------------------------------------------------------------------
# Wave 3 — per-room area for multi-room jobs + area-quality gate
# ---------------------------------------------------------------------------

def test_build_room_stats_multiroom_per_room_area(tmp_path):
    """Multi-room jobs now contribute exact per-room area + wall-time via
    room_timings (was excluded before — equal-splitting would corrupt area)."""
    rb = _make_rebuilder(tmp_path)
    rt = [
        {"room_id": 1, "area_m2": 6.0, "cleaning_wall_seconds": 240},
        {"room_id": 2, "area_m2": 2.0, "cleaning_wall_seconds": 90},
    ]
    jobs = [_job(room_slugs=["kitchen", "bath"], duration_minutes=20.0,
                 transit_capture_valid=True, room_timings=rt)]
    payload = rb.build_room_stats_payload(vacuum_entity_id="vacuum.alfred", jobs=jobs)
    entries = {e["room_slug"]: e for e in payload["room_stats"]}
    assert entries["kitchen"]["area_sample_count"] == 1
    assert entries["kitchen"]["avg_area_m2"] == 6.0
    assert entries["bath"]["avg_area_m2"] == 2.0
    # per-room wall-time becomes the minutes sample (240s=4min, 90s=1.5min)
    assert entries["kitchen"]["avg_minutes"] == 4.0
    assert entries["bath"]["avg_minutes"] == 1.5


def test_build_room_stats_area_gate_excludes_partial(tmp_path):
    """A partial clean (area far below the room's median) is dropped from the
    TIMING stats; area / sample_count keep all samples."""
    rb = _make_rebuilder(tmp_path)
    jobs = []
    for i in range(4):  # 4 full Kitchen cleans: 6 m², 240 s
        jobs.append(_job(job_id=f"full{i}", room_slugs=["kitchen"],
                         transit_capture_valid=True,
                         room_timings=[{"room_id": 1, "area_m2": 6.0,
                                        "cleaning_wall_seconds": 240}]))
    jobs.append(_job(job_id="partial", room_slugs=["kitchen"],  # 1 partial: 2 m², 60 s
                     transit_capture_valid=True,
                     room_timings=[{"room_id": 1, "area_m2": 2.0,
                                    "cleaning_wall_seconds": 60}]))
    payload = rb.build_room_stats_payload(vacuum_entity_id="vacuum.alfred", jobs=jobs)
    entry = payload["room_stats"][0]
    assert entry["sample_count"] == 5            # all cleans counted
    assert entry["area_sample_count"] == 5       # area keeps all samples
    assert entry["partial_excluded_count"] == 1  # the 2 m² partial is gated
    assert entry["timing_sample_count"] == 4
    assert entry["avg_minutes"] == 4.0           # 240 s; the partial's 60 s excluded
