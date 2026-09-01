"""Dreame upkeep guide library — the guards that can actually go red.

The Dreame adapter is DATA ONLY and deliberately unwired, so none of the adapter
contract suites reach it. Before this file, nothing in the tree could fail on any
Dreame guide content: a family could be emptied, two families could be silently
collapsed into one, or the release switch could be thrown, and the suite stayed green.

The library now holds TWO kinds of family (see dreame_upkeep_guides.py):

  * TIER profiles (standard / auto_empty / wash_station / _track / _roller /
    _baseboard) — the composed default for the ~730 models with no authored manual.
  * AUTHORED families (x50, x60_ultra, x60_pro_ultra_complete, l20, x40, l50,
    l10s_gen2, aqua10_ultra_track, aqua10_ultra_roller, and the 2026-08-31 batch:
    matrix10, l60_ultra, l60_ultra_pe, l40s_ultra, d30_ultra, d20_pro_plus, d20_plus)
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
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.dreame import (
    DREAME_MODEL_GUIDE_FAMILIES,
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

ALL_FAMILIES = AUTHORED_FAMILIES + TIER_FAMILIES


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
    """[DUG-2] an entry with no steps is worse than an absent one — it renders empty."""
    fam = DREAME_UPKEEP_GUIDE_LIBRARY[family]
    assert fam, f"{family} is empty"
    for component, guide in fam.items():
        steps = guide.get("steps")
        assert steps, f"{family}.{component} has no steps"
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
