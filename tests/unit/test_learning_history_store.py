"""Unit tests for learning/history_store.py — file-backed store + pure helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.learning.history_store import (
    LearningHistoryStore,
    _vacuum_slug,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store(tmp_path: Path) -> LearningHistoryStore:
    hass = MagicMock()
    hass.config.config_dir = str(tmp_path)
    return LearningHistoryStore(hass)


def _minimal_completed_job(
    *,
    job_id: str = "job-001",
    status: str = "completed",
    used_for_learning: bool = True,
    with_rooms: bool = True,
) -> dict:
    rooms = (
        [{"room_id": 1, "name": "Kitchen", "clean_mode": "vacuum"}]
        if with_rooms
        else []
    )
    return {
        "record_type": "completed_job",
        "job_id": job_id,
        "job": {"ended_at": "2026-01-01T10:00:00+00:00"},
        "job_profile": {"map_id": "6"},
        "resolved_rooms": rooms,
        "outcome": {
            "status": status,
            "used_for_learning": used_for_learning,
        },
    }


# ---------------------------------------------------------------------------
# _vacuum_slug
# ---------------------------------------------------------------------------

def test_vacuum_slug_strips_domain():
    assert _vacuum_slug("vacuum.alfred") == "alfred"


def test_vacuum_slug_no_dot_passthrough():
    assert _vacuum_slug("alfred") == "alfred"


def test_vacuum_slug_lowercases():
    assert _vacuum_slug("vacuum.Alfred") == "alfred"


def test_vacuum_slug_strips_whitespace():
    assert _vacuum_slug("  vacuum.alfred  ") == "alfred"


def test_vacuum_slug_multiple_dots():
    # Only splits on first dot — "alfred.pro" becomes "alfred.pro"
    assert _vacuum_slug("vacuum.alfred.pro") == "alfred.pro"


# ---------------------------------------------------------------------------
# get_paths / ensure_dirs
# ---------------------------------------------------------------------------

def test_get_paths_resolves_correctly(tmp_path):
    store = _make_store(tmp_path)
    paths = store.get_paths(vacuum_entity_id="vacuum.alfred")
    assert paths.root == tmp_path / "eufy_vacuum/learning/alfred"
    assert paths.jobs_dir == paths.root / "jobs"
    assert paths.learned_dir == paths.root / "learned"
    assert paths.exports_dir == paths.root / "exports"
    assert paths.live_dir == paths.root / "live"


def test_ensure_dirs_creates_all_subdirs(tmp_path):
    store = _make_store(tmp_path)
    paths = store.ensure_dirs(vacuum_entity_id="vacuum.alfred")
    assert paths.jobs_dir.is_dir()
    assert paths.learned_dir.is_dir()
    assert paths.exports_dir.is_dir()
    assert paths.live_dir.is_dir()


def test_ensure_dirs_idempotent(tmp_path):
    store = _make_store(tmp_path)
    store.ensure_dirs(vacuum_entity_id="vacuum.alfred")
    # Should not raise on second call
    store.ensure_dirs(vacuum_entity_id="vacuum.alfred")


# ---------------------------------------------------------------------------
# read_json / write_json
# ---------------------------------------------------------------------------

def test_write_and_read_json_roundtrip(tmp_path):
    store = _make_store(tmp_path)
    path = tmp_path / "test.json"
    payload = {"key": "value", "nums": [1, 2, 3]}
    store.write_json(path, payload)
    result = store.read_json(path)
    assert result == payload


def test_read_json_missing_file_returns_none(tmp_path):
    store = _make_store(tmp_path)
    result = store.read_json(tmp_path / "nonexistent.json")
    assert result is None


def test_read_json_empty_file_returns_none(tmp_path):
    store = _make_store(tmp_path)
    path = tmp_path / "empty.json"
    path.write_text("", encoding="utf-8")
    assert store.read_json(path) is None


def test_read_json_invalid_json_returns_none(tmp_path):
    store = _make_store(tmp_path)
    path = tmp_path / "bad.json"
    path.write_text("not json {{", encoding="utf-8")
    assert store.read_json(path) is None


def test_read_json_scalar_returns_none(tmp_path):
    """Top-level JSON scalars (number, string) are rejected."""
    store = _make_store(tmp_path)
    path = tmp_path / "scalar.json"
    path.write_text("42\n", encoding="utf-8")
    assert store.read_json(path) is None


def test_read_json_list_is_accepted(tmp_path):
    store = _make_store(tmp_path)
    path = tmp_path / "list.json"
    store.write_json(path, [1, 2, 3])
    result = store.read_json(path)
    assert result == [1, 2, 3]


def test_write_json_creates_parent_dirs(tmp_path):
    store = _make_store(tmp_path)
    deep = tmp_path / "a" / "b" / "c" / "data.json"
    store.write_json(deep, {"ok": True})
    assert deep.exists()


# ---------------------------------------------------------------------------
# append_csv_row / write_csv_rows
# ---------------------------------------------------------------------------

def test_append_csv_row_creates_with_header(tmp_path):
    store = _make_store(tmp_path)
    path = tmp_path / "out.csv"
    store.append_csv_row(path, ["col1", "col2"], ["val1", "val2"])
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "col1,col2"
    assert lines[1] == "val1,val2"


def test_append_csv_row_does_not_repeat_header(tmp_path):
    store = _make_store(tmp_path)
    path = tmp_path / "out.csv"
    store.append_csv_row(path, ["col1"], ["a"])
    store.append_csv_row(path, ["col1"], ["b"])
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines.count("col1") == 1
    assert "a" in lines
    assert "b" in lines


def test_write_csv_rows_replaces_existing(tmp_path):
    store = _make_store(tmp_path)
    path = tmp_path / "out.csv"
    store.append_csv_row(path, ["c"], ["old"])
    store.write_csv_rows(path, ["c"], [["new1"], ["new2"]])
    lines = path.read_text(encoding="utf-8").splitlines()
    assert "old" not in lines
    assert "new1" in lines
    assert "new2" in lines


# ---------------------------------------------------------------------------
# list_job_files
# ---------------------------------------------------------------------------

def test_list_job_files_returns_sorted(tmp_path):
    store = _make_store(tmp_path)
    paths = store.ensure_dirs(vacuum_entity_id="vacuum.alfred")
    (paths.jobs_dir / "c.json").write_text("{}", encoding="utf-8")
    (paths.jobs_dir / "a.json").write_text("{}", encoding="utf-8")
    (paths.jobs_dir / "b.json").write_text("{}", encoding="utf-8")
    files = store.list_job_files(vacuum_entity_id="vacuum.alfred")
    names = [f.name for f in files]
    assert names == ["a.json", "b.json", "c.json"]


def test_list_job_files_excludes_non_json(tmp_path):
    store = _make_store(tmp_path)
    paths = store.ensure_dirs(vacuum_entity_id="vacuum.alfred")
    (paths.jobs_dir / "job.json").write_text("{}", encoding="utf-8")
    (paths.jobs_dir / "notes.txt").write_text("ignore me", encoding="utf-8")
    files = store.list_job_files(vacuum_entity_id="vacuum.alfred")
    assert all(f.suffix == ".json" for f in files)
    assert len(files) == 1


def test_list_job_files_empty_dir(tmp_path):
    store = _make_store(tmp_path)
    files = store.list_job_files(vacuum_entity_id="vacuum.alfred")
    assert files == []


# ---------------------------------------------------------------------------
# save / load round-trips
# ---------------------------------------------------------------------------

def test_save_and_load_completed_job(tmp_path):
    store = _make_store(tmp_path)
    job = _minimal_completed_job(job_id="j42")
    store.save_completed_job(vacuum_entity_id="vacuum.alfred", job_id="j42", payload=job)
    loaded = store.load_completed_job(vacuum_entity_id="vacuum.alfred", job_id="j42")
    assert loaded == job


def test_load_completed_job_missing_returns_none(tmp_path):
    store = _make_store(tmp_path)
    result = store.load_completed_job(vacuum_entity_id="vacuum.alfred", job_id="ghost")
    assert result is None


def test_load_all_completed_jobs_returns_all(tmp_path):
    store = _make_store(tmp_path)
    for i in range(3):
        job = _minimal_completed_job(job_id=f"job-{i:03}")
        store.save_completed_job(
            vacuum_entity_id="vacuum.alfred", job_id=f"job-{i:03}", payload=job
        )
    jobs = store.load_all_completed_jobs(vacuum_entity_id="vacuum.alfred")
    assert len(jobs) == 3


def test_save_and_load_live_snapshot(tmp_path):
    store = _make_store(tmp_path)
    snap = {"status": "cleaning", "room": "kitchen"}
    store.save_live_snapshot(vacuum_entity_id="vacuum.alfred", snapshot=snap)
    loaded = store.load_live_snapshot(vacuum_entity_id="vacuum.alfred")
    assert loaded == snap


def test_load_live_snapshot_missing_returns_none(tmp_path):
    store = _make_store(tmp_path)
    assert store.load_live_snapshot(vacuum_entity_id="vacuum.alfred") is None


def test_save_and_load_incomplete_run(tmp_path):
    store = _make_store(tmp_path)
    payload = {"missed_rooms": [3, 5]}
    store.save_incomplete_run(vacuum_entity_id="vacuum.alfred", payload=payload)
    loaded = store.load_incomplete_run(vacuum_entity_id="vacuum.alfred")
    assert loaded == payload


def test_clear_incomplete_run_removes_file(tmp_path):
    store = _make_store(tmp_path)
    store.save_incomplete_run(vacuum_entity_id="vacuum.alfred", payload={"x": 1})
    store.clear_incomplete_run(vacuum_entity_id="vacuum.alfred")
    assert store.load_incomplete_run(vacuum_entity_id="vacuum.alfred") is None


def test_clear_incomplete_run_noop_when_missing(tmp_path):
    """Should not raise when the file doesn't exist."""
    store = _make_store(tmp_path)
    store.clear_incomplete_run(vacuum_entity_id="vacuum.alfred")  # no error


