"""Phase 10 integration tests — button entity platform.

Coverage targets
----------------
[BE-1]  EufyVacuumMaintenanceResetButton.unique_id encodes vacuum, component, and suffix.
[BE-2]  EufyVacuumMaintenanceResetButton.icon set from constructor.
[BE-3]  EufyVacuumMaintenanceResetButton.async_press calls manager.reset_maintenance + async_save.
[BE-4]  EufyVacuumSavedRunProfileButton.unique_id uses prefix + profile_id.
[BE-5]  EufyVacuumSavedRunProfileButton resolves its name through the
        translation mechanism (EP-5), not a hardcoded English f-string.
[BE-6]  EufyVacuumSavedRunProfileButton.available True when expose_as_button=True.
[BE-7]  EufyVacuumSavedRunProfileButton.available False when expose_as_button=False or missing.
[BE-8]  EufyVacuumSavedRunProfileButton.extra_state_attributes includes vacuum_entity_id and map_id.
[BE-9]  EufyVacuumSavedRunProfileButton.async_press AWAITS manager.start_run_profile (#42) + async_save.
[BE-11] async_setup_entry wires the update callback; exposing a profile adds its run button.
[BE-12] A profile exposed before setup is built into the initial entities.
[BE-13] Un-exposing a profile reconciles away its stale button (async_remove + registry un-register).
[BE-14] RENAMING a profile swaps the entity OBJECT, keeping the unique_id and
        any user name override -- the forgotten sibling of [INIT-13]'s sensor swap.
[BE-15] The swapped-in object is ADOPTED, so a second notification does not re-swap.
[BE-16] A notification with no rename writes state on the existing buttons -- ALL
        of them, which is what distinguishes `continue` from `break`.
[BE-17] THE MODEL GATE's UNRESOLVED arm at this platform's call site: with no model
        code, a guide-only component is dropped and a sensor-backed one survives.
[BE-18] THE MODEL GATE's RESOLVED arm, which is the half that proves the regime
        TABLE is read at all: a SENSOR-BACKED component the regime omits is dropped.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest

from homeassistant.helpers import device_registry as dr, entity_registry as er

import custom_components.eufy_vacuum.button as button_mod
from custom_components.eufy_vacuum.button import (
    EufyVacuumMaintenanceResetButton,
    EufyVacuumSavedRunProfileButton,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eufy_vacuum.adapters.registry import (
    register_adapter_config,
)
from custom_components.eufy_vacuum.const import DOMAIN

from tests._factories import VAC as _VAC, MAP as _MAP, make_manager_mock
from .conftest import TEST_ADAPTER_CONFIG, setup_map


_COMPONENT = "main_brush"


def _make_reset_button(manager: MagicMock) -> EufyVacuumMaintenanceResetButton:
    return EufyVacuumMaintenanceResetButton(
        manager=manager,
        vacuum_entity_id=_VAC,
        component=_COMPONENT,
        label="Main Brush",
        icon="mdi:brush",
    )


def _make_run_button(manager: MagicMock, profile_id: str = "p1") -> EufyVacuumSavedRunProfileButton:
    return EufyVacuumSavedRunProfileButton(
        manager=manager,
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        profile_id=profile_id,
    )


# ---------------------------------------------------------------------------
# [BE-1] / [BE-2] EufyVacuumMaintenanceResetButton static properties
# ---------------------------------------------------------------------------

def test_reset_button_unique_id_encodes_vacuum_component_suffix():
    """[BE-1] unique_id includes vacuum key, component name, and maintenance_reset suffix."""
    manager = make_manager_mock()
    btn = _make_reset_button(manager)
    uid = btn.unique_id
    assert "alfred" in uid
    assert _COMPONENT in uid
    assert "maintenance_reset" in uid


def test_reset_button_icon_from_constructor():
    """[BE-2] icon is set from the icon argument passed at init."""
    manager = make_manager_mock()
    btn = _make_reset_button(manager)
    assert btn.icon == "mdi:brush"


# ---------------------------------------------------------------------------
# [BE-3] EufyVacuumMaintenanceResetButton.async_press
# ---------------------------------------------------------------------------

async def test_reset_button_async_press_calls_manager(hass):
    """[BE-3] async_press calls reset_maintenance and async_save."""
    manager = make_manager_mock()
    btn = _make_reset_button(manager)
    btn.hass = hass

    await btn.async_press()

    manager.reset_maintenance.assert_called_once_with(
        vacuum_entity_id=_VAC,
        component=_COMPONENT,
    )
    manager.async_save.assert_awaited_once()


# ---------------------------------------------------------------------------
# [BE-4] EufyVacuumSavedRunProfileButton.unique_id
# ---------------------------------------------------------------------------

def test_run_button_unique_id_uses_prefix_and_profile_id():
    """[BE-4] unique_id is prefix + profile_id (stable across renames)."""
    manager = make_manager_mock()
    btn = _make_run_button(manager, profile_id="my_profile")
    uid = btn.unique_id
    assert "alfred" in uid
    assert _MAP in uid
    assert "run_profile" in uid
    assert uid.endswith("my_profile")


# ---------------------------------------------------------------------------
# [BE-5] EufyVacuumSavedRunProfileButton — name via the translation mechanism
# ---------------------------------------------------------------------------

def test_run_button_declares_a_translation_key_and_placeholder():
    """[BE-5] EP-5: the name resolves from strings.json, not an f-string.

    This was the ONE entity class in the integration that set
    has_entity_name = True and then overrode `name` with f"Run {profile_name}",
    so the verb stayed English in all 18 shipped locales while every sibling
    resolved its name from strings.json. HA now composes it from
    entity.button.run_profile with {profile} interpolated.
    """
    manager = make_manager_mock(run_profiles={"p1": {"name": "Morning Vacuum", "expose_as_button": True}})
    btn = _make_run_button(manager)

    assert btn.translation_key == "run_profile"
    assert btn.translation_placeholders == {"profile": "Morning Vacuum"}
    assert btn.profile_name == "Morning Vacuum"
    # The class must NOT carry its own name any more — an override would win over
    # the translation and silently re-introduce the English.
    assert type(btn).name is not None      # inherited Entity.name, not a local one
    assert "name" not in vars(type(btn))


def test_run_button_name_defaults_when_profile_missing():
    """[BE-5] a profile with no name field still yields a usable placeholder."""
    manager = make_manager_mock(run_profiles={"p1": {}})
    btn = _make_run_button(manager)
    assert btn.profile_name == "Saved Run"
    assert btn.translation_placeholders == {"profile": "Saved Run"}


def test_run_profile_translation_key_exists_in_both_files():
    """[BE-5b] EP-5: the key must be in strings.json AND translations/en.json.

    has_entity_name with a translation_key and no matching entry resolves the
    name to None — every saved-run button on a vacuum would collapse to the bare
    device name and become indistinguishable. Cheap to get wrong, invisible in a
    unit test that only reads the entity.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "custom_components" / "eufy_vacuum"
    for rel in ("strings.json", "translations/en.json"):
        data = json.loads((root / rel).read_text(encoding="utf-8"))
        entry = data["entity"]["button"]["run_profile"]
        assert entry["name"] == "Run {profile}", rel
        assert "{profile}" in entry["name"], rel


