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
[GPC-12] the safest-water push RAISING aborts the dispatch -- [GPC-6d] covers the
        target that does not EXIST, which HA answers with a warning; this covers the
        service that exists and FAILS, which is the only way the `except` is reached.
[GPC-13] a non-safest pre-call that raises degrades quietly and the loop continues,
        so one brand's broken select cannot abort a run it was never protecting.
[GPC-14] a missing target WITHOUT the safest marker warns and continues -- the
        best-effort half of the [GPC-6d] refusal.

Idempotence (issues #78/#79) -- this entry runs once at job start AND once per phase,
so a strict-order run re-sent an identical value at every room start and a robot that
acknowledges the write chimed each time. The evidence for suppressing a re-send is OUR
OWN earlier push, never the reported state: see dispatch/manager.py for why the state
cannot carry that weight on the water entry.
[GPC-15] a mid-job re-send of the SAME value to the SAME target is suppressed (one send
        across two calls).
[GPC-16] a NEW job re-sends it, even though the previous job pushed the same value --
        `reuse_pushed_values` defaults to False, which is the fail-safe polarity.
[GPC-17] a target that has since reported something ELSE vetoes the skip and re-sends,
        so an external change the poll has caught re-arms the push.
[GPC-18] absence is no information: (a) an `unavailable` target does NOT veto our own
        evidence, and (b) a reported value alone, with no push of ours behind it, NEVER
        suppresses the first push. (b) is the wet-mop protection -- it is the whole
        reason this is a provenance check and not a state check.
[GPC-19] DQ-ACT-7: the comparison is case-normalised on BOTH sides, so it is not alive
        on a lowercase-option device and dead on a capitalised one.
[GPC-20] a push that RAISED leaves no evidence, so the next phase pushes again.
[GPC-21] the skip never pre-empts the [GPC-6d]/#51 existence refusal: a recorded push
        plus a target that has since vanished still ABORTS.
[GPC-22] where the value is read from follows the service DOMAIN -- a select's value is
        its state, a vacuum's fan speed is an attribute. Both halves, because reading
        the wrong one is silent.
[GPC-22c] an entry may DECLARE the attribute to read, overriding the domain default.
        Nothing shipped reaches it, so without this test the branch is only present.
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


# ---------------------------------------------------------------------------
# The pre-call FAILURE handler.
#
# [GPC-6d] above pins the target that does not EXIST. That is a different path:
# HA answers a missing target with a warning, never an exception, which is why the
# existence check had to be added ahead of the `try` at all. The `except` block is
# therefore reached only when the service EXISTS and FAILS -- an unregistered
# domain, or a select that rejects the option -- and nothing exercised it.
#
# The split matters because the two halves disagree on purpose: with the safest
# marker a failure ABORTS, without it the failure is swallowed so one brand's broken
# entity cannot kill a run the guard was never protecting.
# ---------------------------------------------------------------------------


def _raise_on_select(hass, exc=RuntimeError("device rejected the option")):
    """Replace the recording select handler with one that fails.

    Registered AFTER `_capture` so the target entities it puts in the state machine
    still exist -- otherwise the existence check refuses first and the `try` is never
    entered, which would make these tests pass for the wrong reason.
    """
    async def _boom(call):
        raise exc

    hass.services.async_register("select", "select_option", _boom)


async def test_safest_water_push_that_raises_aborts_the_dispatch(hass, manager):
    """[GPC-12] the safest push FAILING must abort, not proceed.

    Same consequence as [GPC-6d] and a different cause. If the select is present but
    rejects the write, the device keeps whatever water the vendor app last set, and a
    batch containing a dry room gets wet-mopped by the device-global value. The
    abort is the only thing standing between a failed write and a wet floor.
    """
    _register(hass, pre_calls=_SAFEST_WATER)
    _fan, sel = _capture(hass)          # targets EXIST, so the existence check passes
    _raise_on_select(hass)

    with pytest.raises(HomeAssistantError, match="dispatch aborted"):
        await manager._run_global_pre_calls(
            vacuum_entity_id=_VAC,
            # one vacuum-only room -> _any_dry_room, which is what arms _use_safest.
            # Without a dry room the marker alone does nothing and this would pass
            # while testing the best-effort path instead.
            resolved_rooms=[{"clean_mode": "vacuum", "water_level": "off"}],
        )
    assert sel == []


async def test_best_effort_pre_call_that_raises_does_not_abort(hass, manager):
    """[GPC-13] without the safest marker, a failing pre-call is swallowed."""
    _register(hass)                     # _PRE_CALLS: no mixed_mode_water_policy
    fan, sel = _capture(hass)
    _raise_on_select(hass)

    # Must NOT raise.
    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC,
        # `fan_speed` is load-bearing: without it the fan entry is UNRANKABLE and
        # skipped ([GPC-4]), so `fan` would be empty whether or not the loop survived
        # the failure -- the assertion below would pass for the wrong reason.
        resolved_rooms=[{"clean_mode": "vacuum_mop", "water_level": "high",
                         "fan_speed": "max"}],
    )

    # The fan entry precedes the water entry, so a non-empty `fan` proves the loop
    # reached the failing entry and carried on rather than unwinding.
    assert fan == [{"entity_id": _VAC, "fan_speed": "max"}]
    assert sel == []


