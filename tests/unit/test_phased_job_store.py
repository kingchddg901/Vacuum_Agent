"""Phased Job parent store — open at start, attach phases, close with boundaries.

synthesis/DESIGN-phased-jobs.md. The principle under test: "we stop losing good rooms
because we stop treating each phase as a special thing."
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.learning.history_store import LearningHistoryStore

_VAC = "vacuum.alfred"
_PJ = "pj_2026-08-02T11-15-51"


@pytest.fixture
def store(tmp_path):
    hass = MagicMock()
    hass.config.config_dir = str(tmp_path)
    return LearningHistoryStore(hass)


def _open(store, phases=None):
    return store.open_phased_job(
        vacuum_entity_id=_VAC, phased_job_id=_PJ, map_id="12",
        started_at="2026-08-02T18:15:51Z", battery_start=100,
        planned_phases=phases if phases is not None else [
            {"phase_type": "room_group", "queue_room_ids": [5]},
            {"phase_type": "wait"},
            {"phase_type": "room_group", "queue_room_ids": [8, 4]},
        ],
        learning_key="profile:vacuum.alfred:12:pid_7",
    )


def _child(store, job_id, started, ended, seconds, area, rooms):
    store.save_completed_job(
        vacuum_entity_id=_VAC, job_id=job_id,
        payload={
            "job_id": job_id,
            "job": {"started_at": started, "ended_at": ended,
                    "cleaning_time_seconds": seconds, "cleaning_area_m2": area,
                    "room_timings": [{"room_id": r, "cleaning_seconds": 60} for r in rooms]},
            "queue": {"completed_room_ids": rooms},
        },
    )


# ---------------------------------------------------------------------------
# Opened at START — audit H2
# ---------------------------------------------------------------------------

def test_parent_exists_before_any_phase_finishes(store):
    """H2: written at CLOSE, any abnormal end orphans children pointing at a parent that
    never existed. Written at START, an abnormal end leaves a findable `running` parent."""
    parent = _open(store)
    assert parent["status"] == "running"
    assert all(p["record_id"] is None for p in parent["phases"])
    on_disk = store.load_phased_job(vacuum_entity_id=_VAC, phased_job_id=_PJ)
    assert on_disk["phased_job_id"] == _PJ


def test_open_is_idempotent(store):
    """A restart mid-run re-opens; it must not wipe the phases already attached."""
    _open(store)
    store.record_phase_outcome(
        vacuum_entity_id=_VAC, phased_job_id=_PJ, phase_index=0,
        phase_type="room_group", outcome="completed", record_id="job_a",
    )
    again = _open(store)
    assert again["phases"][0]["record_id"] == "job_a"


def test_planned_phases_record_what_was_INTENDED(store):
    """A phase that never runs must still be visible. Absence is indistinguishable from
    'was never planned' — the ambiguity that made a user's 2-minute wait invisible."""
    parent = _open(store)
    assert [p["type"] for p in parent["phases"]] == ["room_group", "wait", "room_group"]
    assert [p["planned_room_ids"] for p in parent["phases"]] == [[5], [], [8, 4]]
    # A phase that has not run yet is PRESENT with a null outcome, never absent.
    assert all(p["outcome"] is None for p in parent["phases"])


# ---------------------------------------------------------------------------
# Attaching phases
# ---------------------------------------------------------------------------

def test_break_records_and_children_go_to_different_buckets(store):
    """A wait is not a job and must never land in `children` — that list feeds the
    aggregate, and a break contributes to wall-clock and nothing else."""
    _open(store)
    store.record_phase_outcome(vacuum_entity_id=_VAC, phased_job_id=_PJ, phase_index=0,
                               phase_type="room_group", outcome="completed", record_id="job_a")
    parent = store.record_phase_outcome(
        vacuum_entity_id=_VAC, phased_job_id=_PJ, phase_index=1,
        phase_type="wait", outcome="held", record_id="phase_w")
    by_type = {p["type"]: p for p in parent["phases"] if p["record_id"]}
    assert by_type["room_group"]["record_id"] == "job_a"
    assert by_type["wait"]["record_id"] == "phase_w"


