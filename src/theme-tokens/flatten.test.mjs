// [TFB] THEME ENVELOPE FLATTEN — tokens / colors / alpha -> one CSS-ready map.
//
// The rule under test: `alpha[k]` COMPOSES onto `colors[k]`; it never replaces
// it. Every case below goes RED against the concatenation this module replaced
// (`{...tokens, ...colors, ...alpha}`), which resolved a paired key to the bare
// number — a value CSS accepts as "defined" and then discards, so the built-in
// default painted and nothing was reported.
//
// Run: node --test src/theme-tokens/flatten.test.mjs   (or npm run test:units)

import { test } from "node:test";
import assert from "node:assert/strict";

import { flattenThemeBuckets, hexWithAlpha, alphaApplies } from "./flatten.js";

/* =========================================================
   COMPOSE — the defect
   ========================================================= */

test("[TFB-1] a paired key composes into 8-digit hex, it does not become the alpha", () => {
  // The reported case: --evcc-text-secondary #F4EBD8 @ 0.9.
  const { bundle, composed } = flattenThemeBuckets({
    colors: { "--evcc-text-secondary": "#F4EBD8" },
    alpha: { "--evcc-text-secondary": 0.9 },
  });
  // 0.9 * 255 = 229.5 -> round 230 -> 0xe6.
  assert.equal(bundle["--evcc-text-secondary"], "#F4EBD8e6");
  assert.deepEqual(composed, ["--evcc-text-secondary"]);
});