async def test_missing_target_without_safest_marker_degrades_quietly(hass, manager):
    """[GPC-14] the best-effort half of [GPC-6d]: warn and continue, never refuse.

    Both targets are absent here -- the water entry names the mop select, and the fan
    entry names no target at all so it falls back to the vacuum entity, which
    `targets_exist=False` also withholds. Neither may raise.
    """
    _register(hass)                     # no safest marker
    fan, sel = _capture(hass, targets_exist=False)

    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC,
        # BOTH fields present on purpose. Omitting `fan_speed` leaves the fan entry
        # unrankable and skipped ([GPC-4]), so `fan == []` would hold without the
        # existence check ever refusing anything -- the assertion would be vacuous.
        # With it, an empty `fan` means the entry was BUILT and then refused.
        resolved_rooms=[{"clean_mode": "vacuum_mop", "water_level": "high",
                         "fan_speed": "max"}],
    )

    assert fan == []
    assert sel == []


async def test_gpc6f_a_disabled_target_says_so_instead_of_does_not_exist(hass, manager):
    """[GPC-6f] "does not exist" is useless to the person who switched it off.

    A disabled entity has no state, so it lands in the same missing-target branch as one
    that was never created — and the two need different advice. The message the user got
    on ISSUE #67 said the entity did not exist while it sat in their entity list,
    disabled, exactly where it had been put. They spent an upgrade cycle on it.

    The refusal itself is unchanged and must stay: a disabled control on a device that
    can mop still cannot receive the call, so proceeding would wet-mop dry rooms
    ([MS-8]). Only the sentence changes.

    ABLATION: drop the `disabled_by` lookup and this goes red on the wording while
    [GPC-6d] stays green — the abort is the same, the explanation is not.
    """
    from homeassistant.helpers import entity_registry as er

    _register(hass, pre_calls=_SAFEST_WATER)
    _fan, sel = _capture(hass, targets_exist=False)
    # Registered and switched off: no state, so the branch above is reached either way.
    er.async_get(hass).async_get_or_create(
        "select", "roborock", "uid_mop_intensity",
        suggested_object_id=_MOP.split(".", 1)[1],
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    assert hass.states.get(_MOP) is None, "a disabled entity has no state"

    with pytest.raises(HomeAssistantError) as err:
        await manager._run_global_pre_calls(
            vacuum_entity_id=_VAC,
            resolved_rooms=[{"clean_mode": "vacuum", "water_level": "off"}],
        )

    msg = str(err.value)
    assert "DISABLED" in msg, f"the refusal must name the actual cause — got: {msg!r}"
    assert "does not exist" not in msg, (
        "telling someone an entity they can see in their own entity list does not "
        "exist is what sent #67 looking in the wrong place"
    )
    assert "Re-enable it" in msg, "say what to do about it"
    assert sel == [], "the refusal still refuses"


# ---------------------------------------------------------------------------
# Idempotence (issues #78/#79). A user on an S6 MaxV heard a chime at every room
# start of a strict-order run: this entry fires at job start AND once per phase,
# and re-sent an identical value each time.
#
# Every test below asserts across TWO calls, because one call can never show the
# defect -- which is why the 18 tests above all stayed green when the skip landed.
# ---------------------------------------------------------------------------


async def test_mid_job_resend_of_the_same_value_is_suppressed(hass, manager):
    """[GPC-15] the chime. One send across two calls in the same job.

    ABLATION: delete the `_pushed_pre_call_values.get(...)` skip in
    dispatch/manager.py and this goes red with two identical sends -- which is the
    behaviour the reporter heard.
    """
    _register(hass, pre_calls=_SAFEST_WATER)
    _fan, sel = _capture(hass)
    rooms = [{"clean_mode": "vacuum", "water_level": "off"}]

    await manager._run_global_pre_calls(vacuum_entity_id=_VAC, resolved_rooms=rooms)
    assert sel == [{"entity_id": _MOP, "option": "off"}], "job start always pushes"

    # The phase runner's call: same job, same value, same target.
    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC, resolved_rooms=rooms, reuse_pushed_values=True,
    )
    assert len(sel) == 1, f"the re-send should have been suppressed, got {sel!r}"


