"""Proof RP-046 (RF-DOCK) — a dock fault is charged against cleaning time.

Driven from the ARCHIVED LIVE RECORD, not a hand-built fixture:
`_frozen/baseline/job_2026-08-01T23-23-35-alfred-heavy.json`. Its own error latch and its
own cleaning time are the inputs, so the proof cannot drift from the incident it
describes.

WHAT HAPPENED. Alfred cleaned the kitchen for 360 s, covered 4.0 m2, drew 3 % battery and
used 30.8 ml of mop water. The record says it cleaned for ZERO seconds:

    cleaning_time_seconds_raw:  360     <- RP-013f's phase sum. CORRECT.
    total_error_seconds:        455
    cleaning_time_seconds:        0     <- max(0, 360 - 455)

All five faults are code 6013, STATION CLEAN WATER PUMP SHORT, at job-elapsed 72, 83, 478,
486 and 525 s. The station's clean-water pump complained while the robot worked through it
-- the area, duration, battery draw and water use all prove the run was productive.
`used_for_learning` was TRUE, so the model learned that 4 m2 takes no time.

  1. THE DEDUCTION. Every error second is subtracted regardless of whose fault it was.
     After the repair only faults that invalidate the run's cleaning evidence are, so
     these five deduct nothing and the 360 s survives.

  2. AN UNKNOWN CODE MUST NOT BE DEDUCTED EITHER. A brand that declares no table, or a
     code the vendor shipped after the table was written, must PRESERVE the run rather
     than zero it. This is the same incident wearing a different hat, and it is the
     failure direction that actually destroys data: wrongly crediting a run adds noise
     that averages out, wrongly zeroing one teaches the model that area takes no time.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_dock_fault_seconds.py
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.adapters.eufy.vocabulary import (   # noqa: E402
    EUFY_EVIDENCE_INVALIDATING_ERROR_CODES,
    EUFY_EVIDENCE_SAFE_ERROR_CODES,
)
from custom_components.eufy_vacuum.adapters.registry import (   # noqa: E402
    register_adapter_config,
)
from custom_components.eufy_vacuum.core.error_tracker import (   # noqa: E402
    classify_error_code,
)
from custom_components.eufy_vacuum.learning.job_finalizer import (   # noqa: E402
    _compute_total_error_seconds,
)

RECORD = pathlib.Path(
    ".claude/notes/_frozen/baseline/job_2026-08-01T23-23-35-alfred-heavy.json"
)
VAC = "vacuum.alfred"


def _live() -> tuple[dict, str, int]:
    """The archived record's own latch, end time and raw cleaning seconds."""
    rec = json.loads(RECORD.read_text(encoding="utf-8"))
    latch = rec["outcome"]["errors"]
    ended_at = rec["job"]["ended_at"]
    raw = 0
    for timing in rec["job"].get("room_timings") or []:
        raw += int(timing.get("cleaning_seconds") or 0)
    return latch, ended_at, raw


def _register(*, declare: bool) -> None:
    cfg = {
        "entities": {},
        "mapping": {"segmenter_engine": "noop_fallback"},
        "job_segmenter": {"engine": "noop_job_fallback"},
        "room_attribution": {"engine": "noop_room_attribution"},
        "error_tracking": {},
    }
    if declare:
        cfg["error_tracking"] = {
            "evidence_invalidating_error_codes": sorted(
                EUFY_EVIDENCE_INVALIDATING_ERROR_CODES
            ),
            "evidence_safe_error_codes": sorted(EUFY_EVIDENCE_SAFE_ERROR_CODES),
        }
    register_adapter_config(VAC, cfg)


def _deductible(latch: dict, ended_at: str) -> int | None:
    """What the finalizer subtracts, or None when the repair is absent.

    Pre-repair _compute_total_error_seconds takes no per-entry filter, so this raises
    TypeError -- which IS the before-state, observed rather than recomputed. An earlier
    draft asserted a hand-computed "before" alongside a hand-computed "after" and the
    harness caught them both matching: two formulas of mine, not a property of the code.
    """
    try:
        return _compute_total_error_seconds(
            latch, job_ended_at=ended_at,
            keep_entry=lambda e: classify_error_code(VAC, e.get("code")) == "invalidating",
        )
    except TypeError:
        return None


def case_dock_fault_zeroes_a_productive_run(proof: H.Proof) -> None:
    latch, ended_at, raw = _live()
    _register(declare=True)

    total = _compute_total_error_seconds(latch, job_ended_at=ended_at)
    deductible = _deductible(latch, ended_at)
    # Pre-repair the whole window is deducted; post-repair only the invalidating share.
    applied = total if deductible is None else deductible
    cleaning = max(0, raw - applied)
    codes = sorted({e.get("code") for e in latch.get("errors", [])})

    proof.case(
        "the archived alfred run: 360 s of kitchen, five dock-side 6013 faults",
        before=deductible is None and cleaning == 0 and total > raw,
        before_msg="a productive 360 s run recorded as 0 s cleaning time — every error "
                   "second was deducted regardless of whose fault it was, and the model "
                   "learned that 4 m2 takes no time",
        after=deductible == 0 and cleaning == raw,
        after_msg="cleaning_time_seconds survives intact; the dock's 455 s are reported, "
                  "not deducted",
        detail=f"codes={codes} · raw cleaning={raw}s · total_error={total}s · "
               f"deducted={applied}s · resulting cleaning_time={cleaning}s",
    )


def case_an_unknown_code_is_preserved_not_deducted(proof: H.Proof) -> None:
    """A brand that declares nothing must keep the run, not zero it."""
    latch, ended_at, raw = _live()
    _register(declare=False)      # no table at all — every code is unclassified

    total = _compute_total_error_seconds(latch, job_ended_at=ended_at)
    deductible = _deductible(latch, ended_at)
    applied = total if deductible is None else deductible
    classification = classify_error_code(VAC, 6013)

    proof.case(
        "the same run on a brand that declares no evidence table",
        before=deductible is None and max(0, raw - applied) == 0,
        before_msg="no classifier exists, so every error second is deducted and the run "
                   "is zeroed — a brand with no table fails toward destroying its data",
        after=classification == "unclassified" and deductible == 0
        and max(0, raw - applied) == raw,
        after_msg="unclassified is PRESERVED — a brand with no table, or a code the "
                  "vendor shipped after the table was written, cannot zero a run",
        detail=f"classification of 6013 with no declaration={classification!r} · "
               f"total_error={total}s · deducted={applied}s · "
               f"resulting cleaning_time={max(0, raw - applied)}s",
    )


def main() -> None:
    proof = H.Proof("RP-046", "a dock fault is charged against cleaning time")
    case_dock_fault_zeroes_a_productive_run(proof)
    case_an_unknown_code_is_preserved_not_deducted(proof)
    proof.finish()


H.run(main)
