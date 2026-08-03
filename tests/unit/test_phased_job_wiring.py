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
# Children are named off the RUN's job_id, not the finalizer's placeholder.
_CHILD0 = "job_2026-08-02T18-00-00.phase0"
_CHILD2 = "job_2026-08-02T18-00-00.phase2"


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
    # A BARE MagicMock silently disables the wave-2 child split: finalize_from_inputs
    # returns a mock, `isinstance(result, dict)` is False, and _finalize_phase_as_child
    # bails returning None — so every "a clean phase has no child" assertion passes for
    # the wrong reason and wave 2 goes completely unexercised. Stub the finalizer with
    # real dicts so the child path actually runs.
    def _collect(**kw):
        return {"active_job_state": {"job_id": "job_x", "phases": []}}

    def _finalize(*, inputs, **kw):
        state = inputs["active_job_state"]
        scoped = state.get("phases") or []
        seconds = sum(
            int(rt.get("cleaning_seconds") or 0)
            for p in scoped for rt in (p.get("room_timing") or [])
        )
        return {
            "completed_job": {
                "record_type": "completed_job",
                "job_id": state["job_id"],
                "job": {
                    "cleaning_time_seconds": seconds,
                    "cleaning_area_m2": state.get("last_cleaning_area_m2"),
                    "started_at": kw.get("started_at"),
                    "ended_at": kw.get("ended_at"),
                },
                "outcome": {"status": "completed", "used_for_learning": True},
                "queue": {"queue_room_ids": [
                    rt.get("room_id") for p in scoped
                    for rt in (p.get("room_timing") or [])
                ]},
            }
        }

    # Wire through the REAL accessor. `mgr.learning` was the original shape here and it
    # is not something the core manager has — a MagicMock manufactures any attribute you
    # ask for, so the tests passed while the live run silently wrote no children at all.
    # Attach to what production actually calls: _get_learning_manager().
    learning = MagicMock()
    learning.finalizer._collect_finalization_inputs = _collect
    learning.finalizer.finalize_from_inputs = _finalize
    learning.store = store
    mgr._get_learning_manager = lambda: learning
    # Prove the accessor is the real one: a manager WITHOUT it must not be silently
    # tolerated by a mock inventing the attribute.
    del mgr.learning
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


def test_every_phase_gets_its_own_record(store, runner):
    """Wave 2: the break gets a phase_break record and each CLEAN phase gets its own
    completed_job child. In wave 1 the clean phases correctly reported no child (the run
    still finalized as one merged record); that contract is what this wave reverses."""
    job = _job()
    _open(store, job)
    _run_all_phases(runner, job)
    slots = _slots(store)
    assert slots[0]["record_id"] == _CHILD0
    assert slots[1]["record_id"]                    # the break
    assert slots[2]["record_id"] == _CHILD2


def test_children_partition_the_run_instead_of_repeating_it(store, runner):
    """The defect this wave had to avoid. job_finalizer sums room_timing across EVERY
    phase on the active job, so an unscoped child would inherit its predecessors — the
    last one carrying the whole run's 1140 s while the others also claim theirs."""
    job = _job()
    job["phases"][0]["room_timing"] = [
        {"room_id": 5, "cleaning_seconds": 570, "cleaning_area_m2": 8.0}]
    job["phases"][2]["room_timing"] = [
        {"room_id": 8, "cleaning_seconds": 300, "cleaning_area_m2": 5.0},
        {"room_id": 4, "cleaning_seconds": 270, "cleaning_area_m2": 4.0}]
    _open(store, job)
    _run_all_phases(runner, job)
    kids = [
        store.load_completed_job(vacuum_entity_id=_VAC, job_id=f"job_2026-08-02T18-00-00.phase{i}")
        for i in (0, 2)
    ]
    secs = [k["job"]["cleaning_time_seconds"] for k in kids]
    assert secs == [570, 570], "a child inherited another phase's seconds"
    assert sum(secs) == 1140                        # the run, counted exactly once
    assert [k["job"]["cleaning_area_m2"] for k in kids] == [8.0, 9.0]


