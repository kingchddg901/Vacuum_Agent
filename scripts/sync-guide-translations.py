#!/usr/bin/env python3
"""
Regenerate src/i18n/guide-translations.js from the integration's guide data.

The maintenance guide (steps / notes / clean & replace frequency) is rendered
on the CARD in the user's per-user language (the globe), not the HA instance
language. To do that the card needs the guide content client-side, so we port
it here from the same Python source of truth:

  - English base:           adapters/eufy/upkeep_guides.py      (UPKEEP_GUIDE_LIBRARY)
  - official translations:  adapters/eufy/upkeep_guides_i18n.py (UPKEEP_GUIDE_TRANSLATIONS)
  - frequency gap-fills:    scripts/data/guide-frequency-translations.json
                            (the unique frequency phrases, machine-translated; the
                            official manuals only stated some frequencies)

Steps/notes are NOT back-filled for the model families the manuals never
covered (only x10_pro_omni has full translations) — those fall back to English
in the card overlay, which is the pre-existing behaviour.

Run from the repo root:  python scripts/sync-guide-translations.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "custom_components", "eufy_vacuum", "adapters", "eufy"))

import upkeep_guides as base          # noqa: E402
import upkeep_guides_i18n as i18n     # noqa: E402

FIELDS = ("steps", "notes", "clean_frequency", "replace_frequency")
LANGS = ("de", "fr", "es", "it", "nl", "pt", "ru")

# English base, trimmed to the localizable fields.
merged = {"en": {}}
for family, comps in base.UPKEEP_GUIDE_LIBRARY.items():
    merged["en"][family] = {
        comp: {k: g[k] for k in FIELDS if k in g} for comp, g in comps.items()
    }

# Official manual translations on top.
for lang, fams in i18n.UPKEEP_GUIDE_TRANSLATIONS.items():
    merged[lang] = json.loads(json.dumps(fams))  # deep copy

# Back-fill frequency gaps from the machine-translated unique phrases.
with open(os.path.join(ROOT, "scripts", "data", "guide-frequency-translations.json"), encoding="utf-8") as fh:
    freq_map = json.load(fh)

filled = 0
for lang in LANGS:
    for family, comps in merged["en"].items():
        for comp, g in comps.items():
            for field in ("clean_frequency", "replace_frequency"):
                en_val = g.get(field)
                if not en_val:
                    continue
                node = merged.setdefault(lang, {}).setdefault(family, {}).setdefault(comp, {})
                if node.get(field):
                    continue  # keep the official manual value
                tr = freq_map.get(lang, {}).get(en_val)
                if tr:
                    node[field] = tr
                    filled += 1

data = json.dumps(merged, ensure_ascii=False, separators=(",", ":"))
header = (
    "/**\n"
    " * GUIDE TRANSLATIONS — per-language upkeep guide content (steps / notes /\n"
    " * frequencies), so the maintenance guide follows the CARD per-user language\n"
    " * (the globe), not the HA instance language.\n"
    " * GENERATED — do not hand-edit. Run: python scripts/sync-guide-translations.py\n"
    " * Source: adapters/eufy/upkeep_guides{,_i18n}.py + scripts/data/guide-frequency-translations.json\n"
    " * Shape: GUIDE_TRANSLATIONS[lang][family][component] = { steps[], notes[], clean_frequency, replace_frequency }\n"
    " */\n"
)
out_path = os.path.join(ROOT, "src", "i18n", "guide-translations.js")
with open(out_path, "w", encoding="utf-8") as fh:
    fh.write(header + "export const GUIDE_TRANSLATIONS = " + data + ";\n")

print(f"wrote {out_path} ({len(data)} bytes data, {filled} frequency gaps filled)")