# ---------------------------------------------------------------------------
# [BE-6] / [BE-7] EufyVacuumSavedRunProfileButton.available
# ---------------------------------------------------------------------------

def test_run_button_available_true_when_expose_flag_set():
    """[BE-6] available=True when profile exists and expose_as_button=True."""
    manager = make_manager_mock(run_profiles={"p1": {"expose_as_button": True}})
    btn = _make_run_button(manager)
    assert btn.available is True


def test_run_button_available_false_when_expose_flag_false():
    """[BE-7] available=False when expose_as_button=False."""
    manager = make_manager_mock(run_profiles={"p1": {"expose_as_button": False}})
    btn = _make_run_button(manager)
    assert btn.available is False


def test_run_button_available_false_when_profile_missing():
    """[BE-7] available=False when the profile_id is not in the library."""
    manager = make_manager_mock(run_profiles={})
    btn = _make_run_button(manager)
    assert btn.available is False


# ---------------------------------------------------------------------------
# [BE-8] EufyVacuumSavedRunProfileButton.extra_state_attributes
# ---------------------------------------------------------------------------

def test_run_button_extra_attrs_include_vacuum_and_map():
    """[BE-8] extra_state_attributes contains vacuum_entity_id and map_id."""
    manager = make_manager_mock(run_profiles={"p1": {"expose_as_button": True}})
    btn = _make_run_button(manager)
    attrs = btn.extra_state_attributes
    assert attrs["vacuum_entity_id"] == _VAC
    assert attrs["map_id"] == _MAP
    assert attrs["profile_id"] == "p1"


