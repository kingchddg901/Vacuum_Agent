"""Dreame upkeep guide library — manufacturer text, composed per robot trim.

``DREAME_UPKEEP_GUIDE_LIBRARY[guide_family][component] = {"steps": [...], "notes": [...]}``

Mirrors ``adapters/roborock/roborock_upkeep_guides.py``. Component keys are the
FRAMEWORK's vocabulary (``main_brush``, ``side_brush``, ``filter``, ``sensor``,
``dustbin``, ``mop_cloth``, ``caster_wheel``, ``main_wheel``), not Dreame's wording —
a guide keyed to a brand's own noun resolves for nobody.

⚠ NOT WIRED. There is deliberately no ``BRAND_REGISTRARS`` row for Dreame; that row is
the switch, and the adapter is gated on a RELEASED upstream build carrying Tasshack
issue #1707. This file is inert data and safe to land ahead of it.

PROVENANCE — every string is Dreame's own text, each family transcribed from ITS OWN
manual, read page by page:

  ``x60``        R6001-X60_Series, EN pp. 15-16
  ``l10s_gen2``  R2469X-L10s_Ultra_Gen_2, EN pp. 19-25

Manuals are mirrored in the git-ignored fixture set. Guide content is AI-authored by
default and transferred only when a manual is genuinely in hand; for these two it is.

⚠ EACH FAMILY IS AUTHORED WHOLE. NOTHING IS SHARED, AND THE FIRST CUT OF THIS FILE WAS
WRONG TO SHARE IT.
------------------------------------------------------------------------------------
A component matrix across six platforms showed the same PARTS on all of them, and that
was read — by me — as evidence the STEPS were shared. They are different claims.
Measured directly afterwards, of the **eleven component keys the X60 and the L10s Gen 2
have in common, exactly ONE (`caster_wheel`) has identical steps.** The other ten
differ, six of them while having the same number of steps, which is why a shape check
does not catch it.

The differences are hardware:

  * side brush — Gen 2 "remove and clean", X60 "unscrew with a screwdriver"
  * dust box   — Gen 2 opens the ROBOT COVER first; X60 does not have one
  * main brush — Gen 2 has end covers and a provided tool; the X60's anti-tangle
    brush has neither, and takes four steps to the Gen 2's two
  * contacts   — Gen 2 is TWO sections (contacts+signalling, then auto-empty vents);
    the X60 combines all three
  * washboard  — Gen 2 has a removable BASE with a filter cover; the X60 has a
    separate washboard filter plus a heating module

Following X60 text on a Gen 2 tells the owner to unscrew a brush that clips and to
skip a cover that must be opened. So: **add a family only from that family's manual**,
and do not factor a shared base out of two families because their component NAMES line
up. `feedback_partial_guard_blind_spot`, and the manual inventory's own rule — lift the
vocabulary, never the prose.

⚠ READ THE PAGES, DO NOT SCRIPT THEM. `Routine Maintenance` locates the care section
reliably (l20 pp20-26, x40 19-26, l10s_gen2 18-25, x50 22-30, l50 23-30) — but PDF text
extraction interleaves adjacent columns, so a collapsed extract of the Gen 2 "Main
Brush" block arrives with used-water-tank sentences inside it. Automate the FINDING;
read the pages.

An unauthored family yields ``{}`` from ``library[family][component]``, so a device
with no family here gets NO guide. That is the correct failure: silence beats confident
wrong instructions about someone's hardware.

⚠ DREAME VARIES ON THE OPPOSITE AXIS TO ROBOROCK. Roborock's suffixes buy DOCK hardware
(``+`` = auto-empty, ``Ultra`` = wash station), so its families are dock tiers. Dreame's
buy ROBOT hardware — X60 Ultra to X60 Max Ultra Complete adds a chassis lift, a carpet
pressure plate, an extending side brush and heated pads while the dock stays put — so
its families are robot trims.

**Do not infer the family from the model name.** The r-code maps a device to its
family; whether a dock has a dust bag to service is answered by live entity presence,
not by counting words in "X60 Max Ultra Complete".
"""

