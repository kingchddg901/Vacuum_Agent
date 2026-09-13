"""
Model number → name and guide family catalog for the Eufy adapter.

UPKEEP_MODEL_NAMES maps Eufy device model numbers to human-readable display
names shown in the UI and upkeep guide headers.

UPKEEP_MODEL_GUIDE_FAMILIES maps model numbers to a guide family key. Multiple
models share one family when their upkeep instructions are identical. This
allows the guide library to be compact without duplicating entries.

UPKEEP_GUIDE_FAMILY_NAMES maps guide family keys to the display name shown
in the upkeep guide header for that family group.

A port to a different brand replaces all three dicts with the equivalent
model numbers and display names for that brand.
"""

# ⚠ THE THREE EUFY CATALOGS DO NOT DESCRIBE THE SAME DEVICE SET, and none of them
# says so. Measured 2026-08-23 (by AST, not grep — a regex over these files counts
# nested keys and gets it wrong):
#
#   MODEL_CODE_FAMILIES (model_catalog.py)   22 codes
#   UPKEEP_MODEL_NAMES  (here)               13
#   UPKEEP_MODEL_GUIDE_FAMILIES (here)       12
#   WATER_MODEL_CONFIGS (water_config.py)     1  — "T2351" only
#
#   • 9 of the 22 codes have NO upkeep name at all.
#   • "T2352" has a NAME here and NO guide row below — a model that presents a
#     display name with no guide behind it.
#   • every Eufy except T2351 takes core's generic water flow rate.
#
# Every one of those degradations is reported honestly at runtime rather than faked,
# which is why none of it is a bug. The HAZARD is a reader: a catalog comment saying
# "dock-action entities confirmed" reads as SUPPORTED, when what it confirms is that
# ONE of three catalogs was updated. Adding a code here does not give it a guide, and
# adding a guide does not give it water rates. Check all three when adding a model.
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
