// Run: node --test src/theme-tokens/helpers.test.mjs
//
// Coverage targets (src/theme-tokens/helpers.js):
//   [TL-*]  makeTokenLabel        — strip --evcc- prefix, hyphens->spaces, title-case word-starts, trim
//   [GT-*]  makeGroupedToken      — validate type vs VALID_TOKEN_TYPES (defaultType fallback), copy only finite range fields
//   [TG-*]  makeTypedGroupToken   — explicit type methods + ranged semantic methods (.unit/.blur/.angle/.signed)
//                                    merging SCALAR_RANGES defaults with an optional per-token {min,max,step} override
//
// Direct-import pattern mirrors src/cards/map-room-color.test.mjs.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  makeTokenLabel,
  makeGroupedToken,
  makeTypedGroupToken,
  SCALAR_RANGES,
  THEME_TOKEN_TYPES,
} from "./helpers.js";

/* =========================================================
   makeTokenLabel
   ========================================================= */

test("[TL-1] strips --evcc- prefix, hyphens->spaces, title-cases word starts", () => {
  assert.equal(makeTokenLabel("--evcc-chip-bg"), "Chip Bg");
  assert.equal(makeTokenLabel("--evcc-room-card-border"), "Room Card Border");
});

test("[TL-2] only the prefix at the START is stripped (anchored)", () => {
  // The regex is ^--evcc-, so an inner occurrence is not stripped; the leading
  // "x-" then becomes "X " and the inner "--evcc-" hyphens become spaces.
  assert.equal(makeTokenLabel("x---evcc-foo"), "X   Evcc Foo");
});

test("[TL-3] title-case is word-START only; existing caps are preserved (no lowercasing)", () => {
  // \b\w upper-cases the first char of each word; trailing chars are untouched.
  assert.equal(makeTokenLabel("--evcc-chip-BG"), "Chip BG");
  assert.equal(makeTokenLabel("--evcc-URL-path"), "URL Path");
});

test("[TL-4] digit-led word: boundary is the digit, following letter stays as-is", () => {
  // "2x-size" -> "2x size"; \b\w matches the leading "2" (already a digit) and
  // the "s" of "size". "x" follows a digit (no \b before it) so stays lowercase.
  assert.equal(makeTokenLabel("--evcc-2x-size"), "2x Size");
});

test("[TL-5] empty / nullish / non-string keys coerce safely", () => {
  assert.equal(makeTokenLabel(""), "");
  assert.equal(makeTokenLabel(null), "");
  assert.equal(makeTokenLabel(undefined), "");
  // Number is coerced via String(); "0" is truthy-as-string only because
  // String(key || "") sees 0 as falsy -> "". So numeric 0 -> "".
  assert.equal(makeTokenLabel(0), "");
  // A non-zero number is truthy -> String() coerces it, first char title-cased.
  assert.equal(makeTokenLabel(42), "42");
});

test("[TL-6] a key without the prefix is still spaced + title-cased + trimmed", () => {
  assert.equal(makeTokenLabel("plain-token-name"), "Plain Token Name");
});

test("[TL-7] the prefix strip is anchored: leading whitespace defeats it, then trim runs LAST", () => {
  // ^--evcc- only matches at string start. Leading spaces mean the string does
  // NOT start with the prefix, so it is NOT stripped -> "--evcc-" -> " Evcc Foo".
  // .trim() (which runs last) only removes the outer whitespace, not the prefix.
  assert.equal(makeTokenLabel("  --evcc-foo  "), "Evcc Foo");
  // Without leading whitespace the anchor matches and the prefix is stripped.
  assert.equal(makeTokenLabel("--evcc-foo  "), "Foo");
});

/* =========================================================
   makeGroupedToken
   ========================================================= */

test("[GT-1] produces a stable entry shape with a derived label", () => {
  const t = makeGroupedToken("Chips");
  assert.deepEqual(t("--evcc-chip-bg"), {
    key: "--evcc-chip-bg",
    label: "Chip Bg",
    group: "Chips",
    type: "color", // defaultType
  });
});

test("[GT-2] explicit label wins over the derived one", () => {
  const t = makeGroupedToken("Chips");
  const entry = t("--evcc-chip-bg", "Custom Label");
  assert.equal(entry.label, "Custom Label");
});

test("[GT-3] a valid type is used; an unknown type falls back to defaultType", () => {
  const t = makeGroupedToken("Map", "size");
  assert.equal(t("--evcc-x", null, "shadow").type, "shadow"); // valid -> kept
  assert.equal(t("--evcc-x", null, "bogus").type, "size");    // unknown -> defaultType fallback
  assert.equal(t("--evcc-x").type, "size");                   // omitted -> defaultType
});

test("[GT-4] range: only Number.isFinite fields are copied onto the entry", () => {
  const t = makeGroupedToken("Map", "number");
  const entry = t("--evcc-x", null, "number", {
    min: 0,
    max: 8,
    step: 0.5,
    junk: "ignored",
  });
  assert.equal(entry.min, 0);
  assert.equal(entry.max, 8);
  assert.equal(entry.step, 0.5);
  assert.ok(!("junk" in entry));
});

test("[GT-5] non-finite range fields (NaN / Infinity / string / missing) are skipped", () => {
  const t = makeGroupedToken("Map", "number");
  const entry = t("--evcc-x", null, "number", {
    min: NaN,
    max: Infinity,
    step: "0.5", // string, not a finite number
  });
  assert.ok(!("min" in entry), "NaN min skipped");
  assert.ok(!("max" in entry), "Infinity max skipped");
  assert.ok(!("step" in entry), "string step skipped");
});

