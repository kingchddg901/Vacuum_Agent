"""Phase 10 integration tests — profiles/room_profiles.py pure functions.

Coverage targets
----------------
[RP-1]  get_available_profile_names returns vacuum-only list without mop support.
[RP-2]  get_available_profile_names returns all 4 with full mop support.
[RP-3]  get_available_profiles excludes mop profiles for non-mop device.
[RP-4]  get_available_profiles includes mop profiles for mop+water device.
[RP-5]  normalize_room_profile applies safe defaults for all fields on empty input.
[RP-6]  normalize_room_profile preserves provided values.
[RP-7]  resolve_room_profile_for_room sets water_level=Off on carpet floor.
[RP-8]  resolve_room_profile_for_room uses floor-type water default on hard floors.
[RP-9]  resolve_room_profile_for_room overrides fan_speed for carpet_high_pile.
[RP-10] resolve_room_profile_for_room mop mode + Off water → applies floor default.
[RP-11] resolve_room_profile_for_room edge_mopping forced False in vacuum mode.
[RP-12] apply_capability_gate downgrades mop → vacuum when not supported.
[RP-13] apply_capability_gate sets water_level=Off in vacuum mode.
[RP-14] apply_capability_gate adds capability_gated=True.
[RP-15] resolve_profile_name_for_constraints maps carpet + mop profiles to vacuum equivalents.
[RP-16] legacy profile names are resolved via LEGACY_PROFILE_ALIASES.
[RP-17] _normalize_floor_type: granite + concrete are canonical settable floor types (not coerced).
[RP-18] apply_room_profile_to_config fills omitted fields from the adapter catalog's normalize_defaults, not the in-code Eufy defaults.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.profiles.room_profiles import (
    _normalize_floor_type,
    apply_capability_gate,
    apply_room_profile_to_config,
    get_available_profile_names,
    get_available_profiles,
    normalize_room_profile,
    resolve_profile_name_for_constraints,
    resolve_room_profile_for_room,
)


_NO_MOP_CAPS = {"supports_mop_features": False, "supports_water_control": False}
_FULL_CAPS = {"supports_mop_features": True, "supports_water_control": True}


# ---------------------------------------------------------------------------
# [RP-1] / [RP-2] get_available_profile_names
# ---------------------------------------------------------------------------

def test_available_profile_names_no_mop():
    """[RP-1] Without mop support, only vacuum_quick and vacuum_deep are returned."""
    names = get_available_profile_names(capabilities=_NO_MOP_CAPS)
    assert names == ["vacuum_quick", "vacuum_deep"]


def test_available_profile_names_full_mop():
    """[RP-2] With full mop support, all 4 built-in profiles are returned."""
    names = get_available_profile_names(capabilities=_FULL_CAPS)
    assert set(names) == {"vacuum_quick", "vacuum_deep", "vacuum_mop_quick", "vacuum_mop_deep"}


def test_available_profile_names_default_no_caps():
    """[RP-1] With no capabilities dict, mop profiles are excluded."""
    names = get_available_profile_names()
    assert "vacuum_mop_quick" not in names


# ---------------------------------------------------------------------------
# [RP-3] / [RP-4] get_available_profiles
# ---------------------------------------------------------------------------

def test_available_profiles_no_mop_excludes_mop_profiles():
    """[RP-3] Mop profiles are absent for non-mop device."""
    profiles = get_available_profiles(capabilities=_NO_MOP_CAPS)
    assert "vacuum_mop_quick" not in profiles
    assert "vacuum_mop_deep" not in profiles
    assert "vacuum_quick" in profiles
    assert "vacuum_deep" in profiles


def test_available_profiles_full_caps_includes_mop():
    """[RP-4] Mop profiles are present for mop+water device."""
    profiles = get_available_profiles(capabilities=_FULL_CAPS)
    assert "vacuum_mop_quick" in profiles
    assert "vacuum_mop_deep" in profiles


def test_available_profiles_returns_normalized_dicts():
    """[RP-4] Each returned profile is a normalized dict with all required keys."""
    profiles = get_available_profiles(capabilities=_FULL_CAPS)
    for name, profile in profiles.items():
        assert "clean_mode" in profile, f"{name} missing clean_mode"
        assert "fan_speed" in profile, f"{name} missing fan_speed"
        assert "water_level" in profile, f"{name} missing water_level"


# ---------------------------------------------------------------------------
# [RP-5] / [RP-6] normalize_room_profile
# ---------------------------------------------------------------------------

def test_normalize_room_profile_defaults_on_none():
    """[RP-5] normalize_room_profile with None input returns safe defaults."""
    p = normalize_room_profile(None)
    assert p["clean_mode"] == "vacuum"
    assert p["fan_speed"] == "Max"
    assert p["water_level"] == "Off"
    assert p["clean_passes"] == 1
    assert p["edge_mopping"] is False


def test_normalize_room_profile_preserves_values():
    """[RP-6] normalize_room_profile does not overwrite provided values."""
    p = normalize_room_profile({"clean_mode": "vacuum_mop", "fan_speed": "Strong", "clean_passes": 2})
    assert p["clean_mode"] == "vacuum_mop"
    assert p["fan_speed"] == "Strong"
    assert p["clean_passes"] == 2


def test_normalize_room_profile_empty_dict():
    """[RP-5] Empty dict produces all defaults."""
    p = normalize_room_profile({})
    assert p["clean_intensity"] == "Standard"
    assert p["path_type"] == "wide"
    assert p["mop_required"] is False


def test_apply_room_profile_threads_adapter_catalog_defaults():
    """[RP-18] apply_room_profile_to_config fills fields the profile OMITS from the
    adapter catalog's normalize_defaults, not the in-code Eufy defaults — so a
    non-Eufy (e.g. Roborock) room-profile apply never gets Eufy's "Max"/"Off"
    written in. Regression for the catalog-blind call in apply_room_profile_to_config."""
    catalog = {"normalize_defaults": {"fan_speed": "Balanced", "water_level": "Low"}}
    profile = {"clean_mode": "vacuum"}  # omits fan_speed / water_level
    updated = apply_room_profile_to_config(
        room_config={}, profile_name="custom", profile=profile, catalog=catalog,
    )
    assert updated["fan_speed"] == "Balanced"  # adapter default, NOT Eufy "Max"
    assert updated["water_level"] == "Low"     # adapter default, NOT Eufy "Off"

    # With no catalog it still falls back to the in-code Eufy defaults (unchanged).
    eufy = apply_room_profile_to_config(
        room_config={}, profile_name="custom", profile=profile,
    )
    assert eufy["fan_speed"] == "Max"
    assert eufy["water_level"] == "Off"


# ---------------------------------------------------------------------------
# [RP-7] / [RP-8] / [RP-9] resolve_room_profile_for_room — floor types
# ---------------------------------------------------------------------------

def test_resolve_carpet_sets_water_off():
    """[RP-7] Carpet floor type forces water_level=Off."""
    result = resolve_room_profile_for_room(
        room_config={"profile_name": "vacuum_mop_quick", "floor_type": "carpet_low_pile"}
    )
    assert result["water_level"] == "Off"


def test_resolve_hard_floor_uses_floor_water_default():
    """[RP-8] Hard floor without explicit water_level override gets the floor default."""
    result = resolve_room_profile_for_room(
        room_config={"profile_name": "vacuum_quick", "floor_type": "tile"}
    )
    # tile default is Medium
    assert result["water_level"] == "Medium"


def test_resolve_hard_floor_explicit_water_level_respected():
    """[RP-8] Explicit water_level in room_config is not overridden by floor default."""
    result = resolve_room_profile_for_room(
        room_config={"profile_name": "vacuum_quick", "floor_type": "tile", "water_level": "High"}
    )
    assert result["water_level"] == "High"


def test_resolve_carpet_high_pile_fan_speed():
    """[RP-9] carpet_high_pile overrides fan_speed to 'Standard'."""
    result = resolve_room_profile_for_room(
        room_config={"profile_name": "vacuum_quick", "floor_type": "carpet_high_pile"}
    )
    assert result["fan_speed"] == "Standard"


def test_resolve_carpet_low_pile_fan_speed():
    """[RP-9] carpet_low_pile overrides fan_speed to 'Max'."""
    result = resolve_room_profile_for_room(
        room_config={"profile_name": "vacuum_quick", "floor_type": "carpet_low_pile"}
    )
    assert result["fan_speed"] == "Max"


# ---------------------------------------------------------------------------
# [RP-10] mop mode + Off water → floor default
# ---------------------------------------------------------------------------

def test_resolve_mop_mode_with_off_water_gets_floor_default():
    """[RP-10] vacuum_mop mode with water_level=Off (hard floor) falls back to floor default."""
    result = resolve_room_profile_for_room(
        room_config={"profile_name": "vacuum_mop_quick", "floor_type": "hardwood", "water_level": "Off"}
    )
    # hardwood default is Low
    assert result["water_level"] == "Low"


# ---------------------------------------------------------------------------
# [RP-11] edge_mopping in vacuum mode
# ---------------------------------------------------------------------------

def test_resolve_vacuum_mode_forces_edge_mopping_false():
    """[RP-11] edge_mopping is forced False when clean_mode is vacuum."""
    result = resolve_room_profile_for_room(
        room_config={"profile_name": "vacuum_deep", "floor_type": "tile", "edge_mopping": True}
    )
    assert result["edge_mopping"] is False


def test_resolve_mop_mode_non_carpet_allows_edge_mopping():
    """[RP-11] edge_mopping is preserved for mop mode on non-carpet floors."""
    result = resolve_room_profile_for_room(
        room_config={"profile_name": "vacuum_mop_deep", "floor_type": "tile"}
    )
    assert result["edge_mopping"] is True


# ---------------------------------------------------------------------------
# [RP-12] / [RP-13] / [RP-14] apply_capability_gate
# ---------------------------------------------------------------------------

def _base_mop_settings() -> dict:
    return {
        "clean_mode": "vacuum_mop",
        "fan_speed": "Standard",
        "water_level": "Medium",
        "clean_intensity": "Quick",
        "path_type": "wide",
        "clean_passes": 1,
        "edge_mopping": True,
    }


def test_capability_gate_downgrades_mop_to_vacuum():
    """[RP-12] When supports_mop_features=False, mop mode is downgraded to vacuum."""
    settings = _base_mop_settings()
    result = apply_capability_gate(settings, _NO_MOP_CAPS)
    assert result["clean_mode"] == "vacuum"


def test_capability_gate_sets_water_off_for_vacuum_mode():
    """[RP-13] Water level is always Off in vacuum mode after gating."""
    settings = {**_base_mop_settings(), "clean_mode": "vacuum"}
    result = apply_capability_gate(settings, _NO_MOP_CAPS)
    assert result["water_level"] == "Off"


def test_capability_gate_adds_capability_gated_flag():
    """[RP-14] apply_capability_gate always adds capability_gated=True."""
    settings = _base_mop_settings()
    result = apply_capability_gate(settings, _FULL_CAPS)
    assert result["capability_gated"] is True


def test_capability_gate_does_not_mutate_input():
    """[RP-14] The original settings dict is not modified."""
    settings = _base_mop_settings()
    original_mode = settings["clean_mode"]
    apply_capability_gate(settings, _NO_MOP_CAPS)
    assert settings["clean_mode"] == original_mode


def test_capability_gate_mop_deep_downgrade_uses_deep_intensity():
    """[RP-12] vacuum_mop_deep downgrade sets Deep intensity (distinguishes from quick downgrade)."""
    settings = _base_mop_settings()
    result = apply_capability_gate(settings, _NO_MOP_CAPS, resolved_profile_name="vacuum_mop_deep")
    assert result["clean_mode"] == "vacuum"
    assert result["clean_intensity"] == "Deep"


# ---------------------------------------------------------------------------
# [RP-15] resolve_profile_name_for_constraints
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("profile,floor,expected", [
    ("vacuum_mop_quick", "carpet_low_pile", "vacuum_quick"),
    ("vacuum_mop_deep", "carpet_high_pile", "vacuum_deep"),
    ("vacuum_quick", "carpet_low_pile", "vacuum_quick"),
    ("vacuum_deep", "carpet_low_pile", "vacuum_deep"),
    ("vacuum_mop_quick", "hardwood", "vacuum_mop_quick"),
])
def test_resolve_profile_for_constraints(profile, floor, expected):
    """[RP-15] Carpet floors map mop profiles to vacuum equivalents; others pass through."""
    result = resolve_profile_name_for_constraints(profile_name=profile, floor_type=floor)
    assert result == expected


# ---------------------------------------------------------------------------
# [RP-16] legacy alias resolution
# ---------------------------------------------------------------------------

def test_legacy_alias_vacuum_standard_resolves_to_vacuum_quick():
    """[RP-16] 'vacuum_standard' resolves to 'vacuum_quick' via LEGACY_PROFILE_ALIASES."""
    result = resolve_profile_name_for_constraints(
        profile_name="vacuum_standard", floor_type="hardwood"
    )
    assert result == "vacuum_quick"


def test_legacy_alias_vacuum_mop_standard_resolves_to_vacuum_mop_quick():
    """[RP-16] 'vacuum_mop_standard' resolves to 'vacuum_mop_quick'."""
    result = resolve_profile_name_for_constraints(
        profile_name="vacuum_mop_standard", floor_type="tile"
    )
    assert result == "vacuum_mop_quick"


# ---------------------------------------------------------------------------
# [RP-17] _normalize_floor_type: granite/concrete are canonical (not coerced)
# ---------------------------------------------------------------------------
def test_normalize_floor_type_keeps_granite_and_concrete():
    """[RP-17] granite + concrete are settable (Setup dropdown) and rendered on the
    floor-texture map, so the profile normalizer must NOT coerce them to hardwood.
    Regression for apply_room_profile_to_config's normalize-on-write silently
    downgrading a granite/concrete room to hardwood on any profile apply."""
    assert _normalize_floor_type("granite") == "granite"
    assert _normalize_floor_type("concrete") == "concrete"
    # the rest of the canonical set is unchanged
    for ft in ("hardwood", "laminate", "tile", "marble", "carpet_low_pile", "carpet_high_pile"):
        assert _normalize_floor_type(ft) == ft
    assert _normalize_floor_type("carpet") == "carpet_low_pile"   # legacy migration kept
    assert _normalize_floor_type("bogus") == "hardwood"           # unknown -> default
