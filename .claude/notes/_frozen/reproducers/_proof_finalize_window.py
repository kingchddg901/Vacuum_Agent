"""Proof (RP-001 / HW-FINAL-1): the exactly-once finalize claim releases before the
permanent gate is written, so a second entrant that arrives after the first call
RETURNS — but before the caller's mark_active_job_finalized — runs the body again.

Models the interleave proven on hardware (ivy-run-BEFORE.log, job_2026-07-31T20-14-28
double emission at 20:16:13.339/.342): listeners/lifecycle.py L316 awaits the finalize
(claim taken and RELEASED in its finally), then L334's executor hop yields the loop,
and only L349 writes finalized=True. Task B fires in that yield.

VALIDITY (REVIEW-04 trap): task B must run AFTER task A has fully returned — B blocks
on an event A sets after its await completes. A version where B enters during A's body
only exercises the in-flight refusal, which already works, and would pass for the
wrong reason.

Run: docker eufy-vacuum-test -> python .claude/notes/_proof_finalize_window.py
"""
import asyncio
import sys
from types import SimpleNamespace

from custom_components.eufy_vacuum.learning.manager import LearningManager


def make_hass():
    return SimpleNamespace(
        config=SimpleNamespace(config_dir="/tmp/_proof_hass", path=lambda *p: "/tmp/_proof_hass"),
        data={},
    )


async def main() -> int:
    lm = LearningManager(make_hass())

    # A minimal manager: the claim only touches manager.data.
    manager = SimpleNamespace(data={
        "active_jobs": {"vacuum.ivy": {"Main floor": {
            "vacuum_entity_id": "vacuum.ivy",
            "map_id": "Main floor",
            "status": "completed",
            "started_at": "2026-08-01T03:14:28Z",
            "battery_start": 96,
        }}}
    })

    body_runs = 0

    async def counting_body(**kwargs):
        nonlocal body_runs
        body_runs += 1
        # the real body awaits (file IO on the executor) between claim and return
        await asyncio.sleep(0)
        return {
            "vacuum_entity_id": kwargs.get("vacuum_entity_id"),
            "map_id": kwargs.get("map_id"),
            "finalized": True,
            "completed_job": {"job_id": "job_proof", "record_type": "completed_job"},
        }

    lm._finalize_claimed = counting_body

    kw = dict(
        manager=manager,
        vacuum_entity_id="vacuum.ivy",
        map_id="Main floor",
        battery_start=96,
        battery_end=95,
        started_at="2026-08-01T03:14:28Z",
    )

    a_returned = asyncio.Event()
    results: list[dict] = []

    async def task_a():
        r = await lm.async_finalize_completed_job(**kw)
        results.append(r)
        # A has FULLY returned: claim popped by the finally. The caller's
        # mark_active_job_finalized has NOT run yet (lifecycle.py L334 executor hop).
        a_returned.set()

    async def task_b():
        await a_returned.wait()
        r = await lm.async_finalize_completed_job(**kw)
        results.append(r)

    await asyncio.gather(task_a(), task_b())

    stored = manager.data["active_jobs"]["vacuum.ivy"]["Main floor"]
    reasons = [str(r.get("reason", "")) for r in results if isinstance(r, dict)]
    refusals = [x for x in reasons if x in ("finalize_in_flight", "already_finalized")]
    completed = sum(1 for r in results if isinstance(r, dict) and r.get("completed_job"))

    print(f"stored job after both calls: finalized={stored.get('finalized')!r} "
          f"claim={stored.get('finalize_claimed_at')!r}")
    print(f"completed_job results returned: {completed}")

    if body_runs == 2:
        print("BODY RAN 2 TIMES")
        print("the second entrant found: no claim (released by A's finally), no "
              "finalized (the caller writes it later) -> claim taken again")
    elif body_runs == 1 and "already_finalized" in reasons:
        print("BODY RAN 1 TIME")
        print("second call refused: already_finalized")
    else:
        print(f"UNEXPECTED SHAPE: body_runs={body_runs} reasons={reasons}")
        return 1
    for x in refusals:
        print(f"refusal observed: {x}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