from __future__ import annotations


# --------------------------------------------------------------------------
# The X60 series' components. NOT a shared base — measured against the L10s Gen 2,
# only ONE of eleven common component keys (caster_wheel) has identical steps.
# --------------------------------------------------------------------------
_X60_BASE: dict[str, dict] = {
    "main_brush": {
        "steps": [
            "Press the brush guard clips inwards to remove the brush guard, and then "
            "lift the brushes out of the robot.",
            "Pull out the brushes. Use a proper tool to remove any hair tangled in the "
            "brushes. After cleaning, push the brushes firmly into the main brush "
            "holder until they click into place.",
            "With the screen-printed arrows facing upwards, insert the main brush "
            "holder into the slots downwards in an inclined way.",
            "Align the front end of the brush guard with the slot, insert it downwards "
            "in an inclined way, and then press it into place.",
        ],
        "notes": [
            "Be careful while pulling out the main brushes to prevent injury.",
        ],
    },
    "side_brush": {
        "steps": [
            "Unscrew the side brush with a screwdriver, clean the hair from the brush, "
            "and then screw it back on.",
        ],
        "notes": [],
    },
    "dustbin": {
        "steps": [
            "Press the dust box clip to remove the dust box.",
            "Remove the dust box filter, and then empty the dust box. Gently tap the "
            "basket of the filter to remove the dirt.",
            "Rinse the dust box and filter with water and dry them completely before "
            "reinstalling.",
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp "
            "objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any "
            "detergent.",
            "Use the dust box and filter only when they are completely dry.",
        ],
    },
    "filter": {
        "steps": [
            "Remove the dust box filter and gently tap the basket of the filter to "
            "remove the dirt.",
            "Rinse the filter with clean water and dry it completely before "
            "reinstalling.",
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp "
            "objects to prevent damage.",
            "Rinse with clean water only. Do not use any detergent.",
        ],
    },
    "mop_cloth": {
        "steps": [
            "Remove the mop pads from the mop pad holders to replace them.",
        ],
        "notes": [],
    },
    "mop_pad_holder": {
        "steps": ["Remove and clean the mop pad holders."],
        "notes": [],
    },
    "caster_wheel": {
        "steps": [
            "Use a tool such as a small screwdriver to separate the axle and tire of "
            "the omnidirectional wheel.",
            "Rinse the omnidirectional wheel under running water and put it back after "
            "drying it completely.",
        ],
        "notes": ["Do not use excessive force when separating the axle and tire."],
    },
    "used_water_tank": {
        "steps": [
            "Remove the used water tank, open its cover and pour out the used water.",
            "Rinse the used water tank with clean water, and use a proper tool to "
            "clean the inner wall of the used water tank.",
        ],
        "notes": [
            "The float ball in the used water tank is a movable part. Do not apply too "
            "much force when cleaning it to avoid damaging it.",
        ],
    },
    "dust_bag": {
        "steps": [
            "Remove the dust tank cover and discard the dust bag.",
            "Remove the dust and debris from the filter with a dry cloth.",
            "Install a new dust bag and reinstall the dust tank cover.",
        ],
        "notes": [
            "Pulling upwards on the handle will seal the bag to prevent the dust and "
            "debris from accidentally falling out.",
        ],
    },
    "washboard_filter": {
        "steps": [
            "Take out the robot and remove the washboard filter after the mop pad "
            "cleaning is complete.",
            "Rinse the washboard filter with clean water, wipe it clean, and then "
            "reinstall it in the washboard.",
            "Use the app or press the button to return the robot to the base station, "
            "or manually put the robot back.",
        ],
        "notes": [
            "The washboard heating module may retain residual heat. To prevent "
            "scalding, be careful when removing the washboard filter.",
        ],
    },
    "dock_contacts": {
        "steps": [
            "Clean the auto-empty vents, charging contacts and the signaling area with "
            "a soft and dry cloth.",
        ],
        "notes": [],
    },
}


# --------------------------------------------------------------------------
# Per-trim overlays. Only what genuinely differs — see the matrix in the docstring.
# --------------------------------------------------------------------------

