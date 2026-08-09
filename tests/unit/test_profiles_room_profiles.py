"""profiles/room_profiles.py pure functions — proven against EVERY declared brand.

These tests take the ``brand`` fixture, so each one runs once per catalog in
``tests/brand_catalogs.py`` (Eufy, Roborock, and a synthetic brand whose words match no
real device). Every assertion states a RELATIONSHIP — "the resolved value equals what
THIS catalog declares" — never a literal.

That is the whole point. These tests previously asserted ``water_level == "Off"`` and
``fan_speed == "Max"`` against no catalog at all, which passed because core carried
Eufy's vocabulary as the framework default. They were simultaneously testing the resolver
and pinning one brand's words into it, and could not tell the difference. Rewriting them
relationally immediately surfaced three live leaks in ``apply_capability_gate``, which
assigned the literal ``"Off"`` — Eufy's casing, absent from Roborock's declared options
and therefore dropped before dispatch.

A literal reintroduced here would pass for one brand and fail for the other two.

Coverage targets
----------------
[RP-1]  get_available_profile_names returns vacuum-only names without mop support.
[RP-2]  get_available_profile_names returns all 4 with full mop support.
[RP-3]  get_available_profiles excludes mop profiles for a non-mop device.
[RP-4]  get_available_profiles includes mop profiles for a mop+water device.
[RP-5]  normalize_room_profile applies safe defaults for all fields on empty input.
[RP-6]  normalize_room_profile preserves provided values.
[RP-7]  resolve_room_profile_for_room suppresses water on carpet, using the brand's word.
[RP-8]  Q2/RP-024: the resolved profile's own water_level outranks the hard-floor default.
[RP-9]  resolve_room_profile_for_room applies the brand's carpet fan default.
[RP-10] mop mode with no water on a hard floor takes the brand's floor default.
[RP-11] edge_mopping is forced False in vacuum mode and otherwise follows the profile.
[RP-12] apply_capability_gate downgrades mop → vacuum when unsupported.
[RP-12b] …for EVERY clean_mode spelling the card can store, not just the token.
[RP-12c] …and leaves a mop room alone on mop hardware (so 12b can't pass by
        flattening every mode).
[RP-13] apply_capability_gate suppresses water in vacuum mode, using the brand's word.
[RP-13b] …including when the mode is the display label "Vacuum".
[RP-14] apply_capability_gate adds capability_gated=True and does not mutate its input.
[RP-15] carpet maps mop profiles to their vacuum equivalents.
[RP-16] a brand's DECLARED legacy aliases resolve; a brand declaring none is unaffected.
[RP-17] _normalize_floor_type: granite + concrete are canonical (not coerced).
[RP-18] apply_room_profile_to_config fills omitted fields from the catalog's normalize_defaults.
[RP-19] coerce_clean_intensity carries no vocabulary — it trims and coerces, rewrites nothing.
[RP-EDGE-1] no Roborock profile requests a capability its adapter declares absent.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.profiles.room_profiles import (
    _normalize_floor_type,
    apply_capability_gate,
    apply_room_profile_to_config,
    coerce_clean_intensity,
    get_available_profile_names,
    get_available_profiles,
    normalize_room_profile,
    resolve_profile_name_for_constraints,
    resolve_room_profile_for_room,
)

_NO_MOP_CAPS = {"supports_mop_features": False, "supports_water_control": False}
_FULL_CAPS = {"supports_mop_features": True, "supports_water_control": True}


def _profile(brand: dict, name: str) -> dict:
    """The named profile exactly as this brand declares it."""
    return brand["builtins"][name]


def _no_water(brand: dict) -> str:
    """This brand's word for "no water" — its declared carpet water default.

    Carpet is the one surface the framework guarantees dry, so the brand's declaration
    for it IS its no-water word. Mirrors ``room_profiles._no_water_value``; asserting
    against a literal instead is how "Off" survived in core for so long.
    """
    return brand["floor_type_water_defaults"]["carpet_low_pile"]


def test_coerce_clean_intensity_carries_no_vocabulary():
    """[RP-19] coercion only — every value passes through trimmed, none is rewritten.

    This deliberately asserts the OPPOSITE of what it used to. The retired Eufy values
    "Standard"/"Normal" were folded to "Quick" here on every read; that fold is now a
    one-shot store repair driven by the brand's declared clean_intensity_options
    (rooms/vocabulary_migration.py). A rewrite happening here again would mean core had
    re-acquired a brand's vocabulary.

    None → "" is load-bearing, not cosmetic: a brand declaring no intensity axis
    (Roborock omits it from every profile) yields None, and a bare str() would write the
    literal "None" into a room.
    """
    for value in ("Standard", "standard", "Normal", "Quick", "Narrow", "Deep"):
        assert coerce_clean_intensity(value) == value, value
    assert coerce_clean_intensity(" Standard ") == "Standard"
    assert coerce_clean_intensity(None) == ""
    assert coerce_clean_intensity("") == ""


# ---------------------------------------------------------------------------
# [RP-1] / [RP-2] get_available_profile_names — framework KEYS, brand-independent
# ---------------------------------------------------------------------------

def test_available_profile_names_no_mop():
    """[RP-1] Without mop support, only the vacuum-only keys are returned."""
    assert get_available_profile_names(capabilities=_NO_MOP_CAPS) == [
        "vacuum_quick", "vacuum_deep",
    ]


def test_available_profile_names_full_mop():
    """[RP-2] With full mop support, all 4 protected keys are returned."""
    assert set(get_available_profile_names(capabilities=_FULL_CAPS)) == {
        "vacuum_quick", "vacuum_deep", "vacuum_mop_quick", "vacuum_mop_deep",
    }


def test_available_profile_names_default_no_caps():
    """[RP-1] With no capabilities dict, mop profiles are excluded."""
    assert "vacuum_mop_quick" not in get_available_profile_names()


# ---------------------------------------------------------------------------
# [RP-3] / [RP-4] get_available_profiles
# ---------------------------------------------------------------------------

def test_available_profiles_no_mop_excludes_mop_profiles(brand):
    """[RP-3] Mop profiles are absent for a non-mop device, whatever the brand."""
    profiles = get_available_profiles(capabilities=_NO_MOP_CAPS, catalog=brand)
    assert "vacuum_mop_quick" not in profiles
    assert "vacuum_mop_deep" not in profiles
    assert "vacuum_quick" in profiles
    assert "vacuum_deep" in profiles


def test_available_profiles_full_caps_includes_mop(brand):
    """[RP-4] Mop profiles are present for a mop+water device."""
    profiles = get_available_profiles(capabilities=_FULL_CAPS, catalog=brand)
    assert "vacuum_mop_quick" in profiles
    assert "vacuum_mop_deep" in profiles


def test_available_profiles_carry_the_brands_own_values(brand):
    """[RP-4] Each returned profile carries THIS brand's declared values.

    The old form asserted only that the keys existed. That passes even when every
    value is another brand's — which is precisely the failure that shipped.
    """
    profiles = get_available_profiles(capabilities=_FULL_CAPS, catalog=brand)
    for name, profile in profiles.items():
        declared = brand["builtins"].get(name)
        if declared is None:
            continue  # a stored/custom profile, not one the brand declares
        for field in ("clean_mode", "fan_speed", "water_level"):
            if field in declared:
                assert profile[field] == declared[field], f"{name}.{field}"


# ---------------------------------------------------------------------------
# [RP-5] / [RP-6] normalize_room_profile
# ---------------------------------------------------------------------------

def test_normalize_room_profile_defaults_on_none():
    """[RP-5] With NO catalog, display-axis fields are "" — "nobody said".

    Not Eufy's "Max"/"Off". Framework canonicals (clean_mode, clean_passes) are
    unaffected because core legitimately owns those.
    """
    p = normalize_room_profile(None)
    assert p["clean_mode"] == "vacuum"
    assert p["fan_speed"] == ""
    assert p["water_level"] == ""
    assert p["clean_passes"] == 1
    assert p["edge_mopping"] is False


def test_normalize_room_profile_preserves_values():
    """[RP-6] normalize_room_profile does not overwrite provided values."""
    p = normalize_room_profile({"clean_mode": "vacuum_mop", "fan_speed": "Strong", "clean_passes": 2})
    assert p["clean_mode"] == "vacuum_mop"
    assert p["fan_speed"] == "Strong"
    assert p["clean_passes"] == 2


def test_normalize_room_profile_empty_dict():
    """[RP-5] Empty dict produces canonical defaults; the vocabulary axes stay unsaid.

    path_type joins clean_intensity here. It used to default to the literal "wide" with
    no catalog present, which made every caller — including brands with no path axis —
    look like it had declared one.
    """
    p = normalize_room_profile({})
    assert p["clean_intensity"] == ""
    assert p["path_type"] == ""
    assert p["mop_required"] is False


def test_apply_room_profile_threads_adapter_catalog_defaults():
    """[RP-18] Omitted fields come from the catalog's normalize_defaults.

    Uses an invented catalog on purpose — the values are nobody's, so a leak cannot
    coincidentally satisfy this.
    """
    catalog = {"normalize_defaults": {"fan_speed": "Balanced", "water_level": "Low"}}
    profile = {"clean_mode": "vacuum"}  # omits fan_speed / water_level
    updated = apply_room_profile_to_config(
        room_config={}, profile_name="custom", profile=profile, catalog=catalog,
    )
    assert updated["fan_speed"] == "Balanced"
    assert updated["water_level"] == "Low"

    # With genuinely no catalog: "" ("nobody said"), never an in-code brand default.
    no_catalog = apply_room_profile_to_config(
        room_config={}, profile_name="custom", profile=profile,
    )
    assert no_catalog["fan_speed"] == ""
    assert no_catalog["water_level"] == ""


# ---------------------------------------------------------------------------
# [RP-7] / [RP-8] / [RP-9] resolve_room_profile_for_room — floor types
# ---------------------------------------------------------------------------

def test_resolve_carpet_suppresses_water(brand):
    """[RP-7] Carpet suppresses water, using the word THIS brand declares for it."""
    result = resolve_room_profile_for_room(
        room_config={"profile_name": "vacuum_mop_quick", "floor_type": "carpet_low_pile"},
        catalog=brand,
    )
    assert result["water_level"] == _no_water(brand)


def test_resolve_hard_floor_profile_water_level_wins_over_floor_default(brand):
    """[RP-8] Q2/RP-024: the SELECTED PROFILE's own water_level outranks the hard
    floor's default — the profile's declared value survives on tile rather than being
    silently overwritten by tile's floor default. Every declared profile carries a
    water_level, so the hard-floor default fires only when the room AND the profile
    both genuinely omit it."""
    result = resolve_room_profile_for_room(
        room_config={"profile_name": "vacuum_quick", "floor_type": "tile"}, catalog=brand,
    )
    assert result["water_level"] == _profile(brand, "vacuum_quick")["water_level"]


def test_resolve_hard_floor_explicit_water_level_respected(brand):
    """[RP-8] An explicit room water_level is not overridden by the floor default."""
    explicit = _profile(brand, "vacuum_mop_quick")["water_level"]
    result = resolve_room_profile_for_room(
        room_config={
            "profile_name": "vacuum_quick", "floor_type": "tile", "water_level": explicit,
        },
        catalog=brand,
    )
    assert result["water_level"] == explicit


@pytest.mark.parametrize("floor", ["carpet_high_pile", "carpet_low_pile"])
def test_resolve_carpet_fan_speed_comes_from_the_catalog(brand, floor):
    """[RP-9] Carpet overrides fan_speed to the brand's declared carpet default."""
    result = resolve_room_profile_for_room(
        room_config={"profile_name": "vacuum_quick", "floor_type": floor}, catalog=brand,
    )
    assert result["fan_speed"] == brand["floor_type_fan_defaults"][floor]


