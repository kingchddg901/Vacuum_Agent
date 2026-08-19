"""Declared room-profile catalogs, for tests that must hold for ANY brand.

A core test that passes only against Eufy proves that Eufy still works, not that the
framework does. Until 2026-08-07 that distinction was invisible: core carried Eufy's
catalog as "the" catalog, so a test asserting ``fan_speed == "Max"`` was simultaneously
testing the framework and pinning one brand's vocabulary into it, and no test could
detect the difference.

Two kinds of catalog live here, and picking the wrong one weakens the test:

**REAL brand catalogs** (``BRAND_BLOCKS``) — sourced from each adapter's own constants
by reference, never copied, so they cannot drift from what the brand actually declares.
Parameterize over these in tests ABOUT resolution and vocabulary. Two brands is the
minimum that can catch a leak; one is indistinguishable from no parameterization.

**SYNTHETIC** — invented words belonging to nobody. Use this in tests about dispatch,
queueing, or planning, which need *a* catalog to function but are not about vocabulary
at all. If such a test names a real brand's word, that word is load-bearing somewhere it
should not be.

Assert RELATIONSHIPS, not literals: that a resolved value equals what the catalog under
test declares, or is a member of that brand's declared options. A literal in a core test
is a brand's word wearing a framework badge, which is the defect this file exists to
prevent.
"""

from __future__ import annotations

from typing import Any

from custom_components.eufy_vacuum.adapters.eufy.room_profiles import (
    BUILT_IN_ROOM_PROFILES as _EUFY_BUILTINS,
    DEFAULT_CUSTOM_ROOM_PROFILE as _EUFY_TEMPLATE,
    FLOOR_TYPE_FAN_DEFAULTS as _EUFY_FAN_DEFAULTS,
    FLOOR_TYPE_WATER_DEFAULTS as _EUFY_WATER_DEFAULTS,
    LEGACY_PROFILE_ALIASES as _EUFY_ALIASES,
)
from custom_components.eufy_vacuum.adapters.roborock.vocabulary import (
    CUSTOM_ROOM_PROFILE as _RB_TEMPLATE,
    FLOOR_TYPE_FAN_DEFAULTS as _RB_FAN_DEFAULTS,
    FLOOR_TYPE_WATER_DEFAULTS as _RB_WATER_DEFAULTS,
    ROOM_PROFILES as _RB_BUILTINS,
)

EUFY_BLOCK: dict[str, Any] = {
    "default_profile": "vacuum_quick",
    "builtins": _EUFY_BUILTINS,
    "custom_template": _EUFY_TEMPLATE,
    "normalize_defaults": _EUFY_TEMPLATE,
    "legacy_aliases": _EUFY_ALIASES,
    "floor_type_water_defaults": _EUFY_WATER_DEFAULTS,
    "floor_type_fan_defaults": _EUFY_FAN_DEFAULTS,
}

ROBOROCK_BLOCK: dict[str, Any] = {
    "default_profile": "vacuum_quick",
    "builtins": _RB_BUILTINS,
    "custom_template": _RB_TEMPLATE,
    "normalize_defaults": _RB_TEMPLATE,
    "legacy_aliases": {},
    "floor_type_water_defaults": _RB_WATER_DEFAULTS,
    "floor_type_fan_defaults": _RB_FAN_DEFAULTS,
}


def _synthetic_profile(**overrides: Any) -> dict[str, Any]:
    record = {
        "label": "Synthetic",
        "clean_mode": "vacuum",
        "fan_speed": "SynthMid",
        "water_level": "SynthDry",
        "clean_intensity": "SynthClose",
        "path_type": "wide",
        "clean_passes": 1,
        "edge_mopping": False,
        "mop_required": False,
    }
    record.update(overrides)
    return record