def test_recording_the_same_phase_twice_does_not_duplicate(store):
    """Re-arm after a restart can replay a phase's completion."""
    _open(store)
    for _ in range(2):
        store.record_phase_outcome(
            vacuum_entity_id=_VAC, phased_job_id=_PJ, phase_index=0,
            phase_type="room_group", outcome="completed", record_id="job_a")
    parent = store.load_phased_job(vacuum_entity_id=_VAC, phased_job_id=_PJ)
    assert [p["record_id"] for p in parent["phases"]] == ["job_a", None, None]
    assert len(parent["phases"]) == 3   # the planned structure, not one row per report


# ---------------------------------------------------------------------------
# Closing — status is never collapsed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("outcomes,expected", [
    (["completed", "completed"], "completed"),
    (["completed", "cancelled"], "partial"),
    (["cancelled", "not_started"], "cancelled"),
    (["completed", "failed"], "failed"),
])
def test_status_summarises_but_the_phase_list_stays_authoritative(store, outcomes, expected):
    """The label is a summary; the per-phase list beside it is the truth. A run where the
    kitchen finished and the rest was cancelled must stay legible as exactly that.

    The plan is sized to the outcomes on purpose. A phase left unreported now shows up as
    a null outcome and drags the run to `partial` -- which is right, and is the shape
    working: an unfinished phase used to be invisible."""
    _open(store, [{"phase_type": "room_group", "queue_room_ids": [r]}
                  for r in range(len(outcomes))])
    for i, o in enumerate(outcomes):
        store.record_phase_outcome(
            vacuum_entity_id=_VAC, phased_job_id=_PJ, phase_index=i,
            phase_type="room_group", outcome=o, record_id=f"job_{i}")
    parent = store.close_phased_job(
        vacuum_entity_id=_VAC, phased_job_id=_PJ,
        ended_at="2026-08-02T18:36:51Z", battery_end=95)
    assert parent["status"] == expected
    assert [p["outcome"] for p in parent["phases"][:len(outcomes)]] == outcomes


def test_aggregate_sums_children_and_never_recomputes(store):
    """Children are the source of truth (H4); the aggregate is a cache over them."""
    _open(store)
    _child(store, "job_0", "2026-08-02T18:15:51Z", "2026-08-02T18:18:16Z", 120, 1.0, [5])
    _child(store, "job_2", "2026-08-02T18:21:41Z", "2026-08-02T18:35:21Z", 750, 7.0, [8, 4])
    for i, jid in ((0, "job_0"), (2, "job_2")):
        store.record_phase_outcome(vacuum_entity_id=_VAC, phased_job_id=_PJ, phase_index=i,
                                   phase_type="room_group", outcome="completed", record_id=jid)
    parent = store.close_phased_job(
        vacuum_entity_id=_VAC, phased_job_id=_PJ,
        ended_at="2026-08-02T18:36:51Z", battery_end=95)
    assert parent["aggregate"]["cleaning_time_seconds"] == 870
    assert parent["aggregate"]["cleaning_area_m2"] == 8.0
    assert sorted(parent["aggregate"]["rooms_cleaned"]) == [4, 5, 8]
    assert parent["battery"]["used"] == 5
    # The parent holds STRUCTURE and pointers; it does not restate the children.
    assert "children" not in parent and "phase_records" not in parent
    assert "phase_count" not in parent


# ---------------------------------------------------------------------------
# Boundaries — the whole point
# ---------------------------------------------------------------------------

def test_a_planned_hold_is_separated_from_real_transit(store):
    """THE payoff. alfred job_2026-08-02T11-15-51: 205s between kitchen and the group, of
    which 120s was a wait Chris chose. Folding the hold into overhead is how a FLAT
    three-room run learned it takes two minutes longer than it does."""
    _open(store)
    _child(store, "job_0", "2026-08-02T18:15:51Z", "2026-08-02T18:18:16Z", 120, 1.0, [5])
    _child(store, "job_2", "2026-08-02T18:21:41Z", "2026-08-02T18:35:21Z", 750, 7.0, [8, 4])
    store.save_phase_record(
        vacuum_entity_id=_VAC, record_id="phase_w",
        payload={"record_type": "phase_record", "phase_index": 1, "phase_type": "wait",
                 "planned": {"wait_minutes": 2}, "actual": {"seconds": 120},
                 "outcome": "held"})
    store.record_phase_outcome(vacuum_entity_id=_VAC, phased_job_id=_PJ, phase_index=0,
                               phase_type="room_group", outcome="completed", record_id="job_0")
    store.record_phase_outcome(vacuum_entity_id=_VAC, phased_job_id=_PJ, phase_index=1,
                               phase_type="wait", outcome="held", record_id="phase_w")
    store.record_phase_outcome(vacuum_entity_id=_VAC, phased_job_id=_PJ, phase_index=2,
                               phase_type="room_group", outcome="completed", record_id="job_2")
    parent = store.close_phased_job(
        vacuum_entity_id=_VAC, phased_job_id=_PJ,
        ended_at="2026-08-02T18:36:51Z", battery_end=95)

    assert len(parent["boundaries"]) == 1
    b = parent["boundaries"][0]
    assert b["seconds"] == 205            # 18:18:16 -> 18:21:41
    assert b["planned_hold_seconds"] == 120
    assert b["transit_seconds"] == 85     # the ONLY learnable part
    assert b["after_phase"] == 0


