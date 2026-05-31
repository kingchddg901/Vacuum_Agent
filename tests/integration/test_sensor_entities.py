"""Phase 8 integration tests — sensor entity property getters.

Coverage targets
----------------
[SE-1]  EufyVacuumOnboardingSensor.native_value = 'complete' when all maps complete.
[SE-2]  EufyVacuumOnboardingSensor.native_value = 'rooms_needed' when map has no rooms.
[SE-3]  EufyVacuumOnboardingSensor.extra_state_attributes includes vacuum_entity_id.
[SE-4]  EufyVacuumProfileSensor.native_value returns a string-encoded count.
[SE-5]  EufyVacuumProfileSensor.extra_state_attributes includes profile_count.
[SE-6]  EufyVacuumThemeStateSensor.native_value = 'none' when no active theme.
[SE-7]  EufyVacuumThemeStateSensor.native_value = theme name when active theme set.
[SE-8]  EufyVacuumThemeStateSensor.extra_state_attributes includes library_count.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.sensor.onboarding import EufyVacuumOnboardingSensor
from custom_components.eufy_vacuum.sensor.profile import EufyVacuumProfileSensor
from custom_components.eufy_vacuum.sensor.theme import EufyVacuumThemeStateSensor

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"


# ---------------------------------------------------------------------------
# [SE-1] / [SE-2] / [SE-3] EufyVacuumOnboardingSensor
# ---------------------------------------------------------------------------

def test_onboarding_sensor_complete_when_all_rooms_configured(manager):
    """[SE-1] native_value='complete' after rooms are imported and configured."""
    setup_map(manager, _VAC, _MAP, count=2)
    # Mark rooms as configured.
    for room in manager.data["maps"][_VAC][_MAP]["rooms"].values():
        room["is_configured"] = True

    sensor = EufyVacuumOnboardingSensor(manager=manager, vacuum_entity_id=_VAC)
    assert sensor.native_value == "complete"


def test_onboarding_sensor_rooms_needed_when_no_rooms(manager):
    """[SE-2] native_value='rooms_needed' when a map exists but has no configured rooms."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    # Ensure a maps entry exists with no rooms.
    manager.data.setdefault("maps", {}).setdefault(_VAC, {}).setdefault(_MAP, {"rooms": {}})

    sensor = EufyVacuumOnboardingSensor(manager=manager, vacuum_entity_id=_VAC)
    # No rooms → rooms_needed state.
    assert sensor.native_value == "rooms_needed"


def test_onboarding_sensor_extra_attributes_include_vacuum_entity_id(manager):
    """[SE-3] extra_state_attributes contains vacuum_entity_id."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    sensor = EufyVacuumOnboardingSensor(manager=manager, vacuum_entity_id=_VAC)
    attrs = sensor.extra_state_attributes
    assert attrs["vacuum_entity_id"] == _VAC
    assert "maps" in attrs
    assert "all_complete" in attrs


# ---------------------------------------------------------------------------
# [SE-4] / [SE-5] EufyVacuumProfileSensor
# ---------------------------------------------------------------------------

def test_profile_sensor_native_value_is_string_count(manager):
    """[SE-4] native_value is a string-encoded integer (profile count)."""
    capabilities = manager.get_vacuum_capabilities(vacuum_entity_id=_VAC, refresh=False)
    sensor = EufyVacuumProfileSensor(
        manager=manager,
        vacuum_entity_id=_VAC,
        capabilities=capabilities,
    )
    value = sensor.native_value
    assert isinstance(value, str)
    assert int(value) >= 0


def test_profile_sensor_extra_attributes_include_profile_count(manager):
    """[SE-5] extra_state_attributes has profile_count and profiles keys."""
    capabilities = manager.get_vacuum_capabilities(vacuum_entity_id=_VAC, refresh=False)
    sensor = EufyVacuumProfileSensor(
        manager=manager,
        vacuum_entity_id=_VAC,
        capabilities=capabilities,
    )
    attrs = sensor.extra_state_attributes
    assert "profile_count" in attrs
    assert "profiles" in attrs
    assert isinstance(attrs["profiles"], dict)


# ---------------------------------------------------------------------------
# [SE-6] / [SE-7] / [SE-8] EufyVacuumThemeStateSensor
# ---------------------------------------------------------------------------

def test_theme_sensor_native_value_is_none_when_no_active_theme(manager):
    """[SE-6] native_value='none' when no active theme is set for the vacuum."""
    sensor = EufyVacuumThemeStateSensor(manager=manager, vacuum_entity_id=_VAC)
    assert sensor.native_value == "none"


def test_theme_sensor_native_value_returns_theme_name(manager):
    """[SE-7] native_value returns the active theme's name after save_theme_as_new."""
    manager.themes.save_theme_as_new(vacuum_entity_id=_VAC, name="Cool Theme")
    sensor = EufyVacuumThemeStateSensor(manager=manager, vacuum_entity_id=_VAC)
    assert sensor.native_value == "Cool Theme"


def test_theme_sensor_extra_attributes_include_library_count(manager):
    """[SE-8] extra_state_attributes includes library_count and active_theme_id."""
    manager.themes.save_theme_as_new(vacuum_entity_id=_VAC, name="Theme A")
    sensor = EufyVacuumThemeStateSensor(manager=manager, vacuum_entity_id=_VAC)
    attrs = sensor.extra_state_attributes
    assert "library_count" in attrs
    assert "active_theme_id" in attrs
    assert "vacuum_entity_id" in attrs
    assert attrs["vacuum_entity_id"] == _VAC
    # At least one theme was saved (plus any preloaded defaults).
    assert attrs["library_count"] >= 1
