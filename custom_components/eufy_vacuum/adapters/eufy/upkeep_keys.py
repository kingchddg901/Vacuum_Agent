# -*- coding: utf-8 -*-
"""Eufy's half of the key guide: its regime table, run through the shared emitter.

The card algorithm, the 42 keys and the eight components live in ``adapters/upkeep_keys.py``.
They are not Eufy's and they are not Dreame's — they are every brand's. What is Eufy's is the
TABLE: 13 models, three measured fields each, generated from the fixture manifest by
scripts/sync-upkeep-regimes.py.

WHAT THIS REPLACED. Five hand-authored guide families (``x8_series``, ``l60_series``, ``s1_pro``,
``x10_pro_omni``, ``omni_c20``) plus seventeen language packs of prose. Those families were
per-PRODUCT-LINE, so a new model meant authoring a sixth and translating it into 17 languages
before it could ship.

EUFY ADDS ZERO NEW KEYS. Every card its 13 models render already existed for Dreame and is
already translated into all 18 languages — it contributes two regimes nobody had measured before
(``none|charge_only|no`` and ``none|auto_empty|no``, the vacuum-only machines) and those collapse
onto one card set that Dreame's own mop-less shapes could never produce, because Dreame ships no
vacuum-only model. The catalogue grew by one card and no words.
"""

from __future__ import annotations

from ..upkeep_keys import build_key_guides
from .upkeep_regimes import EUFY_MODEL_REGIMES

(
    EUFY_UPKEEP_KEY_GUIDES,
    EUFY_MODEL_KEY_REGIMES,
    EUFY_UPKEEP_KEYS,
) = build_key_guides(EUFY_MODEL_REGIMES)

__all__ = [
    "EUFY_UPKEEP_KEY_GUIDES",
    "EUFY_MODEL_KEY_REGIMES",
    "EUFY_UPKEEP_KEYS",
]
