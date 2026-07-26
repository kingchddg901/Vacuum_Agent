#!/usr/bin/env python3
"""
Regenerate src/i18n/guide-translations.js from the integration's guide data.

The maintenance guide (steps / notes / clean & replace frequency) is rendered
on the CARD in the user's per-user language (the globe), not the HA instance
language. To do that the card needs the guide content client-side, so we port
it here from the same Python source of truth (BOTH brands — families are
namespaced by key, so Eufy's x10_pro_omni… and Roborock's s6/s7/s8 coexist):

  - English base:           adapters/eufy/eufy_upkeep_guides.py       (UPKEEP_GUIDE_LIBRARY)
                            adapters/roborock/roborock_upkeep_guides.py (ROBOROCK_UPKEEP_GUIDE_LIBRARY)
  - translations:           adapters/eufy/upkeep_guides_i18n/    (one <lang>.py per
                            language; __init__.py assembles UPKEEP_GUIDE_TRANSLATIONS)
                            (Roborock translations are Phase 2 — English base for now)
  - frequency gap-fills:    scripts/data/guide-frequency-translations.json
                            (the unique frequency phrases, machine-translated; the
                            official manuals only stated some frequencies)

Steps/notes are NOT back-filled for the model families the manuals never
covered — those fall back to English in the card overlay (pre-existing behaviour).

Run from the repo root:  python scripts/sync-guide-translations.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADAPTERS = os.path.join(ROOT, "custom_components", "eufy_vacuum", "adapters")
# Both adapter dirs on the path. The guide libraries are BRAND-PREFIXED
# (eufy_upkeep_guides / roborock_upkeep_guides), so they never collide, and each
# is pure data (no cross-adapter imports) — bare imports are safe.
sys.path.insert(0, os.path.join(ADAPTERS, "eufy"))
sys.path.insert(0, os.path.join(ADAPTERS, "roborock"))

import eufy_upkeep_guides as base          # noqa: E402
import roborock_upkeep_guides as rr_base   # noqa: E402
import upkeep_guides_i18n as i18n          # noqa: E402  (Eufy translations; Roborock's are Phase 2)

FIELDS = ("steps", "notes", "clean_frequency", "replace_frequency")
LANGS = ("de", "fr", "es", "it", "nl", "pt", "ru", "ar", "he", "ja", "zh-Hans", "zh-Hant", "ko")

# English base, trimmed to the localizable fields. Both brands' libraries are
# namespaced by guide family (Eufy: x10_pro_omni…; Roborock: s6/s7/s8), so they
# coexist in one `en` map — the card picks the family for the active vacuum.
merged = {"en": {}}
for library in (base.UPKEEP_GUIDE_LIBRARY, rr_base.ROBOROCK_UPKEEP_GUIDE_LIBRARY):
    for family, comps in library.items():
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
    " * Source: adapters/{eufy/eufy,roborock/roborock}_upkeep_guides.py + eufy/upkeep_guides_i18n/<lang>.py + scripts/data/guide-frequency-translations.json\n"
    " * Shape: GUIDE_TRANSLATIONS[lang][family][component] = { steps[], notes[], clean_frequency, replace_frequency }\n"
    " */\n"
)
out_path = os.path.join(ROOT, "src", "i18n", "guide-translations.js")
with open(out_path, "w", encoding="utf-8") as fh:
    fh.write(header + "export const GUIDE_TRANSLATIONS = " + data + ";\n")

print(f"wrote {out_path} ({len(data)} bytes data, {filled} frequency gaps filled)")
