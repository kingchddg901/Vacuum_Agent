"""Proof RP-013c (RF-11 part 2) — completed evidence does not survive a phase advance.

  1. MISSED = EVERY ROOM. advance_active_job_phase resets completed_room_ids so
     each phase is a fresh sub-job, and nothing accumulates the finished phases'
     evidence at job level. _write_incomplete_run_log computes
         missed = queue_room_ids − active_job_state["completed_room_ids"]
     against the CURRENT phase's (reset) list, so a 3-phase run cancelled in
     phase 2 reports phase 1's genuinely-cleaned rooms as missed. Retry
     automations then re-clean rooms that were already done.

  2. UNRELATED CLEAR. _write_incomplete_run_log clears the log on ANY normal
     completion, with no check that the completing job's rooms overlap the
     logged ones — a one-room Kitchen clean erases a log about a different run's
     missed Bedroom and Den.

Case 3 is the RP-013d extension (#16:A4-STATE-6), per that packet:

  3. THE QUEUE BLOCK IS LIVE-FIRST. build_completed_job_payload resolves the
     record's room identity job-frozen-first — a long comment above it records
     the incident that forced that ladder (a Kitchen+Hallway+zone run recorded as
     Dining+Kitchen+Hallway after rooms were re-queued on top of it). The `queue`
     block twenty lines below inverts it: `queue_state if queue_state has
     queue_room_ids else the job's own`. Live wins. A queue flipped mid-run makes
     the record's own two halves disagree, and every missed/trouble-room consumer
     reads the queue half.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_completed_evidence.py
"""

from __future__ import annotations

import sys
import tempfile

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.learning.job_finalizer import LearningJobFinalizer   # noqa: E402
from custom_components.eufy_vacuum.queue.queue_engine import advance_active_job_phase   # noqa: E402


def _finalizer(tmp):
    return LearningJobFinalizer(H.make_hass(tmp))


def case_missed_every_room(proof: H.Proof) -> None:
    fin = _finalizer(tempfile.mkdtemp(prefix="_proof_ce1_"))

    # A 3-phase run. Phase 1 (room 1) COMPLETED, phase 2 (room 2) was under way
    # when the user cancelled; room 3's phase never started.
    job = H.active_job(
        queue_room_ids=[1, 2, 3],
        phases=[H.room_phase([1]), H.room_phase([2]), H.room_phase([3])],
        current_phase_index=0,
        completed_room_ids=[1],       # phase 1 finished room 1
    )
    # the advance into phase 2 — the real engine, the real reset
    job = advance_active_job_phase(job) or job
    evidence_after_advance = list(job.get("completed_room_ids", []))
    cumulative = job.get("completed_room_ids_cumulative")

    completed_job = {
        "outcome": {"status": "cancelled"},
        "queue": {"queue_room_ids": [1, 2, 3]},
        "resolved_rooms": [{"room_id": r, "name": f"Room {r}"} for r in (1, 2, 3)],
    }
    written = fin._write_incomplete_run_log(
        vacuum_entity_id=H.VAC, map_id=H.MAP,
        completed_job=completed_job, active_job_state=job,
        ended_at="2026-08-01T00:30:00Z",
    )
    missed = sorted((written or {}).get("missed_room_ids", []))

    proof.case(
        "3-phase run, phase 1 completed, cancelled during phase 2",
        before=missed == [1, 2, 3] and cumulative is None,
        before_msg="missed = every room — phase 1's completed room 1 was erased "
                   "by the advance and no job-level cumulative exists, so a "
                   "retry automation re-cleans a room that was already done",
        after=missed == [2, 3] and cumulative is not None,
        after_msg="missed = only unfinished — the cumulative evidence carried "
                  "phase 1's completion across the advance",
        detail=f"missed_room_ids={missed} · completed_room_ids after advance="
               f"{evidence_after_advance} · cumulative field={cumulative!r}",
    )


