"""Dreame upkeep-guide library — maintenance-PROFILE tiers + per-family overrides.

    DREAME_UPKEEP_GUIDE_LIBRARY[family][component] = {
        "clean_frequency": str | None,
        "replace_frequency": str | None,
        "steps": list[str],
        "notes": list[str],
    }

Mirrors the Roborock/Eufy contract (adapters/roborock/roborock_upkeep_guides.py).

TWO KINDS OF FAMILY, one routing namespace (the manager does not distinguish them):

  * TIER profiles (standard / auto_empty / wash_station / _track / _roller /
    _baseboard) are the DEFAULT for the ~730 supported models with no authored
    manual. Each tier is a superset of the one above (dock deltas) with the mop as an
    override axis. The base prose is the MOST-COMPLETE wording measured across the nine
    authored lineups below — real Dreame text, serving as the representative profile.
    PROVISIONAL for the tail: a tail model's tier is name-derived (upkeep_catalog.py)
    and its washboard variant is not yet known, so wash_station carries BOTH the
    removable-filter and the serviceable-board components; refine per DEVICE_INFO.

  * AUTHORED families (x50, x60_ultra, x60_pro_ultra_complete, l20, x40, l50,
    l10s_gen2, aqua10_ultra_track, aqua10_ultra_roller) are MEASURED off their own
    manuals. Each is its tier MINUS the hardware it lacks, OVERRIDING every component
    whose manual states it differently. The Dreame lineup is NOT near-identical (unlike
    Roborock's): these override 6-10 of ~13 components. That is deliberate and measured
    — a "standard" family that let X60 prose stand for five other models was shipped
    once and reverted (commit d45e2ec4). The override is what keeps that from recurring:
    a family NEVER inherits base prose for a component its manual worded differently.

⚠ NOT WIRED. There is deliberately no BRAND_REGISTRARS row for Dreame; that row is the
switch, gated on a RELEASED upstream build carrying Tasshack #1707. Inert data, safe to
land ahead of it.

PROVENANCE — every authored string is Dreame's own text from ITS family's manual;
scripts/verify_dreame_guide_provenance.py scores each authored family against its manual
(the composed TIER keys reuse those same already-scored strings and are skipped there).
PURE DATA (no imports): scripts/sync-guide-translations.py loads this directly.

frequencies are per-component-TYPE (carried on the tier base, inherited by overrides),
stated as typical service intervals.
"""

from __future__ import annotations


def _profile(*groups, override=None, drop=(), add=None):
    """Compose a family: stack tier GROUPS, drop absent hardware, apply per-component
    OVERRIDES (steps/notes, inheriting the base frequencies), append ADDs. Copies deeply
    enough that families never alias each other's component dicts."""
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


# ============================ TIER COMPONENT GROUPS ============================
# base prose = most-complete wording across the nine authored lineups (the tail default).