# ---------------------------------------------------------------------------
# [BE-9] EufyVacuumSavedRunProfileButton.async_press
# ---------------------------------------------------------------------------

async def test_run_button_async_press_awaits_start_run_profile(hass):
    """[BE-9] async_press AWAITS start_run_profile (a coroutine) then saves.

    Regression for #42: the press called start_run_profile WITHOUT awaiting, so its
    body never ran and the button silently did nothing (while the UI service path,
    which awaits the same call, worked). assert_awaited_* (not assert_called_*) is what
    catches this — a sync MagicMock would pass on an un-awaited call."""
    manager = make_manager_mock(run_profiles={"p1": {"expose_as_button": True}})
    btn = _make_run_button(manager, profile_id="p1")
    btn.hass = hass

    await btn.async_press()

    manager.start_run_profile.assert_awaited_once_with(
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        profile_id="p1",
    )
    manager.async_save.assert_awaited_once()


# ---------------------------------------------------------------------------
# [BE-11] async_setup_entry + dynamic run-profile button reconciliation
# ---------------------------------------------------------------------------

_REAL_MAP = "6"


async def test_run_profile_button_reconciliation_adds_exposed(hass, manager):
    """[BE-11] async_setup_entry wires the update callback; exposing a saved
    profile makes the callback build + add a new run button for it."""
    manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred")
    setup_map(manager, "vacuum.alfred", _REAL_MAP, count=1)

    # A REAL config entry, not a mock one. async_setup_entry's only use of it is
    # entry.async_on_unload(...) (button.py:128) — registering an unload callback —
    # and no test asserts that call, so the mock was pure scaffolding standing in
    # for behaviour MockConfigEntry actually has.
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    captured: list = []

    def _add(entities, *args, **kwargs):
        captured.extend(entities)

    await button_mod.async_setup_entry(hass, entry, _add)
    base_count = len(captured)   # no exposed run profiles yet → no run buttons

    # expose a saved profile → the update callback builds a new button
    pid = manager.save_run_profile(
        vacuum_entity_id="vacuum.alfred", map_id=_REAL_MAP, name="Evening")["profile_id"]
    manager.data["run_profiles"]["vacuum.alfred"][_REAL_MAP][pid]["expose_as_button"] = True
    manager._notify_run_profiles_updated(vacuum_entity_id="vacuum.alfred", map_id=_REAL_MAP)
    await hass.async_block_till_done()

    assert len(captured) == base_count + 1
    assert captured[-1].available is True


async def test_run_profile_button_built_at_setup(hass, manager):
    """[BE-12] a profile exposed before setup is built into the initial entities."""
    manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred")
    setup_map(manager, "vacuum.alfred", _REAL_MAP, count=1)
    pid = manager.save_run_profile(
        vacuum_entity_id="vacuum.alfred", map_id=_REAL_MAP, name="Morning")["profile_id"]
    manager.data["run_profiles"]["vacuum.alfred"][_REAL_MAP][pid]["expose_as_button"] = True

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    captured: list = []
    await button_mod.async_setup_entry(
        hass, entry, lambda entities, *a, **k: captured.extend(entities))

    run_buttons = [e for e in captured if isinstance(e, EufyVacuumSavedRunProfileButton)]
    assert len(run_buttons) == 1
    assert run_buttons[0].available is True