def case_unrelated_clear(proof: H.Proof) -> None:
    fin = _finalizer(tempfile.mkdtemp(prefix="_proof_ce2_"))

    # An earlier run stranded the Bedroom and the Den; the log records that.
    fin._write_incomplete_run_log(
        vacuum_entity_id=H.VAC, map_id=H.MAP,
        completed_job={
            "outcome": {"status": "cancelled"},
            "queue": {"queue_room_ids": [5, 6]},
            "resolved_rooms": [{"room_id": 5, "name": "Bedroom"},
                               {"room_id": 6, "name": "Den"}],
        },
        active_job_state={"completed_room_ids": []},
        ended_at="2026-08-01T00:30:00Z",
    )
    logged_before = fin.store.load_incomplete_run(vacuum_entity_id=H.VAC)

    # Now the user runs the KITCHEN (room 1) and it completes normally.
    fin._write_incomplete_run_log(
        vacuum_entity_id=H.VAC, map_id=H.MAP,
        completed_job={
            "outcome": {"status": "completed"},
            "queue": {"queue_room_ids": [1]},
            "resolved_rooms": [{"room_id": 1, "name": "Kitchen"}],
        },
        active_job_state={"completed_room_ids": [1]},
        ended_at="2026-08-01T01:00:00Z",
    )
    logged_after = fin.store.load_incomplete_run(vacuum_entity_id=H.VAC)

    had_log = isinstance(logged_before, dict) and bool(
        logged_before.get("missed_room_ids"))

    proof.case(
        "a one-room Kitchen clean completes while a log about Bedroom+Den exists",
        before=had_log and logged_after is None,
        before_msg="unrelated clear erased log — the completion cleared the log "
                   "without checking that its rooms overlap the missed ones, so "
                   "the Bedroom and Den strand is silently forgotten",
        after=had_log and isinstance(logged_after, dict)
        and sorted(logged_after.get("missed_room_ids", [])) == [5, 6],
        after_msg="log survives non-overlapping clear — only a run covering the "
                  "logged rooms may clear them",
        detail=f"log before={sorted((logged_before or {}).get('missed_room_ids', []))} "
               f"· after an unrelated completion={logged_after if logged_after is None else sorted(logged_after.get('missed_room_ids', []))}",
    )


def case_queue_block_is_live_first(proof: H.Proof) -> None:
    """RP-013d — the record's queue half follows the LIVE queue, its room half
    follows the job. Flip the queue mid-run and the two halves disagree."""
    store = H.learning_store(tempfile.mkdtemp(prefix="_proof_ce3_"))

    # The run that actually launched: Kitchen (1) + Hallway (2).
    job = H.active_job(queue_room_ids=[1, 2], room_count=2)
    job["queue_rooms"] = [{"room_id": 1, "name": "Kitchen"},
                          {"room_id": 2, "name": "Hallway"}]

    # Mid-run the user queues the Den (7) for later. The composer re-hydrates the
    # LIVE queue; the running job's own snapshot is untouched.
    live_queue = {
        "vacuum_entity_id": H.VAC,
        "map_id": H.MAP,
        "room_count": 1,
        "queue_room_ids": [7],
        "queue_rooms": [{"room_id": 7, "name": "Den"}],
    }

    payload = store.build_completed_job_payload(
        vacuum_entity_id=H.VAC,
        job_id="job_proof",
        started_at="2026-08-01T00:00:00Z",
        ended_at="2026-08-01T00:40:00Z",
        battery_start=90,
        battery_end=64,
        queue_state=live_queue,
        payload_state={},
        active_job_state=job,
        outcome_status="cancelled",
        was_cancelled=True,
    )
    recorded_queue = list((payload.get("queue") or {}).get("queue_room_ids", []))
    recorded_rooms = sorted(
        r.get("room_id") for r in payload.get("resolved_rooms", [])
        if isinstance(r, dict)
    )

    proof.case(
        "RP-013d — the Den is queued for LATER while the Kitchen+Hallway run is "
        "still going, then that run is cancelled",
        before=recorded_queue == [7] and recorded_rooms == [1, 2],
        before_msg="the queue block took the LIVE queue — the record now "
                   "contradicts itself (rooms 1,2 · queue 7), and because every "
                   "missed/trouble-room consumer reads the queue half, the run "
                   "reports the Den as missed: a room it was never asked to clean",
        after=recorded_queue == [1, 2] and recorded_rooms == [1, 2],
        after_msg="the queue block mirrors the resolved_rooms ladder — the job's "
                  "own frozen queue wins and the record's halves agree",
        detail=f"payload queue_room_ids={recorded_queue} vs "
               f"resolved_rooms={recorded_rooms} (the job launched with [1, 2]; "
               f"the live queue holds [7])",
    )


def main() -> int:
    proof = H.Proof("RP-013c/d", "job-cumulative completed evidence")
    case_missed_every_room(proof)
    case_unrelated_clear(proof)
    case_queue_block_is_live_first(proof)
    return proof.finish()


if __name__ == "__main__":
    H.run(main)
