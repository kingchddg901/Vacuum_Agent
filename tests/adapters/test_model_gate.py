# -*- coding: utf-8 -*-
"""[MGT] The shared model gate — "does THIS MODEL have this component?"

ONE QUESTION, FOUR CONSUMERS: the three entity platforms (button / number / sensor) and the
card's upkeep snapshot. Until 2026-09-14 only the card asked it, and the platforms walked the
flat BRAND catalog instead — so a component the model does not have still minted three entities.
876 (model, component) pairs across the three brands, confirmed on hardware: a Roborock S6 with
a Cleaning Tray it has no station for, an L10s Ultra with Mop Pad Holders it is not a Matrix10.

Coverage targets
----------------
[MGT-1]  the core five are emitted by every one of 754 models, so the gate can never remove
         them from a model it recognises.
[MGT-2]  a resolved regime gates a SENSOR-BACKED component too. This is the contract change;
         the old gate exempted anything declaring a `sensor_suffix`.
[MGT-3]  regime routed but THIS model unresolved -> guide-only components drop, own-counter
         components stand.
[MGT-4]  an adapter that is NOT regime-routed keeps everything. THE THIRD STATE.
[MGT-5]  no model can be gated down to fewer than the core five.
[MGT-6]  the two live phantoms, pinned by model id.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.upkeep_keys import (
    NOT_REGIME_ROUTED,
    components_for_model,
    model_has_component,
)

CORE_FIVE = {"filter", "main_brush", "side_brush", "sensor", "omnidirectional_wheel"}


def _brand(name):
    mc = __import__(
        f"custom_components.eufy_vacuum.adapters.{name}.maintenance_components",
        fromlist=["MAINTENANCE_COMPONENTS"],
    ).MAINTENANCE_COMPONENTS
    uk = __import__(
        f"custom_components.eufy_vacuum.adapters.{name}.upkeep_keys", fromlist=["x"]
    )
    return (
        mc,
        getattr(uk, f"{name.upper()}_MODEL_KEY_REGIMES"),
        getattr(uk, f"{name.upper()}_UPKEEP_KEY_GUIDES"),
    )


def _config(name):
    _, regimes, guides = _brand(name)
    return {"upkeep_catalog": {"model_key_regimes": regimes, "key_guides": guides}}


def test_the_core_five_are_universal():
    """[MGT-1] Chris: *"the 5 core componsets the vacuums have."* Measured, not asserted from
    the catalog: the intersection of every model's emitted set across all three brands.

    THE INPUT THAT MAKES THIS RED: a regime that omits one of the five. That would mean the
    gate could strip a filter or a brush card off a model we correctly recognise, which is the
    one outcome this whole change must not have.
    """
    universal = None
    total = 0
    for name in ("dreame", "eufy", "roborock"):
        _, regimes, guides = _brand(name)
        for model, rid in regimes.items():
            emitted = frozenset(guides.get(rid, {}))
            universal = emitted if universal is None else (universal & emitted)
            total += 1
    assert total == 754, f"{total} models measured, expected 754"
    assert universal == CORE_FIVE, f"universal set is {sorted(universal or ())}"


def test_a_resolved_regime_gates_a_sensor_backed_component():
    """[MGT-2] THE CONTRACT CHANGE, and the reason it is one.

    The old gate read `maintenance_only and not meta.get("sensor_suffix") and component not in
    <regime set>`, and its comment defended the suffix exemption as keeping Eufy unaffected.
    Eufy's `cleaning_tray` DECLARES a suffix, so the gate could never reach it — structural, not
    an oversight. And the exemption rested on a premise measured FALSE: `robovac_mqtt` gates its
    consumables on `supported_api_types`, a PROTOCOL family, so a novel-protocol Eufy publishes
    a tray counter whether or not it owns a tray. Chris: *"for eufy Gate them."*

    THE INPUT THAT MAKES THIS RED: restore the `not meta.get("sensor_suffix")` clause. Every
    model below then keeps a tray panel its regime omits.
    """
    mc, regimes, guides = _brand("eufy")
    assert mc["cleaning_tray"].get("sensor_suffix"), (
        "this test is only meaningful while Eufy's tray declares a suffix — that declaration is "
        "what the old gate exempted"
    )
    cfg = _config("eufy")
    gated = []
    for model, rid in regimes.items():
        if "cleaning_tray" in guides[rid]:
            continue
        emitted = components_for_model(cfg, model)
        assert not model_has_component(
            emitted, "cleaning_tray", has_own_counter=True
        ), f"{model} has no tray in its regime but the gate let it through"
        gated.append(model)
    assert len(gated) == 8, f"expected 8 tray-less Eufy models, got {len(gated)}: {gated}"


def test_routed_but_unresolved_keeps_only_what_the_device_reports():
    """[MGT-3] Chris: *"if regime is unresolved it will lose its maintenance cards."*

    A regime-routed adapter that cannot place this model has TRIED AND FAILED, which is itself a
    statement: the hardware is unknown, so nothing guide-only is invented. A component the device
    is actively reporting on survives, because that reading is real whatever the model turns out
    to be.

    THE INPUT THAT MAKES THIS RED: return an empty frozenset for an unresolved model instead of
    None. Then `component in emitted` is False for everything and an unrecognised machine loses
    its filter and brushes too — the opposite of honest.
    """
    cfg = _config("roborock")
    emitted = components_for_model(cfg, "roborock.vacuum.does-not-exist")
    assert emitted is None, "an unresolved model must be distinguishable from an empty set"
    assert model_has_component(emitted, "filter", has_own_counter=True) is True
    assert model_has_component(emitted, "cleaning_tray", has_own_counter=False) is False
    assert model_has_component(emitted, "mop", has_own_counter=False) is False


def test_an_adapter_with_no_regime_table_keeps_everything():
    """[MGT-4] THE THIRD STATE, and it was a real bug — caught by
    `test_maintenance_manager` on this gate's first run, six tests red, not reasoned out ahead.

    An adapter declaring no `key_guides` has said NOTHING about hardware, so every component it
    declares stands. That is the shipped behaviour, and the old gate's `_guide_routed` flag is
    precisely what expressed it. Collapse it into the unresolved case — as the first draft did —
    and a test adapter, or any brand that never adopts regimes, silently loses every guide-only
    card while every regime-routed brand looks fine.

    THE INPUT THAT MAKES THIS RED: return `None` instead of `NOT_REGIME_ROUTED` when there are
    no key guides.
    """
    for cfg in ({}, {"upkeep_catalog": {}}, {"upkeep_catalog": {"key_guides": {}}}, None):
        emitted = components_for_model(cfg, "anything")
        assert emitted is NOT_REGIME_ROUTED, f"{cfg!r} should be NOT_REGIME_ROUTED"
        assert model_has_component(emitted, "cleaning_tray", has_own_counter=False) is True, (
            "an adapter with no regime opinion must not have one enforced on it"
        )


@pytest.mark.parametrize("name", ["dreame", "eufy", "roborock"])
def test_no_model_falls_below_the_core_five(name):
    """[MGT-5] The floor, per brand and per model. A regime that emitted 4 components would be a
    machine missing a real maintenance card, and the gate would faithfully hide it."""
    mc, regimes, guides = _brand(name)
    cfg = _config(name)
    for model in regimes:
        emitted = components_for_model(cfg, model)
        kept = {
            c
            for c in mc
            if model_has_component(
                emitted, c, has_own_counter=bool(mc[c].get("sensor_suffix"))
            )
        }
        assert CORE_FIVE <= kept, f"{model} lost {sorted(CORE_FIVE - kept)}"


def test_the_two_live_phantoms_are_gated():
    """[MGT-6] The two measured on hardware, pinned by model id so a regime edit cannot
    silently re-admit them.

    ivy is a Roborock S6 — charge-only dock, `supports_mop_wash: false`, and it had
    `button/number/sensor.ivy_cleaning_tray_maintenance_*` for a station it does not have.
    robin is a Dreame L10s Ultra Gen2, not a Matrix10, and it had `mop_pad_holders` entities
    accumulating hours against no interval.
    """
    rb = _config("roborock")
    s6 = components_for_model(rb, "roborock.vacuum.s6")
    assert s6 is not None and "cleaning_tray" not in s6
    assert not model_has_component(s6, "cleaning_tray", has_own_counter=False)
    assert CORE_FIVE <= set(s6) and "mop" in s6, "an S6 mops with a manual cloth"

    dm = _config("dreame")
    _, regimes, guides = _brand("dreame")
    holders = {m for m, r in regimes.items() if "mop_pad_holders" in guides[r]}
    assert len(holders) == 15, f"{len(holders)} models emit mop_pad_holders, expected 15"
    not_holders = set(regimes) - holders
    assert len(not_holders) == 685
    sample = sorted(not_holders)[0]
    assert not model_has_component(
        components_for_model(dm, sample), "mop_pad_holders", has_own_counter=False
    )
