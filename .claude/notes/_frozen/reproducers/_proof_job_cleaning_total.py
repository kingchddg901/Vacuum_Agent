"""Proof RP-013f (RF-11 part 6) — a stepped run's cleaning time is only its last phase.

THIS PROOF HAS NO FIXTURE. Both cases run against the REAL finalized record from
hardware stepped Run A, frozen at

    .claude/notes/_frozen/baseline/job_2026-08-01T13-49-21-steppedA.json

(Ivy, [Kitchen 27] -> charge_wait 100% -> [Hallway 25], completed and
auto-finalized 2026-08-01 14:08:50, used_for_learning: true.)

Nothing here is modelled, so nothing here can be mis-modelled — the failure mode
that cost tranche 2 three iterations. The assertions are invariants the record
must satisfy, checked against production's own output.

  REC-A — the job's cleaning_time_seconds is read from last_cleaning_time_seconds,
    the last-seen DEVICE counter, and every dispatched phase RESETS that counter.
    The record says 302 s. Its own room timings say 255 + 302 = 557 s. A job
    cannot have cleaned for less time than the sum of its rooms.

  REC-B (the cascade) — compute_overhead_observed derives
    total_overhead_minutes = duration - cleaning_minutes, so the 255 s that went
    missing above reappears as overhead. stats_rebuilder averages that field
    across jobs, so every stepped run permanently inflates the learned overhead
    model that the card's ETAs are built from.

The wall-clock fallback half of RP-013f (it subtracts paused + recharge but not
COMMANDED break phases, and RP-012(d) removed the term that was accidentally
masking it) is specified with tests in the packet but is NOT proof-covered: it
lives inline in an async finalize method, and driving it would mean emulating the
finalize path — which the harness rule forbids. Recorded here so the gap is
deliberate rather than forgotten.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_job_cleaning_total.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.learning.utils import (   # noqa: E402
    compute_overhead_observed,
)

RECORD = Path(".claude/notes/_frozen/baseline/"
              "job_2026-08-01T13-49-21-steppedA.json")


def main() -> int:
    proof = H.Proof("RP-013f", "a stepped run's cleaning time is the whole run")

    job = json.loads(RECORD.read_text(encoding="utf-8"))["job"]
    recorded = int(job.get("cleaning_time_seconds") or 0)
    timings = job.get("room_timings") or []
    summed = sum(int(t.get("cleaning_seconds") or 0) for t in timings)
    per_room = [(t.get("slug"), t.get("cleaning_seconds")) for t in timings]

    proof.case(
        "the finalized record's job total vs the sum of its own room timings",
        before=recorded == 302 and summed == 557,
        before_msg="the job recorded ONLY its last phase — 302 s against 557 s "
                   "actually measured, 46 % short; every dispatched phase resets "
                   "the device counter and the finalizer reads the last value",
        after=recorded == summed,
        after_msg="the job total is the sum of its phases",
        detail=f"job cleaning_time_seconds={recorded} · room timings={per_room} "
               f"· sum={summed}",
    )

    # The cascade, through production's own derivation.
    overhead = compute_overhead_observed(job)
    got = overhead.get("total_overhead_minutes")
    duration = float(job.get("duration_minutes") or 0.0)
    truth = round(max(duration - summed / 60.0, 0.0), 2)

    proof.case(
        "the overhead this record hands to the learning model",
        # `truth` is COMPUTED, never asserted against a typed-in constant — an
        # earlier draft hardcoded 10.19 and the UNEXPECTED arm caught it (the
        # value rounds to 10.2). A proof that pins a derived number to a literal
        # is asserting the author's arithmetic, not production's.
        before=got == 14.45 and got > truth,
        before_msg="overhead inflated by exactly the missing cleaning time — "
                   "stats_rebuilder averages total_overhead_minutes across jobs, "
                   "so every stepped run permanently skews the model the card's "
                   "ETAs come from",
        after=got == truth,
        after_msg="overhead is the residual against the run's real cleaning time",
        detail=f"recorded total_overhead_minutes={got} · truth against the "
               f"summed cleaning time={truth} (duration={duration})",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
