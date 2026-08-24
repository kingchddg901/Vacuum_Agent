"""Tests for EufyVacuumManager.set_room_access_graph — the replace-all write.

Wave B of .claude/notes/DESIGN-access-graph-builder.md. Closes the write half of
live:AGX-CLEAR-1: the start refusal names two exits ("complete their access
links, or clear all access settings") and only the first was reachable.

Coverage targets
------------------------------------------------------------------------------
[SAG-1]  builds a whole tree in one call; blank -> complete never passes
         through the blocked partial state, which is why the write is atomic
[SAG-2]  REPLACE-ALL — links absent from the payload are removed, not merged
[SAG-3]  CLEAR — no dock, no edges blanks the graph and unblocks basic runs
[SAG-4]  clearing a map WITH blocker rules does NOT unlock; the response says so
[SAG-5]  a structurally invalid graph is refused and NOTHING is written
[SAG-6]  an unknown dock room / edge endpoint is refused, nothing written
[SAG-7]  only is_dock_room + grants_access_to are touched
[SAG-8]  an INCOMPLETE graph is accepted (buildable in stages) but reported
[SAG-9]  duplicate edges in the payload collapse rather than raising
[SAG-10] idempotent: applying the same graph twice is a no-op with ok=True
[SAG-11] D10: `issues` has ONE shape on both exits. The refusal path formatted them
         and the success path handed back the raw internal validation, so a consumer
         written against one broke on the other and the key name gave no warning.
[SAG-12] D10: the shape matches the sibling readers — `get_access_graph_health` and
         `get_room_access_editor` both emit formatted issues, so a caller can move
         between them without re-learning the payload.
"""

from __future__ import annotations

import pytest

from tests._factories import VAC as _VAC, set_room_field
from .conftest import setup_map

_MAP = "sag1"


def _blocker(entity, *, reason="window_open"):
    return {"kind": "blocker", "id": "b1", "entity_id": entity,
            "operator": "is_on", "effect": {"reason": reason}}


@pytest.fixture
def mgr_rooms(manager):
    """Four managed rooms on one map, no access graph yet."""
    setup_map(manager, _VAC, _MAP, count=4)
    for i, name in enumerate(["Hallway", "Kitchen", "Study", "Bedroom"], start=1):
        set_room_field(manager, i, map_id=_MAP, name=name, enabled=True)
    return manager, manager.data["maps"][_VAC][_MAP]["rooms"]


def _edges(*pairs):
    return [{"from": a, "to": b} for a, b in pairs]


def _graph_of(rooms):
    """(dock_room_id, {room_id: [targets]}) as stored."""
    dock = next(
        (str(r["room_id"]) for r in rooms.values() if r.get("is_dock_room")), None
    )
    return dock, {
        str(r["room_id"]): [str(t) for t in r.get("grants_access_to", [])]
        for r in rooms.values()
    }


def test_builds_a_whole_tree_in_one_call(mgr_rooms):
    """[SAG-1] the builder's commit: dock + every edge, one write."""
    manager, rooms = mgr_rooms
    out = manager.set_room_access_graph(
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        dock_room_id=1,
        edges=_edges((1, 2), (1, 3), (3, 4)),
    )

    assert out["ok"] is True
    assert out["dock_room_id"] == "1"
    assert out["edge_count"] == 3
    assert out["rooms_updated"] == 4

    dock, grants = _graph_of(rooms)
    assert dock == "1"
    assert grants == {"1": ["2", "3"], "2": [], "3": ["4"], "4": []}

    # BLANK -> COMPLETE, and neither end is blocked: an empty graph is the
    # PERMISSIVE state (basic runs allowed), a valid graph allows everything.
    # The blocked state is PARTIAL, in between — which is precisely why this
    # write is atomic. Built room by room the map would pass through the
    # blocked state on the way to the unblocked one, and a browser closed
    # midway would leave it there.
    assert out["blocked_before"] is False
    assert out["block_code_before"] is None
    assert out["blocked_after"] is False
    assert out["block_code_after"] is None


def test_replace_all_removes_links_absent_from_the_payload(mgr_rooms):
    """[SAG-2] REPLACE, not merge — the whole point of one atomic write.

    A merge would make the map observably half-built between calls, which is
    exactly what the all-or-nothing design forbids.
    """
    manager, rooms = mgr_rooms
    manager.set_room_access_graph(
        vacuum_entity_id=_VAC, map_id=_MAP, dock_room_id=1,
        edges=_edges((1, 2), (1, 3), (3, 4)),
    )

    # Re-shape the tree: 1 -> 2 -> 3 -> 4. Nothing from the old shape survives.
    manager.set_room_access_graph(
        vacuum_entity_id=_VAC, map_id=_MAP, dock_room_id=1,
        edges=_edges((1, 2), (2, 3), (3, 4)),
    )

    dock, grants = _graph_of(rooms)
    assert dock == "1"
    assert grants == {"1": ["2"], "2": ["3"], "3": ["4"], "4": []}


