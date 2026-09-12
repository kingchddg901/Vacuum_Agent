"""Dreame adapter package — DATA ONLY, deliberately not wired.

⚠ THERE IS NO ``BRAND_REGISTRARS`` ROW FOR DREAME, AND ADDING ONE IS THE RELEASE.
That row is the switch. The adapter is gated on a RELEASED upstream build of the
`dreame_vacuum` custom integration carrying Tasshack issue #1707; our #1742 is closed
as a duplicate and reads green, which it is not. Until that lands, everything here is
inert reference data that ships without changing behaviour for anyone.

What lives here is the half that does not depend on the gate: the upkeep guides and the
model metadata. The driving logic (`adapter.py`) does.

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
