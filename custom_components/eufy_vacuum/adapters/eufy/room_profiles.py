"""Eufy's room-profile vocabulary — the WORDS, owned by the brand that speaks them.

Moved out of ``profiles/room_profiles.py`` on 2026-08-07. The framework catalog
had been Eufy's catalog: Eufy was the first brand, so its vocabulary was written
as "the" vocabulary and every other brand inherited it by omission. A brand that
declared no catalog got ``"Max"`` / ``"Boost"`` / ``"Quick"`` — words its device
does not use — and since the card matches option values strictly and
``per_room_live_settings`` filters on ``fan_speed_options``, an unedited room
applied NO SUCTION AT ALL. That is the shipped Roborock incident in dev doc 21.

The split that fixes it: **core owns the profile KEY space, adapters own the
VALUES.** ``vacuum_quick`` / ``vacuum_deep`` / ``vacuum_mop_quick`` /
``vacuum_mop_deep`` are framework identity — both shipped brands use exactly
these keys on purpose, so stored rooms and the profile picker survive a brand
switch — while the settings behind each key are the brand's own words.

Copied from the framework constants so Eufy resolves as it did before, with ONE
deliberate subtraction since: ``path_type``, which was a second name for the axis
``clean_intensity`` already carries (see the note under the profiles below).
``tests/unit/test_profile_catalog.py`` pins the values that remain.

Values only. Nothing here is a framework default for anybody else: a brand
declares its own catalog, or declares it unused (``builtins: {}``). There is no
fallback to inherit.
"""

from __future__ import annotations

from typing import Any


DEFAULT_ROOM_PROFILE_NAME = "vacuum_quick"

BUILT_IN_ROOM_PROFILES: dict[str, dict[str, Any]] = {
    "vacuum_quick": {
        "label": "Vacuum Only Quick",
        "clean_mode": "vacuum",
        "fan_speed": "Standard",
        "water_level": "Off",
        "clean_intensity": "Quick",
        "clean_passes": 1,
        "edge_mopping": False,
        "mop_required": False,
    },
    "vacuum_deep": {
        "label": "Vacuum Only Deep",
        "clean_mode": "vacuum",
        "fan_speed": "Max",
        "water_level": "Off",
        "clean_intensity": "Deep",
        "clean_passes": 2,
        "edge_mopping": False,
        "mop_required": False,
    },
    "vacuum_mop_quick": {
        "label": "Quick",
        "clean_mode": "vacuum_mop",
        "fan_speed": "Standard",
        "water_level": "Medium",
        "clean_intensity": "Quick",
        "clean_passes": 1,
        "edge_mopping": False,
        "mop_required": True,
    },
    "vacuum_mop_deep": {
        "label": "Deep",
        "clean_mode": "vacuum_mop",
        "fan_speed": "Max",
        "water_level": "Medium",
        "clean_intensity": "Deep",
        "clean_passes": 2,
        "edge_mopping": True,
        "mop_required": True,
    },
}

# The retired cleaning-path values "Standard" / "Normal" need no map here. Neither is in
# clean_intensity_options above, so the one-shot store repair in
# rooms/vocabulary_migration.py resets them to this brand's default_profile value —
# "Quick" — by the same rule it applies to every out-of-vocabulary setting on every
# brand. Declaring the real options IS the declaration of what is retired.
#
# path_type is DELIBERATELY ABSENT from every profile above. It was a second name for
# the axis clean_intensity already carries: the built-ins paired Quick/wide and
# Deep/narrow, and core went as far as DERIVING one from the other. Carrying both meant
# the same physical property rode the wire twice, and only invalid stored values
# ("None") kept the device from ever having to choose between them.
#
# Provenance, since the pairing makes it look like a brand leak and it is not: the
# pre-integration YAML system had ONE axis, clean_intensity (Fast/Standard/Deep).
# path_type appears in eae291f, the initial release, three weeks before adapters or a
# second brand existed — so it was invented here as a duplicate, not inherited from
# anyone. The Roborock adapter later declared the field that was already canonical,
# which is why it reads as Roborock's word today. Eufy declares ONE name for this axis:
# clean_intensity. Roborock keeps path_type, the only name that adapter uses for it.


DEFAULT_CUSTOM_ROOM_PROFILE: dict[str, Any] = {
    "label": "User Profile 1",
    "clean_mode": "vacuum",
    "fan_speed": "Max",
    "water_level": "Off",
    "clean_intensity": "Quick",
    "clean_passes": 1,
    "edge_mopping": False,
    "mop_required": False,
}

LEGACY_PROFILE_ALIASES: dict[str, str] = {
    "vacuum_standard": "vacuum_quick",
    "vacuum_mop_standard": "vacuum_mop_quick",
}

# RETIRED IN PRINCIPLE 2026-08-17 — see docs/dev/history/floor-type-cleaning-defaults.md
# The non-carpet rows are a PREFERENCE applied to users who never asked for it: floor_type
# is collected for the map render + the onboarding gate, and nothing ever told the user it
# would also pick a water level. They come out. The CARPET rows STAY — carpet-is-water-off
# is the framework's one guarantee (profiles/room_profiles.py::no_water_value) and is a
# safety property, not a taste. Do not add rows here; add a floor type to the picker only.
FLOOR_TYPE_WATER_DEFAULTS: dict[str, str] = {
    # CARPET ONLY. This is not a table of per-surface preferences any more -- it is
    # this brand's word for "no water", which the framework reads via
    # profiles/room_profiles.py::no_water_value. The hardwood/laminate/tile/marble
    # rows were retired 2026-08-17.
    "carpet_low_pile": "Off",
    "carpet_high_pile": "Off",
}

# Carpet suction defaults keyed by pile height encoded in floor_type.
# KEPT deliberately, ruled 2026-08-17 alongside the water-table retirement next
# door. This looks like the same shape and is not: boosting suction on carpet is
# what most vacuums do in firmware anyway, so it meets an expectation rather than
# imposing a preference. The hard-floor WATER rows went because nobody else held
# that opinion. Do not retire this by applying that reasoning mechanically --
# see docs/dev/history/floor-type-cleaning-defaults.md.
FLOOR_TYPE_FAN_DEFAULTS: dict[str, str] = {
    "carpet_low_pile": "Max",
    "carpet_high_pile": "Standard",
}
