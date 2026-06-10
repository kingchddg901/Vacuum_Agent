"""Delegation wiring smoke-test for core/manager.py.

EufyVacuumManager exposes ~49 thin delegation methods that forward to the
extracted subsystems (RunPlanManager, ActiveJobTracker, AccessGraphManager,
RoomMapManager, MaintenanceManager, ProfileManager). Bug #11 was one of these
that was *called by a listener but never delegated* after the bundle-out.

This test calls each delegation against the real manager and asserts it
forwards without AttributeError — covering the delegation lines and acting as a
regression net for the #11 bug-class (a delegation whose target went missing in
a refactor).

Coverage targets
----------------
[MD-1]  water-model + estimation delegations.
[MD-2]  active-job helper delegations.
[MD-3]  access-graph delegations.
[MD-4]  run-plan delegations (incl. get_runtime_path_block_report).
[MD-5]  room CRUD + maps delegations.
[MD-6]  upkeep / maintenance delegations.
[CMR-1] _find_button_entity_by_tokens: prefix-skip + all-tokens match + None miss.
"""

from __future__ import annotations

import pytest

from homeassistant.helpers import entity_registry as er

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "6"

_ADAPTER = {
    "adapter_id": "t", "source": "t",
    "entities": {
        "task_status": "sensor.alfred_task_status",
        "dock_status": "sensor.alfred_dock_status",
        "active_map": "sensor.alfred_active_map",
        "water_level": "sensor.alfred_water_level",
        "wash_frequency_mode": "select.alfred_wash_mode",
        "wash_frequency_value_time": "number.alfred_wash_interval",
        "charging": "binary_sensor.alfred_charging",
    },
    "water_model_configs": {"X8": {
        "robot_internal_tank_ml": 80, "dock_clean_tank_capacity_ml": 4000,
        "dock_wash_overhead_ml_per_cycle": 100}},
    "vocabulary": {},
    "maintenance_components": {"main_brush": {
        "sensor_suffix": "main_brush", "label": "Main Brush", "icon": "mdi:brush",
        "default_interval_hours": 150.0, "max_interval_hours": 300.0}},
}


@pytest.fixture
def mgr(manager):
    register_adapter_config(_VAC, _ADAPTER)
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2)
    return manager


# ---------------------------------------------------------------------------

def test_water_delegations(mgr):
    """[MD-1]"""
    assert mgr._normalize_water_level_key("High") == "high"
    assert mgr._water_rate_ml_per_minute("high") > 0
    mgr._get_station_clean_water_percent(vacuum_entity_id=_VAC)
    assert isinstance(mgr._get_water_model_config(vacuum_entity_id=_VAC), dict)
    assert isinstance(mgr._derive_wash_frequency_config(vacuum_entity_id=_VAC), dict)
    out = mgr.estimate_job_water_usage(vacuum_entity_id=_VAC, resolved_rooms=[])
    assert "available" in out


def test_active_job_delegations(mgr):
    """[MD-2]"""
    assert mgr._parse_job_timestamp("2026-01-01T00:00:00+00:00") is not None
    assert isinstance(mgr._default_active_job_state(
        vacuum_entity_id=_VAC, map_id=_MAP), dict)
    assert isinstance(mgr._normalize_active_job({"status": "idle"}), dict)
    mgr._derive_active_job_current_room_id({"queue_room_ids": [1, 2]})
    assert isinstance(mgr._is_charging(_VAC), bool)
    assert isinstance(mgr._generate_job_id(), str)
    mgr.record_active_lifecycle_observed(vacuum_entity_id=_VAC, map_id=_MAP)


def test_access_graph_delegations(mgr):
    """[MD-3]"""
    managed = {"1": {"room_id": 1, "name": "K", "is_dock_room": True,
                     "grants_access_to": [2], "rules": []},
               "2": {"room_id": 2, "name": "B", "grants_access_to": [], "rules": []}}
    assert mgr._normalize_grants_access_to([2, 2], room_id=1) == [2]
    assert mgr._normalize_room_rules([]) == []
    v = mgr._validate_room_access_graph(managed_rooms=managed)
    assert "issues" in v
    assert isinstance(mgr._structural_access_graph_issues(v), list)
    assert mgr._access_graph_state(managed, v) in {"blank", "partial", "complete"}
    assert isinstance(mgr._any_rooms_have_rules(managed), bool)
    assert isinstance(mgr._room_rule_matches(
        {"entity_id": "binary_sensor.x", "operator": "exists"}), bool)
    g, r = mgr._build_room_access_views(managed_rooms=managed)
    assert isinstance(g, dict) and isinstance(r, dict)
    assert isinstance(mgr._normalized_managed_rooms_with_automation(
        vacuum_entity_id=_VAC, map_id=_MAP), dict)
    assert "code" in mgr._format_access_graph_issue(
        issue={"type": "self_reference", "room_id": 1}, room_names={})