#: on-bot components every robot has.
_STANDARD = {
    "main_brush": {
        "clean_frequency": "monthly",
        "replace_frequency": "every 6-12 months",
        "steps": [
            "Press the brush guard clips inwards to remove the brush guard, and then lift the brushes out of the robot.",
            "Pull out the brushes as shown in the figure. Use a proper tool to remove any hair tangled in the brushes. After cleaning, push the brushes firmly into the main brush holder until they click into place.",
            "With the screen-printed arrows facing upwards, insert the main brush holder into the slots downwards in an inclined way.",
            "Align the front end of the brush guard with the slot, insert it downwards in an inclined way, and then press it into place.",
        ],
        "notes": [
            "Be careful while pulling out the main brushes to prevent injury.",
        ],
    },
    "side_brush": {
        "clean_frequency": "monthly",
        "replace_frequency": "every 3-6 months",
        "steps": [
            "Unscrew the side brush with a screwdriver, clean the hair from the brush, and then screw it back on.",
        ],
        "notes": [],
    },
    "filter": {
        "clean_frequency": "weekly",
        "replace_frequency": "every 3-6 months",
        "steps": [
            "Open the dust box cover and remove the filter.",
            "Gently tap the basket of the filter to remove the dirt.",
            "Rinse the filter with water and dry it completely before reinstalling.",
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse with clean water only. Do not use any detergent.",
            "Use the filter only when it is completely dry.",
        ],
    },
    "dustbin": {
        "clean_frequency": "as needed",
        "replace_frequency": None,
        "steps": [
            "Open the robot cover and press the dust box clip to remove the dust box.",
            "Open the dust box cover, remove the filter, and then empty the dust box.",
            "Gently tap the basket of the filter to remove the dirt.",
            "Rinse the dust box and filter with water and dry them completely before reinstalling.",
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any detergent.",
            "Use the dust box and filter only when they are completely dry.",
        ],
    },
    "mop_cloth": {
        "clean_frequency": "after each use",
        "replace_frequency": "every 1-3 months",
        "steps": [
            "Press and slide the mop assembly clip at the illustrated angle to remove the mop assembly.",
            "Detach the mop from the bracket and use a proper tool to remove the hair tangled in the bracket.",
            "Install the new mop to the bracket, ensuring it is in place. Then firmly press the mop assembly clip to secure the mop.",
            "Push the mop assembly back into the compartment until it fits into the slot and clicks into place.",
        ],
        "notes": [
            "It is normal for the slot to rotate automatically during installation.",
        ],
    },
    "mop_pad_holder": {
        "clean_frequency": "every 1-2 months",
        "replace_frequency": None,
        "steps": [
            "Remove the mop assembly and fluffing roller from the robot. Clean the mop assembly compartment, wiper and filter to prevent blockage.",
            "Use a proper tool to remove any hair tangled in the roller. Then rinse it with water and dry it completely before reinstalling.",
        ],
        "notes": [],
    },
    "caster_wheel": {
        "clean_frequency": "monthly",
        "replace_frequency": None,
        "steps": [
            "Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.",
            "Rinse the omnidirectional wheel under the running water and put it back after drying it completely.",
        ],
        "notes": [
            "Do not use excessive force when separating the axle and tire.",
        ],
    },
    "sensor": {
        "clean_frequency": "monthly",
        "replace_frequency": None,
        "steps": [
            "Wipe the robot's sensors and charging contacts with a soft, dry cloth: the AI visual sensor, line laser sensors, LED fill lights, laser distance sensor (LDS), edge sensor, bumper, charging contacts, cliff sensors and carpet sensor.",
        ],
        "notes": [
            "A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.",
        ],
    },
}

#: + auto-empty dock.
_AUTO_EMPTY = {
    "dust_bag": {
        "clean_frequency": None,
        "replace_frequency": "every 2-4 months",
        "steps": [
            "Unlock the dust tank cover and then remove it.",
            "Discard the dust bag.",
            "Remove the dust and debris from the filter with a dry cloth.",
            "Install a new dust bag. Then install back the dust tank cover and lock it.",
        ],
        "notes": [
            "Pulling outwards on the handle will seal the dust bag to prevent the dust and debris from accidentally falling out.",
        ],
    },
    "auto_empty_vents": {
        "clean_frequency": "monthly",
        "replace_frequency": None,
        "steps": [
            "Clean the auto-empty vents of the robot and the base station with a soft and dry cloth.",
        ],
        "notes": [],
    },
}

#: + wash station. Carries BOTH washboard variants as a menu; a family keeps one.
_WASH_STATION = {
    "used_water_tank": {
        "clean_frequency": "after each use",
        "replace_frequency": None,
        "steps": [
            "Remove the used water tank, open its cover and pour out the used water.",
            "Rinse the used water tank with clean water, and use the provided cleaning tool to clean the inner wall of the used water tank.",
        ],
        "notes": [
            "The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it.",
        ],
    },
    "washboard": {
        "clean_frequency": "as needed",
        "replace_frequency": None,
        "steps": [
            "Enable the washboard base cleaning function in the app, and the robot will exit the base station automatically. Take out the washboard and wait for water to fill the washboard base.",
            "Use the cleaning tool to clean the washboard base. After a moment, the base station will automatically pump out the used water. Then wipe the washboard base with a soft and dry cloth.",
            "Flip the washboard over, remove the roller cover and the roller in turn, and then pull off the end caps of the roller.",
            "Remove the hair tangled in the roller, and then reassemble the parts according to corresponding colors.",
            "Rinse the washboard with clean water, wipe it clean and then put it back into the base station downwards in an inclined way.",
            "Use the app or briefly press the button on the robot to make it return to the base station.",
        ],
        "notes": [
            "If the roller cover is blocked by wipers on both sides of the washboard, rotate the roller to move them aside.",
            "During cleaning, do not make the robot return to the base station.",
        ],
    },
    "washboard_filter": {
        "clean_frequency": "every 1-2 months",
        "replace_frequency": None,
        "steps": [
            "Take out the robot and remove the washboard filter after the mop pad cleaning is complete.",
            "Rinse the washboard filter with clean water, wipe it clean, and then reinstall it in the washboard.",
            "Use the app or press the button to return the robot to the base station, or manually put the robot back.",
        ],
        "notes": [
            "The washboard heating module may retain residual heat. To prevent scalding, be careful when removing the washboard filter.",
        ],
    },
    "washboard_heating_module": {
        "clean_frequency": "as needed",
        "replace_frequency": None,
        "steps": [
            "During use, the washboard heating module may develop scale. To remove it, take out the robot, pour a small amount of white vinegar (5% acetic acid) on the surface of the heating module and clean it with a proper tool.",
        ],
        "notes": [
            "To prevent scalding, wait until the surface of the heating module cools down to room temperature before cleaning.",
            "An appropriate descaler can also be used in accordance with the instructions it provides.",
            "Do not add white vinegar or descaler directly into the clean water tank, to help prevent malfunction.",
            "Do not use sharp tools or corrosive liquids such as hydrochloric acid to clean the heating module.",
        ],
    },
    "dock_contacts": {
        "clean_frequency": "monthly",
        "replace_frequency": None,
        "steps": [
            "Clean the charging contacts and the signaling area of the base station with a soft and dry cloth.",
        ],
        "notes": [],
    },
    "detergent_inlet": {
        "clean_frequency": "as needed",
        "replace_frequency": None,
        "steps": [
            "If the cleaning solution adding inlet is dirty, wipe it with a soft and dry cloth.",
        ],
        "notes": [],
    },
}

