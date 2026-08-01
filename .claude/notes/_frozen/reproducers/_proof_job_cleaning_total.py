"""Proof RP-013f (RF-11 part 6) — a stepped run's cleaning time is only its last phase.

  REC-A — the job's cleaning_time_seconds comes from last_cleaning_time_seconds,
    the last-seen DEVICE counter, and every dispatched phase RESETS that counter.
    Hardware Run A recorded 302 s against its own room timings' 255 + 302 = 557.
    A job cannot have cleaned for less time than the sum of its rooms.

  REC-B (the cascade) — compute_overhead_observed derives
    total_overhead_minutes = duration - cleaning_minutes, so the missing 255 s
    reappears as overhead; stats_rebuilder averages that field across jobs, so
    every stepped run permanently inflates the learned overhead model the card's
    ETAs are built from.

WHY THIS PROOF IS SHAPED THE WAY IT IS — the first draft asserted directly on the
frozen Run A record, which was WRONG in a way worth recording. A reproducer must
FLIP: same command, different output once repaired. A frozen historical artifact
cannot flip, because no source change rewrites a file on disk — both cases would
have reported BEFORE forever and the "repair" would eventually have been
certified by editing the proof. "No fixture" sounded like a strength and was
precisely the defect.

So the record now plays its correct role: case 0 asserts the FIXTURE MATCHES THE
HARDWARE, and the flipping cases drive the real production seam
(`_collect_finalization_inputs`, a synchronous method returning the derived
`cleaning_time_seconds`). The record guards the fixture against drifting into
fiction; production supplies the behaviour.

The wall-clock FALLBACK half of RP-013f (it subtracts paused + recharge but not
COMMANDED break phases, and RP-012(d) removed the term that accidentally masked
it) is specified with tests in the packet but is not proof-covered here: it fires
only when the counter is unreadable, and forcing that state would mean asserting
the author's arithmetic rather than production's. Deliberate, not forgotten.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_job_cleaning_total.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.learning.job_finalizer import (   # noqa: E402
    LearningJobFinalizer,
)
from custom_components.eufy_vacuum.learning.utils import (   # noqa: E402
    compute_overhead_observed,
)

RECORD = Path(".claude/notes/_frozen/baseline/"
              "job_2026-08-01T13-49-21-steppedA.json")

KITCHEN_S, HALLWAY_S = 255, 302
TOTAL_S = KITCHEN_S + HALLWAY_S          # 557
DURATION_MIN = 19.48


def _timing(room_id: int, slug: str, seconds: int) -> dict:
    return {"room_id": room_id, "slug": slug, "cleaning_seconds": seconds,
            "cleaning_wall_seconds": seconds - 22, "area_m2": 4.1,
            "battery_delta": None, "boundary": "phase"}


def case_fixture_matches_hardware(proof: H.Proof) -> None:
    """Not a flip — a GUARD. If the fixture below stops describing the real run,
    this fails and the two flipping cases stop meaning anything."""
    job = json.loads(RECORD.read_text(encoding="utf-8"))["job"]
    timings = job.get("room_timings") or []
    secs = [int(t.get("cleaning_seconds") or 0) for t in timings]
    recorded = int(job.get("cleaning_time_seconds") or 0)

    matches = (secs == [KITCHEN_S, HALLWAY_S]
               and recorded == HALLWAY_S
               and round(float(job.get("duration_minutes") or 0), 2) == DURATION_MIN)
    proof.case(
        "GUARD — the fixture still describes hardware run job_2026-08-01T13-49-21",
        before=matches,
        before_msg="fixture faithful — the frozen record shows per-room "
                   f"{secs}, a job total of {recorded} (its LAST phase) and "
                   f"{job.get('duration_minutes')} min duration",
        after=False,      # this case never flips; it guards the other two
        after_msg="unreachable",
        detail=f"record per-room={secs} · record job total={recorded} · "
               f"duration={job.get('duration_minutes')}",
    )


def case_job_total_is_last_phase(proof: H.Proof) -> None:
    hass = H.make_hass()
    mgr = H.ManagerStub(hass=hass)
    job = H.active_job(
        queue_room_ids=[25],
        phases=[
            H.room_phase([27], room_timing=[_timing(27, "kitchen", KITCHEN_S)],
                         _timing_end_t="2026-08-01T20:53:46Z"),
            H.break_phase("charge_wait", room_timing=[],
                          _timing_end_t="2026-08-01T21:03:10Z",
                          target_battery_percent=100),
            H.room_phase([25], room_timing=[_timing(25, "hallway", HALLWAY_S)],
                         _timing_end_t="2026-08-01T21:07:49Z"),
        ],
        current_phase_index=2,
        # the device counter as the last phase left it — the clobbered value
        last_cleaning_time_seconds=HALLWAY_S,
        last_cleaning_area_m2=5.8,
        last_station_water_percent=90.0,
    )
    mgr.data["active_jobs"] = {H.VAC: {H.MAP: job}}

    inputs = LearningJobFinalizer(hass)._collect_finalization_inputs(
        manager=mgr,
        vacuum_entity_id=H.VAC,
        map_id=H.MAP,
        battery_start=98,
        started_at="2026-08-01T20:49:21Z",
        ended_at="2026-08-01T21:08:50Z",
        forced_outcome_status=None,
        forced_lifecycle_state=None,
        forced_lifecycle_message=None,
    )
    derived = inputs.get("cleaning_time_seconds")

    proof.case(
        "a 3-phase run whose phases measured 255 s and 302 s — what does "
        "finalization derive as the job's cleaning time?",
        before=derived == HALLWAY_S,
        before_msg=f"the job records ONLY its last phase — {HALLWAY_S} s against "
                   f"{TOTAL_S} s actually measured, 46 % short; every dispatched "
                   f"phase resets the device counter and finalization reads the "
                   f"last value it left behind",
        after=derived == TOTAL_S,
        after_msg=f"the job total is the sum of its phases ({TOTAL_S} s)",
        detail=f"derived cleaning_time_seconds={derived} · phases measured "
               f"{KITCHEN_S} + {HALLWAY_S} = {TOTAL_S}",
    )
    return derived


def case_overhead_cascade(proof: H.Proof, derived: int | None) -> None:
    """The consumer. compute_overhead_observed is CORRECT given a correct input —
    it is driven here with whatever the seam above produced, so this case flips
    as a consequence of the repair rather than needing one of its own."""
    job_block = {"duration_minutes": DURATION_MIN,
                 "cleaning_time_seconds": derived,
                 "recharge_seconds_accumulated": 0}
    got = compute_overhead_observed(job_block).get("total_overhead_minutes")
    truth = round(max(DURATION_MIN - TOTAL_S / 60.0, 0.0), 2)
    inflated = round(max(DURATION_MIN - HALLWAY_S / 60.0, 0.0), 2)

    proof.case(
        "the overhead this run hands to the learning model",
        # `truth` and `inflated` are COMPUTED, never typed-in constants — an
        # earlier draft hardcoded 10.19 and the UNEXPECTED arm caught it (the
        # value rounds to 10.2). A proof pinning a derived number to a literal
        # asserts the author's arithmetic, not production's.
        before=got == inflated and got > truth,
        before_msg="overhead inflated by exactly the missing cleaning time — "
                   "stats_rebuilder averages total_overhead_minutes across jobs, "
                   "so every stepped run permanently skews the model the card's "
                   "ETAs come from",
        after=got == truth,
        after_msg="overhead is the residual against the run's real cleaning time",
        detail=f"total_overhead_minutes={got} · inflated={inflated} · "
               f"truth against {TOTAL_S} s={truth} (duration={DURATION_MIN})",
    )


def main() -> int:
    proof = H.Proof("RP-013f", "a stepped run's cleaning time is the whole run")
    case_fixture_matches_hardware(proof)
    derived = case_job_total_is_last_phase(proof)
    case_overhead_cascade(proof, derived)
    return proof.finish()


if __name__ == "__main__":
    H.run(main)