def test_child_is_distinguishable_from_a_standalone_run(store, runner):
    """A child that reads as an ordinary job lands in job-level averages as its own run.
    The stamp goes on the SAVED record — an unrecognised key on the input state is
    dropped when the payload is built."""
    job = _job()
    _open(store, job)
    _run_all_phases(runner, job)
    child = store.load_completed_job(vacuum_entity_id=_VAC, job_id=_CHILD0)
    assert child["phase_key"]["phased_job_id"] == _PJ
    assert child["phase_key"]["phase_index"] == 0


def test_child_finalize_is_idempotent(store, runner):
    """A pause+resume or an HA-restart re-arm must not write a second child."""
    job = _job()
    _open(store, job)
    _run_all_phases(runner, job)
    _run_all_phases(runner, job)
    jobs_dir = store.get_paths(vacuum_entity_id=_VAC).jobs_dir
    assert len(list(jobs_dir.glob("job_2026-08-02T18-00-00.phase*.json"))) == 2


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
    # Wave 2 fills these in: every clean phase now has a child, so nothing is unsplit
    # and the aggregate is real rather than a truthful zero.
    assert agg["unsplit_phases"] == []
    assert agg["missing_children"] == []
    assert closed["battery"]["used"] == 38


def test_no_boundary_invented_without_two_real_children(store, runner):
    """A boundary needs two adjacent clean children WITH timestamps. The stub child
    carries them, so this now exercises the real boundary maths: the 125 s hold is
    subtracted from the gap so only travel is learnable."""
    job = _job()
    _open(store, job)
    _run_all_phases(runner, job)
    closed = store.close_phased_job(
        vacuum_entity_id=_VAC, phased_job_id=_PJ,
        ended_at="2026-08-02T18:20:00+00:00", battery_end=62,
    )
    assert len(closed["boundaries"]) == 1
    b = closed["boundaries"][0]
    assert b["planned_hold_seconds"] == 125          # the wait's ACTUAL elapsed
    assert b["transit_seconds"] == b["seconds"] - 125


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


# --------------------------------------------------------------------------
# Hostile-probe repairs. Five of seven adversarial cases broke the wiring as
# first landed (74ce10c); each fix is pinned below. See _probe_wire_hostile.py.
# --------------------------------------------------------------------------