#: mop OVERRIDE — tracked mop assembly (Aqua10 Ultra Track).
_MOP_TRACK = {
    "mop_cloth": {
        "clean_frequency": "after each use",
        "replace_frequency": "every 1-3 months",
        "steps": [
            "Press and slide the mop assembly clip at the illustrated angle to remove the mop assembly.",
            "Detach the mop from the bracket and use a proper tool to remove the hair tangled in the bracket.",
            "Install the new mop to the bracket, ensuring it is in place. Then firmly press the mop assembly clip to secure the mop.",
            "Push the mop assembly back into the compartment until it fits into the slot and clicks into place.",
        ],
        "notes": [
            "It is normal for the slot to rotate automatically during installation.",
        ],
    },
    "mop_pad_holder": {
        "clean_frequency": "every 1-2 months",
        "replace_frequency": None,
        "steps": [
            "Remove the mop assembly from the robot. Clean the mop assembly compartment and filter to prevent blockage.",
        ],
        "notes": [],
    },
}

#: mop OVERRIDE — roller mop assembly (Aqua10 Ultra Roller).
_MOP_ROLLER = {
    "mop_cloth": {
        "clean_frequency": "after each use",
        "replace_frequency": "every 1-3 months",
        "steps": [
            "Press the clip and slowly lift the mop assembly to remove it.",
            "Install the new mop assembly until it clicks into place.",
        ],
        "notes": [],
    },
    "mop_pad_holder": {
        "clean_frequency": "every 1-2 months",
        "replace_frequency": None,
        "steps": [
            "Remove the mop assembly and fluffing roller from the robot. Clean the mop assembly compartment, wiper and filter to prevent blockage.",
            "Use a proper tool to remove any hair tangled in the roller. Then rinse it with water and dry it completely before reinstalling.",
        ],
        "notes": [],
    },
}

#: add-on — baseboard/edge brush (X60 Pro Ultra Complete only).
_BASEBOARD = {
    "baseboard_brush": {
        "clean_frequency": None,
        "replace_frequency": None,
        "steps": [
            "After the baseboard cleaning task is complete, pull the cleaning brush upward to remove it, wipe the bristles with a clean damp cloth, and store it properly after air drying.",
        ],
        "notes": [],
    },
}


# ============================ AUTHORED-FAMILY OVERRIDES ============================
# each = the components whose manual wording differs from the tier base (steps/notes;
# frequencies inherited). Measured off the family's own manual — see verify_dreame_guide_provenance.py.