async def test_run_profile_button_reconciliation_removes_stale(hass, manager):
    """[BE-13] un-exposing a previously-exposed saved profile makes the callback
    remove its now-stale run button: it is dropped from the in-memory map (its
    HA-owned async_remove is invoked) AND un-registered from the entity registry,
    so no orphaned button lingers for a profile that is no longer exposed."""
    manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred")
    setup_map(manager, "vacuum.alfred", _REAL_MAP, count=1)
    pid = manager.save_run_profile(
        vacuum_entity_id="vacuum.alfred", map_id=_REAL_MAP, name="Evening")["profile_id"]
    manager.data["run_profiles"]["vacuum.alfred"][_REAL_MAP][pid]["expose_as_button"] = True

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    captured: list = []
    await button_mod.async_setup_entry(
        hass, entry, lambda entities, *a, **k: captured.extend(entities))

    # the exposed profile built one run button at setup; capture its identity
    run_button = next(e for e in captured if isinstance(e, EufyVacuumSavedRunProfileButton))
    unique_id = run_button.unique_id
    # async_remove is HA's own teardown; stub it so an un-added test entity can't
    # error, and assert the reconcile invokes it.
    run_button.async_remove = AsyncMock()

    # register the button so the reconcile's registry un-register path is exercised
    registry = er.async_get(hass)
    registry.async_get_or_create("button", DOMAIN, unique_id)
    assert registry.async_get_entity_id("button", DOMAIN, unique_id) is not None

    # un-expose the profile → the now-stale button must be reconciled away
    manager.data["run_profiles"]["vacuum.alfred"][_REAL_MAP][pid]["expose_as_button"] = False
    manager._notify_run_profiles_updated(vacuum_entity_id="vacuum.alfred", map_id=_REAL_MAP)
    await hass.async_block_till_done()

    run_button.async_remove.assert_awaited()  # popped + removed from the platform
    assert registry.async_get_entity_id("button", DOMAIN, unique_id) is None  # un-registered


# ---------------------------------------------------------------------------
# [BE-14] - [BE-16]  THE RENAME SWAP, which the code itself flagged as unguarded.
#
# The comment at button.py:113 says it in as many words -- "NO TEST REACHES THIS
# BRANCH (ledger T4, open)" -- and names the covered sensor twin, [INIT-13]
# `test_room_rename_swaps_entity_keeping_unique_id`. So the fix for a forgotten
# sibling (EP-5 / SN-4 reached the sensor platform and not this one) was ITSELF
# unguarded: delete the branch and the suite stayed green. Measured.
#
# WHY THE STUBS. This harness never adds the entity to a platform, so HA's real
# `async_remove` / `async_write_ha_state` raise -- and `_notify_run_profiles_updated`
# (core/manager.py:1117-1132) wraps every callback in a blanket `except Exception`
# that logs and continues, so that raise produces NO test failure. [BE-13] already
# stubs `async_remove` for the same reason. Every assertion below is therefore a
# RECORDED CALL or the `async_add_entities` capture list, never an escaping
# exception, and each named red input was confirmed red THROUGH that swallow.
#
# A SHAPE DELIBERATELY NOT TAKEN, and it is a real alternative: these could be
# written as full-platform tests in test_init_setup.py, mirroring [INIT-13] exactly,
# where the entity has a real entity_id and nothing needs stubbing. That version is
# the more faithful sibling; this one reuses the [BE-11]/[BE-13] harness and is
# cheaper. If a third rename claim ever lands here, prefer the INIT- shape.
# ---------------------------------------------------------------------------

async def _setup_one_exposed(hass, manager, name="Evening"):
    """The [BE-11] harness: one exposed profile, set up, entities captured."""
    manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred")
    setup_map(manager, "vacuum.alfred", _REAL_MAP, count=1)
    pid = manager.save_run_profile(
        vacuum_entity_id="vacuum.alfred", map_id=_REAL_MAP, name=name)["profile_id"]
    manager.data["run_profiles"]["vacuum.alfred"][_REAL_MAP][pid][
        "expose_as_button"] = True

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    captured: list = []
    await button_mod.async_setup_entry(
        hass, entry, lambda entities, *a, **k: captured.extend(entities))
    return pid, captured


def _stub_ha_teardown(entity):
    """Replace HA's own teardown/state methods with SPEC'D doubles.

    SPEC'D, NOT BARE, for two reasons. `create_autospec` on the bound method keeps
    the real signature, so a call with the wrong arity fails HERE instead of being
    swallowed by a mock that accepts anything -- and these run inside
    `_notify_run_profiles_updated`'s blanket `except`, which is precisely where a
    silently-wrong call would never be seen. The mock ratchet (W0) is also
    shrink-only, and this file's one bare mock is already spent on [BE-13].

    WHY STUB AT ALL: this harness never adds the entity to a platform, so HA's real
    `async_remove` / `async_write_ha_state` raise -- and that raise is swallowed, so
    the test would observe nothing rather than fail.
    """
    entity.async_remove = create_autospec(entity.async_remove)
    entity.async_write_ha_state = create_autospec(entity.async_write_ha_state)
    return entity


