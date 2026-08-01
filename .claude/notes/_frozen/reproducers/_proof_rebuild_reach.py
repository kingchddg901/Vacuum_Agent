"""Proof RP-020 (RF-22) — learning stores: full rebuild reach.

ONE driven case (SVC-1) plus one ESCALATION -- not a full packet materialization.
Time-boxed after four packets (RP-015/017/018/019) already covered this
session; the remaining required_behavior items (SVC-5 cache coherence,
SVC-8 generation counter, Q6 trouble_rooms rebuilder, STATE-4/STATE-9 map
scoping + dismissal service) are NOT driven here and need a follow-up
materialization pass.

  SVC-1 (driven) -- handle_exclude_learning_job / handle_restore_learning_job
    (learning/services.py:583-614) call learning.exclude_learning_job /
    restore_learning_job, which call self.rebuilder.rebuild_all (the "four
    derived files") and then return a message claiming "stats rebuilt" --
    but NEITHER handler calls runtime.async_rebuild_learning_accumulators,
    the SEPARATE call that reaches accuracy_stats/learned_zones/battery
    aggregates (confirmed: that call exists in exactly one place,
    handle_rebuild_learning_stats, a different service -- services.py:475).
    Driven via the real registered service handler (captured through
    hass.services.async_register, per handoff Sec.5's closure-capture
    guidance), not a hand-written stand-in.

  Lesson-6 (claim-block else) -- ESCALATED, not proof-encoded. Read
  async_finalize_completed_job (learning/manager.py:680-750) end to end: the
  claim block already has an explicit `if _stored_job is None: return
  {..., "reason": "no_active_job_record"}` (lines 717-733) -- a refusal
  local to THIS function, not dependent on any upstream guard. This is
  exactly the invariant required_behavior (6) asks for. Whatever RP-001/002
  landed already closed it; TRANCHE2-AUTHORING-INPUTS' note that this hole
  was "explicitly left for a later packet" predates that landing. A packet
  item with no BEFORE state to reproduce is the RP-013d shape (STOP, don't
  encode) inverted: not a wrong fix, but nothing left to fix. Flagging for
  the packet author to drop or re-scope item (6) before RP-020 is assigned,
  per materialization handoff Sec.1.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_rebuild_reach.py
"""

from __future__ import annotations

import sys
import tempfile

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.const import DOMAIN   # noqa: E402
from custom_components.eufy_vacuum.learning.manager import LearningManager   # noqa: E402
from custom_components.eufy_vacuum.learning.services import (   # noqa: E402
    async_register_learning_services,
    async_unregister_learning_services,
)

VAC = H.VAC


def main() -> int:
    proof = H.Proof("RP-020", "learning stores: full rebuild reach (SVC-1)")

    with tempfile.TemporaryDirectory() as tmp:
        hass = H.make_hass(tmp)
        rebuild_calls: list[dict] = []

        class _Runtime:
            async def async_rebuild_learning_accumulators(self, **kw):
                rebuild_calls.append(kw)

        hass.data.setdefault(DOMAIN, {})["runtime"] = _Runtime()
        learning = LearningManager(hass)
        hass.data[DOMAIN]["learning"] = learning

        import asyncio
        asyncio.run(async_register_learning_services(hass))
        try:
            job_id = "job_proof"
            learning.store.save_completed_job(
                vacuum_entity_id=VAC, job_id=job_id,
                payload={"job_id": job_id, "outcome": {"used_for_learning": True}},
            )

            handler = hass.services._handlers[(DOMAIN, "exclude_learning_job")]

            class _Call:
                data = {"vacuum_entity_id": VAC, "job_id": job_id}

            asyncio.run(handler(_Call()))
        finally:
            asyncio.run(async_unregister_learning_services(hass))

        proof.case(
            "exclude_learning_job (the real registered service handler)",
            before=len(rebuild_calls) == 0,
            before_msg="rebuild_all (the four derived files) ran, but "
                       "async_rebuild_learning_accumulators was never called "
                       "-- accuracy_stats/learned_zones/battery aggregates "
                       "keep whatever poisoned samples the excluded job "
                       "contributed, despite the handler's own return message "
                       "claiming 'stats rebuilt'",
            after=len(rebuild_calls) == 1,
            after_msg="exclude_learning_job also calls "
                      "async_rebuild_learning_accumulators -- the seam "
                      "comment (written for the sibling rebuild_learning_stats "
                      "service) becomes true here too",
            detail=f"async_rebuild_learning_accumulators calls={len(rebuild_calls)}",
        )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
