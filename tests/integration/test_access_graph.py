"""Tests for rooms/access_graph.py — AccessGraphManager.

Pure room-access-graph validation + automation-rule evaluation. Constructed
directly from a crafted root ``data`` dict + the real ``hass`` fixture (for
rule-state reads) — no parent manager needed.

Coverage targets (high-priority: state-machine branches, rule eval, contracts)
------------------------------------------------------------------------------
[AG-1]  _normalize_grants_access_to: dedup, self-exclude, invalid, non-list.
[AG-2]  _normalize_room_rule: kind filter, operator allowlist, blocker→exclude,
        changes whitelist, non-dict.
[AG-3]  _normalize_room_rules: dedup ids + regenerate missing id.
[AG-4]  _build_room_access_views: grants + derived requires, invalid target drop.
[AG-5]  _validate_room_access_graph: every issue type.
[AG-6]  _validate: valid complete graph → no issues.
[AG-7]  _access_graph_state: blank / partial / complete.
[AG-8]  _structural_access_graph_issues + _any_rooms_have_rules.
[AG-9]  _format_access_graph_issue: representative issue types.
[AG-10] get_access_graph_health contract.
[AG-11] get_room_access_editor: room_not_found, normal, stale-reference target.
[AG-12] _room_rule_matches: all operators.
[AG-13] _normalize_rule_operand: bool / number / on-off / string.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.rooms.access_graph import AccessGraphManager


_VAC = "vacuum.alfred"
_MAP = "6"


def _room(rid, *, dock=False, grants=None, name=None, rules=None):
    return {
        "room_id": rid,
        "name": name or f"Room {rid}",
        "is_dock_room": dock,
        "grants_access_to": grants if grants is not None else [],
        "rules": rules or [],
    }


def _rooms(*rooms):
    return {str(r["room_id"]): r for r in rooms}


@pytest.fixture
def ag(hass):
    """AccessGraphManager over an empty root data dict + real hass."""
    data: dict = {"maps": {}}
    return AccessGraphManager(data, hass), data


def _seed_map(data, managed):
    data.setdefault("maps", {}).setdefault(_VAC, {})[_MAP] = {
        "map_id": _MAP, "metadata": {}, "rooms": managed, "summary": {}}


# ---------------------------------------------------------------------------
# normalization
# ---------------------------------------------------------------------------

def test_normalize_grants(ag):
    """[AG-1]"""
    g, _ = ag
    out = g._normalize_grants_access_to([2, 2, 3, "1", -1, 0, 5], room_id=5)
    # dedup 2, drop self (5), drop <=0; "1" coerces to 1
    assert out == [2, 3, 1]
    assert g._normalize_grants_access_to("nope", room_id=1) == []


def test_normalize_room_rule(ag):
    """[AG-2]"""
    g, _ = ag
    assert g._normalize_room_rule("x") is None
    assert g._normalize_room_rule({"kind": "bogus"}) is None
    blocker = g._normalize_room_rule({
        "kind": "blocker", "operator": "weird", "entity_id": "binary_sensor.x",
        "effect": {"action": "mutate", "reason": "open"}})
    assert blocker["operator"] == "equals"      # bad operator falls back
    assert blocker["effect"]["action"] == "exclude"  # blocker forces exclude
    modifier = g._normalize_room_rule({
        "kind": "modifier", "operator": "gt", "value": 5,
        "entity_id": "sensor.x",
        "effect": {"action": "mutate", "changes": {
            "fan_speed": "Max", "bogus_key": "drop"}}})
    assert modifier["effect"]["changes"] == {"fan_speed": "Max"}


def test_normalize_room_rules_dedup(ag):
    """[AG-3]"""
    g, _ = ag
    rules = g._normalize_room_rules([
        {"kind": "blocker", "id": "r1", "entity_id": "binary_sensor.a"},
        {"kind": "blocker", "id": "r1", "entity_id": "binary_sensor.b"},  # dup id
        "junk",
    ])
    assert len(rules) == 2
    assert rules[0]["id"] != rules[1]["id"]  # second got a fresh id


# ---------------------------------------------------------------------------
# access views
# ---------------------------------------------------------------------------

def test_build_room_access_views(ag):
    """[AG-4]"""
    g, _ = ag
    managed = _rooms(
        _room(1, grants=[2, 99]),   # 99 invalid → dropped
        _room(2, grants=[]),
    )
    grants, requires = g._build_room_access_views(managed_rooms=managed)
    assert grants[1] == [2]
    assert requires[2] == [1]
    assert requires[1] == []


# ---------------------------------------------------------------------------
# validation state machine
# ---------------------------------------------------------------------------

def _issue_types(validation):
    return {i["type"] for i in validation["issues"]}


def test_validate_valid_complete(ag):
    """[AG-6] dock→2→3 chain, all reachable, single inbound → valid."""
    g, _ = ag
    managed = _rooms(
        _room(1, dock=True, grants=[2]),
        _room(2, grants=[3]),
        _room(3, grants=[]),
    )
    v = g._validate_room_access_graph(managed_rooms=managed)
    assert v["valid"] is True
    assert v["issues"] == []
    assert v["dock_room_ids"] == [1]


@pytest.mark.parametrize("managed,expected", [
    (_rooms(_room(1, dock=True, grants=[1])), "self_reference"),
    (_rooms(_room(1, dock=True, grants=[99])), "missing_room"),
    (_rooms(_room(1, dock=True, grants=[2, 2]), _room(2)), "duplicate_edge"),
    (_rooms(_room(1, dock=True, grants=[3]), _room(2, grants=[3]), _room(3)),
     "multiple_inbound"),
    (_rooms(_room(1, grants=[])), "missing_dock_room"),
    (_rooms(_room(1, dock=True), _room(2, dock=True)), "multiple_dock_rooms"),
    (_rooms(_room(1, dock=True), _room(2)), "missing_dependency"),
    (_rooms(_room(1, dock=True), _room(2, grants=[3]), _room(3)),
     "unreachable_from_dock"),
    (_rooms(_room(1, dock=True, grants=[2]), _room(2, grants=[1])),
     "cycle_detected"),
])
def test_validate_issue_types(ag, managed, expected):
    """[AG-5] each issue type surfaces."""
    g, _ = ag
    v = g._validate_room_access_graph(managed_rooms=managed)
    assert expected in _issue_types(v)
    assert v["valid"] is False


# ---------------------------------------------------------------------------
# graph-state enum + helpers
# ---------------------------------------------------------------------------

def test_access_graph_state(ag):
    """[AG-7]"""
    g, _ = ag
    blank = _rooms(_room(1), _room(2))
    assert g._access_graph_state(blank) == "blank"
    configured = _rooms(_room(1, dock=True, grants=[2]), _room(2))
    valid = g._validate_room_access_graph(managed_rooms=configured)
    assert g._access_graph_state(configured, valid) == "complete"
    broken = _rooms(_room(1, dock=True, grants=[99]))
    bad = g._validate_room_access_graph(managed_rooms=broken)
    assert g._access_graph_state(broken, bad) == "partial"
    # configuration present but no validation passed → partial
    assert g._access_graph_state(configured) == "partial"


def test_structural_issues_and_any_rules(ag):
    """[AG-8]"""
    g, _ = ag
    managed = _rooms(_room(1, dock=True, grants=[1]))  # self_reference (structural)
    v = g._validate_room_access_graph(managed_rooms=managed)
    structural = g._structural_access_graph_issues(v)
    assert any(i["type"] == "self_reference" for i in structural)
    # missing_dock_room is NOT structural
    nodock = g._validate_room_access_graph(managed_rooms=_rooms(_room(1)))
    assert g._structural_access_graph_issues(nodock) == []

    assert g._any_rooms_have_rules(_rooms(_room(1))) is False
    with_rule = _rooms(_room(1, rules=[{"kind": "blocker", "id": "r1"}]))
    assert g._any_rooms_have_rules(with_rule) is True


def test_format_access_graph_issue(ag):
    """[AG-9]"""
    g, _ = ag
    names = {1: "Kitchen", 2: "Bath"}
    self_ref = g._format_access_graph_issue(
        issue={"type": "self_reference", "room_id": 1}, room_names=names)
    assert self_ref["code"] == "self_reference"
    assert "Kitchen" in self_ref["message"]
    cycle = g._format_access_graph_issue(
        issue={"type": "cycle_detected", "rooms": [1, 2, 1]}, room_names=names)
    assert cycle["code"] == "cycle_detected"
    assert "Kitchen -> Bath" in cycle["message"]
    unknown = g._format_access_graph_issue(issue={"type": "weird"}, room_names=names)
    assert unknown["code"] == "weird"


@pytest.mark.parametrize("issue,code,must_contain", [
    ({"type": "missing_room", "room_id": 1, "target_room_id": 9},
     "missing_room", "Kitchen"),
    ({"type": "duplicate_edge", "room_id": 1, "target_room_id": 2},
     "duplicate_edge", "Kitchen"),
    ({"type": "multiple_inbound", "room_id": 2, "source_room_ids": [1, 3]},
     "multiple_inbound", "Bath"),
    ({"type": "missing_dock_room"}, "missing_dock_room", "dock room"),
    ({"type": "multiple_dock_rooms", "rooms": [1, 2]},
     "multiple_dock_rooms", "Kitchen"),
    ({"type": "missing_dependency", "room_id": 2, "dock_room_id": 1},
     "missing_dependency", "Bath"),
    ({"type": "unreachable_from_dock", "room_id": 2, "dock_room_id": 1},
     "unreachable_from_dock", "Bath"),
])
def test_format_access_graph_issue_all_types(ag, issue, code, must_contain):
    """[AG-9b] every issue type formats to its code + a human message."""
    g, _ = ag
    out = g._format_access_graph_issue(
        issue=issue, room_names={1: "Kitchen", 2: "Bath", 3: "Den"})
    assert out["code"] == code
    assert must_contain in out["message"]
    assert isinstance(out["room_ids"], list)


# ---------------------------------------------------------------------------
# public contracts
# ---------------------------------------------------------------------------

def test_get_access_graph_health(ag):
    """[AG-10]"""
    g, data = ag
    _seed_map(data, _rooms(
        _room(1, dock=True, grants=[2]), _room(2)))
    health = g.get_access_graph_health(vacuum_entity_id=_VAC, map_id=_MAP)
    assert health["vacuum_entity_id"] == _VAC
    assert health["dock_room_ids"] == ["1"]
    assert isinstance(health["issues"], list)


def test_get_room_access_editor_not_found(ag):
    """[AG-11] missing room → room_not_found payload."""
    g, data = ag
    _seed_map(data, _rooms(_room(1, dock=True)))
    out = g.get_room_access_editor(vacuum_entity_id=_VAC, map_id=_MAP, room_id=99)
    assert out["reason"] == "room_not_found"


def test_get_room_access_editor_normal(ag):
    """[AG-11] valid room → editable targets + grants."""
    g, data = ag
    _seed_map(data, _rooms(
        _room(1, dock=True, grants=[2]),
        _room(2, name="Bath"),
        _room(3, name="Den"),
    ))
    out = g.get_room_access_editor(vacuum_entity_id=_VAC, map_id=_MAP, room_id=1)
    assert out["name"] == "Room 1"
    assert out["grants_access_to"] == ["2"]
    target_ids = {t["room_id"] for t in out["editable_targets"]}
    assert {"2", "3"} <= target_ids
    selected = next(t for t in out["editable_targets"] if t["room_id"] == "2")
    assert selected["selected"] is True


def test_get_room_access_editor_stale_reference(ag):
    """[AG-11] grant to a non-existent room → stale missing target entry."""
    g, data = ag
    _seed_map(data, _rooms(_room(1, dock=True, grants=[88]), _room(2)))
    out = g.get_room_access_editor(vacuum_entity_id=_VAC, map_id=_MAP, room_id=1)
    stale = [t for t in out["editable_targets"] if t["missing"]]
    assert any(t["room_id"] == "88" for t in stale)


def test_get_room_access_editor_target_would_cycle(ag):
    """[AG-12] a target whose edge would close a loop is not selectable."""
    g, data = ag
    # 2 -> 1 already; adding 1 -> 2 (from room 1's editor) would create 1<->2
    _seed_map(data, _rooms(_room(1, dock=True), _room(2, grants=[1])))
    out = g.get_room_access_editor(vacuum_entity_id=_VAC, map_id=_MAP, room_id=1)
    t2 = next(t for t in out["editable_targets"] if t["room_id"] == "2")
    assert t2["selectable"] is False
    assert "loop" in t2["reason"].lower()


def test_get_room_access_editor_target_not_selectable_fallback(ag):
    """[AG-13] a candidate edge that makes the graph illegal without the issue
    naming this room → not selectable with the generic legality reason."""
    g, data = ag
    # 3 -> 2 already; adding 1 -> 2 gives room 2 a second inbound edge. The
    # resulting issue names room 2 (the target), not room 1, so the editor
    # falls back to the generic legality reason.
    _seed_map(data, _rooms(_room(1, dock=True), _room(2), _room(3, grants=[2])))
    out = g.get_room_access_editor(vacuum_entity_id=_VAC, map_id=_MAP, room_id=1)
    t2 = next(t for t in out["editable_targets"] if t["room_id"] == "2")
    assert t2["selectable"] is False
    assert t2["reason"] == "Not selectable due to graph legality."


# ---------------------------------------------------------------------------
# rule evaluation (user-visible room-rule gating)
# ---------------------------------------------------------------------------

def test_normalize_rule_operand(ag):
    """[AG-13]"""
    g, _ = ag
    assert g._normalize_rule_operand(True) is True
    assert g._normalize_rule_operand(5) == 5.0
    assert g._normalize_rule_operand("on") is True
    assert g._normalize_rule_operand("OFF") is False
    assert g._normalize_rule_operand("3.5") == 3.5
    assert g._normalize_rule_operand("Hello") == "hello"


def test_room_rule_matches_existence(ag, hass):
    """[AG-12] exists / missing operators."""
    g, _ = ag
    assert g._room_rule_matches(
        {"entity_id": "binary_sensor.ghost", "operator": "exists"}) is False
    assert g._room_rule_matches(
        {"entity_id": "binary_sensor.ghost", "operator": "missing"}) is True
    hass.states.async_set("binary_sensor.win", "on")
    assert g._room_rule_matches(
        {"entity_id": "binary_sensor.win", "operator": "exists"}) is True


def test_room_rule_matches_onoff_equals(ag, hass):
    """[AG-12] is_on / is_off / equals / not_equals."""
    g, _ = ag
    hass.states.async_set("binary_sensor.win", "on")
    assert g._room_rule_matches(
        {"entity_id": "binary_sensor.win", "operator": "is_on"}) is True
    assert g._room_rule_matches(
        {"entity_id": "binary_sensor.win", "operator": "is_off"}) is False
    hass.states.async_set("sensor.mode", "auto")
    assert g._room_rule_matches(
        {"entity_id": "sensor.mode", "operator": "equals", "value": "auto"}) is True
    assert g._room_rule_matches(
        {"entity_id": "sensor.mode", "operator": "not_equals", "value": "auto"}) is False
    # missing entity → False (except exists/missing)
    assert g._room_rule_matches(
        {"entity_id": "sensor.ghost", "operator": "equals", "value": "x"}) is False


def test_room_rule_matches_in_and_numeric(ag, hass):
    """[AG-12] in / not_in / gt / gte / lt / lte + non-numeric guard."""
    g, _ = ag
    hass.states.async_set("sensor.mode", "eco")
    assert g._room_rule_matches(
        {"entity_id": "sensor.mode", "operator": "in", "value": ["eco", "auto"]}) is True
    assert g._room_rule_matches(
        {"entity_id": "sensor.mode", "operator": "not_in", "value": ["auto"]}) is True
    hass.states.async_set("sensor.temp", "25")
    assert g._room_rule_matches(
        {"entity_id": "sensor.temp", "operator": "gt", "value": 20}) is True
    assert g._room_rule_matches(
        {"entity_id": "sensor.temp", "operator": "gte", "value": 25}) is True
    assert g._room_rule_matches(
        {"entity_id": "sensor.temp", "operator": "lt", "value": 20}) is False
    assert g._room_rule_matches(
        {"entity_id": "sensor.temp", "operator": "lte", "value": 25}) is True
    # non-numeric state under a numeric operator → False
    hass.states.async_set("sensor.mode", "eco")
    assert g._room_rule_matches(
        {"entity_id": "sensor.mode", "operator": "gt", "value": 5}) is False
    # unrecognised operator → False
    assert g._room_rule_matches(
        {"entity_id": "sensor.mode", "operator": "", "value": "x"}) is False