async def test_a_new_job_re_sends_even_a_value_the_last_job_pushed(hass, manager):
    """[GPC-16] `reuse_pushed_values=False` is the fail-safe default.

    A new job knows nothing about what the device holds: the vendor app may have
    moved the select since the last run ended. So the first push of every job goes
    out unconditionally, and a caller that forgets the flag gets that behaviour
    rather than inheriting a stale permission to skip.

    ABLATION: make the reset unconditional on `reuse_pushed_values` (or drop the
    per-vacuum clear) and this goes red with one send.
    """
    _register(hass, pre_calls=_SAFEST_WATER)
    _fan, sel = _capture(hass)
    rooms = [{"clean_mode": "vacuum", "water_level": "off"}]

    await manager._run_global_pre_calls(vacuum_entity_id=_VAC, resolved_rooms=rooms)
    # A SECOND JOB -- the default, not reuse_pushed_values=True.
    await manager._run_global_pre_calls(vacuum_entity_id=_VAC, resolved_rooms=rooms)

    assert len(sel) == 2, (
        "a new job must re-assert the safe water; skipping it would trust a reading "
        f"that may be a poll interval out of date. got {sel!r}"
    )


async def test_a_target_reporting_something_else_vetoes_the_skip(hass, manager):
    """[GPC-17] an external change the poll HAS caught re-arms the push.

    This is the half of the design that limits the damage of trusting our own push:
    the record says we set `off`, the select now says `high`, so something moved it
    and the push goes out again.

    ABLATION: drop the `_reported != _wire_norm` clause and this goes red -- the
    mid-run re-assertion of safe water disappears with it.
    """
    _register(hass, pre_calls=_SAFEST_WATER)
    _fan, sel = _capture(hass)
    rooms = [{"clean_mode": "vacuum", "water_level": "off"}]

    await manager._run_global_pre_calls(vacuum_entity_id=_VAC, resolved_rooms=rooms)
    # The vendor app raised it mid-job and the coordinator polled it.
    hass.states.async_set(_MOP, "high", {"options": ["off", "low", "medium", "high"]})

    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC, resolved_rooms=rooms, reuse_pushed_values=True,
    )
    assert len(sel) == 2, f"a disagreeing reading must re-arm the push, got {sel!r}"


async def test_an_unavailable_target_does_not_veto_our_own_evidence(hass, manager):
    """[GPC-18a] absence is no information, so it cannot veto.

    We pushed `off` and the call did not raise, so the device took it. The select
    then going `unavailable` tells us nothing newer -- and re-pushing to an
    unavailable select would RAISE, which on this entry aborts a clean that is
    already running.

    ABLATION: treat a None reading as a disagreement and this goes red.
    """
    _register(hass, pre_calls=_SAFEST_WATER)
    _fan, sel = _capture(hass)
    rooms = [{"clean_mode": "vacuum", "water_level": "off"}]

    await manager._run_global_pre_calls(vacuum_entity_id=_VAC, resolved_rooms=rooms)
    hass.states.async_set(_MOP, "unavailable")

    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC, resolved_rooms=rooms, reuse_pushed_values=True,
    )
    assert len(sel) == 1, f"absence must not re-arm or veto, got {sel!r}"


async def test_a_reported_value_alone_never_suppresses_the_first_push(hass, manager):
    """[GPC-18b] THE WET-MOP PROTECTION. The whole reason this is a provenance check.

    The select already reports `off` and the batch is all-dry, so the value we are
    about to send is the value it claims to hold -- and the push still goes out,
    because that reading can be a poll interval out of date. HA's Roborock
    mop-intensity select registers no push listener, so a vendor-app change does not
    reach it until the next coordinator cycle; `off` is also the modal reading,
    precisely because this code puts it there. Suppressing on that reading alone
    reproduces #51: the run proceeds with whatever water the vendor app last set,
    and the dry rooms get wet-mopped with no warning and no abort.

    ABLATION: add a state-only skip (`if _reported == _wire_norm: continue`) and this
    goes red. That ablation is exactly the fix shape this issue was first written up
    with, which is why the test is here and not in a comment.
    """
    _register(hass, pre_calls=_SAFEST_WATER)
    _fan, sel = _capture(hass)      # seeds the select to "off" -- what we would send
    assert hass.states.get(_MOP).state == "off", "the premise of this test"

    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC,
        resolved_rooms=[{"clean_mode": "vacuum", "water_level": "off"}],
        # Even WITH permission to reuse, there is nothing of ours to reuse.
        reuse_pushed_values=True,
    )
    assert sel == [{"entity_id": _MOP, "option": "off"}], (
        "a value only the state machine claims is not evidence the device holds it"
    )