_X50_OVR = {
    "main_brush": {
        "steps": [
            "Press the brush guard clips inwards to remove the brush guard, and then lift the brushes out of the robot.",
            "Pull out the brushes. Use the provided cleaning tool to remove any hair tangled in the brushes. After cleaning, push the brushes firmly into the main brush holder until they click into place.",
            "With the screen-printed arrows facing upwards, insert the main brush holder into the slots downwards in an inclined way.",
            "Align the front end of the brush guard with the slot, insert it downwards in an inclined way, and then press it into place.",
        ],
        "notes": [
            "Be careful while pulling out the main brushes to prevent injury.",
        ],
    },
    "filter": {
        "steps": [
            "Remove the dust box filter and gently tap the basket of the filter to remove the dirt.",
            "Rinse the filter with clean water and dry it completely before reinstalling.",
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse with clean water only. Do not use any detergent.",
        ],
    },
    "dustbin": {
        "steps": [
            "Remove the robot cover and press the dust box clip to remove the dust box.",
            "Remove the dust box filter, and then empty the dust box.",
            "Gently tap the basket of the filter to remove the dirt.",
            "Rinse the dust box and filter with water and dry them completely before reinstalling.",
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any detergent.",
            "Use the dust box and filter only when they are completely dry.",
        ],
    },
    "mop_cloth": {
        "steps": [
            "Remove the mop pads from the mop pad holders to replace them.",
        ],
        "notes": [],
    },
    "mop_pad_holder": {
        "steps": [
            "Remove and clean the mop pad holders.",
        ],
        "notes": [],
    },
    "caster_wheel": {
        "steps": [
            "Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.",
            "Rinse the omnidirectional wheel under running water and put it back after drying it completely.",
        ],
        "notes": [
            "Do not use excessive force when separating the axle and tire.",
        ],
    },
    "sensor": {
        "steps": [
            "Wipe the robot sensors with a soft, dry cloth: the bumper window, 3D dual-line laser sensors, VersaLift sensor, edge sensor, bumper, cliff sensors and carpet sensor.",
        ],
        "notes": [
            "A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.",
        ],
    },
    "dust_bag": {
        "steps": [
            "Remove the dust tank cover and discard the dust bag.",
            "Remove the dust and debris from the filter with a dry cloth.",
            "Install a new dust bag.",
            "Reinstall the dust tank cover.",
        ],
        "notes": [
            "Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out.",
        ],
    },
    "washboard_filter": {
        "steps": [
            "Take out the robot and remove the washboard filter after the mop pad cleaning is complete.",
            "Rinse the washboard filter with clean water, wipe it clean, and then reinstall it in the washboard.",
            "Use the app or press the button to return the robot to the base station, or manually put the robot back.",
        ],
        "notes": [],
    },
    "dock_contacts": {
        "steps": [
            "Clean the charging contacts and the signaling area with a soft and dry cloth.",
        ],
        "notes": [],
    },
}

_X60_ULTRA_OVR = {
    "main_brush": {
        "steps": [
            "Press the brush guard clips inwards to remove the brush guard, and then lift the brushes out of the robot.",
            "Pull out the brushes. Use a proper tool to remove any hair tangled in the brushes. After cleaning, push the brushes firmly into the main brush holder until they click into place.",
            "With the screen-printed arrows facing upwards, insert the main brush holder into the slots downwards in an inclined way.",
            "Align the front end of the brush guard with the slot, insert it downwards in an inclined way, and then press it into place.",
        ],
        "notes": [
            "Be careful while pulling out the main brushes to prevent injury.",
        ],
    },
    "filter": {
        "steps": [
            "Remove the dust box filter and gently tap the basket of the filter to remove the dirt.",
            "Rinse the filter with clean water and dry it completely before reinstalling.",
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse with clean water only. Do not use any detergent.",
        ],
    },
    "dustbin": {
        "steps": [
            "Press the dust box clip to remove the dust box.",
            "Remove the dust box filter, and then empty the dust box. Gently tap the basket of the filter to remove the dirt.",
            "Rinse the dust box and filter with water and dry them completely before reinstalling.",
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any detergent.",
            "Use the dust box and filter only when they are completely dry.",
        ],
    },
    "mop_cloth": {
        "steps": [
            "Remove the mop pads from the mop pad holders to replace them.",
        ],
        "notes": [],
    },
    "mop_pad_holder": {
        "steps": [
            "Remove and clean the mop pad holders.",
        ],
        "notes": [],
    },
    "caster_wheel": {
        "steps": [
            "Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.",
            "Rinse the omnidirectional wheel under running water and put it back after drying it completely.",
        ],
        "notes": [
            "Do not use excessive force when separating the axle and tire.",
        ],
    },
    "sensor": {
        "steps": [
            "Wipe the robot sensors with a soft, dry cloth: the VersaLift sensor, bumper window, edge sensor, bumper, cliff sensors, dust illumination light and carpet sensor.",
        ],
        "notes": [
            "A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.",
        ],
    },
    "dust_bag": {
        "steps": [
            "Remove the dust tank cover and discard the dust bag.",
            "Remove the dust and debris from the filter with a dry cloth.",
            "Install a new dust bag and reinstall the dust tank cover.",
        ],
        "notes": [
            "Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out.",
        ],
    },
    "used_water_tank": {
        "steps": [
            "Remove the used water tank, open its cover and pour out the used water.",
            "Rinse the used water tank with clean water, and use a proper tool to clean the inner wall of the used water tank.",
        ],
        "notes": [
            "The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it.",
        ],
    },
    "dock_contacts": {
        "steps": [
            "Clean the auto-empty vents, charging contacts and the signaling area with a soft and dry cloth.",
        ],
        "notes": [],
    },
}

