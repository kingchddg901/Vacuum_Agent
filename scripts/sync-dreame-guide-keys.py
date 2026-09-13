#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ship the Dreame guide KEY PACKS into the card.

The Dreame guide is 51 i18n KEYS, not per-family prose (see
adapters/dreame/upkeep_keys.py). The card resolves those keys in the USER's language — the globe,
not the HA instance language — so the packs have to live client-side, exactly like the existing
family-based guide catalogs.

Same bundle-en / serve-the-rest split as `sync-guide-translations.py` and the UI locales:

    src/i18n/guide-keys.js                          ENGLISH, bundled — the universal fallback.
                                                    `_localizedGuide` needs a sync English value
                                                    on every miss, so it can never be fetched.
    frontend/guides/keys/<lang>.json                the other 17, served + lazy-loaded once.
    frontend/guides/keys/index.json                 what exists, for the loader.

Locale spelling follows the EXISTING served catalogs: `zh-Hans` / `zh-Hant` on disk, because the
loader builds `${baseUrl}/${code}.json` from the card's resolved language. The authoring packs
spell them `zh_hans` / `zh_hant`; the map below is the only place that seam is crossed.

SOURCE: durable/dreame-port-fixture/resources/key-authoring/keys_<lang>.json — OUTSIDE git. That
is the authoring home, with the manuals and the provenance. This script can therefore only be run
on a machine that has the fixture; its OUTPUT is what ships and what is committed.

GATE, and it can go red: every key `upkeep_keys.DREAME_UPKEEP_KEYS` can emit must be present in
EVERY pack. A key emitted and not authored renders as its own name on the card — that is the
designed fallback and it cannot be silent, but it must never happen.

