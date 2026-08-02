import { test } from "node:test";
import assert from "node:assert/strict";
import { confidenceTooltip } from "./rooms.js";

/* ---- confidenceTooltip (CARD-2 clause 3) ---------------------------------- */

function fakeT(key, vars) {
  assert.equal(key, "rooms.trust_tooltip_with_samples");
  return `${vars.label} · ${vars.count} samples`;
}

test("[CFT-1] finite sample count folds into the tooltip via the samples key", () => {
  assert.equal(confidenceTooltip("Reliable", 12, fakeT), "Reliable · 12 samples");
});

test("[CFT-2] sample count of 0 still renders (a real, finite count) rather than being dropped", () => {
  assert.equal(confidenceTooltip("Uncertain", 0, fakeT), "Uncertain · 0 samples");
});

test("[CFT-3] a numeric string count coerces the same as a number", () => {
  assert.equal(confidenceTooltip("Learning", "4", fakeT), "Learning · 4 samples");
});

test("[CFT-4] missing/non-finite sample count falls back to the plain label, untranslated", () => {
  const t = () => { throw new Error("t() must not be called when there is no count"); };
  assert.equal(confidenceTooltip("Reliable", undefined, t), "Reliable");
  assert.equal(confidenceTooltip("Reliable", null, t), "Reliable");
  assert.equal(confidenceTooltip("Reliable", NaN, t), "Reliable");
  assert.equal(confidenceTooltip("Reliable", "not-a-number", t), "Reliable");
});
