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
[GPC-6b] an ALL-VACUUM batch forces water OFF (issue #51) -- the old guard only fired on a
        MIXED batch, so zero mop rooms fell through to max-wins and pushed the room's
        STORED water level, because resolved_rooms keeps it on a dry room.
[GPC-6c] ...same across several dry rooms, one of them asking for HIGH.
[GPC-6d] a safest-water target that does NOT EXIST aborts the dispatch (issue #51) --
        HA warns rather than raises on a missing service target, so the abort could
        never fire and the run silently kept the vendor app's water.
[GPC-6e] `target_role` resolves the entity at CALL time, so a rescued (localized)
        entity receives the push -- pre_calls are built before the rescue runs.
[GPC-7] an ALL-MOP batch keeps max-wins even with the safest marker (single-mode).
[GPC-8] the safest marker does NOT touch a fan_speed entry (suction stays max-wins).
[GPC-9] chosen "off" but the target select has no "off" option -> lower to the select's
        minimum available option (never leave a prior HIGH value).
[GPC-10] a vacuum-only room with NO water_level field still forces the safe 'off' — the
        presence of a dry room is the signal, not the min of DECLARED levels.
[GPC-11] DQ-ACT-6: pre-calls run AFTER payload resolution, so a start that aborts
        there leaves the robot's global settings untouched.
"""

from __future__ import annotations

import pytest

from homeassistant.exceptions import HomeAssistantError

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


def _capture(hass, *, targets_exist=True):
    """Register stub fan + select services that record their call data.

    ``targets_exist`` also puts the TARGET ENTITIES in the state machine, which is
    what production looks like and what these tests previously omitted. It matters
    because a pre-call now refuses when its target does not exist: HA does not raise
    on a service call naming a missing entity, it logs a warning, so the old
    behaviour was a silent no-op that the safety abort could never catch (issue #51).
    Pass False to model exactly that install.
    """
    if targets_exist:
        hass.states.async_set(_VAC, "docked")
        hass.states.async_set(_MOP, "off", {"options": ["off", "low", "medium", "high"]})

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


async def test_all_vacuum_batch_forces_water_off(hass, manager):
    """[GPC-6b] issue #51: an ALL-VACUUM batch must push water OFF, not the room's
    stored level.

    The mixed-batch guard read `0 < mop_rooms < len(rooms)`, so a batch with NO mop
    rooms — the plainest "vacuum only" request there is — was not "mixed" and fell
    through to max-wins. Max-wins then FINDS a level, because `resolved_rooms` is the
    framework's internal record and keeps `water_level` on a dry room; only the wire
    payload drops it. So a single vacuum-only room pushed its stored water to the
    device-global mop select and the robot mopped.

    Reported on a Qrevo Curv: "I set up one room for vacuum only ... and it ran it as
    normal with mopping." His run was exactly this shape — Scope: Single Room, one
    room, vacuum profile.
    """
    _register(hass, pre_calls=_SAFEST_WATER)
    _fan, sel = _capture(hass)
    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC,
        resolved_rooms=[{"clean_mode": "vacuum", "water_level": "medium"}],
    )
    assert sel == [{"entity_id": _MOP, "option": "off"}]


async def test_all_vacuum_multi_room_forces_water_off(hass, manager):
    """[GPC-6c] the same for several dry rooms, including one asking for HIGH water.

    A stored water level on a room the user set to vacuum-only is stale intent, not a
    request. Max-wins would have picked 'high' here and wet-mopped every dry room.
    """
    _register(hass, pre_calls=_SAFEST_WATER)
    _fan, sel = _capture(hass)
    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC,
        resolved_rooms=[
            {"clean_mode": "vacuum", "water_level": "high"},
            {"clean_mode": "vacuum", "water_level": "low"},
        ],
    )
    assert sel == [{"entity_id": _MOP, "option": "off"}]


async def test_missing_safest_target_aborts_instead_of_silently_no_opping(hass, manager):
    """[GPC-6d] issue #51: a target that does not exist must REFUSE, not warn.

    The abort below this line could never fire. Home Assistant does not raise when a
    service call names a missing entity — it collects the ids and calls log_missing(),
    a WARNING. So on an install whose mop select is `..._wisch_intensitat` while we
    aimed at `..._mop_intensity`, the water push no-opped, `except Exception` never
    ran, the safety abort never happened, and the run proceeded with whatever water
    the vendor app had last set. Silent, and exactly the wet-mop this guard exists to
    prevent.
    """
    _register(hass, pre_calls=_SAFEST_WATER)
    _fan, sel = _capture(hass, targets_exist=False)   # the localized install

    with pytest.raises(HomeAssistantError, match="dispatch aborted"):
        await manager._run_global_pre_calls(
            vacuum_entity_id=_VAC,
            resolved_rooms=[{"clean_mode": "vacuum", "water_level": "off"}],
        )
    assert sel == []


async def test_pre_call_target_resolves_by_role_not_frozen_id(hass, manager):
    """[GPC-6e] a `target_role` reads the RESOLVED entity at call time.

    global_pre_calls are built BEFORE resolve_declared_entities runs, so any id baked
    into them is the pre-rescue guess. Naming the role instead lets the rescued
    entity — here a German one — receive the call.
    """
    _GERMAN = "select.ivy_wisch_intensitat"
    dispatch = {
        "template": "roborock_segment_clean", "service_domain": "vacuum",
        "service_name": "send_command", "command": "app_segment_clean",
        "global_pre_calls": [{
            "field": "water_level",
            "rank": ["off", "low", "medium", "high"],
            "mixed_mode_water_policy": "safest",
            "service": {
                "domain": "select", "service": "select_option",
                "value_key": "option", "target_role": "mop_intensity",
            },
        }],
    }
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        # What the resolver produced: the role bound to the localized entity.
        "entities": {"mop_intensity": _GERMAN},
        "dispatch": dispatch,
    })
    _fan, sel = _capture(hass, targets_exist=False)
    hass.states.async_set(_VAC, "docked")
    hass.states.async_set(_GERMAN, "off", {"options": ["off", "low", "medium", "high"]})

    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC,
        resolved_rooms=[{"clean_mode": "vacuum", "water_level": "off"}],
    )
    assert sel == [{"entity_id": _GERMAN, "option": "off"}]


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


# ---------------------------------------------------------------------------
# [GPC-11] DQ-ACT-6 — ordering: the device is not reconfigured by a start that
# then fails to reach dispatch.
# ---------------------------------------------------------------------------

def test_pre_calls_run_after_payload_resolution():
    """[GPC-11] DQ-ACT-6: a failed start must not leave the robot rewritten.

    The pre-calls push GLOBAL device settings — on Roborock, the mop-intensity
    select. They used to run BEFORE _resolve_live_dispatch_payload, which is a
    real failure path rather than a theoretical one: it raises when the map has
    been re-segmented and the stored slugs no longer resolve
    (dispatch/manager.py, "been re-segmented; re-import rooms"). The start then
    aborted with the robot's global mop intensity already changed and nothing to
    put it back, so the next clean the user ran from the vendor app inherited a
    setting that outlived the job it was made for.

    ORDER is the fix, so order is what this pins — read off the real start path
    rather than from a stub sequence, because a mock-driven ordering test passes
    just as happily when the production order is wrong: the mocks answer in the
    order the test calls them, not the order the code does.
    """
    import inspect

    from custom_components.eufy_vacuum.core.manager import EufyVacuumManager

    src = inspect.getsource(EufyVacuumManager.start_selected_rooms)

    resolve_at = src.index("await self._resolve_live_dispatch_payload(")
    pre_calls_at = src.index("await self._run_global_pre_calls(")
    dispatch_at = src.index("await self._dispatch_clean_payload(")

    assert resolve_at < pre_calls_at, (
        "global pre-calls run before payload resolution — a resolution failure "
        "would abort the start with the device already reconfigured (DQ-ACT-6)"
    )
    assert pre_calls_at < dispatch_at, (
        "pre-calls must still precede dispatch, or the settings they push do not "
        "apply to the job being dispatched"
    )