def _run_buttons(captured):
    return [e for e in captured if isinstance(e, EufyVacuumSavedRunProfileButton)]


async def test_run_profile_rename_swaps_entity_keeping_unique_id(hass, manager):
    """[BE-14] A renamed profile replaces the entity OBJECT under the same unique_id.

    The stale object caches the old name in `_attr_translation_placeholders`, so
    writing state onto it would never update the friendly name -- which is precisely
    what SN-4 fixed in the sensor platform. The fix here swaps the object and
    deliberately does NOT call `registry.async_update_entity(name=...)`, which would
    stomp a user override and freeze future translation updates.

    THE REGISTRY HALF IS ASSERTED, NOT NARRATED. An earlier draft claimed the
    unique_id check proved "the registry entry is undisturbed" -- it proves nothing
    of the sort: `unique_id` is a pure function of (vacuum, map, profile_id), none of
    which the swap touches, so it holds under every ablation in which `new` exists at
    all. So the entry is really created and really given a user override here, and
    BOTH are asserted to survive. That is the counterfactual against the rejected
    implementation.

    RED, three measured inputs: make line 113's comparison never true (the swap never
    happens, `async_remove` is never awaited, one button stays); delete the
    `hass.async_create_task(_swap_renamed())` (same); delete ONLY the `continue`
    after it (`async_write_ha_state` is then called on the stale object, which is the
    assertion that pins that one line).

    LEDGER NOTE: this test COVERS `entity_map[unique_id] = entity` but does not PIN
    it -- deleting that line leaves this test green. [BE-15] is the only test that
    sees it.
    """
    pid, captured = await _setup_one_exposed(hass, manager)
    old = _run_buttons(captured)[0]
    assert old.profile_name == "Evening"
    uid = old.unique_id

    # A REAL registry entry with a REAL user override, so the survival claim has a
    # subject. Without this the test observes nothing whatsoever about the registry.
    registry = er.async_get(hass)
    ent_id = registry.async_get_or_create("button", DOMAIN, uid).entity_id
    registry.async_update_entity(ent_id, name="My Name")

    _stub_ha_teardown(old)

    # Through the REAL producer: rename_run_profile writes the name and fires the
    # notification itself, so nothing here pokes private state to reach the branch.
    manager.rename_run_profile(
        vacuum_entity_id="vacuum.alfred", map_id=_REAL_MAP, profile_id=pid,
        name="Great Room")
    await hass.async_block_till_done()

    old.async_remove.assert_awaited_once()
    old.async_write_ha_state.assert_not_called()  # the `continue` skipped the write

    runs = _run_buttons(captured)
    assert len(runs) == 2, "the swapped-in object was never added"
    new = runs[-1]
    assert new.profile_name == "Great Room", (
        "the stale object could never report this -- which is what SN-4 was about"
    )
    assert registry.async_get_entity_id("button", DOMAIN, uid) == ent_id
    assert registry.async_get(ent_id).name == "My Name", (
        "the swap stomped the user's name override"
    )


async def test_a_second_notification_does_not_re_swap_the_renamed_button(hass, manager):
    """[BE-15] The swapped-in object is ADOPTED into the map, so the rename settles.

    This is the only test that can see `entity_map[unique_id] = entity`, and the
    reason is a contrast nothing else provides: with that line deleted the closure
    keeps the STALE object, so the NEXT notification finds a name mismatch all over
    again and swaps a second time. One notification cannot distinguish an adopted map
    from an un-adopted one -- [BE-14] and the plain no-rename case both stay GREEN
    under that ablation. Measured: `old.async_remove` awaited twice,
    `new.async_write_ha_state` never called, three buttons instead of two.

    RED: delete `entity_map[unique_id] = entity` (above), or delete
    `existing.async_write_ha_state()` (which reddens [BE-16] too).
    """
    pid, captured = await _setup_one_exposed(hass, manager)
    old = _run_buttons(captured)[0]
    _stub_ha_teardown(old)

    manager.rename_run_profile(
        vacuum_entity_id="vacuum.alfred", map_id=_REAL_MAP, profile_id=pid,
        name="Great Room")
    await hass.async_block_till_done()

    new = _run_buttons(captured)[-1]
    _stub_ha_teardown(new)

    # ...and now a notification carrying NO rename, the steady state after a swap.
    manager._notify_run_profiles_updated(
        vacuum_entity_id="vacuum.alfred", map_id=_REAL_MAP)
    await hass.async_block_till_done()

    new.async_write_ha_state.assert_called_once()
    new.async_remove.assert_not_awaited()
    old.async_remove.assert_awaited_once()  # STILL once -- no second swap
    assert len(_run_buttons(captured)) == 2