# ---------------------------------------------------------------------------
# [RP-10] mop mode + no water → floor default
# ---------------------------------------------------------------------------

def test_resolve_mop_mode_with_no_water_gets_floor_default(brand):
    """[RP-10] Mop mode with water suppressed on a hard floor takes the floor default.

    The guard compares case-insensitively against "off" because that is a FRAMEWORK
    concept (the absence of water) and brands differ only in casing — a strict
    == "Off" meant this never fired on Roborock, whose word is "off", so a mop room
    stayed dry-mopping instead of being corrected.
    """
    result = resolve_room_profile_for_room(
        room_config={
            "profile_name": "vacuum_mop_quick",
            "floor_type": "hardwood",
            "water_level": _no_water(brand),
        },
        catalog=brand,
    )
    assert result["water_level"] == brand["floor_type_water_defaults"]["hardwood"]


# ---------------------------------------------------------------------------
# [RP-11] edge_mopping
# ---------------------------------------------------------------------------

def test_resolve_vacuum_mode_forces_edge_mopping_false(brand):
    """[RP-11] edge_mopping is forced False in vacuum mode — a framework invariant."""
    result = resolve_room_profile_for_room(
        room_config={"profile_name": "vacuum_deep", "floor_type": "tile", "edge_mopping": True},
        catalog=brand,
    )
    assert result["edge_mopping"] is False