def test_transit_never_goes_negative(store):
    """Clock skew, or a hold that outran its own boundary, must not teach a negative
    travel time — the same class as a fault deducting more seconds than the run had."""
    _open(store)
    _child(store, "job_0", "2026-08-02T18:15:51Z", "2026-08-02T18:18:16Z", 120, 1.0, [5])
    _child(store, "job_2", "2026-08-02T18:18:36Z", "2026-08-02T18:35:21Z", 750, 7.0, [8])
    store.save_phase_record(
        vacuum_entity_id=_VAC, record_id="phase_w",
        payload={"phase_index": 1, "phase_type": "wait",
                 "actual": {"seconds": 9999}, "outcome": "held"})
    for i, t, rid in ((0, "room_group", "job_0"), (1, "wait", "phase_w"),
                      (2, "room_group", "job_2")):
        store.record_phase_outcome(vacuum_entity_id=_VAC, phased_job_id=_PJ,
                                   phase_index=i, phase_type=t, outcome="completed",
                                   record_id=rid)
    parent = store.close_phased_job(
        vacuum_entity_id=_VAC, phased_job_id=_PJ,
        ended_at="2026-08-02T18:36:51Z", battery_end=95)
    b = parent["boundaries"][0]
    assert b["transit_seconds"] == 0
    assert b["planned_hold_seconds"] <= b["seconds"]


def test_closing_an_unopened_parent_returns_none(store):
    """Never raise on a missing parent — a run must not die because its parent is gone."""
    assert store.close_phased_job(
        vacuum_entity_id=_VAC, phased_job_id="pj_nope",
        ended_at="2026-08-02T18:36:51Z", battery_end=95) is None


# ---------------------------------------------------------------------------
# What the run cleaned WITH
# ---------------------------------------------------------------------------

def _child_modes(store, job_id, by_mode=None, room_modes=None):
    job = {"started_at": "2026-08-02T18:15:51Z", "ended_at": "2026-08-02T18:18:16Z",
           "cleaning_time_seconds": 60, "cleaning_area_m2": 1.0, "room_timings": []}
    if by_mode is not None:
        job["battery_metrics"] = {"by_clean_mode": {m: {"share": 1.0} for m in by_mode}}
    payload = {"job_id": job_id, "job": job, "queue": {"completed_room_ids": []}}
    if room_modes is not None:
        payload["resolved_rooms"] = [{"room_id": i, "clean_mode": m}
                                     for i, m in enumerate(room_modes, start=1)]
    store.save_completed_job(vacuum_entity_id=_VAC, job_id=job_id, payload=payload)


def _close_with(store, children_spec):
    _open(store, [{"phase_type": "room_group", "queue_room_ids": []}
                  for _ in children_spec])
    for i, spec in enumerate(children_spec):
        _child_modes(store, f"job_{i}", **spec)
        store.record_phase_outcome(vacuum_entity_id=_VAC, phased_job_id=_PJ, phase_index=i,
                                   phase_type="room_group", outcome="completed",
                                   record_id=f"job_{i}")
    return store.close_phased_job(vacuum_entity_id=_VAC, phased_job_id=_PJ,
                                  ended_at="2026-08-02T18:36:51Z", battery_end=95)