_L20_OVR = {
    "main_brush": {
        "steps": [
            "Press the brush guard clips inwards to remove the brush guard and lift the brush out of the robot.",
            "Pull out the brush covers at both ends of the brush. Use the provided cleaning tool to remove any hair tangled in the brush. Reinstall the brush covers on both ends of the brush, and then reinstall the brush. Press on the brush guard to lock it in place.",
        ],
        "notes": [],
    },
    "side_brush": {
        "steps": [
            "Remove and clean the side brush and mop pad holder.",
        ],
        "notes": [],
    },
    "filter": {
        "steps": [
            "Remove the filter and tap its basket gently.",
            "Rinse the dust box and filter with water and dry them completely before reinstalling.",
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any detergent.",
            "Use the dust box and filter only when they are completely dry.",
        ],
    },
    "dustbin": {
        "steps": [
            "Open the robot's cover and press the clip to remove the dust box.",
            "Open the dust box cover and empty the dust box.",
        ],
        "notes": [],
    },
    "mop_cloth": {
        "steps": [
            "Remove the mop pad from the mop pad holder to replace it.",
        ],
        "notes": [],
    },
    "mop_pad_holder": {
        "steps": [
            "Remove and clean the side brush and mop pad holder.",
        ],
        "notes": [],
    },
    "caster_wheel": {
        "steps": [
            "Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.",
            "Rinse the omnidirectional wheel under running water and put it back after drying it completely.",
        ],
        "notes": [
            "Do not use excessive force when separating the axle and tire.",
        ],
    },
    "washboard": {
        "steps": [
            "Press the button to make the robot exit the base station.",
            "Remove the washboard and rinse it with clean water.",
            "Press and hold the button for 3 seconds to add water to the bottom of the base station. Then use the included cleaning tool to clean it.",
            "Press and hold the button for 3 seconds to pump out the used water in the bottom of the base station, dry it with a soft and dry cloth, and then put the washboard back.",
        ],
        "notes": [],
    },
}

_X40_OVR = {
    "main_brush": {
        "steps": [
            "Press the brush guard clips inwards to remove the brush guard and lift the brush out of the robot.",
            "Pull out the brush covers at both ends of the brush. Use the provided cleaning tool to remove any hair tangled in the brush. Reinstall the brush covers on both ends of the brush, and then reinstall the brush. Press on the brush guard to lock it in place.",
        ],
        "notes": [],
    },
    "filter": {
        "steps": [
            "Remove the dust box filter and gently tap the basket of the filter to remove the dirt.",
            "Rinse the filter with clean water and dry it completely before reinstalling.",
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse with clean water only. Do not use any detergent.",
        ],
    },
    "mop_cloth": {
        "steps": [
            "Remove the mop pad from the mop pad holder to replace it.",
        ],
        "notes": [],
    },
    "mop_pad_holder": {
        "steps": [
            "Remove and clean the mop pad holder.",
        ],
        "notes": [],
    },
    "caster_wheel": {
        "steps": [
            "Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.",
            "Rinse the omnidirectional wheel under running water and put it back after drying it completely.",
        ],
        "notes": [
            "Do not use excessive force when separating the axle and tire.",
        ],
    },
    "sensor": {
        "steps": [
            "Wipe the robot's sensors and charging contacts with a soft, dry cloth: the bumper window, laser distance sensor (LDS), 3D dual-line laser sensors, edge sensor, bumper, charging contacts, cliff sensors and carpet sensor.",
        ],
        "notes": [
            "A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.",
        ],
    },
    "dust_bag": {
        "steps": [
            "Remove the dust tank cover and discard the dust bag.",
            "Remove the dust and debris from the filter with a dry cloth.",
            "Install a new dust bag.",
            "Reinstall the dust tank cover.",
        ],
        "notes": [
            "Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out.",
        ],
    },
}

