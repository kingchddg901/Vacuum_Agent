"""Dreame upkeep guide library — the guards that can actually go red.

The Dreame adapter is DATA ONLY and deliberately unwired, so none of the adapter
contract suites reach it. Before this file, nothing in the tree could fail on any
Dreame guide content: a family could be emptied, two families could be silently
collapsed into one, or the release switch could be thrown, and the suite stayed green.

The library now holds TWO kinds of family (see dreame_upkeep_guides.py):

  * TIER profiles (standard / auto_empty / wash_station / _track / _roller /
    _baseboard) — the composed default for the ~730 models with no authored manual.
  * AUTHORED families (x50, x60_ultra, x60_pro_ultra_complete, l20, x40, l50,
    l10s_gen2, aqua10_ultra_track, aqua10_ultra_roller, the 2026-08-31 batch:
    matrix10, l60_ultra, l60_ultra_pe, l40s_ultra, d30_ultra, d20_pro_plus, d20_plus,
    and the 2026-09-01 top-down-by-recency batch: x50_master)
    — measured off their own manuals, each its tier minus absent hardware, overriding
    every component its manual words differently. The override is the guard against the
    shared-base defect that was
    shipped once and reverted (commit d45e2ec4): a family NEVER inherits base prose for a
    component its manual stated differently. DUG-4 and DUG-6 pin exactly that.

[DUG-1]  No BRAND_REGISTRARS row for Dreame. That row is the release, and it is gated
         on a RELEASED upstream build carrying Tasshack #1707.
[DUG-2]  Every component in every family has at least one non-empty step and the four
         contract fields. A renamed or dropped family fails here, not silently.
[DUG-3]  x60_pro_ultra_complete is x60_ultra plus EXACTLY baseboard_brush, bodies
         otherwise identical — the relationship measured off the two manuals.
[DUG-4]  The X50 and the X60 are NOT the same family. The seven components measured to
         differ must keep differing — the regression guard for the shared-base defect.
[DUG-5]  Hardware a family does not have gets no guide: no heating module or baseboard
         brush on the X50, no separate auto-empty vents on the X60, no detergent inlet
         on any family but the L20.
[DUG-6]  The L50 and the X50 -- 11 of 13 components identical, the closest pair here --
         stay two families; the two that MUST differ, and the eleven that must stay the
         same, are both pinned.
[DUG-7]  The composed TIER profiles nest (auto_empty superset of standard, wash_station
         of auto_empty) and the mop tiers override the mop, not the brushes.
[DUG-8]  Every family the CATALOG routes a model to exists in the library — an unrouted
         family is a KeyError waiting for the release switch.
[DUG-9]  Cadence is SINGLE-SOURCED in COMPONENT_FREQUENCIES — no family carries its own
         frequency. The invariant the flat model rests on; before the flatten nothing
         checked frequencies at all (they were implicitly inherited from the tier base).
[DUG-10] Every cadence value is a KNOWN interval — a typo or an unregistered new interval
         fails here instead of rendering untranslated (the freq backfill only covers these).
[DUG-11] The reg-code (PLATFORM) promotions hold: models proven to be the same certified
         machine as an authored line (GoVac 800==X50/RLX85CE, L10s Ultra Gen 3 & L40 Ultra
         Gen 2==the L50 machine/RLH41CE, Aqua 10 Pro Track==Aqua10 Ultra Track/RLR81CE) route
         to that AUTHORED family, not the generic tier. Reverting any row to its old tier —
         or dropping GoVac 800 back to the no-station `standard` — goes red here.
[DUG-12] X50 Master (RLX86CE) is authored as the plumbed X50 — the real X50 maintenance
         minus the manual used-water tank (it auto-drains), with its own washboard-filter
         wording. Its SKUs route to x50_master, not the generic wash_station tier.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.dreame import (
    DREAME_MODEL_GUIDE_FAMILIES,
    DREAME_MODEL_NAMES,
    DREAME_GUIDE_FAMILY_NAMES,
    DREAME_UPKEEP_GUIDE_LIBRARY,
)
from custom_components.eufy_vacuum.adapters.dreame.dreame_upkeep_guides import (
    COMPONENT_FREQUENCIES,
)

#: the controlled cadence vocabulary. A NEW interval must be added here AND to
#: scripts/data/guide-frequency-translations.json (or it renders untranslated); this set is
#: the tripwire that forces both. ``None`` = a part with no replacement interval.
KNOWN_INTERVALS = {
    None, "after each use", "as needed", "weekly", "monthly",
    "every 1-2 months", "every 1-3 months", "every 2-4 months",
    "every 3-6 months", "every 6-12 months",
}

#: measured off their own manuals — the quality anchors.
AUTHORED_FAMILIES = (
    "x50",
    "x50_master",
    "x60_ultra",
    "x60_pro_ultra_complete",
    "l20",
    "x40",
    "l50",
    "l10s_gen2",
    "aqua10_ultra_track",
    "aqua10_ultra_roller",
    # overnight batch 2026-08-31: authored from the api-fetch corpus, provenance-scored
    # (d20_pro_plus's manual is a non-extractable font, verified via the OCR fallback).
    "matrix10",
    "l60_ultra",
    "l60_ultra_pe",
    "l40s_ultra",
    "d30_ultra",
    "d20_pro_plus",
    "d20_plus",
    # 2026-09-01 pipeline pilot (Sonnet extract -> Haiku classify -> deterministic emit),
    # authored from each model's own manual; DUG-2/5/9 gate them like any other family.
    "e30_ultra",
    "e50_ultra",
    "l50_pro_ultra",
    "l50s_ultra",
    "d20_ultra",
    "l40s_pro_ultra",
)

#: composed defaults for the unauthored tail.
TIER_FAMILIES = (
    "standard",
    "auto_empty",
    "wash_station",
    "wash_station_track",
    "wash_station_roller",
    "wash_station_baseboard",
)


# ── GENERATED families (2026-09-01): emitted by the staged authoring pipeline from each
# model's OWN English manual (durable/dreame-port-fixture/authoring). They live in
# dreame_upkeep_guides_generated.py and are merged onto the library with _with_cadence, so
# DUG-9 still holds: no generated block carries its own frequency. Listed here because a
# family key IS the routing key -- this guard is what makes an accidental rename loud.
GENERATED_FAMILIES_EXPECTED = (
    "1c",
    "1t",
    "2c",
    "aqua10_roller",
    "aqua10_roller_ae",
    "aqua10s_roller_ae",
    "aqua20_roller_fe",
    "c20_plus",
    "c30_plus",
    "c9",
    "d10_plus",
    "d10_plus_gen_2",
    "d10s",
    "d10s_plus",
    "d10s_pro",
    "d15",
    "d15_plus",
    "d20",
    "d20_air",
    "d20_air_plus",
    "d20_pro",
    "d30_ultra_ce",
    "d9",
    "d9_max",
    "d9_max_gen_2",
    "d9_plus",
    "d9_pro",
    "e10",
    "e10c",
    "e12",
    "e20",
    "e20_plus",
    "e20_pro",
    "e20_pro_plus",
    "e20s_pro",
    "e20s_pro_plus",
    "e30_aqua",
    "e30_pro_plus",
    "e40_ultra",
    "e5",
    "e50_pro_ultra",
    "f10",
    "f10_plus",
    "f20",
    "f20_eco",
    "f20_eco_plus",
    "f20_plus",
    "f21",
    "f21_plus",
    "f9",
    "f9_pro",
    "govac_100_lite",
    "govac_200",
    "govac_200_kit",
    "govac_200_lite",
    "govac_205_plus",
    "govac_300",
    "govac_300_kit",
    "govac_400",
    "govac_400_complete",
    "govac_500",
    "govac_508",
    "govac_510_complete",
    "govac_600",
    "l10_prime",
    "l10_pro",
    "l10_ultra",
    "l10s_plus",
    "l10s_plus_se",
    "l10s_pro",
    "l10s_pro_gen3",
    "l10s_pro_gen_2",
    "l10s_pro_gen_3",
    "l10s_pro_ultra",
    "l10s_pro_ultra_heat",
    "l10s_ultra",
    "l10s_ultra_ce",
    "l10s_ultra_heat",
    "l30_pro_ultra",
    "l30_ultra",
    "l30_ultra_s",
    "l30s_pro_ultra",
    "l30s_ultra",
    "l40",
    "l40_plus",
    "l40_ultra",
    "l40_ultra_ae",
    "l40_ultra_ce",
    "l40s_ultra_ae",
    "l40s_ultra_ce",
    "l50s_pro_ultra",
    "l50s_pro_ultra_complete",
    "l600",
    "l60_pro_ultra",
    "l60_ultra_ae",
    "m1",
    "matrix10_pro",
    "mi_robot_vacuum_mop_2",
    "mi_robot_vacuum_mop_2_pro",
    "mi_robot_vacuum_mop_2_ultra",
    "mi_robot_vacuum_mop_2_ultra_set",
    "mobius_60",
    "p10_pro_ultra_gen_2",
    "p10_ultra",
    "p10s_pro",
    "p20_ultra",
    "p50",
    "p50_pro_ultra",
    "p50_ultra",
    "p50s_ultra",
    "p70_pro",
    "p70_pro_ultra",
    "p70s",
    "s10",
    "s10_plus",
    "s10t",
    "s12",
    "s20",
    "s20_ultra",
    "s30",
    "s70_pro_roller",
    "s70_roller",
    "s70_ultra_roller",
    "t12",
    "v50_ultra",
    "v50_ultra_complete",
    "v60_mobius",
    "v70_ultra_complete",
    "v70_ultra_complete_x",
    "vacuum_mop_2_lite",
    "vacuum_mop_2_pro",
    "vacuum_mop_2i",
    "vacuum_mop_2s",
    "w10",
    "w10_pro",
    "x20",
    "x20_max",
    "x20_pro",
    "x30_master",
    "x30_ultra",
    "x40_master",
    "x40_pro_ultra",
    "x50_pro",
    "x50_pro_master",
    "x50_pro_ultra",
    "x50_pro_ultra_complete",
    "x50_ultra",
    "x60_master",
    "x70",
    "z10_pro",
    "z500",
    "z50_ultra",
    "z60_ultra_roller",
    "z60_ultra_roller_complete",
    "z60_ultra_roller_sa",
    "z60_ultra_roller_standalone",
    "z70_ultra_roller_complete",
    "z70_ultra_roller_se",
    "z_series",
)


# ── TRANSLATED families (2026-09-02): manuals that are NOT in English (87 Chinese, plus
# ru/ko/ja/de/nl/fr/it), extracted from each model's OWN manual and translated DIRECT to English
# (never pivoted), anchored on Dreame's own English wording. They live in
# dreame_upkeep_guides_translated.py and merge onto the library with _with_cadence, so DUG-9 still
# holds. Listed here because a family key IS the routing key — this guard makes a rename loud.
# ⚠ The NATIVE-language source text is preserved (durable/.../authoring/slices_nonen/); the
# per-language packs must LIFT from it, never be back-translated from this English.
TRANSLATED_FAMILIES_EXPECTED = (
    "10",
    "10_robot_vacuum_and_mop",
    "1s",
    "2",
    "3",
    "3c",
    "aqua10_pro_roller",
    "aqua_10_pro_roller",
    "aqua_10_roller",
    "clean_master_x60_pro_steam",
    "cleaning_and_mopping_robot_2_pro",
    "d9_max_gen_2_se",
    "g20",
    "g20_master",
    "g20_pro",
    "g30",
    "g30_pro",
    "h40",
    "l10_plus",
    "l10s_prime",
    "l20s_plus",
    "l20s_pro",
    "l50s_pro_nano",
    "lds_finder",
    "m30",
    "m30_pro",
    "m40",
    "m40_s",
    "m50_ultra",
    "master_one",
    "master_pro",
    "mi_robot_vacuum_mop",
    "mop_ultra_slim",
    "omni_2",
    "omni_m30s",
    "p10_pro_ultra",
    "p10s_ultra",
    "pro",
    "s10_pro",
    "s10_pro_max",
    "s10_pro_plus",
    "s10_pro_ultra",
    "s20_plus",
    "s20_pro_plus",
    "s30_pro",
    "s30_pro_ultra",
    "s30_pro_ultra_gen_2",
    "s30_ultra_member",
    "s40",
    "s40_member",
    "s40_pro",
    "s40_pro_ultra",
    "s50",
    "s50_max",
    "s50_max_d",
    "s50_plus",
    "s50_pro",
    "s50_ultra",
    "s60",
    "s60_disk",
    "s60_premium_roller",
    "s60_pro",
    "s60_pro_disc",
    "s60_pro_roller",
    "s60_roller",
    "self_cleaning_robot_vacuum_mop",
    "self_cleaning_robot_vacuum_mop_pro",
    "v30",
    "v30_pro",
    "vacuum_mop_2",
    "vacuum_mop_pro",
    "w10s",
    "w10s_pro",
    "w20_pro",
    "w20_pro_ultra",
    "x10",
    "x10_ultra",
    "x20_pro_plus",
    "x30",
    "x30_pro",
    "x30s_pro",
    "x40_pro",
    "x40_pro_plus",
    "x50_plus",
    "x50s_pro_master",
    "x50s_pro_ultra",
    "x60_pro",
    "x60_pro_disc",
    "x60_pro_roller",
    "x60_track",
    "x_series",
)

ALL_FAMILIES = AUTHORED_FAMILIES + TIER_FAMILIES + GENERATED_FAMILIES_EXPECTED + TRANSLATED_FAMILIES_EXPECTED


def test_dreame_has_no_brand_registrar_row():
    """[DUG-1] the switch is off, and this is the test that notices it being thrown."""
    from custom_components.eufy_vacuum.adapters.brands import BRAND_REGISTRARS

    assert BRAND_REGISTRARS, "no brands registered — this test is anchored wrong"
    brands = {r.brand_id for r in BRAND_REGISTRARS}
    assert "dreame" not in brands, (
        "Dreame has a BRAND_REGISTRARS row. That row IS the release and it is gated on "
        "a released upstream build carrying Tasshack #1707 — our #1742 is closed as a "
        "duplicate and reads green, which it is not. If the gate has genuinely cleared, "
        "this test is the thing to delete, deliberately."
    )


def test_every_family_is_present():
    """[DUG-2] a renamed or dropped family fails here, not silently."""
    assert set(DREAME_UPKEEP_GUIDE_LIBRARY) == set(ALL_FAMILIES), (
        f"families are {sorted(DREAME_UPKEEP_GUIDE_LIBRARY)}, expected {sorted(ALL_FAMILIES)}. "
        "A family key is the routing key, so renaming one silently unroutes every model "
        "that pointed at it — update the lists here deliberately, with the manual in hand."
    )


@pytest.mark.parametrize("family", ALL_FAMILIES)
def test_every_component_has_steps_and_fields(family):
    """[DUG-2] an entry with NOTHING to render is worse than an absent one.

    Relaxed 2026-09-01 from "must have steps" to "must have steps OR notes". Some manuals
    give a component a CAUTION but draw the procedure only as a diagram, so the extraction
    yields notes and no steps. That still renders usefully (part + cadence + caution) — an
    entry with neither is the empty row this guard exists to stop. Cadence alone does not
    qualify: _with_cadence gives every component one, so it cannot discriminate.
    """
    fam = DREAME_UPKEEP_GUIDE_LIBRARY[family]
    assert fam, f"{family} is empty"
    for component, guide in fam.items():
        steps = guide.get("steps")
        assert steps or guide.get("notes"), f"{family}.{component} has neither steps nor notes"
        assert all(
            isinstance(s, str) and s.strip() for s in steps
        ), f"{family}.{component} has a blank step"
        assert isinstance(guide.get("notes", []), list)
        # the four-field contract (mirrors Roborock/Eufy) — frequencies may be None but
        # the keys must be present so the card and the translation sync never KeyError.
        for field in ("clean_frequency", "replace_frequency", "steps", "notes"):
            assert field in guide, f"{family}.{component} is missing {field}"


def test_x60_complete_is_ultra_plus_baseboard_brush_only():
    """[DUG-3] the one place prose is shared, and only because it was diffed first."""
    ultra = DREAME_UPKEEP_GUIDE_LIBRARY["x60_ultra"]
    complete = DREAME_UPKEEP_GUIDE_LIBRARY["x60_pro_ultra_complete"]

    assert set(complete) - set(ultra) == {"baseboard_brush"}, (
        "x60_pro_ultra_complete adds something other than the baseboard brush. The two "
        "manuals were diffed sentence by sentence and that brush was the whole delta — "
        "a second extra means the diff needs redoing, not extending."
    )
    assert set(ultra) - set(complete) == set(), (
        "x60_ultra has a component the Pro Ultra Complete lacks. The Complete is a "
        "superset by construction; this means the two have been edited independently."
    )
    for component, guide in ultra.items():
        assert guide == complete[component], (
            f"x60_ultra.{component} and x60_pro_ultra_complete.{component} have "
            "drifted apart. Their manuals (R5089B, R6001) print the same text; if one "
            "genuinely changed, re-diff BOTH manuals and record the new delta."
        )


#: Measured against R2489A (X50) and R5089B (X60 Ultra), page by page. Each of these is
#: a hardware difference, not a wording one.
X50_X60_MUST_DIFFER = (
    "main_brush",  # X50 ships a cleaning tool; the X60 manual says "a proper tool"
    "dustbin",  # the X50's dust box sits under a robot cover; the X60's does not
    "dust_bag",  # X50 splits install/reinstall into two steps; the X60 merges them
    "dirty_water_tank",  # provided cleaning tool vs "a proper tool" again
    "washboard_filter",  # the X60 warns of a heating module the X50 has not got
    "sensor",  # X50 3D dual-line laser vs X60 dust illumination light
    "dock_contacts",  # the X60 folds the auto-empty vents into this section
)


@pytest.mark.parametrize("component", X50_X60_MUST_DIFFER)
def test_x50_and_x60_do_not_share_prose(component):
    """[DUG-4] the regression guard for the shared-base defect this file once shipped."""
    x50 = DREAME_UPKEEP_GUIDE_LIBRARY["x50"][component]
    x60 = DREAME_UPKEEP_GUIDE_LIBRARY["x60_ultra"][component]
    assert x50 != x60, (
        f"x50.{component} is now identical to x60_ultra.{component}. These were read "
        "off two different manuals and measured to differ. Identical content means the "
        "override was dropped and both now inherit the tier base — which is exactly how "
        "a user ends up told to unscrew a brush that clips."
    )


#: The L50 and the X50 share 11 of 13 components outright — the closest pair in the file.
L50_X50_MUST_DIFFER = (
    "dustbin",  # L50 OPENS the robot cover; the X50 REMOVES it
    "sensor",  # L50 has an LDS and no VersaLift; the X50 has a VersaLift and no LDS
)


@pytest.mark.parametrize("component", L50_X50_MUST_DIFFER)
def test_l50_and_x50_do_not_share_prose(component):
    """[DUG-6] eleven of thirteen identical is not thirteen, and the two carry hardware."""
    l50 = DREAME_UPKEEP_GUIDE_LIBRARY["l50"][component]
    x50 = DREAME_UPKEEP_GUIDE_LIBRARY["x50"][component]
    assert l50 != x50, (
        f"l50.{component} is now identical to x50.{component}. These two families are "
        "close enough to look mergeable and are not: one word in `dustbin` and one "
        "sensor in `sensor` are the entire difference, and both are hardware."
    )


def test_the_two_close_families_are_still_mostly_identical():
    """[DUG-6] the other half — the 11/13 figure DUG-6 rests on, pinned."""
    l50 = DREAME_UPKEEP_GUIDE_LIBRARY["l50"]
    x50 = DREAME_UPKEEP_GUIDE_LIBRARY["x50"]
    common = set(l50) & set(x50)
    identical = {c for c in common if l50[c] == x50[c]}
    assert len(common) == 13 and len(identical) == 11, (
        f"l50/x50 overlap is now {len(identical)} identical of {len(common)} common, "
        "measured as 11 of 13. If the manuals were re-read and this genuinely changed, "
        "update the number here AND the block comment in the guide file together."
    )
    assert common - identical == set(L50_X50_MUST_DIFFER), (
        f"the l50/x50 differences are now {sorted(common - identical)}, not "
        f"{sorted(L50_X50_MUST_DIFFER)} — a component changed sides."
    )


@pytest.mark.parametrize(
    ("family", "component"),
    [
        ("x50", "washboard_heating_module"),  # absent from the X50 parts table
        ("x50", "baseboard_brush"),  # absent from the X50 parts table
        ("x60_ultra", "auto_empty_vents"),  # folded into dock_contacts on the X60
        ("x60_pro_ultra_complete", "auto_empty_vents"),
        ("x60_ultra", "baseboard_brush"),  # R5089B lists no baseboard brush
        # The washboard is one part or the other, never both: the X50 and L50 service a
        # removable FILTER, the L20 and X40 service the washboard ITSELF.
        ("l50", "washboard"),
        ("l20", "washboard_filter"),
        ("x40", "washboard_filter"),
        ("l50", "washboard_heating_module"),
        ("l20", "baseboard_brush"),
        ("x40", "baseboard_brush"),
        ("l50", "baseboard_brush"),
        # Auto-detergent dosing is the L20's alone among these seven.
        ("x50", "detergent_inlet"),
        ("x40", "detergent_inlet"),
        ("l50", "detergent_inlet"),
        ("x60_ultra", "detergent_inlet"),
        ("l10s_gen2", "detergent_inlet"),
    ],
)
def test_absent_hardware_gets_no_guide(family, component):
    """[DUG-5] silence beats confident instructions about a part that is not there."""
    assert component not in DREAME_UPKEEP_GUIDE_LIBRARY[family], (
        f"{family} now has a {component} guide. Its manual does not list that part, so "
        "this describes hardware the owner does not have."
    )


def test_tiers_nest_and_mop_is_an_override_axis():
    """[DUG-7] the composed tail profiles are supersets up the dock ladder, and the mop
    tiers change the mop, not the brushes — the property the composition is FOR."""
    lib = DREAME_UPKEEP_GUIDE_LIBRARY
    assert set(lib["standard"]) < set(lib["auto_empty"]), "auto_empty must add to standard"
    assert set(lib["auto_empty"]) < set(lib["wash_station"]), "wash_station must add to auto_empty"
    # the dock ladder shares component prose where it does not add hardware
    for component in lib["standard"]:
        assert lib["standard"][component] == lib["auto_empty"][component] == lib["wash_station"][component], (
            f"{component} drifted across the dock ladder — the tiers no longer compose "
            "from one base, which is the whole point of them."
        )
    # the mop tiers override ONLY the mop components, leaving the brushes/sensors alone
    for mop_tier in ("wash_station_track", "wash_station_roller"):
        changed = {c for c in lib["wash_station"] if lib["wash_station"][c] != lib[mop_tier].get(c)}
        assert changed <= {"mop_cloth", "mop_pad_holder"}, (
            f"{mop_tier} changed {changed - {'mop_cloth', 'mop_pad_holder'}} beyond the "
            "mop — a mop variant must not rewrite the main brush."
        )


def test_every_catalog_family_exists_in_the_library():
    """[DUG-8] the catalog is the routing table; a family it names that the library lacks
    is a KeyError the moment the release switch is thrown and a device resolves to it."""
    used = set(DREAME_MODEL_GUIDE_FAMILIES.values())
    assert used <= set(DREAME_UPKEEP_GUIDE_LIBRARY), (
        f"catalog routes models to {sorted(used - set(DREAME_UPKEEP_GUIDE_LIBRARY))} which "
        "the library does not define. Every routed family must resolve to a guide."
    )
    assert used <= set(DREAME_GUIDE_FAMILY_NAMES), (
        f"{sorted(used - set(DREAME_GUIDE_FAMILY_NAMES))} has no display name in "
        "DREAME_GUIDE_FAMILY_NAMES — the card would show a bare routing key."
    )


#: reg-code (PLATFORM) promotions — (model, expected authored family, proving reg-code).
#: Each is the SAME certified machine as an authored line (verify_rebadge_claims.py's rule
#: "two names sharing an r-code are the same hardware, proof not inference"), so it must get
#: that line's measured guide, not the generic tier it defaulted to. The bite input is the
#: old tier: revert a row and the family assertion goes red naming the model.
REGCODE_PROMOTIONS = [
    ("dreame.vacuum.r2489d", "x50", "RLX85CE"),   # GoVac 800  (was `standard`)
    ("dreame.vacuum.r95385", "x50", "RLX85CE"),   # GoVac 800  (was `standard`)
    ("dreame.vacuum.r501h", "l50", "RLH41CE"),    # L10s Ultra Gen 3 (was `wash_station`)
    ("dreame.vacuum.r501he", "l50", "RLH41CE"),   # L10s Ultra Gen 3
    ("dreame.vacuum.r501t", "l50", "RLH41CE"),    # L40 Ultra Gen 2
    ("dreame.vacuum.r501tt", "l50", "RLH41CE"),   # L10s Ultra Gen 3
    ("dreame.vacuum.r5023a", "l50", "RLH41CE"),   # L10s Ultra Gen 3
    ("dreame.vacuum.r5023e", "l50", "RLH41CE"),   # L10s Ultra Gen 3
    ("dreame.vacuum.r5025b", "l50", "RLH41CE"),   # L10s Ultra Gen 3
    ("dreame.vacuum.r5025t", "l50", "RLH41CE"),   # L10s Ultra Gen 3
    ("dreame.vacuum.r2527b", "aqua10_ultra_track", "RLR81CE"),  # Aqua 10 Pro Track (was _track tier)
    ("dreame.vacuum.r2527j", "aqua10_ultra_track", "RLR81CE"),  # Aqua 10 Pro Track
    ("dreame.vacuum.r2527t", "aqua10_ultra_track", "RLR81CE"),  # Aqua 10 Pro Track
    ("dreame.vacuum.r2527u", "aqua10_ultra_track", "RLR81CE"),  # Aqua 10 Pro Track
]


@pytest.mark.parametrize("model,family,regcode", REGCODE_PROMOTIONS)
def test_regcode_promotion_routes_to_authored_family(model, family, regcode):
    """[DUG-11] a same-machine model gets the authored guide, not the generic tier."""
    got = DREAME_MODEL_GUIDE_FAMILIES.get(model)
    assert got == family, (
        f"{model} routes to {got!r}, expected {family!r} — it is the same certified "
        f"machine ({regcode}) as an authored line and must share its measured guide."
    )
    assert family in AUTHORED_FAMILIES, (
        f"{family} is not an authored family — the promotion's whole point is a "
        "manual-specific guide, not a generic tier."
    )


def test_govac800_station_is_promoted_from_standard():
    """[DUG-11] GoVac 800 == X50 (RLX85CE) has the full wash dock (dual tank, mop self-clean,
    per its retail spec). The old `standard` tier declared has_station=False, hiding its real
    dock controls; the `x50` promotion must restore the full station. Red if it reverts."""
    from custom_components.eufy_vacuum.adapters.dreame.model_catalog import profile_for_model

    prof = profile_for_model("dreame.vacuum.r2489d")
    assert prof["family"] == "x50"
    assert prof["has_station"] and prof["station_washable"] and prof["station_dryable"], (
        f"GoVac 800 profile lost its station: {prof} — `standard` under-claimed the dock; "
        "x50 falls through to the full-station DEFAULT_PROFILE, which is correct."
    )


def test_x50_master_is_the_plumbed_x50_not_generic():
    """[DUG-12] X50 Master (RLX86CE) is the plumbed X50 — automatic water supply and
    drainage — so its authored guide is the real X50 maintenance MINUS the manual
    used-water tank, plus its own washboard-filter wording. Routing its SKUs to the
    generic wash_station tier (the pre-authoring state) is the bug this bites: generic
    prose, and a used-water-tank guide for hardware it does not have (DUG-5)."""
    x50 = DREAME_UPKEEP_GUIDE_LIBRARY["x50"]
    master = DREAME_UPKEEP_GUIDE_LIBRARY["x50_master"]

    assert "dirty_water_tank" in x50, "anchor: X50 Ultra DOES have a manual used-water tank"
    assert "dirty_water_tank" not in master, (
        "X50 Master auto-drains — a used-water-tank guide is hardware it lacks"
    )
    # washboard_filter is measured off X50 Master's OWN manual, not inherited from _X50.
    wb = " ".join(master["washboard_filter"]["steps"])
    assert "washboard base clips" in wb, (
        "washboard_filter must carry X50 Master's own wording (names the base clips)"
    )
    assert master["washboard_filter"]["steps"] != x50["washboard_filter"]["steps"]
    # every X50 Master SKU routes to the authored family, not the generic tier.
    masters = [m for m, n in DREAME_MODEL_NAMES.items() if n == "X50 Master"]
    assert masters, "anchor: X50 Master must be a catalogued platform"
    for m in masters:
        assert DREAME_MODEL_GUIDE_FAMILIES[m] == "x50_master", (
            f"{m} (X50 Master) routes to {DREAME_MODEL_GUIDE_FAMILIES[m]!r}, not x50_master"
        )


def test_frequencies_are_single_sourced():
    """[DUG-9] cadence lives ONLY in COMPONENT_FREQUENCIES — no family carries its own.

    This is the invariant the flat model rests on: steps/notes are per-manual, frequencies
    are one shared owned map. Before the flatten they were inherited implicitly from the
    tier base and NOTHING checked them. This bites if a family dict grows its own
    ``clean_frequency``/``replace_frequency`` (which ``_with_cadence`` would let silently
    override the map), or if the map drifts from what a family renders."""
    for family, comps in DREAME_UPKEEP_GUIDE_LIBRARY.items():
        for component, guide in comps.items():
            assert component in COMPONENT_FREQUENCIES, (
                f"{family}.{component} has no cadence in COMPONENT_FREQUENCIES"
            )
            for field in ("clean_frequency", "replace_frequency"):
                assert guide.get(field) == COMPONENT_FREQUENCIES[component][field], (
                    f"{family}.{component}.{field} = {guide.get(field)!r} but the owned map "
                    f"says {COMPONENT_FREQUENCIES[component][field]!r} — cadence is not "
                    "per-family; put it in COMPONENT_FREQUENCIES or you have introduced drift."
                )


def test_cadence_vocabulary_is_controlled():
    """[DUG-10] every cadence value is a known interval. A typo (\"montly\") or a new
    unregistered interval fails here rather than rendering untranslated on the card — the
    frequency backfill (guide-frequency-translations.json) only covers KNOWN_INTERVALS."""
    for component, cad in COMPONENT_FREQUENCIES.items():
        for field in ("clean_frequency", "replace_frequency"):
            assert cad[field] in KNOWN_INTERVALS, (
                f"{component}.{field} = {cad[field]!r} is not a known interval; add it to "
                "KNOWN_INTERVALS and to scripts/data/guide-frequency-translations.json."
            )