#: Sensor wipe-down. The LIST of sensors is trim-specific, which is why `sensor` is an
#: overlay rather than shared: the X60 adds VersaLift and the dust illumination light,
#: while the earlier platforms carry a 3D line-laser the X60 dropped entirely.
_SENSOR_NOTE = (
    "A wet cloth can damage sensitive elements within the robot and the base station. "
    "Please use a dry cloth for cleaning."
)

_SENSORS_X60 = {
    "sensor": {
        "steps": [
            "Wipe the robot sensors with a soft, dry cloth: the VersaLift sensor, "
            "bumper window, edge sensor, bumper, cliff sensors, dust illumination "
            "light and carpet sensor.",
        ],
        "notes": [_SENSOR_NOTE],
    },
}

_X60_ONLY = {
    "washboard_heating_module": {
        "steps": [
            "During use, the washboard heating module may develop scale. To remove it, "
            "take out the robot, pour a small amount of white vinegar (5% acetic acid) "
            "on the surface of the heating module and clean it with a proper tool.",
        ],
        "notes": [
            "To prevent scalding, wait until the surface of the heating module cools "
            "down to room temperature before cleaning.",
            "An appropriate descaler can also be used in accordance with the "
            "instructions it provides.",
            "Do not add white vinegar or descaler directly into the clean water tank, "
            "to help prevent malfunction.",
            "Do not use sharp tools or corrosive liquids such as hydrochloric acid to "
            "clean the heating module.",
        ],
    },
    "baseboard_brush": {
        "steps": [
            "After the baseboard cleaning task is complete, pull the cleaning brush "
            "upward to remove it, wipe the bristles with a clean damp cloth, and store "
            "it properly after air drying.",
        ],
        "notes": [],
    },
}


# --------------------------------------------------------------------------
# L10s Ultra Gen 2 (r2469). Transcribed from R2469X, EN section pp. 19-25 — its OWN
# manual, read page by page. Nothing here is shared with the X60 block above, and the
# overlap is smaller than it looks: the side brush is pulled, not unscrewed; the dust
# box needs the robot cover opened first; contacts and vents are two sections rather
# than one; and the washboard is a removable BASE with a filter cover, not the X60's
# separate filter plus heating module.
# --------------------------------------------------------------------------
_L10S_GEN2: dict[str, dict] = {
    "main_brush": {
        "steps": [
            "Press the brush guard clips inwards to remove the brush guard and lift "
            "the brush out of the robot.",
            "Pull out the brush covers at both ends of the brush. Use the provided "
            "cleaning tool to remove any hair tangled in the brush. Reinstall the "
            "brush covers on both ends of the brush, and then reinstall the brush. "
            "Press on the brush guard to lock it in place.",
        ],
        "notes": [],
    },
    "side_brush": {
        "steps": ["Remove and clean the side brush."],
        "notes": [],
    },
    "dustbin": {
        "steps": [
            "Open the robot cover and press the dust box clip to remove the dust box.",
            "Open the dust box cover, remove the filter, and then empty the dust box.",
            "Gently tap the basket of the filter to remove the dirt.",
            "Rinse the dust box and filter with water and dry them completely before "
            "reinstalling.",
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp "
            "objects to prevent damage.",
            "Rinse the dust box and filter with clean water only. Do not use any "
            "detergent.",
            "Use the dust box and filter only when they are completely dry.",
        ],
    },
    "filter": {
        "steps": [
            "Open the dust box cover and remove the filter.",
            "Gently tap the basket of the filter to remove the dirt.",
            "Rinse the filter with water and dry it completely before reinstalling.",
        ],
        "notes": [
            "Do not attempt to clean the filter with a brush, a finger or sharp "
            "objects to prevent damage.",
            "Rinse with clean water only. Do not use any detergent.",
            "Use the filter only when it is completely dry.",
        ],
    },
    "used_water_tank": {
        "steps": [
            "Remove the used water tank, open its cover and pour out the used water.",
            "Rinse the used water tank with clean water, and use the provided cleaning "
            "tool to clean the inner wall of the used water tank.",
        ],
        "notes": [
            "The float ball in the used water tank is a movable part. Do not apply too "
            "much force when cleaning it to avoid damaging it.",
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
            "Pulling upwards on the handle will seal the bag to prevent the dust and "
            "debris from accidentally falling out.",
        ],
    },
    "washboard": {
        "steps": [
            "Take out the robot from the base station.",
            "Take out the washboard and open the filter cover. Rinse the washboard "
            "with clean water and clean it with the provided cleaning tool. After "
            "cleaning, close the cover and wipe the washboard with a soft and dry "
            "cloth.",
            "Wipe the washboard base clean, and put the washboard back into the base "
            "station.",
            "Use the app or briefly press the button on the robot to make it return to "
            "the base station.",
        ],
        "notes": ["During cleaning, do not make the robot return to the base station."],
    },
    "mop_cloth": {
        "steps": ["Remove the mop pad from the mop pad holder to replace it."],
        "notes": [],
    },
    "mop_pad_holder": {
        "steps": ["Remove and clean the mop pad holder."],
        "notes": [],
    },
    "caster_wheel": {
        "steps": [
            "Use a tool such as a small screwdriver to separate the axle and tire of "
            "the omnidirectional wheel.",
            "Rinse the omnidirectional wheel under running water and put it back after "
            "drying it completely.",
        ],
        "notes": ["Do not use excessive force when separating the axle and tire."],
    },
    "dock_contacts": {
        "steps": [
            "Clean the charging contacts and the signaling area with a soft and dry "
            "cloth.",
        ],
        "notes": [],
    },
    "auto_empty_vents": {
        "steps": [
            "Clean the auto-empty vents of the robot and the base station with a soft "
            "and dry cloth.",
        ],
        "notes": [],
    },
    "sensor": {
        "steps": [
            "Wipe the robot sensors with a soft, dry cloth: the carpet sensor, cliff "
            "sensors, bumper, edge sensor, laser distance sensor (LDS) and 3D line "
            "laser sensor.",
        ],
        "notes": [_SENSOR_NOTE],
    },
}