# ---------------------------------------------------------------------------
# is_learning_job
# ---------------------------------------------------------------------------

def test_is_learning_job_valid():
    job = _minimal_completed_job()
    store = LearningHistoryStore.__new__(LearningHistoryStore)
    assert store.is_learning_job(job) is True


def test_is_learning_job_wrong_record_type():
    store = LearningHistoryStore.__new__(LearningHistoryStore)
    job = _minimal_completed_job()
    job["record_type"] = "live_snapshot"
    assert store.is_learning_job(job) is False


def test_is_learning_job_cancelled():
    store = LearningHistoryStore.__new__(LearningHistoryStore)
    job = _minimal_completed_job(status="cancelled", used_for_learning=False)
    assert store.is_learning_job(job) is False


def test_is_learning_job_used_for_learning_false():
    store = LearningHistoryStore.__new__(LearningHistoryStore)
    job = _minimal_completed_job(used_for_learning=False)
    assert store.is_learning_job(job) is False


def test_is_learning_job_non_dict_returns_false():
    store = LearningHistoryStore.__new__(LearningHistoryStore)
    assert store.is_learning_job("not a dict") is False  # type: ignore[arg-type]


def test_is_learning_job_missing_outcome():
    store = LearningHistoryStore.__new__(LearningHistoryStore)
    job = _minimal_completed_job()
    del job["outcome"]
    assert store.is_learning_job(job) is False


