"""
Eufy device model catalog for capability detection.

Maps upstream device registry model codes and name hint substrings to
internal family names used by detect_capabilities() to set capability
flags.

MODEL_CODE_FAMILIES — exact product code → family name.
    Keyed by the raw string from the vacuum's device registry
    model attribute (e.g. "T2351"). Unrecognised codes fall back
    to MODEL_FAMILY_HINTS, then to "generic".

MODEL_FAMILY_HINTS — substring hint → family name.
    Matched case-insensitively against the full model string when
    the exact code is not in MODEL_CODE_FAMILIES.

A port to a different brand replaces this file with its own model
catalog. A brand whose HA integration does not expose a model code
returns "generic" for all vacuums — capability detection then relies
entirely on entity presence rather than model family.
"""

from __future__ import annotations


def detect_model_family(detected_model: str | None) -> str:
    """Infer Eufy model family from a detected model string.

    Returns one of the known family names (e.g. 'x10', 'x8', 'l60') or
    'generic' when the model is unrecognised or absent. Used by the Eufy
    adapter to build capability_hints before calling detect_capabilities().
    """
    raw = str(detected_model or "").strip()
    if raw in MODEL_CODE_FAMILIES:
        return MODEL_CODE_FAMILIES[raw]
    text = raw.lower()
    for needle, family in MODEL_FAMILY_HINTS.items():
        if needle in text:
            return family
    return "generic"


MODEL_FAMILY_HINTS: dict[str, str] = {
    "x10": "x10",
    "x8": "x8",
    "l60": "l60",
    "l50": "l50",
    "g50": "g50",
    "g40": "g40",
    "lr30": "lr30",
}

MODEL_CODE_FAMILIES: dict[str, str] = {
    "T2351": "x10",
    "T2320": "x10",
    "T2261": "x8",
    "T2262": "x8",
    "T2266": "x8",
    "T2276": "x8",
    "T2267": "l60",
    "T2268": "l60",
    "T2277": "l60",
    "T2278": "l60",
    "T2280": "c20",
    "T2080": "s1",
    "T2071": "s1",
    "T2210": "g50",
    "T2255": "g40",
    "T2256": "g40",
    "T2192": "lr30",
    "T2193": "lr30",
    "T2181": "lr30",
    "T2194": "lr30",
    "T2182": "lr30",
}