def test_run_plan_delegations(mgr):
    """[MD-4]"""
    assert isinstance(mgr._room_estimate_minutes_map(
        vacuum_entity_id=_VAC, map_id=_MAP), dict)
    assert mgr._build_blocked_room_entry(
        room_id=1, name="K", source="s", reason="r")["room_id"] == 1
    assert mgr._build_modified_room_entry(room_id=1, name="K")["room_id"] == 1
    plan = mgr._build_effective_start_plan(vacuum_entity_id=_VAC, map_id=_MAP)
    assert "preflight" in plan
    # the #11 method — must exist and forward
    mgr.get_runtime_path_block_report(
        vacuum_entity_id=_VAC, map_id=_MAP, trigger_entity_id="binary_sensor.x")


def test_room_crud_delegations(mgr):
    """[MD-5]"""
    assert isinstance(mgr.get_managed_rooms(
        vacuum_entity_id=_VAC, map_id=_MAP), dict)
    assert isinstance(mgr.get_vacuum_maps(vacuum_entity_id=_VAC), dict)
    rebuilt = mgr.rebuild_map(vacuum_entity_id=_VAC, map_id=_MAP)
    assert isinstance(rebuilt, dict)
    removed = mgr.remove_map(vacuum_entity_id=_VAC, map_id=_MAP)
    assert isinstance(removed, dict)


def test_upkeep_delegations(mgr):
    """[MD-6]"""
    assert isinstance(mgr._get_upkeep_model_meta(vacuum_entity_id=_VAC), dict)
    snap = mgr.get_upkeep_snapshot(vacuum_entity_id=_VAC)
    assert isinstance(snap, dict)


@pytest.mark.parametrize("register,notify", [
    ("register_room_update_callback", "_notify_rooms_updated"),
    ("register_run_profile_update_callback", "_notify_run_profiles_updated"),
    ("register_room_history_update_callback", "_notify_room_history_updated"),
    ("register_room_rule_status_update_callback", "_notify_room_rule_status_updated"),
])
def test_notify_callback_resilience(manager, register, notify):
    """[MD-7] a raising callback is logged and skipped; the others still fire.

    Reclassified from logger-only SKIP: the except sits in a fan-out loop, so a
    failing callback must not block the rest (skip-one-continue resilience).
    """
    seen = []

    def bad(**kw):
        raise RuntimeError("boom")

    def good(**kw):
        seen.append(kw)

    getattr(manager, register)(bad)
    getattr(manager, register)(good)
    getattr(manager, notify)(vacuum_entity_id=_VAC, map_id="6")
    assert seen, "the surviving callback should still fire after one raises"


def test_find_button_entity_by_tokens(manager):
    """[CMR-1] _find_button_entity_by_tokens scans the entity registry for a
    button whose entity_id starts with ``button.<object_id>_`` and contains
    every required token.

    Covers manager.py:803 (skip a registry entity whose id doesn't match the
    ``button.<object_id>_`` prefix) and :806 (return None when no entity carries
    all required tokens). The match path returns the matching ``entry.entity_id``.
    """
    reg = er.async_get(manager.hass)
    # The target reset button for vacuum object_id "alfred".
    reg.async_get_or_create(
        "button", "eufy_vacuum", "uid_reset",
        suggested_object_id="alfred_main_brush_reset",
    )
    # An unrelated button whose id fails the button.alfred_ prefix → exercises
    # the prefix-skip continue (803). It carries the same tokens, so if the
    # prefix gate were absent it would be a false positive.
    reg.async_get_or_create(
        "button", "eufy_vacuum", "uid_other",
        suggested_object_id="other_main_brush_reset",
    )
    assert manager.hass.states.get("button.alfred_main_brush_reset") is None

    # Match path: prefix matches and all tokens present → returns the entity_id.
    assert manager._find_button_entity_by_tokens(
        object_id="alfred", required_tokens=["main_brush", "reset"],
    ) == "button.alfred_main_brush_reset"

    # Miss path (806): a token no registered button carries → None, even though
    # the prefix-matching button.alfred_main_brush_reset exists.
    assert manager._find_button_entity_by_tokens(
        object_id="alfred", required_tokens=["nonexistent"],
    ) is None


