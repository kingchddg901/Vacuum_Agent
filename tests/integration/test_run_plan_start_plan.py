"""Tests for planning/run_plan.py::_build_effective_start_plan.

The authoritative rule-evaluation point for job start. Driven against the real
``manager`` fixture (so the access-graph + queue + profile delegation all run
for real), with rooms seeded into manager.data and rule entity states set on
hass.

Coverage targets (high-priority: adapter-degraded gates, state-machine branches)
--------------------------------------------------------------------------------
[RPS-1]  blank graph + no rules → ready preflight, all rooms selected.
[RPS-2]  partial graph (invalid grants) → blocked incomplete_access_graph.
[RPS-3]  blank graph + rooms have rules → blocked access_graph_required_for_rules.
[RPS-4]  complete graph, blocker rule, no grants → blocked access_graph_required.
[RPS-5]  valid graph + matching direct blocker → room in blocked_rooms + confirm.
[RPS-6]  valid graph + matching modifier → modified_rooms carries the changes.
[RPS-7]  access-dependency propagation: blocked parent blocks its child.
[RPS-8]  modifier fan-out: a rule's fan_out_room_ids apply to a derived target.
[RPS-9]  get_runtime_path_block_report exists on the real manager and reports a
        mid-job blocker (regression guard for the method lost in the bundle-out).
[RPS-10] fan-out loop's per-target + matched-rule guards: only a valid, selected,
        unblocked target gets the change; no-entity/no-match/empty-changes skip.
[RPS-11] runtime path-block: a remaining room with its OWN blocker is directly
        blocked, while a reachable sibling propagates accessible and is not flagged.
[RPS-12] mop-carpet caution: an attached water tank + an included carpet room →
        non-blocking warning; None when tank off / no carpet / no tank sensor.
[RPS-13] order advisory: a path-optimizing brand (honors_clean_order False) with
        2+ rooms → advisory; None when order is honored or one room runs.
[RPS-14] strict_order: builds one phase per room for a path-optimizing flat-id
        brand; gated off (one batch phase) when the brand honors order.
[RPS-15] stashed run steps survive a PREFLIGHT (peek) and are consumed only by the real
        dispatch (consume_pending_steps=True) — the shipped bug where get_start_status'
        preflight popped the stash, so a stepped profile ran an atomic (flat) job.
[RPS-16] regression (B2): a stored room whose value dict lacks room_id survives normalization with room_id recovered from its dict KEY.
[RPS-17] PRE-3: the graph-block branch (structurally invalid access graph)
         reports available=False.
[RPS-18] PRE-3: the access_graph_required_for_rules branch reports available=False.
[RPS-19] PRE-3: the access_graph_required branch reports available=False.
[RPS-20] PRE-3: every selected room ending up blocked (included_room_count==0)
         reports available=False, even though the top-level 'blocked' flag
         (reserved for a structurally invalid graph) stays False there.
[RPS-21] PRE-3 control: a PARTIAL block (some rooms still includable) keeps
         available=True.
[RPS-22] A5-AG-2: the graph-block preflight NAMES the offending rooms, in
         reason_params (list, unjoined) and in the English message.
[RPS-23] A5-AG-2: a refusal that no room causes still refuses, with an empty
         room list and the generic sentence.
[RPS-24] A5-AG-2: reason_params is declared on the base shape, so a ready
         preflight has the same keys as a blocked one.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.planning.run_plan import RunPlanManager

from tests.brand_catalogs import adapter_config

from tests._factories import VAC as _VAC, set_room_field
from .conftest import setup_map


@pytest.fixture
def rp(manager):
    return RunPlanManager(manager), manager


def _seed(manager, map_id, rooms_config):
    """Seed N managed rooms then merge per-room overrides; return the bucket."""
    setup_map(manager, _VAC, map_id, count=len(rooms_config))
    for i, cfg in enumerate(rooms_config, start=1):
        set_room_field(manager, i, map_id=map_id, **cfg)
    return manager.data["maps"][_VAC][map_id]["rooms"]


def _blocker(entity, *, reason="window_open"):
    return {"kind": "blocker", "id": "b1", "entity_id": entity,
            "operator": "is_on", "effect": {"reason": reason}}


def _modifier(entity, changes):
    return {"kind": "modifier", "id": "m1", "entity_id": entity,
            "operator": "is_on",
            "effect": {"action": "mutate", "changes": changes}}


# ---------------------------------------------------------------------------

def test_ready_blank_graph(rp):
    """[RPS-1]"""
    rp_, mgr = rp
    _seed(mgr, "spm1", [{"enabled": True}, {"enabled": True}])
    out = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm1")
    pf = out["preflight"]
    assert pf["blocked"] is False
    assert pf["reason"] == "ready"
    assert set(pf["selected_room_ids"]) == {1, 2}
    assert pf["blocked_room_ids"] == []


def test_room_missing_room_id_field_recovers_from_key(rp):
    """[RPS-16] Regression (B2): a stored room whose value dict lacks the `room_id`
    field survives normalization with room_id recovered from its dict KEY, so the
    start plan does not int(None)-crash. `_normalized_managed_rooms_with_automation`
    now writes the computed room_id back (matching the access views' key-fallback)."""
    rp_, mgr = rp
    _seed(mgr, "spm16", [{"enabled": True}, {"enabled": True}])
    # Corrupt: drop the room_id FIELD from room 1's value (its dict key "1" remains).
    mgr.data["maps"][_VAC]["spm16"]["rooms"]["1"].pop("room_id", None)
    out = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm16")
    pf = out["preflight"]
    assert pf["blocked"] is False
    assert set(pf["selected_room_ids"]) == {1, 2}   # room 1 recovered from its key


def test_partial_graph_blocks(rp):
    """[RPS-2] a dock room granting to a missing room → invalid → partial → blocked."""
    rp_, mgr = rp
    _seed(mgr, "spm2", [
        {"enabled": True, "is_dock_room": True, "grants_access_to": [99]},
        {"enabled": True},
    ])
    out = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm2")
    pf = out["preflight"]
    assert pf["blocked"] is True
    assert pf["reason"] == "incomplete_access_graph"


def test_blank_graph_with_rules_blocks(rp):
    """[RPS-3]"""
    rp_, mgr = rp
    _seed(mgr, "spm3", [
        {"enabled": True, "rules": [_blocker("binary_sensor.win")]},
        {"enabled": True},
    ])
    out = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm3")
    pf = out["preflight"]
    assert pf["blocked"] is True
    assert pf["reason"] == "access_graph_required_for_rules"


def test_complete_graph_blocker_without_grants_blocks(rp):
    """[RPS-4] single dock room + blocker rule, no grants → access_graph_required."""
    rp_, mgr = rp
    _seed(mgr, "spm4", [
        {"enabled": True, "is_dock_room": True,
         "rules": [_blocker("binary_sensor.win")]},
    ])
    out = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm4")
    pf = out["preflight"]
    assert pf["blocked"] is True
    assert pf["reason"] == "access_graph_required"


def test_partial_graph_block_is_unavailable(rp):
    """[RPS-17] PRE-3: same seed as [RPS-2] -- the structurally invalid
    access graph means nothing is includable, so available must be False."""
    rp_, mgr = rp
    _seed(mgr, "spm17", [
        {"enabled": True, "is_dock_room": True, "grants_access_to": [99]},
        {"enabled": True},
    ])
    out = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm17")
    pf = out["preflight"]
    assert pf["blocked"] is True
    assert pf["available"] is False


def test_rules_without_graph_block_is_unavailable(rp):
    """[RPS-18] PRE-3: same seed as [RPS-3]."""
    rp_, mgr = rp
    _seed(mgr, "spm18", [
        {"enabled": True, "rules": [_blocker("binary_sensor.win")]},
        {"enabled": True},
    ])
    out = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm18")
    pf = out["preflight"]
    assert pf["blocked"] is True
    assert pf["available"] is False


def test_blocker_without_grants_is_unavailable(rp):
    """[RPS-19] PRE-3: same seed as [RPS-4]."""
    rp_, mgr = rp
    _seed(mgr, "spm19", [
        {"enabled": True, "is_dock_room": True,
         "rules": [_blocker("binary_sensor.win")]},
    ])
    out = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm19")
    pf = out["preflight"]
    assert pf["blocked"] is True
    assert pf["available"] is False


def test_all_selected_rooms_blocked_is_unavailable(rp, hass):
    """[RPS-20] PRE-3: a VALID access graph where every selected room ends up
    individually blocked (included_room_count == 0) must still report
    available=False, even though the top-level 'blocked' key (reserved for a
    structurally invalid graph) is False here — the earlier bug left
    available stuck at True in exactly this shape."""
    rp_, mgr = rp
    _seed(mgr, "spm20", [
        {"enabled": True, "is_dock_room": True, "grants_access_to": [2],
         "rules": [_blocker("binary_sensor.win1")]},
        {"enabled": True, "rules": [_blocker("binary_sensor.win2")]},
    ])
    hass.states.async_set("binary_sensor.win1", "on")
    hass.states.async_set("binary_sensor.win2", "on")
    out = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm20")
    pf = out["preflight"]
    assert pf["blocked"] is False
    assert pf["included_room_count"] == 0
    assert set(pf["blocked_room_ids"]) == {1, 2}
    assert pf["available"] is False


def test_direct_blocker_fires(rp, hass):
    """[RPS-5] valid graph, blocker on a selected room whose entity is on."""
    rp_, mgr = rp
    _seed(mgr, "spm5", [
        {"enabled": True, "is_dock_room": True, "grants_access_to": [2]},
        {"enabled": True, "rules": [_blocker("binary_sensor.win")]},
    ])
    hass.states.async_set("binary_sensor.win", "on")
    out = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm5")
    pf = out["preflight"]
    assert 2 in pf["blocked_room_ids"]
    blocked = next(b for b in pf["blocked_rooms"] if b["room_id"] == 2)
    assert blocked["source"] == "direct_rule"
    assert blocked["reason"] == "window_open"
    # 1 of 2 rooms blocked (50%) → confirmation required + token
    assert pf["requires_confirmation"] is True
    assert pf["confirm_token"] is not None
    assert pf["reason"] == "confirmation_required"
    # [RPS-21] PRE-3 control: a PARTIAL block (room 1 is still includable)
    # must keep available=True.
    assert pf["included_room_count"] == 1
    assert pf["available"] is True


def test_modifier_applies_changes(rp, hass):
    """[RPS-6] valid graph, modifier on a selected room → changes in modified_rooms."""
    rp_, mgr = rp
    _seed(mgr, "spm6", [
        {"enabled": True, "is_dock_room": True, "grants_access_to": [2]},
        {"enabled": True,
         "rules": [_modifier("binary_sensor.quiet", {"fan_speed": "Quiet"})]},
    ])
    hass.states.async_set("binary_sensor.quiet", "on")
    out = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm6")
    pf = out["preflight"]
    assert not pf["blocked_room_ids"]
    mod = next(m for m in pf["modified_rooms"] if m["room_id"] == 2)
    assert mod["changes"]["fan_speed"] == "Quiet"
    assert "m1" in mod["triggered_rule_ids"]


def test_access_dependency_propagates(rp, hass):
    """[RPS-7] blocking a parent room cascades to its dependent child."""
    rp_, mgr = rp
    _seed(mgr, "spm7", [
        {"enabled": True, "is_dock_room": True, "grants_access_to": [2]},
        {"enabled": True, "grants_access_to": [3],
         "rules": [_blocker("binary_sensor.win")]},
        {"enabled": True},
    ])
    hass.states.async_set("binary_sensor.win", "on")
    out = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm7")
    pf = out["preflight"]
    assert 2 in pf["blocked_room_ids"]   # direct blocker
    assert 3 in pf["blocked_room_ids"]   # cascaded
    child = next(b for b in pf["blocked_rooms"] if b["room_id"] == 3)
    assert child["source"] == "access_dependency"
    assert child["blocked_by_room_id"] == 2


def test_modifier_fan_out(rp, hass):
    """[RPS-8] a modifier on the dock room fans its changes out to room 2."""
    rp_, mgr = rp
    fan_rule = {
        "kind": "modifier", "id": "f1", "entity_id": "binary_sensor.quiet",
        "operator": "is_on",
        "fan_out_room_ids": [2],
        "effect": {"action": "mutate", "changes": {"water_level": "low"}},
    }
    _seed(mgr, "spm8", [
        {"enabled": True, "is_dock_room": True, "grants_access_to": [2],
         "rules": [fan_rule]},
        {"enabled": True},   # no direct rule → entry is purely fan-out-derived
    ])
    hass.states.async_set("binary_sensor.quiet", "on")
    out = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm8")
    pf = out["preflight"]
    mod = next(m for m in pf["modified_rooms"] if m["room_id"] == 2)
    assert mod["changes"]["water_level"] == "low"
    assert mod["derived"] is True
    assert mod["source_room_id"] == 1
    assert "f1" in mod["triggered_rule_ids"]


def test_runtime_path_block_report(rp, hass, manager):
    """[RPS-9] real-manager mid-job path-block re-evaluation.

    Regression guard: get_runtime_path_block_report was lost in the bundle-out
    refactor while path_blockers.py still called manager.get_runtime_path_block_
    report(...). The listener test mocked the manager, so it never caught the
    AttributeError. This drives the REAL manager delegation chain.
    """
    # method must exist on the real manager (not just a mock)
    assert hasattr(manager, "get_runtime_path_block_report")

    # valid graph (dock 1 -> 2) + an active job over both rooms; a blocker on
    # room 2 fires mid-job.
    _seed(mgr := manager, "spm9", [
        {"enabled": True, "is_dock_room": True, "grants_access_to": [2],
         "rules": [_blocker("binary_sensor.win")]},
        {"enabled": True},
    ])
    mgr.data.setdefault("active_jobs", {}).setdefault(_VAC, {})["spm9"] = {
        "status": "started", "job_id": "j1",
        "queue_room_ids": [1, 2], "completed_room_ids": [1],
    }
    hass.states.async_set("binary_sensor.win", "on")
    report = manager.get_runtime_path_block_report(
        vacuum_entity_id=_VAC, map_id="spm9",
        trigger_entity_id="binary_sensor.win", trigger_entity_state="on")
    assert report is not None
    assert report["event_scope"] == "active_job_path_blocked"
    assert "2" in report["affected_remaining_room_ids"]

    # idle job → None
    mgr.data["active_jobs"][_VAC]["spm9"]["status"] = "idle"
    assert manager.get_runtime_path_block_report(
        vacuum_entity_id=_VAC, map_id="spm9") is None


def test_runtime_block_walks_the_graph_not_the_queue(rp, hass):
    """[RPS-22] A6-PP-EST-BLK-1 / A5-AG-1: a PARTIAL run must not report every
    remaining room blocked just because their access parent is not queued.

    Graph: dock room 1 grants access to 2, which grants access to 3. The user
    cleans only 2 and 3 — the normal case, and the dock room is not in the queue.
    A blocker fires on an UNRELATED room 4.

    The report used to evaluate rules, seed and walk over queue_room_ids alone.
    Room 2 requires room 1, room 1 was not queued, so its parent list filtered to
    empty, it never became reachable, and both remaining rooms came back
    access_blocked — which the caller can escalate to a cancel. Reachability is a
    property of the graph; the robot drives THROUGH rooms it is not cleaning.
    """
    rp_, mgr = rp
    _seed(mgr, "spm22", [
        {"enabled": True, "is_dock_room": True, "grants_access_to": [2]},
        {"enabled": True, "grants_access_to": [3]},
        {"enabled": True},
        {"enabled": True, "rules": [_blocker("binary_sensor.far")]},
    ])
    mgr.data.setdefault("active_jobs", {}).setdefault(_VAC, {})["spm22"] = {
        "status": "started", "job_id": "j22",
        "queue_room_ids": [2, 3], "completed_room_ids": [],
    }
    hass.states.async_set("binary_sensor.far", "on")

    report = mgr.get_runtime_path_block_report(
        vacuum_entity_id=_VAC, map_id="spm22",
        trigger_entity_id="binary_sensor.far", trigger_entity_state="on")

    # Rooms 2 and 3 are reachable through the unqueued dock room. Neither is
    # blocked, so there is nothing actionable to report at all.
    blocked = [] if report is None else list(report["affected_remaining_room_ids"])
    assert blocked == [], f"a partial run reported {blocked} as blocked"


def test_runtime_block_still_fires_when_the_parent_really_is_blocked(rp, hass):
    """[RPS-22] The other direction — widening the walk must not blind it.

    Same graph, but the blocker sits on the UNQUEUED dock room that rooms 2 and 3
    actually depend on. Walking the graph means a non-queued room can now block,
    which queue-scoping could never see, so the block is real and both remaining
    rooms are correctly unreachable.
    """
    rp_, mgr = rp
    _seed(mgr, "spm23", [
        {"enabled": True, "is_dock_room": True, "grants_access_to": [2],
         "rules": [_blocker("binary_sensor.hall")]},
        {"enabled": True, "grants_access_to": [3]},
        {"enabled": True},
    ])
    mgr.data.setdefault("active_jobs", {}).setdefault(_VAC, {})["spm23"] = {
        "status": "started", "job_id": "j23",
        "queue_room_ids": [2, 3], "completed_room_ids": [],
    }
    hass.states.async_set("binary_sensor.hall", "on")

    report = mgr.get_runtime_path_block_report(
        vacuum_entity_id=_VAC, map_id="spm23",
        trigger_entity_id="binary_sensor.hall", trigger_entity_state="on")
    assert report is not None
    assert sorted(report["affected_remaining_room_ids"]) == ["2", "3"]

    # The room-id list ALONE does not discriminate: queue-scoping also returned
    # [2, 3] here, because filtering their parents to the queue made them
    # unreachable regardless of any blocker. Same output, different cause. The
    # ATTRIBUTION is what separates them — only a graph walk sees the rule on the
    # unqueued room 1 and can name it as the thing standing in the way.
    by_id = {r["room_id"]: r for r in report["affected_rooms"]}
    assert by_id[2]["blocked_by_room_id"] == 1, (
        "room 2 must be blocked BY the dock room whose blocker fired. Queue-scoping "
        "filtered room 2's parents to the queue, leaving none, so it reported None "
        "— blocked, with nothing to point at."
    )
    assert by_id[2]["reason"] == "access_blocked"


def test_runtime_block_propagates_down_the_chain(rp, hass):
    """[RPS-22] Widening the walk must not weaken propagation.

    Chain 1 -> 2 -> 3 -> 4, queue [2, 3, 4]. A blocker MID-CHAIN on room 2 must
    take 3 and 4 with it, and a blocker on the LEAF must take only itself.
    Blocking stays monotone because the seed subtracts direct_blocked, the loop
    skips blocked rooms so they can never re-enter the set, and a child joins
    only via `any(parent in accessible)`.
    """
    rp_, mgr = rp
    for map_id, blocked_room, expected in (("spm24", 2, ["2", "3", "4"]),
                                           ("spm25", 4, ["4"])):
        cfgs = [
            {"enabled": True, "is_dock_room": True, "grants_access_to": [2]},
            {"enabled": True, "grants_access_to": [3]},
            {"enabled": True, "grants_access_to": [4]},
            {"enabled": True},
        ]
        ent = f"binary_sensor.chain{blocked_room}"
        cfgs[blocked_room - 1] = dict(
            cfgs[blocked_room - 1],
            rules=[{"kind": "blocker", "id": f"b{blocked_room}", "entity_id": ent,
                    "operator": "is_on", "effect": {"reason": "window_open"}}],
        )
        _seed(mgr, map_id, cfgs)
        mgr.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[map_id] = {
            "status": "started", "job_id": f"j{map_id}",
            "queue_room_ids": [2, 3, 4], "completed_room_ids": [],
        }
        hass.states.async_set(ent, "on")
        report = mgr.get_runtime_path_block_report(
            vacuum_entity_id=_VAC, map_id=map_id,
            trigger_entity_id=ent, trigger_entity_state="on")
        got = [] if report is None else sorted(report["affected_remaining_room_ids"])
        assert got == expected, f"blocker on {blocked_room}: got {got}"


def test_multiple_inbound_is_structural_so_the_walk_never_sees_two_parents(rp, hass):
    """[RPS-22] A room CANNOT have two parents — asserting the invariant itself.

    Written because a "two parents, one blocked, room stays reachable" test would
    be VACUOUS: `multiple_inbound` is a structural issue, the report bails on
    structural issues, so it returns None and an `== []` assertion passes without
    the walk ever running. The invariant is the thing worth pinning, not a
    reachability behaviour that can never be reached.

    Consequence for the walk: `requires_map[room]` holds 0 or 1 entries in any
    graph that gets that far, so the `any(...)` and the `next(...)` fallback in
    get_runtime_path_block_report are defensive, not semantic.
    """
    rp_, mgr = rp
    _seed(mgr, "spm26", [
        {"enabled": True, "is_dock_room": True, "grants_access_to": [3]},
        {"enabled": True, "grants_access_to": [3]},
        {"enabled": True},
    ])
    rooms = mgr._normalized_managed_rooms_with_automation(
        vacuum_entity_id=_VAC, map_id="spm26")
    validation = mgr._validate_room_access_graph(managed_rooms=rooms)
    assert "multiple_inbound" in [i["type"] for i in validation["issues"]]
    assert "multiple_inbound" in [
        i["type"] for i in mgr._structural_access_graph_issues(validation)
    ], "two inbound edges must be STRUCTURAL, or the walk could see two parents"

    mgr.data.setdefault("active_jobs", {}).setdefault(_VAC, {})["spm26"] = {
        "status": "started", "job_id": "j26",
        "queue_room_ids": [3], "completed_room_ids": [],
    }
    assert mgr.get_runtime_path_block_report(
        vacuum_entity_id=_VAC, map_id="spm26") is None


def test_modifier_fan_out_guard_branches(rp, hass):
    """[RPS-10] the fan-out loop's per-target + matched-rule guards.

    One matching fan rule whose fan_out_room_ids mix a non-numeric id, an
    unknown id, the source room itself, a blocked room, and one valid target —
    only the valid target gets the change. Sibling rules cover the no-entity,
    no-match, and empty-changes early-continues.
    """
    rp_, mgr = rp
    rules = [
        {"kind": "modifier", "id": "g1", "entity_id": "binary_sensor.on",
         "operator": "is_on", "fan_out_room_ids": ["xx", 99, 1, 2, 3],
         "effect": {"action": "mutate", "changes": {"water_level": "low"}}},
        # no entity_id → continue
        {"kind": "modifier", "id": "g2", "entity_id": "", "operator": "is_on",
         "fan_out_room_ids": [3], "effect": {"action": "mutate",
                                             "changes": {"fan_speed": "Quiet"}}},
        # entity off → rule does not match → continue
        {"kind": "modifier", "id": "g3", "entity_id": "binary_sensor.off",
         "operator": "is_on", "fan_out_room_ids": [3],
         "effect": {"action": "mutate", "changes": {"fan_speed": "Quiet"}}},
        # matches but empty changes → continue
        {"kind": "modifier", "id": "g4", "entity_id": "binary_sensor.on",
         "operator": "is_on", "fan_out_room_ids": [3],
         "effect": {"action": "mutate", "changes": {}}},
    ]
    _seed(mgr, "spm10", [
        {"enabled": True, "is_dock_room": True, "grants_access_to": [2, 3],
         "rules": rules},
        {"enabled": True, "rules": [_blocker("binary_sensor.on")]},  # room 2 blocked
        {"enabled": True},                                           # room 3 valid target
    ])
    hass.states.async_set("binary_sensor.on", "on")
    hass.states.async_set("binary_sensor.off", "off")
    out = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm10")
    pf = out["preflight"]
    # only the valid, selected, unblocked target (room 3) receives the change
    mod = next(m for m in pf["modified_rooms"] if m["room_id"] == 3)
    assert mod["changes"]["water_level"] == "low"
    assert mod["derived"] is True
    # the blocked target (room 2) was skipped by the fan-out, not modified
    assert 2 in pf["blocked_room_ids"]
    assert all(m["room_id"] != 2 for m in pf["modified_rooms"])


def test_path_block_directly_blocked_remaining(rp, hass, manager):
    """[RPS-11] a remaining room with its OWN blocker is classified directly
    blocked, while a reachable sibling propagates accessible and is not flagged."""
    mgr = manager
    _seed(mgr, "spm11", [
        {"enabled": True, "is_dock_room": True, "grants_access_to": [2]},
        {"enabled": True, "grants_access_to": [3]},
        {"enabled": True, "rules": [_blocker("binary_sensor.win")]},  # room 3 own blocker
    ])
    mgr.data.setdefault("active_jobs", {}).setdefault(_VAC, {})["spm11"] = {
        "status": "started", "job_id": "j2",
        "queue_room_ids": [1, 2, 3], "completed_room_ids": [1],
    }
    hass.states.async_set("binary_sensor.win", "on")
    report = manager.get_runtime_path_block_report(
        vacuum_entity_id=_VAC, map_id="spm11",
        trigger_entity_id="binary_sensor.win", trigger_entity_state="on")
    assert report is not None
    # room 3 is directly blocked; room 2 stayed reachable (not flagged)
    assert "3" in report["directly_blocked_room_ids"]
    assert "2" not in report["affected_remaining_room_ids"]


def test_path_block_no_affected_returns_none(rp, hass, manager):
    """[RPS-11b] a trigger that blocks no remaining room → report is None, and the
    active job's stale block signature is cleared."""
    _seed(manager, "spm11b", [
        {"enabled": True, "is_dock_room": True, "grants_access_to": [2]},
        {"enabled": True},
    ])
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})["spm11b"] = {
        "status": "started", "job_id": "j3", "queue_room_ids": [1, 2],
        "completed_room_ids": [], "last_path_block_signature": "old"}
    report = manager.get_runtime_path_block_report(
        vacuum_entity_id=_VAC, map_id="spm11b",
        trigger_entity_id="binary_sensor.nobody", trigger_entity_state="on")
    assert report is None
    assert "last_path_block_signature" not in manager.data["active_jobs"][_VAC]["spm11b"]


