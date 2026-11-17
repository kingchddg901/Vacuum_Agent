// Run: node --test src/theme-tokens/shadow-value.test.mjs
//
// [SHV-*] TAKING A box-shadow APART AND PUTTING IT BACK.
//
// THE CORPUS IS REAL DATA, and that is the whole reason this file is shaped the way it is.
// The control this serves newly activates over themes already on disk, so the values were
// read off a live install before a line of it was written. Of the 8 shadow values any
// stored theme actually carries: 3 single-layer, 4 two-layer, 1 three-layer. The SHIPPED
// DEFAULTS are all single-layer, so reading those first gave the wrong answer and nearly
// produced a five-field control that would have covered 37% of the real values and sent
// the rest to a text box.
//
// [SHV-1] is therefore the test that matters most: those exact 8 strings, round-tripped.
// Everything else is a property that holds them up.
//
// Coverage
// --------
// [SHV-1] the 8 REAL stored values round-trip byte-for-byte
// [SHV-2] the shipped defaults round-trip too (single-layer, and `none`)
// [SHV-3] splitting is on TOP-LEVEL commas — rgba()'s own commas do not split
// [SHV-4] `inset` and the colour are found by what they are, not by position
// [SHV-5] it FAILS OPEN on anything the control could not round-trip
// [SHV-6] `none` and empty are different values and stay different
// [SHV-7] zero layers emits `none`, never ""
// [SHV-8] a spread with no blur forces an explicit 0 blur

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  splitShadowLayers, parseShadowLayer, formatShadowLayer, parseShadow, formatShadow,
} from "./shadow-value.js";

/** Read 2026-11-16 from .storage/eufy_vacuum.storage on the live install (read-only).
 *  One theme of 31 sets shadows at all; these are all 8 of its values. */
const REAL = [
  "0 10px 28px rgba(0,0,0,0.68), 0 0 0 1px rgba(201,84,30,0.38)",
  "0 1px 2px rgba(0,0,0,0.50), 0 4px 12px rgba(0,0,0,0.36)",
  "0 24px 64px rgba(0,0,0,0.78)",
  "0 0 0 1px rgba(201,84,30,0.58), 0 0 18px rgba(201,84,30,0.28)",
  "0 0 0 1px rgba(94,124,147,0.42)",
  "0 1px 2px rgba(0,0,0,0.62), 0 6px 18px rgba(0,0,0,0.50)",
  "0 2px 4px rgba(0,0,0,0.66), 0 14px 34px rgba(0,0,0,0.58), 0 0 0 1px rgba(201,84,30,0.26)",
  "0 0 8px rgba(201,84,30,0.55)",
];

/** The var() fallbacks the cards and panel ship with. */
const DEFAULTS = [
  "0 6px 14px rgba(0, 0, 0, 0.14)",
  "0 8px 20px rgba(0, 0, 0, 0.2)",
  "0 12px 32px rgba(0, 0, 0, 0.25)",
  "0 10px 20px rgba(0, 0, 0, 0.18)",
  "0 12px 30px rgba(0, 0, 0, 0.28)",
  "0 14px 28px rgba(0, 0, 0, 0.25)",
  "0 20px 60px rgba(0, 0, 0, 0.6)",
];

test("[SHV-1] the 8 real stored values round-trip byte-for-byte", () => {
  // THE RED INPUT: splitting on every comma, which shreds rgba(); or dropping spread,
  // which silently turns a 1px ring into a blur. Either shows up here and nowhere else.
  for (const v of REAL) {
    const p = parseShadow(v);
    assert.equal(p.ok, true, `refused a value that is live on a real install: ${v}\n${p.reason}`);
    assert.equal(formatShadow(p.layers), v, `did not round-trip:\n  in  ${v}\n  out ${formatShadow(p.layers)}`);
  }
  // And the layer counts are the measured ones, so the corpus cannot quietly become
  // all-single-layer and leave this file testing the easy case.
  const counts = REAL.map((v) => parseShadow(v).layers.length).sort();
  assert.deepEqual(counts, [1, 1, 1, 2, 2, 2, 2, 3],
    "the corpus must keep its real mix of 1-, 2- and 3-layer values");
});

test("[SHV-2] the shipped defaults round-trip, and so does `none`", () => {
  for (const v of DEFAULTS) {
    const p = parseShadow(v);
    assert.equal(p.ok, true, `refused a shipped default: ${v}`);
    assert.equal(formatShadow(p.layers), v);
  }
  const none = parseShadow("none");
  assert.deepEqual([none.ok, none.layers.length, none.explicitNone], [true, 0, true]);
});

