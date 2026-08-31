"""Dreame localized upkeep guides - one module per language (AI-translated drafts).

DREAME_UPKEEP_GUIDE_TRANSLATIONS[lang][guide_family][component] - steps / notes /
frequencies. The maintenance manager overlays these on the English guide PER FIELD,
so any language/family/component/field absent here falls back to English.

Initial AI-translation of the English guide base (2026-08-31); not transcribed from
official per-language manuals. Edit a <lang>.py in place to refine. Pure data.
"""
from . import ar, cs, de, es, fr, he, id, it, ja, ko, nl, pl, pt, ru, tr, zh_hans, zh_hant  # noqa: F401  (`id` = Indonesian; shadows builtin, harmless in pure-data module)

DREAME_UPKEEP_GUIDE_TRANSLATIONS = {
    'ar': ar.GUIDE_TRANSLATIONS,
    'cs': cs.GUIDE_TRANSLATIONS,
    'de': de.GUIDE_TRANSLATIONS,
    'es': es.GUIDE_TRANSLATIONS,
    'fr': fr.GUIDE_TRANSLATIONS,
    'he': he.GUIDE_TRANSLATIONS,
    'id': id.GUIDE_TRANSLATIONS,
    'it': it.GUIDE_TRANSLATIONS,
    'ja': ja.GUIDE_TRANSLATIONS,
    'ko': ko.GUIDE_TRANSLATIONS,
    'nl': nl.GUIDE_TRANSLATIONS,
    'pl': pl.GUIDE_TRANSLATIONS,
    'pt': pt.GUIDE_TRANSLATIONS,
    'ru': ru.GUIDE_TRANSLATIONS,
    'tr': tr.GUIDE_TRANSLATIONS,
    'zh-Hans': zh_hans.GUIDE_TRANSLATIONS,
    'zh-Hant': zh_hant.GUIDE_TRANSLATIONS,
}
