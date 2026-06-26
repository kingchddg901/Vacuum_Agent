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
[CAP-7]  get_vacuum_capabilities: newly-known model refreshes cached caps even with refresh=False.
[CAP-8]  detect_capabilities: an explicit supports_water_control hint wins over the
         mop-derived default (the Roborock S6 declares it False — water is unsettable).
[CAP-9]  detect_capabilities: has_attribute_rooms hint reports rooms/segments support
         WITHOUT a map entity (scalar/Tuya transport); supports_active_map stays False.
[CAP-10] refresh_vacuum_capabilities reproduces startup inputs: re-passes the adapter's
         stored model_family + capability_hints, so a refresh keeps model_family (not
         "generic") and keeps has_attribute_rooms (scalar supports_rooms).
[CAP-11] get_vacuum_capabilities self-heals a stale persisted model_family: re-detects
         (even refresh=False) when the adapter now declares a different family; idempotent.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.core.capabilities import (
    _detect_maintenance_sources,
    _find_registry_entity_by_tokens,
    detect_capabilities,
)
from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

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


def test_detect_water_control_hint_wins(hass):
    """[CAP-8] an explicit supports_water_control=False hint overrides the mop default.

    Mop features are present (water_level entity → supports_mop_features True), which
    would otherwise derive supports_water_control True. The Roborock S6 declares
    supports_water_control False because SET_WATER_BOX/MOP_MODE are unsupported, and
    that explicit hint must win.
    """
    hass.states.async_set(_VAC, "docked")
    hass.states.async_set("sensor.alfred_water", "80")
    caps = detect_capabilities(
        hass,
        vacuum_entity_id=_VAC,
        entity_candidates={"water_level": ["sensor.alfred_water"]},
        capability_hints={"supports_water_control": False},
    )
    # mop support is still derived from the water_level entity ...
    assert caps["supports_mop_features"] is True
    # ... but the explicit hint overrides the mop-derived water-control default.
    assert caps["supports_water_control"] is False


def test_detect_water_control_defaults_to_mop_without_hint(hass):
    """[CAP-8] with no hint, supports_water_control still derives from mop support
    (the unchanged Eufy path)."""
    hass.states.async_set(_VAC, "docked")
    hass.states.async_set("sensor.alfred_water", "80")
    caps = detect_capabilities(
        hass,
        vacuum_entity_id=_VAC,
        entity_candidates={"water_level": ["sensor.alfred_water"]},
    )
    assert caps["supports_mop_features"] is True
    assert caps["supports_water_control"] is True


def test_detect_attribute_rooms_hint(hass):
    """[CAP-9] has_attribute_rooms reports room/segment support without a map
    entity — the scalar/Tuya transport, where the room list lives in the vacuum's
    ``segments`` attribute and there is NO active_map sensor. supports_active_map
    must stay False: there is no map entity to dereference."""
    hass.states.async_set(_VAC, "docked")
    caps = detect_capabilities(
        hass,
        vacuum_entity_id=_VAC,
        capability_hints={"has_attribute_rooms": True},
    )
    assert caps["supports_rooms"] is True
    assert caps["supports_segments"] is True
    assert caps["supports_active_map"] is False
    assert caps["active_map_available"] is False


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
    """[CAP-5] full-suffix entity resolves; None suffix → None; proxy_for wins."""
    hass.states.async_set("sensor.alfred_main_brush_remaining", "90")
    hass.states.async_set("sensor.alfred_filter_remaining", "75")
    sources = _detect_maintenance_sources(
        hass,
        object_id="alfred",
        maintenance_components={
            "main_brush": {"sensor_suffix": "main_brush_remaining"},
            "side_brush": {"sensor_suffix": "side_brush_remaining"},  # no entity → None
            "no_suffix": {"sensor_suffix": None},                     # None suffix → None
            "filter": {"sensor_suffix": "filter_remaining"},
            # proxies filter when present
            "swivel_wheel": {"sensor_suffix": "swivel_wheel_remaining", "proxy_for": "filter"},
        },
    )
    assert sources["main_brush"] == "sensor.alfred_main_brush_remaining"
    assert sources["side_brush"] is None
    assert sources["no_suffix"] is None
    # swivel wheel proxies the filter entity when present
    assert sources["swivel_wheel"] == "sensor.alfred_filter_remaining"