async def test_a_notification_without_a_rename_writes_state_on_every_button(hass, manager):
    """[BE-16] The unchanged arm: keep the object, push it to the state machine, skip.

    TWO EXPOSED PROFILES, AND THAT IS THE WHOLE POINT. With one, the matched row is
    the LAST row of a one-row loop, and `continue` is indistinguishable from `break`
    -- measured: the single-profile version of this test stays green with the
    `continue` turned into a `break`, along with every other test in this file. The
    names are chosen so `_build_run_profile_buttons_for_map`'s sort on
    `profile_name.lower()` makes the order deterministic.

    RED: `continue` -> `break` (the second button never gets its write); delete
    `existing.async_write_ha_state()` (neither does); delete the `continue` entirely
    (both buttons are then re-added as new entities).
    """
    manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred")
    setup_map(manager, "vacuum.alfred", _REAL_MAP, count=1)
    for name in ("Alpha", "Zulu"):
        pid = manager.save_run_profile(
            vacuum_entity_id="vacuum.alfred", map_id=_REAL_MAP, name=name)["profile_id"]
        manager.data["run_profiles"]["vacuum.alfred"][_REAL_MAP][pid][
            "expose_as_button"] = True

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    captured: list = []
    await button_mod.async_setup_entry(
        hass, entry, lambda entities, *a, **k: captured.extend(entities))

    runs = _run_buttons(captured)
    assert len(runs) == 2, "precondition: both profiles must be exposed"
    for button in runs:
        _stub_ha_teardown(button)

    manager._notify_run_profiles_updated(
        vacuum_entity_id="vacuum.alfred", map_id=_REAL_MAP)
    await hass.async_block_till_done()

    for button in runs:
        button.async_write_ha_state.assert_called_once()
        button.async_remove.assert_not_awaited()
    assert len(_run_buttons(captured)) == 2, "an unchanged button was re-added"


# ---------------------------------------------------------------------------
# [BE-17] THE MODEL GATE's call site
#
# A CALL-SITE REACHABILITY GAP, not a logic gap, and the distinction is the finding.
# The gate FUNCTION is heavily tested -- [MGT-1]..[MGT-6] in
# tests/adapters/test_model_gate.py pin `components_for_model` and
# `model_has_component` directly, including the REGIME_UNRESOLVED ruling. But a grep
# of tests/ for either name outside that file returns ZERO hits, against FOUR
# production call sites (button.py:56, number.py:63, sensor/__init__.py:151,
# maintenance/manager.py:601). Nothing proved any platform consults it --
# `feedback_audit_callsite_reachability`: "a correct service with ZERO callers passes
# every audit".
#
# The incident the gate exists for: before 2026-09-14 this loop walked the flat BRAND
# catalog, so a component the model does not have still minted an entity -- 876
# (model, component) pairs across three brands, confirmed on hardware (ivy, a
# Roborock S6, carried button/number/sensor entities for a cleaning tray it has no
# station for).
# ---------------------------------------------------------------------------