@pytest.mark.parametrize("specs,expected", [
    ([{"by_mode": ["vacuum"]}, {"by_mode": ["vacuum"]}], "vacuum"),
    ([{"by_mode": ["mop"]}], "mop"),
    # vacuum_mop is ONE mode the user chose, not a mixture of two.
    ([{"by_mode": ["vacuum_mop"]}, {"by_mode": ["vacuum_mop"]}], "vacuum_mop"),
    # "mixed" means the CHILDREN DISAGREED — the only case one label cannot describe.
    ([{"by_mode": ["vacuum"]}, {"by_mode": ["mop"]}], "mixed"),
    ([{"by_mode": ["vacuum", "mop"]}], "mixed"),
])
def test_run_clean_mode_from_child_metrics(store, specs, expected):
    assert _close_with(store, specs)["aggregate"]["clean_mode"] == expected


def test_falls_back_to_room_settings_and_NORMALIZES_them(store):
    """A run too short to compute shares still has rooms. The fallback reads DISPLAY
    strings ("Vacuum and mop"), the un-normalized-vocabulary trap CLEAN_MODE_ALIASES
    exists for — so it normalizes rather than trusting."""
    parent = _close_with(store, [{"room_modes": ["Vacuum and mop", "vacuum_mop"]}])
    assert parent["aggregate"]["clean_mode"] == "vacuum_mop"


def test_unknown_is_None_not_a_guess(store):
    """Absent is not "vacuum". A review row that guesses is worse than one that says
    nothing — the same rule as an unreadable battery being null, not 0."""
    parent = _close_with(store, [{}])
    assert parent["aggregate"]["clean_mode"] is None


# ---------------------------------------------------------------------------
# planned vs actual — "I planned to do this. I did do this."
# ---------------------------------------------------------------------------

def test_the_parent_carries_the_PLAN_snapshotted_at_open(store):
    """Stolen from get_planned_job_estimate -- the same source the card's estimate panel
    renders -- rather than computed a second time."""
    parent = store.open_phased_job(
        vacuum_entity_id=_VAC, phased_job_id=_PJ, map_id="12",
        started_at="2026-08-02T18:15:51Z", battery_start=100,
        planned_phases=[
            {"phase_type": "room_group", "queue_room_ids": [5]},
            {"phase_type": "wait"},
            {"phase_type": "room_group", "queue_room_ids": [8, 4]},
        ],
        planned_estimate={
            "total_minutes": 21.0, "job_eta_minutes": 21.0,
            "water_estimate": {"estimated_total_dock_clean_water_used_ml": 240.0},
        },
        planned_rooms=[{"clean_mode": "Vacuum"}, {"clean_mode": "Vacuum"},
                       {"clean_mode": "Vacuum and mop"}],
    )
    assert parent["planned"] == {
        "total_minutes": 21.0, "eta_minutes": 21.0,
        "room_count": 3,          # unioned across phases, the wait contributes none
        "clean_mode": "mixed",    # 2 vacuum + 1 vacuum_mop
        "water_ml": 240.0,
    }


def test_planned_and_actual_are_kept_APART(store):
    """They can legitimately disagree -- a room rule can change a mode mid-run, or a room
    can be blocked. The DELTA is the point, so collapsing them would destroy it."""
    store.open_phased_job(
        vacuum_entity_id=_VAC, phased_job_id=_PJ, map_id="12",
        started_at="2026-08-02T18:15:51Z", battery_start=100,
        planned_phases=[{"phase_type": "room_group", "queue_room_ids": [5]}],
        planned_estimate={"total_minutes": 3.61},
        planned_rooms=[{"clean_mode": "vacuum_mop"}],
    )
    _child_modes(store, "job_0", by_mode=["vacuum"])
    store.record_phase_outcome(vacuum_entity_id=_VAC, phased_job_id=_PJ, phase_index=0,
                               phase_type="room_group", outcome="completed",
                               record_id="job_0")
    parent = store.close_phased_job(vacuum_entity_id=_VAC, phased_job_id=_PJ,
                                    ended_at="2026-08-02T18:36:51Z", battery_end=95)
    assert parent["planned"]["clean_mode"] == "vacuum_mop"   # intent
    assert parent["aggregate"]["clean_mode"] == "vacuum"     # outcome
    assert parent["planned"]["total_minutes"] == 3.61        # the 3.61-vs-21 miss
    assert parent["aggregate"]["cleaning_time_seconds"] == 60


def test_no_plan_supplied_leaves_nulls_not_zeros(store):
    """A missing estimate is unknown, not "0 minutes" -- same rule as an unreadable
    battery being null."""
    parent = _open(store)
    assert parent["planned"]["total_minutes"] is None
    assert parent["planned"]["clean_mode"] is None
    assert parent["planned"]["room_count"] == 3   # structure IS known, from the phases


