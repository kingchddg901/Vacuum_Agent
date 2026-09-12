#!/usr/bin/env python3
"""
Regenerate src/i18n/guide-translations.js from the integration's guide data.

The maintenance guide (steps / notes / clean & replace frequency) is rendered
on the CARD in the user's per-user language (the globe), not the HA instance
language. To do that the card needs the guide content client-side, so we port
it here from the same Python source of truth (Eufy + Roborock — families are
namespaced by key, so Eufy's x10_pro_omni… and Roborock's s6/s7/s8 coexist).

DREAME IS NOT HERE, and its absence is the design. Dreame guides are i18n KEYS routed by
regime (adapters/dreame/upkeep_keys.py); the backend ships no Dreame words in any
language, so there is nothing for this script to port. Its packs are built by
scripts/sync-dreame-guide-keys.py into src/i18n/guide-keys.js + frontend/guides/keys/.
⭐ That also RETIRED the cross-brand family-key collision this script used to work around:
Dreame's generic tiers shared bare keys (standard / auto_empty / wash_station…) with
Roborock's while holding different prose, and the card looks a family up with no brand
qualifier. The workaround was to skip Dreame on collision, which left those models
English-only. There is no collision left to skip.

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
import importlib.util
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
# ⚠ THE LESSON FROM THE DREAME HALF, KEPT because it is about THIS script, not about Dreame.
# Loading that adapter's guides needed two import tricks (a synthetic parent package for its
# relative imports, and a subpackage for an i18n __init__ that reached UP one level). Neither
# was in place, so this regenerator RAISED before writing anything — and a stale
# src/i18n/guide-translations.js full of families whose Python source had been deleted kept
# shipping for weeks. A tool that cannot start fails silently in exactly this shape: nothing
# is wrong with the output, because there is no output. If this script grows a third brand,
# run it and read the byte counts; do not assume it ran.


def _load_pkg(pkg_dir, modname):
    """Load an i18n PACKAGE by explicit path under a unique name. Both brands' dirs
    are on sys.path and share the basename ``upkeep_guides_i18n``, so a bare import
    would collide; this resolves each package's relative submodule imports via its
    own search location."""
    init = os.path.join(pkg_dir, "__init__.py")
    spec = importlib.util.spec_from_file_location(modname, init, submodule_search_locations=[pkg_dir])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


i18n = _load_pkg(os.path.join(ADAPTERS, "eufy", "upkeep_guides_i18n"), "eufy_upkeep_guides_i18n")
rr_i18n = _load_pkg(os.path.join(ADAPTERS, "roborock", "upkeep_guides_i18n"), "roborock_upkeep_guides_i18n")

FIELDS = ("steps", "notes", "clean_frequency", "replace_frequency")
LANGS = ("de", "fr", "es", "it", "nl", "pt", "ru", "ar", "he", "ja", "zh-Hans", "zh-Hant", "ko")

# English base, trimmed to the localizable fields. Eufy (x10_pro_omni…) and Roborock
# (standard/auto_empty/wash_station) use disjoint family keys, so they coexist in one
# `en` map — the card picks the family for the active vacuum.
merged = {"en": {}}
for library in (base.UPKEEP_GUIDE_LIBRARY, rr_base.ROBOROCK_UPKEEP_GUIDE_LIBRARY):
    for family, comps in library.items():
        merged["en"][family] = {
            comp: {k: g[k] for k in FIELDS if k in g} for comp, g in comps.items()
        }

# Official manual translations on top. Eufy + Roborock keys are disjoint, so a plain
# update is safe — there is no brand qualifier in the family key and nothing to collide with
# now that Dreame no longer routes by family.
for src in (i18n.UPKEEP_GUIDE_TRANSLATIONS, rr_i18n.ROBOROCK_UPKEEP_GUIDE_TRANSLATIONS):
    for lang, fams in src.items():
        merged.setdefault(lang, {}).update(json.loads(json.dumps(fams)))  # deep copy

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

# =====================================================================
# EMIT the import-loader layout (mirrors the UI-locale debundle: bundle `en`,
# serve the rest lazily):
#   (1) src/i18n/guide-translations.js — EN ONLY, the always-bundled base +
#       universal fallback (must be sync-available; see renderers/maintenance.js
#       _localizedGuide, which always needs the en value even on a miss).
#   (2) custom_components/eufy_vacuum/frontend/guides/<lang>.json — one served
#       file per non-en language, fetched on demand by the guide loader.
#   (3) guides/index.json — the discovery list (like locales/index.json).
# The split is a pure partition-by-language of `merged`; the self-check below
# reconstructs it byte-for-byte — the data-level no-op the whole cutover rests on.
# =====================================================================
def _canon(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


full_bytes = len(json.dumps(merged, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
en_bundle = {"en": merged["en"]}
en_data = json.dumps(en_bundle, ensure_ascii=False, separators=(",", ":"))
header = (
    "/**\n"
    " * GUIDE TRANSLATIONS — the ENGLISH BASE for upkeep guide content (steps /\n"
    " * notes / frequencies). English is BUNDLED (always sync-available as the\n"
    " * universal fallback); every other language is SERVED and lazy-loaded from\n"
    " * custom_components/eufy_vacuum/frontend/guides/<lang>.json by the guide\n"
    " * loader (src/i18n/guide-loader.js) — the same bundle-en / serve-the-rest\n"
    " * split the UI locales use.\n"
    " * GENERATED — do not hand-edit. Run: python scripts/sync-guide-translations.py\n"
    " * Source: adapters/{eufy,roborock,dreame}/<brand>_upkeep_guides.py + <brand>/upkeep_guides_i18n/<lang>.py + scripts/data/guide-frequency-translations.json\n"
    " * Shape: GUIDE_TRANSLATIONS[lang][family][component] = { steps[], notes[], clean_frequency, replace_frequency }\n"
    " */\n"
)
out_path = os.path.join(ROOT, "src", "i18n", "guide-translations.js")
with open(out_path, "w", encoding="utf-8") as fh:
    fh.write(header + "export const GUIDE_TRANSLATIONS = " + en_data + ";\n")

# --- served per-language files + discovery index (the lazy-loaded layout) ---
guides_dir = os.path.join(ROOT, "custom_components", "eufy_vacuum", "frontend", "guides")
os.makedirs(guides_dir, exist_ok=True)
# Remove any stale served file for a language no longer present, so a dropped
# language cannot linger and be served after the source stops emitting it.
_current = {f"{lang}.json" for lang in merged if lang != "en"} | {"index.json"}
for existing in os.listdir(guides_dir):
    if existing.endswith(".json") and existing not in _current:
        os.remove(os.path.join(guides_dir, existing))

langs = sorted(k for k in merged if k != "en")
index, served_bytes = [], 0
for lang in langs:
    payload = json.dumps(merged[lang], ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(guides_dir, f"{lang}.json"), "w", encoding="utf-8") as fh:
        fh.write(payload)
    served_bytes += len(payload.encode("utf-8"))
    index.append(f"{lang}.json")
with open(os.path.join(guides_dir, "index.json"), "w", encoding="utf-8") as fh:
    json.dump(index, fh, ensure_ascii=False)

# --- self-verify the split is a faithful no-op: en (bundled) + served == merged ---
recon = {"en": merged["en"]}
for lang in langs:
    with open(os.path.join(guides_dir, f"{lang}.json"), encoding="utf-8") as fh:
        recon[lang] = json.load(fh)
if _canon(recon) != _canon(merged):
    raise SystemExit("FATAL: guides/ split is NOT a no-op — reconstruct != merged source")

en_bytes = len(en_data.encode("utf-8"))
print(f"wrote {out_path} (EN-only base, {en_bytes} bytes, {filled} frequency gaps filled)")
print(f"wrote {len(langs)} served guide files + index.json to {guides_dir}")
print(f"  languages served: {', '.join(langs)}")
print(f"  no-op self-check: en + served reconstructs merged  OK")
print(f"  bundle: {full_bytes} -> {en_bytes} bytes "
      f"({100 * (1 - en_bytes / full_bytes):.0f}% smaller); {served_bytes} bytes now lazy-loaded")
