"""Phase 8 integration tests — switch entity (EufyVacuumRoomEnabledSwitch).

Coverage targets
----------------
[SW-1]  is_on=False when room data has enabled=False.
[SW-2]  is_on=True when room data has enabled=True.
[SW-3]  available=True when room exists in manager.data; False when absent.
[SW-4]  unique_id encodes vacuum, map, room_id, and 'enabled' suffix.
[SW-5]  async_turn_on writes enabled=True to manager.data.
[SW-6]  async_turn_off writes enabled=False to manager.data.

The Override Order switch (`EufyVacuumCleanOrderOverrideSwitch`) — `SWO-*`, added
2026-11-08. It had NO test anywhere in the suite, and its creation gate never fired,
which is what made `switch.py` the joint-lowest file in the package at 83.74%.

[SWO-1]  the switch exists only where the adapter+model declares the WRITE half.
[SWO-2]  a manager with no `clean_order` subsystem grows no switch — and does not
         take the whole switch platform down with it.
[SWO-3]  the card can find this entity by `role` WITHOUT its entity_id, which is not
         guaranteed; `vacuum_entity_id` alone cannot identify it.
[SWO-4]  `is_on` reads the manager, both ways.
[SWO-4b] ...and fails CLOSED when the subsystem disappears under a live entity.
[SWO-5]  toggling stores intent and reaches NO device — toggling off especially must
         not clear a sequence the user set in their own vendor app.
"""

from __future__ import annotations

import pytest

from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eufy_vacuum import switch as switch_mod
from custom_components.eufy_vacuum.const import DOMAIN
from custom_components.eufy_vacuum.switch import (
    EufyVacuumCleanOrderOverrideSwitch,
    EufyVacuumRoomEnabledSwitch,
)

from tests._factories import VAC as _VAC, MAP as _MAP, ENTRY_ID as _ENTRY_ID
from tests._factories import get_room_data, set_room_field
from .conftest import setup_map

#: A second vacuum, so [SWO-1]'s gate has something to NOT create a switch for.
_OTHER_VAC = "vacuum.ivy"


def _make_switch(manager, room_id: int = 1) -> EufyVacuumRoomEnabledSwitch:
    """Build a switch entity for the given room and wire hass."""
    return EufyVacuumRoomEnabledSwitch(
        coordinator_key=_ENTRY_ID,
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        room_id=room_id,
        room_data=get_room_data(manager, room_id),
    )


# ---------------------------------------------------------------------------
# [SW-1] / [SW-2] is_on reflects room enabled field
# ---------------------------------------------------------------------------

def test_switch_is_on_false_when_room_disabled(hass, manager):
    """[SW-1] is_on=False when room enabled=False."""
    setup_map(manager, _VAC, _MAP, count=2)
    set_room_field(manager, 1, enabled=False)

    sw = _make_switch(manager, room_id=1)
    sw.hass = hass

    assert sw.is_on is False


def test_switch_is_on_true_when_room_enabled(hass, manager):
    """[SW-2] is_on=True when room enabled=True."""
    setup_map(manager, _VAC, _MAP, count=2)
    set_room_field(manager, 1, enabled=True)

    sw = _make_switch(manager, room_id=1)
    sw.hass = hass

    assert sw.is_on is True


# ---------------------------------------------------------------------------
# [SW-3] available reflects room existence
# ---------------------------------------------------------------------------

def test_switch_available_true_when_room_exists(hass, manager):
    """[SW-3] available=True when room data is present in manager.data."""
    setup_map(manager, _VAC, _MAP, count=1)

    sw = _make_switch(manager, room_id=1)
    sw.hass = hass

    assert sw.available is True


def test_switch_available_false_when_room_absent(hass, manager):
    """[SW-3] available=False when room_id is missing from manager.data."""
    setup_map(manager, _VAC, _MAP, count=1)

    sw = _make_switch(manager, room_id=99)  # room 99 not in data
    sw.hass = hass

    assert sw.available is False


# ---------------------------------------------------------------------------
# [SW-4] unique_id format
# ---------------------------------------------------------------------------

def test_switch_unique_id_encodes_vacuum_map_room_suffix(hass, manager):
    """[SW-4] unique_id includes vacuum key, map_id, room_id, and 'enabled' suffix."""
    setup_map(manager, _VAC, _MAP, count=1)

    sw = _make_switch(manager, room_id=1)
    uid = sw.unique_id

    # Expected: vacuum_alfred_1_1_enabled
    assert "alfred" in uid
    assert _MAP in uid
    assert "1" in uid
    assert uid.endswith("enabled")