test("[GT-6] a partial range copies only the finite field present", () => {
  const t = makeGroupedToken("Map", "number");
  const entry = t("--evcc-x", null, "number", { max: 2 });
  assert.ok(!("min" in entry));
  assert.equal(entry.max, 2);
  assert.ok(!("step" in entry));
});

test("[GT-7] no range / null range / non-object range adds no bounds", () => {
  const t = makeGroupedToken("Map", "number");
  for (const bad of [null, undefined, 5, "range"]) {
    const entry = t("--evcc-x", null, "number", bad);
    assert.ok(!("min" in entry) && !("max" in entry) && !("step" in entry));
  }
});

/* =========================================================
   makeTypedGroupToken
   ========================================================= */

test("[TG-1] the base factory still works (bare call uses defaultType)", () => {
  const gm = makeTypedGroupToken("Map", "color");
  assert.deepEqual(gm("--evcc-map-bg"), {
    key: "--evcc-map-bg",
    label: "Map Bg",
    group: "Map",
    type: "color",
  });
});

test("[TG-2] explicit type methods each set their own type", () => {
  const gm = makeTypedGroupToken("Map", "color");
  const cases = [
    ["color", "color"],
    ["text", "text"],
    ["shadow", "shadow"],
    ["size", "size"],
    ["number", "number"],
    ["duration", "duration"],
    ["motion", "motion"],
    ["typography", "typography"],
    ["easing", "easing"],
  ];
  for (const [method, expectedType] of cases) {
    const entry = gm[method]("--evcc-x");
    assert.equal(entry.type, expectedType, `gm.${method}() -> type ${expectedType}`);
    // Type methods carry no range.
    assert.ok(!("min" in entry) && !("max" in entry) && !("step" in entry));
  }
  // Every registry type is covered by a method.
  for (const type of THEME_TOKEN_TYPES) {
    assert.equal(typeof gm[type], "function", `method exists for ${type}`);
  }
});

test("[TG-3] .number is intentionally rangeless", () => {
  const gm = makeTypedGroupToken("Floor Textures", "number");
  const entry = gm.number("--evcc-x");
  assert.equal(entry.type, "number");
  assert.ok(!("min" in entry) && !("max" in entry) && !("step" in entry));
});

test("[TG-4] semantic methods stamp type:number + the kind's SCALAR_RANGES defaults", () => {
  const gm = makeTypedGroupToken("Map", "color");

  const unit = gm.unit("--evcc-alpha");
  assert.equal(unit.type, "number");
  assert.equal(unit.min, SCALAR_RANGES.unit.min);   // 0
  assert.equal(unit.max, SCALAR_RANGES.unit.max);   // 1
  assert.equal(unit.step, SCALAR_RANGES.unit.step); // 0.01

  const blur = gm.blur("--evcc-blur");
  assert.deepEqual(
    { min: blur.min, max: blur.max, step: blur.step },
    { min: 0, max: 8, step: 0.5 },
  );

  const angle = gm.angle("--evcc-hue");
  assert.deepEqual(
    { min: angle.min, max: angle.max, step: angle.step },
    { min: -180, max: 180, step: 1 },
  );

  const signed = gm.signed("--evcc-delta");
  assert.deepEqual(
    { min: signed.min, max: signed.max, step: signed.step },
    { min: -1, max: 1, step: 0.01 },
  );
});

test("[TG-5] a per-token override is merged ON TOP of the kind defaults (only overridden fields change)", () => {
  const gm = makeTypedGroupToken("Map", "color");
  // 0-2 chroma multiplier: override max only, keep unit's min/step.
  const entry = gm.unit("--evcc-chroma", null, { max: 2 });
  assert.equal(entry.min, 0);     // default preserved
  assert.equal(entry.max, 2);     // overridden
  assert.equal(entry.step, 0.01); // default preserved
});

test("[TG-6] a non-finite override value does NOT clobber the finite default", () => {
  const gm = makeTypedGroupToken("Map", "color");
  // { ...defaults, ...override } spreads NaN onto max, but makeGroupedToken then
  // only copies finite fields -> the NaN max is dropped and no max survives...
  const entry = gm.unit("--evcc-x", null, { max: NaN });
  assert.equal(entry.min, 0);
  assert.equal(entry.step, 0.01);
  // NaN overwrote the finite default in the merged object, then failed the
  // Number.isFinite copy gate, so max is absent (NOT the default 1).
  assert.ok(!("max" in entry), "NaN override drops max entirely");
});

test("[TG-7] the semantic method accepts an explicit label", () => {
  const gm = makeTypedGroupToken("Map", "color");
  const entry = gm.unit("--evcc-alpha", "Fill Opacity");
  assert.equal(entry.label, "Fill Opacity");
  assert.equal(entry.type, "number");
  assert.equal(entry.min, 0);
});

test("[TG-8] SCALAR_RANGES / the entry are not mutated by an override (defaults are copied, not shared)", () => {
  const gm = makeTypedGroupToken("Map", "color");
  gm.unit("--evcc-a", null, { min: -5, max: 99, step: 3 });
  // The frozen source-of-truth is untouched by the per-token override.
  assert.deepEqual(SCALAR_RANGES.unit, { min: 0, max: 1, step: 0.01 });
  // A fresh unit token still gets the pristine defaults.
  const fresh = gm.unit("--evcc-b");
  assert.deepEqual(
    { min: fresh.min, max: fresh.max, step: fresh.step },
    { min: 0, max: 1, step: 0.01 },
  );
});