# ---------------------------------------------------------------------------
# Hostile audit of the store itself, 2026-08-02 — six probes, six repairs
# ---------------------------------------------------------------------------

def test_A1_a_zero_minute_estimate_is_real_not_unknown(store):
    """`x or None` turned a genuine 0 into "unknown". Third instance of the falsy-zero
    trap this session — get_battery_level's 0, faultLabel's code 0, now this."""
    from custom_components.eufy_vacuum.learning.history_store import _planned_snapshot
    assert _planned_snapshot({"total_minutes": 0.0}, [], [])["total_minutes"] == 0.0
    assert _planned_snapshot({}, [], [])["total_minutes"] is None


@pytest.mark.parametrize("value", [{"a": 1}, ["vacuum"], 7, object()])
def test_A2_a_non_string_mode_is_unknown_not_manufactured(value):
    """str() on a dict produced "{'a': 1}" and shipped it as a clean mode — a value
    invented from malformed input, the same class as int(3.7) becoming a real code."""
    from custom_components.eufy_vacuum.learning.history_store import clean_mode_of
    assert clean_mode_of([{"clean_mode": value}]) is None


def test_A3_the_plan_owns_the_phase_type(store):
    """A caller's wrong argument rewrote `wait` into `room_group`. The type decides
    whether a phase counts toward `completed` and whether its gap is a hold or transit,
    so a typo silently changed the run's meaning."""
    _open(store)
    store.record_phase_outcome(vacuum_entity_id=_VAC, phased_job_id=_PJ, phase_index=1,
                               phase_type="room_group",  # wrong: phase 1 is a wait
                               outcome="completed", record_id="j1")
    parent = store.load_phased_job(vacuum_entity_id=_VAC, phased_job_id=_PJ)
    assert parent["phases"][1]["type"] == "wait"


def test_A4_a_child_that_will_not_load_is_VISIBLE(store):
    """THE serious one. A parent read status "completed" with 0 seconds and no rooms
    because its child record was gone — a record that LIES, the exact class this design
    exists to remove. The phase outcomes stay authoritative; the gap is named."""
    _open(store, [{"phase_type": "room_group", "queue_room_ids": [5]}])
    store.record_phase_outcome(vacuum_entity_id=_VAC, phased_job_id=_PJ, phase_index=0,
                               phase_type="room_group", outcome="completed",
                               record_id="ghost")
    parent = store.close_phased_job(vacuum_entity_id=_VAC, phased_job_id=_PJ,
                                    ended_at="2026-08-02T18:30:00Z", battery_end=95)
    assert parent["aggregate"]["missing_children"] == ["ghost"]
    assert parent["aggregate"]["cleaning_time_seconds"] == 0


def test_A4b_a_healthy_run_reports_no_missing_children(store):
    """The flag must stay empty in the normal case, or it teaches people to ignore it."""
    _open(store, [{"phase_type": "room_group", "queue_room_ids": [5]}])
    _child(store, "job_0", "2026-08-02T18:15:51Z", "2026-08-02T18:18:16Z", 120, 1.0, [5])
    store.record_phase_outcome(vacuum_entity_id=_VAC, phased_job_id=_PJ, phase_index=0,
                               phase_type="room_group", outcome="completed",
                               record_id="job_0")
    parent = store.close_phased_job(vacuum_entity_id=_VAC, phased_job_id=_PJ,
                                    ended_at="2026-08-02T18:30:00Z", battery_end=95)
    assert parent["aggregate"]["missing_children"] == []


def test_A6_a_phase_reported_after_close_reopens_the_run(store):
    """A late report left status stale while the phase read "completed" — the parent
    contradicting itself. A re-armed poller finishing after the reaper closed the run is
    legitimate, so re-open rather than reject."""
    _open(store, [{"phase_type": "room_group", "queue_room_ids": [5]}])
    store.close_phased_job(vacuum_entity_id=_VAC, phased_job_id=_PJ,
                           ended_at="2026-08-02T18:30:00Z", battery_end=95)
    store.record_phase_outcome(vacuum_entity_id=_VAC, phased_job_id=_PJ, phase_index=0,
                               phase_type="room_group", outcome="completed",
                               record_id="late")
    parent = store.load_phased_job(vacuum_entity_id=_VAC, phased_job_id=_PJ)
    assert parent["status"] == "running"
    assert parent["ended_at"] is None