def test_path_block_all_rooms_completed_returns_none(rp, hass, manager):
    """[RPS-11c] when every queued room is already completed there is nothing
    remaining → no path-block report fires even though the blocker entity is on
    (completion-time early return, arc 1278->1279)."""
    _seed(manager, "spm11c", [
        {"enabled": True, "is_dock_room": True, "grants_access_to": [2],
         "rules": [_blocker("binary_sensor.win")]},
        {"enabled": True},
    ])
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})["spm11c"] = {
        "status": "started", "job_id": "j4", "queue_room_ids": [1, 2],
        "completed_room_ids": [1, 2], "last_path_block_signature": "stale"}
    # blocker entity is on, but it can't affect an already-finished queue.
    hass.states.async_set("binary_sensor.win", "on")
    report = manager.get_runtime_path_block_report(
        vacuum_entity_id=_VAC, map_id="spm11c",
        trigger_entity_id="binary_sensor.win", trigger_entity_state="on")
    assert report is None


def test_mop_carpet_warning(rp, hass):
    """[RPS-12] tank attached + an included carpet room -> a non-blocking caution
    naming the room; None when the tank is off, no carpet room is included, or the
    brand declares no tank sensor (Eufy)."""
    from custom_components.eufy_vacuum.adapters.registry import (
        register_adapter_config,
        unregister_adapter_config,
    )

    rp_, mgr = rp
    # Register BEFORE seeding: creating a room resolves it against the adapter's
    # declared catalog, and core has none to fall back on. Seeding first left the
    # rooms unresolvable and the failure looked like a preflight bug.
    register_adapter_config(_VAC, adapter_config(**{
        "adapter_id": "rb", "source": "code",
        "entities": {"mop_active": "binary_sensor.tank"},
    }))
    rooms = _seed(mgr, "spm12", [
        {"enabled": True, "floor_type": "carpet"},
        {"enabled": True, "floor_type": "hardwood"},
    ])
    carpet_name = rooms["1"]["name"]
    try:
        # Tank attached -> the caution names the carpet room.
        hass.states.async_set("binary_sensor.tank", "on")
        pf = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm12")["preflight"]
        assert pf["mop_carpet_warning"] is not None
        assert carpet_name in pf["mop_carpet_warning"]

        # Tank detached -> no caution.
        hass.states.async_set("binary_sensor.tank", "off")
        pf = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm12")["preflight"]
        assert pf["mop_carpet_warning"] is None

        # Tank attached but no carpet room in the run -> no caution.
        set_room_field(mgr, 1, map_id="spm12", floor_type="hardwood")
        hass.states.async_set("binary_sensor.tank", "on")
        pf = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm12")["preflight"]
        assert pf["mop_carpet_warning"] is None
    finally:
        # A brand declaring NO tank sensor -> never warns, even with a carpet room.
        # Swapped for a tankless adapter rather than unregistering: with no adapter at
        # all there is no profile catalog either, so set_room_field below could not
        # resolve the room and the test would fail for an unrelated reason. "Declares no
        # mop_active entity" is the condition under test; "has no adapter" is not a state
        # a vacuum is ever in.
        register_adapter_config(_VAC, adapter_config(**{
            "adapter_id": "tankless", "source": "code", "entities": {},
        }))

    set_room_field(mgr, 1, map_id="spm12", floor_type="carpet")
    pf = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm12")["preflight"]
    assert pf["mop_carpet_warning"] is None
    unregister_adapter_config(_VAC)


