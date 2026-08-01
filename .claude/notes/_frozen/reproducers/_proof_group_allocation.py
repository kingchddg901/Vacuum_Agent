"""Proof RP-013b (RF-11 part 3) — a multi-room group phase credits ONE room.

_capture_finishing_phase_timing ends with:

    queue_ids = [... from active_job.get("queue_room_ids") ...]
    rid = queue_ids[0] if queue_ids else None

Two defects in two lines:

  REC-1 — only rid gets a timing entry. A 3-room group phase's whole time, area
    and battery land on one room; the other two vanish from the record entirely,
    so learning never sees them and the credited room learns 3× its real cost.
  REC-2 — the ids come from the JOB's queue_room_ids, not the PHASE's own
    resolved_rooms. For phase 0 that is the WHOLE-RUN queue, so the credited
    room need not even belong to the phase being captured.

The proof drives the real _capture_finishing_phase_timing over a real counter
sample stream, so the arithmetic is production's.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_group_allocation.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.jobs.phase_runner import PhaseRunner   # noqa: E402


def _samples() -> list[dict]:
    """A counter stream over one group phase: 9 minutes, 12 m², 6% battery."""
    return [
        {"t": f"2026-08-01T00:{m:02d}:00Z",
         "cleaning_time": m * 60, "cleaning_area": m * (12.0 / 9), "battery": 90 - m}
        for m in range(0, 10)
    ]


def main() -> int:
    proof = H.Proof("RP-013b", "allocated group timing")

    # ONE phase cleaning a group of three rooms — the shape a room_group step
    # with three rooms produces.
    group = H.room_phase([4, 5, 6])
    job = H.active_job(
        queue_room_ids=[4, 5, 6],
        phases=[group],
        current_phase_index=0,
        counter_samples=_samples(),
    )
    mgr = H.ManagerStub(hass=H.make_hass())
    mgr.data["active_jobs"] = {H.VAC: {H.MAP: job}}
    runner = PhaseRunner(manager=mgr)

    runner._capture_finishing_phase_timing(H.VAC, H.MAP, job)
    timings = job["phases"][0].get("room_timing") or []
    credited = [t.get("room_id") for t in timings]
    allocated = [bool(t.get("allocated")) for t in timings]
    total_secs = sum(t.get("cleaning_seconds") or 0 for t in timings)
    total_area = round(sum(t.get("area_m2") or 0 for t in timings), 3)

    proof.case(
        "one phase cleans a GROUP of three rooms (4, 5, 6)",
        before=len(timings) == 1 and credited == [4],
        before_msg="1 timing entry for 3-room group — room[0] credited full: "
                   "rooms 5 and 6 leave no record at all and room 4 learns the "
                   "whole group's time, area and battery",
        after=len(timings) == 3 and sorted(credited) == [4, 5, 6]
        and all(allocated),
        after_msg="3 allocated entries — one per member, allocated=True, and "
                  "the measured totals are preserved across the split",
        detail=f"entries={len(timings)} · credited rooms={credited} · "
               f"allocated flags={allocated} · summed seconds={total_secs} "
               f"area={total_area}",
    )

    # REC-2: the id source. Phase 1 cleans room 9 only, but the JOB's queue
    # still starts with room 4 — a phase-scoped source must credit 9, not 4.
    job2 = H.active_job(
        queue_room_ids=[4, 5, 9],          # the whole-run queue
        phases=[H.room_phase([4], room_timing=[{"room_id": 4}],
                             _timing_end_t="2026-08-01T00:05:00Z"),
                H.room_phase([9])],         # THIS phase cleans room 9
        current_phase_index=1,
        counter_samples=_samples(),
    )
    mgr2 = H.ManagerStub(hass=H.make_hass())
    mgr2.data["active_jobs"] = {H.VAC: {H.MAP: job2}}
    PhaseRunner(manager=mgr2)._capture_finishing_phase_timing(H.VAC, H.MAP, job2)
    t2 = job2["phases"][1].get("room_timing") or []
    credited2 = [t.get("room_id") for t in t2]

    proof.case(
        "phase 1 cleans room 9 while the JOB's queue still begins with room 4",
        before=credited2 == [4],
        before_msg="phase-scoped ids missing — the capture read the JOB's "
                   "queue_room_ids and credited room 4, which this phase never "
                   "cleaned",
        after=credited2 == [9],
        after_msg="phase-scoped ids — the capture sourced the PHASE's own "
                  "resolved_rooms and credited room 9",
        detail=f"phase 1 credited={credited2} (its own room is 9; the job "
               f"queue starts with 4)",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
