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

  ``x50``                     R2489A-X50_Series, EN pp. 22-30
  ``x60_ultra``               R5089B-X60_Ultra, EN pp. 13-15
  ``x60_pro_ultra_complete``  R6001-X60_Series, EN pp. 14-16
  ``l20``                     R2394A-L20_Ultra, EN pp. 20-26
  ``x40``                     R2416A-X40_Ultra, EN pp. 19-26
  ``l50``                     R9493-L50_Ultra, EN pp. 23-30
  ``l10s_gen2``               R2469X-L10s_Ultra_Gen_2, EN pp. 19-25

Manuals are mirrored in the git-ignored fixture set. Guide content is AI-authored by
default and transferred only when a manual is genuinely in hand; for all four it is.

THREE THINGS ARE RECAST RATHER THAN TRANSCRIBED, and the distinction is worth keeping
straight — "manufacturer text" is a provenance claim, and it is not true of these:

  * ``filter`` — no Dreame manual gives the filter a section of its own; it is folded
    into "Dust Box and Filter". The entry is assembled from that section's filter
    sentences, so every sentence is Dreame's but the entry as a unit has no page to
    point at. It exists because a device reporting a filter consumable would otherwise
    get ``{}``.
  * ``sensor`` — the manuals print a NUMBERED LIST OF LABELS beside a figure ("1.
    VersaLift Sensor, 2. Bumper Window, …"). With no figure to look at, that is
    useless, so the labels are folded into one sentence. The sensor NAMES are verbatim;
    the sentence around them is ours.
  * ``caster_wheel`` notes — "Do not use excessive force" is the tail of a manual bullet
    and is lifted out with its subject restored, so it reads on its own.

Everything else is Dreame's own wording. ``scripts/verify_dreame_guide_provenance.py``
re-checks that after any edit — but read what it can and cannot do: it scores bigram
overlap against the source manual, which catches invented content flat (an invented
step scores ~8%) and catches a wrong item in a list (~47%), yet a SINGLE swapped word
in an otherwise-faithful sentence still scores ~93%. It is a net for wholesale drift,
not a proofreader. The three recasts above are the only entries that legitimately score
low; anything else under ~85% is a defect.

⚠ EACH FAMILY IS AUTHORED WHOLE. SHARE ONLY WHAT YOU HAVE DIFFED, AND THE FIRST CUT OF
THIS FILE SHARED WHAT IT HAD NOT.
------------------------------------------------------------------------------------
The bar is a measurement, not a hunch. The two X60 families DO share a body, because
their manuals were compared sentence by sentence first: 48 of 49 identical, the
baseboard cleaning brush the entire delta. State the diff or duplicate the prose —
what is banned is sharing on the strength of the component names lining up, which is
what happened here once and is worth spelling out:

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

⚠ READ THE PAGES, DO NOT PARSE THEM. `Routine Maintenance` locates the care section
reliably (l20 pp20-26, x40 19-26, l10s_gen2 18-25, x50 22-30, l50 23-30) — but plain
text extraction emits content-stream order, which interleaves adjacent columns: a
collapsed extract of the Gen 2 "Main Brush" block arrives with used-water-tank
sentences inside it, and that produced a false "the dust bag differs" finding once.
``scripts/pdf_layout_dump.py`` reconstructs visual reading order from the text matrices
and makes even a three-column care page legible; there is no rasteriser in this
environment, so that, not page images, is how these get read. Automate the FINDING and
the LAYOUT; read the prose.

An unauthored family yields ``{}`` from ``library[family][component]``, so a device
with no family here gets NO guide. That is the correct failure: silence beats confident
wrong instructions about someone's hardware.

⚠ DREAME VARIES ON THE OPPOSITE AXIS TO ROBOROCK. Roborock's suffixes buy DOCK hardware
(``+`` = auto-empty, ``Ultra`` = wash station), so its families are dock tiers. Dreame's
buy ROBOT hardware — X60 Ultra to X60 Max Ultra Complete adds a chassis lift, a carpet
pressure plate, an extending side brush and heated pads while the dock stays put — so
its families are robot trims.

**A FAMILY IS A MANUAL PAGE.** Its scope is every ``dreame.vacuum.*`` key whose
marketing name appears on that page — which is the only boundary Dreame actually draws,
by printing one maintenance section for a set of models. Neither of the obvious keys
works: the r-code is too NARROW (``X40 Ultra Complete`` is ``r2449``, not ``r2416``,
yet shares the X40 Ultra manual) and the marketing name is too BROAD ("X50" is 23 names
across ~20 codes). See ``.claude/notes/SCOPE-dreame-guide-families.md``.

  ``x50``                     X50 Ultra + X50 Ultra Complete   41 keys
  ``l20``                     L20 Ultra + L20 Ultra Complete   15 keys
  ``x40``                     X40 Ultra + X40 Ultra Complete    9 keys
  ``x60_ultra``               X60 Ultra                         4 keys  r5089, r9515
  ``l10s_gen2``               L10s Ultra Gen 2                  3 keys  r2469, r5020
  ``l50``                     L50 Ultra                         2 keys  r9493
  ``x60_pro_ultra_complete``  X60 Pro Ultra Complete            1 key   r6001

**75 of the 587 model keys the integration declares — 12.8%.** Every manual currently
in hand is authored; the next family costs a new manual, not a new read of an old one.
Four of the seven pages name BOTH their variants outright (X50, L20, X40 on the
package-contents pages), and in each case the "Complete" variant differs only by
QUANTITIES of consumables — spares, not hardware. That is what lets one care section
cover two marketing names.

⚠ **A MARKETING NAME CAN HAVE TWO MANUALS, AND "X60" HAD TWO.** An earlier cut of this
file put ``r5089``, ``r6001`` and ``r9515`` in one ``x60`` family. Wrong, and backwards
for two of the three: ``r6001a`` is the X60 Pro Ultra Complete while ``r5089*`` and
``r9515*`` are the X60 Ultra, and each has its OWN manual — different regulatory robot
models (RLX92DE vs RLX96DE/RLX98DE), different parts tables. The tell was there to be
read: the filenames carry the r-codes.

⚠ **THE APPLICABILITY STATEMENT IS ON THE SPECIFICATIONS PAGE, NOT THE COVER.** This
file previously recorded that "the manuals do not resolve it either — no applicability
statement, no model list, checked on pp. 1-6 of each". That conclusion came from
checking the front matter and reading absence as proof. Every manual here in fact lists
its regulatory models under Specifications (X50: six robots, ``RLX85CE`` and ``-1`` to
``-6``), and the X50's what's-in-the-box pages name its two marketing variants outright.

Whether a dock has a dust bag to service is a separate question, answered by live
entity presence — never by counting words in "X60 Max Ultra Complete".
"""

from __future__ import annotations


# --------------------------------------------------------------------------
# The X60 body, transcribed from R6001 and re-verified against R5089B, which prints the
# same care text word for word. NOT a base to hang other trims off: measured against the
# L10s Gen 2, only ONE of eleven common component keys (caster_wheel) has identical
# steps, and against the X50 only 29 of 46 sentences survive.
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

#: Present in BOTH X60 manuals — R5089B lists it in its parts table and gives it the
#: same care section as R6001. It is not a Pro-Ultra-Complete extra.
_X60_HEATER = {
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
}

#: THE ONLY care-section difference between the two X60 manuals. Measured sentence by
#: sentence: 48 of 49 shared, and this is the one that is not. R5089B (X60 Ultra) does
#: not list a baseboard cleaning brush in its parts table and has no section for it, so
#: serving this entry to an X60 Ultra describes a part that robot has not got.
_BASEBOARD_BRUSH = {
    "baseboard_brush": {
        "steps": [
            "After the baseboard cleaning task is complete, pull the cleaning brush "
            "upward to remove it, wipe the bristles with a clean damp cloth, and store "
            "it properly after air drying.",
        ],
        "notes": [],
    },
}

#: The X60 Ultra body — R5089B in full. The Pro Ultra Complete adds exactly one key.
_X60_ULTRA: dict[str, dict] = {**_X60_BASE, **_SENSORS_X60, **_X60_HEATER}


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


# --------------------------------------------------------------------------
# X50 Ultra / X50 Ultra Complete. Transcribed from R2489A, EN section pp. 22-30 — its
# OWN manual, read page by page. That manual names both variants itself, on the
# what's-in-the-box pages: "(Dreame X50 Ultra)" p. 7 and "(Dreame X50 Ultra Complete)"
# p. 8. So the two marketing names on one page are Dreame's assertion, not our
# inference — 41 of the integration's model keys.
#
# It is a DIFFERENT document from the X60's, not a revision of it: 29 of 46 sentences
# shared, and at component level 12 keys in common of which 5 are identical — the four
# that really are word-for-word in both manuals (side brush, mop pads, mop pad holders,
# omnidirectional wheel) plus the derived `filter`. The divergences are all hardware.
# The X50 has no washboard heating
# module and no baseboard brush at all; it carries a 3D dual-line laser the X60
# dropped, where the X60 has a dust illumination light the X50 has not got; its dust
# box sits under a ROBOT COVER; it ships a cleaning tool the X60 manual only calls
# "a proper tool"; and it splits contacts from auto-empty vents where the X60 prints
# all three in one section.
# --------------------------------------------------------------------------
_X50: dict[str, dict] = {
    "main_brush": {
        "steps": [
            "Press the brush guard clips inwards to remove the brush guard, and then "
            "lift the brushes out of the robot.",
            "Pull out the brushes. Use the provided cleaning tool to remove any hair "
            "tangled in the brushes. After cleaning, push the brushes firmly into the "
            "main brush holder until they click into place.",
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
            "Remove the robot cover and press the dust box clip to remove the dust box.",
            "Remove the dust box filter, and then empty the dust box.",
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
    # Verbatim the same source text as the X60's, and rendered the same way on purpose
    # — this is the one component the two families genuinely share, and recasting it
    # differently would make an identical part read as a different procedure.
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
    # No residual-heat note here, unlike the X60's: the X50 has no washboard heating
    # module — neither its parts table nor its care section mentions one.
    "washboard_filter": {
        "steps": [
            "Take out the robot and remove the washboard filter after the mop pad "
            "cleaning is complete.",
            "Rinse the washboard filter with clean water, wipe it clean, and then "
            "reinstall it in the washboard.",
            "Use the app or press the button to return the robot to the base station, "
            "or manually put the robot back.",
        ],
        "notes": [],
    },
    # Two sections on the X50, where the X60 prints one combined block.
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
            "Wipe the robot sensors with a soft, dry cloth: the bumper window, 3D "
            "dual-line laser sensors, VersaLift sensor, edge sensor, bumper, cliff "
            "sensors and carpet sensor.",
        ],
        "notes": [_SENSOR_NOTE],
    },
}


# --------------------------------------------------------------------------
# L20 Ultra / L20 Ultra Complete. Transcribed from R2394A, EN pp. 21-26. The manual
# names both variants on its package pages — "(DreameBot L20 Ultra)" p. 7 and
# "(DreameBot L20 Ultra Complete)" p. 8 — and the Complete differs only by QUANTITIES
# (side brush x3, dust bag x5, mop pad x14). Spares, not hardware.
#
# The MOST DISTINCT family in this file: at most 21 sentences shared with any other,
# against 33 between the L50 and the X50. It is the only one with an AI visual sensor,
# line laser sensors and LED fill lights; the only one with a cleaning-solution inlet
# to wipe; and the only one whose manual treats the side brush and mop pad holder as a
# single instruction.
# --------------------------------------------------------------------------
_L20: dict[str, dict] = {
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
    # One instruction in the manual, carried verbatim under both keys — the L20's side
    # brush and mop pad holder are serviced in the same motion.
    "side_brush": {
        "steps": ["Remove and clean the side brush and mop pad holder."],
        "notes": [],
    },
    "mop_pad_holder": {
        "steps": ["Remove and clean the side brush and mop pad holder."],
        "notes": [],
    },
    "dustbin": {
        "steps": [
            "Open the robot's cover and press the clip to remove the dust box.",
            "Open the dust box cover and empty the dust box.",
        ],
        "notes": [],
    },
    "filter": {
        "steps": [
            "Remove the filter and tap its basket gently.",
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
    "mop_cloth": {
        "steps": ["Remove the mop pad from the mop pad holder to replace it."],
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
            "Rinse the used water tank with clean water, and use the provided cleaning "
            "tool to clean the inner wall of the used water tank.",
        ],
        "notes": [
            "The float ball in the used water tank is a movable part. Do not apply too "
            "much force when cleaning it to avoid damaging it.",
        ],
    },
    # The L20's dust tank cover LOCKS, and its handle is pulled OUTWARDS — both differ
    # from every other family here, where the cover lifts off and the handle pulls up.
    "dust_bag": {
        "steps": [
            "Unlock the dust tank cover and then remove it.",
            "Discard the dust bag.",
            "Remove the dust and debris from the filter with a dry cloth.",
            "Install a new dust bag. Then install back the dust tank cover and lock it.",
        ],
        "notes": [
            "Pulling outwards on the handle will seal the dust bag to prevent the dust "
            "and debris from accidentally falling out.",
        ],
    },
    # A removable washboard cleaned in place, with the base station pumping water in
    # and back out — not the X50's removable filter, and not the X40's roller.
    "washboard": {
        "steps": [
            "Press the button to make the robot exit the base station.",
            "Remove the washboard and rinse it with clean water.",
            "Press and hold the button for 3 seconds to add water to the bottom of the "
            "base station. Then use the included cleaning tool to clean it.",
            "Press and hold the button for 3 seconds to pump out the used water in the "
            "bottom of the base station, dry it with a soft and dry cloth, and then "
            "put the washboard back.",
        ],
        "notes": [],
    },
    "dock_contacts": {
        "steps": [
            "Clean the charging contacts and the signaling area of the base station "
            "with a soft and dry cloth.",
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
    # Unique to the L20 in this file. Its base station doses cleaning solution from a
    # bottle, and the inlet is a part the manual asks you to keep clean.
    "detergent_inlet": {
        "steps": [
            "If the cleaning solution adding inlet is dirty, wipe it with a soft and "
            "dry cloth.",
        ],
        "notes": [],
    },
    "sensor": {
        "steps": [
            "Wipe the robot's sensors and charging contacts with a soft, dry cloth: "
            "the AI visual sensor, line laser sensors, LED fill lights, laser distance "
            "sensor (LDS), edge sensor, bumper, charging contacts, cliff sensors and "
            "carpet sensor.",
        ],
        "notes": [_SENSOR_NOTE],
    },
}


# --------------------------------------------------------------------------
# X40 Ultra / X40 Ultra Complete. Transcribed from R2416A, EN pp. 20-26. Both variants
# named on the package pages, p. 7 and p. 8.
#
# Its washboard is a ROLLER that comes apart — cover, roller, end caps, reassembled by
# colour — and is the longest single procedure in this file at six steps. Nothing else
# here has one, which is why `washboard` cannot be shared even with the L20, whose
# washboard is a flat plate that lifts out.
# --------------------------------------------------------------------------
_X40: dict[str, dict] = {
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
        "steps": [
            "Unscrew the side brush with a screwdriver, clean the hair from the brush, "
            "and then screw it back on.",
        ],
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
            "Enable the washboard base cleaning function in the app, and the robot "
            "will exit the base station automatically. Take out the washboard and wait "
            "for water to fill the washboard base.",
            "Use the cleaning tool to clean the washboard base. After a moment, the "
            "base station will automatically pump out the used water. Then wipe the "
            "washboard base with a soft and dry cloth.",
            "Flip the washboard over, remove the roller cover and the roller in turn, "
            "and then pull off the end caps of the roller.",
            "Remove the hair tangled in the roller, and then reassemble the parts "
            "according to corresponding colors.",
            "Rinse the washboard with clean water, wipe it clean and then put it back "
            "into the base station downwards in an inclined way.",
            "Use the app or briefly press the button on the robot to make it return to "
            "the base station.",
        ],
        "notes": [
            "If the roller cover is blocked by wipers on both sides of the washboard, "
            "rotate the roller to move them aside.",
            "During cleaning, do not make the robot return to the base station.",
        ],
    },
    "dock_contacts": {
        "steps": [
            "Clean the charging contacts and the signaling area of the base station "
            "with a soft and dry cloth.",
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
            "Wipe the robot's sensors and charging contacts with a soft, dry cloth: "
            "the bumper window, laser distance sensor (LDS), 3D dual-line laser "
            "sensors, edge sensor, bumper, charging contacts, cliff sensors and carpet "
            "sensor.",
        ],
        "notes": [_SENSOR_NOTE],
    },
}


# --------------------------------------------------------------------------
# L50 Ultra. Transcribed from R9493, EN pp. 24-30. One marketing name, `r9493`, 2 keys.
#
# ⚠ THE CLOSEST PAIR IN THIS FILE — 33 sentences shared with the X50, and it is STILL
# its own family. The two differences sit INSIDE shared components rather than in an
# extra one, which is exactly the case the X60 pair is not:
#
#   dustbin  the L50 says OPEN the robot cover; the X50 says REMOVE it
#   sensor   the L50 carries a laser distance sensor (LDS) and NO VersaLift;
#            the X50 carries a VersaLift and NO LDS
#
# Sharing a body here would tell an L50 owner to wipe a VersaLift sensor their robot
# does not have, and never mention the LDS it does. One word and one list — which is
# why the diff has to be read, not skimmed for a headline number.
# --------------------------------------------------------------------------
_L50: dict[str, dict] = {
    "main_brush": {
        "steps": [
            "Press the brush guard clips inwards to remove the brush guard, and then "
            "lift the brushes out of the robot.",
            "Pull out the brushes. Use the provided cleaning tool to remove any hair "
            "tangled in the brushes. After cleaning, push the brushes firmly into the "
            "main brush holder until they click into place.",
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
            "Open the robot cover and press the dust box clip to remove the dust box.",
            "Remove the dust box filter, and then empty the dust box.",
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
    # No residual-heat note: like the X50, the L50 has no washboard heating module.
    "washboard_filter": {
        "steps": [
            "Take out the robot and remove the washboard filter after the mop pad "
            "cleaning is complete.",
            "Rinse the washboard filter with clean water, wipe it clean, and then "
            "reinstall it in the washboard.",
            "Use the app or press the button to return the robot to the base station, "
            "or manually put the robot back.",
        ],
        "notes": [],
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
            "Wipe the robot sensors with a soft, dry cloth: the 3D dual-line laser "
            "sensors, bumper window, edge sensor, laser distance sensor (LDS), cliff "
            "sensors, carpet sensor and bumper.",
        ],
        "notes": [_SENSOR_NOTE],
    },
}


DREAME_UPKEEP_GUIDE_LIBRARY: dict[str, dict[str, dict]] = {
    # Each family is transcribed from ITS OWN manual. Prose crosses between two
    # families in exactly one place, and only because it was MEASURED to: the X60
    # Ultra and X60 Pro Ultra Complete manuals share 48 of 49 care sentences, the
    # baseboard brush being the whole of the difference. Everywhere else, families
    # are authored whole and share nothing.
    "x50": _X50,
    "x60_ultra": _X60_ULTRA,
    "x60_pro_ultra_complete": {**_X60_ULTRA, **_BASEBOARD_BRUSH},
    "l20": _L20,
    "x40": _X40,
    "l50": _L50,
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