# ---------------------------------------------------------------------------
# _build_jobs_index_entry
# ---------------------------------------------------------------------------

def test_build_jobs_index_entry_basic(tmp_path):
    store = _make_store(tmp_path)
    job = _minimal_completed_job(job_id="j-001")
    entry = store._build_jobs_index_entry(completed_job=job)
    assert entry is not None
    assert entry["job_id"] == "j-001"
    assert entry["map_id"] == "6"
    assert len(entry["rooms"]) == 1
    assert entry["rooms"][0]["room_id"] == 1
    assert entry["rooms"][0]["room_name"] == "Kitchen"


def test_build_jobs_index_entry_wrong_status_returns_none(tmp_path):
    store = _make_store(tmp_path)
    job = _minimal_completed_job(status="cancelled")
    entry = store._build_jobs_index_entry(completed_job=job)
    assert entry is None


def test_build_jobs_index_entry_wrong_record_type_returns_none(tmp_path):
    store = _make_store(tmp_path)
    job = _minimal_completed_job()
    job["record_type"] = "live_snapshot"
    entry = store._build_jobs_index_entry(completed_job=job)
    assert entry is None


def test_build_jobs_index_entry_no_ended_at_returns_none(tmp_path):
    store = _make_store(tmp_path)
    job = _minimal_completed_job()
    job["job"] = {}  # no ended_at
    entry = store._build_jobs_index_entry(completed_job=job)
    assert entry is None


def test_build_jobs_index_entry_mop_mode_sets_mopped_at(tmp_path):
    store = _make_store(tmp_path)
    job = _minimal_completed_job()
    job["resolved_rooms"] = [{"room_id": 2, "name": "Hallway", "clean_mode": "mop"}]
    entry = store._build_jobs_index_entry(completed_job=job)
    assert entry is not None
    room = entry["rooms"][0]
    assert room["last_mopped_at"] is not None
    assert room["last_vacuumed_at"] is None


