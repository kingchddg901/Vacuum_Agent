"""Proof RP-021a (RF-35 part 1; Q17) — clause (4): empty phase list -> IndexError.

ONE case, out of 14 finding_ids across 7 required_behavior clauses spanning
6 files -- the single most severe, most self-contained claim in the packet
("a fully-blocked stepped Roborock plan yields an EMPTY phase list and
phases[0] IndexErrors the whole dashboard snapshot"). The other six clauses
(leading/trailing charge_wait rejection, zone-first room_count, engine
envelope queue identity, DQ-Q-7 empty-vs-None, honored_strict_order
reporting, floor_type passthrough) are NOT driven here -- left for a
follow-up pass; each is its own independent mechanism.

Mechanism, traced end to end through REAL production code (no reimplementation):
  1. _build_steps_phases (run_plan.py:792-909): a room_group step whose
     included_room_ids intersection is EMPTY (every room in the group is
     blocked/disabled) hits `if not group_ids: continue` (line 828-829) --
     contributes NOTHING to `phases`. No charge_wait/wait/zone steps means
     nothing else contributes either. `collapsed` stays [].
  2. Line 898-908: `if not any(...)` on an EMPTY collapsed list -> any([]) is
     False -> not False is True -> falls into the "collapse to one atomic
     clean" branch, calling `_build_dispatch_phases(queue_room_ids=all_ids or
     sorted(included_room_ids))`. With NOTHING included at all, both operands
     are empty, so queue_room_ids=[].
  3. _build_dispatch_phases (run_plan.py:749-790) resolves the REAL adapter's
     dispatch engine via get_dispatch_engine + honors_clean_order. For a
     Roborock-shaped adapter (honors_clean_order=False) reached through the
     "stepped run WITH STOPS" caller (run_plan.py:1356-1370, which forces
     strict_order=True), effective_strict=True.
  4. GenericRoomIdsEngine.build_phases(strict_order=True, ...) (dispatch_
     engines.py:219-237) delegates to _build_per_room_phases, which does
     `for room in resolved: phases.append(...)` (line 267) -- with
     queue_room_ids=[], `resolved` is empty, so this loop runs ZERO times.
     Returns [] .
  5. _build_effective_start_plan (run_plan.py:1379): `payload_state =
     phases[0]` -- an unguarded index into whatever _build_steps_phases
     returned. On the [] from step 4, this is a raw IndexError.

This proof drives steps 1-4 through the REAL _build_steps_phases /
_build_dispatch_phases / GenericRoomIdsEngine chain (a real adapter config is
registered via adapters.registry, not stubbed), confirms phases == [], then
performs the EXACT operation production performs at line 1379
(`phases[0]`) on that real return value -- not a reimplementation, the same
indexing production does.

INCIDENTAL FINDING while wiring this: build_room_clean_payload's `not
selected_ids or ...` (queue_engine.py:242, selected_ids from `set(queue_room_ids
or [])`) treats an explicitly-empty queue_room_ids identically to None (no
filter) -- an enabled room slips through the collapse-fallback even with
queue_room_ids=[]. This is clause (5)'s own named finding (DQ-Q-7); not
proven here, just independently confirmed real while isolating clause 4
(effective_rooms below uses enabled=False specifically to route around it,
per the inline comment at the call site).

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_empty_phase_crash.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.planning.run_plan import RunPlanManager   # noqa: E402
from custom_components.eufy_vacuum.adapters.registry import register_adapter_config   # noqa: E402

VAC = H.VAC
MAP = "1"

_ROBOROCK_LIKE_ADAPTER = {
    "adapter_id": "roborock",
    "source": "code",
    "entities": {"task_status": "sensor.roborock_status"},
    "capabilities": {"honors_clean_order": False},
    "dispatch": {
        "template": "generic_room_ids",
        "rooms_field": "segments",
        "clean_passes_field": "repeat",
    },
}


def main() -> int:
    proof = H.Proof("RP-021a", "clause 4: empty phase list crashes phases[0], never a structured refusal")

    hass = H.make_hass()
    mgr = H.ManagerStub(hass=hass)
    register_adapter_config(VAC, dict(_ROBOROCK_LIKE_ADAPTER))
    rp = RunPlanManager(manager=mgr)

    # A single room_group step whose only room (id 5) is NOT in
    # included_room_ids -- the group is fully blocked, exactly the scenario
    # the problem statement names ("a fully-blocked stepped Roborock plan").
    run_steps = [
        {
            "type": "room_group",
            "rooms": [{"room_id": 5, "profile_name": "vacuum_quick"}],
        },
    ]

    phases = rp._build_steps_phases(
        vacuum_entity_id=VAC,
        map_id=MAP,
        # enabled=False, not just excluded from included_room_ids: the
        # collapse-fallback (run_plan.py:898-908) calls _build_dispatch_phases
        # with queue_room_ids=[] when nothing survives, and
        # build_room_clean_payload's `not selected_ids or ...` (queue_engine.py:242)
        # treats an EMPTY queue_room_ids as "no filter" (clause 5's own
        # DQ-Q-7 finding, not driven here) -- so an ENABLED room would still
        # slip through that fallback. enabled=False closes that path too and
        # isolates clause 4's empty-phases mechanism specifically.
        effective_rooms={"5": {"room_id": 5, "name": "Blocked Room", "enabled": False}},
        included_room_ids=set(),  # room 5 is NOT included -- fully blocked
        run_steps=run_steps,
        strict_order=True,
    )

    crashed = False
    crash_detail = ""
    try:
        _ = phases[0]  # the EXACT operation run_plan.py:1379 performs
    except IndexError as err:
        crashed = True
        crash_detail = repr(err)

    proof.case(
        "a stepped plan whose only room_group is fully blocked, driven through "
        "the real _build_steps_phases -> _build_dispatch_phases -> "
        "GenericRoomIdsEngine chain with a Roborock-shaped (strict-order) adapter",
        before=(phases == [] and crashed),
        before_msg="_build_steps_phases returns an empty list, and the "
                   "production line's own `phases[0]` operation (replicated "
                   "here verbatim) raises IndexError -- this is what "
                   "_build_effective_start_plan does unconditionally, so the "
                   "whole dashboard snapshot request would crash",
        after=(phases == [] and not crashed),
        after_msg="an empty phase list is still possible (a fully-blocked "
                  "stepped plan is a real state), but the consumer no longer "
                  "indexes into it blindly -- _build_effective_start_plan "
                  "returns a structured {blocked: true, reason: "
                  "no_dispatchable_phases} refusal instead",
        detail=f"phases={phases} · crashed={crashed} ({crash_detail})",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
