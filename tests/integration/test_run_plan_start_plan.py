"""Tests for planning/run_plan.py::_build_effective_start_plan.

The authoritative rule-evaluation point for job start. Driven against the real
``manager`` fixture (so the access-graph + queue + profile delegation all run
for real), with rooms seeded into manager.data and rule entity states set on
hass.

Coverage targets (high-priority: adapter-degraded gates, state-machine branches)
--------------------------------------------------------------------------------
[SP-1]  blank graph + no rules → ready preflight, all rooms selected.
[SP-2]  partial graph (invalid grants) → blocked incomplete_access_graph.
[SP-3]  blank graph + rooms have rules → blocked access_graph_required_for_rules.
[SP-4]  complete graph, blocker rule, no grants → blocked access_graph_required.
[SP-5]  valid graph + matching direct blocker → room in blocked_rooms + confirm.
[SP-6]  valid graph + matching modifier → modified_rooms carries the changes.
[SP-7]  access-dependency propagation: blocked parent blocks its child.
[SP-8]  modifier fan-out: a rule's fan_out_room_ids apply to a derived target.
[SP-9]  get_runtime_path_block_report exists on the real manager and reports a
        mid-job blocker (regression guard for the method lost in the bundle-out).
[SP-10] fan-out loop's per-target + matched-rule guards: only a valid, selected,
        unblocked target gets the change; no-entity/no-match/empty-changes skip.
[SP-11] runtime path-block: a remaining room with its OWN blocker is directly
        blocked, while a reachable sibling propagates accessible and is not flagged.
[SP-12] mop-carpet caution: an attached water tank + an included carpet room →
        non-blocking warning; None when tank off / no carpet / no tank sensor.
[SP-13] order advisory: a path-optimizing brand (honors_clean_order False) with
        2+ rooms → advisory; None when order is honored or one room runs.
[SP-14] strict_order: builds one phase per room for a path-optimizing flat-id
        brand; gated off (one batch phase) when the brand honors order.
[SP-15] stashed run steps survive a PREFLIGHT (peek) and are consumed only by the real
        dispatch (consume_pending_steps=True) — the shipped bug where get_start_status'
        preflight popped the stash, so a stepped profile ran an atomic (flat) job.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.planning.run_plan import RunPlanManager

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
    """[SP-1]"""
    rp_, mgr = rp
    _seed(mgr, "spm1", [{"enabled": True}, {"enabled": True}])
    out = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm1")
    pf = out["preflight"]
    assert pf["blocked"] is False
    assert pf["reason"] == "ready"
    assert set(pf["selected_room_ids"]) == {1, 2}
    assert pf["blocked_room_ids"] == []


def test_partial_graph_blocks(rp):
    """[SP-2] a dock room granting to a missing room → invalid → partial → blocked."""
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
    """[SP-3]"""
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
    """[SP-4] single dock room + blocker rule, no grants → access_graph_required."""
    rp_, mgr = rp
    _seed(mgr, "spm4", [
        {"enabled": True, "is_dock_room": True,
         "rules": [_blocker("binary_sensor.win")]},
    ])
    out = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm4")
    pf = out["preflight"]
    assert pf["blocked"] is True
    assert pf["reason"] == "access_graph_required"


def test_direct_blocker_fires(rp, hass):
    """[SP-5] valid graph, blocker on a selected room whose entity is on."""
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


def test_modifier_applies_changes(rp, hass):
    """[SP-6] valid graph, modifier on a selected room → changes in modified_rooms."""
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
    """[SP-7] blocking a parent room cascades to its dependent child."""
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
    """[SP-8] a modifier on the dock room fans its changes out to room 2."""
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
    """[SP-9] real-manager mid-job path-block re-evaluation.

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


def test_modifier_fan_out_guard_branches(rp, hass):
    """[SP-10] the fan-out loop's per-target + matched-rule guards.

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
    """[SP-11] a remaining room with its OWN blocker is classified directly
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
    """[SP-11b] a trigger that blocks no remaining room → report is None, and the
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
    """[SP-11c] when every queued room is already completed there is nothing
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
    """[SP-12] tank attached + an included carpet room -> a non-blocking caution
    naming the room; None when the tank is off, no carpet room is included, or the
    brand declares no tank sensor (Eufy)."""
    from custom_components.eufy_vacuum.adapters.registry import (
        register_adapter_config,
        unregister_adapter_config,
    )

    rp_, mgr = rp
    rooms = _seed(mgr, "spm12", [
        {"enabled": True, "floor_type": "carpet"},
        {"enabled": True, "floor_type": "hardwood"},
    ])
    carpet_name = rooms["1"]["name"]
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "entities": {"mop_active": "binary_sensor.tank"},
    })
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
        unregister_adapter_config(_VAC)

    # No tank sensor declared (Eufy) -> never warns, even with a carpet room.
    set_room_field(mgr, 1, map_id="spm12", floor_type="carpet")
    pf = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm12")["preflight"]
    assert pf["mop_carpet_warning"] is None


def test_order_advisory(rp):
    """[SP-13] order_advisory surfaces for a path-optimizing brand (honors_clean_order
    False) with 2+ included rooms; None when order is honored (default) or one room
    runs."""
    from custom_components.eufy_vacuum.adapters.registry import (
        register_adapter_config,
        unregister_adapter_config,
    )

    rp_, mgr = rp
    try:
        # Default (no capability declared) -> honored -> no advisory (default-REJECT).
        register_adapter_config(_VAC, {
            "adapter_id": "e", "source": "code", "capabilities": {}})
        _seed(mgr, "spm13a", [{"enabled": True}, {"enabled": True}])
        pf = rp_._build_effective_start_plan(vacuum_entity_id=_VAC, map_id="spm13a")["preflight"]
        assert pf["order_advisory"] is None

        # Path-optimizing brand + 2 rooms -> advisory.
        register_adapter_config(_VAC, {
            "adapter_id": "rb", "source": "code",
            "capabilities": {"honors_clean_order": False}})
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
    """[SP-14] strict_order builds one single-segment phase per room for a
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
        register_adapter_config(_VAC, {
            "adapter_id": "rb", "source": "code",
            "capabilities": {"honors_clean_order": False},
            "dispatch": {"template": "roborock_segment_clean", "passes_max": 3},
        })
        phases = rp_._build_dispatch_phases(
            vacuum_entity_id=_VAC, map_id="spm14",
            managed_rooms=rooms, queue_room_ids=[1, 2], strict_order=True,
        )
        assert len(phases) == 2
        assert phases[0]["payload"]["segments"] == [1]
        assert phases[1]["payload"]["segments"] == [2]

        # Order-honoring brand -> strict_order ignored (single batch phase).
        register_adapter_config(_VAC, {
            "adapter_id": "e", "source": "code",
            "capabilities": {"honors_clean_order": True},
            "dispatch": {"template": "roborock_segment_clean"},
        })
        phases = rp_._build_dispatch_phases(
            vacuum_entity_id=_VAC, map_id="spm14",
            managed_rooms=rooms, queue_room_ids=[1, 2], strict_order=True,
        )
        assert len(phases) == 1
        assert phases[0]["payload"]["segments"] == [1, 2]
    finally:
        unregister_adapter_config(_VAC)


def test_pending_steps_survive_preflight(rp):
    """[SP-15] a preflight (peek) must NOT eat the stashed run steps — only the real dispatch
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
