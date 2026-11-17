// Run: node --test src/theme-tokens/helpers.test.mjs
//
// Coverage targets (src/theme-tokens/helpers.js):
//   [TL-*]  makeTokenLabel        — strip --evcc- prefix, hyphens->spaces, title-case word-starts, trim
//   [GT-*]  makeGroupedToken      — validate type vs VALID_TOKEN_TYPES (defaultType fallback), copy only finite range fields
//   [TG-*]  makeTypedGroupToken   — explicit type methods + ranged semantic methods (.unit/.blur/.angle/.signed)
//                                    merging SCALAR_RANGES defaults with an optional per-token {min,max,step} override
//   [LEN-*] normaliseLengthList   — issue #83's "or at least default to px": a bare number in a
//                                    CSS length list becomes px, and anything unrecognised is
//                                    returned UNTOUCHED rather than guessed at
//
// Direct-import pattern mirrors src/cards/map-room-color.test.mjs.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  makeTokenLabel,
  makeGroupedToken,
  makeTypedGroupToken,
  SCALAR_RANGES,
  THEME_TOKEN_TYPES,
  normaliseLengthList,
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
  // 32, not 8. Blur is px with no CSS ceiling, and 8 was measurably too tight: a
  // 24px vein is a visibly different render that the SLIDER could not reach, so the
  // only way there was typing into the number box beside it. Literal here on
  // purpose -- asserting against SCALAR_RANGES.blur would make this a tautology
  // that cannot notice the constant moving.
  assert.deepEqual(
    { min: blur.min, max: blur.max, step: blur.step },
    { min: 0, max: 32, step: 0.5 },
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

/* =========================================================
   [LEN-*] normaliseLengthList — a bare number means px
   =========================================================
   WHY. Issue #83: the reporter found a text box whose only content was the word
   "Default" and asked what it did. `padding: 8` is not valid CSS — it is dropped
   silently, so the number a user means produces no padding and no error anywhere.
   His words were "or at least default to px".

   The risk in a normaliser is that it mangles something valid, which is worse than
   doing nothing because the user cannot see why their value stopped working. So the
   tests below are weighted toward what it must NOT touch.
   ========================================================= */

test("[LEN-1] a bare number gets px, in every position of the list", () => {
  // THE RED INPUT: removing the coercion. Each of these is a value a user types and
  // CSS then discards.
  assert.equal(normaliseLengthList("8"), "8px");
  assert.equal(normaliseLengthList("8 12"), "8px 12px");
  assert.equal(normaliseLengthList("4 8 12 16"), "4px 8px 12px 16px");
  assert.equal(normaliseLengthList("-4"), "-4px");
  assert.equal(normaliseLengthList(".5"), ".5px");
  assert.equal(normaliseLengthList("  6  "), "6px", "surrounding whitespace is trimmed");
  assert.equal(normaliseLengthList("8   12"), "8px 12px", "inner runs collapse to one space");
});

test("[LEN-2] a ZERO is left unitless, deliberately", () => {
  // THE RED INPUT: coercing every number, including zero. Unitless `0` is valid CSS and
  // is what people actually write — `0 8` is idiomatic and `0px 8px` is noise. This is
  // the one non-coercion inside a list the function CAN read, so it is pinned.
  assert.equal(normaliseLengthList("0"), "0");
  assert.equal(normaliseLengthList("0 8"), "0 8px");
  assert.equal(normaliseLengthList("0.0"), "0.0");
});

test("[LEN-3] a value that already carries units is untouched", () => {
  for (const v of ["8px", "14px 16px 10px", "1rem", "50%", "2em 4em", "8PX", "auto",
                   "inherit", "unset", "1vh 2vw"]) {
    assert.equal(normaliseLengthList(v), v, `${v} must pass through unchanged`);
  }
});

test("[LEN-4] function expressions survive — the PART REGEX is what protects them", () => {
  // THE RED INPUT: relaxing the part regex to a partial/prefix match. Every one of these
  // survives because no whitespace-separated part is a bare number END TO END — NOT
  // because anything recognises `calc(`.
  //
  // THIS TEST WAS RE-AIMED BY AN ABLATION. An explicit `if (/[(),]/.test(raw)) return raw`
  // guard used to sit in the function, and removing it reddened NOTHING: the regex below
  // already covered every input the guard was written for. Worse, measured across eleven
  // inputs it changed the answer for four and was WRONG in three — see [LEN-4b]. The
  // version of this test that named that guard as its red input was testing a guard that
  // could not fail.
  for (const v of ["calc(100% - 2px)", "var(--evcc-space-md)", "min(4px, 1%)",
                   "clamp(4px, 1vw, 12px)", "1px, 2px", "rgba(0,0,0,0.3)", "min(4, 1%)"]) {
    assert.equal(normaliseLengthList(v), v, `${v} must be returned untouched`);
  }
});

test("[LEN-4b] a token mixed with a bare number DOES coerce — what the dead guard broke", () => {
  // `padding: var(--evcc-space-md) 8` is a legitimate two-part list. The removed
  // `/[(),]/` guard returned it whole, so the 8 stayed unitless and that edge got no
  // padding — the exact defect this function exists to prevent, reinstated by the guard
  // meant to make it safe. THE RED INPUT: putting that guard back.
  assert.equal(normaliseLengthList("var(--evcc-space-md) 8"), "var(--evcc-space-md) 8px");
  assert.equal(normaliseLengthList("8 var(--x)"), "8px var(--x)");
  assert.equal(normaliseLengthList("calc(100% - 2) 4"), "calc(100% - 2) 4px");
});

test("[LEN-9] more than four parts is not a length list, and is returned whole", () => {
  // THE RED INPUT: dropping the `parts.length > 4` guard. It is now the ONLY structural
  // guard left, which makes it load-bearing in a way the one removed above never was:
  // without it a five-part string gets px stapled onto every number in it.
  assert.equal(normaliseLengthList("1 2 3 4 5"), "1 2 3 4 5");
  assert.equal(normaliseLengthList("1 2 3 4"), "1px 2px 3px 4px", "four parts still coerce");
});

test("[LEN-5] empty stays empty, because empty means UNSET", () => {
  // THE RED INPUT: returning "0px" (or anything) for an empty box. An empty token must
  // stay empty so the var() fallback chain still inherits from the panel's token — that
  // is the whole of the card-token inheritance ruling. Coercing it to a value would
  // silently pin every card to a literal and kill the panel rung.
  for (const v of ["", "   ", null, undefined]) {
    assert.equal(normaliseLengthList(v), "");
  }
});

test("[LEN-6] it is idempotent — a commit that changes nothing writes nothing", () => {
  // The change handler compares the normalised value against the box's own text and only
  // rewrites on a difference. If normalising twice moved the value, every blur would
  // rewrite the input and the caret would jump for no reason.
  for (const v of ["8", "0 8", "14px 16px", "calc(1px + 1px)", ""]) {
    const once = normaliseLengthList(v);
    assert.equal(normaliseLengthList(once), once, `${v} must be stable under a second pass`);
  }
});

test("[LEN-7] 'lengths' is a real registered type, and the paddings use it", () => {
  // A correct normaliser wired to nothing passes every test about the normaliser. This is
  // the reachability half: the type must exist, and a token must actually carry it.
  assert.ok(THEME_TOKEN_TYPES.includes("lengths"), "lengths must be a registered token type");
  const gm = makeTypedGroupToken("Dashboard Cards", "size");
  assert.equal(gm.lengths("--evcc-card-row-padding", "Row Padding").type, "lengths");
});

test("[LEN-8] the binding actually calls it — the persist path AND the visible one", () => {
  // A correct normaliser with zero callers passes every test above it. This is the
  // reachability half, and it is a TEXT assertion for a structural reason rather than a
  // shortcut: bindings/theme.js reaches the DOM and the live card, and the harness
  // renders the theme editor through its SYNTHETIC frame (mount-entry.js says so), so no
  // runnable surface in this repo wires these two handlers.
  //
  // THE RED INPUT: adding the type and the placeholder and forgetting the normaliser in
  // one of the handlers. Forgetting it in `input` stores the raw `8` that CSS discards;
  // forgetting it in `change` stores `8px` while the box still reads `8`, so the control
  // contradicts what was saved. Two call sites, both required.
  const src = readFileSync("src/bindings/theme.js", "utf8");
  assert.match(
    src,
    /import \{[^}]*normaliseLengthList[^}]*\} from "\.\.\/theme-tokens\/helpers\.js"/,
    "bindings/theme.js must import normaliseLengthList",
  );
  const calls = src.match(/normaliseLengthList\(/g) ?? [];
  assert.ok(
    calls.length >= 2,
    "both halves must call it — the `input` handler (what gets PERSISTED) and the " +
    `\`change\` handler (what the user SEES). Found ${calls.length} call site(s).`,
  );
  assert.match(src, /type === "lengths"/, "...and it must be gated on the lengths type");
});
