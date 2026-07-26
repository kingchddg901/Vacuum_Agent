"""Roborock upkeep catalog — the model/family metadata half of ``upkeep_catalog``.

Mirrors adapters/eufy/upkeep_catalog.py. Three maps the maintenance manager reads
(via the adapter's ``upkeep_catalog`` config block) to pick the right guide for a
device:

- ``ROBOROCK_MODEL_NAMES``          device.model -> human display name
- ``ROBOROCK_MODEL_GUIDE_FAMILIES`` device.model -> guide family key
- ``ROBOROCK_GUIDE_FAMILY_NAMES``   guide family key -> display name (shown as the
                                    guide's "for the …" heading)

The first two are DERIVED from model_catalog.MODEL_PROFILES, so adding a model
there (Chris's "add more later from Roborock support") automatically wires its
guide family — no edit here. An unknown device.model resolves to no family (guide
simply absent) until it is catalogued.
"""

from __future__ import annotations

from .model_catalog import MODEL_PROFILES

# device.model -> display name / guide family, straight off the capability catalog.
ROBOROCK_MODEL_NAMES: dict[str, str] = {
    model: profile["display_name"] for model, profile in MODEL_PROFILES.items()
}

ROBOROCK_MODEL_GUIDE_FAMILIES: dict[str, str] = {
    model: profile["family"] for model, profile in MODEL_PROFILES.items()
}

# guide family key -> the name shown on the guide. Kept explicit (not derived) so
# a family can span several models under one friendly label.
ROBOROCK_GUIDE_FAMILY_NAMES: dict[str, str] = {
    "s6": "Roborock S6",
    "s7": "Roborock S7",
    "s8": "Roborock S8",
    "generic": "Roborock",
}