Run from the repo root:  python scripts/sync-dreame-guide-keys.py
"""
import importlib.util
import io
import json
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(os.path.dirname(os.path.dirname(ROOT)),
                       "durable", "dreame-port-fixture", "resources", "key-authoring")
ADAPTERS = os.path.join(ROOT, "custom_components", "eufy_vacuum", "adapters")
SERVED = os.path.join(ROOT, "custom_components", "eufy_vacuum", "frontend", "guides", "keys")
BUNDLED = os.path.join(ROOT, "src", "i18n", "guide-keys.js")

# authoring spelling -> served spelling. The ONLY place this seam is crossed.
SERVED_NAME = {"zh_hans": "zh-Hans", "zh_hant": "zh-Hant"}


def _load_keys_module():
    """Load the Dreame key surface without executing the whole adapter __init__.

    TWO SYNTHETIC PACKAGE LEVELS, NOT ONE. The emitter moved to `adapters/upkeep_keys.py`
    (it is every brand's, not Dreame's), so `dreame/upkeep_keys.py` reaches it with
    `from ..upkeep_keys import ...`. A single synthetic package rooted at `dreame/` makes that
    relative import walk off the top -- "attempted relative import beyond top-level package".
    So we mint a parent for `adapters` and a child for `dreame`, and the `..` resolves.
    """
    parent = types.ModuleType("_va_adapters")
    parent.__path__ = [ADAPTERS]
    sys.modules["_va_adapters"] = parent
    child = types.ModuleType("_va_adapters.dreame")
    child.__path__ = [os.path.join(ADAPTERS, "dreame")]
    sys.modules["_va_adapters.dreame"] = child

    def _load(full, path):
        spec = importlib.util.spec_from_file_location(full, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[full] = mod
        spec.loader.exec_module(mod)
        return mod

    d = os.path.join(ADAPTERS, "dreame")
    _load("_va_adapters.upkeep_keys", os.path.join(ADAPTERS, "upkeep_keys.py"))
    _load("_va_adapters.dreame.upkeep_regimes", os.path.join(d, "upkeep_regimes.py"))
    return _load("_va_adapters.dreame.upkeep_keys", os.path.join(d, "upkeep_keys.py"))


def main():
    if not os.path.isdir(FIXTURE):
        sys.exit("fixture not found: %s\n(this script needs the authoring fixture; its OUTPUT is "
                 "what ships)" % FIXTURE)
    keys_mod = _load_keys_module()
    required = set(keys_mod.DREAME_UPKEEP_KEYS)

    packs = {}
    for fn in sorted(os.listdir(FIXTURE)):
        if not (fn.startswith("keys_") and fn.endswith(".json")):
            continue
        lang = fn[len("keys_"):-len(".json")]
        raw = json.load(io.open(os.path.join(FIXTURE, fn), encoding="utf-8"))
        packs[lang] = {k: v for k, v in raw.items() if not k.startswith("_")}

    # ── the gate ────────────────────────────────────────────────────────────────────────────
    problems = []
    for lang, pack in sorted(packs.items()):
        missing = sorted(required - set(pack))
        extra = sorted(set(pack) - required)
        if missing:
            problems.append("%s MISSING %d: %s" % (lang, len(missing), missing))
        if extra:
            problems.append("%s has %d key(s) nothing emits: %s" % (lang, len(extra), extra))
    if "en" not in packs:
        problems.append("no English pack — it is the bundled universal fallback, not optional")
    if problems:
        for p in problems:
            print("  REFUSED: %s" % p)
        sys.exit("refusing to write: a pack does not cover the emitted key set")

    # ── English, bundled ────────────────────────────────────────────────────────────────────
    en = packs["en"]
    head = (
        "/**\n"
        " * DREAME GUIDE KEYS — the ENGLISH BASE, bundled.\n"
        " *\n"
        " * The Dreame guide is %d i18n keys rather than per-family prose: the backend ships KEY\n"
        " * LISTS (adapters/dreame/upkeep_keys.py) and the card resolves them in the USER's\n"
        " * language. English is bundled because `_localizedGuide` needs a synchronous fallback on\n"
        " * every miss; the other %d languages are served from frontend/guides/keys/<lang>.json.\n"
        " *\n"
        " * GENERATED — do not hand-edit. Run: python scripts/sync-dreame-guide-keys.py\n"
        " * Source: durable/dreame-port-fixture/resources/key-authoring/keys_<lang>.json\n"
        " * Shape: GUIDE_KEYS[key] = \"complete sentence\"\n"
        " */\n" % (len(en), len(packs) - 1)
    )
    io.open(BUNDLED, "w", encoding="utf-8", newline="\n").write(
        head + "export const GUIDE_KEYS = " + json.dumps(en, ensure_ascii=False,
                                                         sort_keys=True) + ";\n")

    # ── the rest, served ────────────────────────────────────────────────────────────────────
    os.makedirs(SERVED, exist_ok=True)
    for stale in os.listdir(SERVED):
        if stale.endswith(".json"):
            os.remove(os.path.join(SERVED, stale))
    written = []
    for lang, pack in sorted(packs.items()):
        if lang == "en":
            continue
        name = SERVED_NAME.get(lang, lang)
        io.open(os.path.join(SERVED, name + ".json"), "w", encoding="utf-8",
                newline="\n").write(json.dumps(pack, ensure_ascii=False, sort_keys=True))
        written.append(name + ".json")
    io.open(os.path.join(SERVED, "index.json"), "w", encoding="utf-8", newline="\n").write(
        json.dumps(sorted(written), ensure_ascii=False))

    served_bytes = sum(os.path.getsize(os.path.join(SERVED, f)) for f in written)
    print("wrote %s (%d keys, %d bytes)" % (BUNDLED, len(en), os.path.getsize(BUNDLED)))
    print("wrote %d served packs + index.json to %s (%d bytes)"
          % (len(written), SERVED, served_bytes))
    print("  languages served: %s" % ", ".join(sorted(w[:-5] for w in written)))
    print("  gate: every one of the %d emitted keys present in all %d packs  OK"
          % (len(required), len(packs)))


if __name__ == "__main__":
    main()