DREAME_UPKEEP_GUIDE_LIBRARY: dict[str, dict[str, dict]] = {
    # Each family is transcribed from ITS OWN manual. No prose crosses between them.
    "x60": {**_X60_BASE, **_SENSORS_X60, **_X60_ONLY},
    "l10s_gen2": _L10S_GEN2,
}

# ⚠ THERE IS DELIBERATELY NO "standard" FAMILY, AND THE FIRST CUT OF THIS FILE WAS
# WRONG TO HAVE ONE.
#
# It mapped L20 / X40 / L10s Gen 2 / X50 / L50 onto the text above. Spot-checked
# against those manuals, SEVEN OF TEN of its entries do not appear in them at all:
#
#   shared by Gen2+L20+X50 : main-brush step 1, used water tank, omnidirectional wheel
#   NOT shared             : main-brush step 2, side brush ("unscrew"), dust box,
#                            dust bag, mop pads, washboard filter, and the combined
#                            vents/contacts section — which is in none of them
#
# The differences are hardware, not wording. Gen 2's dust box needs the ROBOT COVER
# opened first; its washboard has a filter cover cleaned with a provided tool, where
# the X60 has a separate washboard filter and a heating module; its contacts and
# auto-empty vents are two sections, not one; its main brush has end covers the X60's
# anti-tangle brush does not have.
#
# The error was reading the component MATRIX — which measured whether a part is
# PRESENT — as evidence the STEPS were shared. Those are different claims, and the
# divergence had already been demonstrated earlier in the same session.
#
# An unauthored family yields {} from `library[family][component]`, so a device with
# no family here gets NO guide. That is the correct outcome: telling someone to
# unscrew a brush that clips, or to skip opening a cover that must be opened, is worse
# than saying nothing. Add a family only from ITS OWN manual, and note that PDF text
# extraction interleaves adjacent columns — the "Main Brush" block in the Gen 2 manual
# extracts with used-water-tank sentences inside it, so blocks need reading, not
# scripting.