def test_clear_blanks_the_graph_and_unblocks(mgr_rooms):
    """[SAG-3] the second exit the refusal names, finally reachable.

    Clearing is this same call with no dock and no edges — which is why there is
    no separate clear service.
    """
    manager, rooms = mgr_rooms
    manager.set_room_access_graph(
        vacuum_entity_id=_VAC, map_id=_MAP, dock_room_id=1, edges=_edges((1, 2)),
    )
    # A partial graph: rooms 3 and 4 unlinked -> every run refused.
    assert manager.access_graph_block_code(rooms) == "incomplete_access_graph"

    out = manager.set_room_access_graph(vacuum_entity_id=_VAC, map_id=_MAP)

    assert out["ok"] is True
    assert out["dock_room_id"] is None
    assert out["edge_count"] == 0
    assert out["block_code_before"] == "incomplete_access_graph"
    assert out["block_code_after"] is None
    assert out["blocked_after"] is False

    dock, grants = _graph_of(rooms)
    assert dock is None
    assert grants == {"1": [], "2": [], "3": [], "4": []}


def test_clearing_a_map_with_blocker_rules_does_not_unlock(mgr_rooms):
    """[SAG-4] the remediation trap, caught in the response.

    A6-AGX-1 was about a diagnostic whose own advice moved the user from an
    allowed state into a blocked one. The write side has the same trap: on a map
    with blocker rules, clearing the graph swaps incomplete_access_graph for
    access_graph_required_for_rules — still blocked, different message. A
    "clear to unlock" button that silently fails to unlock is the same defect,
    and block_code_after is where a caller catches it.
    """
    manager, rooms = mgr_rooms
    set_room_field(manager, 2, map_id=_MAP, rules=[_blocker("binary_sensor.win")])
    manager.set_room_access_graph(
        vacuum_entity_id=_VAC, map_id=_MAP, dock_room_id=1, edges=_edges((1, 2)),
    )

    out = manager.set_room_access_graph(vacuum_entity_id=_VAC, map_id=_MAP)

    assert out["ok"] is True                      # the write itself succeeded
    assert out["block_code_before"] == "incomplete_access_graph"
    assert out["block_code_after"] == "access_graph_required_for_rules"
    assert out["blocked_after"] is True, "the user is still blocked and must be told"


def test_structurally_invalid_graph_is_refused_and_writes_nothing(mgr_rooms):
    """[SAG-5] atomic means a refusal leaves the stored graph untouched."""
    manager, rooms = mgr_rooms
    manager.set_room_access_graph(
        vacuum_entity_id=_VAC, map_id=_MAP, dock_room_id=1,
        edges=_edges((1, 2), (1, 3), (3, 4)),
    )
    before = _graph_of(rooms)

    # Room 4 reached from BOTH 3 and 2 — the single-inbound violation.
    out = manager.set_room_access_graph(
        vacuum_entity_id=_VAC, map_id=_MAP, dock_room_id=1,
        edges=_edges((1, 2), (1, 3), (3, 4), (2, 4)),
    )

    assert out["ok"] is False
    assert out["reason"] == "invalid_access_graph"
    assert out["updated"] is False
    assert any(issue["code"] == "multiple_inbound" for issue in out["issues"])
    assert _graph_of(rooms) == before, "a refused write must not have partially applied"

    # A cycle is refused the same way.
    cyc = manager.set_room_access_graph(
        vacuum_entity_id=_VAC, map_id=_MAP, dock_room_id=1,
        edges=_edges((1, 2), (2, 3), (3, 2)),
    )
    assert cyc["ok"] is False
    assert _graph_of(rooms) == before


def test_unknown_rooms_are_refused(mgr_rooms):
    """[SAG-6] a dock room or endpoint that is not on this map."""
    manager, rooms = mgr_rooms
    before = _graph_of(rooms)

    bad_dock = manager.set_room_access_graph(
        vacuum_entity_id=_VAC, map_id=_MAP, dock_room_id=99,
    )
    assert bad_dock["ok"] is False
    assert bad_dock["reason"] == "room_not_found"

    bad_edge = manager.set_room_access_graph(
        vacuum_entity_id=_VAC, map_id=_MAP, dock_room_id=1, edges=_edges((1, 99)),
    )
    assert bad_edge["ok"] is False
    assert bad_edge["reason"] == "room_not_found"

    assert _graph_of(rooms) == before