# ---------------------------------------------------------------------------
# [SW-5] / [SW-6] async_turn_on / async_turn_off write to manager.data
# ---------------------------------------------------------------------------

async def test_async_turn_on_writes_enabled_true(hass, manager):
    """[SW-5] async_turn_on sets enabled=True in manager.data for the room."""
    setup_map(manager, _VAC, _MAP, count=1)
    set_room_field(manager, 1, enabled=False)

    sw = _make_switch(manager, room_id=1)
    sw.hass = hass

    with patch.object(sw, "async_write_ha_state"):
        await sw.async_turn_on()

    room = manager.data["maps"][_VAC][_MAP]["rooms"]["1"]
    assert room["enabled"] is True


async def test_async_turn_off_writes_enabled_false(hass, manager):
    """[SW-6] async_turn_off sets enabled=False in manager.data for the room."""
    setup_map(manager, _VAC, _MAP, count=1)
    set_room_field(manager, 1, enabled=True)

    sw = _make_switch(manager, room_id=1)
    sw.hass = hass

    with patch.object(sw, "async_write_ha_state"):
        await sw.async_turn_off()

    room = manager.data["maps"][_VAC][_MAP]["rooms"]["1"]
    assert room["enabled"] is False


# ---------------------------------------------------------------------------
# [SWO-1] - [SWO-6]  the Override Order switch, which had NO test at all.
#
# `switch.py` was the joint-lowest file in the package at 83.74%, and the gap was one
# thing: `EufyVacuumCleanOrderOverrideSwitch` is named NOWHERE in the suite, and its
# creation gate never fired, so the class and both arms that build it were dead to the
# tests. That matters more than the percentage, because this switch is the consent
# surface for an action its own docstring flags twice: pressing Apply EDITS A
# PERSISTENT, MAP-LEVEL SETTING IN THE USER'S VENDOR APP, and toggling OFF must not
# silently clear it, "because that would destroy a sequence the USER set in their app".
#
# ⚠ `SW-*` IS THE ROOM SWITCH'S NAMESPACE (SW-1..SW-6 above). These are `SWO-*` so the
# two cannot be confused — check both before minting another id in this file.
# ---------------------------------------------------------------------------


class _FakeCleanOrder:
    """A clean_order stand-in that RECORDS rather than raising.

    Recording, not raising, because the switch's turn_on/turn_off are `@callback`-free
    coroutines awaited by HA: a raising stub would be reported against whatever awaited
    it, and `[SWO-5]`'s whole claim is about which calls DID and did NOT happen. A stub
    that explodes cannot answer that.
    """

    def __init__(self, writable=(), enabled=()):
        self._writable = set(writable)
        self._enabled = set(enabled)
        self.calls: list[tuple] = []

    def can_write(self, vacuum_entity_id):
        self.calls.append(("can_write", vacuum_entity_id))
        return vacuum_entity_id in self._writable

    def override_enabled(self, vacuum_entity_id):
        self.calls.append(("override_enabled", vacuum_entity_id))
        return vacuum_entity_id in self._enabled

    async def set_override_enabled(self, vacuum_entity_id, on):
        self.calls.append(("set_override_enabled", vacuum_entity_id, on))
        self._enabled = (self._enabled | {vacuum_entity_id}) if on else (
            self._enabled - {vacuum_entity_id})

    # The device-facing half, which this switch must NEVER reach. Present so that a
    # call would be RECORDED and nameable, rather than an AttributeError whose
    # traceback has to be read to find out what happened.
    async def async_apply(self, *a, **k):
        self.calls.append(("async_apply", a, k))

    async def async_clear(self, *a, **k):
        self.calls.append(("async_clear", a, k))

    def write(self, *a, **k):
        self.calls.append(("write", a, k))


async def _setup_switches(hass, manager, clean_order):
    """Run the real platform setup and return (entities, clean_order)."""
    manager.clean_order = clean_order
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    captured: list = []
    await switch_mod.async_setup_entry(
        hass, entry, lambda entities, *a, **k: captured.extend(entities)
    )
    return captured


def _overrides(entities):
    return [e for e in entities if isinstance(e, EufyVacuumCleanOrderOverrideSwitch)]


