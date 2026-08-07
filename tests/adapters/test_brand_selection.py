"""Tests for adapters/brands.py — which registrar runs for a given vacuum.

This module is the reason the tests below can exist at all. Brand selection used to be a
two-arm ``if/else`` in ``__init__.py`` with Eufy as the unconditional ``else``, so there
was no unsupported-brand code path to point a test at — several future-brand findings from
the adapter audit were unreachable for exactly that reason.

Coverage targets
----------------
[BR-1]  the table is well-formed: unique ids, exactly one default arm, every entry
        registerable.
[BR-2]  positive detection wins, in table order.
[BR-3]  no match reaches the DECLARED default arm and reports source="default" — the
        distinction between "this is a Eufy" and "we could not tell, so we assumed Eufy".
[BR-4]  an explicit per-vacuum override outranks detection (the UI-selector seam).
[BR-5]  a malformed / unknown / absent override degrades to detection, never raises.
[BR-6]  a detector that throws is skipped rather than taking setup down.
[BR-7]  register_brand_adapter actually calls the resolved brand's registrar.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters import brands
from custom_components.eufy_vacuum.adapters.brands import (
    BRAND_OVERRIDES_KEY,
    BRAND_REGISTRARS,
    BrandRegistrar,
    get_default_registrar,
    get_registrar,
    register_brand_adapter,
    resolve_brand,
)


_VAC = "vacuum.alfred"
_RVAC = "vacuum.ivy"


@pytest.fixture
def table(monkeypatch):
    """Swap in a synthetic two-brand table plus a never-matching third.

    Synthetic on purpose: these tests are about the RESOLUTION RULES, not about whether
    a particular firmware reports "Roborock". The real table's own well-formedness is
    asserted separately in [BR-1], and each brand's detector is tested in its own
    package.
    """
    calls: list[tuple[str, str]] = []

    def _reg(brand_id):
        def _inner(hass, vacuum_entity_id):
            calls.append((brand_id, vacuum_entity_id))
        return _inner

    synthetic = (
        BrandRegistrar(
            brand_id="alpha",
            register=_reg("alpha"),
            detect=lambda hass, vid: vid == "vacuum.alpha_one",
        ),
        BrandRegistrar(
            brand_id="beta",
            register=_reg("beta"),
            detect=lambda hass, vid: vid.startswith("vacuum.b"),
        ),
        BrandRegistrar(
            brand_id="fallback",
            register=_reg("fallback"),
            detect=None,
            is_default=True,
        ),
    )
    monkeypatch.setattr(brands, "BRAND_REGISTRARS", synthetic)
    return calls


# --- the shipped table -------------------------------------------------------

def test_shipped_table_is_well_formed():
    """[BR-1] The invariants resolve_brand relies on, asserted on the REAL table.

    A second default arm or a duplicate id would make resolution order meaningless, and
    both are the kind of thing a brand-3 PR gets wrong.
    """
    ids = [r.brand_id for r in BRAND_REGISTRARS]
    assert len(ids) == len(set(ids)), f"duplicate brand_id in the table: {ids}"
    assert all(r.brand_id == r.brand_id.strip().lower() for r in BRAND_REGISTRARS), (
        "brand_id must be lowercase — get_registrar normalizes its input"
    )

    defaults = [r for r in BRAND_REGISTRARS if r.is_default]
    assert len(defaults) == 1, f"expected exactly one default arm, got {len(defaults)}"
    assert get_default_registrar() is defaults[0]

    assert all(callable(r.register) for r in BRAND_REGISTRARS)
    assert all(r.detect is None or callable(r.detect) for r in BRAND_REGISTRARS)

    # The default arm must be reachable by no-match, which means it cannot be shadowed by
    # its own detector claiming everything. Eufy declares no detector at all — deliberately
    # (module docstring: there is no honest positive test to write for it). A brand-3 PR
    # that marks an entry is_default=True AND gives it a detector destroys the very
    # distinction this module exists for: every vacuum would resolve as "detected" and
    # source would stop carrying information.
    assert defaults[0].detect is None, (
        f"the default arm ({defaults[0].brand_id!r}) declares a detector; the terminal arm "
        "must have detect=None or it shadows the no-match route it exists to serve"
    )


def test_shipped_table_still_covers_both_brands():
    """[BR-1] The two shipped brands are present and resolvable by id."""
    assert get_registrar("roborock") is not None
    assert get_registrar("eufy") is not None
    assert get_registrar("EUFY") is not None, "lookup must normalize case"
    assert get_registrar("nope") is None
    assert get_registrar("") is None
    assert get_registrar(None) is None


# --- resolution rules --------------------------------------------------------

def test_detection_wins_in_table_order(table, hass):
    """[BR-2] The first positive detect takes it, later entries never run."""
    registrar, source = resolve_brand(hass, "vacuum.alpha_one")
    assert (registrar.brand_id, source) == ("alpha", "detected")

    registrar, source = resolve_brand(hass, "vacuum.beta_two")
    assert (registrar.brand_id, source) == ("beta", "detected")


def test_no_match_reaches_the_declared_default(table, hass):
    """[BR-3] The case that did not exist before this module.

    source="default" is the load-bearing part: it distinguishes a positively identified
    brand from an assumption, which is what lets __init__ log the one line that tells a
    user with an unrecognised vacuum why it is being driven as a Eufy.
    """
    registrar, source = resolve_brand(hass, "vacuum.something_else")
    assert (registrar.brand_id, source) == ("fallback", "default")


def test_an_explicit_override_outranks_detection(table, hass):
    """[BR-4] The UI-selector seam. A user's stated choice beats auto-detection."""
    data = {BRAND_OVERRIDES_KEY: {"vacuum.alpha_one": "beta"}}
    registrar, source = resolve_brand(hass, "vacuum.alpha_one", data=data)
    assert (registrar.brand_id, source) == ("beta", "override")

    # ...including forcing a brand onto a vacuum nothing would have detected.
    data = {BRAND_OVERRIDES_KEY: {"vacuum.mystery": "ALPHA"}}   # case-normalized
    registrar, source = resolve_brand(hass, "vacuum.mystery", data=data)
    assert (registrar.brand_id, source) == ("alpha", "override")


