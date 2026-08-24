"""Phase 8 integration tests — sensor entity property getters.

Coverage targets
----------------
[SE-1]  EufyVacuumOnboardingSensor.native_value = 'complete' when all maps complete.
[SE-2]  EufyVacuumOnboardingSensor.native_value = 'rooms_needed' when map has no rooms.
[SE-3]  EufyVacuumOnboardingSensor.extra_state_attributes includes vacuum_entity_id.
[SE-4]  EufyVacuumProfileSensor.native_value returns a string-encoded count.
[SE-5]  EufyVacuumProfileSensor.extra_state_attributes includes profile_count.
        WARNING: [SE-5] IS SATISFIED BY AN EMPTY DICT and its sibling by a zero.
        Between 2026-08-07 and 2026-08-24 both passed while the sensor published
        NOTHING on every vacuum. Do not treat them as coverage of the contents.
[SE-13] The profile sensor resolves the vacuum's adapter catalog. Omitting
        `catalog=` makes get_available_profiles return {} for every vacuum --
        the regression [SE-5] could not see -- and it empties the card's
        profile matcher, whose `definition` values come from this attribute.
[SE-14] `capability_filtered: True` must not be published over an empty set.
        It asserts a capability removed the missing profiles; when the catalog
        is absent nothing was capability-filtered at all.
[SE-6]  EufyVacuumThemeStateSensor.native_value = 'none' when no active theme.
[SE-7]  EufyVacuumThemeStateSensor.native_value = theme name when active theme set.
[SE-8]  EufyVacuumThemeStateSensor.extra_state_attributes includes library_count.
[SE-9]  SN-10b: a stored library entry with name=None renders 'none', not the
        literal string 'None'.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.adapters.registry import (
    clear_registry,
    register_adapter_config,
)
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
    """[SE-1] native_value='complete' after rooms are imported and configured.

    ONB-5: native_value/extra_state_attributes read a cache now (mirrors
    EufyVacuumMaintenanceRemainingSensor) — _refresh_summary() primes it, same as
    those tests call _refresh_cache() directly.
    """
    setup_map(manager, _VAC, _MAP, count=2)
    # Mark rooms as configured.
    for room in manager.data["maps"][_VAC][_MAP]["rooms"].values():
        room["is_configured"] = True

    sensor = EufyVacuumOnboardingSensor(manager=manager, vacuum_entity_id=_VAC)
    sensor._refresh_summary()
    assert sensor.native_value == "complete"


def test_onboarding_sensor_rooms_needed_when_no_rooms(manager):
    """[SE-2] native_value='rooms_needed' when a map exists but has no configured rooms."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    # Ensure a maps entry exists with no rooms.
    manager.data.setdefault("maps", {}).setdefault(_VAC, {}).setdefault(_MAP, {"rooms": {}})

    sensor = EufyVacuumOnboardingSensor(manager=manager, vacuum_entity_id=_VAC)
    sensor._refresh_summary()
    # No rooms → rooms_needed state.
    assert sensor.native_value == "rooms_needed"


