# -*- coding: utf-8 -*-
"""[RUK] Roborock on the shared regime → key guide.

Replaces the three authored guide families and the hand-assigned maintenance TIER that chose
between them. The tier is not corrected here — it is deleted, and `dock_tier` is measured per
model in the fixture manifest instead.
"""

from __future__ import annotations

import json

from custom_components.eufy_vacuum.adapters.dreame.upkeep_keys import DREAME_UPKEEP_KEYS
from custom_components.eufy_vacuum.adapters.roborock.maintenance_components import (
    MAINTENANCE_COMPONENTS,
)
from custom_components.eufy_vacuum.adapters.roborock.upkeep_catalog import ROBOROCK_MODEL_NAMES
from custom_components.eufy_vacuum.adapters.roborock.upkeep_keys import (
    ROBOROCK_MODEL_KEY_REGIMES,
    ROBOROCK_UPKEEP_KEY_GUIDES,
    ROBOROCK_UPKEEP_KEYS,
)
from custom_components.eufy_vacuum.adapters.roborock.upkeep_regimes import (
    ROBOROCK_MODEL_REGIMES,
)


def test_roborock_adds_no_new_keys():
    """[RUK-1] 41 models and not one new authored string.

    Its whole washing-cloth lineup — every VibraRise machine and the Qrevo line — emits a card
    set identical to Dreame's SimuMop shapes, because `SimuMop` normalises to `cloth` at
    generation. An unauthored key would render as its own name, and every count below would
    still be green.
    """
    unauthored = ROBOROCK_UPKEEP_KEYS - DREAME_UPKEEP_KEYS
    assert not unauthored, f"Roborock emits {sorted(unauthored)}, which nobody authored"


def test_declared_and_emitted_components_agree():
    """[RUK-2] an emitted-but-undeclared panel has no binding; a declared-but-unemitted one
    can never render. Neither raises."""
    declared = set(MAINTENANCE_COMPONENTS)
    emitted = {c for guide in ROBOROCK_UPKEEP_KEY_GUIDES.values() for c in guide}
    assert emitted - declared == set(), f"emitted but undeclared: {sorted(emitted - declared)}"
    assert declared - emitted == set(), f"declared but never emitted: {sorted(declared - emitted)}"


def test_it_is_seven_components():
    """[RUK-3] 14 → 7, and the eight that went are rulings, not a tidy-up."""
    assert set(MAINTENANCE_COMPONENTS) == {
        "main_brush", "side_brush", "filter", "sensor",
        "mop", "omnidirectional_wheel", "cleaning_tray",
    }
    gone = {"cleaning_brush", "strainer", "dustbin", "water_filter",
            "dust_bag", "clean_water_tank", "dirty_water_tank", "main_wheel",
            "mop_cloth", "caster_wheel"}
    assert not (set(MAINTENANCE_COMPONENTS) & gone)


def test_every_model_is_named_and_routed():
    """[RUK-4] a model in one table and not the other is a card that cannot render, or a name
    for a machine nothing routes."""
    assert set(ROBOROCK_MODEL_NAMES) == set(ROBOROCK_MODEL_KEY_REGIMES) == set(ROBOROCK_MODEL_REGIMES)
    assert len(ROBOROCK_MODEL_NAMES) == 41


