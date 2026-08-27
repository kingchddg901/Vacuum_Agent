"""Dreame vocabulary — DATA ONLY, deliberately not wired.

Sibling of ``dreame_upkeep_guides.py`` and gated the same way: see the package
docstring in ``__init__.py``. There is no ``BRAND_REGISTRARS`` row for Dreame and
no ``adapter.py``; nothing here is reachable at runtime. It ships inert.

⚠ EVERY VALUE IN THIS FILE WAS READ OFF A LIVE DEVICE, NOT A MANUAL.
Captured 2026-08-26 from ``vacuum.robin`` (RLH-class, unique_id
``70:C9:32:8C:1B:61_dreame_vacuum``) via the HA entity registry, running
Tasshack ``dreame_vacuum`` with the #1707 map-decode patch applied locally.
The user manuals do NOT carry these enums — the Aqua10 manual defers to
"Cleaning Mode settings in the app" and prints only three mode names. Do not
"improve" this file from a PDF; re-capture from a device.

⚠ THE PER-ROOM LISTS ARE NOT THE GLOBAL LISTS. Two controls differ, and the
global spelling is the wrong one for room profiles:

    cleaning_mode   global: sweeping / mopping / sweeping_and_mopping /
                            mopping_after_sweeping          (FOUR)
                    room:   sweeping / mopping / sweeping_and_mopping (THREE)

    cleaning_route  global: quick / standard
                    room:   standard / intensive / deep

Only the ROOM lists appear below. A profile built from the global vocabulary
would put ``mopping_after_sweeping`` or ``quick`` on the wire and the dispatch
``options_key`` filter would drop it — silently, the way Roborock's capital-O
"Off" was dropped (``profiles/room_profiles.py::no_water_value``).

⚠ AND THE VACUUM ENTITY DISAGREES WITH THE SELECT. ``vacuum.robin`` advertises
``fan_speed_list = ['Silent', 'Standard', 'Strong', 'Turbo']`` while
``select.robin_room_N_suction_level`` takes ``['quiet', 'standard', 'strong',
'turbo']``. Level 1 is a DIFFERENT WORD, not a casing variant. FAN_SPEED_OPTIONS
below follows the select, because the select is what a per-room write targets.
"""

from __future__ import annotations


# --- per-room option vocabularies -------------------------------------------
#
# The schema (``adapters/config_schema.py``) declares exactly five ``*_options``
# keys and REJECTS undeclared ones: clean_mode / fan_speed / water_level /
# clean_intensity / path_type. Only the four this brand actually exposes are
# declared here.

#: ``select.robin_room_N_suction_level``. See the vacuum-entity warning above:
#: the first level is ``quiet`` here and ``Silent`` on the vacuum entity.
FAN_SPEED_OPTIONS: list[dict] = [
    {"value": "quiet", "label": "Quiet"},
    {"value": "standard", "label": "Standard"},
    {"value": "strong", "label": "Strong"},
    {"value": "turbo", "label": "Turbo"},
]

#: ``select.robin_room_N_mop_pad_humidity``.
#:
#: ⚠ THERE IS NO "OFF". This brand cannot express no-water on the water axis at
#: all: the coarse select is three wet states, and the fine control
#: (``number.robin_room_N_wetness_level``) is an integer scale whose MINIMUM IS 1,
#: not 0. Both Eufy ("Off") and Roborock ("off") declare a no-water word; Dreame
#: has none to declare. That is why FLOOR_TYPE_WATER_DEFAULTS below is empty —
#: see the long note there before adding a row.
WATER_LEVEL_OPTIONS: list[dict] = [
    {"value": "slightly_dry", "label": "Slightly Dry"},
    {"value": "moist", "label": "Moist"},
    {"value": "wet", "label": "Wet"},
]

#: CANONICAL framework values, not device words — the same three Roborock
#: declares. ``profiles/room_profiles.py::canonical_clean_mode`` resolves this
#: axis and ``is_mop_clean_mode`` judges it; an unrecognised brand word answers
#: False there, which would silently disable the carpet downgrade. So the
#: profiles below store canonical tokens and CLEAN_MODE_VALUE_MAP translates at
#: dispatch.
CLEAN_MODE_OPTIONS: list[dict] = [
    {"value": "vacuum", "label": "Vacuum"},
    {"value": "mop", "label": "Mop"},
    {"value": "vacuum_mop", "label": "Vacuum & Mop"},
]

#: canonical -> ``select.robin_room_N_cleaning_mode``. Unlike Roborock — where
#: clean_mode is framework-logical and never reaches the wire — Dreame has a REAL
#: per-room device select, so this map is load-bearing rather than decorative.
CLEAN_MODE_VALUE_MAP: dict[str, str] = {
    "vacuum": "sweeping",
    "mop": "mopping",
    "vacuum_mop": "sweeping_and_mopping",
}

#: ``select.robin_room_N_cleaning_route``.
#:
#: Declared as clean_intensity and NOT as path_type. The schema is explicit that
#: the two are "two names for the same pass-density axis" and that a brand
#: declares exactly one, never both. Roborock's axis is geometry (wide/narrow);
#: this one is density (standard/intensive/deep) and shares Eufy's three-level
#: shape and its "deep" literal, so it belongs in the intensity slot despite the
#: device calling the select a "route".
CLEAN_INTENSITY_OPTIONS: list[dict] = [
    {"value": "standard", "label": "Standard"},
    {"value": "intensive", "label": "Intensive"},
    {"value": "deep", "label": "Deep"},
]

