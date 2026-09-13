# -*- coding: utf-8 -*-
"""[EUK] Eufy on the shared regime -> key guide.

Replaces tests/adapters/eufy/test_upkeep_guides_i18n.py, which checked that five authored
families were translated into seventeen languages. There are no families and no Eufy-authored
prose any more: the backend emits i18n KEY LISTS and the card resolves them in the READER's
language. What is worth asserting changed with it.
"""

from __future__ import annotations

import json

from custom_components.eufy_vacuum.adapters.dreame.upkeep_keys import DREAME_UPKEEP_KEYS
from custom_components.eufy_vacuum.adapters.eufy.maintenance_components import (
    MAINTENANCE_COMPONENTS,
)
from custom_components.eufy_vacuum.adapters.eufy.upkeep_keys import (
    EUFY_MODEL_KEY_REGIMES,
    EUFY_UPKEEP_KEY_GUIDES,
    EUFY_UPKEEP_KEYS,
)
from custom_components.eufy_vacuum.adapters.eufy.upkeep_regimes import EUFY_MODEL_REGIMES


def _emitted_components():
    return {c for guide in EUFY_UPKEEP_KEY_GUIDES.values() for c in guide}


def test_eufy_adds_no_new_keys():
    """[EUK-1] THE CLAIM THE WHOLE PORT RESTS ON, and the one that can go quietly wrong.

    A key Eufy emits that Dreame never did is a key nobody authored and nobody translated. It
    would render as its own name -- the fallback is not silent, but it is not caught by any
    other test here either, because every count below would still be green.
    """
    unauthored = EUFY_UPKEEP_KEYS - DREAME_UPKEEP_KEYS
    assert not unauthored, (
        f"Eufy emits {sorted(unauthored)}, which no authored pack covers. Either author them "
        f"in all 18 packs or change the regime that produces them"
    )


def test_every_declared_component_is_emitted_and_every_emitted_one_declared():
    """[EUK-2] the two halves must agree or a panel silently has no home.

    A component the emitter produces but the catalog does not declare gets no entity binding,
    no interval and no icon. One declared but never emitted is a row the card can never show.
    Neither raises; both just quietly do nothing.
    """
    declared = set(MAINTENANCE_COMPONENTS)
    emitted = _emitted_components()
    assert emitted - declared == set(), f"emitted but undeclared: {sorted(emitted - declared)}"
    assert declared - emitted == set(), f"declared but never emitted: {sorted(declared - emitted)}"


def test_the_canonical_ids_are_used_not_eufys_own_words():
    """[EUK-3] core owns the KEY; the brand keeps the WORD via label_key.

    `mop_cloth` and `caster_wheel` were Eufy's storage keys. The shared emitter names these
    panels `mop` and `omnidirectional_wheel`, so the catalog must too -- and Eufy's display word
    survives as `label_key`, not as the id. `mopping_cloth` is the one that does NOT survive:
    five of Eufy's ten mop-bearing models carry a roller or a pad, so it was wrong on them.
    """
    assert "mop" in MAINTENANCE_COMPONENTS and "mop_cloth" not in MAINTENANCE_COMPONENTS
    assert ("omnidirectional_wheel" in MAINTENANCE_COMPONENTS
            and "caster_wheel" not in MAINTENANCE_COMPONENTS)
    assert MAINTENANCE_COMPONENTS["main_brush"].get("label_key") == "rolling_brush"
    assert MAINTENANCE_COMPONENTS["omnidirectional_wheel"].get("label_key") == "swivel_wheel"
    assert MAINTENANCE_COMPONENTS["mop"].get("label_key") is None, (
        "'Mopping Cloth' is wrong on Eufy's roller and pad machines — `mop` covers all four "
        "shapes, which is why this one brand word does not survive"
    )


def test_the_family_system_is_gone():
    """[EUK-4] the deletion is the point; a leftover import would keep it alive unnoticed."""
    import custom_components.eufy_vacuum.adapters.eufy.adapter as adapter
    import custom_components.eufy_vacuum.adapters.eufy.upkeep_catalog as catalog

    assert not hasattr(catalog, "UPKEEP_MODEL_GUIDE_FAMILIES")
    assert not hasattr(catalog, "UPKEEP_GUIDE_FAMILY_NAMES")
    assert hasattr(catalog, "UPKEEP_MODEL_NAMES"), "display names are still needed"
    assert not hasattr(adapter, "UPKEEP_GUIDE_LIBRARY")
    assert not hasattr(adapter, "UPKEEP_GUIDE_TRANSLATIONS")


def test_the_collapse_holds():
    """[EUK-5] 13 models, 6 regimes, 4 cards — the argument, in Eufy's numbers."""
    bodies = {
        json.dumps(EUFY_UPKEEP_KEY_GUIDES[r], sort_keys=True)
        for r in EUFY_MODEL_KEY_REGIMES.values()
    }
    assert len(EUFY_MODEL_REGIMES) == 13, (
        f"{len(EUFY_MODEL_REGIMES)} models, expected 13 — update deliberately if the catalog grew"
    )
    assert len(EUFY_UPKEEP_KEY_GUIDES) == 6, f"{len(EUFY_UPKEEP_KEY_GUIDES)} regimes, expected 6"
    assert len(bodies) == 4, (
        f"{len(bodies)} distinct card SETS, expected 4. NOTE THE UNIT: unique whole-card-SETS, "
        "not panels. A RISE can be two regimes correctly separating; a FALL can be a real merge "
        "or a panel retired on purpose. Change it deliberately and say which it was."
    )


def test_the_vacuum_only_machines_are_here_and_carry_no_mop_panel():
    """[EUK-6] Eufy is the ONLY brand with a mop-less model, so this case lives or dies here.

    Dreame ships nothing vacuum-only; Roborock's six arrived later. The `none` mop type entered
    the catalog with Eufy, and if these regimes ever stopped emitting no-mop cards there is no
    other brand whose data would catch it.
    """
    vacuum_only = [r for r in EUFY_UPKEEP_KEY_GUIDES if r.startswith("none|")]
    assert vacuum_only, "Eufy's vacuum-only regimes are missing — the L60 and X8 are mop-less"
    for regime in vacuum_only:
        comps = EUFY_UPKEEP_KEY_GUIDES[regime]
        assert "mop" not in comps, f"{regime} documents a mop on a machine that has none"
        assert "cleaning_tray" not in comps, f"{regime} has no station to wash a mop in"
        steps = comps["filter"]["steps"]
        assert "bin.empty_water_too" not in steps, (
            f"{regime} carries no water at all, but its bin card says to empty some"
        )