def test_remaining_delegations_forward(mgr):
    """[MD-8] the remaining manager seams forward to their subsystems without
    AttributeError — the #11/#13 bug-class net (a delegation lost in a refactor).

    Each call exercises only the forwarding line; the return value is incidental.
    """
    # active-job seams
    assert isinstance(mgr._is_low_battery_return_state(
        vacuum_entity_id=_VAC,
        current_battery=15, vacuum_state="returning", task_status="returning"), bool)
    mgr.update_active_job_recharge_observation(vacuum_entity_id=_VAC, map_id=_MAP)
    mgr.update_active_job_mop_wash_observation(vacuum_entity_id=_VAC, map_id=_MAP)
    mgr.record_active_job_transition(
        vacuum_entity_id=_VAC, map_id=_MAP, entity_id="sensor.x",
        from_state="cleaning", to_state="returning")
    mgr._robot_outside_room_bounds(vacuum_entity_id=_VAC, map_id=_MAP, room_id=1)
    mgr._get_robot_position(_VAC)
    mgr._access_graph_path({}, 1, 2)
    mgr.pause_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    mgr.resume_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    mgr.record_completed_room(vacuum_entity_id=_VAC, map_id=_MAP, room_id=1)
    mgr.mark_active_job_finalized(vacuum_entity_id=_VAC, map_id=_MAP, finalize_result=None)
    mgr.get_paused_job_timeout_report(vacuum_entity_id=_VAC, map_id=_MAP)

    # maintenance seams
    assert isinstance(mgr.get_maintenance_state(vacuum_entity_id=_VAC), dict)
    mgr.get_maintenance_remaining(
        vacuum_entity_id=_VAC, component="main_brush", interval_hours=150.0)
    mgr._get_upkeep_item_guide(
        vacuum_entity_id=_VAC, model_code="X8", component="main_brush", item_kind="maintenance")
    mgr._get_replacement_reset_entity(vacuum_entity_id=_VAC, component="main_brush")

    # onboarding seams
    assert isinstance(mgr.check_for_new_rooms(vacuum_entity_id=_VAC, map_id=_MAP), bool)
    assert isinstance(mgr.reset_onboarding(vacuum_entity_id=_VAC, map_id=_MAP), dict)

    # capabilities / profile / room / run-plan seams
    assert isinstance(mgr.refresh_vacuum_capabilities(vacuum_entity_id=_VAC), dict)
    mgr.overwrite_room_profile_from_room(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1, profile_name="ghost")
    assert isinstance(mgr.discover_rooms(vacuum_entity_id=_VAC, map_id=_MAP), dict)
    assert isinstance(mgr._confirmation_token_for_preflight(
        vacuum_entity_id=_VAC, map_id=_MAP,
        selected_room_ids=[1, 2], included_room_ids=[1], blocked_room_ids=[2]), str)


@pytest.mark.parametrize("method", [
    "async_wash_mop",
    "async_dry_mop",
    "async_empty_dust",
    "async_stop_dry_mop",
])
async def test_async_dock_action_delegations(mgr, method):
    """[MD-9] async dock-action delegations forward to DockManager.

    async_wash_mop / async_dry_mop / async_empty_dust / async_stop_dry_mop are
    the manager's async delegations; each awaits
    DockManager._async_run_dock_action and returns its dict. With the bare mgr
    fixture (no docked vacuum_state, no dock action button entities) the action
    is gated, so a *blocked* dict comes back — which still covers the delegation
    line and proves the await/forward wiring is intact (the #11/#13 bug-class).
    """
    out = await getattr(mgr, method)(vacuum_entity_id=_VAC, map_id=_MAP)
    assert isinstance(out, dict)
    # The gated path returns the structured action result, not a bare {}.
    assert out["performed"] is False
    assert out["allowed"] is False
    assert "reason" in out


@pytest.mark.parametrize("method,flag,reason", [
    ("async_pause_active_job", "paused", "no_started_job"),
    ("async_resume_active_job", "resumed", "no_paused_job"),
    ("async_cancel_active_job", "cancelled", "no_active_job"),
])
async def test_async_job_control_delegations(mgr, method, flag, reason):
    """[MD-8] async job-control delegations forward to ActiveJobTracker.

    async_pause_active_job / async_resume_active_job / async_cancel_active_job
    are the manager's async delegations (manager.py:3526/3530/3534); each awaits
    the matching ActiveJobTracker coroutine and returns its dict. With the bare
    mgr fixture no active job is seeded, so the tracked job is the default
    ``status == "idle"`` state. Each method therefore takes its no-job
    short-circuit *before* issuing any ``vacuum.*`` service call or entering the
    cancel-confirm poll loop, returning a structured negative-result dict. That
    still covers the delegation/forward line and proves the await wiring is
    intact (the #11/#13 bug-class), while keeping the test deterministic — no
    real services, no asyncio.sleep, no timers to cancel.
    """
    out = await getattr(mgr, method)(vacuum_entity_id=_VAC, map_id=_MAP)
    assert isinstance(out, dict)
    # The no-job path returns the structured negative result, not a bare {}.
    assert out[flag] is False
    assert out["reason"] == reason
    assert out["vacuum_entity_id"] == _VAC
    assert out["map_id"] == _MAP
    assert isinstance(out["active_job"], dict)
