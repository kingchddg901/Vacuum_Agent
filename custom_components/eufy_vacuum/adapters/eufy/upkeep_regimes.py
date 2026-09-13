# -*- coding: utf-8 -*-
"""Eufy upkeep REGIMES — the three measured fields the guide is derived from.

    EUFY_MODEL_REGIMES[model_id] = (mop_type, dock_tier, tanks)

This replaces five hand-authored guide families and their seventeen language packs. The
families were per-PRODUCT-LINE (x8_series, l60_series, s1_pro, x10_pro_omni, omni_c20), so a
new model meant authoring a sixth and translating it. The card content actually depends on
the three MEASURED fields below, and Eufy adds ZERO new keys to the shared set - every card
it renders already existed for Dreame and is already translated into all 18 languages.

THE TABLE IS THE AUTHORITY, NOT A DERIVED CACHE. `upkeep_keys.py` computes the card from these
three fields at import; the card sets are not stored. Shipping the derived answer instead of
the inputs is how a cache starts being treated as a source.

Adding a model is ONE ROW here. No authored text, no new family, no translation work — the
13 models below already collapse to 4 distinct cards, so a new row almost always renders a
card that already exists and is already translated into all 18 languages.

GENERATED from durable/dreame-port-fixture/derived/manifest_table.csv (outside git — it carries
the full provenance: per-model doc ties, measurement basis per field, and the hand-walk record).
Regenerate with scripts/sync-upkeep-regimes.py.
"""

from __future__ import annotations

EUFY_MODEL_REGIMES: dict[str, tuple[str, str, str]] = {
    "T2071":                       ("roller", "wash+empty", "yes"),
    "T2080":                       ("roller", "wash+empty", "yes"),
    "T2261":                       ("cloth", "charge_only", "no"),
    "T2262":                       ("none", "charge_only", "no"),
    "T2266":                       ("cloth", "charge_only", "no"),
    "T2267":                       ("none", "charge_only", "no"),
    "T2268":                       ("cloth", "charge_only", "no"),
    "T2276":                       ("cloth", "auto_empty", "no"),
    "T2277":                       ("none", "auto_empty", "no"),
    "T2278":                       ("cloth", "auto_empty", "no"),
    "T2280":                       ("pad", "wash+empty", "yes"),
    "T2351":                       ("pad", "wash+empty", "yes"),
    "T2352":                       ("roller", "wash+empty", "yes"),
}

# The 6 distinct regimes present, largest first — a comment, not a second copy. Derive from
# EUFY_MODEL_REGIMES rather than reading this:
#   roller    wash+empty        yes        3 models
#   cloth     charge_only       no         3 models
#   none      charge_only       no         2 models
#   cloth     auto_empty        no         2 models
#   pad       wash+empty        yes        2 models
#   none      auto_empty        no         1 models
