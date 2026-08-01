"""Proof RP-010 (RF-06) — cancel/pause are not effective at the dispatch chokepoint.

Three cases from the packet:

  1. CHOKEPOINT — _dispatch_active_phase performs four sequential awaits
     (pre-calls → per-room settings → live resolve → wire send) and never
     re-reads the job. A cancel that lands mid-chain still ends in a wire send.
  2. DOUBLE CANCEL — async_cancel_active_job has no single-flight latch. A
     second cancel inside the 30s terminal-confirm window runs the whole body
     again and re-finalizes with finalize_result=None, nulling finalize_summary.
  3. GATE DURING CANCEL — maybe_advance_phase does not consult _cancel_in_flight,
     so the cancel's own return-to-base dock reads as phase completion and the
     job advances mid-cancel.

VALIDITY (packet's validity_notes): case 1 must block INSIDE the await chain,
not before entry. Blocking before entry is caught by the existing
top-of-attempt check in _run_advanced_phase and would pass pre-repair for the
wrong reason. Here the block sits in the THIRD await (live resolve), with two
awaits already behind it — the real four-await window.

The function under test is real in every case; only its collaborators are inert
stubs (harness inertness rule).

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_cancel_chokepoint.py
"""

from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.jobs.phase_runner import PhaseRunner   # noqa: E402
from custom_components.eufy_vacuum.jobs.active_job import ActiveJobTracker   # noqa: E402


def _manager_with_job(job: dict) -> H.ManagerStub:
    hass = H.make_hass()
    mgr = H.ManagerStub(hass=hass)
    mgr.data["active_jobs"] = {H.VAC: {H.MAP: job}}
    H.seed_map(mgr, H.managed_rooms(1, 2))
    return mgr


# ---------------------------------------------------------------------------
# Case 1 — the chokepoint
# ---------------------------------------------------------------------------

async def case_chokepoint(proof: H.Proof) -> None:
    job = H.active_job(
        queue_room_ids=[1, 2],
        phases=[H.room_phase([1]), H.room_phase([2])],
        current_phase_index=0,
        _phase_dispatch_pending=True,
    )
    mgr = _manager_with_job(job)
    runner = PhaseRunner(manager=mgr)

    resolve_entered = asyncio.Event()
    release_resolve = asyncio.Event()
    wire_sends: list[dict] = []

    # --- the four collaborators _dispatch_active_phase awaits, in order ---
    mgr._run_global_pre_calls = H.async_noop()
    mgr.active_job = type("AJ", (), {
        "apply_per_room_live_settings_awaited": staticmethod(H.async_noop()),
    })()

    async def _blocking_resolve(**kw):
        # THIRD await: two awaits are already behind us, so a top-of-attempt
        # check cannot rescue this — the packet's validity requirement.
        resolve_entered.set()
        await release_resolve.wait()
        return kw.get("payload", {})

    async def _record_send(**kw):
        wire_sends.append(kw.get("payload", {}))

    mgr._resolve_live_dispatch_payload = _blocking_resolve
    mgr._dispatch_clean_payload = _record_send

    dispatch_task = asyncio.create_task(runner._dispatch_active_phase(
        vacuum_entity_id=H.VAC, map_id=H.MAP, job=job, attempt=1,
    ))
    await resolve_entered.wait()

    # the user hits Cancel while the dispatch is suspended mid-chain
    stored = mgr.stored_job()
    stored["_cancel_in_flight"] = True
    stored["_phase_dispatch_pending"] = False

    release_resolve.set()
    await dispatch_task

    proof.case(
        "cancel lands while _dispatch_active_phase is suspended at await 3 of 4",
        before=len(wire_sends) == 1,
        before_msg="dispatch landed after cancel — the clean was sent to the "
                   "wire although _cancel_in_flight was set before the send",
        after=len(wire_sends) == 0,
        after_msg="dispatch aborted at chokepoint — the stored job was re-read "
                  "after the last await and the send was skipped",
        detail=f"wire sends after cancel: {len(wire_sends)}",
    )


# ---------------------------------------------------------------------------
# Case 2 — second cancel in the confirm window
# ---------------------------------------------------------------------------

