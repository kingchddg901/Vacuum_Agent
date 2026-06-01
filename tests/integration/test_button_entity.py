"""Phase 10 integration tests — button entity platform.

Coverage targets
----------------
[BE-1]  EufyVacuumMaintenanceResetButton.unique_id encodes vacuum, component, and suffix.
[BE-2]  EufyVacuumMaintenanceResetButton.icon set from constructor.
[BE-3]  EufyVacuumMaintenanceResetButton.async_press calls manager.reset_maintenance + async_save.
[BE-4]  EufyVacuumSavedRunProfileButton.unique_id uses prefix + profile_id.
[BE-5]  EufyVacuumSavedRunProfileButton.name returns 'Run {profile_name}'.
[BE-6]  EufyVacuumSavedRunProfileButton.available True when expose_as_button=True.
[BE-7]  EufyVacuumSavedRunProfileButton.available False when expose_as_button=False or missing.
[BE-8]  EufyVacuumSavedRunProfileButton.extra_state_attributes includes vacuum_entity_id and map_id.
[BE-9]  EufyVacuumSavedRunProfileButton.async_press calls manager.start_run_profile + async_save.
[BE-10] _slugify_profile_name lowercases, collapses non-alphanumeric to underscores.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import custom_components.eufy_vacuum.button as button_mod
from custom_components.eufy_vacuum.button import (
    EufyVacuumMaintenanceResetButton,
    EufyVacuumSavedRunProfileButton,
    _slugify_profile_name,
)

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"
_COMPONENT = "main_brush"


def _make_manager(*, run_profile_data: dict | None = None) -> MagicMock:
    """Build a minimal manager mock."""
    manager = MagicMock()
    manager.async_save = AsyncMock()
    manager.reset_maintenance = MagicMock()
    manager.start_run_profile = MagicMock()

    library = run_profile_data or {}
    manager.get_saved_run_profiles.return_value = {"library": library}

    return manager


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
    manager = _make_manager()
    btn = _make_reset_button(manager)
    uid = btn.unique_id
    assert "alfred" in uid
    assert _COMPONENT in uid
    assert "maintenance_reset" in uid


def test_reset_button_icon_from_constructor():
    """[BE-2] icon is set from the icon argument passed at init."""
    manager = _make_manager()
    btn = _make_reset_button(manager)
    assert btn.icon == "mdi:brush"


# ---------------------------------------------------------------------------
# [BE-3] EufyVacuumMaintenanceResetButton.async_press
# ---------------------------------------------------------------------------

async def test_reset_button_async_press_calls_manager(hass):
    """[BE-3] async_press calls reset_maintenance and async_save."""
    manager = _make_manager()
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
    manager = _make_manager()
    btn = _make_run_button(manager, profile_id="my_profile")
    uid = btn.unique_id
    assert "alfred" in uid
    assert _MAP in uid
    assert "run_profile" in uid
    assert uid.endswith("my_profile")


# ---------------------------------------------------------------------------
# [BE-5] EufyVacuumSavedRunProfileButton.name
# ---------------------------------------------------------------------------

def test_run_button_name_returns_run_profile_name():
    """[BE-5] name is 'Run {profile_name}' from the stored profile."""
    manager = _make_manager(run_profile_data={"p1": {"name": "Morning Vacuum", "expose_as_button": True}})
    btn = _make_run_button(manager)
    assert btn.name == "Run Morning Vacuum"


def test_run_button_name_defaults_when_profile_missing():
    """[BE-5] name defaults to 'Run Saved Run' when profile has no name field."""
    manager = _make_manager(run_profile_data={"p1": {}})
    btn = _make_run_button(manager)
    assert btn.name == "Run Saved Run"


# ---------------------------------------------------------------------------
# [BE-6] / [BE-7] EufyVacuumSavedRunProfileButton.available
# ---------------------------------------------------------------------------

def test_run_button_available_true_when_expose_flag_set():
    """[BE-6] available=True when profile exists and expose_as_button=True."""
    manager = _make_manager(run_profile_data={"p1": {"expose_as_button": True}})
    btn = _make_run_button(manager)
    assert btn.available is True


def test_run_button_available_false_when_expose_flag_false():
    """[BE-7] available=False when expose_as_button=False."""
    manager = _make_manager(run_profile_data={"p1": {"expose_as_button": False}})
    btn = _make_run_button(manager)
    assert btn.available is False


def test_run_button_available_false_when_profile_missing():
    """[BE-7] available=False when the profile_id is not in the library."""
    manager = _make_manager(run_profile_data={})
    btn = _make_run_button(manager)
    assert btn.available is False


# ---------------------------------------------------------------------------
# [BE-8] EufyVacuumSavedRunProfileButton.extra_state_attributes
# ---------------------------------------------------------------------------

def test_run_button_extra_attrs_include_vacuum_and_map():
    """[BE-8] extra_state_attributes contains vacuum_entity_id and map_id."""
    manager = _make_manager(run_profile_data={"p1": {"expose_as_button": True}})
    btn = _make_run_button(manager)
    attrs = btn.extra_state_attributes
    assert attrs["vacuum_entity_id"] == _VAC
    assert attrs["map_id"] == _MAP
    assert attrs["profile_id"] == "p1"


# ---------------------------------------------------------------------------
# [BE-9] EufyVacuumSavedRunProfileButton.async_press
# ---------------------------------------------------------------------------

async def test_run_button_async_press_calls_start_run_profile(hass):
    """[BE-9] async_press calls start_run_profile and async_save."""
    manager = _make_manager(run_profile_data={"p1": {"expose_as_button": True}})
    btn = _make_run_button(manager, profile_id="p1")
    btn.hass = hass

    await btn.async_press()

    manager.start_run_profile.assert_called_once_with(
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        profile_id="p1",
    )
    manager.async_save.assert_awaited_once()


# ---------------------------------------------------------------------------
# [BE-10] _slugify_profile_name
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("Morning Vacuum", "morning_vacuum"),
    ("UPSTAIRS & HALL", "upstairs_hall"),
    ("deep-clean!", "deep_clean"),
    ("", "run_profile"),
    (None, "run_profile"),
    ("room 1", "room_1"),
])
def test_slugify_profile_name(value, expected):
    """[BE-10] _slugify_profile_name lowercases and collapses non-alphanumeric to underscores."""
    assert _slugify_profile_name(value) == expected


# ---------------------------------------------------------------------------
# [BE-11] async_setup_entry + dynamic run-profile button reconciliation
# ---------------------------------------------------------------------------

_REAL_MAP = "6"


async def test_run_profile_button_reconciliation_adds_exposed(hass, manager):
    """[BE-11] async_setup_entry wires the update callback; exposing a saved
    profile makes the callback build + add a new run button for it."""
    manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred")
    setup_map(manager, "vacuum.alfred", _REAL_MAP, count=1)

    entry = MagicMock()
    entry.async_on_unload = MagicMock()
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

    entry = MagicMock()
    entry.async_on_unload = MagicMock()
    captured: list = []
    await button_mod.async_setup_entry(
        hass, entry, lambda entities, *a, **k: captured.extend(entities))

    run_buttons = [e for e in captured if isinstance(e, EufyVacuumSavedRunProfileButton)]
    assert len(run_buttons) == 1
    assert run_buttons[0].available is True
