"""Tests for core/capabilities.py — generic vacuum capability detection.

Pure HA state/registry probing driven by adapter-supplied candidate lists and
hints. Tests use the real ``hass`` fixture for the state machine + entity
registry; no manager is required.

Coverage targets
----------------
[CAP-1]  detect_capabilities: minimal (no adapter inputs) reads supported_features.
[CAP-2]  detect_capabilities: entity present → support + available flags True.
[CAP-3]  detect_capabilities: hint OR entity presence for mop/dust/path flags.
[CAP-4]  detect_capabilities: robot position needs both x and y.
[CAP-5]  _detect_maintenance_sources: suffix entity, None suffix, swivel proxy.
[CAP-6]  _find_registry_entity_by_tokens: prefix + token match.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.core.capabilities import (
    _detect_maintenance_sources,
    _find_registry_entity_by_tokens,
    detect_capabilities,
)

from homeassistant.helpers import entity_registry as er


_VAC = "vacuum.alfred"


def test_detect_minimal(hass):
    """[CAP-1] no adapter inputs → minimal map, supported_features from state."""
    hass.states.async_set(_VAC, "docked", {"supported_features": 12})
    caps = detect_capabilities(hass, vacuum_entity_id=_VAC)
    assert caps["vacuum_entity_id"] == _VAC
    assert caps["supported_features"] == 12
    assert caps["model_family"] == "generic"
    assert caps["supports_rooms"] is False
    assert caps["supports_robot_position"] is False


def test_detect_entity_present(hass):
    """[CAP-2] declared entity in the state machine → support + available."""
    hass.states.async_set(_VAC, "docked")
    hass.states.async_set("sensor.alfred_map", "6")
    hass.states.async_set("sensor.alfred_water", "80")
    caps = detect_capabilities(
        hass,
        vacuum_entity_id=_VAC,
        entity_candidates={
            "active_map": ["sensor.alfred_map"],
            "water_level": ["sensor.alfred_water"],
        },
        model_family="x10",
    )
    assert caps["model_family"] == "x10"
    assert caps["supports_active_map"] is True
    assert caps["active_map_available"] is True
    assert caps["supports_station_water"] is True
    assert caps["entities"]["active_map"] == "sensor.alfred_map"
    # mop features derive from water_level presence
    assert caps["supports_mop_features"] is True


def test_detect_hint_or_presence(hass):
    """[CAP-3] capability hints flip support True even without an entity."""
    hass.states.async_set(_VAC, "docked")
    caps = detect_capabilities(
        hass,
        vacuum_entity_id=_VAC,
        capability_hints={
            "supports_mop_wash": True,
            "supports_empty_dust": True,
        },
    )
    assert caps["supports_mop_wash"] is True
    assert caps["supports_empty_dust"] is True
    # no path-control hint and no entity → False
    assert caps["supports_path_control"] is False


def test_detect_robot_position_needs_both(hass):
    """[CAP-4]"""
    hass.states.async_set(_VAC, "docked")
    hass.states.async_set("sensor.alfred_x", "1.0")
    # only x present → not supported
    caps = detect_capabilities(
        hass, vacuum_entity_id=_VAC,
        entity_candidates={"robot_position_x": ["sensor.alfred_x"],
                           "robot_position_y": ["sensor.alfred_y"]},
    )
    assert caps["supports_robot_position"] is False
    assert caps["robot_position_status"] == "inactive"
    # both present → supported + available
    hass.states.async_set("sensor.alfred_y", "2.0")
    caps2 = detect_capabilities(
        hass, vacuum_entity_id=_VAC,
        entity_candidates={"robot_position_x": ["sensor.alfred_x"],
                           "robot_position_y": ["sensor.alfred_y"]},
    )
    assert caps2["supports_robot_position"] is True
    assert caps2["robot_position_available"] is True
    assert caps2["robot_position_status"] == "available"


def test_detect_maintenance_sources(hass):
    """[CAP-5] suffix entity resolves; None suffix → None; swivel proxies filter."""
    hass.states.async_set("sensor.alfred_main_brush_remaining", "90")
    hass.states.async_set("sensor.alfred_filter_remaining", "75")
    sources = _detect_maintenance_sources(
        hass,
        object_id="alfred",
        maintenance_components={
            "main_brush": {"sensor_suffix": "main_brush"},
            "side_brush": {"sensor_suffix": "side_brush"},   # no entity → None
            "no_suffix": {"sensor_suffix": None},             # None suffix → None
            "swivel_wheel": {"sensor_suffix": "swivel_wheel"},  # proxies filter
        },
    )
    assert sources["main_brush"] == "sensor.alfred_main_brush_remaining"
    assert sources["side_brush"] is None
    assert sources["no_suffix"] is None
    # swivel wheel proxies the filter entity when present
    assert sources["swivel_wheel"] == "sensor.alfred_filter_remaining"


def test_detect_maintenance_swivel_own_fallback(hass):
    """[CAP-5] no filter entity → swivel falls back to its own sensor."""
    hass.states.async_set("sensor.alfred_swivel_wheel_remaining", "60")
    sources = _detect_maintenance_sources(
        hass, object_id="alfred",
        maintenance_components={"swivel_wheel": {"sensor_suffix": "swivel_wheel"}},
    )
    assert sources["swivel_wheel"] == "sensor.alfred_swivel_wheel_remaining"


async def test_find_registry_entity_by_tokens(hass):
    """[CAP-6]"""
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "sensor", "eufy_vacuum", "alfred_main_brush_life",
        suggested_object_id="alfred_main_brush_life",
    )
    found = _find_registry_entity_by_tokens(
        hass, domain="sensor", object_id_prefix="alfred",
        required_tokens=["main_brush", "life"],
    )
    assert found is not None and "main_brush_life" in found
    # a token that doesn't match → None
    miss = _find_registry_entity_by_tokens(
        hass, domain="sensor", object_id_prefix="alfred",
        required_tokens=["nonexistent_token"],
    )
    assert miss is None
