"""
Model number → display name catalog for the Eufy adapter.

UPKEEP_MODEL_NAMES maps Eufy device model numbers to human-readable display
names shown in the UI and upkeep guide headers. It is the only dict this module
declares.

⚠ THIS DOCSTRING USED TO DESCRIBE THREE DICTS. ``UPKEEP_MODEL_GUIDE_FAMILIES``
and ``UPKEEP_GUIDE_FAMILY_NAMES`` were deleted in c2725f6a when Eufy was ported
to the shared regime → i18n-key guide system, and the guide family concept went
with them: guidance is now routed by REGIME (``upkeep_keys.py`` over
``upkeep_regimes.py``, the same three measured fields every brand uses), and the
backend holds no guide words at all. The docstring outlived the structure it
described, which is why a doc citing ``UPKEEP_MODEL_GUIDE_FAMILIES`` still read
as current.
"""

# ⚠ THE EUFY CATALOGS DO NOT DESCRIBE THE SAME DEVICE SET, and none of them says so.
# Re-measured 2026-09-13 after the regime port (by AST, not grep — a regex over these
# files counts nested keys and gets it wrong):
#
#   MODEL_CODE_FAMILIES    (model_catalog.py)   22 codes
#   UPKEEP_MODEL_NAMES     (here)               13
#   EUFY_MODEL_KEY_REGIMES (upkeep_keys.py)     13
#   WATER_MODEL_CONFIGS    (water_config.py)     1  — "T2351" only
#
#   • 9 of the 22 codes still have NO upkeep name at all.
#   • every Eufy except T2351 takes core's generic water flow rate.
#
# WHAT THE REGIME PORT FIXED: the old third catalog, UPKEEP_MODEL_GUIDE_FAMILIES, held
# 12 rows against these 13 names, so "T2352" carried a display name with no guide behind
# it. The regime table replaced it and the two now agree EXACTLY — 0 models named here
# without a regime row, 0 the other way. That drift class is closed; the name-vs-code gap
# above is not.
#
# Every one of those degradations is reported honestly at runtime rather than faked,
# which is why none of it is a bug. The HAZARD is a reader: a catalog comment saying
# "dock-action entities confirmed" reads as SUPPORTED, when what it confirms is that ONE
# catalog was updated. Adding a code here does not give it water rates. Check each when
# adding a model.
UPKEEP_MODEL_NAMES: dict[str, str] = {
    "T2351": "Robovac X10 Pro Omni",
    "T2352": "Robovac Omni E28",
    "T2080": "Robovac S1 Pro",
    "T2071": "Robovac S1",
    "T2280": "Robovac Omni C20",
    "T2261": "RoboVac X8 Hybrid",
    "T2262": "RoboVac X8",
    "T2266": "Robovac X8 Pro",
    "T2276": "Robovac X8 Pro SES",
    "T2267": "RoboVac L60",
    "T2268": "Robovac L60 Hybrid",
    "T2277": "Robovac L60 SES",
    "T2278": "Robovac L60 Hybrid SES",
}

# REMOVED 2026-09-12 — UPKEEP_MODEL_GUIDE_FAMILIES and UPKEEP_GUIDE_FAMILY_NAMES.
# Guide routing is by REGIME now (upkeep_regimes.py -> adapters/upkeep_keys.py), so a model
# no longer resolves to a per-product-line family. UPKEEP_MODEL_NAMES stays: it is the
# device.model -> display name map, which the card still shows and the regime does not carry.
