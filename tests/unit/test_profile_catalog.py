"""Adapter-sourced room-profile catalog — the resolve_profile_catalog seam.

The in-code constants stay the framework default; an adapter ``room_profiles`` block
overrides any subset per key. These prove the merge + that resolution honours an
overriding catalog, while a None catalog stays byte-identical to the in-code default.

Coverage targets
----------------
[PC-1] resolve_profile_catalog(None) returns the in-code defaults verbatim.
[PC-2] A partial block overrides only its keys; unspecified keys fall back.
[PC-3] resolve_room_profile_for_room honours a catalog's floor-type water default.
[PC-4] A catalog's default_profile drives the unknown-name fallback.
[PC-5] A catalog with a custom builtins entry resolves that profile.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.profiles.room_profiles import (
    BUILT_IN_ROOM_PROFILES,
    DEFAULT_CUSTOM_ROOM_PROFILE,
    FLOOR_TYPE_WATER_DEFAULTS,
    resolve_profile_catalog,
    resolve_room_profile_for_room,
)


def test_catalog_none_is_in_code_defaults():
    """[PC-1]"""
    cat = resolve_profile_catalog(None)
    assert cat["builtins"] is BUILT_IN_ROOM_PROFILES
    assert cat["custom_template"] is DEFAULT_CUSTOM_ROOM_PROFILE
    assert cat["floor_type_water_defaults"] is FLOOR_TYPE_WATER_DEFAULTS
    assert cat["default_profile"] == "vacuum_quick"


def test_catalog_partial_block_overrides_per_key():
    """[PC-2] only declared keys override; the rest fall back to the in-code defaults."""
    cat = resolve_profile_catalog(
        {"default_profile": "vacuum_deep", "floor_type_water_defaults": {"tile": "High"}}
    )
    assert cat["default_profile"] == "vacuum_deep"
    assert cat["floor_type_water_defaults"] == {"tile": "High"}
    # unspecified → in-code (same object)
    assert cat["builtins"] is BUILT_IN_ROOM_PROFILES


def test_resolution_honours_catalog_floor_water_default():
    """[PC-3] a brand catalog's tile water default flows through resolution; None stays
    byte-identical to the in-code default (Medium for tile)."""
    room = {"profile_name": "vacuum_mop_quick", "floor_type": "tile"}
    assert resolve_room_profile_for_room(room_config=room)["water_level"] == "Medium"
    cat = resolve_profile_catalog({"floor_type_water_defaults": {"tile": "High"}})
    assert resolve_room_profile_for_room(room_config=room, catalog=cat)["water_level"] == "High"


def test_catalog_default_profile_drives_unknown_fallback():
    """[PC-4] an unknown profile name falls back to the catalog's default_profile."""
    room = {"profile_name": "does_not_exist", "floor_type": "hardwood"}
    base = resolve_room_profile_for_room(room_config=room)
    assert base["resolved_profile_name"] == "vacuum_quick"  # in-code default
    cat = resolve_profile_catalog({"default_profile": "vacuum_deep"})
    over = resolve_room_profile_for_room(room_config=room, catalog=cat)
    assert over["resolved_profile_name"] == "vacuum_deep"


def test_catalog_custom_builtins_entry_resolves():
    """[PC-5] a brand can add a built-in profile via the catalog and resolve it."""
    custom = {
        "label": "Turbo",
        "clean_mode": "vacuum",
        "fan_speed": "Turbo",
        "water_level": "Off",
        "clean_intensity": "Deep",
        "path_type": "narrow",
        "clean_passes": 3,
        "edge_mopping": False,
        "mop_required": False,
    }
    builtins = {**BUILT_IN_ROOM_PROFILES, "brand_turbo": custom}
    cat = resolve_profile_catalog({"builtins": builtins})
    resolved = resolve_room_profile_for_room(
        room_config={"profile_name": "brand_turbo", "floor_type": "hardwood"}, catalog=cat
    )
    assert resolved["resolved_profile_name"] == "brand_turbo"
    assert resolved["fan_speed"] == "Turbo"
    assert resolved["clean_passes"] == 3
