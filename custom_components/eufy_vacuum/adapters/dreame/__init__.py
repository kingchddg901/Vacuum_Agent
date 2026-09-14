"""Dreame adapter package — LIVE since 2026-09-13 (v2.2.0).

The ``BRAND_REGISTRARS`` row in ``adapters/brands.py`` is what reaches this package, and
it was deliberately withheld through all 131 commits of development: until it landed the
whole package was inert reference data that shipped without changing behaviour for anyone.
That row is now present, and ``test_dreame_has_a_brand_registrar_row`` [DUK-1] asserts it
stays — a dropped row is the SILENT direction, since nothing else imports this package.

The withholding condition was recorded as "a RELEASED upstream build carrying Tasshack
#1707". It was retired by measurement on 2026-08-30: only an UNMAPPED first setup is
bitten, a mapped device never is, so the remedy is a setup note — map first, then reload —
which shipped with the user guide. Do NOT re-derive the gate from tracker #1742; it is
closed as a duplicate and reads green, which it is not.

The guides are i18n KEY LISTS routed by REGIME (`upkeep_keys.py` over
`upkeep_regimes.py`), not prose routed by guide family. The backend holds no guide words
at all — the card supplies them in the reader's own language.
"""

from __future__ import annotations

from .upkeep_catalog import DREAME_MODEL_NAMES, DREAME_MODELS
from .upkeep_keys import (
    DREAME_MODEL_KEY_REGIMES,
    DREAME_UPKEEP_KEY_GUIDES,
    DREAME_UPKEEP_KEYS,
)
from .upkeep_regimes import DREAME_MODEL_REGIMES

__all__ = [
    "DREAME_MODELS",
    "DREAME_MODEL_NAMES",
    "DREAME_MODEL_REGIMES",
    "DREAME_MODEL_KEY_REGIMES",
    "DREAME_UPKEEP_KEY_GUIDES",
    "DREAME_UPKEEP_KEYS",
]
