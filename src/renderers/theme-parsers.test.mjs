// Run: node --test src/renderers/theme-parsers.test.mjs
//
// Coverage targets (pure helpers in src/renderers/theme.js):
//   [CM-*]  _parseColorMix        — parse color-mix(in srgb, C1 R%, C2 R2%) -> {color1,ratio,color2,ratio2} | null
//   [SM-*]  _serializeColorMix    — (color1, ratio, color2) -> "color-mix(in srgb, C1 r%, C2 (100-r)%)" (ratio clamped+rounded)
//   [RT-*]  round-trip            — _parseColorMix <-> _serializeColorMix
//   [PS-*]  parseScalarThemeValue — type-branched (number|size|duration) -> {numeric, unit}, default-unit fallback
//   [CP-*]  clampPercent          — Number(v); NaN -> 100; else clamp [0,100]
//   [AH-*]  alphaPercentFromHex   — 8-digit #RRGGBBAA -> round(alpha/255*100) clamped; else 100

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  _parseColorMix,
  _serializeColorMix,
  parseScalarThemeValue,
  clampPercent,
  alphaPercentFromHex,
} from "./theme.js";

/* =========================================================
   _parseColorMix
   ========================================================= */

test("[CM-1] parses a canonical two-stop color-mix into all four fields", () => {
  assert.deepEqual(
    _parseColorMix("color-mix(in srgb, #ff0000 30%, #0000ff 70%)"),
    { color1: "#ff0000", ratio: 30, color2: "#0000ff", ratio2: 70 }
  );
});

test("[CM-2] ratios go through parseFloat, so decimals survive", () => {
  const parsed = _parseColorMix("color-mix(in srgb, red 12.5%, blue 87.5%)");
  assert.deepEqual(parsed, { color1: "red", ratio: 12.5, color2: "blue", ratio2: 87.5 });
});

test("[CM-3] non-color-mix / falsy inputs return null", () => {
  assert.equal(_parseColorMix(""), null);
  assert.equal(_parseColorMix(null), null);
  assert.equal(_parseColorMix(undefined), null);
  assert.equal(_parseColorMix("#ff0000"), null);
  assert.equal(_parseColorMix("rgb(1,2,3)"), null);
});

test("[CM-4] prefix match is case-insensitive and tolerates leading space", () => {
  assert.deepEqual(
    _parseColorMix("  COLOR-MIX(in srgb, #aaa 40%, #bbb 60%)  "),
    { color1: "#aaa", ratio: 40, color2: "#bbb", ratio2: 60 }
  );
});

test("[CM-5] the 'in <word>,' colorspace prefix is stripped only for a \\w+ name", () => {
  // The strip regex is /^\s*in\s+\w+\s*,\s*/i — \w+ matches 'srgb' cleanly.
  assert.deepEqual(
    _parseColorMix("color-mix(in srgb , #111 25%, #222 75%)"),
    { color1: "#111", ratio: 25, color2: "#222", ratio2: 75 }
  );
  // A HYPHENATED colorspace (srgb-linear) is NOT matched by \w+, so the prefix
  // survives and gets swept into color1 by the lazy (.*?) stop group.
  assert.deepEqual(
    _parseColorMix("color-mix(in srgb-linear, #111 25%, #222 75%)"),
    { color1: "in srgb-linear, #111", ratio: 25, color2: "#222", ratio2: 75 }
  );
});

test("[CM-6] a single-stop / no-comma expression returns null (split fails)", () => {
  assert.equal(_parseColorMix("color-mix(in srgb, #ff0000 50%)"), null);
});

test("[CM-7] a stop missing its percentage returns null", () => {
  // Second stop has no '%', so the top-level splitMatch never matches.
  assert.equal(_parseColorMix("color-mix(in srgb, #ff0000 50%, #0000ff)"), null);
});