def test_onboarding_sensor_extra_attributes_include_vacuum_entity_id(manager):
    """[SE-3] extra_state_attributes contains vacuum_entity_id."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    sensor = EufyVacuumOnboardingSensor(manager=manager, vacuum_entity_id=_VAC)
    sensor._refresh_summary()
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


def test_theme_sensor_native_value_stored_none_name_renders_none(manager):
    """[SE-9] SN-10b: entry.get("name", "none") only fires its default on an
    ABSENT key — a stored {"name": None} entry rendered the literal string
    "None" instead of "none". The fix is entry.get("name") or "none"."""
    result = manager.themes.save_theme_as_new(vacuum_entity_id=_VAC, name="Temp")
    theme_id = result["theme_id"]
    manager.data["theme"]["library"][theme_id]["name"] = None

    sensor = EufyVacuumThemeStateSensor(manager=manager, vacuum_entity_id=_VAC)
    assert sensor.native_value == "none"


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


# ---------------------------------------------------------------------------
# [SE-13] - [SE-14] the profile sensor must resolve the adapter catalog
# ---------------------------------------------------------------------------

_PROFILE_ADAPTER = {
    "adapter_id": "test",
    "source": "test",
    "room_profiles": {
        "builtins": {
            "vacuum_quick": {"label": "Quick Vacuum", "clean_mode": "Vacuum",
                             "fan_speed": "Standard", "clean_intensity": "Quick"},
            "vacuum_deep": {"label": "Deep Vacuum", "clean_mode": "Vacuum",
                            "fan_speed": "Max", "clean_intensity": "Deep"},
        },
    },
}


def _profile_sensor(manager):
    capabilities = manager.get_vacuum_capabilities(vacuum_entity_id=_VAC, refresh=False)
    return EufyVacuumProfileSensor(
        manager=manager, vacuum_entity_id=_VAC, capabilities=capabilities,
    )


def test_se13_the_profile_sensor_resolves_the_adapter_catalog(manager):
    """[SE-13] RED BEFORE THE FIX, and red for the 17 days nobody noticed.

    The sensor omitted `catalog=`, so `get_default_room_profiles(catalog=None)` gave
    `{}`, the merge kept only stored profiles, and the built-in whitelist filtered
    those out too. Measured live 2026-08-24: alfred, ivy and robin all published '0'.

    Asserted as NON-EMPTY plus a named key present. "len > 0" alone would pass on any
    single junk entry; the named key is what proves the ADAPTER's declared catalog is
    the thing that arrived, which is the actual contract after ad8c074c moved the
    built-ins out of core.
    """
    register_adapter_config(_VAC, _PROFILE_ADAPTER)
    attrs = _profile_sensor(manager).extra_state_attributes

    assert attrs["profiles"], (
        "the sensor published no profiles at all -- catalog= is missing again"
    )
    assert "vacuum_quick" in attrs["profiles"], (
        f"the adapter's declared builtins did not reach the sensor: "
        f"{sorted(attrs['profiles'])}"
    )
    assert attrs["profile_count"] == len(attrs["profiles"])
    assert int(_profile_sensor(manager).native_value) == len(attrs["profiles"])


def test_se13_the_published_labels_come_from_the_adapter_not_core(manager):
    """[SE-13] RED IF CORE EVER RE-ACQUIRES A BUILT-IN CATALOG.

    The whole point of ad8c074c is that core owns the KEY SPACE and never a brand's
    WORDS. This pins the label text to the adapter declaration, so a future 'helpful'
    in-core fallback -- which would make the sensor look fixed while re-introducing
    the invariant violation -- goes red rather than passing quietly.
    """
    register_adapter_config(_VAC, _PROFILE_ADAPTER)
    labels = _profile_sensor(manager).extra_state_attributes["profile_labels"]

    assert labels.get("vacuum_quick") == "Quick Vacuum", labels


def test_se14_capability_filtered_is_not_asserted_over_an_empty_set(manager):
    """[SE-14] RED BEFORE THE FIX -- it was an unconditional True.

    A vacuum whose adapter declares NO profile catalog has nothing to
    capability-filter, so the published set is empty for a reason that has nothing to
    do with capabilities. Saying True there is the "confident and empty" shape: it
    tells a reader the absence was EXPLAINED, so nobody looks further. For 17 days
    that is exactly what it did.

    No adapter registered is the input, deliberately -- it is the only way to reach a
    genuinely catalog-less vacuum now that both shipped brands declare one, and it is
    the state the sensor was ACTUALLY in on every install before the catalog was
    passed.
    """
    clear_registry()
    attrs = _profile_sensor(manager).extra_state_attributes

    assert not attrs["profiles"], "precondition: no catalog means no profiles"
    assert attrs["capability_filtered"] is False, (
        "capability_filtered asserted over an empty profile set -- "
        "it claims a capability removed what a missing catalog removed"
    )


def test_se14_capability_filtered_stays_true_when_there_is_a_catalog(manager):
    """[SE-14] RED IF THE HONESTY FIX IS OVER-APPLIED INTO ALWAYS-FALSE.

    The flag's meaning -- "this list is capability-scoped" -- is unchanged for a
    vacuum that HAS a catalog, including a fully-capable one where nothing is actually
    removed. Narrowing it to "something was filtered out" would be a different flag,
    and existing consumers read this one.
    """
    register_adapter_config(_VAC, _PROFILE_ADAPTER)
    attrs = _profile_sensor(manager).extra_state_attributes

    assert attrs["profiles"]
    assert attrs["capability_filtered"] is True
