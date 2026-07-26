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

PROOF-of-pipeline set today: de, zh-Hans (base family). The remaining official
languages (es/fr/it/nl/pt from the CE manuals; ru/ja/ko/zh-Hant from regional
editions) are the same read-and-copy, added as modules here.
"""
from . import de, zh_hans  # noqa: F401

ROBOROCK_UPKEEP_GUIDE_TRANSLATIONS = {
    "de": de.GUIDE_TRANSLATIONS,
    "zh-Hans": zh_hans.GUIDE_TRANSLATIONS,
}
