"""Unit tests for learning/stats_rebuilder.py — pure helpers + stats builders."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.learning.stats_rebuilder import (
    LearningStatsRebuilder,
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
) -> dict:
    if room_slugs is None:
        room_slugs = ["kitchen"]
    rooms = [
        {
            "slug": slug,
            "room_id": i + 1,
            "name": slug.title(),
            "clean_mode": "vacuum",
            "clean_intensity": "standard",
            "clean_times": 1,
            "is_carpet": False,
        }
        for i, slug in enumerate(room_slugs)
    ]
    return {
        "record_type": "completed_job",
        "job_id": job_id,
        "job": {
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_minutes": duration_minutes,
            "room_count": len(rooms),
        },
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
    assert key == "6::kitchen::vacuum::1::0::standard"


def test_room_key_carpet():
    key = _room_key(6, "bedroom", "vacuum", 1, True, "standard")
    assert key == "6::bedroom::vacuum::1::1::standard"


def test_room_key_double_pass():
    key = _room_key(6, "hallway", "vacuum", 2, False, "boost")
    assert key == "6::hallway::vacuum::2::0::boost"


def test_room_key_none_slug():
    key = _room_key(6, None, "vacuum", 1, False)
    # None slug → empty string
    assert key.startswith("6::::vacuum")


def test_room_key_default_clean_intensity():
    key = _room_key(6, "office", "vacuum", 1, False)  # no intensity arg
    assert key.endswith("::standard")


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
    assert payload["schema_version"] == 3


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
    assert payload["schema_version"] == 3


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
