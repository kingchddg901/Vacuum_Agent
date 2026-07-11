"""Cold-start idle-wall guard — pure logic + break-phase helper + finalizer wiring
+ a golden on REAL Alfred records.

The guard holds an otherwise-eligible COMPLETED run from *defining* a room baseline
when its wall time exceeds active cleaning by >= the floor with no "other answer"
(a commanded charge/wait phase or a logged error). Held via a learning_blocker so
the run stays Restore-able, never hard-excluded.

The golden pins the design's must-hold / must-pass verdicts against real numbers
pulled from the archive. Its load-bearing case: the 96-min-idle exemplar's DEVICE
counter is 33 min but its state-slice actual_cleaning_minutes is ~129 (≈ full wall)
— the guard must read the counter, else the idle hides as a ~0 gap.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.learning.job_finalizer import (
    LearningJobFinalizer,
    _run_had_break_phase,
)
from custom_components.eufy_vacuum.learning.utils import (
    IDLE_WALL_HOLD_BLOCKER,
    IDLE_WALL_HOLD_FLOOR_MINUTES,
    evaluate_idle_wall_hold,
)

FLOOR = IDLE_WALL_HOLD_FLOOR_MINUTES
_FIX = Path(__file__).parent.parent / "fixtures" / "learning" / "idle_wall_records.json"


# --- pure decision logic -----------------------------------------------------

def test_holds_extreme_unexplained_gap():
    v = evaluate_idle_wall_hold(
        duration_minutes=130.0, active_cleaning_minutes=33.0,
        had_errors=False, had_break_phase=False,
    )
    assert v["hold"] is True
    assert v["reason"] == IDLE_WALL_HOLD_BLOCKER
    assert v["idle_gap_minutes"] == 97.0


def test_passes_small_gap():
    v = evaluate_idle_wall_hold(
        duration_minutes=25.0, active_cleaning_minutes=20.0,
        had_errors=False, had_break_phase=False,
    )
    assert v["hold"] is False
    assert v["reason"] is None
    assert v["idle_gap_minutes"] == 5.0


def test_exactly_at_floor_holds_inclusive():
    v = evaluate_idle_wall_hold(
        duration_minutes=FLOOR + 10.0, active_cleaning_minutes=10.0,
        had_errors=False, had_break_phase=False,
    )
    assert v["hold"] is True  # idle_gap == floor -> inclusive


def test_just_under_floor_passes():
    v = evaluate_idle_wall_hold(
        duration_minutes=FLOOR + 10.0 - 0.01, active_cleaning_minutes=10.0,
        had_errors=False, had_break_phase=False,
    )
    assert v["hold"] is False


def test_break_phase_exempts_even_huge_gap():
    v = evaluate_idle_wall_hold(
        duration_minutes=200.0, active_cleaning_minutes=10.0,
        had_errors=False, had_break_phase=True,
    )
    assert v["hold"] is False
    assert v["reason"] is None


def test_error_exempts_even_huge_gap():
    v = evaluate_idle_wall_hold(
        duration_minutes=200.0, active_cleaning_minutes=10.0,
        had_errors=True, had_break_phase=False,
    )
    assert v["hold"] is False


@pytest.mark.parametrize("active", [None, 0.0, -1.0])
def test_missing_active_never_holds(active):
    # Absence of a trustworthy active-cleaning figure is not evidence of idling.
    v = evaluate_idle_wall_hold(
        duration_minutes=999.0, active_cleaning_minutes=active,
        had_errors=False, had_break_phase=False,
    )
    assert v["hold"] is False
    assert v["idle_gap_minutes"] is None


# --- _run_had_break_phase ----------------------------------------------------

@pytest.mark.parametrize("phases,expected", [
    ([{"phase_type": "charge_wait"}], True),
    ([{"phase_type": "wait"}], True),
    ([{"phase_type": "room_group"}, {"phase_type": "charge_wait"}], True),
    ([{"phase_type": "room_group"}], False),
    ([{"phase_type": "CHARGE_WAIT"}], True),  # case-insensitive
    ([], False),
    (None, False),
])
def test_run_had_break_phase(phases, expected):
    state = {"phases": phases} if phases is not None else {}
    assert _run_had_break_phase(state) is expected


def test_run_had_break_phase_non_dict_state():
    assert _run_had_break_phase(None) is False
    assert _run_had_break_phase("nope") is False


# --- finalizer wiring (_apply_idle_wall_hold mutates the outcome) ------------

@pytest.fixture
def finalizer():
    return LearningJobFinalizer(MagicMock())


def _completed(*, duration, ct_secs, status="completed", ufl=True, actual=None, blockers=None):
    return {
        "outcome": {
            "status": status,
            "used_for_learning": ufl,
            "learning_blockers": list(blockers or []),
        },
        "job": {
            "duration_minutes": duration,
            "cleaning_time_seconds": ct_secs,
            "actual_cleaning_minutes": actual,
        },
    }


def test_wiring_holds_big_idle_run(finalizer):
    cj = _completed(duration=130.0, ct_secs=1980)  # active 33 -> gap 97
    finalizer._apply_idle_wall_hold(
        completed_job=cj, active_job_state={}, had_errors=False, job_id="j1",
    )
    assert cj["outcome"]["used_for_learning"] is False
    assert IDLE_WALL_HOLD_BLOCKER in cj["outcome"]["learning_blockers"]
    assert cj["outcome"]["idle_wall_minutes"] == 97.0


def test_wiring_leaves_normal_run_untouched(finalizer):
    cj = _completed(duration=25.0, ct_secs=1200)  # active 20 -> gap 5
    finalizer._apply_idle_wall_hold(
        completed_job=cj, active_job_state={}, had_errors=False, job_id="j2",
    )
    assert cj["outcome"]["used_for_learning"] is True
    assert cj["outcome"]["learning_blockers"] == []
    assert "idle_wall_minutes" not in cj["outcome"]


def test_wiring_break_phase_exempts(finalizer):
    cj = _completed(duration=130.0, ct_secs=1980)
    finalizer._apply_idle_wall_hold(
        completed_job=cj,
        active_job_state={"phases": [{"phase_type": "charge_wait"}]},
        had_errors=False, job_id="j3",
    )
    assert cj["outcome"]["used_for_learning"] is True


def test_wiring_error_exempts(finalizer):
    cj = _completed(duration=130.0, ct_secs=1980)
    finalizer._apply_idle_wall_hold(
        completed_job=cj, active_job_state={}, had_errors=True, job_id="j4",
    )
    assert cj["outcome"]["used_for_learning"] is True


def test_wiring_noop_on_non_completed(finalizer):
    cj = _completed(duration=130.0, ct_secs=1980, status="cancelled")
    finalizer._apply_idle_wall_hold(
        completed_job=cj, active_job_state={}, had_errors=False, job_id="j5",
    )
    # untouched — the cancelled run's own blockers own its exclusion
    assert IDLE_WALL_HOLD_BLOCKER not in cj["outcome"]["learning_blockers"]


def test_wiring_noop_on_already_unlearned(finalizer):
    cj = _completed(duration=130.0, ct_secs=1980, ufl=False, blockers=["manually_excluded"])
    finalizer._apply_idle_wall_hold(
        completed_job=cj, active_job_state={}, had_errors=False, job_id="j6",
    )
    assert cj["outcome"]["learning_blockers"] == ["manually_excluded"]


def test_wiring_prefers_device_counter_over_state_slice(finalizer):
    # The exemplar shape: state-slice ~= wall (would hide the idle); the DEVICE
    # counter exposes it. The guard must read the counter and HOLD.
    cj = _completed(duration=129.52, ct_secs=1980, actual=129.37)
    finalizer._apply_idle_wall_hold(
        completed_job=cj, active_job_state={}, had_errors=False, job_id="j7",
    )
    assert cj["outcome"]["used_for_learning"] is False


# --- golden on REAL records --------------------------------------------------

def _active_minutes(rec: dict) -> float | None:
    # SAME preference the finalizer applies: DEVICE counter first, state-slice fallback.
    ct = rec.get("cleaning_time_seconds") or 0
    if ct > 0:
        return ct / 60.0
    a = rec.get("actual_cleaning_minutes")
    return float(a) if a else None


@pytest.mark.parametrize(
    "rec", json.loads(_FIX.read_text(encoding="utf-8")), ids=lambda r: r["job_id"]
)
def test_real_records_match_design_verdict(rec):
    v = evaluate_idle_wall_hold(
        duration_minutes=float(rec["duration_minutes"]),
        active_cleaning_minutes=_active_minutes(rec),
        had_errors=bool(rec["had_errors"]),
        had_break_phase=bool(rec["has_charge_steps"]),
    )
    assert v["hold"] is bool(rec["expect_hold"]), f"{rec['job_id']}: {rec['note']}"


def test_golden_exemplar_needs_the_device_counter():
    # Lock the field choice on the real exemplar: counter -> HOLD, state-slice -> miss.
    ex = next(
        r for r in json.loads(_FIX.read_text(encoding="utf-8"))
        if r["job_id"] == "job_2026-05-09T11-37-32"
    )
    by_counter = evaluate_idle_wall_hold(
        duration_minutes=float(ex["duration_minutes"]),
        active_cleaning_minutes=ex["cleaning_time_seconds"] / 60.0,
        had_errors=False, had_break_phase=False,
    )
    by_slice = evaluate_idle_wall_hold(
        duration_minutes=float(ex["duration_minutes"]),
        active_cleaning_minutes=float(ex["actual_cleaning_minutes"]),
        had_errors=False, had_break_phase=False,
    )
    assert by_counter["hold"] is True
    assert by_slice["hold"] is False
