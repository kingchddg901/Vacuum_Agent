"""Tests for the localized upkeep guides (adapters/eufy/upkeep_guides_i18n.py).

Pure data — no HA. The maintenance manager overlays these on the English base
per field (selected by HA instance language); these tests guard the data the
overlay consumes.

[GI-1] All expected languages present; each maps the x10_pro_omni family.
[GI-2] Translated components are a SUBSET of the English base (no orphan keys);
       every entry has non-empty steps that actually differ from English.
[GI-3] The four formerly-missing gaps are now translated in every language:
       mopping_cloth + swivel_wheel components, and the rolling_brush /
       cleaning_tray notes (brush-guard / dirty-water-tank).
[GI-4] frequency values, when present, are strings (not accidentally objects).
"""

from custom_components.eufy_vacuum.adapters.eufy.upkeep_guides import UPKEEP_GUIDE_LIBRARY
from custom_components.eufy_vacuum.adapters.eufy.upkeep_guides_i18n import (
    UPKEEP_GUIDE_TRANSLATIONS,
)

FAMILY = "x10_pro_omni"
LANGS = {"de", "es", "fr", "nl", "it", "pt", "ru"}


def test_languages_present():
    """[GI-1]"""
    assert set(UPKEEP_GUIDE_TRANSLATIONS) == LANGS
    for lang in LANGS:
        assert FAMILY in UPKEEP_GUIDE_TRANSLATIONS[lang]


def test_components_subset_and_translated():
    """[GI-2] every translated component exists in English and differs from it."""
    en = UPKEEP_GUIDE_LIBRARY[FAMILY]
    en_comps = set(en)
    for lang in LANGS:
        fam = UPKEEP_GUIDE_TRANSLATIONS[lang][FAMILY]
        assert set(fam) <= en_comps, f"{lang}: orphan component(s) {set(fam) - en_comps}"
        assert fam, f"{lang}: no components"
        for comp, entry in fam.items():
            assert entry.get("steps"), f"{lang}/{comp}: empty steps"
            assert entry["steps"] != en[comp]["steps"], f"{lang}/{comp}: identical to English"


def test_gap_components_now_translated():
    """[GI-3] The four formerly-missing gaps are filled in EVERY language, so a
    localized maintenance card no longer drops to English there: mopping_cloth +
    swivel_wheel components have steps, and rolling_brush (brush-guard note) +
    cleaning_tray (dirty-water-tank note) carry non-empty notes."""
    for lang in LANGS:
        fam = UPKEEP_GUIDE_TRANSLATIONS[lang][FAMILY]
        assert fam.get("mopping_cloth", {}).get("steps"), f"{lang}: mopping_cloth missing/empty"
        assert fam.get("swivel_wheel", {}).get("steps"), f"{lang}: swivel_wheel missing/empty"
        assert fam["rolling_brush"].get("notes"), f"{lang}: rolling_brush note missing"
        assert fam["cleaning_tray"].get("notes"), f"{lang}: cleaning_tray note missing"


def test_frequency_fields_are_strings_or_absent():
    """[GI-4]"""
    for lang in LANGS:
        for entry in UPKEEP_GUIDE_TRANSLATIONS[lang][FAMILY].values():
            for key in ("clean_frequency", "replace_frequency"):
                val = entry.get(key)
                assert val is None or isinstance(val, str), f"{lang}: {key} not str/None"
            assert isinstance(entry.get("notes", []), list)
