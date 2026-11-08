"""Dreame MODEL CATALOG — `profile_for_model`'s three resolution paths.

THE LOWEST-COVERED FILE IN THE PACKAGE AT 76.19%, and the shape of the gap was worse
than the number: the only path any test exercised was (3), the conservative fallback
for a model the catalog has never heard of. Both paths that decide real behaviour —
the hardware-verified override, and the regime-derived profile covering all 700
catalogued models — had never been executed. The Roborock catalog's twin function is
tested for its override path; this is the forgotten sibling.

Resolution order in `profile_for_model`:
  (1) `MODEL_PROFILES[model]` — a hardware-verified override. One entry today:
      `dreame.vacuum.r2469a`, the L10s Ultra Gen 2 (the maintainer's `vacuum.robin`).
  (2) `DREAME_MODEL_REGIMES[model]` — derive `family` + station flags from the model's
      measured (mop_type, dock_tier, tanks) regime, so a catalogued model gets REAL
      station flags instead of a flat `generic` with everything on.
  (3) `DEFAULT_PROFILE` — truly uncatalogued.
`display_name` is single-sourced from `DREAME_MODEL_NAMES` in every case.

[DMC-1] the hardware-verified override wins, and returns the AUTHORED capability set
        (not the default's) — path (1), which Robin's own model had never taken.
[DMC-2] `display_name` is injected from `DREAME_MODEL_NAMES`, never stored per-profile.
[DMC-3] a catalogued model's `family` is its measured regime composite, not "generic".
[DMC-4] `charge_only` FAILS CLOSED — and a wash tier does not, which is what makes the
        claim about `_TIER_STATION` able to fail at all.
[DMC-5] `auto_empty` reduces the station to collect-only.
[DMC-6] an uncatalogued model, and `None`, get the conservative baseline — path (3).
[DMC-7] `has_path_control` fails CLOSED for every one of the 700 catalogued models.
[DMC-8] every authored override has a real display name — the two-table drift the
        module docstring warns about, which would silently rename Robin's own device.

NO VALUE HERE IS COMPUTED THE WAY THE SOURCE COMPUTES IT. The family composites are
hand-written literals; deriving them with the same `"%s|%s|%s"` expression would make
the test agree with the code by construction and survive the separator changing.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.dreame.model_catalog import (
    DEFAULT_PROFILE,
    MODEL_PROFILES,
    _TIER_STATION,
    profile_for_model,
)
from custom_components.eufy_vacuum.adapters.dreame.upkeep_catalog import (
    DREAME_MODEL_NAMES,
)
from custom_components.eufy_vacuum.adapters.dreame.upkeep_regimes import (
    DREAME_MODEL_REGIMES,
)

#: The one authored override — the maintainer's own L10s Ultra Gen 2 (`vacuum.robin`).
_AUTHORED = "dreame.vacuum.r2469a"

#: One REAL model per dock tier, with its regime written out by hand. Picked from the
#: live table rather than invented, so a model that is re-regimed breaks the row that
#: names it instead of silently testing nothing.
_PER_TIER = [
    pytest.param("dreame.vacuum.p2008", "cloth|charge_only|no", id="charge_only"),
    pytest.param("dreame.vacuum.p2028", "cloth|auto_empty|no", id="auto_empty"),
    pytest.param("dreame.vacuum.p2027", "pad|wash_only|yes", id="wash_only"),
    pytest.param("dreame.vacuum.p2114a", "pad|wash+empty|yes", id="wash_empty"),
    pytest.param("dreame.vacuum.r2513", "pad|wash+empty+swap|yes", id="wash_empty_swap"),
]


def test_dmc1_the_authored_override_wins_over_the_regime():
    """[DMC-1] Path (1), never executed before: the hardware-verified override.

    `dreame.vacuum.r2469a` is ALSO in the regime table (the module asserts that at
    import, so the two sources cannot drift), which means this model would resolve
    perfectly happily down path (2). The override has to win, or the authored,
    live-verified capability set is silently replaced by one derived from three
    measured fields.

    THE ASSERTED FIELDS ARE THE ONES THAT DIFFER FROM THE DEFAULT, on purpose.
    `has_path_control` and `supports_zone_clean` are True here and False in
    `DEFAULT_PROFILE` — and a regime-derived profile inherits the default for both,
    since `_TIER_STATION` carries neither key. So these two are what distinguish
    "took path (1)" from "took path (2) or (3)"; asserting `has_mop` would pass on
    all three.

    RED: reorder so the regime is consulted first, or drop the `key in MODEL_PROFILES`
    branch, and `has_path_control` comes back False.
    """
    profile = profile_for_model(_AUTHORED)

    assert profile["family"] == "l10s_gen2", (
        "the authored family label was replaced by a regime composite"
    )
    assert profile["has_path_control"] is True, (
        "per-room cleaning_route was lost — the default and every regime-derived "
        "profile fail this CLOSED, so False here means the override did not win"
    )
    assert profile["supports_zone_clean"] is True, (
        "zone clean was lost; the generic default is False (fail-closed)"
    )
    # The authored device's full station, verified on vacuum.robin 2026-08-29.
    assert profile["station_washable"] is True
    assert profile["station_dryable"] is True

    # The returned dict must be a COPY: callers that mutate a profile must not edit
    # the catalog for every later caller.
    profile["family"] = "mutated"
    assert MODEL_PROFILES[_AUTHORED]["family"] == "l10s_gen2", (
        "profile_for_model handed out a reference to the module-level table"
    )


def test_dmc2_display_name_is_injected_not_stored():
    """[DMC-2] The module's own single-source rule, pinned.

    The docstring is explicit: `display_name` is NOT stored per-profile — it is read
    from `DREAME_MODEL_NAMES`, "the same table that routes guide families", because
    "a maintenance-catalog model table and a capability model table WILL diverge
    unless one derives from the other".

    Both halves are asserted. That the name comes back right is the behaviour; that it
    is ABSENT from the stored profile is the rule, and only the second one goes red if
    somebody adds a per-profile name that happens to match today.

    RED: store `"display_name"` in `MODEL_PROFILES[_AUTHORED]` and the second
    assertion fails; change the lookup table and the first does.
    """
    assert profile_for_model(_AUTHORED)["display_name"] == "L10s Ultra Gen 2"
    assert DREAME_MODEL_NAMES[_AUTHORED] == "L10s Ultra Gen 2", (
        "the name's single source moved; this test now proves nothing about injection"
    )
    for model, stored in MODEL_PROFILES.items():
        assert "display_name" not in stored, (
            f"{model} stores a display_name — that is the two-table divergence the "
            f"module docstring exists to prevent"
        )


@pytest.mark.parametrize("model,expected_family", _PER_TIER)
def test_dmc3_a_catalogued_model_gets_its_regime_composite(model, expected_family):
    """[DMC-3] Path (2), never executed before — and it covers all 700 models.

    Without it every catalogued model fell to a flat `generic` profile with all
    station flags on. The `family` label is how that is visible: core stores and
    reports it, and for a regime-derived profile it is the regime id, which "reads
    back to the three measured fields that produced it".

    The expected composites are HAND-WRITTEN. Building them with the source's own
    `"%s|%s|%s"` would make this test agree by construction — the separator could
    change to anything and both sides would move together.

    RED: drop the `if regime:` branch and every row comes back `generic`.
    """
    profile = profile_for_model(model)

    assert profile["family"] == expected_family, (
        f"{model} did not resolve through its regime"
    )
    assert profile["family"] != "generic"
    assert profile["display_name"] == DREAME_MODEL_NAMES[model]


def test_dmc4_charge_only_fails_closed_and_a_wash_tier_does_not():
    """[DMC-4] The tier that must REDUCE the station, with the contrast that makes the
    claim falsifiable.

    `_TIER_STATION` carries only `charge_only` and `auto_empty`; every wash tier falls
    through to `DEFAULT_PROFILE`'s full-station flags via `.get(dock_tier, {})`. The
    source's reasoning: over-claiming a station only turns on a card control that
    fails safe at dock/manager, while `charge_only` must fail CLOSED.

    ⚠ THE WASH-TIER HALF IS NOT DECORATION. `_TIER_STATION.get(dock_tier, {})` means
    an EMPTY `_TIER_STATION` yields the default for every tier — so "a wash tier has a
    station" passes against a table that was emptied. Only the contrast between the
    two shows the table is consulted at all. 551 of the 700 models are on a tier the
    table does not name, which is exactly why this is easy to get wrong.

    RED: empty `_TIER_STATION`, or drop the `**_TIER_STATION.get(...)` spread, and the
    charge_only assertions fail while the wash row keeps passing.
    """
    assert set(_TIER_STATION) == {"charge_only", "auto_empty"}, (
        "the tier table grew or shrank; the fall-through claim below needs re-checking"
    )

    closed = profile_for_model("dreame.vacuum.p2008")       # F9, charge_only
    assert closed["has_station"] is False, "a dock-less model was given a station"
    assert closed["station_collectable"] is False
    assert closed["station_washable"] is False
    assert closed["station_dryable"] is False

    # THE DISCRIMINATOR: a tier the table does not name keeps the full station.
    full = profile_for_model("dreame.vacuum.p2114a")        # X10+, wash+empty
    assert full["has_station"] is True
    assert full["station_washable"] is True
    assert full["station_dryable"] is True


def test_dmc5_auto_empty_reduces_the_station_to_collect_only():
    """[DMC-5] The other reducing tier: a dock that empties but does not wash.

    Claiming `station_washable` here would render a mop-wash control for a dock with
    no wash function. It fails safe at dispatch (`missing_action_entity`), but a
    control that exists and cannot work is still the wrong answer.

    RED: remove the `auto_empty` row from `_TIER_STATION` and washable/dryable come
    back True from the default.
    """
    profile = profile_for_model("dreame.vacuum.p2028")      # Z10 Pro, auto_empty

    assert profile["has_station"] is True
    assert profile["station_collectable"] is True
    assert profile["station_washable"] is False, "an auto-empty-only dock was given wash"
    assert profile["station_dryable"] is False


@pytest.mark.parametrize("model", [
    pytest.param("dreame.vacuum.not_a_real_model", id="unknown"),
    pytest.param("", id="empty"),
    pytest.param(None, id="none"),
])
def test_dmc6_an_uncatalogued_model_gets_the_conservative_baseline(model):
    """[DMC-6] Path (3), the only one that was already covered — kept as the control.

    Without it the other tests cannot distinguish "resolved correctly" from
    "everything returns the default". `None` and `""` collapse to the same key by
    `model or ""`, and both must be safe rather than raising: this is called from
    `adapter.py` with whatever the device registry holds.

    `has_path_control` is False here by design — offering a route picker a device
    lacks is the worse failure — which is also what makes it [DMC-1]'s discriminator.
    """
    profile = profile_for_model(model)

    assert profile["family"] == "generic"
    assert profile["display_name"] == "Dreame"
    assert profile["has_path_control"] is False
    assert profile["supports_zone_clean"] is False
    # The baseline still assumes a modern Dreame can mop and docks: these degrade
    # safely because live entity presence is the real gate.
    assert profile["has_mop"] is True
    assert profile["has_station"] is True


def test_dmc7_path_control_fails_closed_for_every_catalogued_model():
    """[DMC-7] A sweep, because the fail-closed rule has to hold for all 700.

    `has_path_control` gates a per-room route picker. Only a hardware-verified
    override may turn it on — no regime composite implies a route axis, and
    `_TIER_STATION` carries no such key, so every regime-derived profile must inherit
    the default's False. One model wrongly True renders a control its device cannot
    honour.

    Scoped to models WITHOUT an override, so [DMC-1]'s True is not a counterexample
    to its own rule.

    RED: flip `DEFAULT_PROFILE["has_path_control"]` to True and this names every model
    that changed.
    """
    assert DEFAULT_PROFILE["has_path_control"] is False, (
        "the baseline no longer fails closed; the sweep below is then vacuous"
    )

    wrong = [
        model for model in DREAME_MODEL_REGIMES
        if model not in MODEL_PROFILES
        and profile_for_model(model)["has_path_control"] is not False
    ]
    assert not wrong, (
        f"{len(wrong)} catalogued model(s) claim a route axis with no verified "
        f"override: {sorted(wrong)[:10]}"
    )
    # Positive control: the sweep looked at a real, non-trivial set.
    assert len(DREAME_MODEL_REGIMES) > 500, (
        f"only {len(DREAME_MODEL_REGIMES)} models swept — the regime table shrank and "
        f"this assertion no longer covers what it claims"
    )


def test_dmc8_every_authored_override_has_a_real_display_name():
    """[DMC-8] The two-table drift the module docstring warns about, from the other side.

    The module asserts at import that `MODEL_PROFILES ⊆ DREAME_MODEL_REGIMES`. It does
    NOT assert the same against `DREAME_MODEL_NAMES` — and that is the table
    `display_name` is single-sourced from. A hardware-verified model missing from the
    name table does not raise: it silently renders as the generic `"Dreame"`, which
    for the one authored entry means the maintainer's own L10s Ultra Gen 2 shows up
    unnamed on his card.

    RED: remove `_AUTHORED` from `DREAME_MODEL_NAMES` and this fails; the module's own
    import-time assert stays green, which is the point.
    """
    unnamed = [m for m in MODEL_PROFILES if m not in DREAME_MODEL_NAMES]
    assert not unnamed, (
        f"authored override(s) absent from the name table, so they render as the "
        f"generic 'Dreame': {sorted(unnamed)}"
    )
    for model in MODEL_PROFILES:
        assert profile_for_model(model)["display_name"] != "Dreame", (
            f"{model} has a verified capability profile but no name of its own"
        )
