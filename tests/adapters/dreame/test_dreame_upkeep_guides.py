"""Dreame upkeep guide library — the guards that can actually go red.

The Dreame adapter is DATA ONLY and deliberately unwired, so none of the adapter
contract suites reach it. Before this file, nothing in the tree could fail on any
Dreame guide content: a family could be emptied, two families could be silently
collapsed into one, or the release switch could be thrown, and the suite stayed green.

[DUG-1]  No BRAND_REGISTRARS row for Dreame. That row is the release, and it is gated
         on a RELEASED upstream build carrying Tasshack #1707.
[DUG-2]  Every component in every family has at least one non-empty step.
[DUG-3]  x60_pro_ultra_complete is x60_ultra plus EXACTLY baseboard_brush, bodies
         otherwise identical — the relationship that was measured off the two manuals
         (48 of 49 care sentences shared) rather than assumed.
[DUG-4]  The X50 and the X60 are NOT the same family. The seven components measured to
         differ must keep differing. This is the regression guard for the defect this
         file already shipped once: a shared `_BASE` factored out because the component
         NAMES lined up, which put X60 prose on five other platforms.
[DUG-5]  Hardware a family does not have gets no guide: no heating module or baseboard
         brush on the X50, no separate auto-empty vents on the X60 (its manual prints
         vents, contacts and signalling as one section), no detergent inlet on any
         family but the L20.
[DUG-6]  The L50 and the X50 -- 33 shared care sentences, 11 of 13 components identical,
         the closest pair here -- stay two families. Both halves are pinned: the two
         components that MUST differ, and the eleven that must stay the same, because a
         difference-guard alone goes green on a corpus that has simply rotted.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.dreame import DREAME_UPKEEP_GUIDE_LIBRARY

FAMILIES = (
    "x50",
    "x60_ultra",
    "x60_pro_ultra_complete",
    "l20",
    "x40",
    "l50",
    "l10s_gen2",
)


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
    """[DUG-2] anchor: a renamed or dropped family fails here, not silently."""
    assert set(DREAME_UPKEEP_GUIDE_LIBRARY) == set(FAMILIES), (
        f"families are {sorted(DREAME_UPKEEP_GUIDE_LIBRARY)}, expected {sorted(FAMILIES)}. "
        "A family key is the routing key, so renaming one silently unroutes every model "
        "that pointed at it — update FAMILIES deliberately, with the manual in hand."
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_every_component_has_steps(family):
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
#: a hardware difference, not a wording one — see the block comment above ``_X50``.
X50_X60_MUST_DIFFER = (
    "main_brush",  # X50 ships a cleaning tool; the X60 manual says "a proper tool"
    "dustbin",  # the X50's dust box sits under a robot cover; the X60's does not
    "dust_bag",  # X50 splits install/reinstall into two steps; the X60 merges them
    "used_water_tank",  # provided cleaning tool vs "a proper tool" again
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
        "off two different manuals and measured to differ. Identical content means "
        "someone factored a shared base out of two families — which is exactly how a "
        "user ends up told to unscrew a brush that clips."
    )


#: The L50 and the X50 share 33 care sentences and 11 of 13 components outright — the
#: closest pair in the file, and the one most likely to invite "these are the same
#: family". They are not, and the whole of the difference is here.
L50_X50_MUST_DIFFER = (
    "dustbin",  # L50 OPENS the robot cover; the X50 REMOVES it
    "sensor",  # L50 has an LDS and no VersaLift; the X50 has a VersaLift and no LDS
)


@pytest.mark.parametrize("component", L50_X50_MUST_DIFFER)
def test_l50_and_x50_do_not_share_prose(component):
    """[DUG-6] eleven of thirteen identical is not thirteen, and the two carry hardware.

    This is the case DUG-3 is NOT. The X60 pair could share a body because their delta
    was a whole extra component; here the delta lives INSIDE two shared components, so
    merging them would quietly rewrite the two that matter — telling an L50 owner to
    wipe a VersaLift sensor their robot has not got, and never mentioning its LDS.
    """
    l50 = DREAME_UPKEEP_GUIDE_LIBRARY["l50"][component]
    x50 = DREAME_UPKEEP_GUIDE_LIBRARY["x50"][component]
    assert l50 != x50, (
        f"l50.{component} is now identical to x50.{component}. These two families are "
        "close enough to look mergeable and are not: one word in `dustbin` and one "
        "sensor in `sensor` are the entire difference, and both are hardware."
    )


def test_the_two_close_families_are_still_mostly_identical():
    """[DUG-6] the other half — the 11/13 figure DUG-6 rests on, pinned.

    Without this, deleting content from either family would make them 'differ' more and
    DUG-6 would go green on a corpus that had rotted. A guard on a difference needs the
    sameness pinned too, or it passes for the wrong reason.
    """
    l50 = DREAME_UPKEEP_GUIDE_LIBRARY["l50"]
    x50 = DREAME_UPKEEP_GUIDE_LIBRARY["x50"]
    common = set(l50) & set(x50)
    identical = {c for c in common if l50[c] == x50[c]}
    assert len(common) == 13 and len(identical) == 11, (
        f"l50/x50 overlap is now {len(identical)} identical of {len(common)} common, "
        "measured as 11 of 13. If the manuals were re-read and this genuinely changed, "
        "update the number here AND the block comment above `_L50` together."
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
