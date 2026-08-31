"""Tests for the localized Dreame upkeep guides (adapters/dreame/upkeep_guides_i18n/).

Pure data — no HA. The maintenance manager (and the card's per-user-language overlay)
consume these; these tests guard the shape the overlay depends on. Unlike the Eufy/
Roborock packs (transcribed from official per-language manuals, so they cover only some
families), the Dreame packs are AI-translated from the English base and assembled to FULL
parity — every family, every component, every language. So these assertions are strict
equality, not subset: a pack that drops a family, renames a component, loses a step, or
silently falls back to English is caught here, not in a card render.

[DI18N-1] All 17 locales present; each maps EVERY family the English library defines.
[DI18N-2] Per language/family the component set EQUALS English (no orphans, none missing).
[DI18N-3] steps/notes counts match English exactly — a dropped or duplicated line is red.
[DI18N-4] No translated step line is byte-identical to English — an untranslated fallback
          (the failure the AI batch exists to prevent) would show up as English text here.
[DI18N-5] Frequency fields are str or None; notes are always a list.
"""

from custom_components.eufy_vacuum.adapters.dreame import (
    DREAME_UPKEEP_GUIDE_LIBRARY,
    DREAME_UPKEEP_GUIDE_TRANSLATIONS,
)

# Every locale that overlays Dreame guide translations — the card's 17 non-English
# locales. AI-translated 2026-08-31 from the English base (an initial draft; refine a
# <lang>.py in place if a Dreame manual's own wording is preferred). Update this set when
# a locale is added or removed.
LANGS = {
    "de", "es", "fr", "nl", "it", "pt", "pl", "cs", "tr", "id", "ru",
    "ar", "he", "ja", "zh-Hans", "zh-Hant", "ko",
}


def test_languages_and_families_present():
    """[DI18N-1] all locales present; each carries every English family."""
    assert set(DREAME_UPKEEP_GUIDE_TRANSLATIONS) == LANGS
    en_families = set(DREAME_UPKEEP_GUIDE_LIBRARY)
    for lang in LANGS:
        assert set(DREAME_UPKEEP_GUIDE_TRANSLATIONS[lang]) == en_families, (
            f"{lang}: families differ from English "
            f"{set(DREAME_UPKEEP_GUIDE_TRANSLATIONS[lang]) ^ en_families}"
        )


def test_components_match_english_exactly():
    """[DI18N-2] per family the localized component set equals the English one."""
    for lang in LANGS:
        for family, en_comps in DREAME_UPKEEP_GUIDE_LIBRARY.items():
            tr = DREAME_UPKEEP_GUIDE_TRANSLATIONS[lang][family]
            assert set(tr) == set(en_comps), (
                f"{lang}/{family}: components differ {set(tr) ^ set(en_comps)}"
            )


def test_step_and_note_counts_match_english():
    """[DI18N-3] a dropped/duplicated step or note is caught by the count parity."""
    for lang in LANGS:
        for family, comps in DREAME_UPKEEP_GUIDE_LIBRARY.items():
            for comp, en in comps.items():
                tr = DREAME_UPKEEP_GUIDE_TRANSLATIONS[lang][family][comp]
                assert len(tr.get("steps", [])) == len(en.get("steps", [])), (
                    f"{lang}/{family}/{comp}: step count != English"
                )
                assert len(tr.get("notes", [])) == len(en.get("notes", [])), (
                    f"{lang}/{family}/{comp}: note count != English"
                )


def test_no_step_is_untranslated_english():
    """[DI18N-4] every step is actually localized — none left as the English source.

    An English-identical step is the signature of a translation that fell back to the
    base (a gap the assembler is supposed to fill from the AI batch). Frequencies and the
    occasional symbol-only fragment can legitimately coincide, so this checks STEPS only,
    which are full sentences that never coincide across languages when truly translated.
    """
    for lang in LANGS:
        for family, comps in DREAME_UPKEEP_GUIDE_LIBRARY.items():
            for comp, en in comps.items():
                en_steps = en.get("steps", [])
                tr_steps = DREAME_UPKEEP_GUIDE_TRANSLATIONS[lang][family][comp].get("steps", [])
                for i, (a, b) in enumerate(zip(en_steps, tr_steps)):
                    assert a != b, f"{lang}/{family}/{comp} step {i} is untranslated English: {a!r}"


def test_field_types():
    """[DI18N-5] frequency fields are str/None; notes are a list."""
    for lang in LANGS:
        for family in DREAME_UPKEEP_GUIDE_LIBRARY:
            for entry in DREAME_UPKEEP_GUIDE_TRANSLATIONS[lang][family].values():
                for key in ("clean_frequency", "replace_frequency"):
                    val = entry.get(key)
                    assert val is None or isinstance(val, str), f"{lang}: {key} not str/None"
                assert isinstance(entry.get("notes", []), list)