test("[SHV-3] splitting is on TOP-LEVEL commas only", () => {
  // THE RED INPUT: value.split(","). Every real value has an rgba() carrying three
  // commas of its own, so that produces 4-6 nonsense layers out of a 2-layer value.
  assert.deepEqual(splitShadowLayers("0 1px 2px rgba(0,0,0,0.5)"), ["0 1px 2px rgba(0,0,0,0.5)"]);
  assert.deepEqual(
    splitShadowLayers("0 1px 2px rgba(0, 0, 0, 0.5), inset 0 0 4px #fff"),
    ["0 1px 2px rgba(0, 0, 0, 0.5)", "inset 0 0 4px #fff"],
  );
  assert.deepEqual(splitShadowLayers(""), []);
  assert.deepEqual(splitShadowLayers("  ,  "), []);
});

test("[SHV-4] `inset` and the colour are found by what they are, not where they sit", () => {
  // CSS allows both in any position. A positional parser passes the common shape and
  // mangles the legal-but-unusual one, which is the worst way to be wrong.
  const a = parseShadowLayer("inset 0 2px 4px #000");
  const b = parseShadowLayer("0 2px 4px #000 inset");
  const c = parseShadowLayer("#000 0 2px 4px");
  for (const got of [a, b]) {
    assert.equal(got.inset, true);
    assert.deepEqual([got.x, got.y, got.blur, got.spread, got.color], ["0", "2px", "4px", "", "#000"]);
  }
  assert.equal(c.inset, false);
  assert.deepEqual([c.x, c.y, c.blur, c.color], ["0", "2px", "4px", "#000"]);
  // Two colours or two insets is not valid CSS and must not be guessed at.
  assert.equal(parseShadowLayer("0 0 #000 #fff"), null);
  assert.equal(parseShadowLayer("inset inset 0 0"), null);
});

test("[SHV-5] it FAILS OPEN on anything the control could not round-trip", () => {
  // THE RED INPUT: accepting these. `var(--evcc-shadow-hover, ...)` is a deliberate
  // reference, and a control that parsed it would rewrite it into a literal on the first
  // keystroke — destroying the link with nothing on screen to explain why.
  const refuse = [
    "var(--evcc-shadow-hover, 0 12px 30px rgba(0,0,0,0.28))",
    "var(--ha-card-box-shadow, none)",
    "0 calc(1px + 1px) 4px #000",
    "0 2px 4px currentColor",
    "0 2px 4px var(--evcc-accent)",
    "0 2px 4px 6px 8px #000",   // five lengths is not a box-shadow
    "0",                         // one length: offset-y is required
    "0 1px 2px rgba(0,0,0,.5), var(--x)",   // one bad layer poisons the whole value
  ];
  for (const v of refuse) {
    const p = parseShadow(v);
    assert.equal(p.ok, false, `should have refused and kept the text box: ${v}`);
    assert.equal(p.layers, null);
    assert.ok(p.reason && p.reason.length > 10, `${v}: a refusal needs a reason`);
  }
});

test("[SHV-6] `none` and empty are different, and stay different", () => {
  // They are NOT interchangeable: an empty token inherits a shadow from the cascade,
  // `none` overrides it. Conflating them would make "no shadow" unexpressible.
  const empty = parseShadow("");
  const none = parseShadow("none");
  assert.deepEqual([empty.ok, empty.layers.length, empty.explicitNone], [true, 0, false]);
  assert.deepEqual([none.ok, none.layers.length, none.explicitNone], [true, 0, true]);
  assert.notEqual(empty.explicitNone, none.explicitNone);
  assert.equal(parseShadow("NONE").explicitNone, true, "case-insensitive, like CSS");
});

test("[SHV-7] zero layers emits `none`, never an empty string", () => {
  // THE RED INPUT: returning "". Removing the last layer would then UNSET the token and
  // the card would inherit a shadow the user had just deleted — the opposite of what
  // the button says. Clearing the token is what the row's Reset is for.
  assert.equal(formatShadow([]), "none");
  assert.equal(formatShadow(null), "none");
  assert.equal(formatShadow([{ x: "0", y: "0" }]), "0 0");
});

test("[SHV-8] a spread with no blur forces an explicit 0 blur", () => {
  // `0 0 1px <color>` means blur 1px; `0 0 0 1px <color>` means a 1px RING. Emitting a
  // spread without the blur slot would silently turn the ring into a blur — and the ring
  // idiom is in 4 of the 8 real values.
  assert.equal(formatShadowLayer({ x: "0", y: "0", blur: "", spread: "1px", color: "#000" }),
    "0 0 0 1px #000");
  assert.equal(formatShadowLayer({ x: "0", y: "0", blur: "2px", spread: "", color: "#000" }),
    "0 0 2px #000");
  assert.equal(formatShadowLayer({ x: "0", y: "1px" }), "0 1px");
  assert.equal(formatShadowLayer({ inset: true, x: "0", y: "0", blur: "4px", color: "#fff" }),
    "inset 0 0 4px #fff");
});
