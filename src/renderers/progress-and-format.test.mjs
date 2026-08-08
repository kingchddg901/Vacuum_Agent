// Regression tests — two renderers that showed the user a plainly wrong thing.
//
// [FE-LRN-1] The live-progress list dispatched on completed/current and then had an
//   all-flags-false CATCH-ALL that routed the entry into the CURRENT row. A backend-flagged
//   SKIPPED room has all three false, so it rendered as "▶ <Room>" in the actively-cleaning
//   style — several rows at once claiming to be the room under the robot. The sibling
//   queue-chip surface already read `entry.skipped`; this list never did.
//
// [FE-MET-1] numFmt trimmed trailing zeros with /\.?0+$/. The dot is OPTIONAL there, so on
//   a whole number it ate the number's own trailing zeros: 100 -> "1", 90 -> "9", 20 -> "2",
//   and 0 -> "" (a blank cell). Battery health rendered an order of magnitude wrong.
//
// Run: node --test src/renderers/progress-and-format.test.mjs
//
// Coverage (PF = Progress/Format):
//   [PF-1] a skipped entry does NOT render as the current row
//   [PF-2] a skipped entry is marked skipped and carries no ETA
//   [PF-3] an unclassifiable entry falls to REMAINING, not current
//   [PF-4] a genuinely current entry still renders as current
//   [PF-5] numFmt preserves whole numbers (100/90/20) and zero
//   [PF-6] numFmt still trims real fractional zeros

import { test } from "node:test";
import assert from "node:assert/strict";

// The formatter under test, mirrored exactly from src/renderers/metrics.js.
const numFmt = (raw, digits = 2) => {
  const n = Number(raw);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(digits).replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
};

// Minimal harness for the row dispatch in src/renderers/learning.js.
function dispatch(entry) {
  if (entry.completed) return "completed";
  if (entry.current) return "current";
  if (entry.skipped) return "remaining:skipped";
  return "remaining";
}

test("[PF-1] a skipped entry does not render as the current row", () => {
  const row = dispatch({ completed: false, current: false, remaining: false, skipped: true });
  assert.notEqual(row, "current", "a skipped room was shown as currently cleaning");
});

test("[PF-2] a skipped entry is marked skipped", () => {
  assert.equal(
    dispatch({ completed: false, current: false, remaining: false, skipped: true }),
    "remaining:skipped"
  );
});

test("[PF-3] an unclassifiable entry falls to remaining, not current", () => {
  // All flags false and NOT skipped — the old catch-all sent this to the current row.
  assert.equal(dispatch({ completed: false, current: false, remaining: false }), "remaining");
});

test("[PF-4] a genuinely current entry still renders as current", () => {
  assert.equal(dispatch({ current: true }), "current");
});

test("[PF-5] numFmt preserves whole numbers and zero", () => {
  assert.equal(numFmt(100, 0), "100", "battery health rendered an order of magnitude wrong");
  assert.equal(numFmt(90, 0), "90");
  assert.equal(numFmt(20, 0), "20");
  assert.equal(numFmt(0, 0), "0", "zero rendered as an empty cell");
});

test("[PF-6] numFmt still trims real fractional zeros", () => {
  assert.equal(numFmt(12.5, 2), "12.5");
  assert.equal(numFmt(3.0, 2), "3");
  assert.equal(numFmt(3.14159, 2), "3.14");
  assert.equal(numFmt("nope", 2), "—");
});

// [PF-7]/[PF-8] SOURCE PINS — added 2026-08-07 by the W0 v2 census.
//
// Everything above asserts the `numFmt` and `dispatch` copies declared at the top
// of THIS file. Both are faithful transcriptions, and both prove nothing about the
// shipped renderers: the real numFmt is a closure inside _renderMetricsBatteryTab
// (renderers/metrics.js), the real dispatch is an inline if-chain in
// renderers/learning.js, and neither is exported or referenced by any assertion
// here. Measured: restoring the FE-MET-1 regex in metrics.js leaves this whole
// file green while battery health renders "1" for 100 and a BLANK cell for 0.
//
// Both defects are shape/ordering facts visible in source, so pin them the way
// [C6-4] does in maintenance-census6.test.mjs. Substring checks rather than
// regexes-matching-regexes: the pattern being pinned is itself full of
// metacharacters, and an over-escaped matcher fails for reasons that have nothing
// to do with the code — which is exactly what happened on the first attempt.
test("[PF-7] the SHIPPED numFmt still requires a dot before trimming zeros", async () => {
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("./metrics.js", import.meta.url), "utf-8");

  assert.ok(
    src.includes('.replace(/(\\.\\d*?)0+$/, "$1")'),
    "numFmt's fractional-zero trim changed shape. The dot must be MANDATORY and inside "
    + "the capture; if it becomes optional again the trim eats the trailing zero DIGITS "
    + "of whole numbers (FE-MET-1: 100 -> '1', 90 -> '9', 0 -> blank).",
  );
  // Anchored on `.replace(`, NOT on the bare pattern. metrics.js DOCUMENTS the old
  // regex in a comment ("The previous pattern was /\.?0+$/, whose optional dot…"),
  // so a bare substring check flags the prose that explains the fix and fails
  // identically before and after the mutation — measuring nothing, which is the
  // very defect class this pin was added to close. Same trap that forced
  // scripts/mock_census.py off regexes and onto an AST.
  assert.ok(
    !src.includes(".replace(/\\.?0+$/"),
    "the FE-MET-1 regex is back in a live .replace() call in metrics.js — its optional "
    + "dot eats the trailing zeros of WHOLE numbers",
  );
});

test("[PF-8] the SHIPPED timeline dispatch still tests `skipped` before the catch-all", async () => {
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("./learning.js", import.meta.url), "utf-8");

  const iCurrent = src.indexOf("entry.current");
  const iSkipped = src.indexOf("entry.skipped");
  assert.ok(iCurrent > 0, "the `entry.current` branch is gone from learning.js");
  assert.ok(iSkipped > 0, "the `entry.skipped` branch is gone from learning.js");
  // ORDER is the contract. With `skipped` removed or moved below the catch-all, a
  // skipped room falls through to the CURRENT row, and during an out-of-order run
  // the list shows several rooms at once marked as actively cleaning.
  assert.ok(
    iSkipped > iCurrent,
    "`entry.skipped` no longer follows `entry.current` in the dispatch chain",
  );
  assert.ok(
    /_renderLearningRemainingRow\(\s*entry\s*,\s*\{\s*skipped:\s*true\s*\}\s*\)/.test(src),
    "a skipped entry no longer routes to the REMAINING row — the all-flags-false "
    + "catch-all will render it as the currently-cleaning room",
  );
});

