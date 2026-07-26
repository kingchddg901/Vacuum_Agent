"""Roborock upkeep catalog — the model/family metadata half of ``upkeep_catalog``.

Mirrors adapters/eufy/upkeep_catalog.py. Three maps the maintenance manager reads
(via the adapter's ``upkeep_catalog`` config block) to pick the guide for a device:

- ``ROBOROCK_MODEL_NAMES``          device.model -> human display name
- ``ROBOROCK_MODEL_GUIDE_FAMILIES`` device.model -> guide family (maintenance tier)
- ``ROBOROCK_GUIDE_FAMILY_NAMES``   guide family -> display name

Guide families are MAINTENANCE PROFILES (dock + mop hardware), NOT per-model. The
~37 robot models the HA `roborock` integration supports collapse to a few tiers
because brush/filter/sensor upkeep is identical across the lineup — see
roborock_upkeep_guides.py.

``ROBOROCK_MODELS`` below is the single source: (device.model, display name, TIER).
The model->family map resolves each model to its tier IF that tier is authored in
the guide library, else falls back to ``standard`` — so the whole lineup gets the
base guides today and each model auto-upgrades the moment its tier lands (no edit
here). TIER assignments for the step-up models are PROVISIONAL (dock/mop specifics
pending) — but harmless until the richer tiers are authored, since everything
resolves to ``standard`` for now.

Wet/dry stick vacs (roborock.wetdryvac.*, "Dyad") and the Zeo washer are excluded
— different products, no room maps, different upkeep.
"""

from __future__ import annotations

from .roborock_upkeep_guides import ROBOROCK_UPKEEP_GUIDE_LIBRARY

# (device.model, display name, maintenance tier). Tier ∈
# standard | auto_empty | wash_station | dual_pad. Provisional for step-ups.
ROBOROCK_MODELS: list[tuple[str, str, str]] = [
    # -- standard: no dock, single/no mop pad -------------------------------
    ("roborock.vacuum.v1", "V1", "standard"),
    ("roborock.vacuum.s4", "S4", "standard"),
    ("roborock.vacuum.a19", "S4 Max", "standard"),
    ("roborock.vacuum.s5", "S5", "standard"),
    ("roborock.vacuum.s5e", "S5 Max", "standard"),
    ("roborock.vacuum.s6", "S6", "standard"),
    ("roborock.vacuum.t6", "S6 (CN)", "standard"),
    ("roborock.vacuum.a08", "S6 Pure", "standard"),
    ("roborock.vacuum.a10", "S6 MaxV", "standard"),
    ("roborock.vacuum.a01", "E4", "standard"),
    ("roborock.vacuum.e2", "E2", "standard"),
    ("roborock.vacuum.m1s", "1S", "standard"),
    ("roborock.vacuum.c1", "C1", "standard"),
    ("roborock.vacuum.a11", "T7 (S7 CN)", "standard"),
    ("roborock.vacuum.a14", "T7S", "standard"),
    ("roborock.vacuum.a23", "T7S Plus", "standard"),
    ("roborock.vacuum.a15", "S7", "standard"),
    ("roborock.vacuum.a27", "S7 MaxV", "standard"),
    ("roborock.vacuum.a34", "Q5", "standard"),
    ("roborock.vacuum.a40", "Q7", "standard"),
    ("roborock.vacuum.a51", "S8", "standard"),
    ("roborock.vacuum.a29", "G10", "standard"),
    ("roborock.vacuum.a46", "G10S", "standard"),
    ("roborock.vacuum.a26", "G10S Pro", "standard"),
    # -- auto_empty: dust-collection dock -----------------------------------
    ("roborock.vacuum.a72", "Q5 Pro", "auto_empty"),
    ("roborock.vacuum.a38", "Q7 Max", "auto_empty"),
    ("roborock.vacuum.a73", "Q8 Max", "auto_empty"),
    ("roborock.vacuum.ss07", "Q10", "auto_empty"),
    # -- wash_station: wash & dry dock, single/vibrating pad ----------------
    ("roborock.vacuum.a65", "S7 MaxV Ultra", "wash_station"),
    ("roborock.vacuum.a62", "S7 Pro Ultra", "wash_station"),
    ("roborock.vacuum.a70", "S8 Pro Ultra", "wash_station"),
    ("roborock.vacuum.a75", "Q Revo", "wash_station"),
    ("roborock.vacuum.a104", "Qrevo S", "wash_station"),
    ("roborock.vacuum.a101", "Qrevo Pro", "wash_station"),
    ("roborock.vacuum.a87", "Qrevo MaxV", "wash_station"),
    ("roborock.vacuum.a143", "G20S Ultra", "wash_station"),
    # -- dual_pad: wash station + twin spinning mop pads (roller mops) ------
    ("roborock.vacuum.a97", "S8 MaxV Ultra", "dual_pad"),
    ("roborock.vacuum.a135", "Qrevo Curv", "dual_pad"),
    ("roborock.vacuum.a117", "Qrevo Master", "dual_pad"),
    ("roborock.vacuum.a144", "Saros 10R", "dual_pad"),
    ("roborock.vacuum.a147", "Saros 10", "dual_pad"),
]

ROBOROCK_MODEL_NAMES: dict[str, str] = {code: name for code, name, _ in ROBOROCK_MODELS}

# A model resolves to its tier only if that tier is AUTHORED; otherwise it falls
# back to `standard` (still correct — every model has the base components). So
# authoring a new tier in the guide library auto-activates it for its models with
# no edit here.
_AUTHORED_FAMILIES = set(ROBOROCK_UPKEEP_GUIDE_LIBRARY)  # today: {"standard"}
ROBOROCK_MODEL_GUIDE_FAMILIES: dict[str, str] = {
    code: (tier if tier in _AUTHORED_FAMILIES else "standard")
    for code, _, tier in ROBOROCK_MODELS
}

ROBOROCK_GUIDE_FAMILY_NAMES: dict[str, str] = {
    "standard": "Roborock",
    "auto_empty": "Roborock (auto-empty dock)",
    "wash_station": "Roborock (wash & dry station)",
    "dual_pad": "Roborock (twin-pad station)",
    "generic": "Roborock",
}
