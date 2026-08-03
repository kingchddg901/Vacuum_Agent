"""REGRESSION GATE for the phased-run work landed 2026-08-03.

Chris: "ensure none of these break what we just fixed in phased runs."

The remaining audit packets are not neutral to that work — two RP-021b findings
land squarely on it:

  #8:A4-PP-RP-6  edits planning/run_plan.py::_build_steps_phases, the per-group
                 overlay that FEEDS engine.build_phases — i.e. the function that
                 decides what a phase contains and therefore what the rollover
                 advances through and what the segmenter slices.
  #8:A4-PP-RP-4  adds a third step source to _build_effective_start_plan, which
                 decides whether a run is stepped at all.

RP-017 / RP-023 / RP-041 also touch learning/ and the job paths.

So this gate names, in one place, exactly what today's five phased-run commits
bought — run it BEFORE and AFTER every remaining packet. A full green pytest run
is NOT the same thing: this suite is 3500+ tests and a phased regression is a
handful of them, easy to lose in the noise, and two of the guarantees below are
proven by REPRODUCERS rather than tests at all (the campaign's own rule: "run the
reproducer, not just pytest" — a fix-up once shipped an over-credit bug with 3146
tests green and only the proof reporting UNEXPECTED SHAPE).

WHAT IS BEING PROTECTED
  40cbaac  rooms advance INSIDE an Eufy room_group (the phases-guard moved off
           the whole rollover function onto the native-signal branch)
  5ec6893  dock trips are not charged to the room the robot is not in
           (current_room_noncleaning_seconds accumulator)
  def78af  a group phase's rooms get MEASURED timings, not an even split
           (allocated:false when the counter slice shows the split)
  a3ea685  the estimate panel serves the plan frozen AT DISPATCH during a run
  6831ccd  the live snapshot presents the PHASE, not room[0]

Run: python .claude/notes/_gate_phased_runs.py
     (needs docker — the suite runs in the Linux image; see scripts/test.bat)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: pytest targets. Files, not -k expressions: an -k that silently matches nothing
#: is the classic way a gate reports green while testing zero.
PYTEST_TARGETS = [
    "tests/unit/test_jobs_active_job.py",            # rollover guard position, accumulator
    "tests/integration/test_jobs_active_job.py",     # accumulator wiring, phased rollover
    "tests/unit/test_core_run_state.py",             # the non-cleaning predicate + fail-open
    "tests/integration/test_strict_order_phase_timing.py",  # segmentation vs apportioning
    "tests/integration/test_manager_progress.py",    # estimate freeze + live progress
    "tests/integration/test_charge_wait_phase.py",   # _build_steps_phases callers
    "tests/unit/test_phased_job_wiring.py",
    "tests/unit/test_phased_job_store.py",
    "tests/unit/test_queue_engine.py",
    "tests/integration/test_zone_phase.py",
    "tests/integration/test_dock_phase_rearm.py",
]

#: Reproducers/proofs. These carry guarantees no test asserts.
PROOFS = [
    ".claude/notes/_proof_group_live_progress.py",
    ".claude/notes/_probe_phase_slice_seg.py",
]

_DOCKER = [
    "docker", "run", "--rm",
    "-v", f"{ROOT}:/workspace", "-w", "/workspace",
    "-e", "PYTHONPATH=/workspace", "eufy-vacuum-test",
]


def _run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True)
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")


def main() -> int:
    failures: list[str] = []

    missing = [t for t in PYTEST_TARGETS + PROOFS if not (ROOT / t).exists()]
    if missing:
        # A renamed file must fail the gate, not shrink it silently.
        print("GATE IS STALE — these targets no longer exist:")
        for m in missing:
            print(f"  {m}")
        return 2

    print(f"pytest: {len(PYTEST_TARGETS)} files")
    code, out = _run(_DOCKER + ["python", "-m", "pytest", *PYTEST_TARGETS,
                                "--no-cov", "-q", "-p", "no:cacheprovider"])
    tail = [ln for ln in out.strip().splitlines() if ln.strip()][-1:]
    print("  " + (tail[0] if tail else "<no output>"))
    if code != 0:
        failures.append("pytest")
        print(out[-3000:])

    for proof in PROOFS:
        code, out = _run(_DOCKER + ["python", proof])
        verdict = [ln for ln in out.strip().splitlines() if ln.strip()][-1:]
        name = Path(proof).name
        print(f"proof {name}: {verdict[0] if verdict else '<no output>'}")
        if code != 0:
            failures.append(name)
            print(out[-1500:])

    print("\n" + "=" * 70)
    if failures:
        print(f"PHASED-RUN GATE: FAILED ({', '.join(failures)})")
        return 1
    print("PHASED-RUN GATE: GREEN — today's phased-run behaviour intact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
