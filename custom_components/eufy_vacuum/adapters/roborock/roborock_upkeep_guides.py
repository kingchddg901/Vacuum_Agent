"""Roborock upkeep-guide library — per-component maintenance steps / notes /
frequencies, keyed by guide family.

Mirrors the Eufy contract (adapters/eufy/eufy_upkeep_guides.py ``UPKEEP_GUIDE_LIBRARY``):

    ROBOROCK_UPKEEP_GUIDE_LIBRARY[guide_family][component] = {
        "clean_frequency": str | None,
        "replace_frequency": str | None,
        "steps": list[str],
        "notes": list[str],
    }

Guide families are MAINTENANCE PROFILES (dock + mop hardware), NOT per-model and
NOT the capability families in model_catalog.py. The ~37 HA-supported robot models
collapse to a handful of profiles because brush/filter/sensor upkeep is near-
identical across the lineup — only the dock (auto-empty / wash station) and mop
(single pad vs twin spinning pads) differ. Planned tiers, each a superset of the
one above (see upkeep_catalog.py for the model→tier map):

    standard      no dock, single mop cloth           (S4/S5/S6/S7, Q5/Q7, E, G…)
    auto_empty    + dust-collection dock              (Q5 Pro, Q7/Q8 Max, Q10)
    wash_station  + wash&dry dock, water tanks        (S7·S8 Pro Ultra, Q Revo, Qrevo, Saros, S8 MaxV Ultra…)
    dual_pad      RESERVED — a true ROTATING roller mop (Qrevo Curv 2 Flow); not yet authored

The manager overlays a localized copy PER FIELD, so any field left None/absent
falls back to English. Component keys match maintenance_components.py so each
guide attaches to its card; the manager gates guide-only DOCK components to the
station families (a dockless base robot never shows a dust-bag/water-tank card).
Content is sourced from Roborock's official manuals, written as concise factual
steps — intervals as stated by Roborock. PURE DATA (no imports):
scripts/sync-guide-translations.py loads this directly.

standard / auto_empty / wash_station are authored; auto_empty & wash_station are
COMPOSED from standard + dock deltas (below). The DOCK drives the tier. The MOP is
a SEPARATE axis with four types — (1) drag cloth, (2) VibraRise vibrating drag,
(3) twin spinning discs, (4) rotating roller — but the CARE for types 1-3 is the
same move (take the cloth/pad(s) off, rinse, air-dry), so the mop_cloth guide owns
all three. Only the brand-new rotating ROLLER (type 4, e.g. Qrevo Curv 2 Flow) is
genuinely different and not yet documented — `dual_pad` is reserved for it. An
unauthored tier's models fall back to `standard`.
"""

ROBOROCK_UPKEEP_GUIDE_LIBRARY: dict[str, dict[str, dict]] = {
    "standard": {
        "main_brush": {
            "clean_frequency": "weekly",
            "replace_frequency": "every 6-12 months",
            "steps": [
                "Flip the robot over and push the latch to release the main brush cover.",
                "Lift out the main brush, then pull off and clean the bearing cap at each end.",
                "Use the supplied cleaning tool to cut and pull away any hair wound around the brush and bearings.",
                "Refit the bearing caps and cover in the lock direction, then press the cover until the latch clicks.",
            ],
            "notes": [
                "Wipe out the brush compartment if it looks dirty before refitting.",
                "Replace the main brush every 6-12 months for the best cleaning.",
            ],
        },
        "side_brush": {
            "clean_frequency": "monthly",
            "replace_frequency": "every 3-6 months",
            "steps": [
                "Flip the robot over and remove the screw holding the side brush.",
                "Lift the side brush off and clear any hair or debris wound around the post.",
                "Refit the side brush and tighten the screw.",
            ],
            "notes": [
                "Replace the side brush every 3-6 months, or sooner if it is bent or splayed.",
            ],
        },
        "filter": {
            "clean_frequency": "every 2 weeks",
            "replace_frequency": "every 6-12 months",
            "steps": [
                "Press the dustbin latch, lift out the dustbin, open its cover and empty it.",
                "Take out the washable filter and rinse it under clean water — no detergent.",
                "Tap the filter frame against a hard surface to shake loose trapped dust, rinsing until clean.",
                "Let the filter air-dry for at least 24 hours before refitting.",
            ],
            "notes": [
                "Never use detergent, hot water, a dishwasher, or a hair dryer on the filter.",
                "Keeping a second filter to swap in lets one dry fully while the other is in use.",
            ],
        },
        "sensor": {
            "clean_frequency": "monthly",
            "replace_frequency": None,
            "steps": [
                "Wipe the six cliff sensors on the underside with a soft, dry cloth.",
                "Wipe the wall sensor on the right edge and the recharge sensor.",
                "Wipe the charging contacts on the underside at the same time.",
            ],
            "notes": [
                "Use a dry cloth only — cleaning fluids can damage the sensor covers.",
            ],
        },
        "dustbin": {
            "clean_frequency": "weekly",
            "replace_frequency": None,
            "steps": [
                "Open the top cover, press the dustbin latch, and lift the dustbin out.",
                "Open the dustbin cover and tip the contents into the bin.",
                "Rinse the dustbin with clean water when needed — remove the filter first, and use no detergent.",
            ],
            "notes": [
                "Dry the dustbin fully before refitting so damp dust cannot clog the filter.",
            ],
        },
        "mop_cloth": {
            "clean_frequency": "after each use",
            "replace_frequency": "every 3-6 months",
            "steps": [
                "Take the mop cloth off the mopping module after each mopping run.",
                "Rinse it clean and let it dry.",
            ],
            "notes": [
                "Always remove the cloth for cleaning so dirty water cannot run back into the tank and block the filter.",
                "Replace a reusable cloth every 3-6 months; swap a disposable cloth after each use.",
            ],
        },
        "water_filter": {
            "clean_frequency": None,
            "replace_frequency": "every 1-3 months",
            "steps": [
                "Pull the water filters out of the tank as shown in the manual.",
                "Fit new filters and slide them back into place.",
            ],
            "notes": [
                "Replace every 1-3 months depending on your water quality and how often you mop.",
            ],
        },
        "caster_wheel": {
            "clean_frequency": "monthly",
            "replace_frequency": None,
            "steps": [
                "Flip the robot over and pry up the omni-directional (front caster) wheel.",
                "Remove hair and dirt wound around the wheel body and axle.",
                "Press the wheel firmly back into place.",
            ],
            "notes": [
                "The wheel bracket is not removable — only the wheel body lifts out.",
            ],
        },
        "main_wheel": {
            "clean_frequency": "weekly",
            "replace_frequency": None,
            "steps": [
                "Once a week, check both main drive wheels for hair or thread wound around the axles.",
                "Cut and pull away anything trapped so the wheels spin freely.",
                "Wipe the wheels with a slightly damp cloth if debris is stuck on.",
            ],
            "notes": [
                "Free-spinning wheels keep the robot tracking straight and climbing thresholds.",
            ],
        },
    },
}