def _attrs(entity):
    """Read an entity's attributes WITHOUT swallowing a raising property.

    ⚠ `getattr(entity, "extra_state_attributes", None) or {}` is the obvious spelling
    and it LIES. `getattr` with a default swallows an AttributeError raised from INSIDE
    the property, and `EufyVacuumRoomEntity.manager` is `self.hass.data[DOMAIN]
    ["runtime"]` — so every room switch whose `.hass` is unset raises, gets silently
    dropped, and the filter reports that only the override switch carries
    `vacuum_entity_id`. A first draft of [SWO-3] concluded exactly that and its
    precondition caught it; the room entities do carry the attribute
    (`room_entities.py::EufyVacuumRoomEntity.extra_state_attributes`).

    So: no default, and no `or {}` around the call. The base `SwitchEntity` genuinely
    returns None, which is normalised AFTER the read, not instead of it.
    """
    attrs = entity.extra_state_attributes   # may raise -- that must be visible
    return attrs or {}


async def test_swo1_the_switch_exists_only_where_the_write_is_declared(hass, manager):
    """[SWO-1] The creation gate, which had never fired either way.

    `can_write` is MODEL-gated, not brand-gated: `set_clean_sequence` is the V1 device
    protocol, and newer Qrevo/B01 models answer a different transport entirely.
    Declaring the write for every Roborock would ship a control that silently does
    nothing on those — so a vacuum whose adapter does not declare the write half must
    gain NO entity, rather than one that turns on and achieves nothing.

    TWO VACUUMS, ONE WRITABLE, and that is what makes this falsifiable: asserting "a
    switch was created" with one writable vacuum passes against a gate that was
    deleted. The count AND the owner are both asserted, because a gate that creates
    one switch for the WRONG vacuum would satisfy a bare count.

    RED: drop the `can_write` gate and two switches appear.
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    manager.ensure_vacuum_record(vacuum_entity_id=_OTHER_VAC)

    entities = await _setup_switches(
        hass, manager, _FakeCleanOrder(writable=[_VAC])
    )
    overrides = _overrides(entities)

    assert len(overrides) == 1, (
        f"expected exactly one Override Order switch, for {_VAC} alone -- got "
        f"{[e.unique_id for e in overrides]}"
    )
    overrides[0].hass = hass
    assert _attrs(overrides[0])["vacuum_entity_id"] == _VAC
    assert overrides[0].unique_id == "vacuum_alfred_clean_order_override"


async def test_swo2_a_manager_without_clean_order_grows_no_switch(hass, manager):
    """[SWO-2] The other arm of the same gate: no `clean_order` on the manager at all.

    This is not a contrived state — `clean_order` is an optional subsystem reached
    through `getattr(manager, "clean_order", None)`, and the guard exists so platform
    setup cannot die on a manager that lacks it. Dying here would take the WHOLE switch
    platform down, including every per-room switch, not just this one entity.

    The room switches are asserted present for that reason: "no override switch" is
    also what a setup that crashed before adding anything produces.

    RED: drop the `is not None` guard and setup raises AttributeError on `.can_write`.
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2)

    entities = await _setup_switches(hass, manager, None)

    assert _overrides(entities) == []
    assert [e for e in entities if isinstance(e, EufyVacuumRoomEnabledSwitch)], (
        "the room switches are missing too, so setup did not merely skip the "
        "override switch -- it failed before adding anything"
    )


async def test_swo3_the_card_can_find_this_entity_without_its_id(hass, manager):
    """[SWO-3] `role` is the discriminator, and the measured reason it has to be.

    The entity_id is NOT guaranteed. With `_attr_has_entity_name` plus a
    `translation_key`, HA composes the id from the device name and the entity name, and
    the name is not resolvable when the platform ADDS the entity. Observed live
    2026-08-24: the registry recorded `original_name: 'Clean Order Override'` while
    `entity_id` was plain `switch.ivy` — and an entity_id is STICKY once assigned.
    Re-registering produced the same id three times. So the card scans STATES for these
    attributes instead.

    ⚠ `vacuum_entity_id` ALONE CANNOT IDENTIFY IT, which is the whole point of `role`
    and the half a weaker test would miss. Every per-room "selected for cleaning" switch
    carries `vacuum_entity_id` too, so this asserts the ambiguity directly: filtering
    the real platform's output by that attribute yields MORE THAN ONE entity, and
    filtering by `role` yields exactly one. Matching the friendly NAME is not an
    alternative — it is translated, so a Chinese install reads `覆盖清扫顺序` and an
    English match finds nothing.

    RED: drop `"role"` from the attributes and the role filter finds zero.
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=3)

    entities = await _setup_switches(hass, manager, _FakeCleanOrder(writable=[_VAC]))
    # Wire hass before reading attributes: the room entities resolve their manager
    # through `self.hass`, so an unwired entity raises rather than answering. See
    # `_attrs` for why that must not be swallowed.
    for entity in entities:
        entity.hass = hass

    with_vac = [e for e in entities if _attrs(e).get("vacuum_entity_id") == _VAC]
    assert len(with_vac) > 1, (
        "precondition: other switches must also carry vacuum_entity_id, or this test "
        f"is not measuring why `role` exists -- found {len(with_vac)}"
    )

    by_role = [e for e in entities if _attrs(e).get("role") == "clean_order_override"]
    assert len(by_role) == 1, (
        f"the card's role scan found {len(by_role)} entities, not 1 -- it cannot "
        f"locate this switch without relying on an entity_id nobody guarantees"
    )
    assert isinstance(by_role[0], EufyVacuumCleanOrderOverrideSwitch)


@pytest.mark.parametrize("enabled,expected", [
    pytest.param([], False, id="off"),
    pytest.param(["vacuum.alfred"], True, id="on"),
])
async def test_swo4_is_on_reads_the_manager(hass, manager, enabled, expected):
    """[SWO-4] The state read, both ways — plus the fail-closed arm below it."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    entities = await _setup_switches(
        hass, manager, _FakeCleanOrder(writable=[_VAC], enabled=enabled)
    )
    assert _overrides(entities)[0].is_on is expected