def test_resolve_mop_mode_non_carpet_follows_the_profile(brand):
    """[RP-11] Off carpet, mop mode carries through whatever the PROFILE declares.

    Asserted as agreement rather than True: Roborock declares edge_mopping False on
    every profile because its adapter declares the capability absent, so a hardcoded
    True here would fail for a brand that is behaving correctly.
    """
    result = resolve_room_profile_for_room(
        room_config={"profile_name": "vacuum_mop_deep", "floor_type": "tile"}, catalog=brand,
    )
    assert result["edge_mopping"] == _profile(brand, "vacuum_mop_deep")["edge_mopping"]


# ---------------------------------------------------------------------------
# [RP-12] / [RP-13] / [RP-14] apply_capability_gate
# ---------------------------------------------------------------------------

def _mop_settings(brand: dict) -> dict:
    """Settings in THIS brand's vocabulary, as resolution would have produced them."""
    declared = _profile(brand, "vacuum_mop_quick")
    return {
        "clean_mode": "vacuum_mop",
        "fan_speed": declared["fan_speed"],
        "water_level": declared["water_level"],
        "clean_intensity": declared.get("clean_intensity", ""),
        "path_type": declared.get("path_type", "wide"),
        "clean_passes": 1,
        "edge_mopping": True,
    }


