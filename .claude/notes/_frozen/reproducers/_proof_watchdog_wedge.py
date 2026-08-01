"""Proof RP-011 (RF-07) — the watchdog wedges and the reaper cannot reach it.

  1. WEDGED — _phase_dispatch_pending is BOTH the "a watchdog owns this phase"
     flag AND an unconditional reaper exclusion. Every abnormal watchdog exit
     (raise, exhausted retries) leaves it set, so the slot is simultaneously
     wedged and invisible to the reaper. is_stranded_started has no liveness
     input at all, so a DEAD watchdog looks exactly like a live one.
  2. REAPER TICK DIES — the reaper loop iterates (vacuum, map) slots with no
     per-slot isolation. One raising async_finalize_stranded_job kills the whole
     tick, so every later slot is never processed — this tick or any other.
  3. NEVER-STARTED — a run dispatched but never observed active leaves
     has_observed_active_lifecycle False, which is an unconditional early
     return. The slot can never be reaped, and the NEXT run's terminal signals
     finalize this stale one.

VALIDITY (packet): case 3 must NOT arm has_observed_active_lifecycle — the whole
point is a slot that never observed a lifecycle. Cases 1 and 3 drive the real
PURE predicate is_stranded_started; case 2 drives the real listener tick.

Post-repair the predicate is expected to consult the liveness fields the packet
names on the record (_phase_watchdog_dead, _phase_dispatch_pending_since). The
proof discovers them by signature so it reports the ACTUAL signature if the
repair names them differently, rather than silently passing.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_watchdog_wedge.py
"""

from __future__ import annotations

import inspect
import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.jobs.job_monitor import is_stranded_started   # noqa: E402
from custom_components.eufy_vacuum.listeners import pause_timeout   # noqa: E402
from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN   # noqa: E402

# a run that genuinely ran and now reads ended: docked, secondary satisfied,
# but task_status never reached the brand's completion value — the FN-1 strand.
ENDED_LOOKING = dict(
    status="started",
    has_observed_active_lifecycle=True,
    vacuum_state="docked",
    task_status="Standby",
    completion_task_status_value="completed",
    secondary_satisfied=True,
    job_active_on=False,
    is_mid_run_status=False,
)

LIVENESS_PARAMS = ("phase_watchdog_dead", "phase_dispatch_pending_since",
                   "watchdog_dead", "pending_since")


def _liveness_aware() -> list[str]:
    params = inspect.signature(is_stranded_started).parameters
    return [p for p in LIVENESS_PARAMS if p in params]


def case_wedged(proof: H.Proof) -> None:
    live = is_stranded_started(**ENDED_LOOKING, phase_dispatch_pending=True)
    known = _liveness_aware()

    dead_reapable = None
    if known:
        kwargs = dict(ENDED_LOOKING, phase_dispatch_pending=True)
        for p in known:
            kwargs[p] = True if "dead" in p else "2020-01-01T00:00:00Z"
        dead_reapable = is_stranded_started(**kwargs)

    proof.case(
        "a phase whose watchdog DIED still holds _phase_dispatch_pending",
        before=live is False and not known,
        before_msg="wedged: pending set, reaper excluded — the predicate takes "
                   "no liveness input, so a dead watchdog is indistinguishable "
                   "from a live one and the slot is excluded forever",
        after=bool(known) and dead_reapable is True,
        after_msg=f"dead watchdog reapable — predicate consults {known}",
        detail=f"pending+ended → stranded={live} · liveness params present: "
               f"{known or 'none'}",
    )


def case_never_started(proof: H.Proof) -> None:
    # dispatched, but the device never reported an active lifecycle: it stayed
    # docked/Standby throughout (validity note — has_observed stays False).
    kwargs = dict(ENDED_LOOKING, has_observed_active_lifecycle=False,
                  phase_dispatch_pending=False)
    reapable = is_stranded_started(**kwargs)
    params = inspect.signature(is_stranded_started).parameters
    dispatch_aware = [p for p in ("dispatched_at", "dispatched_seconds_ago",
                                  "never_started") if p in params]

    proof.case(
        "a run dispatched 10+ minutes ago that never reported an active lifecycle",
        before=reapable is False and not dispatch_aware,
        before_msg="never-started slot unreapable — has_observed_active_lifecycle "
                   "False is an unconditional early return, so the stale slot "
                   "survives to absorb the NEXT run's terminal signals",
        after=bool(dispatch_aware),
        after_msg=f"never_started reaped — predicate consults {dispatch_aware}",
        detail=f"never-observed slot → stranded={reapable} · dispatch-age "
               f"params: {dispatch_aware or 'none'}",
    )


async def case_reaper_isolation(proof: H.Proof) -> None:
    hass = H.make_hass()
    mgr = H.ManagerStub(hass=hass)
    hass.data[DOMAIN] = {DATA_RUNTIME: mgr}

    processed: list[str] = []
    mgr.get_known_vacuum_ids = lambda: [H.VAC, H.IVY]
    mgr.get_known_map_ids = lambda _vac: [H.MAP]
    mgr.get_paused_job_timeout_report = lambda **kw: None
    mgr.poll_stranded_started_job = lambda **kw: {"vacuum_entity_id": kw["vacuum_entity_id"]}

    async def _finalize_stranded(*, vacuum_entity_id, map_id, **kw):
        processed.append(vacuum_entity_id)
        if vacuum_entity_id == H.VAC:
            raise RuntimeError("finalize raised for this slot (proof fixture)")
        return {"finalized": True}

    mgr.async_finalize_stranded_job = _finalize_stranded
    mgr.async_save = H.async_noop()

    # Capture the REAL tick closure the module registers, so the loop under test
    # is production's — not a re-implementation of it here.
    captured: list = []

    def _capture(hass_arg, handler, interval):
        captured.append(handler)
        return lambda: None

    original = pause_timeout.async_track_time_interval
    pause_timeout.async_track_time_interval = _capture
    try:
        pause_timeout.register(hass)
    finally:
        pause_timeout.async_track_time_interval = original

    if not captured:
        proof.case("reaper tick capture", before=False, before_msg="",
                   after=False, after_msg="",
                   detail="could not capture the tick handler — proof needs updating")
        return

    captured[0](None)          # fire one tick
    await H._block_till_done()
    pause_timeout.remove(hass)

    reached_second = H.IVY in processed

    proof.case(
        "one slot's finalize raises while a second slot also needs reaping",
        before=processed == [H.VAC],
        before_msg="reaper tick died on raise — the loop has no per-slot "
                   "isolation, so vacuum.ivy was never reached this tick",
        after=reached_second and processed == [H.VAC, H.IVY],
        after_msg="reaper survived raising slot — per-slot isolation let the "
                  "second slot finalize",
        detail=f"slots the real tick reached: {processed}",
    )


async def main() -> int:
    proof = H.Proof("RP-011", "watchdog wedges + reaper reach")
    case_wedged(proof)
    case_never_started(proof)
    await case_reaper_isolation(proof)
    return proof.finish()


if __name__ == "__main__":
    H.run(main)