def test_build_jobs_index_entry_vacuum_mop_mode_sets_both(tmp_path):
    store = _make_store(tmp_path)
    job = _minimal_completed_job()
    job["resolved_rooms"] = [{"room_id": 3, "name": "Office", "clean_mode": "vacuum_mop"}]
    entry = store._build_jobs_index_entry(completed_job=job)
    assert entry is not None
    room = entry["rooms"][0]
    assert room["last_vacuumed_at"] is not None
    assert room["last_mopped_at"] is not None


# ---------------------------------------------------------------------------
# rebuild_jobs_index_from_completed_jobs
# ---------------------------------------------------------------------------

def test_rebuild_jobs_index_creates_file(tmp_path):
    store = _make_store(tmp_path)
    jobs = [_minimal_completed_job(job_id=f"j-{i:03}") for i in range(3)]
    path = store.rebuild_jobs_index_from_completed_jobs(
        vacuum_entity_id="vacuum.alfred", completed_jobs=jobs
    )
    assert path.exists()
    index = json.loads(path.read_text(encoding="utf-8"))
    assert index["record_type"] == "jobs_index"
    assert index["job_count"] == 3


def test_rebuild_jobs_index_skips_non_completed(tmp_path):
    store = _make_store(tmp_path)
    jobs = [
        _minimal_completed_job(job_id="good"),
        _minimal_completed_job(job_id="bad", status="cancelled"),
    ]
    path = store.rebuild_jobs_index_from_completed_jobs(
        vacuum_entity_id="vacuum.alfred", completed_jobs=jobs
    )
    index = json.loads(path.read_text(encoding="utf-8"))
    assert index["job_count"] == 1
    assert index["jobs"][0]["job_id"] == "good"


def test_rebuild_jobs_index_sorted_by_ended_at(tmp_path):
    store = _make_store(tmp_path)
    j1 = _minimal_completed_job(job_id="first")
    j1["job"]["ended_at"] = "2026-01-01T08:00:00+00:00"
    j2 = _minimal_completed_job(job_id="second")
    j2["job"]["ended_at"] = "2026-01-02T08:00:00+00:00"
    # Pass in reverse order
    path = store.rebuild_jobs_index_from_completed_jobs(
        vacuum_entity_id="vacuum.alfred", completed_jobs=[j2, j1]
    )
    index = json.loads(path.read_text(encoding="utf-8"))
    assert index["jobs"][0]["job_id"] == "first"
    assert index["jobs"][1]["job_id"] == "second"


# ---------------------------------------------------------------------------
# update_jobs_index_with_completed_job
# ---------------------------------------------------------------------------

def test_update_jobs_index_appends_new_entry(tmp_path):
    store = _make_store(tmp_path)
    job = _minimal_completed_job(job_id="j-new")
    path = store.update_jobs_index_with_completed_job(
        vacuum_entity_id="vacuum.alfred", completed_job=job
    )
    assert path is not None
    index = store.load_jobs_index(vacuum_entity_id="vacuum.alfred")
    assert index["job_count"] == 1
    assert index["jobs"][0]["job_id"] == "j-new"


def test_update_jobs_index_replaces_existing_entry(tmp_path):
    store = _make_store(tmp_path)
    job = _minimal_completed_job(job_id="j-001")
    store.update_jobs_index_with_completed_job(
        vacuum_entity_id="vacuum.alfred", completed_job=job
    )
    # Update same job_id again
    job2 = _minimal_completed_job(job_id="j-001")
    job2["resolved_rooms"] = [{"room_id": 9, "name": "Patio", "clean_mode": "vacuum"}]
    store.update_jobs_index_with_completed_job(
        vacuum_entity_id="vacuum.alfred", completed_job=job2
    )
    index = store.load_jobs_index(vacuum_entity_id="vacuum.alfred")
    assert index["job_count"] == 1
    assert index["jobs"][0]["rooms"][0]["room_name"] == "Patio"


def test_update_jobs_index_returns_none_for_non_completed(tmp_path):
    store = _make_store(tmp_path)
    job = _minimal_completed_job(status="cancelled")
    result = store.update_jobs_index_with_completed_job(
        vacuum_entity_id="vacuum.alfred", completed_job=job
    )
    assert result is None


# ---------------------------------------------------------------------------
# build_completed_job_payload
# ---------------------------------------------------------------------------