_L50_OVR = {
    "main_brush": {
        "steps": [
            "Press the brush guard clips inwards to remove the brush guard, and then lift the brushes out of the robot.",
            "Pull out the brushes. Use the provided cleaning tool to remove any hair tangled in the brushes. After cleaning, push the brushes firmly into the main brush holder until they click into place.",
            "With the screen-printed arrows facing upwards, insert the main brush holder into the slots downwards in an inclined way.",
            "Align the front end of the brush guard with the slot, insert it downwards in an inclined way, and then press it into place.",
        ],
        "notes": [
            "Be careful while pulling out the main brushes to prevent injury.",
        ],
    },
    "filter": {
        "steps": [
            "Remove the dust box filter and gently tap the basket of the filter to remove the dirt.",
            "Rinse the filter with clean water and dry it completely before reinstalling.",
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse with clean water only. Do not use any detergent.",
        ],
    },
    "dustbin": {
        "steps": [
            "Open the robot cover and press the dust box clip to remove the dust box.",
            "Remove the dust box filter, and then empty the dust box.",
            "Gently tap the basket of the filter to remove the dirt.",
            "Rinse the dust box and filter with water and dry them completely before reinstalling.",
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any detergent.",
            "Use the dust box and filter only when they are completely dry.",
        ],
    },
    "mop_cloth": {
        "steps": [
            "Remove the mop pads from the mop pad holders to replace them.",
        ],
        "notes": [],
    },
    "mop_pad_holder": {
        "steps": [
            "Remove and clean the mop pad holders.",
        ],
        "notes": [],
    },
    "caster_wheel": {
        "steps": [
            "Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.",
            "Rinse the omnidirectional wheel under running water and put it back after drying it completely.",
        ],
        "notes": [
            "Do not use excessive force when separating the axle and tire.",
        ],
    },
    "sensor": {
        "steps": [
            "Wipe the robot sensors with a soft, dry cloth: the 3D dual-line laser sensors, bumper window, edge sensor, laser distance sensor (LDS), cliff sensors, carpet sensor and bumper.",
        ],
        "notes": [
            "A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.",
        ],
    },
    "dust_bag": {
        "steps": [
            "Remove the dust tank cover and discard the dust bag.",
            "Remove the dust and debris from the filter with a dry cloth.",
            "Install a new dust bag.",
            "Reinstall the dust tank cover.",
        ],
        "notes": [
            "Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out.",
        ],
    },
    "washboard_filter": {
        "steps": [
            "Take out the robot and remove the washboard filter after the mop pad cleaning is complete.",
            "Rinse the washboard filter with clean water, wipe it clean, and then reinstall it in the washboard.",
            "Use the app or press the button to return the robot to the base station, or manually put the robot back.",
        ],
        "notes": [],
    },
    "dock_contacts": {
        "steps": [
            "Clean the charging contacts and the signaling area with a soft and dry cloth.",
        ],
        "notes": [],
    },
}

_L10S_GEN2_OVR = {
    "main_brush": {
        "steps": [
            "Press the brush guard clips inwards to remove the brush guard and lift the brush out of the robot.",
            "Pull out the brush covers at both ends of the brush. Use the provided cleaning tool to remove any hair tangled in the brush. Reinstall the brush covers on both ends of the brush, and then reinstall the brush. Press on the brush guard to lock it in place.",
        ],
        "notes": [],
    },
    "side_brush": {
        "steps": [
            "Remove and clean the side brush.",
        ],
        "notes": [],
    },
    "mop_cloth": {
        "steps": [
            "Remove the mop pad from the mop pad holder to replace it.",
        ],
        "notes": [],
    },
    "mop_pad_holder": {
        "steps": [
            "Remove and clean the mop pad holder.",
        ],
        "notes": [],
    },
    "caster_wheel": {
        "steps": [
            "Use a tool such as a small screwdriver to separate the axle and tire of the omnidirectional wheel.",
            "Rinse the omnidirectional wheel under running water and put it back after drying it completely.",
        ],
        "notes": [
            "Do not use excessive force when separating the axle and tire.",
        ],
    },
    "sensor": {
        "steps": [
            "Wipe the robot sensors with a soft, dry cloth: the carpet sensor, cliff sensors, bumper, edge sensor, laser distance sensor (LDS) and 3D line laser sensor.",
        ],
        "notes": [
            "A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.",
        ],
    },
    "dust_bag": {
        "steps": [
            "Remove the dust tank cover and discard the dust bag.",
            "Remove the dust and debris from the filter with a dry cloth.",
            "Install a new dust bag.",
            "Reinstall the dust tank cover.",
        ],
        "notes": [
            "Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out.",
        ],
    },
    "washboard": {
        "steps": [
            "Take out the robot from the base station.",
            "Take out the washboard and open the filter cover. Rinse the washboard with clean water and clean it with the provided cleaning tool. After cleaning, close the cover and wipe the washboard with a soft and dry cloth.",
            "Wipe the washboard base clean, and put the washboard back into the base station.",
            "Use the app or briefly press the button on the robot to make it return to the base station.",
        ],
        "notes": [
            "During cleaning, do not make the robot return to the base station.",
        ],
    },
    "dock_contacts": {
        "steps": [
            "Clean the charging contacts and the signaling area with a soft and dry cloth.",
        ],
        "notes": [],
    },
}

