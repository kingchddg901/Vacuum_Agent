"""Dreame upkeep-guide library — FLAT per-manual tables + one owned cadence map.

    DREAME_UPKEEP_GUIDE_LIBRARY[family][component] = {
        "clean_frequency": str | None,   # from COMPONENT_FREQUENCIES (shared)
        "replace_frequency": str | None, # from COMPONENT_FREQUENCIES (shared)
        "steps": list[str],              # verbatim from THIS family's own manual
        "notes": list[str],              # verbatim from THIS family's own manual
    }

Mirrors the Roborock/Eufy contract. Two fields with OPPOSITE sharing profiles are
kept apart on purpose:

  * STEPS / NOTES are per-manual. Each AUTHORED family is a FLAT, explicit table,
    every component transcribed from its own model's manual page (measured, not
    inherited). There is no base-to-override composition for authored families: a
    flat table cannot silently inherit generic prose for a component its manual
    words differently (the shared-_BASE defect shipped once, reverted d45e2ec4) and
    cannot hide a missing component behind a fallback. Provenance-scored per family
    by scripts/verify_dreame_guide_provenance.py (0 defects).

  * FREQUENCIES are one owned, NORMALISED cadence per component-type
    (COMPONENT_FREQUENCIES), deliberately shared so the service interval reads the
    same across every model and language — NOT a per-manual value. It is the single
    source; the library injects it. Guarded by test_dreame_upkeep_guides.py and the
    provenance verifier (which now also checks every component resolves a cadence).

TIER profiles (standard / auto_empty / wash_station / _track / _roller /
_baseboard) stay COMPOSED from the tier groups below (each a superset of the one
above) — they are the DEFAULT for the ~730 models with no authored manual, and
their nesting is real. VARIANT families that share a manual page with a measured
delta are still built family+delta (see the scope note). Detailed per-family
provenance + the divergence lessons live in .claude/notes/SCOPE-dreame-guide-families.md.
"""

from __future__ import annotations

from .dreame_upkeep_guides_generated import GENERATED_FAMILIES
from .dreame_upkeep_guides_translated import TRANSLATED_FAMILIES


def _profile(*groups, override=None, drop=(), add=None):
    """Compose a TIER profile: stack steps/notes groups, drop absent hardware, apply
    per-component overrides, append adds. Copies deeply enough that profiles never
    alias each other. Frequencies are injected later by _with_cadence."""
    d: dict[str, dict] = {}
    for g in groups:
        for k, v in g.items():
            d[k] = dict(v)
    for k in drop:
        d.pop(k, None)
    for k, v in (override or {}).items():
        d[k] = {**d.get(k, {}), **v}
    for k, v in (add or {}).items():
        d[k] = dict(v)
    return d


def _with_cadence(components):
    """Inject the shared COMPONENT_FREQUENCIES onto each component's steps/notes. A
    component with no cadence entry is a bug — every component type has one interval.
    Fields come out clean_frequency, replace_frequency, steps, notes."""
    out: dict[str, dict] = {}
    for c, v in components.items():
        out[c] = {**COMPONENT_FREQUENCIES[c], **v}
    return out


# ============================ CADENCE (the one owned frequency map) ============================
# Component-type -> normalised service interval. Shared on purpose (see module docstring);
# NOT per-manual. Every component a family uses MUST have an entry here.
COMPONENT_FREQUENCIES = {
    'acoustic_foam': {"clean_frequency": 'as needed', "replace_frequency": 'as needed'},
    'air_duct': {"clean_frequency": 'as needed', "replace_frequency": None},
    'base_station_filter': {"clean_frequency": 'as needed', "replace_frequency": None},
    'auto_empty_vents': {"clean_frequency": 'monthly', "replace_frequency": None},
    'baseboard_brush': {"clean_frequency": None, "replace_frequency": None},
    'caster_wheel': {"clean_frequency": 'monthly', "replace_frequency": None},
    'charging_contacts': {"clean_frequency": 'monthly', "replace_frequency": None},
    'clean_water_tank': {"clean_frequency": 'as needed', "replace_frequency": None},
    'detergent_inlet': {"clean_frequency": 'as needed', "replace_frequency": None},
    'dock_contacts': {"clean_frequency": 'monthly', "replace_frequency": None},
    'dust_bag': {"clean_frequency": None, "replace_frequency": 'every 2-4 months'},
    'dustbin': {"clean_frequency": 'as needed', "replace_frequency": None},
    'fluffing_roller': {"clean_frequency": 'as needed', "replace_frequency": None},
    'filter': {"clean_frequency": 'weekly', "replace_frequency": 'every 3-6 months'},
    'main_brush': {"clean_frequency": 'monthly', "replace_frequency": 'every 6-12 months'},
    'main_wheel': {"clean_frequency": 'monthly', "replace_frequency": None},
    'mop_cloth': {"clean_frequency": 'after each use', "replace_frequency": 'every 1-3 months'},
    'mop_compartment': {"clean_frequency": 'as needed', "replace_frequency": None},
    'mop_pad_holder': {"clean_frequency": 'every 1-2 months', "replace_frequency": None},
    'sensor': {"clean_frequency": 'monthly', "replace_frequency": None},
    'side_brush': {"clean_frequency": 'monthly', "replace_frequency": 'every 3-6 months'},
    'dirty_water_tank': {"clean_frequency": 'after each use', "replace_frequency": None},
    'washboard': {"clean_frequency": 'as needed', "replace_frequency": None},
    'washboard_filter': {"clean_frequency": 'every 1-2 months', "replace_frequency": None},
    'washboard_heating_module': {"clean_frequency": 'as needed', "replace_frequency": None},
}


# ============================ TIER GROUPS (steps/notes; the no-manual fallback) ============================
# ⚠ MECHANISM-NEUTRAL BY RULE (rewritten 2026-09-02). A tier is the fallback for a model whose
# manual we do NOT have, so its prose must hold for EVERY machine: it says WHAT to do, never HOW to
# detach. The previous text was "the most-complete wording measured across the authored lineups",
# which is backwards for a fallback - the most complete wording is the most SPECIFIC. It told owners
# of unknown hardware to "press and slide the mop assembly clip at the illustrated angle" (one
# premium tracked-mop model's procedure) and to "unscrew the side brush with a screwdriver" (plenty
# of models clip on). Measured at the time: mop_cloth, mop_pad_holder and sensor each matched
# exactly ONE authored family.
#
# "Remove the mop pad" is true whether the pad is velcro, clipped, or on a tray. Anything
# mechanism-specific belongs in an AUTHORED family, transcribed from that model's own manual.
# Cadence still comes from COMPONENT_FREQUENCIES via _with_cadence (DUG-9) - never stated here.
_STANDARD = {
    'main_brush': {
        "steps": [
            'Remove the main brush from the underside of the robot.',
            'Remove any hair or thread wound around the brush and its end caps.',
            'Refit the brush and check that it turns freely.',
        ],
        "notes": [
            'Brush releases differ between models - check your manual rather than forcing it.',
        ],
    },
    'side_brush': {
        "steps": [
            'Remove the side brush.',
            'Remove any hair wound around the brush and its spindle.',
            'Refit the side brush.',
        ],
        "notes": [
            'Some side brushes clip on, others are held by a screw.',
        ],
    },
    'filter': {
        "steps": [
            'Remove the filter from the dust bin.',
            'Tap it gently to shake the dust loose.',
            'Rinse it with clean water only, then let it dry completely before refitting.',
        ],
        "notes": [
            'Do not scrub the filter with a brush, your fingers or anything sharp.',
            'Never refit a filter that is still damp.',
        ],
    },
    'dustbin': {
        "steps": [
            'Remove the dust bin from the robot.',
            'Empty it.',
            'Rinse it with clean water only, then dry it fully before refitting.',
        ],
        "notes": [
            'Do not use detergent.',
        ],
    },
    'mop_cloth': {
        "steps": [
            'Remove the mop pad.',
            'Rinse it under running water until the water runs clear.',
            'Let it air-dry fully before refitting it.',
        ],
        "notes": [
            'Replace the pad when it stays discoloured or stops absorbing.',
        ],
    },
    'mop_pad_holder': {
        "steps": [
            'Remove the mop pad holder.',
            'Rinse away trapped dirt and remove any hair wound around it.',
            'Refit it once it is dry.',
        ],
        "notes": [],
    },
    'caster_wheel': {
        "steps": [
            'Remove any hair or debris wound around the caster wheel so that it turns freely.',
        ],
        "notes": [],
    },
    'sensor': {
        "steps": [
            'Wipe the sensors and charging contacts with a soft, dry cloth.',
        ],
        "notes": [
            'Never use water, detergent or spray on sensors or contacts.',
        ],
    },
}

_AUTO_EMPTY = {
    'dust_bag': {
        "steps": [
            'Open the dust compartment on the base station.',
            'Remove the full dust bag and dispose of it.',
            'Fit a new bag and close the compartment.',
        ],
        "notes": [
            'Close the bag before lifting it out so that dust does not escape.',
        ],
    },
    'auto_empty_vents': {
        "steps": [
            'Check the auto-empty vent on the robot and on the base station.',
            'Clear any blockage and wipe the vent with a dry cloth.',
        ],
        "notes": [],
    },
}

_WASH_STATION = {
    'dirty_water_tank': {
        "steps": [
            'Remove the dirty water tank from the base station.',
            'Empty it and rinse it with clean water.',
            'Refit it once it is dry.',
        ],
        "notes": [
            'Empty it after each wash cycle to stop odours developing.',
        ],
    },
    'washboard': {
        "steps": [
            'Remove the washboard from the base station.',
            'Rinse it and clear away trapped hair and debris.',
            'Wipe the tray it sits in, then refit the washboard once dry.',
        ],
        "notes": [],
    },
    'washboard_filter': {
        "steps": [
            'Remove the washboard filter.',
            'Rinse it clean and let it dry fully before refitting.',
        ],
        "notes": [],
    },
    'washboard_heating_module': {
        "steps": [
            'Check the heating module for scale build-up.',
            'If your base station provides a descaling routine, run it.',
        ],
        "notes": [
            'Scale builds up faster in hard-water areas.',
        ],
    },
    'dock_contacts': {
        "steps": [
            'Wipe the charging contacts and signal area on the base station with a soft, dry cloth.',
        ],
        "notes": [
            'Never use water or detergent on the contacts.',
        ],
    },
    'detergent_inlet': {
        "steps": [
            'If the cleaning-solution inlet is dirty, wipe it with a soft, dry cloth.',
        ],
        "notes": [
            'Use only the cleaning solution approved for your model.',
        ],
    },
}

# Mop-type overrides. Still mechanism-neutral - they only name the part correctly for that hardware.
_MOP_TRACK = {
    'mop_cloth': {
        "steps": [
            'Remove the mop from its track assembly.',
            'Rinse it under running water until the water runs clear.',
            'Let it air-dry fully before refitting it.',
        ],
        "notes": [],
    },
    'mop_pad_holder': {
        "steps": [
            'Remove the mop track assembly.',
            'Rinse away trapped dirt and remove any hair wound around it.',
            'Refit it once it is dry.',
        ],
        "notes": [],
    },
}

_MOP_ROLLER = {
    'mop_cloth': {
        "steps": [
            'Remove the roller mop.',
            'Rinse it under running water until the water runs clear.',
            'Let it air-dry fully before refitting it.',
        ],
        "notes": [],
    },
    'mop_pad_holder': {
        "steps": [
            'Remove the roller mop assembly.',
            'Rinse away trapped dirt and remove any hair wound around it.',
            'Refit it once it is dry.',
        ],
        "notes": [],
    },
}

_BASEBOARD = {
    'baseboard_brush': {
        "steps": [
            'Remove the baseboard brush.',
            'Wipe the bristles clean and remove any trapped hair.',
            'Let it dry, then refit or store it.',
        ],
        "notes": [],
    },
}


