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
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.planning.run_plan import RunPlanManager

from .conftest import setup_map


_VAC = "vacuum.alfred"


@pytest.fixture
def rp(manager):
    return RunPlanManager(manager), manager


def _seed(manager, map_id, rooms_config):
    """Seed N managed rooms then merge per-room overrides; return the bucket."""
    setup_map(manager, _VAC, map_id, count=len(rooms_config))
    bucket = manager.data["maps"][_VAC][map_id]["rooms"]
    for i, cfg in enumerate(rooms_config, start=1):
        bucket[str(i)].update(cfg)
    return bucket


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
