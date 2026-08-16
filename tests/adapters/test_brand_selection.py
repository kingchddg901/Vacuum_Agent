"""Tests for adapters/brands.py — which registrar runs for a given vacuum.

This module is the reason the tests below can exist at all. Brand selection used to be a
two-arm ``if/else`` in ``__init__.py`` with Eufy as the unconditional ``else``, so there
was no unsupported-brand code path to point a test at — several future-brand findings from
the adapter audit were unreachable for exactly that reason.

Coverage targets
----------------
[BR-1]  the table is well-formed: unique ids, every entry registerable, every entry
        declaring the platform(s) it claims.
[BR-2]  positive detection wins, in table order.
[BR-3]  no match is UNSUPPORTED and says so — support is a positive statement, and an
        unclaimed vacuum is left unconfigured rather than driven as a Eufy.
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
    get_registrar,
    register_brand_adapter,
    resolve_brand,
)


_VAC = "vacuum.alfred"
_RVAC = "vacuum.ivy"


@pytest.fixture
def table(monkeypatch, hass):
    """Swap in a synthetic two-brand table plus a never-matching third.

    Synthetic on purpose: these tests are about the RESOLUTION RULES, not about whether
    a particular firmware reports "Roborock". The real table's own well-formedness is
    asserted separately in [BR-1], and each brand's detector is tested in its own
    package.
    """
    calls: list[tuple[str, str]] = []

    def _reg(brand_id):
        # `entity_overrides` is part of the registrar contract: the tier extracts
        # the user's {role: entity_id} map and hands the brand the meaning, never
        # the storage key (ISO-1 confines brand packages to the adapter SDK).
        def _inner(hass, vacuum_entity_id, *, entity_overrides=None):
            calls.append((brand_id, vacuum_entity_id))
        return _inner

    synthetic = (
        BrandRegistrar(
            brand_id="alpha",
            register=_reg("alpha"),
            platforms=("alpha_integration",),
        ),
        BrandRegistrar(
            brand_id="beta",
            register=_reg("beta"),
            # Deliberately also claims alpha's platform, to prove TABLE ORDER decides.
            platforms=("beta_integration", "alpha_integration"),
        ),
        BrandRegistrar(
            brand_id="claims_nothing",
            register=_reg("claims_nothing"),
            platforms=(),
        ),
    )
    monkeypatch.setattr(brands, "BRAND_REGISTRARS", synthetic)

    # Identity is now DATA, so the fixture must put real entities in the registry
    # carrying those platforms. The old table matched on entity-id patterns, which
    # meant these tests never touched the registry at all — convenient, and exactly
    # the shape that let a detector claim a vacuum it had never actually identified.
    from homeassistant.helpers import entity_registry as er
    reg = er.async_get(hass)
    reg.async_get_or_create("vacuum", "alpha_integration", "u_alpha",
                            suggested_object_id="alpha_one")
    reg.async_get_or_create("vacuum", "beta_integration", "u_beta",
                            suggested_object_id="beta_two")
    # `vacuum.something_else` and `vacuum.mystery` are deliberately NOT registered —
    # they are the no-match cases.
    return calls


# --- the shipped table -------------------------------------------------------

def test_shipped_table_is_well_formed():
    """[BR-1] The invariants resolve_brand relies on, asserted on the REAL table.

    A duplicate id would make resolution order meaningless, and it is the kind of thing
    a brand-3 PR gets wrong.
    """
    ids = [r.brand_id for r in BRAND_REGISTRARS]
    assert len(ids) == len(set(ids)), f"duplicate brand_id in the table: {ids}"
    assert all(r.brand_id == r.brand_id.strip().lower() for r in BRAND_REGISTRARS), (
        "brand_id must be lowercase — get_registrar normalizes its input"
    )

    assert not any(hasattr(r, "is_default") for r in BRAND_REGISTRARS), (
        "a default arm is back. Support is a POSITIVE statement — an unclaimed vacuum "
        "must be reported unsupported, never silently driven as another brand."
    )

    assert all(callable(r.register) for r in BRAND_REGISTRARS)
    assert all(isinstance(r.platforms, tuple) for r in BRAND_REGISTRARS)
    assert not any(hasattr(r, "detect") for r in BRAND_REGISTRARS), (
        "a `detect` callable is back on the registrar. Identity is DATA — core "
        "asking each brand 'is this yours?' is `if brand:` with a function pointer, "
        "which is the arrangement the adapter seam exists to remove."
    )

    # Every shipped brand must claim at least one platform, or it is unreachable.


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
    """[BR-2] The first registrar CLAIMING the platform takes it, in table order.

    `beta` also declares `alpha_integration`, so this fails if the loop stops keying on
    order — a real risk once more than one brand can be served by one integration.
    """
    registrar, source = resolve_brand(hass, "vacuum.alpha_one")
    assert (registrar.brand_id, source) == ("alpha", "platform")

    registrar, source = resolve_brand(hass, "vacuum.beta_two")
    assert (registrar.brand_id, source) == ("beta", "platform")


def test_no_match_is_unsupported(table, hass):
    """[BR-3] An unclaimed vacuum gets NO registrar, and says so.

    This is the whole policy: `registrar is None` rather than a silent Eufy. The vacuum
    stays managed and simply has no adapter config, which every consumer of
    get_adapter_config already tolerates.
    """
    registrar, source = resolve_brand(hass, "vacuum.something_else")
    assert registrar is None
    assert source == "unsupported"


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
def test_an_unusable_override_degrades_to_the_platform_match(table, hass, data):
    """[BR-5] Brand resolution runs for every vacuum during setup.

    One hand-edited or stale stored value must not take the integration down, and must
    not silently change which brand a DIFFERENT vacuum gets.
    """
    registrar, source = resolve_brand(hass, "vacuum.alpha_one", data=data)
    assert (registrar.brand_id, source) == ("alpha", "platform")


def test_an_unknown_override_id_falls_through_loudly(table, hass, caplog):
    """[BR-5] An unknown id is ignored — but never silently: the user's stated intent
    is being overruled, which is exactly the class of thing this campaign kept finding
    happening without a log line."""
    data = {BRAND_OVERRIDES_KEY: {"vacuum.alpha_one": "dreame"}}
    registrar, source = resolve_brand(hass, "vacuum.alpha_one", data=data)
    assert (registrar.brand_id, source) == ("alpha", "platform")
    assert "dreame" in caplog.text


def test_an_unreadable_entity_registry_is_not_fatal(monkeypatch, hass):
    """[BR-6] The old version of this test guarded a throwing DETECTOR.

    That failure mode no longer exists — there is no per-brand callable to throw. The
    equivalent risk moved one layer down: resolution now reads the entity registry, and
    that read happens during setup for every managed vacuum. If it raises, the vacuum
    must resolve as unsupported rather than taking setup down with it.
    """
    def _boom(hass_):
        raise RuntimeError("entity registry unavailable")

    synthetic = (
        BrandRegistrar(brand_id="claims_all", register=lambda h, v: None,
                       platforms=("anything",)),
        BrandRegistrar(brand_id="claims_nothing", register=lambda h, v: None,
                       platforms=()),
    )
    monkeypatch.setattr(brands, "BRAND_REGISTRARS", synthetic)
    monkeypatch.setattr(brands.er, "async_get", _boom)

    registrar, source = resolve_brand(hass, _VAC)
    assert (registrar, source) == (None, "unsupported")


# REMOVED — test_missing_default_arm_is_a_wiring_error. A table without a default arm
# was a wiring error when a terminal arm was mandatory. It is now the normal shape: no
# entry is terminal, and an unclaimed vacuum resolves to (None, "unsupported").


# --- the call site -----------------------------------------------------------

def test_register_brand_adapter_runs_the_resolved_registrar(table, hass):
    """[BR-7] Resolution is only useful if it actually dispatches."""
    brand_id, source = register_brand_adapter(hass, "vacuum.beta_two")
    assert (brand_id, source) == ("beta", "platform")
    assert table == [("beta", "vacuum.beta_two")]


def test_register_brand_adapter_refuses_loudly(table, hass, caplog):
    """[BR-3 + BR-7] An unsupported vacuum gets NO adapter, and the refusal is loud.

    Loud matters more than usual here: this is a guard that activates over existing
    installs, so a user whose vacuum stops being driven must be able to find out why
    and how to overrule us. The message therefore has to carry BOTH the platform we did
    not recognise and the override key.
    """
    import logging
    caplog.set_level(logging.WARNING)

    brand_id, source = register_brand_adapter(hass, "vacuum.mystery")
    assert (brand_id, source) == (None, "unsupported")
    assert table == [], "no registrar may run for an unsupported vacuum"
    assert "not a supported vacuum" in caplog.text
    assert "brand_overrides" in caplog.text, (
        "the refusal must name the escape hatch, or a wrongly-refused user is stuck"
    )


# --- the real Roborock detector, through the real table ----------------------

def test_a_real_roborock_resolves_to_roborock(hass):
    """[BR-2] End-to-end against the SHIPPED table, so the wiring is proven.

    No device-registry monkeypatch, because the shipped table no longer reads it. This
    used to fake a device with manufacturer "Roborock" — a string the vendor controls
    and which was blank on plenty of real installs. `platform` is set by HA itself.
    """
    from homeassistant.helpers import entity_registry as er

    vid = er.async_get(hass).async_get_or_create(
        "vacuum", "roborock", "u_real_rb", suggested_object_id="ivy_real"
    ).entity_id
    registrar, source = resolve_brand(hass, vid)
    assert (registrar.brand_id, source) == ("roborock", "platform")


def test_a_real_eufy_resolves_to_eufy_positively(hass):
    """[BR-2] The one that could not be written before.

    A Eufy now resolves as "platform", not "default" — `robovac_mqtt` is a fact about
    which integration created the entity, not a guess about hardware. Verified against
    `vacuum.alfred` live and against all 65 entities in ptruman's issue #49 dump.
    """
    from homeassistant.helpers import entity_registry as er

    vid = er.async_get(hass).async_get_or_create(
        "vacuum", "robovac_mqtt", "u_real_eufy", suggested_object_id="alfred_real"
    ).entity_id
    registrar, source = resolve_brand(hass, vid)
    assert (registrar.brand_id, source) == ("eufy", "platform")


def test_an_unrecognised_device_is_refused_not_assumed(hass):
    """[BR-3] END-TO-END against the SHIPPED table — the policy, on real registrars.

    This test used to assert the opposite: an unrecognised device resolved to Eufy and
    reported "default". That was the leak. A Dreame (`dreame_vacuum`) is the live case —
    `vacuum.robin` bound 2 of ~10 Eufy roles by coincidence of naming and looked
    configured rather than wrong.
    """
    from homeassistant.helpers import entity_registry as er

    vid = er.async_get(hass).async_get_or_create(
        "vacuum", "dreame_vacuum", "u_dreame", suggested_object_id="robin_real"
    ).entity_id
    registrar, source = resolve_brand(hass, vid)
    assert registrar is None
    assert source == "unsupported"


# --- the platform arm: the adapter's own identity claim -----------------------
#
# [BR-8..BR-12] These exist because the platform arm is INVISIBLE to every test above
# it. Both other arms resolve the same two registrars, so an arm that never fired would
# leave the whole suite green — the dead-column shape. Each test below therefore asserts
# source == "platform", not just the brand_id.

def _register_vacuum(hass, platform: str, object_id: str) -> str:
    """Put a real vacuum entity in the registry, owned by `platform`."""
    from homeassistant.helpers import entity_registry as er

    entry = er.async_get(hass).async_get_or_create(
        "vacuum", platform, f"unique_{object_id}", suggested_object_id=object_id
    )
    return entry.entity_id


def test_eufy_finally_has_a_positive_test(hass):
    """[BR-8] `robovac_mqtt` identifies a Eufy — the test brands.py said couldn't exist.

    The module long held that Eufy had no honest positive test because the DEVICE
    registry's manufacturer/model are free text and often blank. The ENTITY registry's
    platform is neither. Alfred reports `robovac_mqtt` live, and so do all 65 of
    ptruman's entities in issue #49.

    source MUST be "platform", not "default": the whole point is that "this is a Eufy"
    and "we could not tell, so we assumed Eufy" stop being the same answer.
    """
    vid = _register_vacuum(hass, "robovac_mqtt", "alfred_platform")
    registrar, source = resolve_brand(hass, vid)
    assert (registrar.brand_id, source) == ("eufy", "platform")


def test_roborock_resolves_by_platform_without_touching_the_device_registry(hass):
    """[BR-9] No `_device_for_vacuum` monkeypatch here — that is the point.

    The detect arm needs a device-registry read; the platform arm does not. This test
    would fail if the platform arm were inert, because nothing else can identify a
    Roborock without that patch.
    """
    vid = _register_vacuum(hass, "roborock", "ivy_platform")
    registrar, source = resolve_brand(hass, vid)
    assert (registrar.brand_id, source) == ("roborock", "platform")


def test_an_unmatched_platform_is_unsupported(hass):
    """[BR-10] The leak, closed. This test previously asserted the opposite.

    It was written as a PIN on the wrong behaviour, so that removing the default arm
    would change exactly one test. It did.
    """
    vid = _register_vacuum(hass, "dreame_vacuum", "robin_platform")
    registrar, source = resolve_brand(hass, vid)
    assert (registrar, source) == (None, "unsupported")


def test_a_vacuum_absent_from_the_registry_falls_through(hass, monkeypatch):
    """[BR-11] No registry entry is a real answer, not a brand.

    A YAML/template vacuum, or a lookup during teardown, has no platform. That must fall
    through to the remaining arms rather than raising or being read as "no brand".
    """
    from custom_components.eufy_vacuum.adapters.roborock import adapter as rb

    class _Blank:
        manufacturer = None
        model = None

    monkeypatch.setattr(rb, "_device_for_vacuum", lambda h, v: _Blank())
    registrar, source = resolve_brand(hass, "vacuum.never_registered")
    assert (registrar, source) == (None, "unsupported")


def test_an_override_still_outranks_the_platform(hass):
    """[BR-12] Order matters: override → platform → detect → default.

    The escape hatch has to beat a positive platform match, or a user on a renamed fork
    could never correct us.
    """
    vid = _register_vacuum(hass, "robovac_mqtt", "alfred_override")
    registrar, source = resolve_brand(
        hass, vid, data={BRAND_OVERRIDES_KEY: {vid: "roborock"}}
    )
    assert (registrar.brand_id, source) == ("roborock", "override")


def test_every_shipped_registrar_declares_its_platforms(hass):
    """[BR-13] A registrar with an empty `platforms` tuple can never match.

    It would silently depend on the default arm — which is precisely what we are
    dismantling. Catch it at the table, not in the field.
    """
    for registrar in BRAND_REGISTRARS:
        assert registrar.platforms, (
            f"{registrar.brand_id} declares no platforms; it can only ever be reached "
            "by the default arm"
        )
        assert isinstance(registrar.platforms, tuple), registrar.brand_id
