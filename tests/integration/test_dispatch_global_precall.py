"""Tests for the global fan/mop pre-call (Wave 2b follow-up).

Roborock exposes fan + water only as GLOBAL device settings (app_segment_clean
carries passes only), so before dispatch the framework pushes one fan + one mop
value, max-wins across the selected rooms. Driven entirely by the adapter's
dispatch.global_pre_calls — no brand logic in core.

Coverage targets
----------------
[GPC-1] fan: max-wins over the suction rank; case-insensitive (default "Max").
[GPC-2] water: max-wins -> the mop-intensity select.
[GPC-3] no global_pre_calls declared -> no service calls (Eufy).
[GPC-4] a value absent from the rank is ignored; all-unrankable -> no call.
[GPC-5] all rooms water=off -> mop pushed off (not skipped).
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config


_VAC = "vacuum.ivy"
_MOP = "select.ivy_mop_intensity"

_PRE_CALLS = [
    {
        "field": "fan_speed",
        "rank": ["gentle", "quiet", "balanced", "turbo", "max"],
        "service": {"domain": "vacuum", "service": "set_fan_speed", "value_key": "fan_speed"},
    },
    {
        "field": "water_level",
        "rank": ["off", "low", "medium", "high"],
        "service": {
            "domain": "select", "service": "select_option",
            "value_key": "option", "target_entity_id": _MOP,
        },
    },
]


def _register(hass, *, pre_calls=_PRE_CALLS):
    dispatch = {"template": "roborock_segment_clean", "service_domain": "vacuum",
                "service_name": "send_command", "command": "app_segment_clean"}
    if pre_calls is not None:
        dispatch["global_pre_calls"] = pre_calls
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code", "entities": {}, "dispatch": dispatch,
    })


def _capture(hass):
    """Register stub fan + select services that record their call data."""
    fan: list[dict] = []
    sel: list[dict] = []

    async def _set_fan(call):
        fan.append(dict(call.data))

    async def _select_option(call):
        sel.append(dict(call.data))

    hass.services.async_register("vacuum", "set_fan_speed", _set_fan)
    hass.services.async_register("select", "select_option", _select_option)
    return fan, sel


async def test_fan_and_water_max_wins(hass, manager):
    """[GPC-1] + [GPC-2]"""
    _register(hass)
    fan, sel = _capture(hass)
    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC,
        resolved_rooms=[
            {"fan_speed": "quiet", "water_level": "off"},
            {"fan_speed": "Max", "water_level": "high"},   # capitalized default
            {"fan_speed": "turbo", "water_level": "low"},
        ],
    )
    assert fan == [{"entity_id": _VAC, "fan_speed": "max"}]
    assert sel == [{"entity_id": _MOP, "option": "high"}]


async def test_no_pre_calls_when_absent(hass, manager):
    """[GPC-3]"""
    _register(hass, pre_calls=None)
    fan, sel = _capture(hass)
    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC, resolved_rooms=[{"fan_speed": "max", "water_level": "high"}]
    )
    assert fan == []
    assert sel == []


async def test_unrankable_values_skipped(hass, manager):
    """[GPC-4] Eufy-flavored values not in the Roborock rank are ignored."""
    _register(hass)
    fan, sel = _capture(hass)
    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC,
        resolved_rooms=[{"fan_speed": "Boost", "water_level": "Standard"}],
    )
    assert fan == []   # "boost" not in the fan rank
    assert sel == []   # "standard" not in the water rank


async def test_all_off_pushes_off(hass, manager):
    """[GPC-5] all rooms vacuum-only -> mop explicitly pushed off."""
    _register(hass)
    fan, sel = _capture(hass)
    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC,
        resolved_rooms=[
            {"fan_speed": "balanced", "water_level": "off"},
            {"fan_speed": "balanced", "water_level": "off"},
        ],
    )
    assert fan == [{"entity_id": _VAC, "fan_speed": "balanced"}]
    assert sel == [{"entity_id": _MOP, "option": "off"}]
