"""Proof RP-037 (RF-29) — SNAP-2: the dashboard snapshot is neither pure nor composed once.

The packet's reproducer_script names two things. The mkdir half ("32 mkdir calls per
snapshot" -> "0 mkdir on warm path") is already driven by `_proof_ensure_dirs_memo.py`;
this drives the other half, SNAP-2: "get_dashboard_snapshot composes the progress payload
ONCE (memoized within the call) and the side-effecting rollover/anomaly steps HOIST to the
tick path (listener), leaving the snapshot pure". Together the two files satisfy the
script. The remaining seven finding_ids (ROBORO-2, GEO-2, ONB-5, DRAFT-5, TRK-7) are
independent and not driven here.

RP-037 is marked `blocked_by RP-013c`. That block cleared when RP-013c landed
(0ff4a8a) — the dependency was on RP-013's progress-path changes, which are now in.

  1. A READ PATH FIRES EVENTS AND PERSISTS. get_job_progress_snapshot — a card poll,
     nothing more — calls detect_run_anomalies, which does
     `self._manager.hass.bus.async_fire(...)` AND writes `_stall_notified_room_ids`
     back into `_manager.data["active_jobs"]` (jobs/active_job.py:70-77). Whether an
     automation ever sees a stall event therefore depends on whether a card happened to
     be open and polling. The once-per-room dedup guard makes this look harmless — the
     second read does not re-fire — but the guard is itself state written from a read,
     and it means THE CARD'S POLL CONSUMES THE EVENT. A tick that fires afterwards finds
     the room already notified.

  2. AND THE PAYLOAD IS COMPOSED TWICE PER POLL. get_dashboard_snapshot calls
     get_job_progress_snapshot directly, then calls get_job_control_state, which calls
     get_job_progress_snapshot again. Two full composes — and, before clause (1) lands,
     two runs of the side-effecting anomaly pass — for one card poll.

     Case 2 reads the CURRENT source rather than asserting against copied line numbers,
     so it cannot quietly pass after a refactor moves the calls. That is the same
     technique `_proof_blocker_unavailable.py` uses.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_loop_hygiene.py
"""

from __future__ import annotations

import inspect
import re
import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.core import manager as manager_mod   # noqa: E402
from custom_components.eufy_vacuum.jobs.active_job import ActiveJobTracker   # noqa: E402


def case_read_path_fires_and_persists(proof: H.Proof) -> None:
    hass = H.make_hass()
    mgr = H.ManagerStub(hass=hass)

    # A job whose current room is well past its timing estimate and whose rollover is
    # blocked by the bounds gate — the exact live condition a stall describes.
    job = H.active_job(queue_room_ids=[5], current_room_id=5, status="started")
    mgr.data.setdefault("active_jobs", {}).setdefault(H.VAC, {})[str(H.MAP)] = job

    tracker = ActiveJobTracker(mgr)
    result = tracker.detect_run_anomalies(
        vacuum_entity_id=H.VAC, map_id=H.MAP, active_job=job,
        # minutes=2.0 with low confidence -> threshold ~2.4 min; 30 min elapsed is
        # far past threshold * stall_ratio (2.0), so the stall branch is entered.
        raw_timeline=[{"room_id": 5, "minutes": 2.0, "confidence_score": 0.3,
                       "sample_count": 4}],
        current_room_id=5,
        current_room_elapsed_minutes=30.0,
        completed_room_ids=[],
        awaiting_bounds_exit=True,
    )

    fired = list(hass.bus.events)
    persisted = mgr.data["active_jobs"][H.VAC][str(H.MAP)].get("_stall_notified_room_ids")

    proof.case(
        "one card poll over a stalled room — a pure read by contract",
        before=bool(fired) and bool(persisted),
        before_msg="events fired from the read path, and the read wrote state — "
                   "whether an automation ever sees a stall depends on whether a card "
                   "was open and polling, and the card's poll CONSUMES the "
                   "once-per-room event",
        after=not fired and not persisted,
        after_msg="the snapshot is a pure read; the anomaly emit + notified-room "
                  "bookkeeping are hoisted to the tick path",
        detail=f"stall_detected={result.get('stall_detected')} · events fired="
               f"{[t for t, _ in fired]} · _stall_notified_room_ids persisted="
               f"{persisted!r}",
    )


def _calls_to(fn_name: str, source: str) -> int:
    return len(re.findall(rf"self\.{fn_name}\s*\(", source))


def case_progress_composed_twice(proof: H.Proof) -> None:
    """Read the shipped source; do not assert against copied line numbers."""
    cls = manager_mod.EufyVacuumManager
    dashboard = inspect.getsource(cls.get_dashboard_snapshot)
    control = inspect.getsource(cls.get_job_control_state)

    direct = _calls_to("get_job_progress_snapshot", dashboard)
    via_control = _calls_to("get_job_progress_snapshot", control)
    calls_control = _calls_to("get_job_control_state", dashboard)
    total = direct + (via_control * calls_control)

    proof.case(
        "how many times one get_dashboard_snapshot composes the progress payload",
        before=total >= 2,
        before_msg="progress composed twice — directly, and again inside "
                   "get_job_control_state; before clause (1) lands that is also two "
                   "runs of the side-effecting anomaly pass per poll",
        after=total == 1,
        after_msg="single compose — memoized within the call and shared by the "
                  "consumers that need it",
        detail=f"get_dashboard_snapshot calls it {direct}x directly and calls "
               f"get_job_control_state {calls_control}x, which calls it "
               f"{via_control}x -> {total} composes per poll",
    )


def main() -> None:
    proof = H.Proof("RP-037", "SNAP-2 — the dashboard snapshot is neither pure nor composed once")
    case_read_path_fires_and_persists(proof)
    case_progress_composed_twice(proof)
    proof.finish()


H.run(main)
