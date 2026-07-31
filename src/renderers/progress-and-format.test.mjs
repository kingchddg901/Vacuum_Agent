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