async def test_the_model_gate_drops_a_guide_only_maintenance_button(hass, manager):
    """[BE-17] An unresolved regime keeps a sensor-backed part and drops a guide-only one.

    This is the live [MGT-3] ruling, not a synthetic state: *"if regime is unresolved
    it will lose its maintenance cards"*. `components_for_model` is keyed on
    `manager._get_registry_model_code`, and the `manager` fixture leaves vacuum.alfred
    out of the entity registry, so the model code is None, `model_key_regimes` misses,
    and the helper returns REGIME_UNRESOLVED -- after which `model_has_component`
    answers `has_own_counter`: True for the filter, False for the guide-only tray.

    THE DROPPED COMPONENT IS DECLARED FIRST, AND THAT IS LOAD-BEARING -- do not tidy
    the order. Dict iteration is insertion order, so with the tray declared LAST the
    `continue` on line 59 is the last row of the loop and `continue` -> `break` leaves
    this test green at its exact asserted set. Declared first, that ablation yields an
    EMPTY set and the test goes red. Measured both ways.

    THE TWO-KEY CONTRAST IS WHAT DEFEATS THE EMPTY-CONTAINER TRAP: one surviving
    button and one dropped button. A dead loop or an emptied catalog yields zero and
    fails; a gate that always says yes yields two and fails. And BOTH components sit
    in `maintenance_sources` with non-None values, so the `sources.get(component) is
    None` arm one line up cannot be what drops the tray.

    RED, three measured inputs: delete the whole `if not model_has_component(...):
    continue` guard (the tray mints a second button); restore the pre-2026-09-14
    suffix exemption by forcing `has_own_counter=True` (both survive) -- the very
    clause [MGT-2] exists to keep retired; or turn either `continue` into a `break`.

    ⚠ WHAT THIS TEST DOES *NOT* PIN, and it took an adversarial audit to see it:
    `components_for_model`. In REGIME_UNRESOLVED `_emitted` is ALREADY None, so
    replacing the whole `components_for_model(...)` call with `_emitted = None`
    changes nothing and reddens NOTHING -- measured, with a control (hardcoding a
    model code the regime KNOWS does redden this test, so the probe can see the
    call and the null is real). An identity is not a mutation: this test pins
    `model_has_component` and the two `continue`s, and [BE-18] is what pins the
    regime table being consulted at all. Neither half is sufficient alone.
    """
    register_adapter_config(
        "vacuum.alfred",
        {
            **TEST_ADAPTER_CONFIG,
            "maintenance_components": {
                # FIRST on purpose -- see the docstring.
                "cleaning_tray": {"label": "Cleaning Tray", "icon": "mdi:tray"},
                # MIDDLE on purpose, and it is dropped by the OTHER `continue` --
                # the one a line above the gate, on `sources.get(component) is
                # None`. Both are now non-terminal rows, so neither `continue` can
                # be a `break` in disguise. The two are copies of each other, and a
                # guard that exists reads as complete: this is the shoulder just
                # outside the window the gate test was aiming at.
                "side_brush": {"label": "Side Brush", "icon": "mdi:broom"},
                "filter": {"label": "Filter", "icon": "mdi:air-filter",
                           "sensor_suffix": "filter_life"},
            },
            "upkeep_catalog": {
                "key_guides": {"r1": {"filter": {}, "cleaning_tray": {}}},
                "model_key_regimes": {"T2320": "r1"},
            },
        },
    )
    try:
        manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred")
        # Pre-seed the snapshot so get_vacuum_capabilities(refresh=False) answers from
        # it rather than re-detecting. TEST_ADAPTER_CONFIG declares no model_family, so
        # the self-heal re-detect at core/manager.py:1986 cannot fire.
        # The two keys mirror `core/capabilities.py`'s payload, which
        # `core/manager.py` stores at data["capabilities"][vacuum] -- named so a
        # rename sweep greps its way here rather than leaving this passing against
        # a shape production no longer emits.
        manager.data.setdefault("capabilities", {})["vacuum.alfred"] = {
            "detected_model": "a-model-no-regime-knows",
            "maintenance_sources": {
                "filter": "sensor.alfred_filter_life",
                "cleaning_tray": "sensor.alfred_uptime",
                # DECLARED AND UNRESOLVED -- the shape the `sources is None` arm
                # exists for: the adapter names the part, the device reports nothing.
                "side_brush": None,
            },
        }

        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)
        captured: list = []
        await button_mod.async_setup_entry(
            hass, entry, lambda entities, *a, **k: captured.extend(entities))
    finally:
        # Restore the fixture's adapter: the registry is MODULE-GLOBAL state, and a
        # leaked registration is how another file's test once passed for the wrong
        # reason (docs/testing/05-gotchas-and-pitfalls.md, SS15).
        register_adapter_config("vacuum.alfred", dict(TEST_ADAPTER_CONFIG))

    reset_ids = {
        entity.unique_id for entity in captured
        if isinstance(entity, EufyVacuumMaintenanceResetButton)
    }
    assert reset_ids == {"vacuum_alfred_filter_maintenance_reset"}, reset_ids


