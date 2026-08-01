"""Proof RP-041 (RF-13 remainder, Q20) — job-relevant error blocking at preflight.

Two cases, both driving required_behavior (1) (the set-logic fix) directly
and concretely. Items (2)-(4)'s NEW fault_blocks_job/adapter fault_relevance
mechanism is NOT driven -- it is a wholly new question-helper with an
adapter-declared config block that does not exist yet anywhere in the
codebase (grepped: zero hits for "fault_relevance" or "fault_blocks_job"),
same disposition as every other not-yet-built mechanism flagged this
session (RP-015's Q4, RP-017's PER_MAP_STORES walker) -- flagged rather
than guessed at.

Root cause, verified at source (jobs/job_monitor.py:138-230,
evaluate_job_lifecycle): _HA_ACTIVE_VACUUM_STATES = {"cleaning",
"returning", "paused", "error"} (core/manager.py:104-109) is used for TWO
OPPOSITE questions with the same set:
  - line 200: "is vacuum_state EVIDENCE of an active tracked job" (only
    reached when active_job_exists=True)
  - line 217: "is vacuum_state an EXEMPTION from the busy check" (`vacuum_
    state_n not in active_vacuum_states`) -- reached regardless of whether
    a job is tracked.
A state that legitimately proves activity when a job EXISTS (line 200) is
therefore ALSO treated as "not busy" when NO job is tracked (line 217) --
exactly backwards for "error" and "cleaning": with active_job_exists=False,
neither the active_job_running branch (needs a tracked job) nor the busy
branch (exempted via the same set) fires, and both fall through to "ready".

  #1 -- an externally-faulted robot (vacuum_state="error", no tracked job)
    classifies as ready; Start would dispatch a room-clean at a robot
    sitting in an error state.
  #2 -- an externally-cleaning robot (vacuum_state="cleaning", started from
    the vendor app, no tracked job) ALSO classifies as ready -- the same
    membership-as-exemption bug, a different externally-driven run.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_fault_relevance.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.jobs.job_monitor import evaluate_job_lifecycle   # noqa: E402


def main() -> int:
    proof = H.Proof("RP-041", "job-relevant error blocking at preflight (set-logic half)")

    # -------------------------------------------------------------------
    # Case 1: an errored robot with no tracked job classifies as ready.
    # -------------------------------------------------------------------
    result_error = evaluate_job_lifecycle(
        active_job_exists=False,
        active_cleaning_target=None,
        vacuum_state="error",
        task_status=None,
        dock_status=None,
        active_map_id="1",
        selected_map_id="1",
    )

    proof.case(
        "vacuum_state='error', no tracked job (the vacuum-state busy branch)",
        before=result_error["lifecycle_state"] == "ready",
        before_msg="'error' is a member of active_vacuum_states, so it is "
                   "EXEMPTED from the busy check -- with no active job "
                   "tracked, nothing else catches it and it falls through "
                   "to ready. Start would dispatch at an errored robot",
        after=result_error["lifecycle_state"] != "ready" and result_error["blocking"] is True,
        after_msg="the set logic no longer exempts 'error' from the busy "
                  "evaluation -- an errored robot with no tracked job blocks "
                  "start",
        detail=f"lifecycle_state={result_error['lifecycle_state']!r} "
               f"blocking={result_error['blocking']}",
    )

    # -------------------------------------------------------------------
    # Case 2: an externally-cleaning robot (vendor app) classifies as ready.
    # -------------------------------------------------------------------
    result_external = evaluate_job_lifecycle(
        active_job_exists=False,
        active_cleaning_target=None,
        vacuum_state="cleaning",
        task_status=None,
        dock_status=None,
        active_map_id="1",
        selected_map_id="1",
    )

    proof.case(
        "vacuum_state='cleaning' (started from the vendor app), no tracked job",
        before=result_external["lifecycle_state"] == "ready",
        before_msg="the SAME membership-as-exemption bug: 'cleaning' is "
                   "also in active_vacuum_states, so an untracked external "
                   "run is also exempted from busy and reads as ready",
        after=result_external["lifecycle_state"] != "ready"
        and result_external["blocking"] is True,
        after_msg="externally-cleaning (untracked run) is blocked as busy "
                  "with a reason distinct from error (external_run_in_progress)",
        detail=f"lifecycle_state={result_external['lifecycle_state']!r} "
               f"blocking={result_external['blocking']}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
