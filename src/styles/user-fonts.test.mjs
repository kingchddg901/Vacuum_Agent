// Run: node --test src/styles/user-fonts.test.mjs
// Drop-in fonts, catalog architecture: the BACKEND (user_fonts.py) owns
// discovery, cmap parsing, and per-locale verification and writes
// catalog.json; the card consumes it generically. The sanitizer here is
// defense in depth (the catalog rides a user-writable directory and its
// fields become CSS), and the card NEVER render-verifies — rendered-text
// checks lie through per-glyph fallback (the live:FONT-1 instrument class).
// UF = User Fonts.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  sanitizeUserFontDef, loadUserFonts, allFontDefs, runtimeFontPresets,
  runtimeFontFaceCss, runtimeFontTokenRules, runtimeShadowFontCss,
} from "./fonts.js";
import { FONT_SUPPORT, registerRuntimeFontSupport, fontSupportsLang } from "../i18n/font-store.js";

const GOOD = () => ({
  id: "atkinson",
  family: "Atkinson Hyperlegible",
  dir: "atkinson",
  faces: [{ file: "Atkinson-Regular.woff2", weight: 400 }],
  fallback: ["Arial", "sans-serif"],
  locales: ["en", "de"],
  status: "verified",
});

test("[UF-1] sanitizer accepts a catalog entry and derives the stack + base", () => {
  const def = sanitizeUserFontDef(GOOD());
  assert.ok(def);
  assert.equal(def.id, "atkinson");
  assert.equal(def.label, "Atkinson Hyperlegible");
  assert.equal(def.base, "/eufy_vacuum/user_fonts/atkinson");
  assert.equal(def.stack, `"Atkinson Hyperlegible", var(--paper-font-body1_-_font-family, Arial, sans-serif)`);
  assert.deepEqual(def.locales, ["en", "de"]);
  assert.equal(def.runtime, true);
  // Never a fallback-less var() (TF-10's guaranteed-invalid trap).
  assert.doesNotMatch(def.stack, /var\(--[\w-]+\)/);
});

test("[UF-2] sanitizer rejects everything that could smuggle CSS or paths", () => {
  const bad = [
    { ...GOOD(), id: "Bad Id" },
    { ...GOOD(), id: "opendyslexic" },                        // shipped-id collision
    { ...GOOD(), dir: "../evil" },
    { ...GOOD(), dir: "a/b" },
    { ...GOOD(), family: 'Evil"; } * { color: red; } /*' },  // CSS breakout
    { ...GOOD(), family: "" },
    { ...GOOD(), faces: [] },
    { ...GOOD(), faces: [{ file: "../../secret.woff2", weight: 400 }] },
    { ...GOOD(), faces: [{ file: "font.ttf", weight: 400 }] },
    null,
    "string",
  ];
  for (const raw of bad) {
    assert.equal(sanitizeUserFontDef(raw), null, JSON.stringify(raw)?.slice(0, 60));
  }
  // Field-level tolerance: bad weight -> 400; a fallback list that does not
  // end in a generic keyword gets sans-serif appended; junk locales dropped.
  const soft = sanitizeUserFontDef({
    ...GOOD(),
    fallback: ["Arial", 'ev"il'],
    faces: [{ file: "a.woff2", weight: 9999 }],
    locales: ["en", "NOT A LANG", "../x", "zh-Hans"],
  });
  assert.equal(soft.faces[0].weight, 400);
  assert.match(soft.stack, /Arial, sans-serif\)$/);
  assert.deepEqual(soft.locales, ["en", "zh-hans"]);
});