def test_order_advisory(rp):
    """[RPS-13] order_advisory surfaces for a path-optimizing brand (honors_clean_order
    False) with 2+ included rooms; None when order is honored (default) or one room
    runs."""
    from custom_components.eufy_vacuum.adapters.registry import (
        register_adapter_config,
        unregister_adapter_config,
    )

    rp_, mgr = rp
    try:
        # Default (no capability declared) -> honored -> no advisory (default-REJECT).
        register_adapter_config(_VAC, adapter_config(**{
            "adapter_id": "e", "source": "code", "capabilities": {}}))
        _seed(mgr, "spm13a", [{"enabled": True}, {"enabled": True}])
        pf = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm13a")["preflight"]
        assert pf["order_advisory"] is None

        # Path-optimizing brand + 2 rooms -> advisory.
        register_adapter_config(_VAC, adapter_config(**{
            "adapter_id": "rb", "source": "code",
            "capabilities": {"honors_clean_order": False}}))
        _seed(mgr, "spm13b", [{"enabled": True}, {"enabled": True}])
        pf = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm13b")["preflight"]
        assert pf["order_advisory"] is not None
        assert "advisory" in pf["order_advisory"].lower()

        # Path-optimizing but only ONE included room -> order is moot -> None.
        _seed(mgr, "spm13c", [{"enabled": True}, {"enabled": False}])
        pf = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm13c")["preflight"]
        assert pf["order_advisory"] is None
    finally:
        unregister_adapter_config(_VAC)


