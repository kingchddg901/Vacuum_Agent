# -*- coding: utf-8 -*-
"""Roborock's half of the key guide: its regime table, run through the shared emitter.

The card algorithm, the 42 keys and the eight components live in ``adapters/upkeep_keys.py``.
What is Roborock's is the TABLE: 41 models, three measured fields each, generated from the
fixture manifest by scripts/sync-upkeep-regimes.py.

WHAT THIS REPLACED. Three authored guide families keyed off a hand-assigned maintenance TIER,
plus 19 files of translated prose. The tier column was wrong on 8 of 41 models and the errors
went both ways — four China-market machines shipped as `standard` (no dock at all) when they
carry one, four Q-series shipped as `auto_empty` when the base SKU has no dock. None of those
are corrected: the column is gone, and `dock_tier` is measured per model in the manifest.

ROBOROCK ADDS ZERO NEW KEYS AND ZERO NEW CARD SETS. Its washing-cloth lineup — every VibraRise
machine and the whole Qrevo line — emits a card set byte-identical to Dreame's SimuMop shapes,
because `SimuMop` normalises to `cloth` at generation. Chris wrote that alias into the schema
before any of this was measured, and it is what made the entire line free.
"""

from __future__ import annotations

from ..upkeep_keys import build_key_guides
from .upkeep_regimes import ROBOROCK_MODEL_REGIMES

(
    ROBOROCK_UPKEEP_KEY_GUIDES,
    ROBOROCK_MODEL_KEY_REGIMES,
    ROBOROCK_UPKEEP_KEYS,
) = build_key_guides(ROBOROCK_MODEL_REGIMES)

__all__ = [
    "ROBOROCK_UPKEEP_KEY_GUIDES",
    "ROBOROCK_MODEL_KEY_REGIMES",
    "ROBOROCK_UPKEEP_KEYS",
]
