"""Phased Job WIRING — the advance path actually attaching phases to a parent.

test_phased_job_store.py pins the store in isolation. This pins the hook: driving the
real ``PhaseRunner._record_phase_to_parent`` over a realistic phased run, does a break
get the record it never had, and does the closed parent tell the truth about the phases
it cannot yet account for?

synthesis/DESIGN-phased-jobs.md wave 1. Kept from the pre-wiring probe.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.jobs.phase_runner import PhaseRunner
from custom_components.eufy_vacuum.learning.history_store import LearningHistoryStore

_VAC = "vacuum.alfred"
_MAP = "12"
_PJ = "pj_2026-08-02T18-00-00"


@pytest.fixture
def store(tmp_path):
    hass = MagicMock()
    # Roots off config_dir, NOT hass.config.path — mocking the wrong one lets a MagicMock
    # stringify into a RELATIVE path, so writes land in the repo and the assertion below
    # reports "no file". That is exactly how this suite's first run failed.
    hass.config.config_dir = str(tmp_path)
    return LearningHistoryStore(hass)


@pytest.fixture
def runner(store):
    mgr = MagicMock()
    mgr.hass = store.hass
    return PhaseRunner(manager=mgr)


def _job():
    """kitchen -> 2 min wait -> two-room group: the run that mis-taught Entryway."""
    return {
        "vacuum_entity_id": _VAC,
        "map_id": _MAP,
        "job_id": "job_2026-08-02T18-00-00",
        "phased_job_id": _PJ,
        "started_at": "2026-08-02T18:00:00+00:00",
        "current_phase_index": 0,
        "phases": [
            {"phase_type": "room_group", "queue_room_ids": [5],
             "resolved_rooms": [{"room_id": 5, "clean_mode": "vacuum"}], "room_count": 1},
            {"phase_type": "wait", "wait_minutes": 2, "queue_room_ids": [],
             "resolved_rooms": [], "room_count": 0},
            {"phase_type": "room_group", "queue_room_ids": [8, 4],
             "resolved_rooms": [{"room_id": 8, "clean_mode": "vacuum"},
                                {"room_id": 4, "clean_mode": "vacuum"}], "room_count": 2},
        ],
    }


def _open(store, job):
    return store.open_phased_job(
        vacuum_entity_id=_VAC, phased_job_id=_PJ, map_id=_MAP,
        started_at=job["started_at"], battery_start=100,
        planned_phases=job["phases"],
        planned_estimate={
            "total_minutes": 21.0, "job_eta_minutes": 21.0,
            "water_estimate": {"estimated_total_dock_clean_water_used_ml": 240.0},
        },
        planned_rooms=[{"room_id": 5, "clean_mode": "vacuum"}],
    )


def _run_all_phases(runner, job):
    """Advance through every phase the way the completion hook does."""
    ends = {
        0: "2026-08-02T18:09:35+00:00",
        1: "2026-08-02T18:11:40+00:00",  # 125 s actual against a 120 s plan
        2: "2026-08-02T18:20:00+00:00",
    }
    for idx, end_t in ends.items():
        job["current_phase_index"] = idx
        job["phases"][idx]["_timing_end_t"] = end_t
        runner._record_phase_to_parent(_VAC, _MAP, job)


def _slots(store):
    parent = store.load_phased_job(vacuum_entity_id=_VAC, phased_job_id=_PJ)
    return {p["index"]: p for p in (parent or {}).get("phases", [])}


def test_planned_counts_the_whole_run_not_the_first_phase(store):
    job = _job()
    parent = _open(store, job)
    assert parent["planned"]["room_count"] == 3


def test_every_phase_attaches_to_the_parent(store, runner):
    job = _job()
    _open(store, job)
    _run_all_phases(runner, job)
    assert sorted(_slots(store)) == [0, 1, 2]


def test_a_break_gets_a_record_a_clean_phase_does_not_yet(store, runner):
    """Wave 1's whole point. The wait is recorded; a clean phase truthfully reports no
    child, because the phased run still finalizes as ONE merged record."""
    job = _job()
    _open(store, job)
    _run_all_phases(runner, job)
    slots = _slots(store)
    assert slots[1]["record_id"]
    assert slots[0]["record_id"] is None
    assert slots[2]["record_id"] is None


def test_break_record_keeps_planned_and_actual_apart(store, runner, tmp_path):
    """A 2 min hold that actually ran 125 s is a different fact from the 120 s asked for.
    Collapsing them is how a planned pause became indistinguishable from travel time."""
    job = _job()
    _open(store, job)
    _run_all_phases(runner, job)
    rid = _slots(store)[1]["record_id"]
    path = store.get_paths(vacuum_entity_id=_VAC).phases_dir / f"{rid}.json"
    assert path.exists()
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert rec["record_type"] == "phase_break"
    assert "queue" not in rec  # never wears the completed_job schema
    assert rec["planned"]["hold_seconds"] == 120
    assert rec["actual"]["seconds"] == 125


def test_zero_minute_wait_is_a_plan_not_an_absent_one(store, runner):
    """Falsy-zero: `x or None` would turn a genuine 0-minute hold into "unplanned"."""
    job = _job()
    job["phases"][1]["wait_minutes"] = 0
    _open(store, job)
    _run_all_phases(runner, job)
    rid = _slots(store)[1]["record_id"]
    path = store.get_paths(vacuum_entity_id=_VAC).phases_dir / f"{rid}.json"
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert rec["planned"]["hold_seconds"] == 0


def test_clock_skew_cannot_produce_a_negative_hold(store, runner):
    """A negative hold would be subtracted from a boundary and teach negative travel."""
    job = _job()
    _open(store, job)
    job["current_phase_index"] = 0
    job["phases"][0]["_timing_end_t"] = "2026-08-02T18:09:35+00:00"
    runner._record_phase_to_parent(_VAC, _MAP, job)
    job["current_phase_index"] = 1
    job["phases"][1]["_timing_end_t"] = "2026-08-02T18:05:00+00:00"  # BEFORE phase 0 ended
    runner._record_phase_to_parent(_VAC, _MAP, job)
    rid = _slots(store)[1]["record_id"]
    path = store.get_paths(vacuum_entity_id=_VAC).phases_dir / f"{rid}.json"
    assert json.loads(path.read_text(encoding="utf-8"))["actual"]["seconds"] == 0


def test_closed_parent_names_the_phases_it_cannot_account_for(store, runner):
    """Without this the parent closes "completed" with 0 seconds and an EMPTY
    missing_children — the same record-that-lies A4 removed, through another door."""
    job = _job()
    _open(store, job)
    _run_all_phases(runner, job)
    closed = store.close_phased_job(
        vacuum_entity_id=_VAC, phased_job_id=_PJ,
        ended_at="2026-08-02T18:20:00+00:00", battery_end=62,
    )
    agg = closed["aggregate"]
    assert agg["unsplit_phases"] == [0, 2]
    assert agg["cleaning_time_seconds"] == 0
    assert agg["missing_children"] == []
    assert closed["battery"]["used"] == 38


def test_no_boundary_invented_without_two_real_children(store, runner):
    """A boundary needs two adjacent clean children. Until the split lands there are
    none, and inventing one would hand the estimator a fabricated transit."""
    job = _job()
    _open(store, job)
    _run_all_phases(runner, job)
    closed = store.close_phased_job(
        vacuum_entity_id=_VAC, phased_job_id=_PJ,
        ended_at="2026-08-02T18:20:00+00:00", battery_end=62,
    )
    assert closed["boundaries"] == []


def test_atomic_run_writes_nothing(store, runner, tmp_path):
    """Presence is the signal: no phased_job_id, no parent, no files."""
    before = {p.name for p in tmp_path.rglob("*.json")}
    runner._record_phase_to_parent(
        _VAC, _MAP,
        {"vacuum_entity_id": _VAC, "map_id": _MAP, "job_id": "job_x",
         "current_phase_index": 0, "phases": None},
    )
    assert {p.name for p in tmp_path.rglob("*.json")} == before


def test_a_store_failure_cannot_block_the_next_phase(store, runner, monkeypatch):
    """The parent is review telemetry. A run must keep cleaning without it."""
    job = _job()
    _open(store, job)
    monkeypatch.setattr(
        LearningHistoryStore, "save_phase_record",
        MagicMock(side_effect=OSError("disk full")),
    )
    job["current_phase_index"] = 1
    job["phases"][1]["_timing_end_t"] = "2026-08-02T18:11:40+00:00"
    runner._record_phase_to_parent(_VAC, _MAP, job)  # must not raise