def test_production_finalize_path_reaches_the_parent_close():
    """H1, the serious one. The close hook first landed on the SYNC
    finalize_completed_job — which only tests call. Production goes
    async_finalize_completed_job -> _finalize_claimed -> finalize_from_inputs, so the
    parent would have stayed "running" on every real run while every test passed.

    A correct function with no live caller passes every suite; this asserts the caller.
    """
    import ast
    from pathlib import Path

    import custom_components.eufy_vacuum.learning.manager as lm_mod

    src = Path(lm_mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    bodies = {
        n.name: ast.get_source_segment(src, n) or ""
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    chain, seen, reaches = ["async_finalize_completed_job"], set(), False
    while chain:
        fn = chain.pop()
        if fn in seen:
            continue
        seen.add(fn)
        body = bodies.get(fn, "")
        if "_close_phased_job_parent" in body:
            reaches = True
        chain.extend(c for c in bodies if c != fn and f".{c}(" in body)
    assert reaches, "the production finalize path does not close the phased-job parent"


def test_closed_parent_has_no_null_outcomes(store, runner):
    """H3. outcome None is the SAME value a phase carries while in flight — on a closed
    parent nothing distinguishes "never ran" from "still going"."""
    job = _job()
    _open(store, job)
    job["current_phase_index"] = 0
    job["phases"][0]["_timing_end_t"] = "2026-08-02T18:09:00+00:00"
    runner._record_phase_to_parent(_VAC, _MAP, job)
    closed = store.close_phased_job(
        vacuum_entity_id=_VAC, phased_job_id=_PJ,
        ended_at="2026-08-02T18:10:00+00:00", battery_end=80,
    )
    assert all(p.get("outcome") for p in closed["phases"])
    assert closed["status"] == "partial"


def test_cancel_propagates_to_the_later_phases(store, runner):
    """H4 / Chris's directive 1. Sealed at CLOSE, not in the cancel path: the cancel path
    returns early by design (it owns finalization), so it never visits what it cancelled.
    """
    job = _job()
    _open(store, job)
    job["current_phase_index"] = 0
    job["phases"][0]["_timing_end_t"] = "2026-08-02T18:09:00+00:00"
    runner._record_phase_to_parent(_VAC, _MAP, job)
    closed = store.close_phased_job(
        vacuum_entity_id=_VAC, phased_job_id=_PJ,
        ended_at="2026-08-02T18:10:00+00:00", battery_end=80,
        ended_reason="cancelled",
    )
    slots = {p["index"]: p for p in closed["phases"]}
    assert slots[1]["outcome"] == "cancelled_upstream"
    assert slots[2]["outcome"] == "cancelled_upstream"


def test_interrupted_run_does_not_claim_the_user_cancelled_it(store, runner):
    """A restart-killed run reading "cancelled" is a false statement about who did what,
    and the two have different repair paths (resume vs re-plan)."""
    job = _job()
    _open(store, job)
    closed = store.close_phased_job(
        vacuum_entity_id=_VAC, phased_job_id=_PJ,
        ended_at="2026-08-02T18:10:00+00:00", battery_end=None,
        ended_reason="interrupted",
    )
    assert closed["status"] == "interrupted"


def test_no_orphan_break_record_when_the_parent_is_missing(store, runner):
    """H6. The parent open is best-effort, so it may be absent. A break record written
    anyway is referenced by nothing and accounted for by no close."""
    job = _job()  # deliberately NOT opened
    job["current_phase_index"] = 1
    job["phases"][1]["_timing_end_t"] = "2026-08-02T18:11:40+00:00"
    runner._record_phase_to_parent(_VAC, _MAP, job)
    phases_dir = store.get_paths(vacuum_entity_id=_VAC).phases_dir
    assert not list(phases_dir.glob("*.json"))


def test_reaper_closes_a_stranded_parent_and_spares_a_live_one():
    """H2. Writing the parent at RUN START was justified by it being reapable — but the
    reaper did not exist, so parents would have accumulated as "running" forever."""
    import tempfile
    from pathlib import Path

    from custom_components.eufy_vacuum.core.manager import EufyVacuumManager

    tmp = Path(tempfile.mkdtemp())
    hass = MagicMock()
    hass.config.config_dir = str(tmp)
    store = LearningHistoryStore(hass)
    for pj in ("pj_dead", "pj_live"):
        store.open_phased_job(
            vacuum_entity_id=_VAC, phased_job_id=pj, map_id=_MAP,
            started_at="2026-08-02T18:00:00+00:00", battery_start=100,
            planned_phases=[{"phase_type": "room_group", "queue_room_ids": [5]}],
            planned_estimate={}, planned_rooms=[],
        )
    fake = MagicMock()
    fake.hass = hass
    fake.data = {"active_jobs": {_VAC: {_MAP: {"phased_job_id": "pj_live"}}}}

    assert EufyVacuumManager._reap_stranded_phased_jobs(fake) == 1
    dead = store.load_phased_job(vacuum_entity_id=_VAC, phased_job_id="pj_dead")
    live = store.load_phased_job(vacuum_entity_id=_VAC, phased_job_id="pj_live")
    assert dead["status"] == "interrupted"
    assert all(p.get("outcome") for p in dead["phases"])
    assert live["status"] == "running", "the reaper killed a live run"


# --------------------------------------------------------------------------
# Live-run repairs. The FIRST real phased run wrote a correct parent and break
# record but no children at all, and a parent that knew none of its own rooms.
# Both passed every test beforehand. See _verify_phased_run.py.
# --------------------------------------------------------------------------


def test_missing_learning_manager_is_survived_not_crashed(store):
    """The learning manager comes from hass.data and can legitimately be absent
    (early startup, a failed setup). That must skip the child, not raise."""
    mgr = MagicMock()
    mgr.hass = store.hass
    mgr._get_learning_manager = lambda: None
    del mgr.learning
    runner = PhaseRunner(manager=mgr)
    job = _job()
    _open(store, job)
    job["current_phase_index"] = 0
    job["phases"][0]["_timing_end_t"] = "2026-08-02T18:09:35+00:00"
    runner._record_phase_to_parent(_VAC, _MAP, job)   # must not raise
    assert _slots(store)[0]["outcome"] == "completed"
    assert _slots(store)[0]["record_id"] is None


def test_parent_knows_the_rooms_it_planned(store):
    """The first live parent reported room_count 0 and empty planned_room_ids on a run
    that cleaned three rooms: the phases carry `resolved_rooms`, and only the BREAK
    phases carry `queue_room_ids` (set to [] defensively), so reading that key alone
    found nothing."""
    parent = store.open_phased_job(
        vacuum_entity_id=_VAC, phased_job_id="pj_rooms", map_id=_MAP,
        started_at="2026-08-02T18:00:00+00:00", battery_start=100,
        planned_phases=[
            # resolved_rooms only — the shape a real dispatch phase actually has
            {"phase_type": "room_group",
             "resolved_rooms": [{"room_id": 5, "clean_mode": "vacuum"}]},
            {"phase_type": "wait", "queue_room_ids": [], "resolved_rooms": []},
            {"phase_type": "room_group",
             "resolved_rooms": [{"room_id": 8}, {"room_id": 4}]},
        ],
        planned_estimate={}, planned_rooms=[],
    )
    assert parent["planned"]["room_count"] == 3
    assert parent["phases"][0]["planned_room_ids"] == [5]
    assert parent["phases"][2]["planned_room_ids"] == [8, 4]
    assert parent["phases"][1]["planned_room_ids"] == []


def test_cancel_distinguishes_the_phase_that_was_running(store, runner):
    """Hardware, pj_2026-08-02T17-38-07: a cancel during the kitchen sealed ALL THREE
    phases `cancelled_upstream`, so a kitchen that had run 92 s read identically to a
    phase that never dispatched. A cancelled run's one useful fact is how far it got."""
    job = _job()
    _open(store, job)
    closed = store.close_phased_job(
        vacuum_entity_id=_VAC, phased_job_id=_PJ,
        ended_at="2026-08-02T18:01:32+00:00", battery_end=99,
        ended_reason="cancelled", active_phase_index=0,
    )
    slots = {p["index"]: p for p in closed["phases"]}
    assert slots[0]["outcome"] == "cancelled"           # the user stopped THIS one
    assert slots[1]["outcome"] == "cancelled_upstream"  # never reached
    assert slots[2]["outcome"] == "cancelled_upstream"


def test_cancel_in_a_later_phase_leaves_finished_work_alone(store, runner):
    """A completed phase keeps its outcome — sealing must never overwrite real evidence."""
    job = _job()
    _open(store, job)
    job["current_phase_index"] = 0
    job["phases"][0]["_timing_end_t"] = "2026-08-02T18:09:35+00:00"
    runner._record_phase_to_parent(_VAC, _MAP, job)
    closed = store.close_phased_job(
        vacuum_entity_id=_VAC, phased_job_id=_PJ,
        ended_at="2026-08-02T18:15:00+00:00", battery_end=90,
        ended_reason="cancelled", active_phase_index=2,
    )
    slots = {p["index"]: p for p in closed["phases"]}
    assert slots[0]["outcome"] == "completed"           # untouched
    assert slots[1]["outcome"] == "cancelled_upstream"
    assert slots[2]["outcome"] == "cancelled"
    assert closed["status"] == "partial"                # some work survived