def test_strict_order_phases(rp):
    """[RPS-14] strict_order builds one single-segment phase per room for a
    path-optimizing flat-id brand; gated off (one batch phase) when the brand
    honors order, even if strict_order is requested."""
    from custom_components.eufy_vacuum.adapters.registry import (
        register_adapter_config,
        unregister_adapter_config,
    )

    rp_, mgr = rp
    rooms = _seed(mgr, "spm14", [
        {"enabled": True, "order": 1}, {"enabled": True, "order": 2}])
    try:
        # Path-optimizing flat-id brand -> one phase per room, in order.
        register_adapter_config(_VAC, adapter_config(**{
            "adapter_id": "rb", "source": "code",
            "capabilities": {"honors_clean_order": False},
            "dispatch": {"template": "roborock_segment_clean", "passes_max": 3},
        }))
        phases = rp_._build_dispatch_phases(
            vacuum_entity_id=_VAC, map_id="spm14",
            managed_rooms=rooms, queue_room_ids=[1, 2], strict_order=True,
        )
        assert len(phases) == 2
        assert phases[0]["payload"]["segments"] == [1]
        assert phases[1]["payload"]["segments"] == [2]

        # Order-honoring brand -> strict_order ignored (single batch phase).
        register_adapter_config(_VAC, adapter_config(**{
            "adapter_id": "e", "source": "code",
            "capabilities": {"honors_clean_order": True},
            "dispatch": {"template": "roborock_segment_clean"},
        }))
        phases = rp_._build_dispatch_phases(
            vacuum_entity_id=_VAC, map_id="spm14",
            managed_rooms=rooms, queue_room_ids=[1, 2], strict_order=True,
        )
        assert len(phases) == 1
        assert phases[0]["payload"]["segments"] == [1, 2]
    finally:
        unregister_adapter_config(_VAC)