# ===========================================================================
# STEP-UP TIER DELTAS  —  DOCK / STATION components on top of the base 9.
# ===========================================================================
# Cross-checked across the Qrevo Curv (dock EWFD49LRR), S8 MaxV Ultra (EWFD13LRR),
# and Z70 manuals — all three describe these the same way, which is what validates
# the tier grouping. The tier's DIFFERENTIATOR is the DOCK, not the mop: every
# current mopping model uses removable FLAT mop cloths on mounts (single, or two on
# twin mounts) with the same remove-wash-airdry care — the true ROTATING roller mop
# is brand-new and rare (Qrevo Curv 2 Flow) and not covered yet, so there is no
# separate dual-pad tier. Composition is shallow (pure read-only data; callers deep-
# copy on read), so the base-9 dicts are shared, not duplicated.
_std = ROBOROCK_UPKEEP_GUIDE_LIBRARY["standard"]

_DOCK_DUST_BAG = {
    "clean_frequency": None,
    "replace_frequency": "when full (about every 7 weeks)",
    "steps": [
        "Open the dock's dust-compartment cover.",
        "Lift the full dust bag straight out — the handle seals it as you pull, so dust stays inside.",
        "Slide a new dust bag in until it seats, then close the cover.",
    ],
    "notes": [
        "Always have a bag installed before closing the cover, or the dock will auto-empty without one.",
        "If the dock has sat unused a while, empty the robot's dustbin by hand and check the air inlet is clear.",
    ],
}

_CLEAN_WATER_TANK = {
    "clean_frequency": "as needed",
    "replace_frequency": None,
    "steps": [
        "Lift the clean-water tank out of the dock and open its top cover.",
        "Fill it with cool tap water (add Roborock cleaning solution only if your dock supports it).",
        "Close the cover and seat the tank back in the dock.",
    ],
    "notes": [
        "Use cool water only — hot water can deform the tank.",
        "Wipe any water off the outside before refitting.",
    ],
}

_DIRTY_WATER_TANK = {
    "clean_frequency": "as needed",
    "replace_frequency": None,
    "steps": [
        "Open the dirty-water tank lid and pour the waste water out.",
        "Add a little clean water, close and lock the lid, shake, then pour it out again to rinse.",
        "Lock the lid and seat the tank back in the dock.",
    ],
    "notes": [
        "The dirty-water lid does not detach — rinse it in place.",
        "Use cool water only, and wipe the outside dry before refitting.",
    ],
}

# Station override of the base mop_cloth: the dock auto-washes it, so the routine
# changes from "after each use" to a weekly deep-rinse.
_MOP_CLOTH_STATION = {
    "clean_frequency": "the dock washes it each run; deep-rinse weekly",
    "replace_frequency": "every 1-3 months",
    "steps": [
        "The dock auto-washes and dries the mop after each run — no daily cleaning needed.",
        "Once a week, take the mop cloth(s) off the mount(s), rinse thoroughly, and air-dry.",
        "Press the cloth(s) back flat on the mount(s).",
    ],
    "notes": [
        "Whether a flat drag cloth, a vibrating VibraRise pad, or twin spinning discs, the care is the same — rinse and air-dry; clean both if your model carries two.",
        "A dirty or worn cloth hurts mopping; replace every 1-3 months.",
    ],
}

# auto_empty = base + a dust bag.  wash_station = auto_empty + water tanks + the
# station mop routine.  (dual_pad reserved for a future true rotating-mop model.)
ROBOROCK_UPKEEP_GUIDE_LIBRARY["auto_empty"] = {
    **_std,
    "dock_dust_bag": _DOCK_DUST_BAG,
}
ROBOROCK_UPKEEP_GUIDE_LIBRARY["wash_station"] = {
    **_std,
    "dock_dust_bag": _DOCK_DUST_BAG,
    "clean_water_tank": _CLEAN_WATER_TANK,
    "dirty_water_tank": _DIRTY_WATER_TANK,
    "mop_cloth": _MOP_CLOTH_STATION,
}
