"""Dreame upkeep guide library — manufacturer text, composed per robot trim.

``DREAME_UPKEEP_GUIDE_LIBRARY[guide_family][component] = {"steps": [...], "notes": [...]}``

Mirrors ``adapters/roborock/roborock_upkeep_guides.py``. Component keys are the
FRAMEWORK's vocabulary (``main_brush``, ``side_brush``, ``filter``, ``sensor``,
``dustbin``, ``mop_cloth``, ``caster_wheel``, ``main_wheel``), not Dreame's wording —
a guide keyed to a brand's own noun resolves for nobody.

⚠ NOT WIRED. There is deliberately no ``BRAND_REGISTRARS`` row for Dreame; that row is
the switch, and the adapter is gated on a RELEASED upstream build carrying Tasshack
issue #1707. This file is inert data and safe to land ahead of it.

PROVENANCE — every string below is Dreame's own text, transcribed from
``R6001-X60_Series`` (the 28-language global series manual, EN section pp. 15-16),
mirrored in the git-ignored fixture set. Guide content is AI-authored by default and
transferred only when a manual is genuinely in hand; for this line it is.

WHY THE LIBRARY COMPOSES RATHER THAN REPEATING ITSELF
-----------------------------------------------------
Measured across six platforms (L20 R2394, X40 R2416, L10s Gen2 R2469, X50 R2489,
L50 R9493, X60 R6001), spanning 2023-2026 and both product lines:

  * **17 components are identical on every one of them** — brushes, dust box, filter,
    mop pad, both water tanks, washboard, dust bag, carpet/edge sensors, both wheel
    types, charging contacts, auto-empty, detergent.
  * **Six components vary at all**, and only at the edges.

So the shared text is authored ONCE in ``_BASE`` and families extend it. The lookup in
``maintenance/manager.py`` is a flat ``library[family][component]`` with **no
per-component fallback** — an unauthored component yields ``{}``, a silently missing
guide rather than an error. Composition sidesteps that: every family is a complete
dict by construction.

⚠ DREAME VARIES ON THE OPPOSITE AXIS TO ROBOROCK, and the family names below reflect
that. Roborock's suffixes buy DOCK hardware (``+`` = auto-empty, ``Ultra`` = wash
station), so its families are dock tiers. Dreame's suffixes buy ROBOT hardware —
X60 Ultra to X60 Max Ultra Complete adds a chassis lift, a carpet pressure plate, an
extending side brush and heated pads, while the dock stays put. Its families are
therefore robot trims, and the dock text lives in ``_BASE`` for everyone.

**Do not infer the family from the model name.** Whether a dock has a dust bag to
service is answered by live entity presence (the technique the Roborock catalog
already documents), not by counting words in "X60 Max Ultra Complete".
"""

from __future__ import annotations


# --------------------------------------------------------------------------
# Shared across every measured platform, 2023-2026, both product lines.
# --------------------------------------------------------------------------
_BASE: dict[str, dict] = {
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

_SENSORS_PRE_X60 = {
    "sensor": {
        "steps": [
            "Wipe the robot sensors with a soft, dry cloth: the laser distance sensor "
            "(LDS), bumper window, edge sensor, bumper, cliff sensors and carpet "
            "sensor.",
        ],
        "notes": [_SENSOR_NOTE],
    },
}

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


DREAME_UPKEEP_GUIDE_LIBRARY: dict[str, dict[str, dict]] = {
    # Everything measured before the X60: L20, X40, L10s Gen 2, X50, L50.
    "standard": {**_BASE, **_SENSORS_PRE_X60},
    # X60 series. Adds the heated washboard and the baseboard brush; swaps the line
    # laser for VersaLift in the sensor list.
    "x60": {**_BASE, **_SENSORS_X60, **_X60_ONLY},
}