# ============================ AUTHORED FAMILIES (flat; steps/notes verbatim from own manual) ============================
# x50 — authored verbatim from robot/x50_R2489A.pdf
_X50 = {
    'main_brush': {
        "steps": [
            'Press the brush guard clips inwards to remove the brush guard, and then lift the brushes out of the robot.',
            'Pull out the brushes. Use the provided cleaning tool to remove any hair tangled in the brushes. After cleaning, push the brushes firmly into the main brush holder until they click into place.',
            'With the screen-printed arrows facing upwards, insert the main brush holder into the slots downwards in an inclined way.',
            'Align the front end of the brush guard with the slot, insert it downwards in an inclined way, and then press it into place.',
        ],
        "notes": [
            'Be careful while pulling out the main brushes to prevent injury.',
        ],
    },
    'side_brush': {
        "steps": [
            'Unscrew the side brush with a screwdriver, clean the hair from the brush, and then screw it back on.',
        ],
        "notes": [],
    },
    'filter': {
        "steps": [
            'Remove the dust box filter and gently tap the basket of the filter to remove the dirt.',
            'Rinse the filter with clean water and dry it completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse with clean water only. Do not use any detergent.',
        ],
    },
    'dustbin': {
        "steps": [
            'Remove the robot cover and press the dust box clip to remove the dust box.',
            'Remove the dust box filter, and then empty the dust box.',
            'Gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'mop_cloth': {
        "steps": [
            'Remove the mop pads from the mop pad holders to replace them.',
        ],
        "notes": [],
    },
    'mop_pad_holder': {
        "steps": [
            'Remove and clean the mop pad holders.',
        ],
        "notes": [],
    },
    'caster_wheel': {
        "steps": [
            'Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.',
            'Rinse the omnidirectional wheel under running water and put it back after drying it completely.',
        ],
        "notes": [
            'Do not use excessive force when separating the axle and tire.',
        ],
    },
    'sensor': {
        "steps": [
            'Wipe the robot sensors with a soft, dry cloth: the bumper window, 3D dual-line laser sensors, VersaLift sensor, edge sensor, bumper, cliff sensors and carpet sensor.',
        ],
        "notes": [
            'A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.',
        ],
    },
    'dust_bag': {
        "steps": [
            'Remove the dust tank cover and discard the dust bag.',
            'Remove the dust and debris from the filter with a dry cloth.',
            'Install a new dust bag.',
            'Reinstall the dust tank cover.',
        ],
        "notes": [
            'Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out.',
        ],
    },
    'auto_empty_vents': {
        "steps": [
            'Clean the auto-empty vents of the robot and the base station with a soft and dry cloth.',
        ],
        "notes": [],
    },
    'dirty_water_tank': {
        "steps": [
            'Remove the used water tank, open its cover and pour out the used water.',
            'Rinse the used water tank with clean water, and use the provided cleaning tool to clean the inner wall of the used water tank.',
        ],
        "notes": [
            'The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it.',
        ],
    },
    'washboard_filter': {
        "steps": [
            'Take out the robot and remove the washboard filter after the mop pad cleaning is complete.',
            'Rinse the washboard filter with clean water, wipe it clean, and then reinstall it in the washboard.',
            'Use the app or press the button to return the robot to the base station, or manually put the robot back.',
        ],
        "notes": [],
    },
    'dock_contacts': {
        "steps": [
            'Clean the charging contacts and the signaling area with a soft and dry cloth.',
        ],
        "notes": [],
    },
}

# x50_master — RLX86CE, the plumbed X50 (automatic water supply + drainage), from
# robot/x50-master_RLX86CE-1.pdf. Its Routine Maintenance is identical to the X50 Ultra
# (_X50) EXCEPT: it has no manual used-water tank (the base auto-drains), so that
# component is dropped; and its washboard-filter procedure is worded differently — it
# names the washboard base clips and the water-status sensors — so that one is taken
# from the X50 Master manual, not inherited (the measured-off-its-own-manual rule).
_X50_MASTER = _profile(_X50, drop=('dirty_water_tank',), override={
    'washboard_filter': {
        "steps": [
            'After the mop pad cleaning is complete, take out the robot and press the washboard base clips to remove the washboard filter.',
            'Remove and rinse the washboard filter with clean water, and wipe it clean.',
            'Reinstall the washboard filter first, and then the washboard base.',
            'Use the app or press the button to return the robot to the base station, or manually put the robot back.',
        ],
        "notes": [
            'If there are water stains remaining on the water status sensors, be sure to wipe them with a soft and dry cloth before reinstalling the washboard base.',
            'When reinstalling the washboard base, make sure that the clips at both ends are firmly in place after you hear a click.',
        ],
    },
})

# x60_ultra — authored verbatim from robot/x60-ultra_R5089B.pdf
_X60_ULTRA = {
    'main_brush': {
        "steps": [
            'Press the brush guard clips inwards to remove the brush guard, and then lift the brushes out of the robot.',
            'Pull out the brushes. Use a proper tool to remove any hair tangled in the brushes. After cleaning, push the brushes firmly into the main brush holder until they click into place.',
            'With the screen-printed arrows facing upwards, insert the main brush holder into the slots downwards in an inclined way.',
            'Align the front end of the brush guard with the slot, insert it downwards in an inclined way, and then press it into place.',
        ],
        "notes": [
            'Be careful while pulling out the main brushes to prevent injury.',
        ],
    },
    'side_brush': {
        "steps": [
            'Unscrew the side brush with a screwdriver, clean the hair from the brush, and then screw it back on.',
        ],
        "notes": [],
    },
    'filter': {
        "steps": [
            'Remove the dust box filter and gently tap the basket of the filter to remove the dirt.',
            'Rinse the filter with clean water and dry it completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse with clean water only. Do not use any detergent.',
        ],
    },
    'dustbin': {
        "steps": [
            'Press the dust box clip to remove the dust box.',
            'Remove the dust box filter, and then empty the dust box. Gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'mop_cloth': {
        "steps": [
            'Remove the mop pads from the mop pad holders to replace them.',
        ],
        "notes": [],
    },
    'mop_pad_holder': {
        "steps": [
            'Remove and clean the mop pad holders.',
        ],
        "notes": [],
    },
    'caster_wheel': {
        "steps": [
            'Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.',
            'Rinse the omnidirectional wheel under running water and put it back after drying it completely.',
        ],
        "notes": [
            'Do not use excessive force when separating the axle and tire.',
        ],
    },
    'sensor': {
        "steps": [
            'Wipe the robot sensors with a soft, dry cloth: the VersaLift sensor, bumper window, edge sensor, bumper, cliff sensors, dust illumination light and carpet sensor.',
        ],
        "notes": [
            'A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.',
        ],
    },
    'dust_bag': {
        "steps": [
            'Remove the dust tank cover and discard the dust bag.',
            'Remove the dust and debris from the filter with a dry cloth.',
            'Install a new dust bag and reinstall the dust tank cover.',
        ],
        "notes": [
            'Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out.',
        ],
    },
    'dirty_water_tank': {
        "steps": [
            'Remove the used water tank, open its cover and pour out the used water.',
            'Rinse the used water tank with clean water, and use a proper tool to clean the inner wall of the used water tank.',
        ],
        "notes": [
            'The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it.',
        ],
    },
    'washboard_filter': {
        "steps": [
            'Take out the robot and remove the washboard filter after the mop pad cleaning is complete.',
            'Rinse the washboard filter with clean water, wipe it clean, and then reinstall it in the washboard.',
            'Use the app or press the button to return the robot to the base station, or manually put the robot back.',
        ],
        "notes": [
            'The washboard heating module may retain residual heat. To prevent scalding, be careful when removing the washboard filter.',
        ],
    },
    'washboard_heating_module': {
        "steps": [
            'During use, the washboard heating module may develop scale. To remove it, take out the robot, pour a small amount of white vinegar (5% acetic acid) on the surface of the heating module and clean it with a proper tool.',
        ],
        "notes": [
            'To prevent scalding, wait until the surface of the heating module cools down to room temperature before cleaning.',
            'An appropriate descaler can also be used in accordance with the instructions it provides.',
            'Do not add white vinegar or descaler directly into the clean water tank, to help prevent malfunction.',
            'Do not use sharp tools or corrosive liquids such as hydrochloric acid to clean the heating module.',
        ],
    },
    'dock_contacts': {
        "steps": [
            'Clean the auto-empty vents, charging contacts and the signaling area with a soft and dry cloth.',
        ],
        "notes": [],
    },
}

# l20 — authored verbatim from robot/l20-ultra-complete+1_R2394A.pdf
_L20 = {
    'main_brush': {
        "steps": [
            'Press the brush guard clips inwards to remove the brush guard and lift the brush out of the robot.',
            'Pull out the brush covers at both ends of the brush. Use the provided cleaning tool to remove any hair tangled in the brush. Reinstall the brush covers on both ends of the brush, and then reinstall the brush. Press on the brush guard to lock it in place.',
        ],
        "notes": [],
    },
    'side_brush': {
        "steps": [
            'Remove and clean the side brush and mop pad holder.',
        ],
        "notes": [],
    },
    'filter': {
        "steps": [
            'Remove the filter and tap its basket gently.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'dustbin': {
        "steps": [
            "Open the robot's cover and press the clip to remove the dust box.",
            'Open the dust box cover and empty the dust box.',
        ],
        "notes": [],
    },
    'mop_cloth': {
        "steps": [
            'Remove the mop pad from the mop pad holder to replace it.',
        ],
        "notes": [],
    },
    'mop_pad_holder': {
        "steps": [
            'Remove and clean the side brush and mop pad holder.',
        ],
        "notes": [],
    },
    'caster_wheel': {
        "steps": [
            'Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.',
            'Rinse the omnidirectional wheel under running water and put it back after drying it completely.',
        ],
        "notes": [
            'Do not use excessive force when separating the axle and tire.',
        ],
    },
    'sensor': {
        "steps": [
            "Wipe the robot's sensors and charging contacts with a soft, dry cloth: the AI visual sensor, line laser sensors, LED fill lights, laser distance sensor (LDS), edge sensor, bumper, charging contacts, cliff sensors and carpet sensor.",
        ],
        "notes": [
            'A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.',
        ],
    },
    'dust_bag': {
        "steps": [
            'Unlock the dust tank cover and then remove it.',
            'Discard the dust bag.',
            'Remove the dust and debris from the filter with a dry cloth.',
            'Install a new dust bag. Then install back the dust tank cover and lock it.',
        ],
        "notes": [
            'Pulling outwards on the handle will seal the dust bag to prevent the dust and debris from accidentally falling out.',
        ],
    },
    'auto_empty_vents': {
        "steps": [
            'Clean the auto-empty vents of the robot and the base station with a soft and dry cloth.',
        ],
        "notes": [],
    },
    'dirty_water_tank': {
        "steps": [
            'Remove the used water tank, open its cover and pour out the used water.',
            'Rinse the used water tank with clean water, and use the provided cleaning tool to clean the inner wall of the used water tank.',
        ],
        "notes": [
            'The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it.',
        ],
    },
    'washboard': {
        "steps": [
            'Press the button to make the robot exit the base station.',
            'Remove the washboard and rinse it with clean water.',
            'Press and hold the button for 3 seconds to add water to the bottom of the base station. Then use the included cleaning tool to clean it.',
            'Press and hold the button for 3 seconds to pump out the used water in the bottom of the base station, dry it with a soft and dry cloth, and then put the washboard back.',
        ],
        "notes": [],
    },
    'dock_contacts': {
        "steps": [
            'Clean the charging contacts and the signaling area of the base station with a soft and dry cloth.',
        ],
        "notes": [],
    },
    'detergent_inlet': {
        "steps": [
            'If the cleaning solution adding inlet is dirty, wipe it with a soft and dry cloth.',
        ],
        "notes": [],
    },
}

# x40 — authored verbatim from robot/x40-ultra-complete+1_R2416A.pdf
_X40 = {
    'main_brush': {
        "steps": [
            'Press the brush guard clips inwards to remove the brush guard and lift the brush out of the robot.',
            'Pull out the brush covers at both ends of the brush. Use the provided cleaning tool to remove any hair tangled in the brush. Reinstall the brush covers on both ends of the brush, and then reinstall the brush. Press on the brush guard to lock it in place.',
        ],
        "notes": [],
    },
    'side_brush': {
        "steps": [
            'Unscrew the side brush with a screwdriver, clean the hair from the brush, and then screw it back on.',
        ],
        "notes": [],
    },
    'filter': {
        "steps": [
            'Remove the dust box filter and gently tap the basket of the filter to remove the dirt.',
            'Rinse the filter with clean water and dry it completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse with clean water only. Do not use any detergent.',
        ],
    },
    'dustbin': {
        "steps": [
            'Open the robot cover and press the dust box clip to remove the dust box.',
            'Open the dust box cover, remove the filter, and then empty the dust box.',
            'Gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'mop_cloth': {
        "steps": [
            'Remove the mop pad from the mop pad holder to replace it.',
        ],
        "notes": [],
    },
    'mop_pad_holder': {
        "steps": [
            'Remove and clean the mop pad holder.',
        ],
        "notes": [],
    },
    'caster_wheel': {
        "steps": [
            'Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.',
            'Rinse the omnidirectional wheel under running water and put it back after drying it completely.',
        ],
        "notes": [
            'Do not use excessive force when separating the axle and tire.',
        ],
    },
    'sensor': {
        "steps": [
            "Wipe the robot's sensors and charging contacts with a soft, dry cloth: the bumper window, laser distance sensor (LDS), 3D dual-line laser sensors, edge sensor, bumper, charging contacts, cliff sensors and carpet sensor.",
        ],
        "notes": [
            'A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.',
        ],
    },
    'dust_bag': {
        "steps": [
            'Remove the dust tank cover and discard the dust bag.',
            'Remove the dust and debris from the filter with a dry cloth.',
            'Install a new dust bag.',
            'Reinstall the dust tank cover.',
        ],
        "notes": [
            'Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out.',
        ],
    },
    'auto_empty_vents': {
        "steps": [
            'Clean the auto-empty vents of the robot and the base station with a soft and dry cloth.',
        ],
        "notes": [],
    },
    'dirty_water_tank': {
        "steps": [
            'Remove the used water tank, open its cover and pour out the used water.',
            'Rinse the used water tank with clean water, and use the provided cleaning tool to clean the inner wall of the used water tank.',
        ],
        "notes": [
            'The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it.',
        ],
    },
    'washboard': {
        "steps": [
            'Enable the washboard base cleaning function in the app, and the robot will exit the base station automatically. Take out the washboard and wait for water to fill the washboard base.',
            'Use the cleaning tool to clean the washboard base. After a moment, the base station will automatically pump out the used water. Then wipe the washboard base with a soft and dry cloth.',
            'Flip the washboard over, remove the roller cover and the roller in turn, and then pull off the end caps of the roller.',
            'Remove the hair tangled in the roller, and then reassemble the parts according to corresponding colors.',
            'Rinse the washboard with clean water, wipe it clean and then put it back into the base station downwards in an inclined way.',
            'Use the app or briefly press the button on the robot to make it return to the base station.',
        ],
        "notes": [
            'If the roller cover is blocked by wipers on both sides of the washboard, rotate the roller to move them aside.',
            'During cleaning, do not make the robot return to the base station.',
        ],
    },
    'dock_contacts': {
        "steps": [
            'Clean the charging contacts and the signaling area of the base station with a soft and dry cloth.',
        ],
        "notes": [],
    },
}

# l50 — authored verbatim from robot/l50-ultra_R9493.pdf
_L50 = {
    'main_brush': {
        "steps": [
            'Press the brush guard clips inwards to remove the brush guard, and then lift the brushes out of the robot.',
            'Pull out the brushes. Use the provided cleaning tool to remove any hair tangled in the brushes. After cleaning, push the brushes firmly into the main brush holder until they click into place.',
            'With the screen-printed arrows facing upwards, insert the main brush holder into the slots downwards in an inclined way.',
            'Align the front end of the brush guard with the slot, insert it downwards in an inclined way, and then press it into place.',
        ],
        "notes": [
            'Be careful while pulling out the main brushes to prevent injury.',
        ],
    },
    'side_brush': {
        "steps": [
            'Unscrew the side brush with a screwdriver, clean the hair from the brush, and then screw it back on.',
        ],
        "notes": [],
    },
    'filter': {
        "steps": [
            'Remove the dust box filter and gently tap the basket of the filter to remove the dirt.',
            'Rinse the filter with clean water and dry it completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse with clean water only. Do not use any detergent.',
        ],
    },
    'dustbin': {
        "steps": [
            'Open the robot cover and press the dust box clip to remove the dust box.',
            'Remove the dust box filter, and then empty the dust box.',
            'Gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'mop_cloth': {
        "steps": [
            'Remove the mop pads from the mop pad holders to replace them.',
        ],
        "notes": [],
    },
    'mop_pad_holder': {
        "steps": [
            'Remove and clean the mop pad holders.',
        ],
        "notes": [],
    },
    'caster_wheel': {
        "steps": [
            'Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.',
            'Rinse the omnidirectional wheel under running water and put it back after drying it completely.',
        ],
        "notes": [
            'Do not use excessive force when separating the axle and tire.',
        ],
    },
    'sensor': {
        "steps": [
            'Wipe the robot sensors with a soft, dry cloth: the 3D dual-line laser sensors, bumper window, edge sensor, laser distance sensor (LDS), cliff sensors, carpet sensor and bumper.',
        ],
        "notes": [
            'A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.',
        ],
    },
    'dust_bag': {
        "steps": [
            'Remove the dust tank cover and discard the dust bag.',
            'Remove the dust and debris from the filter with a dry cloth.',
            'Install a new dust bag.',
            'Reinstall the dust tank cover.',
        ],
        "notes": [
            'Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out.',
        ],
    },
    'auto_empty_vents': {
        "steps": [
            'Clean the auto-empty vents of the robot and the base station with a soft and dry cloth.',
        ],
        "notes": [],
    },
    'dirty_water_tank': {
        "steps": [
            'Remove the used water tank, open its cover and pour out the used water.',
            'Rinse the used water tank with clean water, and use the provided cleaning tool to clean the inner wall of the used water tank.',
        ],
        "notes": [
            'The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it.',
        ],
    },
    'washboard_filter': {
        "steps": [
            'Take out the robot and remove the washboard filter after the mop pad cleaning is complete.',
            'Rinse the washboard filter with clean water, wipe it clean, and then reinstall it in the washboard.',
            'Use the app or press the button to return the robot to the base station, or manually put the robot back.',
        ],
        "notes": [],
    },
    'dock_contacts': {
        "steps": [
            'Clean the charging contacts and the signaling area with a soft and dry cloth.',
        ],
        "notes": [],
    },
}

# l10s_gen2 — authored verbatim from robot/l10s-ultra-gen-2_R2469X.pdf
_L10S_GEN2 = {
    'main_brush': {
        "steps": [
            'Press the brush guard clips inwards to remove the brush guard and lift the brush out of the robot.',
            'Pull out the brush covers at both ends of the brush. Use the provided cleaning tool to remove any hair tangled in the brush. Reinstall the brush covers on both ends of the brush, and then reinstall the brush. Press on the brush guard to lock it in place.',
        ],
        "notes": [],
    },
    'side_brush': {
        "steps": [
            'Remove and clean the side brush.',
        ],
        "notes": [],
    },
    'filter': {
        "steps": [
            'Open the dust box cover and remove the filter.',
            'Gently tap the basket of the filter to remove the dirt.',
            'Rinse the filter with water and dry it completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse with clean water only. Do not use any detergent.',
            'Use the filter only when it is completely dry.',
        ],
    },
    'dustbin': {
        "steps": [
            'Open the robot cover and press the dust box clip to remove the dust box.',
            'Open the dust box cover, remove the filter, and then empty the dust box.',
            'Gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'mop_cloth': {
        "steps": [
            'Remove the mop pad from the mop pad holder to replace it.',
        ],
        "notes": [],
    },
    'mop_pad_holder': {
        "steps": [
            'Remove and clean the mop pad holder.',
        ],
        "notes": [],
    },
    'caster_wheel': {
        "steps": [
            'Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.',
            'Rinse the omnidirectional wheel under running water and put it back after drying it completely.',
        ],
        "notes": [
            'Do not use excessive force when separating the axle and tire.',
        ],
    },
    'sensor': {
        "steps": [
            'Wipe the robot sensors with a soft, dry cloth: the carpet sensor, cliff sensors, bumper, edge sensor, laser distance sensor (LDS) and 3D line laser sensor.',
        ],
        "notes": [
            'A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.',
        ],
    },
    'dust_bag': {
        "steps": [
            'Remove the dust tank cover and discard the dust bag.',
            'Remove the dust and debris from the filter with a dry cloth.',
            'Install a new dust bag.',
            'Reinstall the dust tank cover.',
        ],
        "notes": [
            'Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out.',
        ],
    },
    'auto_empty_vents': {
        "steps": [
            'Clean the auto-empty vents of the robot and the base station with a soft and dry cloth.',
        ],
        "notes": [],
    },
    'dirty_water_tank': {
        "steps": [
            'Remove the used water tank, open its cover and pour out the used water.',
            'Rinse the used water tank with clean water, and use the provided cleaning tool to clean the inner wall of the used water tank.',
        ],
        "notes": [
            'The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it.',
        ],
    },
    'washboard': {
        "steps": [
            'Take out the robot from the base station.',
            'Take out the washboard and open the filter cover. Rinse the washboard with clean water and clean it with the provided cleaning tool. After cleaning, close the cover and wipe the washboard with a soft and dry cloth.',
            'Wipe the washboard base clean, and put the washboard back into the base station.',
            'Use the app or briefly press the button on the robot to make it return to the base station.',
        ],
        "notes": [
            'During cleaning, do not make the robot return to the base station.',
        ],
    },
    'dock_contacts': {
        "steps": [
            'Clean the charging contacts and the signaling area with a soft and dry cloth.',
        ],
        "notes": [],
    },
}

# x60_pro_ultra_complete — authored verbatim from robot-unmatched/r6001-x60-series-en-de-fr-it-es-pl-nl-no-sv-el-p.pdf
_X60_PRO_ULTRA_COMPLETE = {
    'main_brush': {
        "steps": [
            'Press the brush guard clips inwards to remove the brush guard, and then lift the brushes out of the robot.',
            'Pull out the brushes. Use a proper tool to remove any hair tangled in the brushes. After cleaning, push the brushes firmly into the main brush holder until they click into place.',
            'With the screen-printed arrows facing upwards, insert the main brush holder into the slots downwards in an inclined way.',
            'Align the front end of the brush guard with the slot, insert it downwards in an inclined way, and then press it into place.',
        ],
        "notes": [
            'Be careful while pulling out the main brushes to prevent injury.',
        ],
    },
    'side_brush': {
        "steps": [
            'Unscrew the side brush with a screwdriver, clean the hair from the brush, and then screw it back on.',
        ],
        "notes": [],
    },
    'filter': {
        "steps": [
            'Remove the dust box filter and gently tap the basket of the filter to remove the dirt.',
            'Rinse the filter with clean water and dry it completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse with clean water only. Do not use any detergent.',
        ],
    },
    'dustbin': {
        "steps": [
            'Press the dust box clip to remove the dust box.',
            'Remove the dust box filter, and then empty the dust box. Gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'mop_cloth': {
        "steps": [
            'Remove the mop pads from the mop pad holders to replace them.',
        ],
        "notes": [],
    },
    'mop_pad_holder': {
        "steps": [
            'Remove and clean the mop pad holders.',
        ],
        "notes": [],
    },
    'caster_wheel': {
        "steps": [
            'Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.',
            'Rinse the omnidirectional wheel under running water and put it back after drying it completely.',
        ],
        "notes": [
            'Do not use excessive force when separating the axle and tire.',
        ],
    },
    'sensor': {
        "steps": [
            'Wipe the robot sensors with a soft, dry cloth: the VersaLift sensor, bumper window, edge sensor, bumper, cliff sensors, dust illumination light and carpet sensor.',
        ],
        "notes": [
            'A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.',
        ],
    },
    'dust_bag': {
        "steps": [
            'Remove the dust tank cover and discard the dust bag.',
            'Remove the dust and debris from the filter with a dry cloth.',
            'Install a new dust bag and reinstall the dust tank cover.',
        ],
        "notes": [
            'Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out.',
        ],
    },
    'dirty_water_tank': {
        "steps": [
            'Remove the used water tank, open its cover and pour out the used water.',
            'Rinse the used water tank with clean water, and use a proper tool to clean the inner wall of the used water tank.',
        ],
        "notes": [
            'The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it.',
        ],
    },
    'washboard_filter': {
        "steps": [
            'Take out the robot and remove the washboard filter after the mop pad cleaning is complete.',
            'Rinse the washboard filter with clean water, wipe it clean, and then reinstall it in the washboard.',
            'Use the app or press the button to return the robot to the base station, or manually put the robot back.',
        ],
        "notes": [
            'The washboard heating module may retain residual heat. To prevent scalding, be careful when removing the washboard filter.',
        ],
    },
    'washboard_heating_module': {
        "steps": [
            'During use, the washboard heating module may develop scale. To remove it, take out the robot, pour a small amount of white vinegar (5% acetic acid) on the surface of the heating module and clean it with a proper tool.',
        ],
        "notes": [
            'To prevent scalding, wait until the surface of the heating module cools down to room temperature before cleaning.',
            'An appropriate descaler can also be used in accordance with the instructions it provides.',
            'Do not add white vinegar or descaler directly into the clean water tank, to help prevent malfunction.',
            'Do not use sharp tools or corrosive liquids such as hydrochloric acid to clean the heating module.',
        ],
    },
    'dock_contacts': {
        "steps": [
            'Clean the auto-empty vents, charging contacts and the signaling area with a soft and dry cloth.',
        ],
        "notes": [],
    },
    'baseboard_brush': {
        "steps": [
            'After the baseboard cleaning task is complete, pull the cleaning brush upward to remove it, wipe the bristles with a clean damp cloth, and store it properly after air drying.',
        ],
        "notes": [],
    },
}

# aqua10_ultra_track — authored verbatim from robot/aqua10-ultra-track_R9528A.pdf
_AQUA10_ULTRA_TRACK = {
    'main_brush': {
        "steps": [
            'Press the brush guard clips inwards to remove the brush guard, and then lift the brushes out of the robot.',
            'Pull out the brushes. Use a proper tool to remove any hair tangled in the brushes. After cleaning, push the brushes firmly into the main brush holder until they click into place.',
            'With the screen-printed arrows facing upwards, insert the main brush holder into the slots downwards in an inclined way.',
            'Align the front end of the brush guard with the slot, insert it downwards in an inclined way, and then press it into place.',
        ],
        "notes": [
            'Be careful while pulling out the main brushes to prevent injury.',
        ],
    },
    'side_brush': {
        "steps": [
            'Unscrew the side brush with a screwdriver, clean the hair from the brush, and then screw it back on.',
        ],
        "notes": [],
    },
    'filter': {
        "steps": [
            'Open the dust box cover and remove the filter.',
            'Gently tap the basket of the filter to remove the dirt.',
            'Rinse the filter with water and dry it completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse with clean water only. Do not use any detergent.',
            'Use the filter only when it is completely dry.',
        ],
    },
    'dustbin': {
        "steps": [
            'Remove the robot cover and press the dust box clip to remove the dust box.',
            'Open the dust box cover, remove the filter, and then empty the dust box. Gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'mop_cloth': {
        "steps": [
            'Press and slide the mop assembly clip at the illustrated angle to remove the mop assembly.',
            'Detach the mop from the bracket and use a proper tool to remove the hair tangled in the bracket.',
            'Install the new mop to the bracket, ensuring it is in place. Then firmly press the mop assembly clip to secure the mop.',
            'Push the mop assembly back into the compartment until it fits into the slot and clicks into place.',
        ],
        "notes": [
            'It is normal for the slot to rotate automatically during installation.',
        ],
    },
    'mop_pad_holder': {
        "steps": [
            'Remove the mop assembly from the robot. Clean the mop assembly compartment and filter to prevent blockage.',
        ],
        "notes": [],
    },
    'caster_wheel': {
        "steps": [
            'Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.',
            'Rinse the omnidirectional wheel under the running water and put it back after drying it completely.',
        ],
        "notes": [
            'Do not use excessive force when separating the axle and tire.',
        ],
    },
    'sensor': {
        "steps": [
            'Wipe the robot sensors by using a soft and dry cloth: the bumper window, VersaLift sensor, edge sensor, bumper, cliff sensors and carpet sensor.',
        ],
        "notes": [
            'A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.',
        ],
    },
    'dust_bag': {
        "steps": [
            'Remove the dust tank cover and discard the dust bag.',
            'Remove the dust and debris from the filter with a dry cloth.',
            'Install a new dust bag.',
            'Reinstall the dust tank cover.',
        ],
        "notes": [
            'Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out.',
        ],
    },
    'auto_empty_vents': {
        "steps": [
            'Clean the auto-empty vents of the robot and the base station with a soft and dry cloth.',
        ],
        "notes": [],
    },
    'dirty_water_tank': {
        "steps": [
            'Remove the used water tank, open its cover and pour out the used water.',
            'Rinse the used water tank with clean water, and use a proper tool to clean the inner wall of the used water tank.',
        ],
        "notes": [
            'The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it.',
        ],
    },
    'washboard_filter': {
        "steps": [
            'Take out the robot and remove the washboard filter after the mop cleaning is complete.',
            'Rinse the washboard filter with clean water, wipe it clean, and then reinstall it in the washboard.',
            'Use the app or press the button to return the robot to the base station, or manually put the robot back.',
        ],
        "notes": [
            'The washboard heating module may retain residual heat. To prevent scalding, be careful when removing the washboard filter.',
        ],
    },
    'washboard_heating_module': {
        "steps": [
            'During use, the washboard heating module may develop scale. To remove it, take out the robot, pour a small amount of white vinegar (5% acetic acid) on the surface of the heating module and clean it with a proper tool.',
        ],
        "notes": [
            'To prevent scalding, wait until the surface of the heating module cools down to room temperature before cleaning.',
            'An appropriate descaler can also be used in accordance with the instructions it provides.',
            'Do not add white vinegar or descaler directly into the clean water tank to help prevent malfunction.',
            'Do not use sharp tools or corrosive liquids such as hydrochloric acid to clean the heating module.',
        ],
    },
    'dock_contacts': {
        "steps": [
            'Clean the charging contacts and the signaling area with a soft and dry cloth.',
        ],
        "notes": [],
    },
}

# aqua10_ultra_roller — authored verbatim from robot/aqua10-ultra-roller_R9535.pdf
_AQUA10_ULTRA_ROLLER = {
    'main_brush': {
        "steps": [
            'Press the brush guard clips inwards to remove the brush guard, and then lift the brushes out of the robot.',
            'Pull out the brushes. Use a proper tool to remove any hair tangled in the brushes. After cleaning, push the brushes firmly into the main brush holder until they click into place.',
            'With the screen-printed arrows facing upwards, insert the main brush holder into the slots downwards in an inclined way.',
            'Align the front end of the brush guard with the slot, insert it downwards in an inclined way, and then press it into place.',
        ],
        "notes": [
            'Be careful while pulling out the main brushes to prevent injury.',
        ],
    },
    'side_brush': {
        "steps": [
            'Unscrew the side brush with a screwdriver, clean the hair from the brush, and then screw it back on.',
        ],
        "notes": [],
    },
    'filter': {
        "steps": [
            'Open the dust box cover and remove the filter.',
            'Gently tap the basket of the filter to remove the dirt.',
            'Rinse the filter with water and dry it completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse with clean water only. Do not use any detergent.',
            'Use the filter only when it is completely dry.',
        ],
    },
    'dustbin': {
        "steps": [
            'Remove the robot cover and press the dust box clip to remove the dust box.',
            'Open the dust box cover, remove the filter, and then empty the dust box. Gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'mop_cloth': {
        "steps": [
            'Press the clip and slowly lift the mop assembly to remove it.',
            'Install the new mop assembly until it clicks into place.',
        ],
        "notes": [],
    },
    'mop_pad_holder': {
        "steps": [
            'Remove the mop assembly and fluffing roller from the robot. Clean the mop assembly compartment, wiper and filter to prevent blockage.',
            'Use a proper tool to remove any hair tangled in the roller. Then rinse it with water and dry it completely before reinstalling.',
        ],
        "notes": [],
    },
    'caster_wheel': {
        "steps": [
            'Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.',
            'Rinse the omnidirectional wheel under the running water and put it back after drying it completely.',
        ],
        "notes": [
            'Do not use excessive force when separating the axle and tire.',
        ],
    },
    'sensor': {
        "steps": [
            'Wipe the robot sensors by using a soft and dry cloth: the bumper window, VersaLift sensor, edge sensor, bumper, cliff sensors and carpet sensor.',
        ],
        "notes": [
            'A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.',
        ],
    },
    'dust_bag': {
        "steps": [
            'Remove the dust tank cover and discard the dust bag.',
            'Remove the dust and debris from the filter with a dry cloth.',
            'Install a new dust bag.',
            'Reinstall the dust tank cover.',
        ],
        "notes": [
            'Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out.',
        ],
    },
    'auto_empty_vents': {
        "steps": [
            'Clean the auto-empty vents of the robot and the base station with a soft and dry cloth.',
        ],
        "notes": [],
    },
    'dirty_water_tank': {
        "steps": [
            'Remove the used water tank, open its cover and pour out the used water.',
            'Rinse the used water tank with clean water, and use a proper tool to clean the inner wall of the used water tank.',
        ],
        "notes": [
            'The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it.',
        ],
    },
    'washboard': {
        "steps": [
            'Take out the robot and remove the washboard after the mop cleaning is complete. Then rinse the washboard with clean water and wipe it clean.',
            'During use, the heating module may develop scale. To remove it, take out the robot, pour a small amount of white vinegar (5% acetic acid) on the surface of the heating module and clean it with a proper tool. Then reinstall the washboard.',
            'Use the app or press the button to return the robot to the base station, or manually put the robot back.',
        ],
        "notes": [
            'The heating module under the washboard may retain residual heat. To prevent scalding, be careful when removing the washboard.',
            'To prevent scalding, wait until the surface of the heating module cools down to room temperature before cleaning.',
            'An appropriate descaler can also be used in accordance with the instructions it provides.',
            'Do not add white vinegar or descaler directly into the clean water tank to help prevent malfunction.',
            'Do not use sharp tools or corrosive liquids such as hydrochloric acid to clean the heating module.',
        ],
    },
    'dock_contacts': {
        "steps": [
            'Clean the charging contacts and the signaling area with a soft and dry cloth.',
        ],
        "notes": [],
    },
}

# matrix10 — authored verbatim from api-fetch/dreame.vacuum.r2513a__3f71ba99.pdf
_MATRIX10 = {
    'main_brush': {
        "steps": [
            'Press the brush guard clips inwards to remove the brush guard, and then lift the brushes out of the robot.',
            'Pull out the brushes. Use a proper tool to remove any hair tangled in the brushes. After cleaning, push the brushes firmly into the main brush holder until they click into place.',
            'With the screen-printed arrows facing upwards, insert the main brush holder into the slots downwards in an inclined way.',
            'Align the front end of the brush guard with the slot, insert it downwards in an inclined way, and then press it into place.',
        ],
        "notes": [
            'Be careful while pulling out the main brushes to prevent injury.',
        ],
    },
    'side_brush': {
        "steps": [
            'Unscrew the side brush with a screwdriver, clean the hair from the brush, and then screw it back on.',
        ],
        "notes": [],
    },
    'filter': {
        "steps": [
            'Remove the dust box filter, and then empty the dust box.',
            'Gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'dustbin': {
        "steps": [
            'Remove the robot cover and press the dust box clip to remove the dust box.',
            'Remove the dust box filter, and then empty the dust box. Gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'mop_cloth': {
        "steps": [
            'Remove the mop pads from the mop pad holders to replace them.',
        ],
        "notes": [
            'When replacing the mop pads, ensure that each new mop pad is installed in the mop pad holder of the matching color.',
        ],
    },
    'mop_pad_holder': {
        "steps": [
            'Remove and clean the mop pad holders. After cleaning, reinstall them into their corresponding slots on the base station door.',
        ],
        "notes": [],
    },
    'caster_wheel': {
        "steps": [
            'Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel. Do not use excessive force.',
            'Rinse the omnidirectional wheel under the running water and put it back after drying it completely.',
        ],
        "notes": [],
    },
    'sensor': {
        "steps": [
            'Wipe the robot sensors by using a soft and dry cloth: the VersaLift sensor, bumper window, 3D dual-line laser sensors, edge sensor, bumper, cliff sensors and carpet sensor.',
        ],
        "notes": [
            'A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.',
        ],
    },
    'dust_bag': {
        "steps": [
            'Press the base station door button to open the door. Remove the dust tank cover and discard the dust bag.',
            'Remove the dust and debris from the filter with a dry cloth.',
            'Install a new dust bag, then reinstall the dust tank cover and close the base station door.',
        ],
        "notes": [
            'Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out.',
        ],
    },
    'dirty_water_tank': {
        "steps": [
            'Remove the used water tank, open its cover and pour out the used water.',
            'Rinse the used water tank with clean water, and use a proper tool to clean the inner wall of the used water tank.',
        ],
        "notes": [
            'The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it.',
        ],
    },
    'washboard_filter': {
        "steps": [
            'After mop pad cleaning is complete, take out the robot, open the base station door and remove the washboard filter.',
            'Rinse the washboard filter with clean water and wipe it clean. Then, reinstall it into the washboard and close the base station door.',
            'Use the app or press the button to return the robot to the base station, or manually put the robot back.',
        ],
        "notes": [
            'The washboard heating module may retain residual heat. To prevent scalding, be careful when removing the washboard filter.',
        ],
    },
    'washboard_heating_module': {
        "steps": [
            'During use, the washboard heating module may develop scale. To remove it, take out the robot, pour a small amount of white vinegar (5% acetic acid) on the surface of the heating module and clean it with a brush.',
        ],
        "notes": [
            'To prevent scalding, wait until the surface of the heating module cools down to room temperature before cleaning.',
            'An appropriate descaler can also be used in accordance with the instructions it provides.',
            'Do not add white vinegar or descaler directly into the clean water tank to help prevent malfunction.',
            'Do not use sharp tools or corrosive liquids such as hydrochloric acid to clean the heating module.',
        ],
    },
    'dock_contacts': {
        "steps": [
            'Clean the auto-empty vents, charging contacts and the signaling area with a soft and dry cloth.',
        ],
        "notes": [],
    },
}

# l60_ultra — authored verbatim from api-fetch/dreame.vacuum.r5090a__a0c79c98.pdf
_L60_ULTRA = {
    'main_brush': {
        "steps": [
            'Press the brush guard clips inwards to remove the brush guard, and then lift the brushes out of the robot.',
            'Pull out the brushes. Use a proper tool to remove any hair tangled in the brushes. After cleaning, push the brushes firmly into the main brush holder until they click into place.',
            'With the screen-printed arrows facing upwards, insert the main brush holder into the slots downwards in an inclined way.',
            'Align the front end of the brush guard with the slot, insert it downwards in an inclined way, and then press it into place.',
        ],
        "notes": [
            'Be careful while pulling out the main brushes to prevent injury.',
        ],
    },
    'side_brush': {
        "steps": [
            'Unscrew the side brush with a screwdriver, clean the hair from the brush, and then screw it back on.',
        ],
        "notes": [],
    },
    'filter': {
        "steps": [
            'Remove the dust box filter and gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
        ],
    },
    'dustbin': {
        "steps": [
            'Press the dust box clip to remove the dust box.',
            'Remove the dust box filter, and then empty the dust box. Gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'mop_cloth': {
        "steps": [
            'Remove the mop pads from the mop pad holders to replace them.',
        ],
        "notes": [],
    },
    'mop_pad_holder': {
        "steps": [
            'Remove and clean the mop pad holders.',
        ],
        "notes": [],
    },
    'caster_wheel': {
        "steps": [
            'Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.',
            'Rinse the omnidirectional wheel under the running water and put it back after drying it completely.',
        ],
        "notes": [
            'Do not use excessive force when separating the axle and tire.',
        ],
    },
    'sensor': {
        "steps": [
            'Wipe the robot sensors by using a soft and dry cloth: the bumper window, edge sensor, bumper, cliff sensors and carpet sensor.',
        ],
        "notes": [
            'A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.',
        ],
    },
    'dust_bag': {
        "steps": [
            'Remove the dust tank cover and discard the dust bag.',
            'Remove the dust and debris from the filter with a dry cloth.',
            'Install a new dust bag.',
            'Reinstall the dust tank cover.',
        ],
        "notes": [
            'Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out.',
        ],
    },
    'dirty_water_tank': {
        "steps": [
            'Remove the used water tank, open its cover and pour out the used water.',
            'Rinse the used water tank with clean water, and use a proper tool to clean the inner wall of the used water tank.',
        ],
        "notes": [
            'The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it.',
        ],
    },
    'washboard_filter': {
        "steps": [
            'Take out the robot and remove the washboard filter after the mop pad cleaning is complete.',
            'Rinse the washboard filter with clean water, wipe it clean, and then reinstall it in the washboard.',
            'Use the app or press the button to return the robot to the base station, or manually put the robot back.',
        ],
        "notes": [
            'The washboard heating module may retain residual heat. To prevent scalding, be careful when removing the washboard filter.',
        ],
    },
    'washboard_heating_module': {
        "steps": [
            'During use, the washboard heating module may develop scale. To remove it, take out the robot, pour a small amount of white vinegar (5% acetic acid) on the surface of the heating module and clean it with a proper tool.',
        ],
        "notes": [
            'To prevent scalding, wait until the surface of the heating module cools down to room temperature before cleaning.',
            'An appropriate descaler can also be used in accordance with the instructions it provides.',
            'Do not add white vinegar or descaler directly into the clean water tank to help prevent malfunction.',
            'Do not use sharp tools or corrosive liquids such as hydrochloric acid to clean the heating module.',
        ],
    },
    'dock_contacts': {
        "steps": [
            'Clean the auto-empty vents, charging contacts and the signaling area with a soft and dry cloth.',
        ],
        "notes": [],
    },
}

# l60_ultra_pe — authored verbatim from api-fetch/dreame.vacuum.r50393__5bb8de70.pdf
_L60_ULTRA_PE = {
    'main_brush': {
        "steps": [
            'Press the brush guard clips inwards to remove the brush guard, and then lift the brushes out of the robot.',
            'Pull out the brushes. Use a proper tool to remove any hair tangled in the brushes. After cleaning, push the brushes firmly into the main brush holder until they click into place.',
            'With the screen-printed arrows facing upwards, insert the main brush holder into the slots downwards in an inclined way.',
            'Align the front end of the brush guard with the slot, insert it downwards in an inclined way, and then press it into place.',
        ],
        "notes": [
            'Be careful while pulling out the main brushes to prevent injury.',
        ],
    },
    'side_brush': {
        "steps": [
            'Unscrew the side brush with a screwdriver, clean the hair from the brush, and then screw it back on.',
        ],
        "notes": [],
    },
    'filter': {
        "steps": [
            'Remove the dust box filter, and then empty the dust box. Gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'dustbin': {
        "steps": [
            'Press the dust box clip to remove the dust box.',
            'Remove the dust box filter, and then empty the dust box. Gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'mop_cloth': {
        "steps": [
            'Remove the mop pads from the mop pad holders to replace them.',
        ],
        "notes": [],
    },
    'mop_pad_holder': {
        "steps": [
            'Remove and clean the mop pad holders.',
        ],
        "notes": [],
    },
    'caster_wheel': {
        "steps": [
            'Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.',
            'Rinse the omnidirectional wheel under the running water and put it back after drying it completely.',
        ],
        "notes": [
            'Do not use excessive force when separating the axle and tire.',
        ],
    },
    'sensor': {
        "steps": [
            'Wipe the robot sensors by using a soft and dry cloth: the laser distance sensor (LDS), bumper window, bumper, edge sensor, cliff sensors and carpet sensor.',
        ],
        "notes": [
            'A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.',
        ],
    },
    'dust_bag': {
        "steps": [
            'Remove the dust tank cover and discard the dust bag.',
            'Remove the dust and debris from the filter with a dry cloth.',
            'Install a new dust bag.',
            'Reinstall the dust tank cover.',
        ],
        "notes": [
            'Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out.',
        ],
    },
    'dirty_water_tank': {
        "steps": [
            'Remove the used water tank, open its cover and pour out the used water.',
            'Rinse the used water tank with clean water, and use a proper tool to clean the inner wall of the used water tank.',
        ],
        "notes": [
            'The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it.',
        ],
    },
    'washboard_filter': {
        "steps": [
            'Take out the robot and remove the washboard filter after the mop pad cleaning is complete.',
            'Rinse the washboard filter with clean water, wipe it clean, and then reinstall it in the washboard.',
            'Use the app or press the button to return the robot to the base station, or manually put the robot back.',
        ],
        "notes": [
            'The washboard heating module may retain residual heat. To prevent scalding, be careful when removing the washboard filter.',
        ],
    },
    'washboard_heating_module': {
        "steps": [
            'During use, the washboard heating module may develop scale. To remove it, take out the robot, pour a small amount of white vinegar (5% acetic acid) on the surface of the heating module and clean it with a proper tool.',
        ],
        "notes": [
            'To prevent scalding, wait until the surface of the heating module cools down to room temperature before cleaning.',
            'An appropriate descaler can also be used in accordance with the instructions it provides.',
            'Do not add white vinegar or descaler directly into the clean water tank to help prevent malfunction.',
            'Do not use sharp tools or corrosive liquids such as hydrochloric acid to clean the heating module.',
        ],
    },
    'dock_contacts': {
        "steps": [
            'Clean the auto-empty vents, charging contacts and the signaling area with a soft and dry cloth.',
        ],
        "notes": [],
    },
}

# l40s_ultra — authored verbatim from api-fetch/dreame.vacuum.r2551a__acbc1fa4.pdf
_L40S_ULTRA = {
    'main_brush': {
        "steps": [
            'Press the brush guard clips inwards to remove the brush guard, and then lift the brushes out of the robot.',
            'Pull out the brushes. Use the provided cleaning tool to remove any hair tangled in the brushes. After cleaning, push the brushes firmly into the main brush holder until they click into place.',
            'With the screen-printed arrows facing upwards, insert the main brush holder into the slots downwards in an inclined way.',
            'Align the front end of the brush guard with the slot, insert it downwards in an inclined way, and then press it into place.',
        ],
        "notes": [
            'Be careful while pulling out the main brushes to prevent injury.',
        ],
    },
    'side_brush': {
        "steps": [
            'Unscrew the side brush with a screwdriver, clean the hair from the brush, and then screw it back on.',
        ],
        "notes": [],
    },
    'filter': {
        "steps": [
            'Remove the dust box filter and gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'dustbin': {
        "steps": [
            'Open the robot cover and press the dust box clip to remove the dust box.',
            'Remove the dust box filter, and then empty the dust box.',
            'Gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'mop_cloth': {
        "steps": [
            'Remove the mop pads from the mop pad holders to replace them.',
        ],
        "notes": [],
    },
    'mop_pad_holder': {
        "steps": [
            'Remove and clean the mop pad holders.',
        ],
        "notes": [],
    },
    'caster_wheel': {
        "steps": [
            'Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.',
            'Rinse the omnidirectional wheel under the running water and put it back after drying it completely.',
        ],
        "notes": [
            'Do not use excessive force.',
        ],
    },
    'sensor': {
        "steps": [
            'Wipe the robot sensors by using a soft and dry cloth: the bumper window, laser distance sensor (LDS), edge sensor, bumper, cliff sensors and carpet sensor.',
        ],
        "notes": [
            'A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.',
        ],
    },
    'dust_bag': {
        "steps": [
            'Remove the dust tank cover and discard the dust bag.',
            'Remove the dust and debris from the filter with a dry cloth.',
            'Install a new dust bag.',
            'Reinstall the dust tank cover.',
        ],
        "notes": [
            'Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out.',
        ],
    },
    'auto_empty_vents': {
        "steps": [
            'Clean the auto-empty vents of the robot and the base station with a soft and dry cloth.',
        ],
        "notes": [],
    },
    'dirty_water_tank': {
        "steps": [
            'Remove the used water tank, open its cover and pour out the used water.',
            'Rinse the used water tank with clean water, and use the provided cleaning tool to clean the inner wall of the used water tank.',
        ],
        "notes": [
            'The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it.',
        ],
    },
    'washboard_filter': {
        "steps": [
            'Take out the robot and remove the washboard filter after the mop pad cleaning is complete.',
            'Rinse the washboard filter with clean water, wipe it clean, and then reinstall it in the washboard.',
            'Use the app or press the button to return the robot to the base station, or manually put the robot back.',
        ],
        "notes": [],
    },
    'dock_contacts': {
        "steps": [
            'Clean the charging contacts and the signaling area with a soft and dry cloth.',
        ],
        "notes": [],
    },
    'main_wheel': {
        "steps": [
            'Rotate the auxiliary climbing wheel until the "OUT" arrow is facing upward, and then pull out the wheel.',
            'Use a proper tool to clean the hair tangled in the main wheel and auxiliary climbing wheel.',
            'After cleaning, rotate the main wheel to align the two arrows. Then, with the "IN" arrow facing downward, insert the left and right auxiliary climbing wheels accordingly until they click into place.',
        ],
        "notes": [],
    },
}

# d30_ultra — authored verbatim from api-fetch/dreame.vacuum.r5057a__def7d841.pdf
_D30_ULTRA = {
    'main_brush': {
        "steps": [
            'Press the brush guard clips inwards to remove the brush guard, and lift the brush out of the robot.',
            'Pull out the brush cover at the square end of the brush. Use a proper tool to remove any foreign object in the brush.',
            'Pull out and clean the brush strips. Use a proper tool to clean the comb.',
            'Reinstall the brush strips, brush cover, and brush in turn. Press on the brush guard to lock it in place.',
        ],
        "notes": [
            "It's recommended to remove the brush strips separately for water cleaning, but do not wash the brush directly.",
            "If the brush is severely tangled, please check whether the robot's dust box is full and cannot suck in hair. If so, please empty the dust box.",
            'Keep the brush out of the reach of children and pets to avoid injuries.',
            'When pulling out the brush cover and removing/reinstalling the brush strips, please handle with care to avoid scratches.',
        ],
    },
    'side_brush': {
        "steps": [
            'Remove and clean the side brush.',
        ],
        "notes": [],
    },
    'filter': {
        "steps": [
            'Open the dust box cover, remove the filter, and then empty the dust box.',
            'Gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'dustbin': {
        "steps": [
            'Open the robot cover and press the dust box clip to remove the dust box.',
            'Open the dust box cover, remove the filter, and then empty the dust box.',
            'Gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'mop_cloth': {
        "steps": [
            'Remove the mop pads from the mop pad holders to replace them.',
        ],
        "notes": [],
    },
    'mop_pad_holder': {
        "steps": [
            'Remove and clean the mop pad holders.',
        ],
        "notes": [],
    },
    'caster_wheel': {
        "steps": [
            'Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel. Do not use excessive force.',
            'Rinse the omnidirectional wheel under the running water and put it back after drying it completely.',
        ],
        "notes": [],
    },
    'sensor': {
        "steps": [
            'Wipe the robot sensors by using a soft and dry cloth: the laser distance sensor (LDS), bumper window, bumper, edge sensor, cliff sensors and carpet sensor.',
        ],
        "notes": [
            'A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.',
        ],
    },
    'dust_bag': {
        "steps": [
            'Remove the dust tank cover and discard the dust bag.',
            'Remove the dust and debris from the filter with a dry cloth.',
            'Install a new dust bag.',
            'Reinstall the dust tank cover.',
        ],
        "notes": [
            'Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out.',
        ],
    },
    'auto_empty_vents': {
        "steps": [
            'Clean the auto-empty vents of the robot and the base station with a soft and dry cloth.',
        ],
        "notes": [],
    },
    'dirty_water_tank': {
        "steps": [
            'Remove the used water tank, open its cover and pour out the used water.',
            'Rinse the used water tank with clean water, and use a proper tool to clean the inner wall of the used water tank.',
        ],
        "notes": [
            'The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it.',
        ],
    },
    'washboard_filter': {
        "steps": [
            'Take out the robot and remove the washboard filter after the mop pad cleaning is complete.',
            'Rinse the washboard filter with clean water, wipe it clean, and then reinstall it in the washboard.',
            'Use the app or press the button to return the robot to the base station, or manually put the robot back.',
        ],
        "notes": [
            'During cleaning, do not make the robot return to the base station.',
        ],
    },
    'dock_contacts': {
        "steps": [
            'Clean the charging contacts and the signaling area with a soft and dry cloth.',
        ],
        "notes": [],
    },
}

# d20_pro_plus — authored verbatim from api-fetch/dreame.vacuum.r2566a__dbe6320d.pdf
_D20_PRO_PLUS = {
    'main_brush': {
        "steps": [
            'Press the brush guard clips inwards to remove the brush guard, and then lift the brushes out of the robot.',
            'Pull out the brushes. Use the appropriate cleaning tool to remove any hair tangled in the brushes. After cleaning, push the brushes firmly into the main brush holder until they click into place.',
            'With the screen-printed arrows facing upwards, insert the main brush holder into the slots downwards in an inclined way.',
            'Align the front end of the brush guard with the slot, insert it downwards in an inclined way, and then press it into place.',
        ],
        "notes": [
            'Be careful while pulling out the main brushes to prevent injury.',
        ],
    },
    'side_brush': {
        "steps": [
            'Unscrew the side brush with a screwdriver, clean the hair from the brush, and then screw it back on.',
        ],
        "notes": [],
    },
    'filter': {
        "steps": [
            'Remove the dust box filter, and then empty the dust box.',
            'Gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'dustbin': {
        "steps": [
            "Open the robot's cover and press the clip to remove the dust box.",
            'Remove the dust box filter, and then empty the dust box.',
            'Gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'mop_cloth': {
        "steps": [
            'Remove the water tank and the mop pad holder.',
            'Remove and clean the mop pad with water only, then dry it completely before reinstalling.',
        ],
        "notes": [],
    },
    'caster_wheel': {
        "steps": [
            'Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel. Do not use excessive force.',
            'Rinse the omnidirectional wheel under the running water and put it back after drying it completely.',
        ],
        "notes": [],
    },
    'sensor': {
        "steps": [
            'Wipe the robot sensors by using a soft and dry cloth: the laser distance sensor (LDS), 3D line laser sensor, dock sensors, edge sensor, cliff sensors and carpet sensor.',
        ],
        "notes": [
            'A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.',
        ],
    },
    'dust_bag': {
        "steps": [
            'Remove and discard the dust bag.',
            'Remove the dust and debris from the filter with a dry cloth.',
            'Install a new dust bag.',
            'Reinstall the dust tank cover.',
        ],
        "notes": [
            'Pulling outwards on the handle will seal the dust bag to prevent the dust and debris from accidentally falling out.',
        ],
    },
    'auto_empty_vents': {
        "steps": [
            'Clean the auto-empty vents of the robot and the base station with a soft and dry cloth.',
        ],
        "notes": [],
    },
    'clean_water_tank': {
        "steps": [
            'Pour out the water in the tank. Clean the tank with water only and leave it to air dry before reinstalling.',
            'If the water flow is slow or unevenly distributed, clean the air hole on the water inlet lid.',
        ],
        "notes": [
            'Do not directly expose the water tank to sunlight.',
        ],
    },
    'charging_contacts': {
        "steps": [
            'Clean the charging contacts and the signaling area with a soft and dry cloth.',
        ],
        "notes": [],
    },
}

# d20_plus — authored verbatim from api-fetch/dreame.vacuum.r2564b__1fb0f250.pdf
_D20_PLUS = {
    'main_brush': {
        "steps": [
            'Press the brush guard clips inwards to remove the brush guard, and then lift the brushes out of the robot.',
            'Pull out the brushes. Use the appropriate cleaning tool to remove any hair tangled in the brushes. After cleaning, push the brushes firmly into the main brush holder until they click into place.',
            'With the screen-printed arrows facing upwards, insert the main brush holder into the slots downwards in an inclined way.',
            'Align the front end of the brush guard with the slot, insert it downwards in an inclined way, and then press it into place.',
        ],
        "notes": [
            'Be careful while pulling out the main brushes to prevent injury.',
        ],
    },
    'side_brush': {
        "steps": [
            'Remove and clean the side brush.',
        ],
        "notes": [],
    },
    'filter': {
        "steps": [
            'Remove the dust box filter, and then empty the dust box.',
            'Gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'dustbin': {
        "steps": [
            "Open the robot's cover and press the clip to remove the dust box.",
            'Remove the dust box filter, and then empty the dust box.',
            'Gently tap the basket of the filter to remove the dirt.',
            'Rinse the dust box and filter with water and dry them completely before reinstalling.',
        ],
        "notes": [
            'Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.',
            'Rinse the dust box and filter with clean water only. Do not use any detergent.',
            'Use the dust box and filter only when they are completely dry.',
        ],
    },
    'mop_cloth': {
        "steps": [
            'Remove the water tank and the mop pad holder.',
            'Remove and clean the mop pad with water only, then dry it completely before reinstalling.',
            'Pour out the water in the tank. Clean the tank with water only and leave it to air dry before reinstalling.',
            'If the water flow is slow or unevenly distributed, clean the air hole on the water inlet lid.',
        ],
        "notes": [
            'Do not directly expose the water tank to sunlight.',
        ],
    },
    'caster_wheel': {
        "steps": [
            'Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel. Do not use excessive force.',
            'Rinse the omnidirectional wheel under the running water and put it back after drying it completely.',
        ],
        "notes": [],
    },
    'sensor': {
        "steps": [
            'Wipe the robot sensors by using a soft and dry cloth: the laser distance sensor (LDS), dock sensors, edge sensor and cliff sensors.',
        ],
        "notes": [
            'A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.',
        ],
    },
    'dust_bag': {
        "steps": [
            'Remove and discard the dust bag.',
            'Remove the dust and debris from the filter with a dry cloth.',
            'Install a new dust bag.',
            'Reinstall the dust tank cover.',
        ],
        "notes": [
            'Pulling outwards on the handle will seal the dust bag to prevent the dust and debris from accidentally falling out.',
        ],
    },
    'auto_empty_vents': {
        "steps": [
            'Clean the auto-empty vents of the robot and the base station with a soft and dry cloth.',
        ],
        "notes": [],
    },
    'charging_contacts': {
        "steps": [
            'Clean the charging contacts and the signaling area with a soft and dry cloth.',
        ],
        "notes": [],
    },
    'air_duct': {
        "steps": [
            'Unscrew mounting screws on the air duct cover and remove the cover.',
            'Check whether the air duct is blocked by foreign objects. If any, clean them.',
            'Reinstall the air duct cover.',
        ],
        "notes": [
            'If the air duct is blocked, please clean it according to the following steps.',
        ],
    },
}


# ============================ THE LIBRARY (inject the shared cadence) ============================
# ==== PILOT-FAMILIES-START ====
# e30_ultra - authored from the manual via the Sonnet->Haiku pipeline (pilot 2026-09-01)
_E30_ULTRA = {
    "main_brush": {
        "steps": [
            "Press the brush guard clips inwards to remove the brush guard and lift the brush out of the robot.",
            "Pull out the brush covers at both ends of the brush. Use a proper cleaning tool to remove any hair tangled in the brush. Reinstall the brush covers on both ends of the brush, and then reinstall the brush. Press on the brush guard to lock it in place."
        ],
        "notes": []
    },
    "side_brush": {
        "steps": [
            "Remove and clean the side brush."
        ],
        "notes": []
    },
    "filter": {
        "steps": [
            "Open the robot cover and press the dust box clip to remove the dust box.",
            "Open the dust box cover, remove the filter, and then empty the dust box.",
            "Gently tap the basket of the filter to remove the dirt.",
            "Rinse the dust box and filter with water and dry them completely before reinstalling."
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any detergent.",
            "Use the dust box and filter only when they are completely dry."
        ]
    },
    "dustbin": {
        "steps": [
            "Open the robot cover and press the dust box clip to remove the dust box.",
            "Open the dust box cover, remove the filter, and then empty the dust box.",
            "Gently tap the basket of the filter to remove the dirt.",
            "Rinse the dust box and filter with water and dry them completely before reinstalling."
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any detergent.",
            "Use the dust box and filter only when they are completely dry."
        ]
    },
    "dust_bag": {
        "steps": [
            "Remove the dust tank cover and discard the dust bag.",
            "Remove the dust and debris from the filter with a dry cloth.",
            "Install a new dust bag.",
            "Reinstall the dust tank cover."
        ],
        "notes": [
            "Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out."
        ]
    },
    "mop_cloth": {
        "steps": [
            "Remove the mop pad from the mop pad holder to replace it."
        ],
        "notes": []
    },
    "mop_pad_holder": {
        "steps": [
            "Remove and clean the mop pad holder."
        ],
        "notes": []
    },
    "caster_wheel": {
        "steps": [
            "Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.",
            "Rinse the omnidirectional wheel under the running water and put it back after drying it completely."
        ],
        "notes": [
            "Do not use excessive force."
        ]
    },
    "sensor": {
        "steps": [
            "Wipe robot sensors by using a soft and dry cloth."
        ],
        "notes": [
            "A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning."
        ]
    },
    "dock_contacts": {
        "steps": [
            "Clean the charging contacts and the signaling area with a soft and dry cloth."
        ],
        "notes": []
    },
    "auto_empty_vents": {
        "steps": [
            "Clean the auto-empty vents of the robot and the base station with a soft and dry cloth."
        ],
        "notes": []
    },
    "dirty_water_tank": {
        "steps": [
            "Remove the used water tank, open its cover and pour out the used water.",
            "Rinse the used water tank with clean water, and use a proper cleaning tool to clean the inner wall of the used water tank."
        ],
        "notes": [
            "The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it."
        ]
    },
    "washboard": {
        "steps": [
            "Enable the washboard base cleaning function in the app, and the robot will exit the base station automatically. Take out the washboard and wait for water to fill the bottom of the base station.",
            "Rinse the washboard with clean water, and use a proper cleaning tool to clean the bottom of the base station.",
            "After a moment, the base station will automatically pump out the used water. Then dry it with a soft and dry cloth, and put the washboard back into place.",
            "Use the app or briefly press the button on the robot to make it return to the base station."
        ],
        "notes": [
            "During cleaning, do not make the robot return to the base station."
        ]
    }
}

# e50_ultra - authored from the manual via the Sonnet->Haiku pipeline (pilot 2026-09-01)
_E50_ULTRA = {
    "main_brush": {
        "steps": [
            "Press the brush guard clips inwards to remove the brush guard and lift the brush out of the robot.",
            "Pull out the brush covers at both ends of the brush. Use a proper cleaning tool to remove any hair tangled in the brush. Reinstall the brush covers on both ends of the brush, and then reinstall the brush. Press on the brush guard to lock it in place."
        ],
        "notes": []
    },
    "side_brush": {
        "steps": [
            "Unscrew the side brush with a screwdriver, clean the hair from the brush, and then screw it back on."
        ],
        "notes": []
    },
    "filter": {
        "steps": [
            "Open the robot cover and press the dust box clip to remove the dust box.",
            "Open the dust box cover, remove the filter, and then empty the dust box.",
            "Gently tap the basket of the filter to remove the dirt.",
            "Rinse the dust box and filter with water and dry them completely before reinstalling."
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any detergent.",
            "Use the dust box and filter only when they are completely dry."
        ]
    },
    "dustbin": {
        "steps": [
            "Open the robot cover and press the dust box clip to remove the dust box.",
            "Open the dust box cover, remove the filter, and then empty the dust box.",
            "Gently tap the basket of the filter to remove the dirt.",
            "Rinse the dust box and filter with water and dry them completely before reinstalling."
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any detergent.",
            "Use the dust box and filter only when they are completely dry."
        ]
    },
    "dust_bag": {
        "steps": [
            "Remove the dust tank cover and discard the dust bag.",
            "Remove the dust and debris from the filter with a dry cloth.",
            "Install a new dust bag.",
            "Reinstall the dust tank cover."
        ],
        "notes": [
            "Pulling the handle outward will seal the bag to prevent the dust and debris from accidentally falling out."
        ]
    },
    "mop_cloth": {
        "steps": [
            "Remove the mop pad from the mop pad holder to replace it."
        ],
        "notes": []
    },
    "mop_pad_holder": {
        "steps": [
            "Remove and clean the mop pad holders."
        ],
        "notes": []
    },
    "caster_wheel": {
        "steps": [
            "Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.",
            "Rinse the omnidirectional wheel under the running water and put it back after drying it completely."
        ],
        "notes": [
            "Do not use excessive force."
        ]
    },
    "sensor": {
        "steps": [
            "Wipe the robot sensors by using a soft and dry cloth."
        ],
        "notes": [
            "A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning."
        ]
    },
    "dock_contacts": {
        "steps": [
            "Clean the auto-empty vents, charging contacts and the signaling area with a soft and dry cloth."
        ],
        "notes": []
    },
    "auto_empty_vents": {
        "steps": [
            "Clean the auto-empty vents, charging contacts and the signaling area with a soft and dry cloth."
        ],
        "notes": []
    },
    "dirty_water_tank": {
        "steps": [
            "Remove the used water tank, open its cover and pour out the used water.",
            "Rinse the used water tank with clean water, and use a proper cleaning tool to clean the inner wall of the used water tank."
        ],
        "notes": [
            "The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it."
        ]
    },
    "washboard_filter": {
        "steps": [
            "Take out the robot and remove the washboard filter after the mop pad cleaning is complete.",
            "Rinse the washboard filter with clean water, wipe it clean, and then reinstall it in the washboard.",
            "Use the app or press the button to return the robot to the base station, or manually put the robot back."
        ],
        "notes": []
    }
}

# l50_pro_ultra - authored from the manual via the Sonnet->Haiku pipeline (pilot 2026-09-01)
_L50_PRO_ULTRA = {
    "main_brush": {
        "steps": [
            "Press the brush guard clips inwards to remove the brush guard, and then lift the brushes out of the robot.",
            "Pull out the brushes. Use the provided cleaning tool to remove any hair tangled in the brushes. After cleaning, push the brushes firmly into the main brush holder until they click into place.",
            "With the screen-printed arrows facing upwards, insert the main brush holder into the slots downwards in an inclined way.",
            "Align the front end of the brush guard with the slot, insert it downwards in an inclined way, and then press it into place."
        ],
        "notes": [
            "Be careful while pulling out the main brushes to prevent injury."
        ]
    },
    "side_brush": {
        "steps": [
            "Unscrew the side brush with a screwdriver, clean the hair from the brush, and then screw it back on."
        ],
        "notes": []
    },
    "filter": {
        "steps": [
            "Remove the robot cover and press the dust box clip to remove the dust box.",
            "Remove the dust box filter, and then empty the dust box.",
            "Gently tap the basket of the filter to remove the dirt.",
            "Rinse the dust box and filter with water and dry them completely before reinstalling."
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any detergent.",
            "Use the dust box and filter only when they are completely dry."
        ]
    },
    "dustbin": {
        "steps": [
            "Remove the robot cover and press the dust box clip to remove the dust box.",
            "Remove the dust box filter, and then empty the dust box.",
            "Gently tap the basket of the filter to remove the dirt.",
            "Rinse the dust box and filter with water and dry them completely before reinstalling."
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any detergent.",
            "Use the dust box and filter only when they are completely dry."
        ]
    },
    "dust_bag": {
        "steps": [
            "Remove the dust tank cover and discard the dust bag.",
            "Remove the dust and debris from the filter with a dry cloth.",
            "Install a new dust bag.",
            "Reinstall the dust tank cover."
        ],
        "notes": [
            "Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out."
        ]
    },
    "mop_cloth": {
        "steps": [
            "Remove the mop pads from the mop pad holders to replace them."
        ],
        "notes": []
    },
    "mop_pad_holder": {
        "steps": [
            "Remove and clean the mop pad holders."
        ],
        "notes": []
    },
    "caster_wheel": {
        "steps": [
            "Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.",
            "Rinse the omnidirectional wheel under the running water and put it back after drying it completely."
        ],
        "notes": [
            "Do not use excessive force."
        ]
    },
    "main_wheel": {
        "steps": [
            "Rotate the auxiliary climbing wheel until the \"OUT\" arrow is facing upward, and then pull out the wheel.",
            "Use a proper tool to clean the hair tangled in the main wheel and auxiliary climbing wheel.",
            "After cleaning, rotate the main wheel to align the two arrows. Then, with the \"IN\" arrow facing downward, insert the left and right auxiliary climbing wheels accordingly until they click into place."
        ],
        "notes": []
    },
    "sensor": {
        "steps": [
            "Wipe the robot sensors by using a soft and dry cloth."
        ],
        "notes": []
    },
    "dock_contacts": {
        "steps": [
            "Clean the charging contacts and the signaling area with a soft and dry cloth."
        ],
        "notes": [
            "A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning."
        ]
    },
    "auto_empty_vents": {
        "steps": [
            "Clean the auto-empty vents of the robot and the base station with a soft and dry cloth."
        ],
        "notes": []
    },
    "dirty_water_tank": {
        "steps": [
            "Remove the used water tank, open its cover and pour out the used water.",
            "Rinse the used water tank with clean water, and use the provided cleaning tool to clean the inner wall of the used water tank."
        ],
        "notes": [
            "Be careful while pulling out the main brush to prevent injury."
        ]
    },
    "washboard_filter": {
        "steps": [
            "Take out the robot and remove the washboard filter after the mop pad cleaning is complete.",
            "Rinse the washboard filter with clean water, wipe it clean, and then reinstall it in the washboard.",
            "Use the app or press the button to return the robot to the base station, or manually put the robot back."
        ],
        "notes": []
    }
}

# l50s_ultra - authored from the manual via the Sonnet->Haiku pipeline (pilot 2026-09-01)
_L50S_ULTRA = {
    "main_brush": {
        "steps": [
            "Press the brush guard clips inwards to remove the brush guard, and then lift the brushes out of the robot.",
            "Pull out the brushes. Use a proper tool to remove any hair tangled in the brushes. After cleaning, push the brushes firmly into the main brush holder until they click into place.",
            "With the screen-printed arrows facing upwards, insert the main brush holder into the slots downwards in an inclined way.",
            "Align the front end of the brush guard with the slot, insert it downwards in an inclined way, and then press it into place."
        ],
        "notes": [
            "Be careful while pulling out the main brushes to prevent injury."
        ]
    },
    "side_brush": {
        "steps": [
            "Unscrew the side brush with a screwdriver, clean the hair from the brush, and then screw it back on."
        ],
        "notes": []
    },
    "filter": {
        "steps": [
            "Remove the robot cover and press the dust box clip to remove the dust box.",
            "Remove the dust box filter, and then empty the dust box.",
            "Gently tap the basket of the filter to remove the dirt.",
            "Rinse the dust box and filter with water and dry them completely before reinstalling."
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any detergent.",
            "Use the dust box and filter only when they are completely dry."
        ]
    },
    "dustbin": {
        "steps": [
            "Remove the robot cover and press the dust box clip to remove the dust box.",
            "Remove the dust box filter, and then empty the dust box.",
            "Gently tap the basket of the filter to remove the dirt.",
            "Rinse the dust box and filter with water and dry them completely before reinstalling."
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any detergent.",
            "Use the dust box and filter only when they are completely dry."
        ]
    },
    "dust_bag": {
        "steps": [
            "Remove the dust tank cover and discard the dust bag.",
            "Remove the dust and debris from the filter with a dry cloth.",
            "Install a new dust bag.",
            "Reinstall the dust tank cover."
        ],
        "notes": [
            "Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out."
        ]
    },
    "mop_cloth": {
        "steps": [
            "Remove the mop pads from the mop pad holders to replace them."
        ],
        "notes": []
    },
    "mop_pad_holder": {
        "steps": [
            "Remove and clean the mop pad holders."
        ],
        "notes": []
    },
    "caster_wheel": {
        "steps": [
            "Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.",
            "Rinse the omnidirectional wheel under the running water and put it back after drying it completely."
        ],
        "notes": [
            "Do not use excessive force."
        ]
    },
    "sensor": {
        "steps": [
            "Wipe the robot sensors by using a soft and dry cloth: Rear ToF Sensor, Bumper Window, Edge Sensor, Bumper, Cliff Sensors, Carpet Sensor."
        ],
        "notes": [
            "A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning."
        ]
    },
    "dock_contacts": {
        "steps": [
            "Clean the charging contacts and the signaling area with a soft and dry cloth."
        ],
        "notes": []
    },
    "auto_empty_vents": {
        "steps": [
            "Clean the auto-empty vents of the robot and the base station with a soft and dry cloth."
        ],
        "notes": []
    },
    "dirty_water_tank": {
        "steps": [
            "Remove the used water tank, open its cover and pour out the used water.",
            "Rinse the used water tank with clean water, and use a proper tool to clean the inner wall of the used water tank."
        ],
        "notes": [
            "The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it."
        ]
    },
    "washboard_filter": {
        "steps": [
            "Take out the robot and remove the washboard filter after the mop pad cleaning is complete.",
            "Rinse the washboard filter with clean water, wipe it clean, and then reinstall it in the washboard.",
            "Use the app or press the button to return the robot to the base station, or manually put the robot back."
        ],
        "notes": [
            "The washboard heating module may retain residual heat. To prevent scalding, be careful when removing the washboard filter."
        ]
    },
    "washboard_heating_module": {
        "steps": [
            "During use, the washboard heating module may develop scale. To remove it, take out the robot, pour a small amount of white vinegar (5% acetic acid) on the surface of the heating module and clean it with a proper tool."
        ],
        "notes": [
            "To prevent scalding, wait until the surface of the heating module cools down to room temperature before cleaning.",
            "An appropriate descaler can also be used in accordance with the instructions it provides.",
            "Do not add white vinegar or descaler directly into the clean water tank to help prevent malfunction.",
            "Do not use sharp tools or corrosive liquids such as hydrochloric acid to clean the heating module."
        ]
    }
}

# d20_ultra - authored from the manual via the Sonnet->Haiku pipeline (pilot 2026-09-01)
_D20_ULTRA = {
    "main_brush": {
        "steps": [
            "Press the brush guard clips inwards to remove the brush guard and lift the brush out of the robot.",
            "Pull out the brush covers at both ends of the brush. Use a proper cleaning tool to remove any hair tangled in the brush. Reinstall the brush covers on both ends of the brush, and then reinstall the brush.",
            "Press on the brush guard to lock it in place."
        ],
        "notes": []
    },
    "side_brush": {
        "steps": [
            "Remove and clean the side brush."
        ],
        "notes": []
    },
    "filter": {
        "steps": [
            "Open the robot cover and press the dust box clip to remove the dust box.",
            "Open the dust box cover, remove the filter, and then empty the dust box.",
            "Gently tap the basket of the filter to remove the dirt.",
            "Rinse the dust box and filter with water and dry them completely before reinstalling."
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any detergent.",
            "Use the dust box and filter only when they are completely dry."
        ]
    },
    "dustbin": {
        "steps": [
            "Open the robot cover and press the dust box clip to remove the dust box.",
            "Open the dust box cover, remove the filter, and then empty the dust box.",
            "Gently tap the basket of the filter to remove the dirt.",
            "Rinse the dust box and filter with water and dry them completely before reinstalling."
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any detergent.",
            "Use the dust box and filter only when they are completely dry."
        ]
    },
    "dust_bag": {
        "steps": [
            "Remove the dust tank cover and discard the dust bag.",
            "Remove the dust and debris from the filter with a dry cloth.",
            "Install a new dust bag.",
            "Reinstall the dust tank cover."
        ],
        "notes": [
            "Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out."
        ]
    },
    "mop_cloth": {
        "steps": [
            "Remove the mop pad from the mop pad holder to replace it."
        ],
        "notes": []
    },
    "mop_pad_holder": {
        "steps": [
            "Remove and clean the mop pad holder."
        ],
        "notes": []
    },
    "caster_wheel": {
        "steps": [
            "Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.",
            "Rinse the omnidirectional wheel under the running water and put it back after drying it completely."
        ],
        "notes": [
            "Do not use excessive force."
        ]
    },
    "sensor": {
        "steps": [
            "Wipe robot sensors by using a soft and dry cloth."
        ],
        "notes": [
            "A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning."
        ]
    },
    "dock_contacts": {
        "steps": [
            "Clean the charging contacts and the signaling area with a soft and dry cloth."
        ],
        "notes": []
    },
    "auto_empty_vents": {
        "steps": [
            "Clean the auto-empty vents of the robot and the base station with a soft and dry cloth."
        ],
        "notes": []
    },
    "dirty_water_tank": {
        "steps": [
            "Remove the used water tank, open its cover and pour out the used water.",
            "Rinse the used water tank with clean water, and use a proper cleaning tool to clean the inner wall of the used water tank."
        ],
        "notes": [
            "The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it."
        ]
    },
    "washboard": {
        "steps": [
            "Enable the washboard base cleaning function in the app, and the robot will exit the base station automatically. Take out the washboard and wait for water to fill the bottom of the base station.",
            "Rinse the washboard with clean water, and use a proper cleaning tool to clean the bottom of the base station.",
            "After a moment, the base station will automatically pump out the used water. Then dry it with a soft and dry cloth, and put the washboard back into place.",
            "Use the app or briefly press the button on the robot to make it return to the base station."
        ],
        "notes": [
            "During cleaning, do not make the robot return to the base station."
        ]
    }
}

# l40s_pro_ultra - authored from the manual via the Sonnet->Haiku pipeline (pilot 2026-09-01)
_L40S_PRO_ULTRA = {
    "main_brush": {
        "steps": [
            "Press the brush guard clips inwards to remove the brush guard, and then lift the brushes out of the robot.",
            "Pull out the brushes. Use the provided cleaning tool to remove any hair tangled in the brushes. After cleaning, push the brushes firmly into the main brush holder until they click into place.",
            "With the screen-printed arrows facing upwards, insert the main brush holder into the slots downwards in an inclined way.",
            "Align the front end of the brush guard with the slot, insert it downwards in an inclined way, and then press it into place."
        ],
        "notes": [
            "Be careful while pulling out the main brushes to prevent injury."
        ]
    },
    "side_brush": {
        "steps": [
            "Unscrew the side brush with a screwdriver, clean the hair from the brush, and then screw it back on."
        ],
        "notes": []
    },
    "filter": {
        "steps": [
            "Open the robot cover and press the dust box clip to remove the dust box.",
            "Remove the dust box filter, and then empty the dust box.",
            "Gently tap the basket of the filter to remove the dirt.",
            "Rinse the dust box and filter with water and dry them completely before reinstalling."
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any detergent.",
            "Use the dust box and filter only when they are completely dry."
        ]
    },
    "dustbin": {
        "steps": [
            "Open the robot cover and press the dust box clip to remove the dust box.",
            "Remove the dust box filter, and then empty the dust box.",
            "Gently tap the basket of the filter to remove the dirt.",
            "Rinse the dust box and filter with water and dry them completely before reinstalling."
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any detergent.",
            "Use the dust box and filter only when they are completely dry."
        ]
    },
    "dust_bag": {
        "steps": [
            "Remove the dust tank cover and discard the dust bag.",
            "Remove the dust and debris from the filter with a dry cloth.",
            "Install a new dust bag.",
            "Reinstall the dust tank cover."
        ],
        "notes": [
            "Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out."
        ]
    },
    "mop_cloth": {
        "steps": [
            "Remove the mop pads from the mop pad holders to replace them."
        ],
        "notes": []
    },
    "mop_pad_holder": {
        "steps": [
            "Remove and clean the mop pad holders."
        ],
        "notes": []
    },
    "caster_wheel": {
        "steps": [
            "Insert the omnidirectional wheel under the running water and put it back after drying it completely."
        ],
        "notes": [
            "Use tools such as a small screwdriver to separate the axle and tire of the omnidirectional wheel. Do not use excessive force."
        ]
    },
    "main_wheel": {
        "steps": [
            "Rotate the auxiliary climbing wheel until the \"OUT\" arrow is facing upward, and then pull out the wheel.",
            "Use a proper tool to clean the hair tangled in the main wheel and auxiliary climbing wheel.",
            "After cleaning, rotate the main wheel to align the two arrows. Then, with the \"IN\" arrow facing downward, insert the left and right auxiliary climbing wheels accordingly until they click into place."
        ],
        "notes": []
    },
    "sensor": {
        "steps": [
            "Wipe the robot sensors by using a soft and dry cloth: sensors: 1. Laser Distance Sensor (LDS) 2. 3D Dual-Line Laser Sensors 3. Bumper Window 4. Edge Sensor 5. Bumper 6. Cliff Sensors 7. Carpet Sensor."
        ],
        "notes": [
            "Wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning."
        ]
    },
    "dock_contacts": {
        "steps": [
            "Clean the charging contacts and the signaling area with a soft and dry cloth."
        ],
        "notes": []
    },
    "auto_empty_vents": {
        "steps": [
            "Clean the auto-empty vents of the robot and the base station with a soft and dry cloth."
        ],
        "notes": []
    },
    "dirty_water_tank": {
        "steps": [
            "Remove the used water tank, open its cover and pour out the used water.",
            "Rinse the used water tank with clean water, and use the provided cleaning tool to clean the inner wall of the used water tank."
        ],
        "notes": [
            "The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it."
        ]
    },
    "washboard_filter": {
        "steps": [
            "Take out the robot and remove the washboard filter after the mop pad cleaning is complete.",
            "Rinse the washboard filter with clean water, wipe it clean, and then reinstall it in the washboard.",
            "Use the app or press the button to return the robot to the base station, or manually put the robot back."
        ],
        "notes": []
    }
}
# ==== PILOT-FAMILIES-END ====

# ── P60 FAMILY (three trims on ONE platform, family+delta) ───────────────────────────────────
# P60 / P60 Pro / MOBIUS 60 are one platform (reg code RLV83LE) in three trims, and the TOP trim
# is the one that got EXPORTED under the MOBIUS name - which is why the only manual we hold for
# the family titles itself "MOBIUS 60 Robotic Vacuum Cleaner User Manual". Evidence they are one
# family: same twin spinning discs, same 82mm-class body, same 80C wash, and the SAME 3.2L dust
# bag (MOVA's own accessory listing covers E40/P50/Z60/MOBIUS/S70 with one part). Specs ladder
# rather than diverge - P60 24000Pa/8N/250rpm, P60 Pro 26000Pa/12N/260rpm, MOBIUS 30000Pa/100C.
#
# MOBIUS's UNIQUE FEATURE is the AI dual-arm pad SWAP with three stored pairs in the station. The
# CN trims have fixed discs, so the manual's mop_pad_holder step - "reinstall them into their
# corresponding docks on the base station hatch" - describes hardware they do not have. That is
# the ONLY divergence, so this is built family+delta per the module rule rather than by authoring
# a second flat table: MOBIUS's own family keeps the swap wording, the P60 trims override it.
# detergent_inlet is added back because the P-series takes MOVA's cleaning solution (accessory
# listing: E40/E50/P50...), which the Mobius table does not enumerate.
# ⚠ OPEN: if a P60 Pro station turns out to have pad docks after all, delete the override - one
# line - and the trims collapse onto mobius_60 exactly.
_P60 = _profile(
    GENERATED_FAMILIES['mobius_60'],
    override={'mop_pad_holder': _STANDARD['mop_pad_holder']},
    add={'detergent_inlet': _WASH_STATION['detergent_inlet']},
)

DREAME_UPKEEP_GUIDE_LIBRARY: dict[str, dict[str, dict]] = {
    # --- tier profiles: composed fallback for unauthored models ---
    'standard': _with_cadence(_profile(_STANDARD)),
    'auto_empty': _with_cadence(_profile(_STANDARD, _AUTO_EMPTY)),
    'wash_station': _with_cadence(_profile(_STANDARD, _AUTO_EMPTY, _WASH_STATION)),
    'wash_station_track': _with_cadence(_profile(_STANDARD, _AUTO_EMPTY, _WASH_STATION, override=_MOP_TRACK)),
    'wash_station_roller': _with_cadence(_profile(_STANDARD, _AUTO_EMPTY, _WASH_STATION, override=_MOP_ROLLER)),
    'wash_station_baseboard': _with_cadence(_profile(_STANDARD, _AUTO_EMPTY, _WASH_STATION, add=_BASEBOARD)),
    'p60': _with_cadence(_P60),
    # --- authored families: flat per-manual tables ---
    'x50': _with_cadence(_X50),
    'x50_master': _with_cadence(_X50_MASTER),
    'x60_ultra': _with_cadence(_X60_ULTRA),
    'l20': _with_cadence(_L20),
    'x40': _with_cadence(_X40),
    'l50': _with_cadence(_L50),
    'l10s_gen2': _with_cadence(_L10S_GEN2),
    'x60_pro_ultra_complete': _with_cadence(_X60_PRO_ULTRA_COMPLETE),
    'aqua10_ultra_track': _with_cadence(_AQUA10_ULTRA_TRACK),
    'aqua10_ultra_roller': _with_cadence(_AQUA10_ULTRA_ROLLER),
    'matrix10': _with_cadence(_MATRIX10),
    'l60_ultra': _with_cadence(_L60_ULTRA),
    'l60_ultra_pe': _with_cadence(_L60_ULTRA_PE),
    'l40s_ultra': _with_cadence(_L40S_ULTRA),
    'd30_ultra': _with_cadence(_D30_ULTRA),
    'd20_pro_plus': _with_cadence(_D20_PRO_PLUS),
    'd20_plus': _with_cadence(_D20_PLUS),
    'e30_ultra': _with_cadence(_E30_ULTRA),
    'e50_ultra': _with_cadence(_E50_ULTRA),
    'l50_pro_ultra': _with_cadence(_L50_PRO_ULTRA),
    'l50s_ultra': _with_cadence(_L50S_ULTRA),
    'd20_ultra': _with_cadence(_D20_ULTRA),
    'l40s_pro_ultra': _with_cadence(_L40S_PRO_ULTRA),
}

# ── GENERATED FAMILIES ───────────────────────────────────────────────────────────────────────
# 159 families extracted from each model's OWN English manual by the staged authoring pipeline
# and emitted deterministically (see dreame_upkeep_guides_generated.py). Merged here rather than
# inlined so the hand-authored families above stay untouched and the generated set regenerates
# (or backs out) as one unit. Cadence is STILL single-sourced: _with_cadence injects
# COMPONENT_FREQUENCIES, so no generated block carries a frequency of its own (DUG-9).
# A generated family NEVER shadows a hand-authored one — the emitter skips any key collision.
DREAME_UPKEEP_GUIDE_LIBRARY.update(
    {family: _with_cadence(components) for family, components in GENERATED_FAMILIES.items()}
)

# ── TRANSLATED FAMILIES ──────────────────────────────────────────────────────────────────────
# 91 families whose manual is NOT in English (87 Chinese, plus ru/ko/ja/de/nl/fr/it). Extracted
# from each model's OWN manual and translated DIRECT to English (never pivoted), anchored on
# Dreame's own English wording so terminology matches the rest of the library.
# ⚠ The NATIVE-language source text is preserved in durable/dreame-port-fixture/authoring/
# slices_nonen/ — when the per-language packs are built, LIFT the native language from there.
# Generating e.g. `zh` from this English would be CN->EN->CN and would discard Dreame's own
# Chinese wording. See .claude/notes/DESIGN-reverse-translate-provenance.md.
# Cadence still single-sourced via _with_cadence (DUG-9); a translated family never shadows a
# hand-authored or English-manual one (the emitter skips key collisions).
DREAME_UPKEEP_GUIDE_LIBRARY.update(
    {family: _with_cadence(components) for family, components in TRANSLATED_FAMILIES.items()}
)
