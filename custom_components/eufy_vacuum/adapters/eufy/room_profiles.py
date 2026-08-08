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

Copied VERBATIM from the framework constants, byte-identical, so Eufy resolves
exactly as it did before. ``tests/unit/test_profile_catalog.py`` pins that
fidelity.

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
        "path_type": "wide",
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
        "path_type": "narrow",
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
        "path_type": "wide",
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
        "path_type": "narrow",
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


DEFAULT_CUSTOM_ROOM_PROFILE: dict[str, Any] = {
    "label": "User Profile 1",
    "clean_mode": "vacuum",
    "fan_speed": "Max",
    "water_level": "Off",
    "clean_intensity": "Quick",
    "path_type": "wide",
    "clean_passes": 1,
    "edge_mopping": False,
    "mop_required": False,
}

LEGACY_PROFILE_ALIASES: dict[str, str] = {
    "vacuum_standard": "vacuum_quick",
    "vacuum_mop_standard": "vacuum_mop_quick",
}

FLOOR_TYPE_WATER_DEFAULTS: dict[str, str] = {
    "hardwood": "Low",
    "laminate": "Low",
    "tile": "Medium",
    "marble": "Low",
    "carpet_low_pile": "Off",
    "carpet_high_pile": "Off",
}

# Carpet suction defaults keyed by pile height encoded in floor_type.
FLOOR_TYPE_FAN_DEFAULTS: dict[str, str] = {
    "carpet_low_pile": "Max",
    "carpet_high_pile": "Standard",
}