def test_pending_steps_survive_preflight(rp):
    """[RPS-15] a preflight (peek) must NOT eat the stashed run steps — only the real dispatch
    (consume_pending_steps=True) pops them. The shipped bug: start_selected_rooms calls
    get_start_status first, whose _build_effective_start_plan popped the stash, so the real
    dispatch fell back to an ATOMIC job — a stepped profile ran one flat pass, no charge."""
    rp_, mgr = rp
    _seed(mgr, "6", [{"enabled": True}])
    mgr.build_queue(vacuum_entity_id=_VAC, map_id="6")
    steps = [
        {"type": "room_group", "rooms": [{"room_id": 1}]},
        {"type": "charge_wait", "target_battery_percent": 95},
        {"type": "room_group", "rooms": [{"room_id": 1}]},
    ]
    mgr.data.setdefault("_pending_run_steps", {}).setdefault(_VAC, {})["6"] = steps

    # Preflight PEEK (default consume_pending_steps=False): stash intact, plan still stepped.
    plan1 = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="6")
    assert mgr.data["_pending_run_steps"][_VAC].get("6") == steps            # NOT eaten
    assert any(p.get("phase_type") == "charge_wait" for p in plan1["phases"])

    # Real dispatch CONSUME: stash gone, plan still stepped.
    plan2 = rp_._build_effective_start_plan(
        vacuum_entity_id=_VAC, map_id="6", consume_pending_steps=True)
    assert mgr.data["_pending_run_steps"][_VAC].get("6") is None            # consumed
    assert any(p.get("phase_type") == "charge_wait" for p in plan2["phases"])


