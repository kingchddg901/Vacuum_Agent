"""Proof RP-012 (RF-31) — tracker/job lifecycle divergence.

  1. TRK-1 — the mapping tracker is ended only from the lifecycle finalize path's
     finally block. async_cancel_active_job finalizes DIRECTLY, never through
     that listener, so a cancelled job leaves the tracker holding the job
     forever: the next run starts with the previous run's tracker state.
  2. A4-AJ-1 (HIGH) — mid-job recharge NEVER ends. The recharge-end branch is
     unreachable: the function returns early when not charging, so everything
     below runs with _is_charging() True, and the end-check asks the SAME pure
     state read again in the same synchronous block. recharge_seconds_accumulated
     stays 0, observed_mid_job_recharge is never cleared, and resume_sampling is
     never called — the sampler stays paused for the rest of the run.
  3. DQ-PH-6 — advance_active_job_phase resets every per-phase pointer EXCEPT
     _native_current_room_id, leaving the previous phase's room id live as the
     next phase begins.

  4. HOLD MUST NOT ACCRUE — a COMMANDED dock (charge_wait / wait phase) owns its
     own timing; the unplanned-recharge accounting must not also claim it, or the
     planned dock is double-counted as a battery-driven recharge.

PACKET-FRAGMENT NOTE (corrected 2026-08-01): an earlier version of this proof
reported "hold accrued 300s" as matching no finding in RP-012's finding_ids.
That was wrong. The repaired accrual is exactly 300s for a five-minute recharge,
and the fragment refers to case 4 — a commanded hold must NOT accrue that time.
It is a post-repair invariant filed under expected_before in the packet, i.e. a
labelling slip, not a missing finding. No action needed from the author.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_tracker_lifecycle.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.jobs.active_job import ActiveJobTracker   # noqa: E402
from custom_components.eufy_vacuum.mapping.tracker import MappingTracker   # noqa: E402
from custom_components.eufy_vacuum.queue.queue_engine import advance_active_job_phase   # noqa: E402
from custom_components.eufy_vacuum.const import DOMAIN   # noqa: E402


async def case_tracker_after_cancel(proof: H.Proof) -> None:
    hass = H.make_hass()
    mgr = H.ManagerStub(hass=hass)
    tracker = MappingTracker(hass)
    hass.data[DOMAIN] = {"mapping_tracker": tracker}

    job = H.active_job(queue_room_ids=[1], phases=[H.room_phase([1])],
                       current_phase_index=0)
    mgr.data["active_jobs"] = {H.VAC: {H.MAP: job}}
    aj = ActiveJobTracker(mgr)
    mgr.active_job = aj

    tracker.start_job(vacuum_entity_id=H.VAC, map_id=H.MAP,
                      rooms=H.managed_rooms(1))
    held_before = H.VAC in tracker._active_job

    hass.states.async_set(H.VAC, "docked")
    ActiveJobTracker._CANCEL_POLL_INTERVAL_S = 0.0
    mgr.finalize_learning_for_active_job = H.async_noop(
        {"job_id": "job_proof", "finalized": True})
    mgr.async_save = H.async_noop()
    mgr._async_save_logged = H.async_noop()

    await aj.async_cancel_active_job(vacuum_entity_id=H.VAC, map_id=H.MAP)
    await H._block_till_done()
    held_after = H.VAC in tracker._active_job

    proof.case(
        "the job is CANCELLED (not completed) — does the tracker get released?",
        before=held_before and held_after,
        before_msg="tracker stuck after cancel — end_job is only reachable from "
                   "the lifecycle finalize path, which a cancel bypasses; the "
                   "next run inherits this run's tracker state",
        after=held_before and not held_after,
        after_msg="tracker released on cancel — the cancel path ends the job",
        detail=f"tracker held job before cancel={held_before} · after={held_after}",
    )


def case_recharge_never_ends(proof: H.Proof) -> None:
    hass = H.make_hass()
    mgr = H.ManagerStub(hass=hass)
    tracker = MappingTracker(hass)
    hass.data[DOMAIN] = {"mapping_tracker": tracker}
    job = H.active_job(queue_room_ids=[1],
                       observed_mid_job_recharge=True,
                       observed_mid_job_recharge_started_at="2026-08-01T00:00:00Z",
                       pending_mid_job_recharge_return=True,
                       recharge_seconds_accumulated=0)
    mgr.data["active_jobs"] = {H.VAC: {H.MAP: job}}
    aj = ActiveJobTracker(mgr)
    mgr._get_battery_level = lambda _v: 55

    # a recharge is in progress and the sampler is paused
    tracker.pause_sampling(H.VAC)
    aj._is_charging = lambda _v: True
    aj.update_active_job_recharge_observation(
        vacuum_entity_id=H.VAC, map_id=H.MAP,
        observed_at="2026-08-01T00:05:00Z")

    # ...now the robot STOPS charging and resumes cleaning: the recharge ended.
    #
    # SEAM NOTE (RP-012 execution): this case asserts the BEHAVIOUR, not a call
    # site. Pre-repair the only path was a second call to
    # update_active_job_recharge_observation — which could never detect the end,
    # because its own top guard had already proven charging True in the same
    # synchronous call. The repair moved end-resolution to
    # resolve_mid_job_recharge_resumed, driven from the lifecycle tick, where a
    # LATER tick can observe the flipped state. Both are exercised below and the
    # verdict is on the OUTCOME (seconds accrued / flag cleared / sampler
    # resumed), so the proof survives the seam moving. It was rewritten this way
    # only AFTER the new path was independently confirmed to produce 300s — a
    # proof edited to match a repair is otherwise how a bad fix gets laundered.
    aj._is_charging = lambda _v: False
    out = aj.update_active_job_recharge_observation(
        vacuum_entity_id=H.VAC, map_id=H.MAP,
        observed_at="2026-08-01T00:05:00Z")
    resolver = getattr(aj, "resolve_mid_job_recharge_resumed", None)
    if resolver is not None:
        out = resolver(vacuum_entity_id=H.VAC, map_id=H.MAP,
                       observed_at="2026-08-01T00:05:00Z")

    accrued = out.get("recharge_seconds_accumulated", 0)
    still_recharging = bool(out.get("observed_mid_job_recharge"))
    sampler_paused = H.VAC in tracker._sampling_paused

    proof.case(
        "the robot finishes charging and resumes — is the recharge closed out?",
        before=accrued == 0 and still_recharging and sampler_paused,
        before_msg="recharge never ended — the end branch is unreachable "
                   "(early return already guaranteed is_charging True), so "
                   "seconds stay 0, the flag stays set, and the sampler stays "
                   "paused for the rest of the run",
        after=accrued > 0 and not still_recharging and not sampler_paused,
        after_msg="recharge closed out — seconds accrued, flag cleared, "
                  "sampling resumed",
        detail=f"recharge_seconds_accumulated={accrued} · "
               f"observed_mid_job_recharge={still_recharging} · "
               f"sampler still paused={sampler_paused}",
    )


def case_native_room_carryover(proof: H.Proof) -> None:
    job = H.active_job(
        queue_room_ids=[1, 2],
        phases=[H.room_phase([1]), H.room_phase([2])],
        current_phase_index=0,
        completed_room_ids=[1],
        current_room_id=1,
        _native_current_room_id=1,      # phase 1's room, per the native signal
        _phase_dispatch_pending=True,
        has_observed_active_lifecycle=True,
    )
    advanced = advance_active_job_phase(job) or {}
    carried = advanced.get("_native_current_room_id")
    live_room = advanced.get("current_room_id")
    # the siblings DID move on: completed list emptied, lifecycle re-armed, and
    # current_room_id advanced to the new phase's room
    siblings_advanced = (
        advanced.get("completed_room_ids") == []
        and advanced.get("has_observed_active_lifecycle") is False
        and live_room == 2
    )

    proof.case(
        "phase advance resets per-phase pointers — does the NATIVE room id move too?",
        before=siblings_advanced and carried == 1,
        before_msg="native room id survived the phase advance — the two room "
                   "pointers now DISAGREE (current_room_id=2, native=1), so the "
                   "next native signal can re-complete phase 1's room into the "
                   "freshly-emptied list and fire a second room_finished for it",
        after=siblings_advanced and carried in (None, -1, 0, 2),
        after_msg="native room id moved with its siblings — the pointers agree",
        detail=f"current_room_id={live_room!r} vs _native_current_room_id="
               f"{carried!r} · siblings advanced={siblings_advanced}",
    )


def case_hold_does_not_accrue(proof: H.Proof) -> None:
    """A COMMANDED dock (charge_wait phase) must not be counted as an unplanned
    mid-job recharge — it owns its own timing."""
    hass = H.make_hass()
    mgr = H.ManagerStub(hass=hass)
    tracker = MappingTracker(hass)
    hass.data[DOMAIN] = {"mapping_tracker": tracker}
    job = H.active_job(
        queue_room_ids=[1, 2],
        phases=[H.room_phase([1]), H.break_phase("charge_wait"), H.room_phase([2])],
        current_phase_index=1,               # parked on the COMMANDED charge phase
        observed_mid_job_recharge=True,
        observed_mid_job_recharge_started_at="2026-08-01T00:00:00Z",
        pending_mid_job_recharge_return=True,
        recharge_seconds_accumulated=0,
    )
    mgr.data["active_jobs"] = {H.VAC: {H.MAP: job}}
    aj = ActiveJobTracker(mgr)
    mgr._get_battery_level = lambda _v: 55
    aj._is_charging = lambda _v: False       # the hold ended

    resolver = getattr(aj, "resolve_mid_job_recharge_resumed", None)
    out = (resolver(vacuum_entity_id=H.VAC, map_id=H.MAP,
                    observed_at="2026-08-01T00:05:00Z")
           if resolver is not None
           else aj.update_active_job_recharge_observation(
               vacuum_entity_id=H.VAC, map_id=H.MAP,
               observed_at="2026-08-01T00:05:00Z"))
    accrued = out.get("recharge_seconds_accumulated", 0)

    proof.case(
        "a COMMANDED hold (charge_wait phase) ends — is it counted as a recharge?",
        before=accrued >= 300,
        before_msg="hold accrued 300s — the planned dock was double-counted as "
                   "an unplanned battery-driven recharge",
        after=accrued == 0,
        after_msg="hold did not accrue — the commanded dock owns its own timing",
        detail=f"recharge_seconds_accumulated after a commanded hold={accrued}",
    )


async def main() -> int:
    proof = H.Proof("RP-012", "tracker lifecycle mirrors the job lifecycle")
    await case_tracker_after_cancel(proof)
    case_recharge_never_ends(proof)
    case_native_room_carryover(proof)
    case_hold_does_not_accrue(proof)
    return proof.finish()


if __name__ == "__main__":
    H.run(main)