#: A third brand that exists only here. Its words match no real device, so a core
#: behaviour that depends on recognising a specific string fails against it — which is
#: the point. It declares the same four protected profile KEYS every brand must.
SYNTHETIC_BLOCK: dict[str, Any] = {
    "default_profile": "vacuum_quick",
    "builtins": {
        "vacuum_quick": _synthetic_profile(label="Synth Vacuum Quick"),
        "vacuum_deep": _synthetic_profile(
            label="Synth Vacuum Deep", fan_speed="SynthMax", clean_passes=2,
            clean_intensity="SynthDeep", path_type="narrow",
        ),
        "vacuum_mop_quick": _synthetic_profile(
            label="Synth Mop Quick", clean_mode="vacuum_mop",
            water_level="SynthWet", mop_required=True,
        ),
        "vacuum_mop_deep": _synthetic_profile(
            label="Synth Mop Deep", clean_mode="vacuum_mop", water_level="SynthWet",
            fan_speed="SynthMax", clean_passes=2, clean_intensity="SynthDeep",
            path_type="narrow", mop_required=True,
        ),
    },
    "custom_template": _synthetic_profile(label="Synth Custom"),
    "normalize_defaults": _synthetic_profile(label="Synth Custom"),
    "legacy_aliases": {},
    # CARPET ONLY -- the brand's no-water word, read by _no_water_value(). The
    # hard-floor rows were retired 2026-08-17 in both shipped adapters
    # (docs/dev/history/floor-type-cleaning-defaults.md); the synthetic brand mirrors
    # them, or a retired feature keeps passing its own tests here.
    "floor_type_water_defaults": {
        "carpet_low_pile": "SynthDry",
        "carpet_high_pile": "SynthDry",
    },
    "floor_type_fan_defaults": {
        "carpet_low_pile": "SynthMax",
        "carpet_high_pile": "SynthMax",
    },
}

#: The synthetic brand's declared option lists, matching SYNTHETIC_BLOCK's values.
SYNTHETIC_VOCABULARY: dict[str, Any] = {
    "clean_mode_options": [
        {"value": "vacuum", "label": "Vacuum"},
        {"value": "mop", "label": "Mop"},
        {"value": "vacuum_mop", "label": "Vacuum & Mop"},
    ],
    "fan_speed_options": [
        {"value": "SynthLow", "label": "Synth Low"},
        {"value": "SynthMid", "label": "Synth Mid"},
        {"value": "SynthMax", "label": "Synth Max"},
    ],
    "water_level_options": [
        {"value": "SynthDry", "label": "Synth Dry"},
        {"value": "SynthWet", "label": "Synth Wet"},
    ],
    "clean_intensity_options": [
        {"value": "SynthClose", "label": "Synth Close"},
        {"value": "SynthDeep", "label": "Synth Deep"},
    ],
}

#: A complete adapter config for the synthetic brand — enough to register.
SYNTHETIC_ADAPTER_CONFIG: dict[str, Any] = {
    "adapter_id": "synthetic",
    "source": "code",
    "room_profiles": SYNTHETIC_BLOCK,
    "vocabulary": SYNTHETIC_VOCABULARY,
}


def adapter_config(**overrides: Any) -> dict[str, Any]:
    """A registerable adapter config: synthetic brand + whatever this test needs.

    Test modules routinely register a partial adapter declaring only the block they care
    about — ``entities`` for a lifecycle test, ``dispatch`` for a payload test.
    Registration OVERWRITES, so such a config silently replaced the catalog its fixture
    had declared, and room resolution then had none. That went unnoticed for as long as
    core carried a fallback catalog to supply instead.

    Use this instead of a bare dict wherever the test's code path can reach room
    resolution. Overrides are shallow and replace whole blocks, which is what callers
    want: ``adapter_config(entities={...})`` keeps the profile catalog and swaps the
    entities wholesale.
    """
    config = dict(SYNTHETIC_ADAPTER_CONFIG)
    config.update(overrides)
    return config

#: Every REAL brand this integration ships. Parameterize vocabulary tests over all of
#: them plus the synthetic one; adding a brand adapter should mean adding a row here and
#: nothing else.
BRAND_BLOCKS: dict[str, dict[str, Any]] = {
    "eufy": EUFY_BLOCK,
    "roborock": ROBOROCK_BLOCK,
    "synthetic": SYNTHETIC_BLOCK,
}
