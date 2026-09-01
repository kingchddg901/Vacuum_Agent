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
sys.path.insert(0, os.path.join(ADAPTERS, "dreame"))

import eufy_upkeep_guides as base          # noqa: E402
import roborock_upkeep_guides as rr_base   # noqa: E402
import dreame_upkeep_guides as dr_base     # noqa: E402


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
dr_i18n = _load_pkg(os.path.join(ADAPTERS, "dreame", "upkeep_guides_i18n"), "dreame_upkeep_guides_i18n")

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

# Dreame is added AFTER, COLLISION-SAFE. Its generic tier families (standard / auto_empty
# / wash_station / wash_station_track / _roller / _baseboard) share KEYS with Roborock's
# but hold DIFFERENT prose (measured off different manuals), and the card looks a family
# up by its bare key with no brand qualifier (renderers/maintenance.js). Overwriting would
# silently swap Roborock's tier guide for Dreame's. So Dreame only CLAIMS keys no earlier
# brand used: its uniquely-named authored families (matrix10, l60_ultra, x50, l10s_gen2,
# aqua10_ultra_*, …) localize on the card, while its bare-tier-family models fall back to
# English until the keys are brand-namespaced (the proper fix — a cross-brand card change,
# deferred). Skipped keys are reported below.
_claimed = set(merged["en"])
dreame_skipped = sorted(set(dr_base.DREAME_UPKEEP_GUIDE_LIBRARY) & _claimed)
for family, comps in dr_base.DREAME_UPKEEP_GUIDE_LIBRARY.items():
    if family in _claimed:
        continue
    merged["en"][family] = {
        comp: {k: g[k] for k in FIELDS if k in g} for comp, g in comps.items()
    }

# Official manual translations on top. Eufy + Roborock first (disjoint keys), then Dreame
# with the same collision-skip so it never overwrites a family an earlier brand claimed.
for src in (i18n.UPKEEP_GUIDE_TRANSLATIONS, rr_i18n.ROBOROCK_UPKEEP_GUIDE_TRANSLATIONS):
    for lang, fams in src.items():
        merged.setdefault(lang, {}).update(json.loads(json.dumps(fams)))  # deep copy
for lang, fams in dr_i18n.DREAME_UPKEEP_GUIDE_TRANSLATIONS.items():
    dest = merged.setdefault(lang, {})
    for family, comps in json.loads(json.dumps(fams)).items():
        if family not in _claimed:
            dest[family] = comps

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
if dreame_skipped:
    print(f"Dreame families NOT localized on the card (key shared with an earlier brand; "
          f"fall back to English until brand-namespaced): {dreame_skipped}")