def test_A7_reopening_with_a_different_plan_keeps_the_original(store):
    """The run's plan is fixed at start, so the existing parent wins — but a differing
    plan means a re-plan or an id collision, and both must be logged, not swallowed."""
    _open(store, [{"phase_type": "room_group", "queue_room_ids": [5]}])
    again = _open(store, [{"phase_type": "room_group", "queue_room_ids": [9]},
                          {"phase_type": "room_group", "queue_room_ids": [7]}])
    assert [p["planned_room_ids"] for p in again["phases"]] == [[5]]


# --------------------------------------------------------------------------
# Parent eligibility — "if any run keyed to a phased run is excluded, that
# phased run is excluded by default: it lost part of its identity" (Chris).
# --------------------------------------------------------------------------


def _parent_with_children(store, *, child_ok=(True, True), status="completed",
                          unsplit=None, missing=None):
    """A closed 3-phase parent whose two clean phases point at real child records."""
    for i, ok in zip((0, 2), child_ok):
        store.save_completed_job(
            vacuum_entity_id=_VAC, job_id=f"job_p.phase{i}",
            payload={
                "record_type": "completed_job",
                "job_id": f"job_p.phase{i}",
                "outcome": {"status": "completed", "used_for_learning": bool(ok)},
                "job": {"cleaning_time_seconds": 100},
                "queue": {},
                "phase_key": {"phased_job_id": "pj_elig", "phase_index": i},
            },
        )
    return {
        "record_type": "phased_job",
        "phased_job_id": "pj_elig",
        "status": status,
        "phases": [
            {"index": 0, "type": "room_group", "record_id": "job_p.phase0",
             "outcome": "completed"},
            {"index": 1, "type": "wait", "record_id": "pj_elig.phase1",
             "outcome": "completed"},
            {"index": 2, "type": "room_group", "record_id": "job_p.phase2",
             "outcome": "completed"},
        ],
        "aggregate": {"unsplit_phases": unsplit or [], "missing_children": missing or []},
    }


def _eligible(store, parent):
    return store.is_learning_phased_job(vacuum_entity_id=_VAC, parent=parent)


def test_a_complete_phased_run_teaches_the_phased_pool(store):
    assert _eligible(store, _parent_with_children(store)) is True


def test_excluding_ONE_child_excludes_its_parent(store):
    """The parent's value is that it describes a COMPLETE orchestration. Drop a child and
    the total describes a run that never happened."""
    parent = _parent_with_children(store, child_ok=(True, False))
    assert _eligible(store, parent) is False


def test_restoring_the_child_makes_the_parent_eligible_again(store):
    """Derived, not stored — restore needs no second action to undo, because nothing was
    written down. A stored flag would need exclude_learning_job to remember its parent."""
    parent = _parent_with_children(store, child_ok=(True, False))
    assert _eligible(store, parent) is False
    store.save_completed_job(
        vacuum_entity_id=_VAC, job_id="job_p.phase2",
        payload={
            "record_type": "completed_job", "job_id": "job_p.phase2",
            "outcome": {"status": "completed", "used_for_learning": True},
            "job": {"cleaning_time_seconds": 100}, "queue": {},
        },
    )
    assert _eligible(store, parent) is True


def test_an_unsplit_phase_makes_the_parent_ineligible(store):
    """The total is short by however long that phase took — invisible in the number."""
    parent = _parent_with_children(store, unsplit=[2])
    assert _eligible(store, parent) is False


def test_a_missing_child_makes_the_parent_ineligible(store):
    parent = _parent_with_children(store, missing=["job_p.phase2"])
    assert _eligible(store, parent) is False


def test_a_cancelled_phased_run_never_teaches(store):
    for bad in ("cancelled", "interrupted", "partial", "running"):
        assert _eligible(store, _parent_with_children(store, status=bad)) is False


def test_a_break_only_parent_is_not_a_sample(store):
    """No clean phase means nothing was cleaned — not a zero-cost orchestration."""
    parent = _parent_with_children(store)
    parent["phases"] = [{"index": 0, "type": "wait", "record_id": "x", "outcome": "completed"}]
    assert _eligible(store, parent) is False