async def case_double_cancel(proof: H.Proof) -> None:
    job = H.active_job(
        queue_room_ids=[1],
        phases=[H.room_phase([1])],
        current_phase_index=0,
        finalize_summary={"job_id": "job_proof", "job_path": "/x/job_proof.json"},
    )
    mgr = _manager_with_job(job)
    tracker = ActiveJobTracker(mgr)
    mgr.active_job = tracker

    # Confirm immediately: the device is already docked, so the poll loop breaks
    # on its first iteration instead of burning the 30s timeout.
    mgr.hass.states.async_set(H.VAC, "docked")
    ActiveJobTracker._CANCEL_POLL_INTERVAL_S = 0.0   # fixture: keep the proof fast

    # Model finalize as RP-001 actually leaves it: the FIRST call succeeds and
    # returns a record-shaped dict; a SECOND call hits the exactly-once claim and
    # returns a refusal dict. That distinction is the mechanism —
    # mark_active_job_finalized only rewrites finalize_summary when it receives a
    # DICT, and a refusal dict carries no job_id/job_path, so the summary is
    # overwritten with Nones. (A first draft of this proof stubbed None for both
    # calls; the summary then survived and the case reported UNEXPECTED, which is
    # how the mis-model was caught.)
    finalize_calls = {"n": 0}

    async def _finalize(**kw):
        finalize_calls["n"] += 1
        if finalize_calls["n"] == 1:
            return {"job_id": "job_proof", "job_path": "/x/job_proof.json",
                    "finalized": True, "completed_job": {"finalized_at": "2026-08-01T00:10:00Z"}}
        return {"finalized": False, "reason": "already_finalized"}

    mgr.finalize_learning_for_active_job = _finalize
    mgr.async_save = H.async_noop()
    mgr._async_save_logged = H.async_noop()

    first = asyncio.create_task(tracker.async_cancel_active_job(
        vacuum_entity_id=H.VAC, map_id=H.MAP))
    await asyncio.sleep(0)          # let the first cancel enter its body
    second = await tracker.async_cancel_active_job(
        vacuum_entity_id=H.VAC, map_id=H.MAP)
    await first

    stored = mgr.stored_job()
    summary = stored.get("finalize_summary")
    reason = str(second.get("reason") or "")
    summary_nulled = isinstance(summary, dict) and summary.get("job_id") is None

    proof.case(
        "a second cancel arrives inside the first cancel's confirm window",
        before=reason != "cancel_in_progress" and summary_nulled,
        before_msg="second cancel nulled summary — it ran the whole body again "
                   "and overwrote finalize_summary from the claim's refusal dict",
        after=reason == "cancel_in_progress",
        after_msg="second cancel refused: cancel_in_progress — the single-flight "
                  "latch held and the summary survived",
        detail=f"second cancel reason={reason!r} · finalize_summary={summary!r}",
    )


# ---------------------------------------------------------------------------
# Case 3 — completion gate advances during the cancel window
# ---------------------------------------------------------------------------

async def case_gate_during_cancel(proof: H.Proof) -> None:
    job = H.active_job(
        queue_room_ids=[1, 2],
        phases=[H.room_phase([1]), H.room_phase([2])],
        current_phase_index=0,
        _cancel_in_flight=True,          # a cancel is in flight RIGHT NOW
        _phase_dispatch_pending=False,   # cancel already released it (by design)
    )
    mgr = _manager_with_job(job)
    runner = PhaseRunner(manager=mgr)
    mgr._run_global_pre_calls = H.async_noop()
    mgr._resolve_live_dispatch_payload = H.async_noop({})
    mgr._dispatch_clean_payload = H.async_noop()
    mgr.async_save = H.async_noop()
    # the advance spawns the next phase's watchdog, which reads this
    mgr._phase_timing = lambda _vac: {
        "settle_seconds": 0, "dock_settle_seconds": 0, "verify_seconds": 0,
        "confirm_seconds": 0, "poll_seconds": 0, "max_attempts": 1,
    }

    advanced = await runner.maybe_advance_phase(
        vacuum_entity_id=H.VAC, map_id=H.MAP)
    await H._block_till_done()
    idx = mgr.stored_job().get("current_phase_index", 0)

    proof.case(
        "the cancel's own return-to-base dock reaches the completion gate",
        before=advanced is True and idx == 1,
        before_msg="gate advanced during cancel window — the job moved to "
                   "phase 2 while a cancel owned finalization",
        after=advanced is False and idx == 0,
        after_msg="gate held during cancel — maybe_advance_phase suppressed on "
                  "_cancel_in_flight; the cancel path owns finalization",
        detail=f"maybe_advance_phase returned {advanced} · phase index now {idx}",
    )


async def main() -> int:
    proof = H.Proof("RP-010", "cancel/pause effective at the dispatch chokepoint")
    await case_chokepoint(proof)
    await case_double_cancel(proof)
    await case_gate_during_cancel(proof)
    return proof.finish()


if __name__ == "__main__":
    H.run(main)
