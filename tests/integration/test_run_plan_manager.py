"""Tests for planning/run_plan.py — RunPlanManager (mock manager + real hass).

RunPlanManager hangs off the core manager and reads adapter config
(water_model_configs / vocabulary / entities), manager capability getters, and
live hass states. Tests drive it with a MagicMock manager (``.data``, ``.hass``,
capability/meta getters) plus register_adapter_config for the adapter-config
driven helpers.

Coverage targets
----------------
[RPM-1]  _normalize_water_level_key: empty→off, canonical passthrough, alias, raw.
[RPM-2]  _water_rate_ml_per_minute: per-level rates + unknown default.
[RPM-3]  _get_station_clean_water_percent: numeric state, clamp, missing/negative→None.
[RPM-4]  _get_water_model_config: known model → available, unknown → unavailable.
[RPM-5]  _derive_wash_frequency_config: alias mode + interval clamp + default.
[RPM-6]  estimate_job_water_usage: model_unsupported early return.
[RPM-7]  estimate_job_water_usage: full positive path (robot + wash + clean tank).
[RPM-8]  _room_estimate_minutes_map: learning estimates → id→minutes; no learning → {}.
[RPM-9]  _build_blocked_room_entry / _build_modified_room_entry canonical shape.
[RPM-10] _confirmation_token_for_preflight deterministic + 12 hex chars.
[RPM-11] _update_room_rule_status_snapshot delegates to the manager.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.planning.run_plan import RunPlanManager


_VAC = "vacuum.alfred"


@pytest.fixture
def rpm(hass):
    """Return (RunPlanManager, mock_manager) with a real hass for states."""
    mgr = MagicMock()
    mgr.hass = hass
    mgr.data = {}
    return RunPlanManager(mgr), mgr


# ---------------------------------------------------------------------------
# water model helpers (pure-ish)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,aliases,expected", [
    ("", None, "off"),
    (None, None, "off"),
    ("High", None, "high"),
    ("LOW", None, "low"),
    ("med-ium", None, "med ium"),          # separators→space, not a canonical key
    ("Aqua", {"aqua": "high"}, "high"),    # adapter alias lookup
    ("weird", None, "weird"),              # unknown → compact passthrough
])
def test_normalize_water_level_key(rpm, value, aliases, expected):
    """[RPM-1]"""
    rm, _ = rpm
    assert rm._normalize_water_level_key(value, aliases=aliases) == expected


@pytest.mark.parametrize("level,expected", [
    ("off", 0.0), ("low", 3.2), ("medium", 4.0), ("high", 5.3),
    ("", 0.0),            # empty → off → 0.0
    ("mystery", 4.0),     # unknown key → default 4.0
])
def test_water_rate(rpm, level, expected):
    """[RPM-2]"""
    rm, _ = rpm
    assert rm._water_rate_ml_per_minute(level) == pytest.approx(expected)


def test_station_clean_water_percent(rpm, hass):
    """[RPM-3]"""
    rm, mgr = rpm
    caps = {"entities": {"water_level": "sensor.alfred_water"}}
    # numeric state in range
    hass.states.async_set("sensor.alfred_water", "75")
    assert rm._get_station_clean_water_percent(
        vacuum_entity_id=_VAC, capabilities=caps) == pytest.approx(75.0)
    # over 100 → clamped
    hass.states.async_set("sensor.alfred_water", "140")
    assert rm._get_station_clean_water_percent(
        vacuum_entity_id=_VAC, capabilities=caps) == pytest.approx(100.0)
    # unavailable / non-numeric → None
    hass.states.async_set("sensor.alfred_water", "unavailable")
    assert rm._get_station_clean_water_percent(
        vacuum_entity_id=_VAC, capabilities=caps) is None
    # no declared entity → None
    assert rm._get_station_clean_water_percent(
        vacuum_entity_id=_VAC, capabilities={"entities": {}}) is None


def test_water_model_config(rpm):
    """[RPM-4]"""
    rm, mgr = rpm
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "water_model_configs": {
            "X8": {"model_name": "X8 Pro", "dock_clean_tank_capacity_ml": 4000},
        },
    })
    # known model code → available with merged fields
    mgr._get_upkeep_model_meta.return_value = {"code": "X8", "name": "X8 Pro"}
    cfg = rm._get_water_model_config(vacuum_entity_id=_VAC)
    assert cfg["available"] is True
    assert cfg["model_code"] == "X8"
    assert cfg["dock_clean_tank_capacity_ml"] == 4000
    # unknown model code → empty config → unavailable
    mgr._get_upkeep_model_meta.return_value = {"code": "ZZ", "name": None}
    assert rm._get_water_model_config(vacuum_entity_id=_VAC)["available"] is False


def test_derive_wash_frequency_config(rpm, hass):
    """[RPM-5]"""
    rm, mgr = rpm
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {
            "wash_frequency_mode": "select.wash_mode",
            "wash_frequency_value_time": "number.wash_interval",
        },
        "vocabulary": {"wash_frequency_mode_aliases": {"by room": "by_room"}},
    })
    hass.states.async_set("select.wash_mode", "By Room")
    hass.states.async_set("number.wash_interval", "18")
    cfg = rm._derive_wash_frequency_config(vacuum_entity_id=_VAC)
    assert cfg["mode"] == "by_room"
    assert cfg["interval_minutes"] == pytest.approx(18.0)
    assert cfg["mode_available"] is True and cfg["interval_available"] is True

    # interval below floor (15) clamps up; unknown mode → "unknown"
    hass.states.async_set("select.wash_mode", "Whatever")
    hass.states.async_set("number.wash_interval", "5")
    cfg2 = rm._derive_wash_frequency_config(vacuum_entity_id=_VAC)
    assert cfg2["mode"] == "unknown"
    assert cfg2["interval_minutes"] == pytest.approx(15.0)


# ---------------------------------------------------------------------------
# water usage estimation
# ---------------------------------------------------------------------------

def test_estimate_model_unsupported(rpm):
    """[RPM-6]"""
    rm, mgr = rpm
    register_adapter_config(_VAC, {"adapter_id": "t", "source": "t",
                                   "water_model_configs": {}})
    mgr._get_upkeep_model_meta.return_value = {"code": "ZZ", "name": None}
    out = rm.estimate_job_water_usage(vacuum_entity_id=_VAC, resolved_rooms=[])
    assert out["available"] is False
    assert out["reason"] == "model_unsupported"


def test_estimate_full_path(rpm, hass):
    """[RPM-7] one high-water mop room → robot + bookend wash + clean-tank math."""
    rm, mgr = rpm
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "water_model_configs": {
            "X8": {
                "model_name": "X8 Pro",
                "robot_internal_tank_ml": 80,
                "dock_clean_tank_capacity_ml": 4000,
                "dock_wash_overhead_ml_per_cycle": 100,
            },
        },
        "entities": {
            "water_level": "sensor.alfred_water",
            "wash_frequency_mode": "select.wash_mode",
            "wash_frequency_value_time": "number.wash_interval",
        },
        "vocabulary": {"wash_frequency_mode_aliases": {"by room": "by_room"}},
    })
    mgr._get_upkeep_model_meta.return_value = {"code": "X8", "name": "X8 Pro"}
    mgr.get_vacuum_capabilities.return_value = {
        "entities": {"water_level": "sensor.alfred_water"}}
    hass.states.async_set("sensor.alfred_water", "75")
    hass.states.async_set("select.wash_mode", "By Room")
    hass.states.async_set("number.wash_interval", "20")

    out = rm.estimate_job_water_usage(
        vacuum_entity_id=_VAC,
        resolved_rooms=[{"room_id": 1, "name": "Kitchen",
                         "clean_mode": "vacuum_mop", "water_level": "high"}],
        room_timeline=[{"room_id": 1, "minutes": 10}],
    )
    assert out["available"] is True
    assert out["mopping_room_count"] == 1
    # 10 min * 5.3 ml/min (high)
    assert out["estimated_robot_water_used_ml"] == pytest.approx(53.0)
    # by_room → 1 cycle, floored to 2 bookend washes
    assert out["wash_cycle_count"] == 2
    assert out["estimated_dock_wash_water_used_ml"] == pytest.approx(200.0)
    # 75% of 4000 ml clean tank
    assert out["available_clean_tank_ml"] == pytest.approx(3000.0)
    assert out["not_enough_clean_water"] is False
    assert len(out["rooms"]) == 1


def test_estimate_no_station_water_leaves_clean_tank_unknown(rpm, hass):
    """[RPM-7b] no station-water sensor (percent None) → estimate still available
    but the clean-tank fields stay None (arc 476->500: clean-tank block skipped)."""
    rm, mgr = rpm
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "water_model_configs": {
            "X8": {
                "model_name": "X8 Pro",
                "robot_internal_tank_ml": 80,
                "dock_clean_tank_capacity_ml": 4000,
                "dock_wash_overhead_ml_per_cycle": 100,
            },
        },
        # No water_level entity declared → station_water_percent resolves to None.
        "entities": {
            "wash_frequency_mode": "select.wash_mode",
            "wash_frequency_value_time": "number.wash_interval",
        },
        "vocabulary": {"wash_frequency_mode_aliases": {"by room": "by_room"}},
    })
    mgr._get_upkeep_model_meta.return_value = {"code": "X8", "name": "X8 Pro"}
    mgr.get_vacuum_capabilities.return_value = {"entities": {}}
    hass.states.async_set("select.wash_mode", "By Room")
    hass.states.async_set("number.wash_interval", "20")

    out = rm.estimate_job_water_usage(
        vacuum_entity_id=_VAC,
        resolved_rooms=[{"room_id": 1, "name": "Kitchen",
                         "clean_mode": "vacuum_mop", "water_level": "high"}],
        room_timeline=[{"room_id": 1, "minutes": 10}],
    )
    assert out["available"] is True
    # robot/wash accounting still computed
    assert out["estimated_robot_water_used_ml"] == pytest.approx(53.0)
    assert out["estimated_dock_wash_water_used_ml"] == pytest.approx(200.0)
    # but the station-water-derived clean-tank contract fields are left unknown
    assert out["station_clean_water_percent"] is None
    assert out["available_clean_tank_ml"] is None
    assert out["estimated_clean_tank_remaining_ml"] is None
    assert out["estimated_clean_tank_remaining_percent"] is None
    assert out["clean_water_shortfall_ml"] is None
    assert out["not_enough_clean_water"] is False
    assert out["low_clean_water_margin"] is False


# ---------------------------------------------------------------------------
# run-plan helpers
# ---------------------------------------------------------------------------

def test_room_estimate_minutes_map(rpm):
    """[RPM-8]"""
    rm, mgr = rpm
    learning = MagicMock()
    learning.get_room_learning_estimates.return_value = {"rooms": [
        {"room_id": 1, "minutes": 12.5},
        {"room_id": 2, "minutes": None},     # no minutes → skipped
        {"room_id": 0, "minutes": 9},         # non-positive id → skipped
        "junk",                                # non-dict → skipped
    ]}
    mgr._get_learning_manager.return_value = learning
    mgr._get_battery_level.return_value = 90
    out = rm._room_estimate_minutes_map(vacuum_entity_id=_VAC, map_id="6")
    assert out == {1: pytest.approx(12.5)}

    # no learning manager → {}
    mgr._get_learning_manager.return_value = None
    assert rm._room_estimate_minutes_map(vacuum_entity_id=_VAC, map_id="6") == {}


def test_build_room_entries(rpm):
    """[RPM-9]"""
    rm, _ = rpm
    blocked = rm._build_blocked_room_entry(
        room_id=3, name="Den", source="direct_rule", reason="window_open",
        triggered_rule_id="r1")
    assert blocked["room_id"] == 3 and blocked["reason"] == "window_open"
    assert blocked["source"] == "direct_rule"
    assert blocked["trigger_entity_id"] is None

    modified = rm._build_modified_room_entry(
        room_id=4, name="Hall", derived=True, source_room_id=3)
    assert modified["changes"] == {} and modified["triggered_rule_ids"] == []
    assert modified["derived"] is True and modified["source_room_id"] == 3


def test_confirmation_token_deterministic(rpm):
    """[RPM-10]"""
    rm, _ = rpm
    kwargs = dict(vacuum_entity_id=_VAC, map_id="6",
                  selected_room_ids=[1, 2, 3], included_room_ids=[1, 2],
                  blocked_room_ids=[3])
    t1 = rm._confirmation_token_for_preflight(**kwargs)
    t2 = rm._confirmation_token_for_preflight(**kwargs)
    assert t1 == t2 and len(t1) == 12
    int(t1, 16)  # valid hex
    # different inputs → different token
    kwargs["blocked_room_ids"] = []
    assert rm._confirmation_token_for_preflight(**kwargs) != t1


def test_update_room_rule_status_snapshot_delegates(rpm):
    """[RPM-11]"""
    rm, mgr = rpm
    rm._update_room_rule_status_snapshot(
        vacuum_entity_id=_VAC, map_id="6", managed_rooms={}, selected_room_ids=[1],
        included_room_ids=[1], blocked_rooms=[], modified_rooms=[], preflight={})
    mgr._update_room_rule_status_snapshot.assert_called_once()
    kwargs = mgr._update_room_rule_status_snapshot.call_args.kwargs
    assert kwargs["vacuum_entity_id"] == _VAC and kwargs["map_id"] == "6"