_AQUA10_TRACK_OVR = {
    "dustbin": {
        "steps": [
            "Remove the robot cover and press the dust box clip to remove the dust box.",
            "Open the dust box cover, remove the filter, and then empty the dust box. Gently tap the basket of the filter to remove the dirt.",
            "Rinse the dust box and filter with water and dry them completely before reinstalling.",
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any detergent.",
            "Use the dust box and filter only when they are completely dry.",
        ],
    },
    "sensor": {
        "steps": [
            "Wipe the robot sensors by using a soft and dry cloth: the bumper window, VersaLift sensor, edge sensor, bumper, cliff sensors and carpet sensor.",
        ],
        "notes": [
            "A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.",
        ],
    },
    "dust_bag": {
        "steps": [
            "Remove the dust tank cover and discard the dust bag.",
            "Remove the dust and debris from the filter with a dry cloth.",
            "Install a new dust bag.",
            "Reinstall the dust tank cover.",
        ],
        "notes": [
            "Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out.",
        ],
    },
    "used_water_tank": {
        "steps": [
            "Remove the used water tank, open its cover and pour out the used water.",
            "Rinse the used water tank with clean water, and use a proper tool to clean the inner wall of the used water tank.",
        ],
        "notes": [
            "The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it.",
        ],
    },
    "washboard_filter": {
        "steps": [
            "Take out the robot and remove the washboard filter after the mop cleaning is complete.",
            "Rinse the washboard filter with clean water, wipe it clean, and then reinstall it in the washboard.",
            "Use the app or press the button to return the robot to the base station, or manually put the robot back.",
        ],
        "notes": [
            "The washboard heating module may retain residual heat. To prevent scalding, be careful when removing the washboard filter.",
        ],
    },
    "washboard_heating_module": {
        "steps": [
            "During use, the washboard heating module may develop scale. To remove it, take out the robot, pour a small amount of white vinegar (5% acetic acid) on the surface of the heating module and clean it with a proper tool.",
        ],
        "notes": [
            "To prevent scalding, wait until the surface of the heating module cools down to room temperature before cleaning.",
            "An appropriate descaler can also be used in accordance with the instructions it provides.",
            "Do not add white vinegar or descaler directly into the clean water tank to help prevent malfunction.",
            "Do not use sharp tools or corrosive liquids such as hydrochloric acid to clean the heating module.",
        ],
    },
    "dock_contacts": {
        "steps": [
            "Clean the charging contacts and the signaling area with a soft and dry cloth.",
        ],
        "notes": [],
    },
}

