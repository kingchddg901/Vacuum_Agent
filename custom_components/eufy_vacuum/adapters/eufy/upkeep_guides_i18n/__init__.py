"""Localized upkeep guides — one module per language.

``UPKEEP_GUIDE_TRANSLATIONS[lang][guide_family][component]`` mirrors a subset of
``UPKEEP_GUIDE_LIBRARY`` (../upkeep_guides.py) with translated steps / notes /
frequencies. Each language lives in its OWN module (de.py, he.py, zh_hans.py, …)
so a native reviewer edits just their language without scrolling past every other.

The maintenance manager overlays these on the English base PER FIELD, so any
component or field a locale omits falls back to English. Selected by the card's
resolved language (frontend) / hass.config.language (backend). Pure data.

Edit a ``<lang>.py``, then run ``python scripts/sync-guide-translations.py``.
"""
from . import de, es, fr, nl, it, pt, ru, ar, he, ja, zh_hans, zh_hant, ko  # noqa: F401

UPKEEP_GUIDE_TRANSLATIONS = {
    "de": de.GUIDE_TRANSLATIONS,
    "es": es.GUIDE_TRANSLATIONS,
    "fr": fr.GUIDE_TRANSLATIONS,
    "nl": nl.GUIDE_TRANSLATIONS,
    "it": it.GUIDE_TRANSLATIONS,
    "pt": pt.GUIDE_TRANSLATIONS,
    "ru": ru.GUIDE_TRANSLATIONS,
    "ar": ar.GUIDE_TRANSLATIONS,
    "he": he.GUIDE_TRANSLATIONS,
    "ja": ja.GUIDE_TRANSLATIONS,
    "zh-Hans": zh_hans.GUIDE_TRANSLATIONS,
    "zh-Hant": zh_hant.GUIDE_TRANSLATIONS,
    "ko": ko.GUIDE_TRANSLATIONS,
}