test("[TFB-2] no paired key ever resolves to a bare number", () => {
  // RED under concatenation: every one of these came out as "0.16"/"0.9"/…,
  // which is not a colour — and `var()` still counted the property as defined.
  const colors = {};
  const alpha = {};
  for (const [i, a] of [0.16, 0.42, 0.7, 0.9, 1].entries()) {
    colors[`--evcc-k${i}`] = "#112233";
    alpha[`--evcc-k${i}`] = a;
  }
  const { bundle, unappliedAlpha } = flattenThemeBuckets({ colors, alpha });
  for (const [key, value] of Object.entries(bundle)) {
    assert.match(value, /^#[0-9a-fA-F]{8}$/, `${key} should be a colour, got ${value}`);
    assert.ok(Number.isNaN(Number(value)), `${key} must not be numeric`);
  }
  assert.deepEqual(unappliedAlpha, []);
});

test("[TFB-3] alpha 0 composes (falsy, but a real value — not 'no alpha')", () => {
  const { bundle, composed } = flattenThemeBuckets({
    colors: { "--evcc-a": "#010203" },
    alpha: { "--evcc-a": 0 },
  });
  assert.equal(bundle["--evcc-a"], "#01020300");
  assert.deepEqual(composed, ["--evcc-a"]);
});

/* =========================================================
   BUCKET PRECEDENCE
   ========================================================= */

test("[TFB-4] colors beats a pre-baked tokens value, so an alpha-only change re-bakes", () => {
  const { bundle } = flattenThemeBuckets({
    tokens: { "--evcc-a": "#aabbccff", "--evcc-gap": "14px" },
    colors: { "--evcc-a": "#aabbcc" },
    alpha: { "--evcc-a": 0.5 },
  });
  assert.equal(bundle["--evcc-a"], "#aabbcc80"); // NOT the stale #aabbccff
  assert.equal(bundle["--evcc-gap"], "14px");    // token-only keys pass through
});

test("[TFB-5] an unpaired colour is left exactly as authored (8-digit hex included)", () => {
  const { bundle, composed, unappliedAlpha } = flattenThemeBuckets({
    colors: { "--evcc-a": "#00FF00", "--evcc-b": "#00FF0080" },
  });
  assert.equal(bundle["--evcc-a"], "#00FF00");
  assert.equal(bundle["--evcc-b"], "#00FF0080");
  assert.deepEqual(composed, []);
  assert.deepEqual(unappliedAlpha, []);
});

/* =========================================================
   ALPHA THAT REACHES NOTHING — reported, never written
   ========================================================= */

test("[TFB-6] an orphan alpha (no colour for that key) is dropped AND named", () => {
  const { bundle, unappliedAlpha } = flattenThemeBuckets({
    tokens: { "--evcc-gap": "14px" },
    alpha: { "--evcc-orphan": 0.76 },
  });
  assert.ok(!("--evcc-orphan" in bundle), "a bare 0.76 must never enter the bundle");
  assert.deepEqual(unappliedAlpha, ["--evcc-orphan"]);
});

test("[TFB-7] alpha on a base no alpha can bake into is reported, not silently lost", () => {
  // rgb()/color-mix() bases pass through unchanged — correct, but the author's
  // alpha vanished, and that used to be invisible.
  const { bundle, composed, unappliedAlpha } = flattenThemeBuckets({
    colors: { "--evcc-a": "rgb(1,2,3)", "--evcc-b": "color-mix(in srgb, red, blue)" },
    alpha: { "--evcc-a": 0.5, "--evcc-b": 0.5 },
  });
  assert.equal(bundle["--evcc-a"], "rgb(1,2,3)");
  assert.equal(bundle["--evcc-b"], "color-mix(in srgb, red, blue)");
  assert.deepEqual(composed, []);
  assert.deepEqual(unappliedAlpha.sort(), ["--evcc-a", "--evcc-b"]);
});

test("[TFB-8] a non-numeric alpha is reported unapplied and leaves the colour intact", () => {
  const { bundle, unappliedAlpha } = flattenThemeBuckets({
    colors: { "--evcc-a": "#112233" },
    alpha: { "--evcc-a": "nope" },
  });
  assert.equal(bundle["--evcc-a"], "#112233");
  assert.deepEqual(unappliedAlpha, ["--evcc-a"]);
});

test("[TFB-9] the report distinguishes 'nothing to do' from 'nothing done'", () => {
  // The ablation this suite exists for: an all-empty report must be reachable
  // ONLY when there is genuinely no alpha, so a populated `composed` is real
  // evidence rather than a constant.
  const none = flattenThemeBuckets({ colors: { "--evcc-a": "#112233" } });
  assert.deepEqual(none.composed, []);
  assert.deepEqual(none.unappliedAlpha, []);

  const some = flattenThemeBuckets({
    colors: { "--evcc-a": "#112233" },
    alpha: { "--evcc-a": 0.5 },
  });
  assert.deepEqual(some.composed, ["--evcc-a"]);
});

/* =========================================================
   MALFORMED INPUT — data, never trusted
   ========================================================= */

test("[TFB-10] absent / malformed buckets are ignored without throwing", () => {
  for (const theme of [undefined, {}, null, { tokens: null, colors: "x", alpha: 5 }, { colors: [] }]) {
    const { bundle, composed, unappliedAlpha } = flattenThemeBuckets(theme);
    assert.deepEqual(bundle, {}, `bundle for ${JSON.stringify(theme)}`);
    assert.deepEqual(composed, []);
    assert.deepEqual(unappliedAlpha, []);
  }
});

/* =========================================================
   PRIMITIVES
   ========================================================= */

test("[TFB-11] hexWithAlpha: re-bases an 8-digit hex, clamps out of range, passes non-hex", () => {
  assert.equal(hexWithAlpha("#112233ff", 1), "#112233ff"); // existing alpha stripped, new applied
  assert.equal(hexWithAlpha("#112233ff", 0), "#11223300");
  assert.equal(hexWithAlpha("#112233", 5), "#112233ff");   // clamped high
  assert.equal(hexWithAlpha("#112233", -2), "#11223300");  // clamped low
  assert.equal(hexWithAlpha("#112233", "nope"), "#112233"); // NaN -> unchanged
  assert.equal(hexWithAlpha("#112233", null), "#112233");   // no alpha -> unchanged
  assert.equal(hexWithAlpha("  #112233  ", null), "#112233"); // trimmed
  assert.equal(hexWithAlpha("rgb(1,2,3)", 0.5), "rgb(1,2,3)");
  assert.equal(hexWithAlpha("", 0.5), "");
});

test("[TFB-12] alphaApplies answers what hexWithAlpha's return value cannot", () => {
  // Baking 1.0 onto an already-opaque hex is a no-op by VALUE but did apply;
  // comparing input to output would mis-report it, which is why the predicate
  // is structural.
  assert.equal(alphaApplies("#112233ff", 1), true);
  assert.equal(alphaApplies("#112233", 0), true);
  assert.equal(alphaApplies("#112233", null), false);
  assert.equal(alphaApplies("#112233", undefined), false);
  assert.equal(alphaApplies("#112233", "nope"), false);
  assert.equal(alphaApplies("rgb(1,2,3)", 0.5), false);
  assert.equal(alphaApplies("#1122", 0.5), false); // 4-digit hex is not a base we bake
  assert.equal(alphaApplies("", 0.5), false);
});