@pytest.mark.parametrize("data", [
    None,
    {},
    {BRAND_OVERRIDES_KEY: None},
    {BRAND_OVERRIDES_KEY: "not-a-dict"},
    {BRAND_OVERRIDES_KEY: {}},
    {BRAND_OVERRIDES_KEY: {"vacuum.alpha_one": ""}},
    {BRAND_OVERRIDES_KEY: {"vacuum.alpha_one": "   "}},
    {BRAND_OVERRIDES_KEY: {"vacuum.alpha_one": 7}},
    {BRAND_OVERRIDES_KEY: {"other.vacuum": "beta"}},
])
def test_an_unusable_override_degrades_to_detection(table, hass, data):
    """[BR-5] Brand resolution runs for every vacuum during setup.

    One hand-edited or stale stored value must not take the integration down, and must
    not silently change which brand a DIFFERENT vacuum gets.
    """
    registrar, source = resolve_brand(hass, "vacuum.alpha_one", data=data)
    assert (registrar.brand_id, source) == ("alpha", "detected")


def test_an_unknown_override_id_falls_through_loudly(table, hass, caplog):
    """[BR-5] An unknown id is ignored — but never silently: the user's stated intent
    is being overruled, which is exactly the class of thing this campaign kept finding
    happening without a log line."""
    data = {BRAND_OVERRIDES_KEY: {"vacuum.alpha_one": "dreame"}}
    registrar, source = resolve_brand(hass, "vacuum.alpha_one", data=data)
    assert (registrar.brand_id, source) == ("alpha", "detected")
    assert "dreame" in caplog.text


def test_a_throwing_detector_is_skipped_not_fatal(monkeypatch, hass):
    """[BR-6] detect reads the device registry, which can be absent or unhappy.

    A raising detector must not abort resolution for that vacuum, let alone for the
    whole setup loop — the next brand gets its turn and the default arm still catches.
    """
    def _boom(hass_, vid):
        raise RuntimeError("device registry unavailable")

    synthetic = (
        BrandRegistrar(brand_id="explodes", register=lambda h, v: None, detect=_boom),
        BrandRegistrar(brand_id="fallback", register=lambda h, v: None,
                       detect=None, is_default=True),
    )
    monkeypatch.setattr(brands, "BRAND_REGISTRARS", synthetic)

    registrar, source = resolve_brand(hass, _VAC)
    assert (registrar.brand_id, source) == ("fallback", "default")


def test_missing_default_arm_is_a_wiring_error(monkeypatch, hass):
    """[BR-1] A table with no default arm is a programming mistake, and should say so
    rather than returning None for something every caller must handle."""
    monkeypatch.setattr(brands, "BRAND_REGISTRARS", (
        BrandRegistrar(brand_id="only", register=lambda h, v: None,
                       detect=lambda h, v: False),
    ))
    with pytest.raises(RuntimeError, match="no default arm"):
        resolve_brand(hass, _VAC)


# --- the call site -----------------------------------------------------------

def test_register_brand_adapter_runs_the_resolved_registrar(table, hass):
    """[BR-7] Resolution is only useful if it actually dispatches."""
    brand_id, source = register_brand_adapter(hass, "vacuum.beta_two")
    assert (brand_id, source) == ("beta", "detected")
    assert table == [("beta", "vacuum.beta_two")]


def test_register_brand_adapter_falls_back_and_says_so(table, hass, caplog):
    """[BR-3 + BR-7] The unidentified vacuum still gets an adapter — and now the log
    says the brand was assumed rather than identified. That line is the entire
    user-facing difference of this change."""
    import logging
    caplog.set_level(logging.INFO)

    brand_id, source = register_brand_adapter(hass, "vacuum.mystery")
    assert (brand_id, source) == ("fallback", "default")
    assert table == [("fallback", "vacuum.mystery")]
    assert "not identified as any supported brand" in caplog.text


# --- the real Roborock detector, through the real table ----------------------

def test_a_real_roborock_resolves_to_roborock(monkeypatch, hass):
    """[BR-2] End-to-end against the SHIPPED table, so the wiring is proven and not
    only the rules."""
    from custom_components.eufy_vacuum.adapters.roborock import adapter as rb

    class _FakeDevice:
        manufacturer = "Roborock"
        model = "roborock.vacuum.s6"

    monkeypatch.setattr(rb, "_device_for_vacuum", lambda h, v: _FakeDevice())
    registrar, source = resolve_brand(hass, _RVAC)
    assert (registrar.brand_id, source) == ("roborock", "detected")


def test_an_unrecognised_device_resolves_to_the_eufy_default(monkeypatch, hass):
    """[BR-3] The behaviour the old `else` arm had, now declared and reported.

    A Eufy with a blank manufacturer in the device registry is a real install shape, and
    it must keep working exactly as before — the ONLY change is that the resolution now
    reports "default" rather than being indistinguishable from a positive match.
    """
    from custom_components.eufy_vacuum.adapters.roborock import adapter as rb

    class _BlankDevice:
        manufacturer = None
        model = None

    monkeypatch.setattr(rb, "_device_for_vacuum", lambda h, v: _BlankDevice())
    registrar, source = resolve_brand(hass, _VAC)
    assert (registrar.brand_id, source) == ("eufy", "default")