def test_only_the_two_access_fields_are_touched(mgr_rooms):
    """[SAG-7] rules, selection, order, colour and is_transition survive.

    is_transition in particular is NOT a graph field — the validator never reads
    it (it is used by mapping/tracker.py for attribution) — so a graph write must
    not disturb it.
    """
    manager, rooms = mgr_rooms
    set_room_field(
        manager, 2, map_id=_MAP,
        enabled=False, color="#ff0000", is_transition=True,
        rules=[_blocker("binary_sensor.win")],
    )
    keep = {k: v for k, v in rooms["2"].items()
            if k not in ("is_dock_room", "grants_access_to")}

    manager.set_room_access_graph(
        vacuum_entity_id=_VAC, map_id=_MAP, dock_room_id=1, edges=_edges((1, 2)),
    )

    after = {k: v for k, v in rooms["2"].items()
             if k not in ("is_dock_room", "grants_access_to")}
    assert after == keep


def test_incomplete_graph_is_accepted_but_reported(mgr_rooms):
    """[SAG-8] buildable in stages; the block is reported, not enforced here.

    Refusing incompleteness at the write would make a graph unbuildable — the
    same reason the card-side validateEdit does not enforce it ([AGM-11]).
    """
    manager, rooms = mgr_rooms
    out = manager.set_room_access_graph(
        vacuum_entity_id=_VAC, map_id=_MAP, dock_room_id=1, edges=_edges((1, 2)),
    )

    assert out["ok"] is True
    assert out["blocked_after"] is True
    assert out["block_code_after"] == "incomplete_access_graph"
    # ...and it names which rooms are the problem (A5-AG-2).
    assert {r["name"] for r in out["blocking_rooms"]} == {"Study", "Bedroom"}


def test_duplicate_edges_collapse(mgr_rooms):
    """[SAG-9] the same pair twice is one link, not a duplicate_edge refusal.

    The builder cannot emit a duplicate, but a YAML caller can, and the
    de-duplicated intent is unambiguous.
    """
    manager, rooms = mgr_rooms
    out = manager.set_room_access_graph(
        vacuum_entity_id=_VAC, map_id=_MAP, dock_room_id=1,
        edges=_edges((1, 2), (1, 2), (1, 3), (3, 4)),
    )
    assert out["ok"] is True
    assert out["edge_count"] == 3
    assert _graph_of(rooms)[1]["1"] == ["2", "3"]


def test_applying_the_same_graph_twice_is_stable(mgr_rooms):
    """[SAG-10] idempotent — a retried call is not a second, different write."""
    manager, rooms = mgr_rooms
    payload = dict(
        vacuum_entity_id=_VAC, map_id=_MAP, dock_room_id=1,
        edges=_edges((1, 2), (1, 3), (3, 4)),
    )
    first = manager.set_room_access_graph(**payload)
    snapshot = _graph_of(rooms)
    second = manager.set_room_access_graph(**payload)

    assert first["ok"] is second["ok"] is True
    assert _graph_of(rooms) == snapshot
    assert second["block_code_before"] is None
    assert second["block_code_after"] is None


def test_sag11_issues_have_one_shape_on_both_exits(mgr_rooms):
    """[SAG-11] RED BEFORE THE FIX.

    An INCOMPLETE graph is accepted and reported, so the success path routinely carries
    a non-empty `issues` list — this is not an edge case reachable only by contrivance.
    The two exits are compared against each other rather than against a hardcoded shape,
    so the test says what it means: one key, one payload.
    """
    manager, rooms = mgr_rooms

    ok = manager.set_room_access_graph(
        vacuum_entity_id=_VAC, map_id=_MAP, dock_room_id=1, edges=_edges((1, 2)),
    )
    assert ok["ok"] is True
    assert ok["issues"], "precondition: an incomplete graph reports issues"

    refused = manager.set_room_access_graph(
        vacuum_entity_id=_VAC, map_id=_MAP, dock_room_id=1,
        edges=_edges((1, 2), (1, 3), (3, 4), (2, 4)),      # multiple inbound
    )
    assert refused["ok"] is False and refused["issues"]

    _KEYS = {"code", "message", "params", "room_ids"}
    for issue in ok["issues"]:
        assert set(issue) == _KEYS, issue
        assert "type" not in issue, "the RAW internal validation shape leaked out"
    for issue in refused["issues"]:
        assert set(issue) == _KEYS, issue


def test_sag12_the_shape_matches_the_sibling_readers(mgr_rooms):
    """[SAG-12] RED IF THE WRITE PATH DIVERGES AGAIN.

    Compared against `get_access_graph_health` rather than a literal, so the assertion
    tracks the convention instead of a copy of it. Formatted is what every public reader
    in the subsystem emits; raw belongs to `_validate_room_access_graph` and stops there.
    """
    manager, rooms = mgr_rooms
    written = manager.set_room_access_graph(
        vacuum_entity_id=_VAC, map_id=_MAP, dock_room_id=1, edges=_edges((1, 2)),
    )
    health = manager.get_access_graph_health(vacuum_entity_id=_VAC, map_id=_MAP)

    assert written["issues"] and health["issues"]
    assert {frozenset(i) for i in written["issues"]} == {frozenset(i) for i in health["issues"]}
    assert [i["code"] for i in written["issues"]] == [i["code"] for i in health["issues"]]