_AQUA10_ROLLER_OVR = {
    "dustbin": {
        "steps": [
            "Remove the robot cover and press the dust box clip to remove the dust box.",
            "Open the dust box cover, remove the filter, and then empty the dust box. Gently tap the basket of the filter to remove the dirt.",
            "Rinse the dust box and filter with water and dry them completely before reinstalling.",
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any detergent.",
            "Use the dust box and filter only when they are completely dry.",
        ],
    },
    "sensor": {
        "steps": [
            "Wipe the robot sensors by using a soft and dry cloth: the bumper window, VersaLift sensor, edge sensor, bumper, cliff sensors and carpet sensor.",
        ],
        "notes": [
            "A wet cloth can damage sensitive elements within the robot and the base station. Please use a dry cloth for cleaning.",
        ],
    },
    "dust_bag": {
        "steps": [
            "Remove the dust tank cover and discard the dust bag.",
            "Remove the dust and debris from the filter with a dry cloth.",
            "Install a new dust bag.",
            "Reinstall the dust tank cover.",
        ],
        "notes": [
            "Pulling upwards on the handle will seal the bag to prevent the dust and debris from accidentally falling out.",
        ],
    },
    "used_water_tank": {
        "steps": [
            "Remove the used water tank, open its cover and pour out the used water.",
            "Rinse the used water tank with clean water, and use a proper tool to clean the inner wall of the used water tank.",
        ],
        "notes": [
            "The float ball in the used water tank is a movable part. Do not apply too much force when cleaning it to avoid damaging it.",
        ],
    },
    "washboard": {
        "steps": [
            "Take out the robot and remove the washboard after the mop cleaning is complete. Then rinse the washboard with clean water and wipe it clean.",
            "During use, the heating module may develop scale. To remove it, take out the robot, pour a small amount of white vinegar (5% acetic acid) on the surface of the heating module and clean it with a proper tool. Then reinstall the washboard.",
            "Use the app or press the button to return the robot to the base station, or manually put the robot back.",
        ],
        "notes": [
            "The heating module under the washboard may retain residual heat. To prevent scalding, be careful when removing the washboard.",
            "To prevent scalding, wait until the surface of the heating module cools down to room temperature before cleaning.",
            "An appropriate descaler can also be used in accordance with the instructions it provides.",
            "Do not add white vinegar or descaler directly into the clean water tank to help prevent malfunction.",
            "Do not use sharp tools or corrosive liquids such as hydrochloric acid to clean the heating module.",
        ],
    },
    "dock_contacts": {
        "steps": [
            "Clean the charging contacts and the signaling area with a soft and dry cloth.",
        ],
        "notes": [],
    },
}


# ============================ THE LIBRARY ============================
DREAME_UPKEEP_GUIDE_LIBRARY: dict[str, dict[str, dict]] = {
    # --- tier profiles: the default for unauthored models (upkeep_catalog.py maps to these) ---
    "standard": _profile(_STANDARD),
    "auto_empty": _profile(_STANDARD, _AUTO_EMPTY),
    "wash_station": _profile(_STANDARD, _AUTO_EMPTY, _WASH_STATION),
    "wash_station_track": _profile(_STANDARD, _AUTO_EMPTY, _WASH_STATION, override=_MOP_TRACK),
    "wash_station_roller": _profile(_STANDARD, _AUTO_EMPTY, _WASH_STATION, override=_MOP_ROLLER),
    "wash_station_baseboard": _profile(_STANDARD, _AUTO_EMPTY, _WASH_STATION, add=_BASEBOARD),
    # --- authored families: measured off their own manuals (override the tier where it differs) ---
    "x50": _profile(_STANDARD, _AUTO_EMPTY, _WASH_STATION, override=_X50_OVR, drop=("washboard", "washboard_heating_module", "detergent_inlet")),
    "x60_ultra": _profile(_STANDARD, _AUTO_EMPTY, _WASH_STATION, override=_X60_ULTRA_OVR, drop=("auto_empty_vents", "washboard", "detergent_inlet")),
    "l20": _profile(_STANDARD, _AUTO_EMPTY, _WASH_STATION, override=_L20_OVR, drop=("washboard_filter", "washboard_heating_module")),
    "x40": _profile(_STANDARD, _AUTO_EMPTY, _WASH_STATION, override=_X40_OVR, drop=("washboard_filter", "washboard_heating_module", "detergent_inlet")),
    "l50": _profile(_STANDARD, _AUTO_EMPTY, _WASH_STATION, override=_L50_OVR, drop=("washboard", "washboard_heating_module", "detergent_inlet")),
    "l10s_gen2": _profile(_STANDARD, _AUTO_EMPTY, _WASH_STATION, override=_L10S_GEN2_OVR, drop=("washboard_filter", "washboard_heating_module", "detergent_inlet")),
    "x60_pro_ultra_complete": _profile(
        _STANDARD, _AUTO_EMPTY, _WASH_STATION, override=_X60_ULTRA_OVR,
        drop=("auto_empty_vents", "washboard", "detergent_inlet"), add=_BASEBOARD,
    ),
    "aqua10_ultra_track": _profile(_STANDARD, _AUTO_EMPTY, _WASH_STATION, override={**_MOP_TRACK, **_AQUA10_TRACK_OVR}, drop=("washboard", "detergent_inlet")),
    "aqua10_ultra_roller": _profile(_STANDARD, _AUTO_EMPTY, _WASH_STATION, override={**_MOP_ROLLER, **_AQUA10_ROLLER_OVR}, drop=("washboard_filter", "washboard_heating_module", "detergent_inlet")),
}