test("[CM-8] multi-word colors keep their spaces in colorN, pct is stripped", () => {
  // 'var(--x)' and 'rgb( a )' would break the naive splitter, but a plain
  // multi-token color name still round-trips its whitespace via the (.*?) group.
  const parsed = _parseColorMix("color-mix(in srgb, hsl(0 100% 50%) 30%, black 70%)");
  // The lazy '(.*?)\\s+\\d+%' anchors on the LAST '<space>NN%', so color1 keeps its inner spaces.
  assert.equal(parsed.color1, "hsl(0 100% 50%)");
  assert.equal(parsed.ratio, 30);
  assert.equal(parsed.color2, "black");
  assert.equal(parsed.ratio2, 70);
});

/* =========================================================
   _serializeColorMix
   ========================================================= */

test("[SM-1] serializes with the complement (100 - r) on the second stop", () => {
  assert.equal(
    _serializeColorMix("#ff0000", 30, "#0000ff"),
    "color-mix(in srgb, #ff0000 30%, #0000ff 70%)"
  );
});

test("[SM-2] ratio is rounded to an integer", () => {
  assert.equal(
    _serializeColorMix("red", 33.6, "blue"),
    "color-mix(in srgb, red 34%, blue 66%)"
  );
});

test("[SM-3] ratio is clamped to [0,100]", () => {
  assert.equal(_serializeColorMix("a", -20, "b"), "color-mix(in srgb, a 0%, b 100%)");
  assert.equal(_serializeColorMix("a", 250, "b"), "color-mix(in srgb, a 100%, b 0%)");
});

/* =========================================================
   round-trip _parseColorMix <-> _serializeColorMix
   ========================================================= */

test("[RT-1] serialize(parse(x)) is stable for a well-formed complement pair", () => {
  const src = "color-mix(in srgb, #123456 40%, #abcdef 60%)";
  const p = _parseColorMix(src);
  assert.equal(_serializeColorMix(p.color1, p.ratio, p.color2), src);
});

test("[RT-2] parse(serialize(...)) recovers the same inputs", () => {
  const out = _serializeColorMix("#0a0b0c", 25, "#ffffff");
  assert.deepEqual(_parseColorMix(out), {
    color1: "#0a0b0c",
    ratio: 25,
    color2: "#ffffff",
    ratio2: 75,
  });
});

test("[RT-3] serialize normalizes a non-complement pair to the complement", () => {
  // Second stop's ratio2 is ignored by serialize — it always emits 100 - r.
  const p = _parseColorMix("color-mix(in srgb, #111 30%, #222 30%)");
  assert.equal(p.ratio2, 30); // parser faithfully reports the odd input
  assert.equal(
    _serializeColorMix(p.color1, p.ratio, p.color2),
    "color-mix(in srgb, #111 30%, #222 70%)"
  );
});

/* =========================================================
   parseScalarThemeValue
   ========================================================= */

const T_NUMBER   = { type: "number" };
const T_SIZE     = { type: "size" };
const T_DURATION = { type: "duration" };

test("[PS-1] number type: parseFloat with an empty unit", () => {
  assert.deepEqual(parseScalarThemeValue(T_NUMBER, "0.42"), { numeric: 0.42, unit: "" });
  assert.deepEqual(parseScalarThemeValue(T_NUMBER, "3px"), { numeric: 3, unit: "" }); // parseFloat stops at unit
});

test("[PS-2] number type with unparseable text -> numeric null, empty unit", () => {
  assert.deepEqual(parseScalarThemeValue(T_NUMBER, "abc"), { numeric: null, unit: "" });
});

test("[PS-3] empty/whitespace value -> null numeric + the token's DEFAULT unit", () => {
  assert.deepEqual(parseScalarThemeValue(T_SIZE, ""), { numeric: null, unit: "px" });
  assert.deepEqual(parseScalarThemeValue(T_SIZE, "   "), { numeric: null, unit: "px" });
  assert.deepEqual(parseScalarThemeValue(T_DURATION, ""), { numeric: null, unit: "ms" });
  assert.deepEqual(parseScalarThemeValue(T_NUMBER, ""), { numeric: null, unit: "" });
});

