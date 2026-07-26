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

    standard      no dock, single/no mop pad          (S4/S5/S6/S7, Q5/Q7, E, G…)
    auto_empty    + dust-collection dock              (Q5 Pro, Q7/Q8 Max, Q10)
    wash_station  + wash&dry dock, tanks, station filter (S7·S8 Pro Ultra, Q Revo…)
    dual_pad      + twin spinning mop pads (roller mops) (S8 MaxV Ultra, Qrevo Curv, Saros)

The manager overlays a localized copy PER FIELD, so any field left None/absent
falls back to English. Component keys match maintenance_components.py so each
guide attaches to its card. Content is sourced from Roborock's official manuals +
support pages, written as concise factual steps — intervals as stated by Roborock.
PURE DATA (no imports): scripts/sync-guide-translations.py loads this directly.

TODAY only `standard` is authored (from the S6 manual); it covers the whole
no-dock base lineup. The step-up tiers (their dock / roller-mop deltas) are the
next pass — until authored, upkeep_catalog maps their models to `standard` so
every model still gets the base guides.
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