async def test_the_comparison_is_case_normalised_on_both_sides(hass, manager):
    """[GPC-19] DQ-ACT-7: a bare `==` is dead on a capitalised-option install.

    `rank` is lowercased when it is read, while a select keeps its own option case,
    so the maintainer's lowercase S6 would have shown a working skip while a
    capitalised-option device silently kept chiming.

    ABLATION: drop `.casefold()` from either side and this goes red with two sends.
    """
    _register(hass, pre_calls=_SAFEST_WATER)
    _fan, sel = _capture(hass)
    # A device whose select advertises capitalised options and reports one.
    hass.states.async_set(_MOP, "Off", {"options": ["Off", "Low", "Medium", "High"]})
    rooms = [{"clean_mode": "vacuum", "water_level": "off"}]

    await manager._run_global_pre_calls(vacuum_entity_id=_VAC, resolved_rooms=rooms)
    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC, resolved_rooms=rooms, reuse_pushed_values=True,
    )
    assert len(sel) == 1, (
        f"'Off' and 'off' are the same rung; a case-sensitive read makes the skip "
        f"install-dependent. got {sel!r}"
    )


async def test_a_push_that_raised_leaves_no_evidence(hass, manager):
    """[GPC-20] a failed push must never read as a value the device holds.

    Recorded in the `else` of the try, so only a call that returned without raising
    counts. Were it recorded before or regardless of the outcome, a rejected write
    would suppress every later attempt and leave the device on the vendor app's
    water for the rest of the run.

    ABLATION: move the record above the `await` (or into a `finally`) and this goes
    red with one attempt.
    """
    _register(hass)                  # best-effort: a raise is swallowed, not aborted
    _fan, _sel = _capture(hass)

    attempts: list[dict] = []

    async def _boom_once_then_record(call):
        attempts.append(dict(call.data))
        if len(attempts) == 1:
            raise RuntimeError("device rejected the option")

    hass.services.async_register("select", "select_option", _boom_once_then_record)
    rooms = [{"fan_speed": "balanced", "water_level": "off"}]

    await manager._run_global_pre_calls(vacuum_entity_id=_VAC, resolved_rooms=rooms)
    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC, resolved_rooms=rooms, reuse_pushed_values=True,
    )
    assert len(attempts) == 2, (
        f"the first push raised, so the second must still be attempted. got {attempts!r}"
    )


async def test_the_skip_never_pre_empts_the_missing_target_refusal(hass, manager):
    """[GPC-21] #51's guarantee survives the skip, and ORDERING is what preserves it.

    A recorded push is not a licence to stop checking that the target is still there.
    If the select has vanished since (a re-import, a rename, a disabled entity) the
    safest entry must abort exactly as [GPC-6d] requires -- an unapplied safe-water
    push aborts rather than passing silently.

    ABLATION: move the skip block ABOVE the existence check in dispatch/manager.py
    and this goes red: the recorded value matches, nothing vetoes it (a missing
    entity reads as None), so the dispatch proceeds with no water push and no abort.
    That is #51 re-opened.
    """
    _register(hass, pre_calls=_SAFEST_WATER)
    _fan, sel = _capture(hass)
    rooms = [{"clean_mode": "vacuum", "water_level": "off"}]

    await manager._run_global_pre_calls(vacuum_entity_id=_VAC, resolved_rooms=rooms)
    assert len(sel) == 1
    hass.states.async_remove(_MOP)       # the target is gone

    with pytest.raises(HomeAssistantError, match="dispatch aborted"):
        await manager._run_global_pre_calls(
            vacuum_entity_id=_VAC, resolved_rooms=rooms, reuse_pushed_values=True,
        )
    assert len(sel) == 1, "no further push went out"