def test_graph_block_names_the_offending_rooms(rp):
    """[RPS-22] A5-AG-2: the refusal names which rooms it is about.

    THE FINDING: 'no shipped surface names the offending room'. Room 3 has no
    inbound edge — the shape a map rebuild produces — and every Start on this
    map is refused. Before, with a sentence that named nothing.

    `rooms` rides as a LIST so the card joins it with the locale's separator;
    pre-joining it here would bake an English list convention into 18 locales.
    """
    rp_, mgr = rp
    _seed(mgr, "spm22", [
        {"enabled": True, "is_dock_room": True, "grants_access_to": [2], "name": "Hallway"},
        {"enabled": True, "name": "Kitchen"},
        {"enabled": True, "name": "Study"},
    ])
    out = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm22")
    pf = out["preflight"]

    assert pf["blocked"] is True
    assert pf["reason"] == "incomplete_access_graph"

    assert pf["reason_params"]["rooms"] == ["Study"]
    assert isinstance(pf["reason_params"]["rooms"], list), "must NOT be pre-joined"
    assert pf["reason_params"]["room_ids"] == ["3"]
    assert pf["blocking_rooms"] == [{"room_id": "3", "name": "Study"}]

    # The English fallback improves too — it is what a non-card consumer reads.
    assert "Study" in pf["message"]


