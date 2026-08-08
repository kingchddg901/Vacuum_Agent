"""Adapter-sourced room-profile catalog — the resolve_profile_catalog seam.

There is NO framework default catalog. An adapter's ``room_profiles`` block is the
only source of profile vocabulary; an undeclared key resolves EMPTY rather than to
whichever brand happened to arrive first. These prove that emptiness, that declared
keys are carried verbatim, and that resolution runs entirely off the supplied
catalog.

Every catalog in this module is SYNTHETIC. That is the point: if a core test needed
a real brand's words to pass, core would still own them.

Coverage targets
----------------
[PC-1] resolve_profile_catalog(None) yields an empty vocabulary, not a brand's.
[PC-2] A partial block carries its own keys; undeclared keys stay EMPTY.
[PC-3] resolve_room_profile_for_room honours a catalog's floor-type water default.
[PC-4] A catalog's default_profile drives the unknown-name fallback.
[PC-5] A catalog's builtins entry resolves.
[PC-6] RP-025/RF-18 clause (ii): a declared-empty value is carried, and an explicit
       None is treated as absent.
"""

from __future__ import annotations

from typing import Any

from custom_components.eufy_vacuum.profiles.room_profiles import (
    DEFAULT_ROOM_PROFILE_NAME,
    resolve_profile_catalog,
    resolve_room_profile_for_room,
)

# The seven keys resolve_profile_catalog answers for. Six carry vocabulary and
# resolve empty; default_profile names WHICH profile a new room starts on, which
# is a framework concern rather than a brand word.
VOCABULARY_KEYS = (
    "builtins",
    "custom_template",
    "legacy_aliases",
    "floor_type_water_defaults",
    "floor_type_fan_defaults",
    "normalize_defaults",
)


def _profile(**overrides: Any) -> dict[str, Any]:
    """A complete synthetic ProfileRecord — invented words, no brand's."""
    record = {
        "label": "Synthetic",
        "clean_mode": "vacuum",
        "fan_speed": "SynthMid",
        "water_level": "SynthWet",
        "clean_intensity": "SynthClose",
        "path_type": "narrow",
        "clean_passes": 1,
        "edge_mopping": False,
        "mop_required": False,
    }
    record.update(overrides)
    return record


def _catalog(**overrides: Any) -> dict[str, Any]:
    """A populated synthetic catalog, standing in for a brand that declared one."""
    block = {
        "builtins": {
            "synth_light": _profile(label="Synth Light", fan_speed="SynthLow"),
            "synth_heavy": _profile(label="Synth Heavy", fan_speed="SynthMax", clean_passes=2),
            "synth_wet": _profile(label="Synth Wet", clean_mode="mop", mop_required=True),
        },
        "default_profile": "synth_light",
        # Carpet's entry IS this brand's no-water word — core reads it rather than
        # assigning a literal, so a catalog that declares none yields "".
        "floor_type_water_defaults": {"carpet_low_pile": "SynthDry"},
    }
    block.update(overrides)
    return resolve_profile_catalog(block)


def test_catalog_none_is_empty_not_a_brands():
    """[PC-1] no adapter block ⇒ no vocabulary. Core holds nobody's words.

    The regression this pins is not cosmetic: when this returned Eufy's catalog,
    a brand that declared nothing inherited fan speeds its own options never
    contained, per_room_live_settings filtered them out, and an unedited room
    applied no suction at all.
    """
    cat = resolve_profile_catalog(None)
    for key in VOCABULARY_KEYS:
        assert cat[key] == {}, f"{key} resolved non-empty without an adapter block"
    assert cat["default_profile"] == DEFAULT_ROOM_PROFILE_NAME


def test_catalog_partial_block_leaves_undeclared_keys_empty():
    """[PC-2] declared keys are carried; the rest do NOT fall back to anything."""
    cat = resolve_profile_catalog(
        {"default_profile": "synth_heavy", "floor_type_water_defaults": {"tile": "SynthWet"}}
    )
    assert cat["default_profile"] == "synth_heavy"
    assert cat["floor_type_water_defaults"] == {"tile": "SynthWet"}
    assert cat["builtins"] == {}
    assert cat["legacy_aliases"] == {}


def test_resolution_honours_catalog_floor_water_default():
    """[PC-3] a catalog's carpet water default flows through resolution.

    Q2/RP-024: hard-floor water defaults only fire when NEITHER the room NOR the
    resolved profile supplies water_level — every built-in/normalized profile
    always has one, so a hard floor can no longer demonstrate this; the carpet
    safety clamp is unconditional regardless of profile, so it's the catalog
    plumbing that still exercises floor_type_water_defaults.
    """
    room = {"profile_name": "synth_wet", "floor_type": "carpet_low_pile"}
    base = resolve_room_profile_for_room(room_config=room, catalog=_catalog())
    assert base["water_level"] == "SynthDry"  # the catalog's own no-water word
    over = _catalog(floor_type_water_defaults={"carpet_low_pile": "SynthHigh"})
    assert resolve_room_profile_for_room(room_config=room, catalog=over)["water_level"] == "SynthHigh"
    # A catalog declaring no carpet default gets "" — core has no word of its own to
    # substitute. This is the assertion that would have failed before the fix: the
    # carpet clamp used to assign the literal "Off", which is Eufy's casing.
    bare = _catalog(floor_type_water_defaults={})
    assert resolve_room_profile_for_room(room_config=room, catalog=bare)["water_level"] == ""


def test_catalog_default_profile_drives_unknown_fallback():
    """[PC-4] an unknown profile name falls back to the catalog's default_profile."""
    room = {"profile_name": "does_not_exist", "floor_type": "hardwood"}
    base = resolve_room_profile_for_room(room_config=room, catalog=_catalog())
    assert base["resolved_profile_name"] == "synth_light"
    over = _catalog(default_profile="synth_heavy")
    assert resolve_room_profile_for_room(room_config=room, catalog=over)["resolved_profile_name"] == (
        "synth_heavy"
    )


def test_catalog_builtins_entry_resolves():
    """[PC-5] a brand's declared built-in resolves, values intact."""
    resolved = resolve_room_profile_for_room(
        room_config={"profile_name": "synth_heavy", "floor_type": "hardwood"}, catalog=_catalog()
    )
    assert resolved["resolved_profile_name"] == "synth_heavy"
    assert resolved["fan_speed"] == "SynthMax"
    assert resolved["clean_passes"] == 2


def test_catalog_declared_empty_is_carried():
    """[PC-6] RP-025/RF-18 clause (ii): builtins={} is carried as {}.

    Resolution treats declared-empty and absent identically — this function
    resolves, it does not judge. The distinction is made where it is actionable:
    registry validation reports an ABSENT key as an incomplete declaration while
    accepting an explicit {}. See the adapter-declaration tests for that half.
    """
    assert resolve_profile_catalog({"builtins": {}})["builtins"] == {}
    assert resolve_profile_catalog({"default_profile": ""})["default_profile"] == ""


def test_catalog_explicit_none_is_treated_as_absent():
    """[PC-6c] an explicit None is absent — there is no "declared None" for these
    dict/str-typed fields — and absent now resolves EMPTY, not to a brand."""
    cat = resolve_profile_catalog({"builtins": None, "default_profile": None})
    assert cat["builtins"] == {}
    assert cat["default_profile"] == DEFAULT_ROOM_PROFILE_NAME
