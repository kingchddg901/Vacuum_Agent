"""The canonical/provider vocabulary boundary for water level.

Core legitimately owns an internal canonical key space — ``off / low / medium / high``
— which the water estimator keys its rate table on. What core may NOT do is assume a
provider's vocabulary equals that space. Those are different claims, and only the first
one is allowed.

Both shipped brands hide the difference. Roborock's declared values are already
``off/low/medium/high``, and Eufy's ``"Low"`` reaches ``"low"`` through a generic
case-folding rule that is itself legitimate. So neither brand exercises the alias path,
and it could break without a single test noticing — the same shape as the fixture that
registered no adapter and therefore agreed with the fallback it was standing on.

This module uses a brand whose water words resemble nothing canonical
(``SynthMist``, ``SynthFlood``) so the ONLY route to a canonical key is the declared
alias map. If aliasing regresses, these go red and the two real brands stay green.

Coverage targets
----------------
[WV-1] provider vocabulary resolves to canonical keys ONLY via declared aliases.
[WV-2] the mutation control: remove the aliases and the same values stop resolving.
[WV-3] case-folding to a canonical key is a generic rule, not a brand assumption.
[WV-4] an unknown value is passed through, not silently coerced to a canonical key.
[WV-5] the estimator's rate table is reached through the alias path end-to-end.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.planning.run_plan import RunPlanManager

from tests._factories import spec_manager

#: A brand whose water words share no letters with the canonical keys. Deliberately not
#: derived from SYNTHETIC_BLOCK's profile values: this is about the vocabulary → key
#: mapping, and reusing a value that happens to be canonical would weaken it.
SYNTH_WATER_ALIASES = {
    "synthdry": "off",
    "synthmist": "low",
    "synthwet": "medium",
    "synthflood": "high",
}


@pytest.fixture
def rp() -> RunPlanManager:
    """Both methods under test are pure — neither touches the manager back-reference.

    Specced anyway rather than a bare MagicMock: a bare mock agrees with whatever the
    caller does, so if one of these methods later grew a manager call, it would be
    answered by a fabricated attribute and this suite would keep passing while testing
    something that cannot happen in production.
    """
    return RunPlanManager(spec_manager())


@pytest.mark.parametrize("provider_value,canonical", sorted(SYNTH_WATER_ALIASES.items()))
def test_provider_vocabulary_resolves_only_through_declared_aliases(
    rp, provider_value, canonical
):
    """[WV-1] A brand's own word becomes a canonical key because it DECLARED the map."""
    assert rp._normalize_water_level_key(
        provider_value, aliases=SYNTH_WATER_ALIASES
    ) == canonical


@pytest.mark.parametrize("provider_value", sorted(SYNTH_WATER_ALIASES))
def test_without_the_aliases_the_same_values_do_not_resolve(rp, provider_value):
    """[WV-2] The mutation control — the thing that makes WV-1 mean something.

    Drop the declared map and every one of those values stops resolving. Without this,
    WV-1 would still pass if the normalizer had quietly learned the synthetic words some
    other way, and the test would be measuring nothing.
    """
    assert rp._normalize_water_level_key(provider_value, aliases=None) != (
        SYNTH_WATER_ALIASES[provider_value]
    )


@pytest.mark.parametrize("provider_value,canonical", [
    ("Low", "low"), ("MEDIUM", "medium"), ("  High  ", "high"), ("Off", "off"),
    ("medium-high", "medium high"),
])
def test_case_and_separator_folding_is_a_generic_rule(rp, provider_value, canonical):
    """[WV-3] Folding case/separators is core's own normalization, not a brand fact.

    This is why Eufy needs no alias for "Low" and Roborock needs none at all. That is
    legitimate — but it is also why neither brand proves the alias path, which is WV-1's
    entire job.
    """
    assert rp._normalize_water_level_key(provider_value, aliases=None) == canonical


def test_an_unknown_value_passes_through_rather_than_being_guessed(rp):
    """[WV-4] No nearest-match, no default — an unrecognised word stays itself.

    Coercing it to a canonical key would be the same class of guess as the framework
    catalog that shipped one brand's words to every brand: a plausible answer that is
    silently wrong, in place of an obviously unhandled one.
    """
    assert rp._normalize_water_level_key("SynthTsunami", aliases=SYNTH_WATER_ALIASES) == (
        "synthtsunami"
    )


def test_the_rate_table_is_reached_through_the_alias_path(rp):
    """[WV-5] End to end: provider word → declared alias → canonical key → declared rate.

    Every hop is a declaration. Core supplies the KEY SPACE and the ``off`` = 0 universal;
    the brand supplies the words and the measured rates.
    """
    rates = {"low": 1.0, "medium": 2.0, "high": 3.0}

    assert rp._water_rate_ml_per_minute(
        "SynthMist", aliases=SYNTH_WATER_ALIASES, rate_override=rates) == 1.0
    assert rp._water_rate_ml_per_minute(
        "SynthFlood", aliases=SYNTH_WATER_ALIASES, rate_override=rates) == 3.0
    # off = 0 is core's universal and survives a rate table that omits it (EST-H2O-2).
    assert rp._water_rate_ml_per_minute(
        "SynthDry", aliases=SYNTH_WATER_ALIASES, rate_override=rates) == 0.0

    # Same provider values, aliases withdrawn: they no longer reach a declared rate.
    assert rp._water_rate_ml_per_minute(
        "SynthMist", aliases=None, rate_override=rates) != 1.0
