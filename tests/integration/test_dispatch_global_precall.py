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

Mixed-batch safe water (mixed_mode_water_policy="safest"):
[GPC-6] a MIXED mop + vacuum-only batch picks the SAFEST (lowest) water, not the strongest,
        so a dry room is never wet-mopped by the device-global select.
[GPC-7] an ALL-MOP batch keeps max-wins even with the safest marker (single-mode).
[GPC-8] the safest marker does NOT touch a fan_speed entry (suction stays max-wins).
[GPC-9] chosen "off" but the target select has no "off" option -> lower to the select's
        minimum available option (never leave a prior HIGH value).
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


# ---------------------------------------------------------------------------
# Mixed-batch safe water (defect: a mixed mop + vacuum-only batch on a settable
# device max-wins the GLOBAL water select to the strongest, wet-mopping the dry
# rooms). mixed_mode_water_policy="safest" flips a MIXED batch to the lowest water.
# ---------------------------------------------------------------------------

_SAFEST_WATER = [
    {
        "field": "water_level",
        "rank": ["off", "low", "medium", "high"],
        "mixed_mode_water_policy": "safest",
        "service": {
            "domain": "select", "service": "select_option",
            "value_key": "option", "target_entity_id": _MOP,
        },
    },
]


async def test_mixed_batch_picks_safest_water(hass, manager):
    """[GPC-6] a vacuum-only room (no mop clean_mode) alongside a HIGH-water mop room ->
    the global select is pushed to the SAFEST (off), never high, so the dry room isn't
    wet-mopped. (Max-wins would have pushed 'high' and wet-mopped the vacuum-only room.)"""
    _register(hass, pre_calls=_SAFEST_WATER)
    _fan, sel = _capture(hass)
    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC,
        resolved_rooms=[
            {"clean_mode": "vacuum", "water_level": "off"},          # vacuum-only (dry)
            {"clean_mode": "vacuum_mop", "water_level": "high"},     # mop, high water
        ],
    )
    assert sel == [{"entity_id": _MOP, "option": "off"}]


async def test_all_mop_batch_keeps_max_wins(hass, manager):
    """[GPC-7] a single-mode ALL-MOP batch is NOT mixed, so even with the safest marker it
    keeps max-wins -> the strongest requested water (high)."""
    _register(hass, pre_calls=_SAFEST_WATER)
    _fan, sel = _capture(hass)
    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC,
        resolved_rooms=[
            {"clean_mode": "mop", "water_level": "low"},
            {"clean_mode": "vacuum_mop", "water_level": "high"},
        ],
    )
    assert sel == [{"entity_id": _MOP, "option": "high"}]


async def test_safest_marker_does_not_touch_fan(hass, manager):
    """[GPC-8] the marker rides only the water entry; a fan entry stays max-wins even in a
    mixed batch (suction is safe to run strong on every room)."""
    pre = [_PRE_CALLS[0], _SAFEST_WATER[0]]   # fan (no marker) + water (safest)
    _register(hass, pre_calls=pre)
    fan, sel = _capture(hass)
    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC,
        resolved_rooms=[
            {"clean_mode": "vacuum", "fan_speed": "quiet", "water_level": "off"},
            {"clean_mode": "mop", "fan_speed": "turbo", "water_level": "high"},
        ],
    )
    assert fan == [{"entity_id": _VAC, "fan_speed": "turbo"}]     # fan: still max-wins
    assert sel == [{"entity_id": _MOP, "option": "off"}]          # water: safest (mixed)


async def test_off_fallback_to_min_option_when_no_off(hass, manager):
    """[GPC-9] chosen 'off' but the target select exposes only low/medium/high -> lower to
    the minimum available option (low), never leave a prior (possibly HIGH) value."""
    _register(hass, pre_calls=_SAFEST_WATER)
    _fan, sel = _capture(hass)
    # The select advertises NO "off" option.
    hass.states.async_set(_MOP, "high", {"options": ["low", "medium", "high"]})
    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC,
        resolved_rooms=[
            {"clean_mode": "vacuum", "water_level": "off"},
            {"clean_mode": "mop", "water_level": "high"},
        ],
    )
    # Mixed -> safest is "off", but the select has no "off" -> the minimum it DOES have (low).
    assert sel == [{"entity_id": _MOP, "option": "low"}]


async def test_mixed_batch_vacuum_room_without_water_level(hass, manager):
    """[GPC-10] a vacuum-only room that carries NO water_level field still forces the safe
    'off' — the presence of a dry room is the signal, not the min of DECLARED levels (which
    would leave the mop room's 'high' as the only rankable value and wet-mop the dry room)."""
    _register(hass, pre_calls=_SAFEST_WATER)
    _fan, sel = _capture(hass)
    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC,
        resolved_rooms=[
            {"clean_mode": "vacuum"},                                 # dry, no water_level key
            {"clean_mode": "vacuum_mop", "water_level": "high"},      # mop, high water
        ],
    )
    assert sel == [{"entity_id": _MOP, "option": "off"}]
