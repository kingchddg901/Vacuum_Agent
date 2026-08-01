"""Proof RP-013a (RF-11 part 1) — a break phase is read as a capture failure.

phase_runner._capture_finishing_phase_timing DELIBERATELY writes
room_timing = [] for a dock-polled phase (charge_wait / wait): "record an EMPTY
timing so finalize reads it as a dock/hold interval, not a phantom zero-metric
room". Zone phases do the same.

build_completed_job_payload then does:

    _rt = _p.get("room_timing")
    if _rt:  _phase_room_timings.extend(_rt)
    else:    _every_phase_captured = False     # ← [] is falsy

so the writer's intentional empty is indistinguishable from "the segmenter
failed". EVERY stepped run therefore records transit_capture_valid=False, and
the learner falls back to an even wall-time split that includes the dock time
the break phase exists to represent.

VALIDITY (packet): the fixture mirrors the REAL writer shape — room_timing=[]
plus the _timing_end_t stamp the writer sets, with no synthetic marker the
writer never emits. Both CLEANING phases carry good per-room timings, so the
only thing that can invalidate the run is the break phase.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_phase_validity.py
"""

from __future__ import annotations

import sys
import tempfile

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402


def _timing(room_id: int, seconds: int, start: str, end: str) -> dict:
    return {
        "room_id": room_id, "slug": f"room_{room_id}",
        "cleaning_start": start, "cleaning_end": end,
        "cleaning_seconds": seconds, "cleaning_wall_seconds": seconds,
        "area_m2": 4.0, "battery_delta": 1, "boundary": "phase",
    }


def main() -> int:
    proof = H.Proof("RP-013a", "phase-type-aware capture validity")
    store = H.learning_store(tempfile.mkdtemp(prefix="_proof_pv_"))

    # A real stepped run: clean room 1 → charge to 90% → clean room 2.
    # Phase 1 is written EXACTLY as _capture_finishing_phase_timing writes it.
    phases = [
        H.room_phase([1], room_timing=[_timing(1, 120, "2026-08-01T00:00:00Z",
                                               "2026-08-01T00:02:00Z")],
                     _timing_end_t="2026-08-01T00:02:00Z"),
        H.break_phase("charge_wait", room_timing=[],
                      _timing_end_t="2026-08-01T00:20:00Z",
                      target_battery_percent=90),
        H.room_phase([2], room_timing=[_timing(2, 180, "2026-08-01T00:20:00Z",
                                               "2026-08-01T00:23:00Z")],
                     _timing_end_t="2026-08-01T00:23:00Z"),
    ]
    active = H.active_job(queue_room_ids=[1, 2], phases=phases,
                          current_phase_index=2)

    payload = store.build_completed_job_payload(
        vacuum_entity_id=H.VAC, job_id="job_stepped",
        started_at="2026-08-01T00:00:00Z", ended_at="2026-08-01T00:23:00Z",
        battery_start=95, battery_end=80,
        queue_state={"queue_room_ids": [1, 2],
                     "queue_rooms": [{"room_id": 1, "slug": "room_1"},
                                     {"room_id": 2, "slug": "room_2"}]},
        payload_state={}, active_job_state=active,
    )

    job = payload.get("job", {}) if isinstance(payload, dict) else {}
    valid = job.get("transit_capture_valid")
    timings = job.get("room_timings", [])
    secs = {t.get("room_id"): t.get("cleaning_seconds") for t in timings}
    # the two cleaning phases carried DIFFERENT real durations (120 vs 180);
    # an even split would erase that distinction
    distinct = len({v for v in secs.values() if v}) > 1

    proof.case(
        "a stepped run: room → charge_wait → room, both room phases captured cleanly",
        before=valid is False,
        before_msg="transit_capture_valid=False for stepped run — the break "
                   "phase's intentional empty room_timing was read as a capture "
                   "failure, so the whole run is flagged invalid and the learner "
                   "falls back to an even split that includes the charge time",
        after=valid is True,
        after_msg="transit_capture_valid=True — a non-cleaning phase with an "
                  "empty room_timing is VALID-EMPTY, not a failure",
        detail=f"transit_capture_valid={valid!r} · per-room seconds={secs} "
               f"· real per-room durations preserved in the record={distinct}",
    )

    # The record itself keeps the real timings (the concatenation branch runs);
    # it is the VALIDITY FLAG that poisons what the learner does with them.
    proof.case(
        "the per-room evidence itself survives — only the flag is wrong",
        before=distinct and valid is False,
        # NOTE the claim boundary: this proof observes the RECORD, not the
        # learner. It shows the real 120s/180s survive while the flag says not to
        # trust them. What the learner then does with an invalid capture (the
        # even wall-time split) is downstream and NOT observed here — stating it
        # as though it were measured is the "faithful where it actuates,
        # unfaithful where it qualifies" pattern Audit #6 named.
        before_msg="the record still holds the real 120s/180s, but "
                   "transit_capture_valid=False tells every consumer not to "
                   "trust them — the evidence survives and is then disregarded",
        after=distinct and valid is True,
        after_msg="per-room timings preserved AND trusted",
        detail=f"room_timings entries={len(timings)} · seconds by room={secs}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