def test_graph_block_with_no_room_at_fault_still_refuses(rp):
    """[RPS-23] A5-AG-2: no dock room blames no room, and says so generically.

    The empty list must not degrade into naming a room that does not exist, and
    the block itself is unchanged — this finding's semantics half (should ONE
    unconfigured room block the whole map?) is a separate decision.
    """
    rp_, mgr = rp
    _seed(mgr, "spm23", [
        {"enabled": True, "grants_access_to": [2]},   # a grant, but nothing is the dock
        {"enabled": True},
    ])
    pf = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm23")["preflight"]

    assert pf["blocked"] is True
    assert pf["reason"] == "incomplete_access_graph"
    assert pf["reason_params"] == {"rooms": [], "room_ids": []}
    assert pf["blocking_rooms"] == []
    assert "partially configured" in pf["message"]


def test_ready_preflight_declares_the_same_keys(rp):
    """[RPS-24] A5-AG-2: an absent key and an empty one read alike to a template
    but not to code, so the base shape declares both fields."""
    rp_, mgr = rp
    _seed(mgr, "spm24", [{"enabled": True}, {"enabled": True}])
    pf = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm24")["preflight"]

    assert pf["blocked"] is False
    assert pf["reason_params"] == {}
    assert pf["blocking_rooms"] == []


# ---------------------------------------------------------------------------
# [RPS-25]..[RPS-27] the RUNTIME sibling, `get_runtime_path_block_report`.
#
# Everything above drives `_build_effective_start_plan`, which runs at job start. This
# one re-evaluates the same rules MID-JOB, so a window opening behind a running vacuum
# pauses it. Its ignorable-rule walk had never been exercised: a corrupt room row, a
# disabled rule, a modifier, a blocker with no entity, an unmatched blocker and an
# INDETERMINATE one all reach it, and every one of those arms was asserted by absence.
# ---------------------------------------------------------------------------

def _start_job(manager, map_id, queue_room_ids, **extra):
    """Put a started job on the map, the way the progress tests seed one."""
    job = {
        "status": "started", "job_id": "rpsj1",
        "queue_room_ids": list(queue_room_ids),
        "completed_room_ids": [],
    }
    job.update(extra)
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[map_id] = job
    return job


def test_rps25_the_runtime_walk_files_only_the_rule_that_actually_matched(rp, hass):
    """[RPS-25] One job, seven rule shapes, one block.

    Five of the six must contribute NOTHING, and each is ignorable for a different
    reason -- a rule that is not a dict, a disabled rule, a modifier rather than a
    blocker, a blocker naming no entity, and a blocker whose entity is off. The sixth
    matches. Driving them in ONE call is the point: five separate tests would each
    prove only that its own shape is survivable, while this bites the SET, which is
    where near-identical guards drift apart.

    THE CORRUPT ROOM ROW IN THE FIXTURE DOES NOT REACH THIS MODULE, measured: ablating
    `run_plan.py`'s own `if not isinstance(room, dict)` left this green, because
    `access_graph.py:283-284` drops every non-dict row while building the normalised
    view this method reads. The row is kept because it is a realistic thing to find in
    storage, but what it proves is the UPSTREAM guard, which [AG-22] owns; the copy
    here is unreachable and is recorded as a ceiling rather than claimed.

    THE ASSERTION IS THE EXACT BLOCKED LIST, NOT ITS LENGTH. `["2"]` names which room
    was filed; a count of one is satisfied by filing the wrong room, and that is the
    failure that matters here -- a mid-job pause attributed to a room the user can see
    is fine, one attributed to the wrong room sends them looking at the wrong window.

    THE INDETERMINATE RULE IS HERE BECAUSE IT CANNOT BE OBSERVED ALONE. Room 4's
    blocker names an entity that does not exist, so `_room_rule_matches_known` reports
    unknown and RP-008 says HOLD-PREVIOUS: neither block nor clear. But a report with
    nothing blocked returns None at :1956 and the diagnostics go with it -- so the
    indeterminate rule is only visible beside a real block, which is exactly how it
    reaches a reader in production too.

    Room 1 grants access, which is required: with blocker rules present and no room
    granting anything, the method bails at :1879-1884 ([RPS-27] pins that).
    """
    rp_, mgr = rp
    _seed(mgr, "rpm25", [
        # 1: the dock room, and the only grant -- without it [RPS-27]'s bail fires
        {"enabled": True, "is_dock_room": True, "grants_access_to": [2, 3, 4]},
        # 2: the one real block
        {"enabled": True, "rules": [_blocker("binary_sensor.rps25_open")]},
        # 3: four shapes that must all be ignored
        {"enabled": True, "rules": [
            "not-a-dict",
            dict(_blocker("binary_sensor.rps25_disabled"), id="b_disabled",
                 enabled=False),
            _modifier("binary_sensor.rps25_mod", {"fan_speed": "Max"}),
            dict(_blocker(""), id="b_noentity"),
            dict(_blocker("binary_sensor.rps25_shut"), id="b_unmatched"),
        ]},
        # 4: a blocker whose entity is absent from the state machine entirely
        {"enabled": True, "rules": [
            dict(_blocker("binary_sensor.rps25_vanished"), id="b_indeterminate"),
        ]},
    ])
    # a corrupt room row, which `_normalized_managed_rooms_with_automation` passes
    # through and the walk must step over
    mgr.data["maps"][_VAC]["rpm25"]["rooms"]["junk"] = "not-a-dict"

    hass.states.async_set("binary_sensor.rps25_open", "on")
    hass.states.async_set("binary_sensor.rps25_disabled", "on")
    hass.states.async_set("binary_sensor.rps25_mod", "on")
    hass.states.async_set("binary_sensor.rps25_shut", "off")
    # rps25_vanished is deliberately never set

    _start_job(mgr, "rpm25", [1, 2, 3, 4])
    report = rp_.get_runtime_path_block_report(
        vacuum_entity_id=_VAC, map_id="rpm25",
        trigger_entity_id="binary_sensor.rps25_open", trigger_entity_state="on",
    )

    assert report is not None, "the matched blocker produced no runtime report at all"
    assert report["directly_blocked_room_ids"] == ["2"], (
        "the wrong rooms were filed as directly blocked: %r"
        % (report["directly_blocked_room_ids"],)
    )
    assert report["job_id"] == "rpsj1"

    assert [r["entity_id"] for r in report["indeterminate_rules"]] == [
        "binary_sensor.rps25_vanished"
    ], "the dropout was not recorded, or a resolvable rule was recorded with it"
    assert report["indeterminate_rules"][0]["room_id"] == 4
    assert "4" not in report["directly_blocked_room_ids"], (
        "RP-008: an INDETERMINATE rule must neither block nor clear -- treating it as "
        "matched is GUARD-1's bug inverted"
    )