async def test_swo4b_is_on_fails_closed_when_clean_order_disappears(hass, manager):
    """[SWO-4b] The subsystem can go away under a live entity, and `is_on` must say OFF.

    `is_on` re-reads `getattr(self._manager, "clean_order", None)` on every call rather
    than trusting the one captured at construction, because a config-entry reload
    rebuilds the manager's subsystems while the entity object survives. Returning False
    is the fail-closed answer: an override reported ON with no subsystem behind it
    invites Apply, which is the call that edits the user's vendor app.

    RED: delete the `if clean_order is None: return False` guard and this raises
    AttributeError out of a property HA calls on every state write.
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    entities = await _setup_switches(
        hass, manager, _FakeCleanOrder(writable=[_VAC], enabled=[_VAC])
    )
    sw = _overrides(entities)[0]
    assert sw.is_on is True, "precondition: it must start ON, or False proves nothing"

    manager.clean_order = None
    assert sw.is_on is False


async def test_swo5_toggling_stores_intent_and_touches_no_device(hass, manager):
    """[SWO-5] THE SAFETY CLAIM, and the reason this file needed tests at all.

    Toggling is STORAGE-ONLY. Apply and Clear are separate services, and the UI design
    is explicit that toggling off must NOT clear the device: "Clear is EXPLICIT, never
    implicit on toggle-off. Toggling off must not silently write [] — that would destroy
    a sequence the USER set in their app."

    So the assertions are in two halves, and the second is the load-bearing one:
    `set_override_enabled` is called with the right vacuum and the right flag, AND no
    device-facing call is recorded at all. The stub carries `async_apply`, `async_clear`
    and `write` precisely so such a call would be RECORDED and nameable instead of
    raising an AttributeError somebody has to read a traceback to understand.

    RED: have `async_turn_off` clear the device (the plausible "tidy-up" — making
    toggle-off symmetrical with Apply) and the device-call assertion fires while every
    state assertion stays green.
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    co = _FakeCleanOrder(writable=[_VAC])
    sw = _overrides(await _setup_switches(hass, manager, co))[0]
    sw.hass = hass

    with patch.object(type(sw), "async_write_ha_state"):
        await sw.async_turn_on()
        await sw.async_turn_off()

    writes = [c for c in co.calls if c[0] == "set_override_enabled"]
    assert writes == [
        ("set_override_enabled", _VAC, True),
        ("set_override_enabled", _VAC, False),
    ], f"intent was not persisted as declared: {writes}"

    device_calls = [c for c in co.calls
                    if c[0] in ("async_apply", "async_clear", "write")]
    assert device_calls == [], (
        "toggling the switch reached the DEVICE. Toggling off especially must not "
        f"clear a sequence the user set in their own app: {device_calls}"
    )