async def test_the_model_gate_reads_the_regime_for_a_known_model(hass, manager):
    """[BE-18] The RESOLVED arm: a SENSOR-BACKED part the regime omits is dropped.

    THIS IS THE HALF THAT PROVES THE REGIME TABLE IS READ. [BE-17] runs with no
    model code, where `model_has_component` collapses to `return has_own_counter`
    and the table is never touched -- so `button.py` could stop consulting the
    adapter's `upkeep_catalog` entirely and [BE-17] would not notice. Measured:
    `_emitted = None` left all 19 tests green before this one existed.

    AND IT IS THE RULING, not a style choice. Under a RESOLVED regime a
    sensor-backed component is gated TOO -- Chris: *"for eufy Gate them."* The old
    gate exempted anything declaring a `sensor_suffix`, and since Eufy's tray
    declares one it could never be reached, so the hole was structural rather than
    an oversight. `cleaning_tray` here therefore declares a `sensor_suffix` AND
    resolves to a real source, and must still be dropped because `r1` omits it.
    That is the exact 876-pair shape confirmed on hardware: ivy, a Roborock S6,
    carried button/number/sensor entities for a cleaning tray it has no station for.

    THE DROPPED COMPONENT IS DECLARED FIRST for the same reason as in [BE-17] --
    do not tidy the order, or `continue` -> `break` stops being visible.

    RED: replace `_emitted = components_for_model(...)` with `_emitted = None` --
    the regime goes unresolved, `has_own_counter` is True for the tray, and it mints
    a second button. This test is the ONLY one in the suite that sees that mutation.
    """
    # A REAL device-registry model, which is what `_get_registry_model_code` reads;
    # the `manager` fixture deliberately leaves vacuum.alfred out of the registry,
    # which is why [BE-17] gets REGIME_UNRESOLVED for free.
    dev_entry = MockConfigEntry(domain=DOMAIN, entry_id="be18dev")
    dev_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=dev_entry.entry_id,
        identifiers={(DOMAIN, "alfred-be18")},
        model="T2320",
    )
    er.async_get(hass).async_get_or_create(
        "vacuum", "robovac_mqtt", "alfred_be18",
        suggested_object_id="alfred", device_id=device.id,
    )
    assert manager._get_registry_model_code(
        vacuum_entity_id="vacuum.alfred") == "T2320", (
        "precondition: the model must RESOLVE, or this is [BE-17] again"
    )

    register_adapter_config(
        "vacuum.alfred",
        {
            **TEST_ADAPTER_CONFIG,
            "maintenance_components": {
                # Sensor-backed AND omitted from regime r1. Declared FIRST.
                "cleaning_tray": {"label": "Cleaning Tray", "icon": "mdi:tray",
                                  "sensor_suffix": "tray_life"},
                "filter": {"label": "Filter", "icon": "mdi:air-filter",
                           "sensor_suffix": "filter_life"},
            },
            "upkeep_catalog": {
                "key_guides": {"r1": {"filter": {}}},
                "model_key_regimes": {"T2320": "r1"},
            },
        },
    )
    try:
        manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred")
        # Keys mirror `core/capabilities.py`'s payload -- see [BE-17].
        manager.data.setdefault("capabilities", {})["vacuum.alfred"] = {
            "detected_model": "T2320",
            "maintenance_sources": {
                "filter": "sensor.alfred_filter_life",
                "cleaning_tray": "sensor.alfred_tray_life",
            },
        }

        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)
        captured: list = []
        await button_mod.async_setup_entry(
            hass, entry, lambda entities, *a, **k: captured.extend(entities))
    finally:
        register_adapter_config("vacuum.alfred", dict(TEST_ADAPTER_CONFIG))

    reset_ids = {
        entity.unique_id for entity in captured
        if isinstance(entity, EufyVacuumMaintenanceResetButton)
    }
    # ONE survives and ONE is dropped, both sensor-backed -- so the only thing that
    # can separate them is the regime table.
    assert reset_ids == {"vacuum_alfred_filter_maintenance_reset"}, reset_ids