def test_the_eight_the_tier_column_got_wrong():
    """[RUK-5] THE WALK-BACK, pinned. The old tier was wrong on 8 of 41, in BOTH directions.

    Under-tiered: four China-market machines shipped as `standard` — no dock at all — when they
    carry one. Over-tiered: four Q-series shipped as `auto_empty` because the "+" variant's dock
    was read as the model's, when the base SKU has none. The second group disagreed with the
    shipped table's OWN convention too: the S7, S7 MaxV and S8 have the same optional-dock
    arrangement and were correctly left at `standard`.
    """
    regimes = ROBOROCK_MODEL_KEY_REGIMES
    assert regimes["roborock.vacuum.a29"] == "cloth|wash_only|yes"       # G10 — washes, never empties
    assert regimes["roborock.vacuum.a46"] == "cloth|wash+empty|yes"      # G10S
    assert regimes["roborock.vacuum.a26"] == "cloth|wash+empty|yes"      # G10S Pro
    assert regimes["roborock.vacuum.a23"] == "cloth|auto_empty|no"       # T7S Plus
    for sku, name in (("a38", "Q7 Max"), ("a72", "Q5 Pro"),
                      ("a73", "Q8 Max"), ("ss07", "Q10")):
        assert regimes["roborock.vacuum.%s" % sku].endswith("|charge_only|no"), (
            f"{name} has no dock at base SKU"
        )


# anchor: RNARRS0S
def test_twin_flat_cloths_are_not_a_roller():
    """[RUK-6] RNARRS0S, REHOUSED — the rule outlived both of its original sites.

    It was a REPLICA anchor across `roborock_upkeep_guides.py`'s tier docstring and
    `upkeep_catalog.py`'s model table, which both reserved a `dual_pad` tier for a true
    ROTATING roller mop and kept twin-mount flat cloths on `wash_station`. This port deleted
    the guide library and the tier column, so there is no longer a second place saying it and
    it cannot be a replica. Chris: *"its a good rule but cant survive as is."*

    IT SURVIVES BETTER AS A MEASUREMENT, because the distinction it protected is now a measured
    field rather than a reserved tier. Two flat cloths on twin mounts are the SAME JOB as one
    cloth — peel off, wash, dry, refit — so they are `cloth` or `pad`. `roller` means a rotating
    assembly that lifts out of a compartment, which is a different set of hands entirely and
    emits different steps.

    THE INPUT THAT MAKES THIS RED: type any of these five as `roller` and its owners are told to
    take a mop assembly out of a compartment their machine does not have. As a doc reservation
    that was unfalsifiable; here it fails.

    Roborock ships NO roller today, which is exactly why this is worth pinning: the roller
    branch rests entirely on Dreame and Eufy evidence, so a wrong Roborock measurement has
    nothing else to contradict it.
    """
    twin_flat_cloth = {
        "roborock.vacuum.a97": "S8 MaxV Ultra",
        "roborock.vacuum.a135": "Qrevo Curv",
        "roborock.vacuum.a117": "Qrevo Master",
        "roborock.vacuum.a144": "Saros 10R",
        "roborock.vacuum.a143": "G20S Ultra",
    }
    for model, name in twin_flat_cloth.items():
        mop_type = ROBOROCK_MODEL_REGIMES[model][0]
        assert mop_type in ("cloth", "pad"), (
            f"{name} carries twin FLAT cloths, which is the same job as one cloth — typing it "
            f"{mop_type!r} emits roller steps for a compartment it does not have"
        )

    assert not any(r[0] in ("roller", "track") for r in ROBOROCK_MODEL_REGIMES.values()), (
        "Roborock ships no roller or track mop. If one genuinely lands, measure it from its "
        "manual and delete this line deliberately — do not widen the assertion to make a "
        "surprise pass"
    )


def test_the_collapse_holds():
    """[RUK-7] 41 models, 6 regimes, 4 cards."""
    bodies = {
        json.dumps(ROBOROCK_UPKEEP_KEY_GUIDES[r], sort_keys=True)
        for r in ROBOROCK_MODEL_KEY_REGIMES.values()
    }
    assert len(ROBOROCK_MODEL_REGIMES) == 41
    assert len(ROBOROCK_UPKEEP_KEY_GUIDES) == 6, f"{len(ROBOROCK_UPKEEP_KEY_GUIDES)} regimes, expected 6"
    assert len(bodies) == 4, (
        f"{len(bodies)} distinct card SETS, expected 4. NOTE THE UNIT: unique whole-card-SETS, "
        "not panels. Change it deliberately and say whether it was a merge or a retirement."
    )