#: ``select.robin_room_N_cleaning_times`` takes "1x"/"2x"/"3x" while the
#: framework's ``clean_passes`` is an int. Translate at dispatch; do not store
#: the suffixed string in a profile.
CLEAN_PASSES_VALUE_MAP: dict[int, str] = {1: "1x", 2: "2x", 3: "3x"}


# --- room profiles ----------------------------------------------------------
#
# Same profile KEYS as the framework catalog so stored rooms and the profile
# picker keep working; only the VALUES are Dreame's. This is the rule the
# Roborock port had to learn the hard way — omitting the block inherited EUFY's
# catalog, so rooms were created with another brand's words and applied nothing
# (see adapters/roborock/adapter.py above its own room_profiles block).
#
# clean_mode is canonical (see CLEAN_MODE_OPTIONS); fan_speed, water_level and
# clean_intensity are this brand's own words.

ROOM_PROFILES: dict[str, dict] = {
    "vacuum_quick": {
        "label": "Vacuum Only Quick",
        "clean_mode": "vacuum",
        "fan_speed": "standard",
        "water_level": "",
        "clean_intensity": "standard",
        "clean_passes": 1,
        "edge_mopping": False,
        "mop_required": False,
    },
    "vacuum_deep": {
        "label": "Vacuum Only Deep",
        "clean_mode": "vacuum",
        "fan_speed": "turbo",
        "water_level": "",
        "clean_intensity": "deep",
        "clean_passes": 2,
        "edge_mopping": False,
        "mop_required": False,
    },
    "vacuum_mop_quick": {
        "label": "Quick",
        "clean_mode": "vacuum_mop",
        "fan_speed": "standard",
        "water_level": "moist",
        "clean_intensity": "standard",
        "clean_passes": 1,
        "edge_mopping": False,
        "mop_required": True,
    },
    "vacuum_mop_deep": {
        "label": "Deep",
        "clean_mode": "vacuum_mop",
        "fan_speed": "turbo",
        "water_level": "wet",
        "clean_intensity": "deep",
        "clean_passes": 2,
        # Declared False to match the brand-wide position, NOT because every
        # Dreame lacks the hardware. Follow the Roborock precedent recorded at
        # adapters/roborock/vocabulary.py: an edge/lift capability is a PER-MODEL
        # fact, and freezing it at brand level then gating the card on it hides
        # the control on every model including those that have it. Add a real
        # per-model declaration before turning this on anywhere.
        "edge_mopping": False,
        "mop_required": True,
    },
}

#: The user-editable slot. Vacuum-only and dry, matching both siblings.
CUSTOM_ROOM_PROFILE: dict = {
    "label": "User Profile 1",
    "clean_mode": "vacuum",
    "fan_speed": "standard",
    "water_level": "",
    "clean_intensity": "standard",
    "clean_passes": 1,
    "edge_mopping": False,
    "mop_required": False,
}


# --- floor-type defaults ----------------------------------------------------

#: ⚠ DELIBERATELY EMPTY, AND THIS IS NOT AN OMISSION. Read this before adding a
#: row — the obvious repair is wrong twice over.
#:
#: ``profiles/room_profiles.py::no_water_value`` reads the carpet entry here as
#: "this brand's word for no water". Dreame HAS NO SUCH WORD (see
#: WATER_LEVEL_OPTIONS: three wet states, and a wetness scale whose minimum is 1).
#: Inventing one — "off", "none", 0 — puts a value on the wire that is not in the
#: brand's own option list, and the dispatch ``options_key`` filter drops it
#: silently. That is precisely the Roborock capital-O "Off" defect, which cost a
#: live install its mop intensity on every mop-settable model.
#:
#: THE CARPET GUARANTEE IS STILL ENFORCED, AND NOT BY THIS DICT. The real
#: enforcement is the MODE DOWNGRADE in ``profiles/manager.py`` (the ``if
#: is_carpet:`` branch): a carpet room in a mop mode has clean_mode rewritten to
#: ``"vacuum"``, which CLEAN_MODE_VALUE_MAP sends as ``sweeping`` — vacuum-only,
#: no mop deployed. After that downgrade ``is_mop`` is False, so
#: ``queue/queue_engine.py``'s ``if supports_water and is_mop and water_level:``
#: never writes water either. Two independent gates, neither needing a no-water
#: word.
#:
#: ⚠ AND DO NOT SUBSTITUTE MOP-LIFT FOR THIS. VersaLift would appear to solve it
#: natively, but lift is a PER-MODEL fact and not every Dreame has it; leaning on
#: it would move a framework safety property onto firmware that may be absent.
#: The mode downgrade works on every Dreame ever made, because every one of them
#: can vacuum without mopping. Ruled 2026-08-26.
FLOOR_TYPE_WATER_DEFAULTS: dict[str, str] = {}

#: Carpet suction boost. KEPT for the same reason both siblings keep theirs:
#: boosting suction on carpet is what most vacuums do in firmware anyway, so it
#: meets an expectation rather than imposing a preference. This is NOT the same
#: shape as the water dict above despite looking like it — see
#: docs/dev/history/floor-type-cleaning-defaults.md before retiring it by
#: applying that reasoning mechanically.
FLOOR_TYPE_FAN_DEFAULTS: dict[str, str] = {
    "carpet_low_pile": "strong",
    "carpet_high_pile": "turbo",
}

#: DECLARED EMPTY, not absent. Dreame has no retired profile names of its own to
#: map, and there is no framework catalog left to inherit Eufy's from. Empty says
#: "this brand supports the contract and has none"; ABSENT says "the declaration
#: is incomplete" and is a validation error. The two must not be the same state.
LEGACY_ALIASES: dict[str, str] = {}
