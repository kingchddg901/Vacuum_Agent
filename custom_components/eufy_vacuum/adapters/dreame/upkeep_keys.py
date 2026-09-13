# -*- coding: utf-8 -*-
"""Dreame's half of the key guide: its regime table, run through the shared emitter.

The card algorithm, the 42 keys and the eight components live in ``adapters/upkeep_keys.py`` --
they are not Dreame's, they are every brand's. What is Dreame's is the TABLE: 700 models, three
measured fields each, generated from the fixture manifest by scripts/sync-dreame-regimes.py.

Adding a model stays ONE ROW in ``upkeep_regimes.py``. No authored text, no new family, no
translation work.
"""

from __future__ import annotations

from ..upkeep_keys import (  # re-exported: this module is the Dreame-facing surface
    BACK_IN,
    BIN_IS_2IN1,
    DOCK_IT,
    MANUAL,
    MOP,
    build_key_guides,
    emit,
    regime_id,
)
from .upkeep_regimes import DREAME_MODEL_REGIMES

(
    DREAME_UPKEEP_KEY_GUIDES,
    DREAME_MODEL_KEY_REGIMES,
    DREAME_UPKEEP_KEYS,
) = build_key_guides(DREAME_MODEL_REGIMES)

__all__ = [
    "DREAME_UPKEEP_KEY_GUIDES",
    "DREAME_MODEL_KEY_REGIMES",
    "DREAME_UPKEEP_KEYS",
    "BACK_IN", "BIN_IS_2IN1", "DOCK_IT", "MANUAL", "MOP",
    "build_key_guides", "emit", "regime_id",
]