test("[UF-3] loader consumes catalog.json, dedupes, and is unbreakable", async () => {
  const responses = {
    "/eufy_vacuum/user_fonts/catalog.json": [
      { ...GOOD(), id: "uf3good", family: "Good Font", dir: "good", locales: ["en"] },
      { ...GOOD(), id: "NOPE!", dir: "bad" },                 // rejected entry
      "garbage",
    ],
  };
  const fetchFn = async (url) => ({
    ok: url in responses,
    json: async () => responses[url],
  });
  const added = await loadUserFonts(fetchFn);
  assert.equal(added.length, 1);
  assert.equal(added[0].id, "uf3good");
  assert.ok(allFontDefs().some((d) => d.id === "uf3good"));
  // Second load of the same id: dedupe, not duplicate.
  assert.equal((await loadUserFonts(fetchFn)).length, 0);
  // A dead fetch is a no-op, never a throw.
  assert.deepEqual(await loadUserFonts(async () => { throw new Error("net down"); }), []);
  assert.deepEqual(await loadUserFonts(undefined), []);
});

test("[UF-4] runtime CSS generators mirror the shipped generators", () => {
  // uf3good was registered in UF-3 (same module instance), base dir "good".
  const faces = runtimeFontFaceCss();
  assert.match(faces, /font-family: "Good Font"/);
  assert.match(faces, /url\("\/eufy_vacuum\/user_fonts\/good\/Atkinson-Regular\.woff2"\)/);
  assert.ok(!/https?:\/\//.test(faces), "external URL in runtime faces");

  const rules = runtimeFontTokenRules((id) => `.probe-${id}`);
  assert.match(rules, /\.probe-uf3good \{\s*--evcc-a11y-font-family: "Good Font"/);
  assert.ok(!rules.includes("--evcc-font-family:"), "runtime setter writes the THEME token");

  const shadow = runtimeShadowFontCss();
  assert.match(shadow, /:host\(\[data-evcc-font="uf3good"\]\)/);
  assert.match(shadow, /\.evcc-font-sample-uf3good/);

  assert.ok(runtimeFontPresets().some((p) => p.id === "uf3good" && p.label === "Good Font"));
});

test("[UF-5] offering comes from the catalog's verified locales, per language", () => {
  assert.equal(fontSupportsLang("uf5font", "en"), false);
  registerRuntimeFontSupport("uf5font", "en");
  registerRuntimeFontSupport("uf5font", "de");
  assert.equal(fontSupportsLang("uf5font", "en"), true);
  assert.equal(fontSupportsLang("uf5font", "en-GB"), true, "base-tag match");
  assert.equal(fontSupportsLang("uf5font", "ru"), false, "per-locale, never global");
  assert.ok(Object.hasOwn(FONT_SUPPORT, "uf5font"), "stored-font validation can restore it");
  // A drop-in can never widen a shipped font's HUMAN-verified set.
  const before = new Set(FONT_SUPPORT.opendyslexic);
  registerRuntimeFontSupport("opendyslexic", "ru");
  assert.deepEqual(FONT_SUPPORT.opendyslexic, before, "shipped set was widened at runtime");
});

test("[UF-6] main.js wires load, render re-injection, both body hosts — and NO render-verification", () => {
  const main = readFileSync(new URL("../main.js", import.meta.url), "utf-8");
  assert.match(main, /_maybeLoadUserFonts\(\);/, "drop-in load lost its first-hass trigger");
  assert.match(main, /ensureUserFontFacesInDocument\(\)/, "document-level face registration vanished");
  assert.match(main, /registerRuntimeFontSupport\(def\.id, lang\)/,
    "offering no longer registered from the catalog's verified locales");
  assert.match(main, /this\._ensureRuntimeFontStyles\(\); \/\/ survives frame resets/,
    "the runtime shadow style is no longer re-injected in _render — a frame reset silently drops drop-in fonts");
  assert.match(main, /MODAL_HOST_STYLES\}\$\{runtimeFontTokenRules/, "modal host lost runtime setters");
  assert.match(main, /TOAST_HOST_STYLES\}\$\{runtimeFontTokenRules/, "toast host lost runtime setters");
  // The forbidden instrument: no browser render-verification anywhere.
  assert.ok(!main.includes("font-coverage"),
    "a render-verification module crept back in — the cmap catalog is the only gate");
});