async def test_swo6_the_stale_sweep_removes_every_stale_switch_not_just_the_first(
    hass, manager, caplog
):
    """[SWO-6] The stale-removal loop sweeps EVERY stale switch, not just the first.

    `_on_rooms_updated` removes switches for rooms that no longer exist: it pops the
    entity, asks it to remove itself, then clears the registry entry. A room list that
    shrinks by two must lose two switches.

    TWO STALE ROOMS, SO POSITION PROVES THE LOOP CONTINUED. With one, a `break` written
    where the loop should carry on is indistinguishable from correct behaviour; the
    second removal is the evidence. Same reasoning as [RD-20] and [PC-4].

    THE MANAGER SWALLOWS THIS CALLBACK'S EXCEPTIONS, which is why the log is asserted
    as well as the removals. `core/manager.py::_notify_rooms_updated` wraps each
    callback in a blanket `except` that logs "Room update callback failed" and moves on
    -- so anything that starts raising in here produces NO failure by itself. Measured,
    not assumed: a first draft of this test passed while the callback died on every
    run, twice, on two different unwired attributes.

    ⚠ THIS DOES NOT COVER THE `if entity_id:` ARM, and that arm is SUBSUMED -- red set
    deliberately EMPTY. `er.EntityRegistry.async_remove` opens with `if entity_id not
    in self.entities: return`, carrying its own comment that attempts to remove a
    non-existent entity are ALLOWED because "there will be races during cleanup".
    Measured: `async_remove(None)` raises nothing and leaves the registry size
    unchanged, so no input distinguishes `switch.py` with that guard from without it.
    Ablating it reddens nothing, which is how this was found.

    RED: stop the loop after the first stale id (`for uid in stale_ids[:1]:`) and only
    one removal is recorded.
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=3)

    entities = await _setup_switches(hass, manager, _FakeCleanOrder())
    rooms = [e for e in entities if isinstance(e, EufyVacuumRoomEnabledSwitch)]
    assert len(rooms) == 3, f"precondition: three room switches, got {len(rooms)}"
    for entity in entities:
        entity.hass = hass

    removed: list[str] = []

    async def _record_remove(self, *a, **k):
        removed.append(self.unique_id)

    bucket = manager.data["maps"][_VAC][_MAP]["rooms"]
    for key in [k for k in list(bucket) if str(k) in ("2", "3")]:
        bucket.pop(key)
    assert len(bucket) == 1, f"precondition: one room left, got {sorted(bucket)}"

    caplog.clear()
    # `async_write_ha_state` is patched as well, for the SURVIVING room: the callback
    # re-writes the state of every entity it keeps, and that needs a real entity
    # platform these hand-collected entities never got. Leaving it unpatched makes the
    # callback die there instead of at the arm under test -- which is how the swallowed
    # failure above was found, and the reason the log assertion is in this test at all.
    with patch.object(EufyVacuumRoomEnabledSwitch, "async_remove", _record_remove), \
            patch.object(EufyVacuumRoomEnabledSwitch, "async_write_ha_state"):
        manager._notify_rooms_updated(vacuum_entity_id=_VAC, map_id=_MAP)
        await hass.async_block_till_done()

    failures = [r.getMessage() for r in caplog.records
                if r.levelname == "ERROR" and "callback failed" in r.getMessage()]
    assert failures == [], (
        f"the room-update callback raised and the manager swallowed it: {failures}"
    )
    assert len(removed) == 2, (
        f"both stale switches must be swept -- the second is what proves the loop "
        f"continued past the registry miss. Removed: {removed}"
    )


# ---------------------------------------------------------------------------
# NOT TESTED -- `switch.py::async_setup_entry._on_rooms_updated`'s
# `if stale is not None:` arm (the false half).
#
# NOT TESTED -- the same callback's `if entity_id:` arm (the false half).
#
# SUBSUMED, red set deliberately EMPTY. `er.EntityRegistry.async_remove` begins
# `if entity_id not in self.entities: return`, with its own comment that removing a
# non-existent entity is ALLOWED because "there will be races during cleanup".
# Measured in the test image: `async_remove(None)` raises nothing and the registry
# size does not move, so nothing distinguishes this module with the guard from
# without it. Ablation confirms: deleting it reddens no test. Kept because it states
# the intent locally and costs nothing, but it is not a coverage gap.
#
# UNREACHABLE. `stale = entity_map.pop(uid, None)` is called with a `uid` taken from
# `list(entity_map.items())` two statements earlier, in the same synchronous callback,
# so the pop cannot miss. The `None` default exists to make that safe rather than to
# describe a state the code can be in; reaching it would need another coroutine to
# mutate `entity_map` between the comprehension and the loop, and the callback is
# `@callback`-synchronous throughout. Recorded rather than pragma'd, because an
# unreachable guard with no written reason is the one that gets "simplified" later --
# and because the programme admits `pragma: no cover` for logger lines only.
# ---------------------------------------------------------------------------
