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
[AG-8b] A6-AGX-2: structural_issue_key identity — order-free sources, ordered cycles.
[AG-8c] A6-AGX-2: a PRE-EXISTING violation no longer blocks an unrelated edit.
[AG-8d] A6-AGX-2: a NEW violation, and making an existing one worse, still caught.
[AG-11b] A6-AGX-5: a graph-scoped issue reaches every room's editor.
[AG-13b] A6-AGX-3: one PRE-EXISTING violation no longer greys out every target.
[AG-10b] A6-AGX-1: get_access_graph_health distinguishes blank from partial.
[AG-10c] A6-AGX-1: a blank graph names the rooms a dock room would strand.
[AG-16]  A5-AG-2: access_graph_block_rooms names the rooms the refusal is about.
[AG-16b] A5-AG-2: a room-less issue names nothing rather than a placeholder.
[AG-16c] A5-AG-2: set-valued issues (cycles, dock rooms) are deduped and named.
[AG-17]  A5-DOCK-1: linking rooms is refused while no room is the dock.
[AG-17b] A5-DOCK-1: ...unless that same save sets the dock.
[AG-17c] A5-DOCK-1: ...and a non-access edit on a rootless map is untouched.
[AG-18]  INNPA4ZV: every emitted code carries the params its locale string names.
[AG-18b] INNPA4ZV: list params arrive UNJOINED — the separator is the locale's.
[AG-18c] INNPA4ZV: params are the values the English sentence interpolates.
"""

from __future__ import annotations

import pathlib
import re

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


def test_get_room_access_editor_target_not_selectable_names_the_reason(ag):
    """[AG-13] A6-AGX-3: a refused candidate edge says WHY, accurately.

    This test previously asserted the contentless "Not selectable due to graph
    legality." and its own comment explained why — "the resulting issue names
    room 2 (the target), not room 1" — i.e. it encoded the defect rather than
    the intent. The reason lookup matched only the EDITING room, so
    multiple_inbound (which is keyed on the TARGET, with the editing room merely
    listed as a source) matched nothing and fell through to the fallback. That is
    the commonest refusal there is, so in practice the editor almost never
    explained itself.

    The lookup now matches either END of the candidate edge, which makes the
    branch that describes this exact case reachable.
    """
    g, data = ag
    # 3 -> 2 already; adding 1 -> 2 would give room 2 a second inbound edge.
    _seed_map(data, _rooms(_room(1, dock=True), _room(2), _room(3, grants=[2])))
    out = g.get_room_access_editor(vacuum_entity_id=_VAC, map_id=_MAP, room_id=1)
    t2 = next(t for t in out["editable_targets"] if t["room_id"] == "2")
    assert t2["selectable"] is False
    assert t2["reason"] == "Target already has an inbound access room."
    # reason_code is the localizable half A6-AGX-4's card resolver keys on.
    assert t2["reason_code"] == "target_has_inbound"


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
    """[AG-12] exists / missing operators.

    RP-008 superseded contract: `missing` on an ABSENT entity used to match.
    An absent entity is the definition of not-knowing, and a rule must not fire
    on ignorance (GATE4 Q18) — so `missing` is INDETERMINATE there and the
    boolean wrapper returns False. `exists` stays determinate both ways
    (presence is an observable fact).
    """
    g, _ = ag
    assert g._room_rule_matches(
        {"entity_id": "binary_sensor.ghost", "operator": "exists"}) is False
    assert g._room_rule_matches(
        {"entity_id": "binary_sensor.ghost", "operator": "missing"}) is False
    assert g._room_rule_matches_known(
        {"entity_id": "binary_sensor.ghost", "operator": "missing"}) == (False, False)
    hass.states.async_set("binary_sensor.win", "on")
    assert g._room_rule_matches(
        {"entity_id": "binary_sensor.win", "operator": "exists"}) is True
    # a PRESENT entity makes `missing` a known non-match, not indeterminate
    assert g._room_rule_matches_known(
        {"entity_id": "binary_sensor.win", "operator": "missing"}) == (False, True)


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


def test_room_rule_indeterminate_tristate(ag, hass):
    """[AG-15] (RP-008 / GUARD-1) dropout sentinels are INDETERMINATE for every
    value operator — negating operators especially must NOT match them (a
    not_equals rule used to cancel a live run when a door sensor's battery died)."""
    g, _ = ag
    rule_ne = {"entity_id": "binary_sensor.door", "operator": "not_equals", "value": "closed"}
    rule_ni = {"entity_id": "binary_sensor.door", "operator": "not_in", "value": ["closed"]}
    rule_eq = {"entity_id": "binary_sensor.door", "operator": "equals", "value": "unavailable"}

    for sentinel in ("unavailable", "unknown"):
        hass.states.async_set("binary_sensor.door", sentinel)
        assert g._room_rule_matches_known(rule_ne) == (False, False)
        assert g._room_rule_matches_known(rule_ni) == (False, False)
        # even an EXPLICIT equals-on-the-sentinel cannot match: dropout is the
        # absence of a fact, not a value (GATE4 Q18 — recorded as a known
        # limitation; fail-closed arrives as a per-rule field if ever wanted)
        assert g._room_rule_matches_known(rule_eq) == (False, False)

    hass.states.async_set("binary_sensor.door", "open")
    assert g._room_rule_matches_known(rule_ne) == (True, True)   # genuine block
    hass.states.async_set("binary_sensor.door", "closed")
    assert g._room_rule_matches_known(rule_ne) == (False, True)  # genuine clear


# ---------------------------------------------------------------------------
# [AG-8b] A6-AGX-2 — structural_issue_key identifies ONE violation
# ---------------------------------------------------------------------------

def test_structural_issue_key_distinguishes_and_matches():
    """[AG-8b] the identity the delta gate compares against a baseline."""
    from custom_components.eufy_vacuum.rooms.access_graph import structural_issue_key

    a = {"type": "multiple_inbound", "room_id": 3, "source_room_ids": [1, 2]}
    assert structural_issue_key(a) == structural_issue_key(dict(a))       # stable
    # source order must not matter...
    assert structural_issue_key(a) == structural_issue_key(
        {"type": "multiple_inbound", "room_id": 3, "source_room_ids": [2, 1]})
    # ...but a THIRD source is a different, worse violation and must not match.
    assert structural_issue_key(a) != structural_issue_key(
        {"type": "multiple_inbound", "room_id": 3, "source_room_ids": [1, 2, 4]})

    # `rooms` is a cycle CHAIN: order carries meaning, so two different cycles
    # over the same room set must NOT collapse to one key (which is what sorting
    # it would have done).
    assert structural_issue_key({"type": "cycle_detected", "rooms": [1, 2, 3]}) \
        != structural_issue_key({"type": "cycle_detected", "rooms": [1, 3, 2]})


def test_structural_gate_ignores_a_preexisting_violation(ag):
    """[AG-8c] A6-AGX-2: a violation already in the graph must not block an
    unrelated edit.

    The gate validated the whole post-edit graph and refused on ANY structural
    issue, so a stored violation rejected a fan-speed change or a colour. Such a
    violation genuinely pre-exists: reconciliation rewrites grants through an id
    remap and de-dupes only WITHIN one room's list, never re-checking the
    cross-room single-inbound constraint.

    Asserted at the level that owns the decision -- the baseline/post-edit key
    diff -- because update_room_fields also needs a full manager. [AG-8d] pins
    that a NEW violation is still caught.
    """
    from custom_components.eufy_vacuum.rooms.access_graph import structural_issue_key

    g, _ = ag
    # rooms 1 and 2 BOTH grant to 3 -> multiple_inbound on 3, already stored
    before = _rooms(_room(1, dock=True, grants=[3]), _room(2, grants=[3]), _room(3))
    baseline = {
        structural_issue_key(i)
        for i in g._structural_access_graph_issues(
            g._validate_room_access_graph(managed_rooms=before))
    }
    assert baseline, "precondition: the graph already violates single-inbound"

    # an edit that touches nothing structural (rename room 3)
    after = _rooms(_room(1, dock=True, grants=[3]), _room(2, grants=[3]),
                   _room(3, name="Kitchen"))
    post = g._structural_access_graph_issues(
        g._validate_room_access_graph(managed_rooms=after))
    new = [i for i in post if structural_issue_key(i) not in baseline]
    assert new == [], f"an unrelated edit was blocked by a pre-existing issue: {new}"


def test_structural_gate_still_catches_a_new_violation(ag):
    """[AG-8d] A6-AGX-2: the delta must not become a no-op.

    Two directions: a brand-new violation, and making an EXISTING one worse.
    """
    from custom_components.eufy_vacuum.rooms.access_graph import structural_issue_key

    g, _ = ag

    def _keys(managed):
        return {
            structural_issue_key(i)
            for i in g._structural_access_graph_issues(
                g._validate_room_access_graph(managed_rooms=managed))
        }

    # (1) clean graph -> an edit introduces multiple_inbound
    clean = _rooms(_room(1, dock=True, grants=[3]), _room(2), _room(3))
    baseline = _keys(clean)
    broken = _rooms(_room(1, dock=True, grants=[3]), _room(2, grants=[3]), _room(3))
    assert _keys(broken) - baseline, "a NEW violation must be caught"

    # (2) already violating -> a THIRD source is worse, and has a fresh key
    worse = _rooms(_room(1, dock=True, grants=[3]), _room(2, grants=[3]),
                   _room(4, grants=[3]), _room(3))
    assert _keys(worse) - _keys(broken), "making it worse must still be caught"


def test_graph_scoped_issue_reaches_every_room_editor(ag):
    """[AG-11b] A6-AGX-5: an issue with no room_ids applies to every room.

    missing_dock_room is a property of the whole graph. The old membership test
    dropped it from every room's editor, so a user opening a room panel while the
    map was unusable saw a clean list and no explanation.
    """
    g, data = ag
    _seed_map(data, _rooms(_room(1, grants=[2]), _room(2)))   # grants, NO dock room
    out = g.get_room_access_editor(vacuum_entity_id=_VAC, map_id=_MAP, room_id=2)
    codes = [i.get("code") or i.get("type") for i in out["issues"]]
    assert codes, "a graph-scoped issue must reach this room's editor"


def test_selectability_ignores_a_preexisting_violation(ag):
    """[AG-13b] A6-AGX-3: one stored violation must not grey out EVERY target.

    Selectability asked "is the candidate graph legal?" absolutely, so a single
    pre-existing structural issue anywhere — a second dock room, a stored
    multiple_inbound, a cycle reconciliation created — made every unselected
    target unselectable on every room's editor, each with the contentless
    fallback reason. The whole editor became unusable and the report could not
    say why.
    """
    g, data = ag
    # TWO dock rooms: structurally illegal, and nothing to do with room 4's links
    _seed_map(data, _rooms(
        _room(1, dock=True), _room(2, dock=True), _room(3), _room(4),
    ))
    out = g.get_room_access_editor(vacuum_entity_id=_VAC, map_id=_MAP, room_id=4)
    targets = {t["room_id"]: t for t in out["editable_targets"]}
    assert targets, "precondition: room 4 has candidate targets"
    assert any(t["selectable"] for t in targets.values()), (
        "a pre-existing multiple_dock_rooms greyed out every target: "
        f"{ {k: v['reason'] for k, v in targets.items()} }"
    )


def test_access_graph_health_distinguishes_blank_from_partial(ag):
    """[AG-10b] A6-AGX-1: blank and partial are no longer indistinguishable.

    Both produce byte-identical dock_room_ids / missing_rooms / issues — exactly
    [{'type': 'missing_dock_room'}] — while a BLANK graph allows every run and a
    PARTIAL one refuses every run. The documented diagnostic could not tell a
    user which they were in.
    """
    g, data = ag

    _seed_map(data, _rooms(_room(1), _room(2), _room(3)))          # blank
    blank = g.get_access_graph_health(vacuum_entity_id=_VAC, map_id=_MAP)

    _seed_map(data, _rooms(_room(1, grants=[2]), _room(2, grants=[3]), _room(3)))
    partial = g.get_access_graph_health(vacuum_entity_id=_VAC, map_id=_MAP)

    # the collision this finding is about, documented rather than assumed
    assert blank["issues"] == partial["issues"]
    assert blank["dock_room_ids"] == partial["dock_room_ids"]
    assert blank["missing_rooms"] == partial["missing_rooms"]

    # ...and now distinguishable
    assert blank["state"] == "blank"
    assert blank["runs_blocked"] is False
    assert blank["block_code"] is None

    assert partial["state"] == "partial"
    assert partial["runs_blocked"] is True
    assert partial["block_code"] == "incomplete_access_graph"


def test_access_graph_health_names_the_remediation_trap(ag):
    """[AG-10c] A6-AGX-1: a blank graph reports which rooms setting a dock room
    would strand.

    A blank graph's ONLY issue is "no dock room". Acting on that single
    instruction flips the state to partial and blocks every run, because every
    other room then trips missing_dependency. Naming those rooms up front is what
    stops the diagnostic's own advice being a trap.
    """
    g, data = ag
    _seed_map(data, _rooms(_room(1), _room(2), _room(3)))
    health = g.get_access_graph_health(vacuum_entity_id=_VAC, map_id=_MAP)
    assert health["state"] == "blank"
    assert set(health["unlinked_room_ids"]) == {"1", "2", "3"}


def test_access_graph_block_rooms_names_the_offending_rooms(ag):
    """[AG-16] A5-AG-2: the refusal finally names which rooms it is about.

    THE FINDING: a map rebuild discovers one new room, the graph flips to
    `partial`, and every Start is refused with a sentence that names no room on
    a map that may have eleven. The block itself is unchanged here — only
    whether the user can tell which room to go fix.
    """
    g, data = ag
    rooms = _rooms(
        _room(1, dock=True, grants=[2], name="Hallway"),
        _room(2, name="Kitchen"),
        _room(3, name="Study"),          # discovered by the rebuild, no inbound edge
    )
    _seed_map(data, rooms)

    validation = g._validate_room_access_graph(managed_rooms=rooms)
    assert validation["valid"] is False
    assert g.access_graph_block_code(rooms, validation) == "incomplete_access_graph"

    named = g.access_graph_block_rooms(rooms, validation)
    assert [entry["name"] for entry in named] == ["Study"]
    assert [entry["room_id"] for entry in named] == ["3"]


def test_access_graph_block_rooms_is_empty_when_no_room_is_at_fault(ag):
    """[AG-16b] A5-AG-2: missing_dock_room names no room — say nothing, not "Room 0".

    An empty list is the honest answer and the caller has a sentence for it. A
    placeholder here would put a room that does not exist into a refusal.
    """
    g, data = ag
    rooms = _rooms(_room(1, grants=[2]), _room(2))     # grants, but no dock room
    _seed_map(data, rooms)

    validation = g._validate_room_access_graph(managed_rooms=rooms)
    assert {issue["type"] for issue in validation["issues"]} == {"missing_dock_room"}
    assert g.access_graph_block_code(rooms, validation) == "incomplete_access_graph"
    assert g.access_graph_block_rooms(rooms, validation) == []


def test_access_graph_block_rooms_dedups_set_valued_issues(ag):
    """[AG-16c] A5-AG-2: a cycle chain repeats its entry room; name it once.

    cycle_detected carries `rooms` (a chain that starts and ends on the same
    room) rather than a single room_id, so the dedup is load-bearing rather than
    defensive — without it the refusal names one room twice.
    """
    g, data = ag
    rooms = _rooms(
        _room(1, dock=True, grants=[2], name="Hallway"),
        _room(2, grants=[3], name="Kitchen"),
        _room(3, grants=[2], name="Study"),        # 2 -> 3 -> 2
    )
    _seed_map(data, rooms)

    validation = g._validate_room_access_graph(managed_rooms=rooms)
    named = g.access_graph_block_rooms(rooms, validation)
    ids = [entry["room_id"] for entry in named]
    assert len(ids) == len(set(ids)), f"a room was named more than once: {ids}"
    assert set(ids) >= {"2", "3"}
    # name-sorted, so the list reads the way the card renders it
    assert [entry["name"] for entry in named] == sorted(
        entry["name"] for entry in named
    )


def test_ag16e_multiple_inbound_names_the_source_rooms(ag):
    """[AG-16e] R6: multiple_inbound refusals must name the two rooms the user
    must edit — which are the SOURCES of the extra inbound edges, in
    `source_room_ids`. Naming only the target (the room these edges converge
    on) tells the user which room is IN trouble but not which grants to remove.

    Before R6 (2026-08-24) the loop consumed `room_id` and `rooms` from every
    issue and stopped there. The docstring's comment even enumerated the two
    set-valued types as complete, so nobody added source_room_ids when
    multiple_inbound arrived. The refusal read as if handled while quietly
    hiding two of the three rooms it was about.
    """
    g, data = ag
    # Both 2 and 3 grant into 4, so 4 has multiple inbound edges. 2 and 3 are
    # the rooms the user must go edit; 4 is where the problem shows up.
    rooms = _rooms(
        _room(1, dock=True, grants=[2, 3], name="Hallway"),
        _room(2, grants=[4], name="Kitchen"),
        _room(3, grants=[4], name="Study"),
        _room(4, name="Office"),
    )
    _seed_map(data, rooms)

    validation = g._validate_room_access_graph(managed_rooms=rooms)
    assert {issue["type"] for issue in validation["issues"]} >= {"multiple_inbound"}

    named = g.access_graph_block_rooms(rooms, validation)
    ids = {entry["room_id"] for entry in named}
    assert {"2", "3"} <= ids, (
        f"multiple_inbound refusal named the target only, not the sources: {sorted(ids)}"
    )


def test_access_graph_block_rooms_tolerates_a_missing_validation(ag):
    """[AG-16d] A5-AG-2: no validation -> no rooms, never a crash on the start path."""
    g, data = ag
    rooms = _rooms(_room(1, dock=True))
    _seed_map(data, rooms)
    assert g.access_graph_block_rooms(rooms, None) == []
    assert g.access_graph_block_rooms(rooms, {}) == []


# ---------------------------------------------------------------------------
# A5-DOCK-1 — the dock gate. Exercised through the real update_room_fields on
# the parent manager, since the gate lives with the write.
# ---------------------------------------------------------------------------


def test_linking_rooms_is_refused_without_a_dock_room(manager):
    """[AG-17] A5-DOCK-1: links without a root are meaningless, and were savable.

    The tree is rooted at the dock. Saved rootless, every room trips
    missing_dependency and the map refuses every run — yet nothing stopped it:
    `missing_dock_room` has never been in the structural set (v0.9.0 identical),
    while its mirror `multiple_dock_rooms` always has been.
    """
    from tests._factories import VAC, set_room_field
    from .conftest import setup_map

    setup_map(manager, VAC, "dg1", count=3)
    out = manager.update_room_fields(
        vacuum_entity_id=VAC, map_id="dg1", room_id=1, grants_access_to=[2]
    )

    assert out["ok"] is False
    assert out["reason"] == "no_dock_room"
    assert out["updated"] is False
    # and nothing was written
    stored = manager.data["maps"][VAC]["dg1"]["rooms"]["1"]
    assert list(stored.get("grants_access_to") or []) == []


def test_the_save_that_sets_the_dock_is_allowed(manager):
    """[AG-17b] A5-DOCK-1: the escape hatch that keeps a fresh map buildable.

    Chris's own walkthrough sets the dock and picks the first children in ONE
    save. Gating that would mean a rootless map could never get its first edge —
    the gate would lock out the only action that clears it.
    """
    from tests._factories import VAC, set_room_field
    from .conftest import setup_map

    setup_map(manager, VAC, "dg2", count=3)
    out = manager.update_room_fields(
        vacuum_entity_id=VAC, map_id="dg2", room_id=1,
        is_dock_room=True, grants_access_to=[2, 3],
    )

    assert out["ok"] is True
    stored = manager.data["maps"][VAC]["dg2"]["rooms"]["1"]
    assert stored["is_dock_room"] is True
    assert [str(t) for t in stored["grants_access_to"]] == ["2", "3"]


def test_a_non_access_edit_on_a_rootless_map_is_untouched(manager):
    """[AG-17c] A5-DOCK-1: only ACCESS edits are gated.

    A6-AGX-2's defect was refusing unrelated edits because the graph had a
    pre-existing problem. Re-creating it here would be the same bug wearing a
    different hat: a colour change on a map with no dock room is nobody's
    business but the user's.
    """
    from tests._factories import VAC
    from .conftest import setup_map

    setup_map(manager, VAC, "dg3", count=3)
    out = manager.update_room_fields(
        vacuum_entity_id=VAC, map_id="dg3", room_id=1, color="#ff0000", enabled=False
    )
    assert out["ok"] is True
    assert manager.data["maps"][VAC]["dg3"]["rooms"]["1"]["color"] == "#ff0000"


# ---------------------------------------------------------------------------
# INNPA4ZV — a user-facing message is a CODE plus PARAMS; the sentence, and its
# punctuation, belong to the locale.
#
# The card never reads the English sentence when it can help it: it resolves
# `room_access.issue.<code>` and interpolates `params` into it
# (src/state/coded-label.js::resolveCodedLabel). So the two surfaces are the same
# sentence only if the backend's param NAMES are exactly the placeholders the
# locale declares, and only if list params arrive UNJOINED — the card joins them
# with `room_access.issue.list_separator`, because ", " is an English convention
# and a translated sentence with an untranslatable comma is not translated.
#
# Nothing here tested `params`. Every AG-9 assertion reads `code`, `message` or
# `room_ids`, so emptying the seam — or pre-joining a chain with ", " — leaves
# the whole suite green while all 18 locales silently fall back to English prose,
# including AR and HE, where it lands inside an RTL layout.
#
# The two sides are independent sources: the templates are read from
# src/i18n/en.js, which nothing in rooms/ writes. Comparing them is a real
# cross-check rather than a table agreeing with itself.
# ---------------------------------------------------------------------------

_EN_JS = pathlib.Path(__file__).resolve().parents[2] / "src" / "i18n" / "en.js"

#: The card-facing name for each room in the scenarios below, so a param can be
#: matched against the label the formatter must have interpolated.
_ISSUE_NAMES = {1: "Hallway", 2: "Kitchen", 3: "Study"}

#: Raw-issue fields that carry a SET or CHAIN of rooms. The param they feed is
#: the one that must stay a list; which param that is comes from the locale
#: string, not from this file.
_RAW_ROOM_LISTS = ("rooms", "source_room_ids")


def _issue_room(rid, **kwargs):
    return _room(rid, name=_ISSUE_NAMES[rid], **kwargs)


#: One managed-room graph per issue type, each of which the REAL validator turns
#: into that issue. Fixture values are therefore the validator's own payloads
#: rather than hand-written ones.
_ISSUE_SCENARIOS = {
    "self_reference": _rooms(_issue_room(1, dock=True, grants=[1])),
    "missing_room": _rooms(_issue_room(1, dock=True, grants=[99])),
    "duplicate_edge": _rooms(_issue_room(1, dock=True, grants=[2, 2]), _issue_room(2)),
    "multiple_inbound": _rooms(
        _issue_room(1, dock=True, grants=[3]), _issue_room(2, grants=[3]), _issue_room(3)),
    "missing_dock_room": _rooms(_issue_room(1)),
    "multiple_dock_rooms": _rooms(_issue_room(1, dock=True), _issue_room(2, dock=True)),
    "missing_dependency": _rooms(_issue_room(1, dock=True), _issue_room(2)),
    "unreachable_from_dock": _rooms(
        _issue_room(1, dock=True), _issue_room(2, grants=[3]), _issue_room(3)),
    "cycle_detected": _rooms(
        _issue_room(1, dock=True, grants=[2]),
        _issue_room(2, grants=[3]),
        _issue_room(3, grants=[2]),
    ),
}

#: Plus the fallback branch, which no graph can produce.
_ISSUE_CODES = sorted(_ISSUE_SCENARIOS) + ["unknown_issue"]


def _english_issue_template(code):
    """`room_access.issue.<code>`'s English string, translator note stripped.

    The note is dropped by matching only the quoted literal: nearly every en.js
    entry carries a trailing `// …` and those notes NAME placeholders, so a
    line-wide placeholder scan reports them as expected-and-missing.
    """
    src = _EN_JS.read_text(encoding="utf-8")
    found = re.findall(
        r'^  "room_access\.issue\.([a-z_]+)":\s*"((?:[^"\\]|\\.)*)"',
        src,
        re.MULTILINE,
    )
    templates = dict(found)
    assert code in templates, (
        f"src/i18n/en.js declares no room_access.issue.{code}. Either the code is "
        f"unlocalized — the whole failure INNPA4ZV exists to prevent — or this "
        f"parser stopped matching, in which case every assertion below is vacuous. "
        f"It found {len(templates)} keys."
    )
    return templates[code]


def _placeholders(template):
    return set(re.findall(r"\{([a-z_]+)\}", template))


def _formatted_issue(g, code):
    """Drive `code` through the REAL validator and the REAL formatter.

    Returns ``(payload, raw_issue, room_names)``.
    """
    if code == "unknown_issue":
        return g._format_access_graph_issue(issue={}, room_names={}), {}, {}
    managed = _ISSUE_SCENARIOS[code]
    names = {int(room["room_id"]): room["name"] for room in managed.values()}
    validation = g._validate_room_access_graph(managed_rooms=managed)
    raw = next(
        issue for issue in validation["issues"] if issue["type"] == code
    )
    return g._format_access_graph_issue(issue=raw, room_names=names), raw, names


def _expected_room_chain(raw, names):
    """The room labels the raw issue names, in the order it names them."""
    for field in _RAW_ROOM_LISTS:
        value = raw.get(field)
        if isinstance(value, list):
            return [names[int(rid)] for rid in value]
    return []


@pytest.mark.parametrize("code", _ISSUE_CODES)
def test_issue_params_carry_every_placeholder_the_locale_names(ag, code):
    """[AG-18] INNPA4ZV: `params` is the translation seam, not decoration.

    The card interpolates `params` into `room_access.issue.<code>`. A param the
    locale does not name is dead; a placeholder no param fills renders as a bare
    `{room}` in front of the user. So the two key sets must be equal, and an
    empty `params` fails for every code whose sentence interpolates anything.
    """
    g, _ = ag
    payload, _raw, _names = _formatted_issue(g, code)

    assert payload["code"] == code
    params = payload["params"]
    assert isinstance(params, dict), (
        f"{code}: params must be a dict, got {type(params).__name__}"
    )
    expected = _placeholders(_english_issue_template(code))
    assert set(params) == expected, (
        f"{code}: the locale string interpolates {sorted(expected)} but the "
        f"backend emits {sorted(params)}. The card resolves the code and fills "
        f"these in; a mismatch renders a bare placeholder or drops a name."
    )


def test_issue_params_are_never_pre_joined(ag):
    """[AG-18b] INNPA4ZV: a list stays a list so the LOCALE picks the separator.

    The subtle half of the rule. `", "` is an English convention; pre-joining
    bakes it into all 18 packs, and `flattenParams` only reaches its separator
    for values that are still arrays. A joined chain still renders — in English
    punctuation, inside a Japanese or Arabic sentence — so nothing looks broken.

    Not parametrized, deliberately. Only three issues name a SET or CHAIN of
    rooms, and which three is derived from the validator's own payloads rather
    than listed here — so the count is asserted too. A run that found no chains
    would otherwise pass while checking nothing, which is the shape this whole
    file exists to avoid.
    """
    g, _ = ag
    checked = {}
    for code in sorted(_ISSUE_SCENARIOS):
        payload, raw, names = _formatted_issue(g, code)
        chain = _expected_room_chain(raw, names)
        if not chain:
            continue
        checked[code] = chain
        params = payload["params"]
        matched = [name for name, value in params.items() if value == chain]
        assert matched, (
            f"{code}: no param equals the room chain {chain}. Got {params!r}. "
            f"A pre-joined string, a truncated list and a missing param all land "
            f"here — the card can only choose the locale's separator while this "
            f"is still a list."
        )
        for name in matched:
            assert all(isinstance(entry, str) for entry in params[name]), (
                f"{code}: {name} must interpolate strings; the packs put them in "
                f"a sentence."
            )

    assert sorted(checked) == [
        "cycle_detected", "multiple_dock_rooms", "multiple_inbound",
    ], (
        "the multi-room issues changed. Every issue that names more than one "
        f"room must be checked here; this run only reached {sorted(checked)}."
    )


@pytest.mark.parametrize("code", _ISSUE_CODES)
def test_issue_params_are_the_values_the_sentence_interpolates(ag, code):
    """[AG-18c] INNPA4ZV: the English prose and the seam say the same thing.

    `message` is kept — it is the documented response-service surface and the
    last fallback — so the two are only consistent if every value in `params`
    also appears in the sentence. A param that appears nowhere in the message is
    a seam that drifted from the prose beside it.
    """
    g, _ = ag
    payload, _raw, _names = _formatted_issue(g, code)
    message = payload["message"]
    assert message, f"{code}: the fallback sentence must not be blank"

    for name, value in payload["params"].items():
        values = value if isinstance(value, list) else [value]
        assert values, f"{code}: {name} is empty; it fills a placeholder"
        for entry in values:
            assert isinstance(entry, str), (
                f"{code}: {name} must interpolate strings, got "
                f"{type(entry).__name__}"
            )
            assert entry in message, (
                f"{code}: params[{name!r}] carries {entry!r}, which appears "
                f"nowhere in {message!r}. params must be the values the sentence "
                f"interpolates."
            )