def _make_build_args(**overrides) -> dict:
    base = dict(
        vacuum_entity_id="vacuum.alfred",
        job_id="j-build-001",
        started_at="2026-01-01T09:00:00+00:00",
        ended_at="2026-01-01T09:30:00+00:00",
        battery_start=85,
        battery_end=60,
        queue_state={
            "vacuum_entity_id": "vacuum.alfred",
            "map_id": 6,
            "room_count": 1,
            "queue_room_ids": [1],
            "queue_rooms": [],
        },
        payload_state={
            "resolved_rooms": [
                {"room_id": 1, "slug": "kitchen", "name": "Kitchen", "clean_mode": "vacuum"}
            ],
        },
        active_job_state={
            "map_id": 6,
            "room_count": 1,
            "queue_room_ids": [1],
            "queue_rooms": [],
            "resolved_rooms": [
                {"room_id": 1, "slug": "kitchen", "name": "Kitchen", "clean_mode": "vacuum"}
            ],
            "paused_duration_seconds": 0,
            "recharge_seconds_accumulated": 0,
        },
    )
    base.update(overrides)
    return base


def test_build_completed_job_payload_structure(tmp_path):
    store = _make_store(tmp_path)
    payload = store.build_completed_job_payload(**_make_build_args())
    assert payload["record_type"] == "completed_job"
    assert payload["schema_version"] == 1
    assert payload["job_id"] == "j-build-001"
    assert "job" in payload
    assert "battery" in payload
    assert "outcome" in payload


def test_build_completed_job_payload_duration(tmp_path):
    store = _make_store(tmp_path)
    payload = store.build_completed_job_payload(**_make_build_args())
    # 30 min wall clock, no pauses/recharges
    assert payload["job"]["wall_clock_duration_minutes"] == 30.0
    assert payload["job"]["duration_minutes"] == 30.0


def test_build_completed_job_payload_battery(tmp_path):
    store = _make_store(tmp_path)
    payload = store.build_completed_job_payload(**_make_build_args())
    assert payload["battery"]["start"] == 85
    assert payload["battery"]["end"] == 60
    assert payload["battery"]["used"] == 25


def test_build_completed_job_payload_used_for_learning(tmp_path):
    store = _make_store(tmp_path)
    payload = store.build_completed_job_payload(**_make_build_args())
    assert payload["outcome"]["used_for_learning"] is True
    assert payload["outcome"]["status"] == "completed"


def test_build_completed_job_payload_cancelled_blocks_learning(tmp_path):
    store = _make_store(tmp_path)
    payload = store.build_completed_job_payload(
        **_make_build_args(was_cancelled=True)
    )
    assert payload["outcome"]["used_for_learning"] is False
    assert payload["outcome"]["status"] == "cancelled"
    assert "job_cancelled" in payload["outcome"]["learning_blockers"]


def test_build_completed_job_payload_test_job_blocks_learning(tmp_path):
    store = _make_store(tmp_path)
    payload = store.build_completed_job_payload(**_make_build_args(is_test_job=True))
    assert payload["outcome"]["used_for_learning"] is False
    assert "test_job" in payload["outcome"]["learning_blockers"]


def test_build_completed_job_payload_vacuum_slug_in_name(tmp_path):
    store = _make_store(tmp_path)
    payload = store.build_completed_job_payload(**_make_build_args())
    assert payload["vacuum"]["name"] == "alfred"


def test_append_job_csv_row(tmp_path):
    """The jobs CSV export writes a header + the appended row."""
    store = _make_store(tmp_path)
    row = ["j1", "s", "e", "6", 2, 10, 90, 70, 20, "completed",
           True, True, "", "", 0, 0, 0, 0, 0]
    path = store.append_job_csv_row(vacuum_entity_id="vacuum.alfred", row=row)
    content = Path(path).read_text(encoding="utf-8")
    assert "job_id" in content        # header row written
    assert "j1" in content            # data row written


def test_append_room_csv_rows(tmp_path):
    """The rooms CSV export writes a header + each appended row."""
    store = _make_store(tmp_path)
    rows = [["j1", "s", "e", "6", "kitchen", 1, 1, "vacuum", "vacuum", 1,
             "Max", "Off", "Standard", False, False, 2, 10, 20, "completed",
             True, True, "", "", 5, 10, 0, 0]]
    path = store.append_room_csv_rows(vacuum_entity_id="vacuum.alfred", rows=rows)
    content = Path(path).read_text(encoding="utf-8")
    assert "room_slug" in content
    assert "kitchen" in content
