# -*- coding: utf-8 -*-
"""Roborock upkeep REGIMES — the three measured fields the guide is derived from.

    ROBOROCK_MODEL_REGIMES[model_id] = (mop_type, dock_tier, tanks)

This replaces a MAINTENANCE TIER column (standard / auto_empty / wash_station) that was hand
assigned per model and wrong on 8 of 41. The measurement is in the manifest: the four G10 and
T7S Plus rows shipped as `standard` (no dock at all) actually carry one, and the four Q-series
rows shipped as `auto_empty` were given the '+' variant's dock when the base SKU has none.
Those 8 are not corrected here — the column is DELETED. dock_tier is measured per model now,
and Roborock adds ZERO new keys and ZERO new card sets to the shared set.

THE TABLE IS THE AUTHORITY, NOT A DERIVED CACHE. `upkeep_keys.py` computes the card from these
three fields at import; the card sets are not stored. Shipping the derived answer instead of
the inputs is how a cache starts being treated as a source.

Adding a model is ONE ROW here. No authored text, no new family, no translation work — the
41 models below already collapse to 4 distinct cards, so a new row almost always renders a
card that already exists and is already translated into all 18 languages.

GENERATED from durable/dreame-port-fixture/derived/manifest_table.csv (outside git — it carries
the full provenance: per-model doc ties, measurement basis per field, and the hand-walk record).
Regenerate with scripts/sync-upkeep-regimes.py.
"""

from __future__ import annotations

ROBOROCK_MODEL_REGIMES: dict[str, tuple[str, str, str]] = {
    "roborock.vacuum.a01":         ("cloth", "charge_only", "no"),
    "roborock.vacuum.a08":         ("cloth", "charge_only", "no"),
    "roborock.vacuum.a10":         ("cloth", "charge_only", "no"),
    "roborock.vacuum.a101":        ("pad", "wash+empty", "yes"),
    "roborock.vacuum.a104":        ("pad", "wash+empty", "yes"),
    "roborock.vacuum.a11":         ("cloth", "charge_only", "no"),
    "roborock.vacuum.a117":        ("pad", "wash+empty", "yes"),
    "roborock.vacuum.a135":        ("pad", "wash+empty", "yes"),
    "roborock.vacuum.a14":         ("cloth", "charge_only", "no"),
    "roborock.vacuum.a143":        ("pad", "wash+empty", "yes"),
    "roborock.vacuum.a144":        ("pad", "wash+empty", "yes"),
    "roborock.vacuum.a147":        ("cloth", "wash+empty", "yes"),
    "roborock.vacuum.a15":         ("cloth", "charge_only", "no"),
    "roborock.vacuum.a19":         ("none", "charge_only", "no"),
    "roborock.vacuum.a23":         ("cloth", "auto_empty", "no"),
    "roborock.vacuum.a26":         ("cloth", "wash+empty", "yes"),
    "roborock.vacuum.a27":         ("cloth", "charge_only", "no"),
    "roborock.vacuum.a29":         ("cloth", "wash_only", "yes"),
    "roborock.vacuum.a34":         ("none", "charge_only", "no"),
    "roborock.vacuum.a38":         ("cloth", "charge_only", "no"),
    "roborock.vacuum.a40":         ("cloth", "charge_only", "no"),
    "roborock.vacuum.a46":         ("cloth", "wash+empty", "yes"),
    "roborock.vacuum.a51":         ("cloth", "charge_only", "no"),
    "roborock.vacuum.a62":         ("cloth", "wash+empty", "yes"),
    "roborock.vacuum.a65":         ("cloth", "wash+empty", "yes"),
    "roborock.vacuum.a70":         ("cloth", "wash+empty", "yes"),
    "roborock.vacuum.a72":         ("cloth", "charge_only", "no"),
    "roborock.vacuum.a73":         ("cloth", "charge_only", "no"),
    "roborock.vacuum.a75":         ("pad", "wash+empty", "yes"),
    "roborock.vacuum.a87":         ("pad", "wash+empty", "yes"),
    "roborock.vacuum.a97":         ("cloth", "wash+empty", "yes"),
    "roborock.vacuum.c1":          ("none", "charge_only", "no"),
    "roborock.vacuum.e2":          ("cloth", "charge_only", "no"),
    "roborock.vacuum.m1s":         ("none", "charge_only", "no"),
    "roborock.vacuum.s4":          ("none", "charge_only", "no"),
    "roborock.vacuum.s5":          ("cloth", "charge_only", "no"),
    "roborock.vacuum.s5e":         ("cloth", "charge_only", "no"),
    "roborock.vacuum.s6":          ("cloth", "charge_only", "no"),
    "roborock.vacuum.ss07":        ("cloth", "charge_only", "no"),
    "roborock.vacuum.t6":          ("cloth", "charge_only", "no"),
    "roborock.vacuum.v1":          ("none", "charge_only", "no"),
}

# The 6 distinct regimes present, largest first — a comment, not a second copy. Derive from
# ROBOROCK_MODEL_REGIMES rather than reading this:
#   cloth     charge_only       no        18 models
#   pad       wash+empty        yes        8 models
#   cloth     wash+empty        yes        7 models
#   none      charge_only       no         6 models
#   cloth     auto_empty        no         1 models
#   cloth     wash_only         yes        1 models
