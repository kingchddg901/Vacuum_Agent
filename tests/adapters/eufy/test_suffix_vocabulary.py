"""Eufy suffix vocabulary — the brand-specific half of live:ENT-4.

The core exclusivity rule is proved brand-agnostically in
tests/integration/test_core_capabilities.py [CAP-12]. What can only be checked
HERE is that the real Eufy vocabulary actually contains the colliding pair, and
that the adapter hands it to detect_capabilities. Either half missing and the
core guard is correct but never armed on real hardware — which is exactly the
shape issue #49 arrived in.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.adapters.eufy.entities import (
    ALL_SUFFIXES,
    SUFFIX_CLEANING_AREA,
    SUFFIX_CLEANING_TIME,
    SUFFIX_TOTAL_CLEANING_AREA,
    SUFFIX_TOTAL_CLEANING_TIME,
)


def test_vocabulary_contains_the_colliding_pairs():
    """The pair that made this necessary must be present, both halves.

    `_cleaning_area` is a substring of `_total_cleaning_area`, so without the
    longer one declared the shorter role claims BOTH entities and can resolve
    to the lifetime counter. Confirmed on the issue #49 device, which carries
    both.
    """
    for shorter, longer in (
        (SUFFIX_CLEANING_AREA, SUFFIX_TOTAL_CLEANING_AREA),
        (SUFFIX_CLEANING_TIME, SUFFIX_TOTAL_CLEANING_TIME),
    ):
        assert longer.endswith(shorter), (
            f"{longer!r} no longer ends with {shorter!r} — if the naming changed, "
            f"the collision this guards may have moved rather than gone"
        )
        assert shorter in ALL_SUFFIXES
        assert longer in ALL_SUFFIXES, (
            f"{longer!r} missing from ALL_SUFFIXES — the exclusivity guard "
            f"cannot see the conflict and the per-run role will claim it"
        )


def test_vocabulary_is_derived_not_hand_listed():
    """A hand-kept list drifts the moment a suffix is added.

    ALL_SUFFIXES is built from the module's own SUFFIX_* constants, so this
    asserts the derivation still picks them all up rather than asserting a
    frozen count that would just need bumping.
    """
    from custom_components.eufy_vacuum.adapters.eufy import entities

    declared = {
        value
        for name, value in vars(entities).items()
        if name.startswith("SUFFIX_") and isinstance(value, str) and value
    }
    assert declared, "no SUFFIX_* constants found — has the module moved?"
    assert set(ALL_SUFFIXES) == declared, (
        "ALL_SUFFIXES has drifted from the SUFFIX_* constants it derives from"
    )


def test_adapter_call_site_passes_the_vocabulary():
    """The guard is only armed if the adapter actually hands the vocabulary over.

    A correct core rule with NO CALLER is precisely the reachability gap behind
    issue #49 — the rescue existed, shipped, and passed every test, while the
    field said otherwise. Audit the call site, not just the function.

    Source-level on purpose: the alternative is standing up a full adapter
    registration, which these suites already cover, and which would pass even
    if the kwarg were dropped as long as nothing asserted on it.
    """
    import inspect

    from custom_components.eufy_vacuum.adapters.eufy import adapter as eufy_adapter

    source = inspect.getsource(eufy_adapter.register_eufy_adapter_for_vacuum)

    assert "detect_capabilities(" in source, (
        "the adapter no longer calls detect_capabilities here — this test is "
        "anchored to the wrong function"
    )
    assert "reserved_suffixes=ALL_SUFFIXES" in source, (
        "the adapter stopped passing its suffix vocabulary; the core exclusivity "
        "guard is now unarmed on real hardware and a per-run role can resolve to "
        "a lifetime total again"
    )