async def test_a_selects_value_is_read_from_its_state(hass, manager):
    """[GPC-22a] a select publishes `options` and nothing else; its value IS the state.

    A verbatim copy of the per-room suction skip reads
    `state.attributes.get(value_key)` -- `attributes["option"]` on a select, which
    does not exist. It would read None forever: no veto, no skip ever created, a
    guard that cannot fire and a chime unfixed.

    The select here carries a BOGUS `option` attribute that disagrees with its state,
    so the two read locations give opposite answers and the test can tell them apart.

    ABLATION: read the attribute for every domain and this goes red with two sends.
    """
    _register(hass, pre_calls=_SAFEST_WATER)
    _fan, sel = _capture(hass)
    hass.states.async_set(
        _MOP, "off",
        {"options": ["off", "low", "medium", "high"], "option": "high"},
    )
    rooms = [{"clean_mode": "vacuum", "water_level": "off"}]

    await manager._run_global_pre_calls(vacuum_entity_id=_VAC, resolved_rooms=rooms)
    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC, resolved_rooms=rooms, reuse_pushed_values=True,
    )
    assert len(sel) == 1, (
        f"the state says off and only a non-existent attribute says high. got {sel!r}"
    )


async def test_a_vacuums_fan_speed_is_read_from_its_attribute(hass, manager):
    """[GPC-22b] the other half: a non-select target keeps its value in an attribute.

    Reading the STATE of a vacuum gets `cleaning`/`docked`, never a suction word, so
    getting this backwards is silent -- it never matches, so it never creates a wrong
    skip, it just quietly stops the guard working on that domain. The vacuum here
    reports a state that EQUALS the wire value and an attribute that does not, so the
    two read locations disagree.

    ABLATION: read the state for every domain and this goes red with one send.
    """
    _register(hass, pre_calls=[_PRE_CALLS[0]])      # the fan entry alone
    fan, _sel = _capture(hass)
    hass.states.async_set(_VAC, "max", {"fan_speed": "quiet"})
    rooms = [{"fan_speed": "max"}]

    await manager._run_global_pre_calls(vacuum_entity_id=_VAC, resolved_rooms=rooms)
    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC, resolved_rooms=rooms, reuse_pushed_values=True,
    )
    assert len(fan) == 2, (
        f"the fan_speed attribute says quiet, so the push must go out. Only the "
        f"vacuum's STATE coincidentally reads 'max'. got {fan!r}"
    )


async def test_a_declared_state_attribute_overrides_the_domain_default(hass, manager):
    """[GPC-22c] an entry may name the attribute to read, overriding the domain default.

    Without this the reader has two paths -- state for a select, `value_key` as an
    attribute otherwise -- and a target that keeps its value somewhere else has no way
    to say so. The override existed from the start and NOTHING reached it: no shipped
    adapter declares `state_attribute` on a global pre-call, and the other tests here
    all take one of the two defaults. Coverage found it as one uncovered line, which is
    exactly how a prepared key reads as covered when it is only ever present.

    The vacuum below disagrees with itself ON PURPOSE: `suction` holds the value we
    pushed, `fan_speed` (the `value_key` default) holds something else. Only reading
    the declared attribute can suppress the re-send.

    ABLATION: delete the `if state_attribute:` branch in `_reported_pre_call_value`
    and this goes red with two sends -- the reader falls back to `fan_speed`, sees a
    disagreement, and pushes again.
    """
    entry = {
        "field": "fan_speed",
        "rank": ["gentle", "quiet", "balanced", "turbo", "max"],
        "service": {
            "domain": "vacuum", "service": "set_fan_speed", "value_key": "fan_speed",
            # The declared override: not the state (this is not a select), and not
            # `value_key` either.
            "state_attribute": "suction",
        },
    }
    _register(hass, pre_calls=[entry])
    fan, _sel = _capture(hass)
    hass.states.async_set(_VAC, "docked", {"suction": "max", "fan_speed": "quiet"})
    rooms = [{"fan_speed": "max"}]

    await manager._run_global_pre_calls(vacuum_entity_id=_VAC, resolved_rooms=rooms)
    assert fan == [{"entity_id": _VAC, "fan_speed": "max"}], "job start always pushes"

    await manager._run_global_pre_calls(
        vacuum_entity_id=_VAC, resolved_rooms=rooms, reuse_pushed_values=True,
    )
    assert len(fan) == 1, (
        f"the declared attribute `suction` reports 'max', which is what we pushed, so "
        f"the re-send is redundant. Only `fan_speed` disagrees, and it is not what the "
        f"entry asked us to read. got {fan!r}"
    )