def test_rps26_the_runtime_report_is_deduped_by_its_own_signature(rp, hass):
    """[RPS-26] The method is called on every blocker state change, and the caller
    fires an event on whatever it returns -- so returning the same block twice would
    re-pause a run already paused for that reason.

    THE PAIR IS THE CLAIM: the first call reports, the identical second call returns
    None, and then a DIFFERENT trigger state reports again. Two calls alone could not
    separate "deduped" from "only ever answers once"; the third call is what shows the
    signature is about the content and not a one-shot latch.
    """
    rp_, mgr = rp
    _seed(mgr, "rpm26", [
        {"enabled": True, "is_dock_room": True, "grants_access_to": [2]},
        {"enabled": True, "rules": [_blocker("binary_sensor.rps26_open")]},
    ])
    hass.states.async_set("binary_sensor.rps26_open", "on")
    _start_job(mgr, "rpm26", [1, 2])

    first = rp_.get_runtime_path_block_report(
        vacuum_entity_id=_VAC, map_id="rpm26",
        trigger_entity_id="binary_sensor.rps26_open", trigger_entity_state="on",
    )
    assert first is not None and first["directly_blocked_room_ids"] == ["2"]

    again = rp_.get_runtime_path_block_report(
        vacuum_entity_id=_VAC, map_id="rpm26",
        trigger_entity_id="binary_sensor.rps26_open", trigger_entity_state="on",
    )
    assert again is None, "the same block was reported twice -- the run would re-pause"

    moved = rp_.get_runtime_path_block_report(
        vacuum_entity_id=_VAC, map_id="rpm26",
        trigger_entity_id="binary_sensor.rps26_open", trigger_entity_state="on-again",
    )
    assert moved is not None, (
        "a genuinely different trigger state was swallowed by the dedup"
    )


def test_rps27_blocker_rules_with_no_access_graph_authored_report_nothing(rp, hass):
    """[RPS-27] A map where someone wrote blocker rules but no room grants access to
    any other.

    There is no graph to walk, so a mid-job re-evaluation has nothing to say about
    reachability and bails. The contrast with [RPS-25] is one field: that fixture's
    room 1 carries `grants_access_to`, this one's carries none, and the blocker is
    identical and matched in both.

    THE MATCHED BLOCKER IS WHAT MAKES THIS MORE THAN A NULL. `None` is also what an
    idle job, an empty queue and a deduped repeat return, so the input has to be one
    that WOULD report -- the same shape [RPS-25] reports on -- with the grant removed.
    """
    rp_, mgr = rp
    _seed(mgr, "rpm27", [
        {"enabled": True, "is_dock_room": True},
        {"enabled": True, "rules": [_blocker("binary_sensor.rps27_open")]},
    ])
    hass.states.async_set("binary_sensor.rps27_open", "on")
    _start_job(mgr, "rpm27", [1, 2])

    assert rp_.get_runtime_path_block_report(
        vacuum_entity_id=_VAC, map_id="rpm27",
        trigger_entity_id="binary_sensor.rps27_open", trigger_entity_state="on",
    ) is None, (
        "blocker rules with no grants anywhere produced a reachability report"
    )


def test_rps28_the_three_pure_helpers_agree_with_their_core_manager_twins():
    """[RPS-28] `_safe_int`, `_safe_float` and `_display_label` are copied into this
    module from `core/manager.py` -- the comment above them at :75 says so.

    THE CLAIM IS AGREEMENT, NOT BEHAVIOUR. Each copy's behaviour is already pinned on
    the manager side; what nothing checked is that the two copies still answer the same
    way, which is the only property a duplicate can break on its own. A divergence here
    is silent: the planner would read a sentinel one way and the manager the other, and
    both would look locally correct.

    THE NAMED RED INPUT IS `int(float(v))` -> `int(v)` IN THE PLANNER'S COPY, which
    makes `"12.7"` answer 0 here and 12 in the manager. Finding that took a measurement
    and the obvious mutation was DEAD: dropping `"unavailable"` from this copy's
    sentinel tuple changes nothing observable, because `float("unavailable")` then
    raises and the `except (TypeError, ValueError)` returns the same default. FOR EVERY
    STRING SENTINEL IN THAT TUPLE THE GUARD IS SUBSUMED BY ITS OWN EXCEPT -- it is an
    optimisation, not a behaviour, and a divergence test built on it cannot bite.

    So the table carries inputs whose answers differ by ROUTE, not only by guard:
    `"12.7"` (string float), `12.7` (real float), `True` (a bool is an int) and `[]`
    (no conversion at all). `"_"` is the `_display_label` case that normalises to empty
    AFTER passing the first emptiness check -- the arm reached only by a value that is
    non-blank but contains nothing but separators.
    """
    from custom_components.eufy_vacuum.core import manager as core_manager
    from custom_components.eufy_vacuum.planning import run_plan as planner

    sentinels = [None, "", "unknown", "unavailable", "12", "12.7", 12, 12.7, "abc",
                 True, []]
    for value in sentinels:
        assert planner._safe_int(value) == core_manager._safe_int(value), value
        assert planner._safe_float(value) == core_manager._safe_float(value), value

    for value in [None, "", "   ", "_", "-", "__--__", "by_time", "vacuum mop", 7]:
        assert planner._display_label(value) == core_manager._display_label(value), value

    # and the arms those sentinels reach, stated so the table is not just a diff of two
    # unknowns: the absence spellings fall back, junk falls back, "_" normalises to None
    assert planner._safe_int("unavailable", 9) == 9
    assert planner._safe_float("abc", 1.5) == 1.5
    assert planner._display_label("_") is None
    assert planner._display_label("by_time") == "By Time"
