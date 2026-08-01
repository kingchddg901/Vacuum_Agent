"""Proof RP-023 (RF-26+RF-27) — access graph: one answer, a verdict, delta gates.

STOP CONDITION NOTED (not mine to resolve): the packet's own stop_conditions
require Chris to confirm the AG-2 warning+exclude semantics BEFORE
ASSIGNMENT (an un-numbered Gate-4 decision). That blocks EXECUTION, not
materialization -- per handoff Sec.4 every proof runs against current
master regardless of repair-order blocks (the same disposition RP-013a/c
had). This proof does not touch AG-2 at all; it is unaffected either way.

Two cases (of eleven finding_ids -- RF-27's issue-code+i18n work (5) and the
editor's baseline-vs-candidate diff (AGX-3/AGX-5/AGX-6) are card/frontend or
architecturally separate; not driven here, time-boxed).

  AG-1 + BLK-1 -- reachability is re-implemented divergently, verified by
    reading BOTH walks in full:
      - rooms/access_graph.py:_validate_room_access_graph (753-787): GRAPH-
        scoped. Seeds a BFS from the dock room and walks the full
        grants_access_to graph -- a room counts as reachable purely from
        STRUCTURAL graph connectivity, with no reference to which rooms are
        actually enabled/queued for a given run.
      - planning/run_plan.py:get_runtime_path_block_report (1633-1655):
        QUEUE-scoped. Its accessible_room_ids fixed-point loop only
        propagates through a parent that is ALSO in queue_room_id_set
        (line 1649: `if parent_id in queue_room_id_set`) -- a room whose
        access-graph parent is structurally valid but simply not SELECTED
        for this run's queue never becomes accessible, and is reported
        "access_blocked" for a run that is otherwise completely legal.
    A room can therefore pass preflight (graph-scoped: the structural edge
    exists) and then get reported blocked mid-run (queue-scoped: its parent
    isn't queued) for a room selection the user made deliberately, not by
    mistake -- and an automation wired to the resulting block event can
    cancel an otherwise-healthy job.
  AGX-2 -- _validate_room_access_graph takes the WHOLE managed_rooms
    snapshot and returns issues for the WHOLE graph; it has no concept of
    "what changed". update_room_fields (core/manager.py:1439) calls it
    unconditionally on every field update (verified: no check anywhere in
    that method for whether the update touches grants_access_to/
    is_dock_room before validating) -- so a pre-existing structural issue
    ELSEWHERE in the graph rejects an edit that never touched access fields
    at all.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_reachability.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.rooms.access_graph import AccessGraphManager   # noqa: E402
from custom_components.eufy_vacuum.planning.run_plan import RunPlanManager   # noqa: E402

VAC = H.VAC
MAP = "1"


def _rooms_transit_chain():
    """Dock(1) -> Hallway(2) -> Bedroom(3). Bedroom requires Hallway."""
    return {
        "1": {"room_id": 1, "name": "Dock Room", "is_dock_room": True,
              "enabled": True, "grants_access_to": [2], "rules": []},
        "2": {"room_id": 2, "name": "Hallway", "is_dock_room": False,
              "enabled": False, "grants_access_to": [3], "rules": []},   # NOT selected this run
        "3": {"room_id": 3, "name": "Bedroom", "is_dock_room": False,
              "enabled": True, "grants_access_to": [], "rules": []},
    }


def main() -> int:
    proof = H.Proof("RP-023", "access graph: one answer, a verdict, delta gates")

    # -------------------------------------------------------------------
    # Case 1 (AG-1/BLK-1): graph-scoped preflight vs queue-scoped mid-run.
    # -------------------------------------------------------------------
    hass = H.make_hass()
    data: dict = {}
    ag = AccessGraphManager(data=data, hass=hass)
    rooms = _rooms_transit_chain()

    # PREFLIGHT: graph-scoped -- structurally, dock -> hallway -> bedroom
    # all exist, so this passes clean (no unreachable_from_dock issue for
    # bedroom, since the structural edge from the dock exists).
    preflight = ag._validate_room_access_graph(managed_rooms=rooms)
    preflight_ok = not any(
        i.get("type") == "unreachable_from_dock" and i.get("room_id") == 3
        for i in preflight["issues"]
    )

    # MID-RUN: queue-scoped. Only Dock(1) and Bedroom(3) are enabled/queued
    # (the user deliberately skipped Hallway -- maybe it's a hallway they
    # don't want vacuumed today, and Bedroom's real-world door doesn't
    # require walking through it to be entered by the robot's own path
    # once dispatched -- the point is: THIS is the run the user asked for).
    mgr = H.ManagerStub(hass=hass)
    mgr.data["maps"] = {VAC: {MAP: {"rooms": rooms}}}
    mgr.data["active_jobs"] = {VAC: {MAP: {
        "status": "started", "queue_room_ids": [1, 3], "completed_room_ids": [],
    }}}
    mgr._normalize_active_job = lambda aj: aj
    mgr._normalized_managed_rooms_with_automation = lambda **kw: rooms
    mgr._validate_room_access_graph = lambda **kw: ag._validate_room_access_graph(**kw)
    mgr._structural_access_graph_issues = staticmethod(
        AccessGraphManager._structural_access_graph_issues
    )
    mgr._build_room_access_views = lambda **kw: ag._build_room_access_views(**kw)
    mgr.access_graph = ag
    plan = RunPlanManager(manager=mgr)

    report = plan.get_runtime_path_block_report(vacuum_entity_id=VAC, map_id=MAP)

    proof.case(
        "Bedroom (3) is queued; its access-graph parent Hallway (2) is not enabled",
        before=preflight_ok and report is not None,
        before_msg="preflight (graph-scoped) sees a structurally valid path "
                   "dock->hallway->bedroom and passes; mid-run (queue-scoped) "
                   "then reports Bedroom access_blocked because its parent "
                   "isn't in the queue -- a run the user selected deliberately "
                   "reads as blocked, and an automation on the block event "
                   "can cancel it",
        after=report is None,
        after_msg="one shared compute_reachability answers both call sites "
                  "consistently -- a room the user didn't select for this "
                  "run's queue is not treated as a missing dependency for "
                  "the rooms that ARE queued",
        detail=f"preflight passed={preflight_ok} · mid-run report={report}",
    )

    # -------------------------------------------------------------------
    # Case 2 (AGX-2): the structural gate has no concept of "what changed".
    # Drives the REAL update_room_fields (an EufyVacuumManager method) via
    # an unbound call against a stub standing in for `self` -- the same
    # technique as constructing DispatchManager(manager=stub) elsewhere in
    # this session's proofs, just for a method that lives on the manager
    # class itself rather than a sub-manager.
    # -------------------------------------------------------------------
    from custom_components.eufy_vacuum.core.manager import EufyVacuumManager

    hass2 = H.make_hass()
    ag2 = AccessGraphManager(data={}, hass=hass2)
    # a genuine, PRE-EXISTING structural issue between rooms 10 and 11 that
    # has NOTHING to do with room 99 (the one about to be "edited").
    broken_rooms = {
        "10": {"room_id": 10, "name": "A", "is_dock_room": True,
               "grants_access_to": [11], "rules": []},
        "11": {"room_id": 11, "name": "B", "is_dock_room": False,
               "grants_access_to": [], "rules": []},
        "12": {"room_id": 12, "name": "C", "is_dock_room": False,
               "grants_access_to": [11], "rules": []},   # SAME target as room 10 -> multiple_inbound
        "99": {"room_id": 99, "name": "Unrelated", "is_dock_room": False,
               "grants_access_to": [], "rules": [], "fan_speed": "Max"},
    }
    mgr2 = H.ManagerStub(hass=hass2)
    mgr2.data["maps"] = {VAC: {MAP: {"rooms": broken_rooms}}}
    mgr2._validate_room_access_graph = lambda **kw: ag2._validate_room_access_graph(**kw)
    mgr2._structural_access_graph_issues = AccessGraphManager._structural_access_graph_issues
    mgr2._format_access_graph_issue = lambda **kw: dict(kw.get("issue") or {})
    mgr2._finalize_room_update = lambda room: room   # derived-field recompute, not under test
    mgr2._refresh_room_derived_state = lambda **kw: None
    mgr2._notify_rooms_updated = lambda **kw: None

    result = EufyVacuumManager.update_room_fields(
        mgr2, vacuum_entity_id=VAC, map_id=MAP, room_id=99, fan_speed="Quiet",
    )

    proof.case(
        "room 99's fan_speed is edited while rooms 10/11/12 carry a pre-existing "
        "multiple_inbound conflict",
        before=result["ok"] is False and result.get("reason") == "invalid_access_graph",
        before_msg="update_room_fields calls _validate_room_access_graph "
                   "unconditionally on every field update (verified at "
                   "source: core/manager.py:1439, no check for which fields "
                   "changed) -- an edit to room 99's fan_speed, which never "
                   "touched grants_access_to or is_dock_room, is rejected "
                   "for a conflict between two ENTIRELY OTHER rooms",
        after=result["ok"] is True and mgr2.data["maps"][VAC][MAP]["rooms"]["99"]["fan_speed"] == "Quiet",
        after_msg="update_room_fields validates structurally ONLY when the "
                  "edit itself touches access fields (delta-scoped) -- the "
                  "unrelated fan_speed edit saves without consulting the "
                  "graph at all",
        detail=f"result={result}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