def test_detect_maintenance_swivel_own_fallback(hass):
    """[CAP-5] proxy target absent → component falls back to its own sensor."""
    hass.states.async_set("sensor.alfred_swivel_wheel_remaining", "60")
    sources = _detect_maintenance_sources(
        hass, object_id="alfred",
        maintenance_components={
            "swivel_wheel": {"sensor_suffix": "swivel_wheel_remaining", "proxy_for": "filter"},
        },
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


def test_get_vacuum_capabilities_refreshes_when_model_newly_known(manager):
    """[CAP-7] cached caps with no detected_model + a now-known model triggers a
    refresh even with refresh=False (upgrades the cached snapshot on first detect)."""
    manager.data.setdefault("capabilities", {})[_VAC] = {"supports_rooms": True}
    out = manager.get_vacuum_capabilities(
        vacuum_entity_id=_VAC, detected_model="X8", refresh=False)
    assert out["detected_model"] == "X8"


def test_refresh_preserves_model_family_and_attribute_room_hint(hass, manager):
    """[CAP-10] A capability REFRESH must reproduce the SAME detect_capabilities
    inputs as startup by re-passing the adapter's stored model_family +
    capability_hints. Without that, refresh_vacuum_capabilities omits model_family
    (detect_capabilities defaults it to 'generic') and drops INPUT-ONLY hints like
    has_attribute_rooms — so an attribute-mode/scalar device silently loses
    supports_rooms on any refresh. Guards the live regression observed on an X10
    (detected_model 'T2351' but model_family 'generic')."""
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        # Attribute-mode shape: NO active_map entity at all.
        "entities": {"vacuum": _VAC},
        "model_family": "x10",
        "capability_hints": {"has_attribute_rooms": True, "supports_mop_wash": True},
        # The curated capabilities subset deliberately lacks model_family /
        # has_attribute_rooms — proving the fix reads capability_hints, not this.
        "capabilities": {"supports_path_control": True},
    })
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 1, "name": "Kitchen"}]})

    caps = manager.refresh_vacuum_capabilities(
        vacuum_entity_id=_VAC, detected_model="T2351")

    assert caps["detected_model"] == "T2351"
    assert caps["model_family"] == "x10"          # preserved, NOT reverted to "generic"
    assert caps["supports_rooms"] is True          # via the has_attribute_rooms hint
    assert caps["supports_segments"] is True
    assert caps["supports_active_map"] is False    # no active_map entity to dereference
    assert caps["supports_mop_wash"] is True       # stored hint honored on refresh


def test_get_vacuum_capabilities_self_heals_stale_model_family(hass, manager):
    """[CAP-11] A persisted snapshot with a stale model_family ("generic") is
    re-detected when the freshly-registered adapter now declares a better family
    ("x10") — so a detection fix lands on existing installs without a manual
    refresh, even with refresh=False. Idempotent: once healed, stored matches the
    adapter family so it does not re-detect again. (This is what made the live X10
    keep reading "generic" until the adapter began publishing model_family.)"""
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "entities": {"active_map": "sensor.alfred_map"},
        "model_family": "x10",
        "capability_hints": {"supports_mop_wash": True},
        "capabilities": {},
    })
    hass.states.async_set("sensor.alfred_map", "6")
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 1, "name": "Kitchen"}]})
    # Stale persisted snapshot (pre-fix): detected_model set, model_family generic.
    manager.data.setdefault("capabilities", {})[_VAC] = {
        "detected_model": "T2351", "model_family": "generic", "supports_rooms": True,
    }

    out = manager.get_vacuum_capabilities(vacuum_entity_id=_VAC, refresh=False)
    assert out["model_family"] == "x10"            # self-healed
    assert out["supports_mop_wash"] is True        # via the stored hint

    # The refresh wrote the adapter family back, so the mismatch is gone.
    assert manager.data["capabilities"][_VAC]["model_family"] == "x10"