test("[PS-4] size type parses a numeric + a recognized unit (case-folded)", () => {
  assert.deepEqual(parseScalarThemeValue(T_SIZE, "16px"), { numeric: 16, unit: "px" });
  assert.deepEqual(parseScalarThemeValue(T_SIZE, "1.5REM"), { numeric: 1.5, unit: "rem" });
  assert.deepEqual(parseScalarThemeValue(T_SIZE, "-2 em"), { numeric: -2, unit: "em" }); // interior space ok
  assert.deepEqual(parseScalarThemeValue(T_SIZE, "50%"), { numeric: 50, unit: "%" });
});

test("[PS-5] size type with a bad/missing unit -> null numeric + default 'px'", () => {
  assert.deepEqual(parseScalarThemeValue(T_SIZE, "16"), { numeric: null, unit: "px" });   // no unit
  assert.deepEqual(parseScalarThemeValue(T_SIZE, "16pt"), { numeric: null, unit: "px" });  // pt not in the allow-list
});

test("[PS-6] duration type parses ms and s, else default 'ms'", () => {
  assert.deepEqual(parseScalarThemeValue(T_DURATION, "250ms"), { numeric: 250, unit: "ms" });
  assert.deepEqual(parseScalarThemeValue(T_DURATION, "0.3S"), { numeric: 0.3, unit: "s" });
  assert.deepEqual(parseScalarThemeValue(T_DURATION, "250"), { numeric: null, unit: "ms" }); // no unit
  assert.deepEqual(parseScalarThemeValue(T_DURATION, "250px"), { numeric: null, unit: "ms" }); // wrong unit
});

test("[PS-7] an unknown token type -> null numeric + empty unit", () => {
  assert.deepEqual(parseScalarThemeValue({ type: "color" }, "#fff"), { numeric: null, unit: "" });
});

/* =========================================================
   clampPercent
   ========================================================= */

test("[CP-1] non-numeric / NaN defaults to 100", () => {
  assert.equal(clampPercent("abc"), 100);
  assert.equal(clampPercent(undefined), 100);
  assert.equal(clampPercent(NaN), 100);
});

test("[CP-2] clamps below 0 and above 100, passes through in-range", () => {
  assert.equal(clampPercent(-5), 0);
  assert.equal(clampPercent(150), 100);
  assert.equal(clampPercent(42), 42);
  assert.equal(clampPercent("73"), 73); // numeric string coerces
});

test("[CP-3] boundary values are inclusive", () => {
  assert.equal(clampPercent(0), 0);
  assert.equal(clampPercent(100), 100);
});

/* =========================================================
   alphaPercentFromHex
   ========================================================= */

test("[AH-1] 8-digit hex maps the alpha byte to a rounded percent", () => {
  assert.equal(alphaPercentFromHex("#ffffffff"), 100); // ff -> 255/255 = 100
  assert.equal(alphaPercentFromHex("#00000000"), 0);   // 00 -> 0
  assert.equal(alphaPercentFromHex("#ff000080"), 50);  // 80 = 128 -> round(50.19) = 50
});

test("[AH-2] mixed-case 8-digit hex is accepted; result stays in [0,100]", () => {
  assert.equal(alphaPercentFromHex("#AABBCCFF"), 100);
  assert.equal(alphaPercentFromHex("#aabbcc40"), 25); // 40 = 64 -> round(25.098) = 25
});

test("[AH-3] anything that is not exactly 8 hex digits -> 100 (fully opaque)", () => {
  assert.equal(alphaPercentFromHex("#ffffff"), 100);   // 6-digit, no alpha
  assert.equal(alphaPercentFromHex("#fff"), 100);      // 3-digit
  assert.equal(alphaPercentFromHex("#fffffffff"), 100); // 9 digits
  assert.equal(alphaPercentFromHex("red"), 100);
  assert.equal(alphaPercentFromHex(""), 100);
  assert.equal(alphaPercentFromHex(null), 100);
  assert.equal(alphaPercentFromHex(undefined), 100);
});

test("[AH-4] surrounding whitespace is trimmed before the hex test", () => {
  assert.equal(alphaPercentFromHex("  #ff000080  "), 50);
});
