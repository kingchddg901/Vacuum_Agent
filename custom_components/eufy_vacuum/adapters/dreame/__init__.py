"""Dreame adapter package — DATA ONLY, deliberately not wired.

⚠ THERE IS NO ``BRAND_REGISTRARS`` ROW FOR DREAME, AND ADDING ONE IS THE RELEASE.
That row is the switch. The adapter is gated on a RELEASED upstream build of the
`dreame_vacuum` custom integration carrying Tasshack issue #1707; our #1742 is closed
as a duplicate and reads green, which it is not. Until that lands, everything here is
inert reference data that ships without changing behaviour for anyone.

What lives here is the half that does not depend on the gate: the upkeep guides and
the model/family metadata (the catalog that routes each model to a guide family). The
driving logic (`adapter.py`) does.
"""

from __future__ import annotations

from .dreame_upkeep_guides import DREAME_UPKEEP_GUIDE_LIBRARY
from .upkeep_catalog import (
    DREAME_GUIDE_FAMILY_NAMES,
    DREAME_MODEL_GUIDE_FAMILIES,
    DREAME_MODEL_NAMES,
    DREAME_MODELS,
)

__all__ = [
    "DREAME_UPKEEP_GUIDE_LIBRARY",
    "DREAME_MODELS",
    "DREAME_MODEL_NAMES",
    "DREAME_MODEL_GUIDE_FAMILIES",
    "DREAME_GUIDE_FAMILY_NAMES",
]
