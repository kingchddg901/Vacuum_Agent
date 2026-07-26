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

EU set (de/es/fr/it/nl/pt) + zh-Hans transcribed from the official CE + CN
manuals. Remaining official languages (ru/ja/ko/zh-Hant from regional editions;
ar/he under the agree-in-principle check) are the same read-and-copy, added here.
"""
from . import de, es, fr, it, nl, pt, zh_hans  # noqa: F401

ROBOROCK_UPKEEP_GUIDE_TRANSLATIONS = {
    "de": de.GUIDE_TRANSLATIONS,
    "es": es.GUIDE_TRANSLATIONS,
    "fr": fr.GUIDE_TRANSLATIONS,
    "it": it.GUIDE_TRANSLATIONS,
    "nl": nl.GUIDE_TRANSLATIONS,
    "pt": pt.GUIDE_TRANSLATIONS,
    "zh-Hans": zh_hans.GUIDE_TRANSLATIONS,
}
