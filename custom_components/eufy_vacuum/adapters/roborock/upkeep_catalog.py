"""Roborock upkeep catalog — the model/display-name map, and nothing else now.

``ROBOROCK_MODEL_NAMES``  device.model -> human display name.

WHAT THIS FILE USED TO HOLD, AND WHY IT DOES NOT. A third column on every row assigned each
model a maintenance TIER (standard / auto_empty / wash_station), and two maps turned that into
a guide family. The stated rationale was that "the ~37 robot models collapse to a few tiers
because brush/filter/sensor upkeep is identical across the lineup" — which is true, and is
exactly why the tier could not carry its own weight: it was a hand-assigned proxy for the dock,
and it was WRONG ON 8 OF 41 MODELS, in both directions.

    SHIPPED TOO LITTLE — `standard`, i.e. no dock at all, on machines that ship one:
        a29 G10 · a46 G10S · a26 G10S Pro · a23 T7S Plus
    SHIPPED TOO MUCH — `auto_empty` on models whose BASE SKU has no dock, because the
    "+" variant's station was read as the model's:
        a38 Q7 Max · a72 Q5 Pro · a73 Q8 Max · ss07 Q10

The Q-series four disagreed with this file's OWN convention as well: a15 S7, a27 S7 MaxV and
a51 S8 have the same optional-dock arrangement and were correctly left at `standard`.

None of the 8 are corrected. The column is DELETED, and `dock_tier` is MEASURED per model in
the fixture manifest, which is what `upkeep_regimes.py` is generated from. A hand-maintained
column that duplicates a measurable fact will drift from it again; the fix is to stop keeping
two copies, not to re-align them once.

Wet/dry stick vacs (roborock.wetdryvac.*, "Dyad") and the Zeo washer are excluded — different
products, no room maps, different upkeep.
"""

from __future__ import annotations

ROBOROCK_MODELS: list[tuple[str, str]] = [
    # (device.model, display name). THE TIER COLUMN IS GONE — see the note above.
    ("roborock.vacuum.v1", "V1"),
    ("roborock.vacuum.s4", "S4"),
    ("roborock.vacuum.a19", "S4 Max"),
    ("roborock.vacuum.s5", "S5"),
    ("roborock.vacuum.s5e", "S5 Max"),
    ("roborock.vacuum.s6", "S6"),
    ("roborock.vacuum.t6", "S6 (CN)"),
    ("roborock.vacuum.a08", "S6 Pure"),
    ("roborock.vacuum.a10", "S6 MaxV"),
    ("roborock.vacuum.a01", "E4"),
    ("roborock.vacuum.e2", "E2"),
    ("roborock.vacuum.m1s", "1S"),
    ("roborock.vacuum.c1", "C1"),
    ("roborock.vacuum.a11", "T7 (S7 CN)"),
    ("roborock.vacuum.a14", "T7S"),
    ("roborock.vacuum.a23", "T7S Plus"),
    ("roborock.vacuum.a15", "S7"),
    ("roborock.vacuum.a27", "S7 MaxV"),
    ("roborock.vacuum.a34", "Q5"),
    ("roborock.vacuum.a40", "Q7"),
    ("roborock.vacuum.a51", "S8"),
    ("roborock.vacuum.a29", "G10"),
    ("roborock.vacuum.a46", "G10S"),
    ("roborock.vacuum.a26", "G10S Pro"),
    ("roborock.vacuum.a72", "Q5 Pro"),
    ("roborock.vacuum.a38", "Q7 Max"),
    ("roborock.vacuum.a73", "Q8 Max"),
    ("roborock.vacuum.ss07", "Q10"),
    ("roborock.vacuum.a65", "S7 MaxV Ultra"),
    ("roborock.vacuum.a62", "S7 Pro Ultra"),
    ("roborock.vacuum.a70", "S8 Pro Ultra"),
    ("roborock.vacuum.a75", "Q Revo"),
    ("roborock.vacuum.a104", "Qrevo S"),
    ("roborock.vacuum.a101", "Qrevo Pro"),
    ("roborock.vacuum.a87", "Qrevo MaxV"),
    ("roborock.vacuum.a143", "G20S Ultra"),
    ("roborock.vacuum.a97", "S8 MaxV Ultra"),
    ("roborock.vacuum.a135", "Qrevo Curv"),
    ("roborock.vacuum.a117", "Qrevo Master"),
    ("roborock.vacuum.a144", "Saros 10R"),
    ("roborock.vacuum.a147", "Saros 10"),
]

ROBOROCK_MODEL_NAMES: dict[str, str] = {code: name for code, name in ROBOROCK_MODELS}

# REMOVED 2026-09-12 — the TIER column, ROBOROCK_MODEL_GUIDE_FAMILIES and
# ROBOROCK_GUIDE_FAMILY_NAMES. Guide routing is by REGIME now (upkeep_regimes.py ->
# adapters/upkeep_keys.py), and dock_tier is MEASURED per model in the fixture manifest
# rather than assigned here by hand. The tier was wrong on 8 of 41 and the 8 are not
# corrected: the column that held them does not exist any more.
