"""The profile-catalog declaration contract, proven in all three of its states.

Core carries no room-profile catalog. An adapter declares one, or it cannot resolve a
room. That rule is only worth anything if all three states are pinned — a suite that
only ever exercises a WORKING adapter proves the happy path and nothing about the rule:

  1. **Declared and populated** — a real brand's own config resolves its own words.
  2. **Not declared at all** — a LOUD contract failure. No fallback, no substitution,
     and specifically not a quiet empty answer that looks like success.
  3. **Declared empty** — graceful, honest absence. The brand said "none"; it is taken
     at its word, and nothing is invented to fill the gap.

State 2 is the one that matters most and the one a normal suite never reaches. Before
2026-08-07 it was indistinguishable from state 1: an adapter that declared nothing
silently received Eufy's catalog, so the framework answered every question with one
brand's vocabulary and no test could tell. That shipped — three Roborock rooms stored a
Eufy fan speed their device does not accept, and dispatch dropped it silently.

State 3 must stay distinguishable from state 2, or "this brand has none" and "the porter
forgot" collapse back into one state and the fail-soft ambiguity returns one level along.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import (
    _validate_adapter,
    get_adapter_config,
    register_adapter_config,
    unregister_adapter_config,
)
from custom_components.eufy_vacuum.profiles.room_profiles import (
    UndeclaredProfileCatalogError,
    resolve_profile_catalog,
    resolve_room_profile_for_room,
)

from custom_components.eufy_vacuum.adapters.brands import BRAND_REGISTRARS
from tests.brand_catalogs import BRAND_BLOCKS, EUFY_BLOCK, ROBOROCK_BLOCK, SYNTHETIC_BLOCK

_VAC = "vacuum.contract_probe"


@pytest.fixture(autouse=True)
def _clean_registry():
    """Nothing registered before or after — this module is about registration itself."""
    unregister_adapter_config(_VAC)
    yield
    unregister_adapter_config(_VAC)


# ---------------------------------------------------------------------------
# State 1 — declared and populated
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("brand_name", sorted(BRAND_BLOCKS))
def test_a_declared_catalog_resolves_that_brands_own_words(brand_name):
    """[DC-1] Every shipped brand's real declaration resolves to ITS values.

    Sourced from each adapter's own constants, so this cannot pass by agreeing with a
    copy that has drifted from what the adapter actually declares.
    """
    block = BRAND_BLOCKS[brand_name]
    catalog = resolve_profile_catalog(block)
    declared = block["builtins"]["vacuum_quick"]

    resolved = resolve_room_profile_for_room(
        room_config={"profile_name": "vacuum_quick", "floor_type": "hardwood"},
        catalog=catalog,
    )
    assert resolved["resolved_profile_name"] == "vacuum_quick"
    assert resolved["fan_speed"] == declared["fan_speed"]
    assert resolved["clean_mode"] == declared["clean_mode"]


def test_the_two_shipped_brands_do_not_share_vocabulary():
    """[DC-1b] Eufy and Roborock must actually DIFFER, or DC-1 proves nothing.

    If both brands spelled every value the same way, every relational test in this repo
    would pass against a hardcoded literal and the parameterization would be decorative.
    This asserts the premise those tests rest on.
    """
    eufy = EUFY_BLOCK["builtins"]["vacuum_quick"]
    rb = ROBOROCK_BLOCK["builtins"]["vacuum_quick"]
    assert eufy["fan_speed"] != rb["fan_speed"], (
        "The two brands now declare the same fan speed. Either a brand's vocabulary was "
        "overwritten with the other's — the exact leak this suite exists to catch — or "
        "the fixtures have stopped reading the real adapters."
    )


# ---------------------------------------------------------------------------
# State 2 — not declared at all. The loud failure.
# ---------------------------------------------------------------------------

def test_an_undeclared_catalog_fails_loudly_not_silently():
    """[DC-2] Resolving with no declaration RAISES, naming the missing declaration.

    The failure must be loud AND specific. A bare KeyError would be loud but would read
    as "that profile is missing" rather than "this adapter declared nothing", sending
    the next reader after the wrong thing entirely.
    """
    with pytest.raises(UndeclaredProfileCatalogError) as excinfo:
        resolve_room_profile_for_room(
            room_config={"profile_name": "vacuum_quick", "floor_type": "hardwood"},
            catalog=resolve_profile_catalog(None),
        )

    message = str(excinfo.value)
    assert "room_profiles.builtins" in message, message
    assert "core holds no catalog" in message, message


def test_an_undeclared_catalog_never_yields_another_brands_words():
    """[DC-2b] The negative control. Nothing is substituted — not even quietly.

    The regression is specific: this used to return Eufy's catalog. So it is not enough
    that resolution fails; the resolved catalog itself must be EMPTY, or a future
    fallback could be reintroduced anywhere upstream of the raise and DC-2 would still
    pass.
    """
    catalog = resolve_profile_catalog(None)
    assert catalog["builtins"] == {}
    assert catalog["custom_template"] == {}
    assert catalog["floor_type_water_defaults"] == {}

    eufy_words = {
        str(v) for profile in EUFY_BLOCK["builtins"].values() for v in profile.values()
    }
    leaked = {
        str(v)
        for profile in (catalog["builtins"] or {}).values()
        for v in profile.values()
    } & eufy_words
    assert not leaked, f"an undeclared catalog produced Eufy vocabulary: {sorted(leaked)}"


def test_registration_rejects_an_adapter_that_declares_no_catalog():
    """[DC-2c] The gate sits at REGISTRATION, so the failure lands on the porter.

    Raising at first-clean would be loud too, but hours later and far from the cause.
    """
    issues = _validate_adapter({"adapter_id": "forgot", "source": "code"})
    assert any(i.startswith("room_profiles:") for i in issues), issues


# ---------------------------------------------------------------------------
# State 3 — declared empty. Graceful absence.
# ---------------------------------------------------------------------------

def test_a_declared_empty_key_is_honoured_not_treated_as_absent():
    """[DC-3] ``legacy_aliases: {}`` means "this brand has none", and is carried.

    Roborock declares exactly this. The old ``block.get(key) or default`` treated any
    falsy declared value as absent and substituted Eufy's aliases, so the brand's
    explicit "we have none" was literally unrepresentable.
    """
    block = {**SYNTHETIC_BLOCK, "legacy_aliases": {}}
    catalog = resolve_profile_catalog(block)
    assert catalog["legacy_aliases"] == {}

    # ...and a room still resolves, because the keys the brand DID declare are intact.
    resolved = resolve_room_profile_for_room(
        room_config={"profile_name": "vacuum_quick", "floor_type": "hardwood"},
        catalog=catalog,
    )
    assert resolved["fan_speed"] == SYNTHETIC_BLOCK["builtins"]["vacuum_quick"]["fan_speed"]


def test_a_partially_declared_adapter_registers_and_resolves_empty():
    """[DC-3b] Declaring SOME keys is a complete-enough declaration; the rest are empty.

    The gate is the block, not each key. A porter who declared ``builtins`` and stopped
    has engaged with the contract, and their undeclared keys resolve empty — a defined
    answer. Only declaring NOTHING means "not written yet".
    """
    block = {"builtins": SYNTHETIC_BLOCK["builtins"], "default_profile": "vacuum_quick"}
    assert not [i for i in _validate_adapter(
        {"adapter_id": "partial", "source": "code", "room_profiles": block}
    ) if i.startswith("room_profiles:")]

    catalog = resolve_profile_catalog(block)
    assert catalog["legacy_aliases"] == {}
    assert catalog["floor_type_water_defaults"] == {}
    # Carpet has no declared no-water word, so nothing is invented for it.
    resolved = resolve_room_profile_for_room(
        room_config={"profile_name": "vacuum_quick", "floor_type": "carpet_low_pile"},
        catalog=catalog,
    )
    assert resolved["water_level"] == ""


def test_registration_rejects_a_wholly_empty_block():
    """[DC-3c] ``room_profiles: {}`` is not a declaration of emptiness — it is nothing.

    A brand with zero profile vocabulary cannot resolve a single room, so it is never a
    working state. Emptiness is stated per key, which keeps the keys the brand DOES
    supply visible as deliberate.
    """
    issues = _validate_adapter(
        {"adapter_id": "hollow", "source": "code", "room_profiles": {}}
    )
    assert any(i.startswith("room_profiles:") for i in issues), issues


# ---------------------------------------------------------------------------
# The instrument, exercised — a gate only ever seen passing has not been tested.
# ---------------------------------------------------------------------------

def test_the_registration_gate_accepts_every_shipped_brand():
    """[DC-4] All three states above are worthless if the gate rejects real adapters.

    Runs each shipped brand's real declaration through the same validator that rejects
    the undeclared ones, so "rejects the bad" and "accepts the good" are both proven by
    the same instrument.
    """
    for name, block in BRAND_BLOCKS.items():
        issues = [
            i for i in _validate_adapter(
                {"adapter_id": name, "source": "code", "room_profiles": block}
            ) if i.startswith("room_profiles:")
        ]
        assert not issues, f"{name}: {issues}"


def test_a_registered_adapter_is_what_resolution_actually_reads():
    """[DC-5] End to end: what the registry holds is what a room resolves against.

    The three states above all test the resolver directly with a catalog in hand. This
    closes the last gap — that the REGISTERED config is the one reaching resolution —
    which is precisely where the original defect lived: four call sites resolved rooms
    without ever consulting the registry, and the framework's fallback covered for them.
    """
    register_adapter_config(_VAC, {
        "adapter_id": "synthetic", "source": "code", "room_profiles": SYNTHETIC_BLOCK,
    })
    catalog = resolve_profile_catalog(
        (get_adapter_config(_VAC) or {}).get("room_profiles")
    )
    resolved = resolve_room_profile_for_room(
        room_config={"profile_name": "vacuum_deep", "floor_type": "hardwood"},
        catalog=catalog,
    )
    assert resolved["fan_speed"] == SYNTHETIC_BLOCK["builtins"]["vacuum_deep"]["fan_speed"]


# ---------------------------------------------------------------------------
# [DC-20] / [DC-21] RN7WK2CX -- the two test-side brand registries must cover the
# shipped one.
#
# Neither of these can FAIL when a brand is missing; they go SILENT. BRAND_BLOCKS
# feeds the `brand` fixture, so a brand without a row simply never appears in any
# parameterization, and ADAPTER_BUILDERS feeds the contract suite, which the
# adapters conftest advertises as needing "no new test code required" per brand.
# Both read green over a shrinking fraction of the brands they claim to cover.
#
# MEASURED, not hypothetical: dreame shipped in BRAND_REGISTRARS on 2026-09-13 and
# BRAND_BLOCKS never got its row. For eight weeks the whole vocabulary suite ran
# over two of three brands while its docstrings said every shipped one, and the
# brand-leak gate's corpus -- built from the same two blocks -- was structurally
# unable to report a Dreame word however plainly core bound it.
#
# The shipped registry is the primary and these are the replicas, so these two
# tests are the fences the anchor cannot be. Synthetic is excluded on purpose: it
# is an invented catalog belonging to no brand, which is the whole reason it exists.
# ---------------------------------------------------------------------------


def _shipped_brand_ids() -> set[str]:
    """Every brand id the integration actually registers an adapter for."""
    return {r.brand_id for r in BRAND_REGISTRARS}


def test_dc20_every_shipped_brand_has_a_catalog_block():
    """[DC-20] BRAND_BLOCKS covers the shipped registry, and claims nothing extra.

    Equality on the real-brand set, in both directions. A row here for a brand the
    integration does not register would parameterize every vocabulary test over a
    catalog no user can have, which is the same defect pointing the other way.
    """
    real = set(BRAND_BLOCKS) - {"synthetic"}
    shipped = _shipped_brand_ids()

    assert real == shipped, (
        "tests/brand_catalogs.py::BRAND_BLOCKS has drifted from "
        "adapters/brands.py::BRAND_REGISTRARS -- RN7WK2CX.\n"
        f"  missing a catalog block: {sorted(shipped - real) or 'none'}\n"
        f"  block for an unregistered brand: {sorted(real - shipped) or 'none'}\n"
        "A missing row does not fail anything; it removes that brand from the "
        "`brand` fixture and from the leak gate's corpus, silently."
    )


def test_dc21_every_shipped_brand_has_an_adapter_builder():
    """[DC-21] ADAPTER_BUILDERS covers the shipped registry.

    The builder bodies are necessarily test-side -- each assembles one brand's config
    directly, without going through brand resolution, which `test_brand_selection`
    owns separately. The KEY SET is the part that restates the shipped registry, and
    it is the part that can rot.
    """
    from tests.adapters.conftest import ADAPTER_BUILDERS

    shipped = _shipped_brand_ids()
    assert set(ADAPTER_BUILDERS) == shipped, (
        "tests/adapters/conftest.py::ADAPTER_BUILDERS has drifted from "
        "adapters/brands.py::BRAND_REGISTRARS -- RN7WK2CX.\n"
        f"  no builder: {sorted(shipped - set(ADAPTER_BUILDERS)) or 'none'}\n"
        f"  builder for an unregistered brand: "
        f"{sorted(set(ADAPTER_BUILDERS) - shipped) or 'none'}\n"
        "A brand with no builder never runs the brand-agnostic contract suite, which "
        "is exactly what that suite exists to guarantee it does."
    )


def test_dc20_the_premise_is_not_an_empty_set():
    """[DC-20] The shipped registry is non-empty, or both fences above are vacuous.

    `set() == set()` passes. If `BRAND_REGISTRARS` were ever emptied -- or if this
    import resolved to something that is not the registry -- the two equality
    assertions would become identities and report coverage of nothing. The floor is
    the three brands shipped today, asserted as a minimum rather than a count so
    adding a fourth does not fail here.
    """
    shipped = _shipped_brand_ids()
    assert len(shipped) >= 3, f"suspiciously few shipped brands: {sorted(shipped)}"
    assert {"eufy", "roborock", "dreame"} <= shipped, sorted(shipped)
