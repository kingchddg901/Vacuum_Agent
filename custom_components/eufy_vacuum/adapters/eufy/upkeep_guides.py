"""
Upkeep guide library for the Eufy adapter.

Each entry maps a guide family key (from UPKEEP_MODEL_GUIDE_FAMILIES in
upkeep_catalog.py) to a dict of component guide entries.

Structure:
    {
        family_key: {
            component_key: {
                "clean_frequency": str,
                "replace_frequency": str | None,
                "steps": list[str],
                "notes": list[str],
            }
        }
    }

Component keys match MAINTENANCE_COMPONENTS in core/capabilities.py.
A guide family with no cleaning_tray or swivel_wheel simply omits those keys.
The framework iterates whatever keys are present — absent keys produce no
upkeep cards in the UI.

No imports are needed — this is pure data.
"""

UPKEEP_GUIDE_LIBRARY = {
    "x10_pro_omni": {
        "filter": {
            "clean_frequency": "weekly",
            "replace_frequency": "every 3-6 months",
            "steps": [
                "Open the top cover and remove the dust box.",
                "Remove the filter from the dust box.",
                "Tap dust off the filter and empty the dust box.",
                "Rinse the dust box and filter with water only.",
                "Let both parts air dry completely before reinstalling.",
            ],
            "notes": [
                "Do not use a brush, hot water, or detergent.",
                "Replace the filter every 3-6 months.",
            ],
        },
        "sensor": {
            "clean_frequency": "monthly",
            "replace_frequency": None,
            "steps": [
                "Use a soft, dry cloth to wipe the sensors and cameras.",
                "Also wipe the charging pins while doing sensor maintenance.",
            ],
            "notes": [
                "No replacement interval is listed for sensors in the manual.",
            ],
        },
        "side_brush": {
            "clean_frequency": "monthly",
            "replace_frequency": "every 3-6 months or when worn",
            "steps": [
                "Remove the side brush with a screwdriver.",
                "Unwind and remove any hair or debris.",
                "Rinse the brush with water and air dry it fully.",
                "Reinstall the brush after it is dry.",
            ],
            "notes": [],
        },
        "rolling_brush": {
            "clean_frequency": "monthly",
            "replace_frequency": "every 6 months",
            "steps": [
                "Unlock the brush guard tabs and lift the guard out.",
                "Remove the rolling brush.",
                "Cut away and remove wrapped hair and debris.",
                "Rinse the brush and guard, then air dry them.",
                "Reinstall the brush and snap the guard back into place.",
            ],
            "notes": [
                "Brush guard should also be replaced every 3-6 months or when worn.",
            ],
        },
        "mopping_cloth": {
            "clean_frequency": "wash after use / inspect regularly",
            "replace_frequency": "every 3-6 months",
            "steps": [
                "Remove the mopping pads from the robot.",
                "Wash and fully dry the pads before reuse.",
                "Replace the pads when they become worn or no longer clean effectively.",
            ],
            "notes": [],
        },
        "cleaning_tray": {
            "clean_frequency": "as needed",
            "replace_frequency": None,
            "steps": [
                "Remove the cleaning tray from the Omni Station.",
                "Rinse the tray thoroughly with water.",
                "Reinstall the tray after cleaning.",
            ],
            "notes": [
                "Dirty water tank should be emptied and rinsed when full.",
            ],
        },
        "swivel_wheel": {
            "clean_frequency": "monthly",
            "replace_frequency": None,
            "steps": [
                "Inspect the swivel wheel for wrapped hair or debris.",
                "Remove debris carefully and wipe the wheel area clean.",
                "Confirm the wheel spins freely before the next run.",
            ],
            "notes": [
                "The manual lists swivel wheel cleaning but does not provide a dedicated replacement interval.",
            ],
        },
    },
    "s1_pro": {
        "filter": {
            "clean_frequency": "every 60 hours",
            "replace_frequency": "every 3 months",
            "steps": [
                "Remove the high-performance filter from the dust bin area.",
                "Tap off dust and debris gently.",
                "Reinstall or replace the filter once it is clean and dry.",
            ],
            "notes": [
                "Accessory service guidance in the app is the primary official reset flow for S1 Pro.",
            ],
        },
        "sensor": {
            "clean_frequency": "every 360 hours",
            "replace_frequency": None,
            "steps": [
                "Wipe the robot sensors with a soft, dry cloth.",
                "Also clean the charging contacts while servicing the sensors.",
            ],
            "notes": [],
        },
        "side_brush": {
            "clean_frequency": "every 180 hours",
            "replace_frequency": "as needed when worn",
            "steps": [
                "Inspect the side brush for trapped hair and debris.",
                "Remove buildup around the base and bristles.",
                "Replace the brush if bristles are bent or damaged.",
            ],
            "notes": [],
        },
        "rolling_brush": {
            "clean_frequency": "every 180 hours",
            "replace_frequency": "every 6 months",
            "steps": [
                "Remove the rolling brush guard.",
                "Check the brush and both end caps for tangled hair or debris.",
                "Clean the brush thoroughly before reinstalling.",
            ],
            "notes": [],
        },
        "mopping_cloth": {
            "clean_frequency": "every 60 hours",
            "replace_frequency": "every 6 months",
            "steps": [
                "Remove the rolling mop or mop contact surfaces and clean away residue.",
                "Allow cleaned parts to dry before reuse.",
                "Replace the mop-related consumable when wear becomes visible or performance drops.",
            ],
            "notes": [
                "S1 documentation is rolling-mop oriented rather than detachable twin-pad wording.",
            ],
        },
        "cleaning_tray": {
            "clean_frequency": "every 30 hours",
            "replace_frequency": None,
            "steps": [
                "Remove the filter tray or tray insert from the station area.",
                "Rinse away residue and buildup.",
                "Reinstall after cleaning.",
            ],
            "notes": [
                "Also clean the clean/dirty water tanks and dirty water filter as needed.",
            ],
        },
        "swivel_wheel": {
            "clean_frequency": "as needed",
            "replace_frequency": None,
            "steps": [
                "Inspect the swivel wheel for hair and debris.",
                "Remove buildup and confirm the wheel rotates freely.",
            ],
            "notes": [],
        },
    },
    "omni_c20": {
        "filter": {
            "clean_frequency": "regularly",
            "replace_frequency": "every 3-6 months",
            "steps": [
                "Remove the dust bin or filter compartment.",
                "Take out the filter and tap off dust.",
                "Wash only if the manual/app guidance allows, then dry fully before reinstalling.",
            ],
            "notes": [
                "The Omni C20 accessory guide is primarily video-based.",
            ],
        },
        "sensor": {
            "clean_frequency": "regularly",
            "replace_frequency": None,
            "steps": [
                "Use a clean, dry cloth to wipe the sensors and charging contacts on both the robot and station.",
            ],
            "notes": [],
        },
        "side_brush": {
            "clean_frequency": "inspect every 2 weeks",
            "replace_frequency": "every 3-6 months",
            "steps": [
                "Inspect the side brush for wear, tangles, or damage.",
                "Remove wrapped hair and debris from the brush and base.",
                "Replace the brush if bristles are bent or missing.",
            ],
            "notes": [],
        },
        "rolling_brush": {
            "clean_frequency": "periodically",
            "replace_frequency": "as needed",
            "steps": [
                "Inspect the rolling brush for tangled hair or debris.",
                "Use the cleaning tool or scissors to cut away wrapped material.",
                "Reinstall after cleaning.",
            ],
            "notes": [
                "The Pro-Detangle Comb reduces but does not eliminate manual cleaning.",
            ],
        },
        "mopping_cloth": {
            "clean_frequency": "after dirty runs / regularly",
            "replace_frequency": "as needed",
            "steps": [
                "Remove the mop pads from the robot or station.",
                "Clean and fully dry them before reuse.",
                "Replace the pads when worn or no longer cleaning effectively.",
            ],
            "notes": [],
        },
        "cleaning_tray": {
            "clean_frequency": "regularly",
            "replace_frequency": None,
            "steps": [
                "Detach the station base or mop washing area component.",
                "Rinse and wipe away residue from the tray area.",
                "Reinstall the tray after cleaning.",
            ],
            "notes": [
                "Also monitor and service the clean and dirty water tanks.",
            ],
        },
    },
    "x8_series": {
        "filter": {
            "clean_frequency": "regularly",
            "replace_frequency": "every 3-6 months",
            "steps": [
                "Remove the dust bin and take out the filter.",
                "Tap the filter gently to remove dust.",
                "If rinsed, allow it to dry completely before reinstalling.",
            ],
            "notes": [],
        },
        "sensor": {
            "clean_frequency": "regularly",
            "replace_frequency": None,
            "steps": [
                "Wipe drop sensors, bumper sensors, and charging contacts with a dry cloth.",
            ],
            "notes": [],
        },
        "side_brush": {
            "clean_frequency": "regularly",
            "replace_frequency": "every 3-6 months",
            "steps": [
                "Remove the side brush.",
                "Clear away hair and debris from the brush and its base.",
                "Reattach or replace if worn.",
            ],
            "notes": [],
        },
        "rolling_brush": {
            "clean_frequency": "regularly",
            "replace_frequency": "every 3-6 months",
            "steps": [
                "Pinch the main brush guard tabs and remove the guard.",
                "Lift out the main brush.",
                "Use the cleaning tool or scissors to remove hair and debris.",
                "Reinstall the brush and guard.",
            ],
            "notes": [],
        },
        "mopping_cloth": {
            "clean_frequency": "after mop runs",
            "replace_frequency": "as needed",
            "steps": [
                "Remove the mop pad from the holder.",
                "Wash and dry it before reuse.",
                "Replace if it becomes worn or ineffective.",
            ],
            "notes": [
                "Applies only to hybrid/mop-capable X8 models.",
            ],
        },
    },
    "l60_series": {
        "filter": {
            "clean_frequency": "regularly",
            "replace_frequency": "every 3-6 months",
            "steps": [
                "Press the dustbin release button and remove the dust bin.",
                "Remove the filter and tap off loose dirt.",
                "If allowed by the specific model guide, rinse and dry fully before reinstalling.",
            ],
            "notes": [],
        },
        "sensor": {
            "clean_frequency": "regularly",
            "replace_frequency": None,
            "steps": [
                "Use a dry cloth to wipe the sensors and charging contacts on the robot and base.",
            ],
            "notes": [],
        },
        "side_brush": {
            "clean_frequency": "regularly",
            "replace_frequency": "every 3-6 months",
            "steps": [
                "Pull off the side brush.",
                "Remove tangled hair and debris.",
                "Reattach or replace if worn.",
            ],
            "notes": [],
        },
        "rolling_brush": {
            "clean_frequency": "at least weekly",
            "replace_frequency": "every 3-6 months",
            "steps": [
                "Remove the main brush cover.",
                "Lift out the roller brush.",
                "Clean wrapped hair and debris from the brush and bearings.",
                "Wipe dry and reinstall the brush and guard.",
            ],
            "notes": [
                "SES models also use automatic hair-cutting to reduce maintenance.",
            ],
        },
        "mopping_cloth": {
            "clean_frequency": "after mop runs",
            "replace_frequency": "as needed",
            "steps": [
                "Remove the mop pad or cloth.",
                "Clean and dry it fully before reuse.",
                "Replace the cloth when worn.",
            ],
            "notes": [
                "Applies only to hybrid variants.",
            ],
        },
    },
}
