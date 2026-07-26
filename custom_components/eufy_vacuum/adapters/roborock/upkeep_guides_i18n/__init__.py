"""Roborock localized upkeep guides — one module per language.

``ROBOROCK_UPKEEP_GUIDE_TRANSLATIONS[lang][guide_family][component]`` — steps /
notes / frequencies TRANSCRIBED from Roborock's official per-language manuals (not
AI-translated: Roborock already did the translating, so this is read-and-copy).
The maintenance manager overlays these on the English guide PER FIELD, so any
language/family/component/field not present here falls back to English.

Each language lives in its OWN module (de.py, zh_hans.py, … — hyphens→underscores
in the module name) so it can be filled/reviewed in isolation. Frequencies are set
to match the English base so the interval reads the same in every language. Pure
data. Assembled into the adapter's ``upkeep_catalog.guide_translations``.

Transcribed from official manuals: de/es/fr/it/nl/pt (CE), zh-Hans (CN CDN),
zh-Hant (TW), ru (S6 MaxV), ja (S5 Max — base only, rest fall back to English).
ar/he are AI-DRAFTS (no official manual; manuals.plus inaccessible) — flagged in
their modules, consistent with the card's ar/he draft locales.
"""
from . import ar, de, es, fr, he, it, ja, ko, nl, pt, ru, zh_hans, zh_hant  # noqa: F401

ROBOROCK_UPKEEP_GUIDE_TRANSLATIONS = {
    "de": de.GUIDE_TRANSLATIONS,
    "es": es.GUIDE_TRANSLATIONS,
    "fr": fr.GUIDE_TRANSLATIONS,
    "it": it.GUIDE_TRANSLATIONS,
    "nl": nl.GUIDE_TRANSLATIONS,
    "pt": pt.GUIDE_TRANSLATIONS,
    "ru": ru.GUIDE_TRANSLATIONS,
    "ja": ja.GUIDE_TRANSLATIONS,
    "ko": ko.GUIDE_TRANSLATIONS,
    "zh-Hans": zh_hans.GUIDE_TRANSLATIONS,
    "zh-Hant": zh_hant.GUIDE_TRANSLATIONS,
    "ar": ar.GUIDE_TRANSLATIONS,
    "he": he.GUIDE_TRANSLATIONS,
}