def test_capability_gate_downgrades_mop_to_vacuum(brand):
    """[RP-12] With supports_mop_features False, mop mode downgrades to vacuum."""
    result = apply_capability_gate(_mop_settings(brand), _NO_MOP_CAPS, catalog=brand)
    assert result["clean_mode"] == "vacuum"


def test_capability_gate_suppresses_water_using_the_brands_word(brand):
    """[RP-13] Vacuum mode suppresses water — with the brand's word, not a literal.

    This is the regression for the leak this rewrite found: the gate assigned the
    literal "Off" at three sites. Roborock's word is "off", which is absent from its
    declared water_level_options, so dispatch filtered the setting out and mop
    intensity was never applied on a mop-settable model.
    """
    settings = {**_mop_settings(brand), "clean_mode": "vacuum"}
    result = apply_capability_gate(settings, _NO_MOP_CAPS, catalog=brand)
    assert result["water_level"] == _no_water(brand)


# The spellings the CARD can actually put in the store. _canonicalCleanModeDisplay
# writes a human label ("Vacuum and mop"), not the token, and older records carry
# the other phrasings. Every gate test above this point uses "vacuum_mop" — the one
# spelling that never broke — which is why the suite stayed green through the whole
# of issue #48 and through its dispatch-side sibling.
_MOP_SPELLINGS = ["vacuum_mop", "Vacuum and mop", "vacuum & mop", "VACUUM_MOP", "mop", "Mop"]


@pytest.mark.parametrize("spelling", _MOP_SPELLINGS)
def test_capability_gate_downgrades_every_mop_spelling(brand, spelling):
    """[RP-12b] The downgrade fires for every spelling the card can store.

    ISSUE #48, dispatch side. The predicate was an exact, case-sensitive membership
    test run against a value the gate's own docstring calls a display/storage value
    and does not lowercase. "Vacuum and mop" and "Mop" walked straight past it, so a
    device with no mop hardware was handed a mop payload.

    Parameterised rather than one case per spelling so a future narrowing of the
    predicate cannot pass by satisfying the canonical token alone.
    """
    settings = {**_mop_settings(brand), "clean_mode": spelling}
    result = apply_capability_gate(settings, _NO_MOP_CAPS, catalog=brand)
    assert result["clean_mode"] == "vacuum"
    # The downgrade is not just the label: mop-only settings must go with it.
    assert result["edge_mopping"] is False
    assert result["water_level"] == _no_water(brand)


# _FULL_CAPS does NOT declare supports_edge_mopping, and the gate defaults that to
# False. Asserting "edge is off" under those caps therefore proves nothing — the
# capability clause cleared it before the mode clause was ever consulted. Both tests
# below need edge support DECLARED so the clearing is attributable to the thing they
# name.
_FULL_CAPS_EDGE = {**_FULL_CAPS, "supports_edge_mopping": True}


@pytest.mark.parametrize("spelling", ["vacuum", "Vacuum", "VACUUM"])
def test_capability_gate_clears_water_and_edge_for_display_vacuum(brand, spelling):
    """[RP-13b] A vacuum-only room clears water and edge however it is spelled.

    The mirror of [RP-12b] and the same root: `clean_mode == "vacuum"` never matched
    the display label "Vacuum", so a vacuum-only room dispatched still carrying a
    water level and an edge-mopping flag on a fully mop-capable device — where
    nothing downstream would refuse it.

    Runs on edge-CAPABLE caps on purpose: under _FULL_CAPS the assertion would hold
    for a device that simply has no edge hardware, and would pass with the mode
    clause deleted entirely.
    """
    settings = {**_mop_settings(brand), "clean_mode": spelling}
    result = apply_capability_gate(settings, _FULL_CAPS_EDGE, catalog=brand)
    assert result["edge_mopping"] is False
    assert result["water_level"] == _no_water(brand)


def test_capability_gate_leaves_mop_alone_on_a_mop_device(brand):
    """[RP-12c] The guard against fixing [RP-12b] by downgrading everything.

    A test that only asserts "mop became vacuum" is satisfied by a gate that
    flattens every mode, so pin the opposite direction too: given mop hardware, a
    display-label mop room keeps its mop settings.
    """
    settings = {**_mop_settings(brand), "clean_mode": "Vacuum and mop"}
    result = apply_capability_gate(settings, _FULL_CAPS_EDGE, catalog=brand)
    assert result["clean_mode"] == "Vacuum and mop"
    assert result["edge_mopping"] is True
    assert result["water_level"] == _mop_settings(brand)["water_level"]


def test_capability_gate_adds_capability_gated_flag(brand):
    """[RP-14] apply_capability_gate always adds capability_gated=True."""
    result = apply_capability_gate(_mop_settings(brand), _FULL_CAPS, catalog=brand)
    assert result["capability_gated"] is True


def test_capability_gate_does_not_mutate_input(brand):
    """[RP-14] The original settings dict is not modified."""
    settings = _mop_settings(brand)
    original = dict(settings)
    apply_capability_gate(settings, _NO_MOP_CAPS, catalog=brand)
    assert settings == original


def test_capability_gate_mop_deep_downgrade_uses_the_deep_profile(brand):
    """[RP-12] A vacuum_mop_deep downgrade adopts the brand's vacuum_deep values.

    Distinguishes the deep downgrade from the quick one without naming any brand's
    intensity word — Roborock declares no intensity axis at all, so a literal "Deep"
    here would assert a field that brand deliberately does not have.
    """
    # supports_path_control ON so the gate does not drop the path axis before the
    # downgrade's choice can be observed on a brand that has one.
    caps = {**_NO_MOP_CAPS, "supports_path_control": True}
    result = apply_capability_gate(
        _mop_settings(brand), caps,
        resolved_profile_name="vacuum_mop_deep", catalog=brand,
    )
    deep = _profile(brand, "vacuum_deep")
    assert result["clean_mode"] == "vacuum"
    # Relational per axis, because the two brands declare DIFFERENT ones: Eufy has no
    # path_type and Roborock no clean_intensity, they being one property under two
    # names. A downgrade must carry through whatever this brand declares and must not
    # grow an axis it does not have — asserting a literal here would demand exactly
    # that of whichever brand lacks it.
    for axis in ("path_type", "clean_intensity"):
        if axis in deep:
            assert result.get(axis) == deep[axis], axis
        else:
            assert not result.get(axis), axis


# ---------------------------------------------------------------------------
# [RP-15] resolve_profile_name_for_constraints — framework KEYS
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("profile,floor,expected", [
    ("vacuum_mop_quick", "carpet_low_pile", "vacuum_quick"),
    ("vacuum_mop_deep", "carpet_high_pile", "vacuum_deep"),
    ("vacuum_quick", "carpet_low_pile", "vacuum_quick"),
    ("vacuum_deep", "carpet_low_pile", "vacuum_deep"),
    ("vacuum_mop_quick", "hardwood", "vacuum_mop_quick"),
])
def test_resolve_profile_for_constraints(brand, profile, floor, expected):
    """[RP-15] Carpet maps mop profiles to their vacuum equivalents.

    These are protected profile KEYS, which core owns and every brand declares, so the
    expected values are legitimately literal here.
    """
    assert resolve_profile_name_for_constraints(
        profile_name=profile, floor_type=floor, catalog=brand,
    ) == expected


# ---------------------------------------------------------------------------
# [RP-16] legacy aliases — per brand, including brands that declare none
# ---------------------------------------------------------------------------

def test_declared_legacy_aliases_resolve(brand):
    """[RP-16] Each alias THIS brand declares resolves to its target.

    A brand declaring ``legacy_aliases: {}`` has none to resolve and the loop is empty —
    which is the correct assertion for it, not a skipped test. Eufy declares
    ``vacuum_standard`` → ``vacuum_quick``; Roborock declares none, and asserting Eufy's
    aliases against it would be asserting one brand's history as framework behaviour.
    """
    aliases = brand["legacy_aliases"]
    for old_name, target in aliases.items():
        assert resolve_profile_name_for_constraints(
            profile_name=old_name, floor_type="hardwood", catalog=brand,
        ) == target, old_name

    unknown = "definitely_not_a_declared_alias"
    assert resolve_profile_name_for_constraints(
        profile_name=unknown, floor_type="hardwood", catalog=brand,
    ) == unknown


# ---------------------------------------------------------------------------
# [RP-17] _normalize_floor_type — framework-owned, brand-independent
# ---------------------------------------------------------------------------

def test_normalize_floor_type_keeps_granite_and_concrete():
    """[RP-17] granite + concrete are settable (Setup dropdown) and rendered on the
    floor-texture map, so the profile normalizer must NOT coerce them to hardwood.
    Regression for apply_room_profile_to_config's normalize-on-write silently
    downgrading a granite/concrete room to hardwood on any profile apply."""
    assert _normalize_floor_type("granite") == "granite"
    assert _normalize_floor_type("concrete") == "concrete"
    for ft in ("hardwood", "laminate", "tile", "marble", "carpet_low_pile", "carpet_high_pile"):
        assert _normalize_floor_type(ft) == ft
    assert _normalize_floor_type("carpet") == "carpet_low_pile"   # legacy migration kept
    assert _normalize_floor_type("bogus") == "hardwood"           # unknown -> default


def test_roborock_profiles_never_request_an_undeclared_capability():
    """[RP-EDGE-1] no Roborock room profile may request edge_mopping while the
    adapter declares supports_edge_mopping False.

    vacuum_mop_deep used to be the only one of the five profiles in that file
    asking for it, against a brand-wide False in adapter.py (:179 and :610) —
    the adapter contradicting itself, requesting a capability it declares absent.

    Pins the AGREEMENT, not the literal: re-declaring the capability per model
    (the eventual fix for a Roborock that CAN edge mop) makes the profile legal
    again automatically, instead of tripping a test that hard-coded False.

    Deliberately NOT asserted: that the card hides the control. Gating the UI on
    supports_edge_mopping would hide it on EVERY Roborock, including models that
    can do it — the flag is a hardcoded brand-wide literal with no model gating,
    unlike the Eufy adapter's `model_family in {...}` per-model checks.
    """
    import re
    from pathlib import Path

    from custom_components.eufy_vacuum.adapters.roborock.vocabulary import ROOM_PROFILES

    adapter_src = (
        Path(__file__).resolve().parents[2]
        / "custom_components" / "eufy_vacuum" / "adapters" / "roborock" / "adapter.py"
    ).read_text(encoding="utf-8")

    declarations = re.findall(r'"supports_edge_mopping":\s*(True|False)', adapter_src)
    assert declarations, "the adapter no longer declares supports_edge_mopping at all"

    requesting = sorted(
        name for name, cfg in ROOM_PROFILES.items()
        if isinstance(cfg, dict) and cfg.get("edge_mopping") is True
    )

    if all(value == "False" for value in declarations):
        assert requesting == [], (
            "these profiles request edge_mopping while every adapter declaration "
            f"says it is absent: {requesting}"
        )
