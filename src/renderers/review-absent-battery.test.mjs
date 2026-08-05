// Run: node --test src/renderers/review-absent-battery.test.mjs
//
// REV-6 — every externally-captured run rendered "Battery 0". External records
// carry no battery block (history_store writes {"start":…, "end":None,
// "used":None}), stats_rebuilder folded that to 0.0, and the card's isFinite
// guard passed it through as a confident zero.
//
// Coverage (RAB = Review Absent Battery):
//   [RAB-1] a real battery figure still renders
//   [RAB-2] null / undefined omit the stat entirely — never "Battery 0"
//   [RAB-3] a genuine measured 0 DOES render (the value is real, not absent)
//   [RAB-4] the renderer still guards null BEFORE the finite check

import { test } from "node:test";
import assert from "node:assert/strict";

/** The detail-line predicate, transcribed from renderers/review.js. */
function batteryPart(job, t = (k, v) => `${k}(${v.value})`) {
  return job?.battery_used != null && Number.isFinite(Number(job.battery_used))
    ? t("review.detail_battery", { value: Number(job.battery_used) })
    : "";
}

test("[RAB-1] a real battery figure renders", () => {
  assert.equal(batteryPart({ battery_used: 23 }), "review.detail_battery(23)");
});

test("[RAB-2] absent battery omits the stat, never 'Battery 0'", () => {
  // The whole finding: these are what an externally-captured run carries.
  assert.equal(batteryPart({ battery_used: null }), "");
  assert.equal(batteryPart({ battery_used: undefined }), "");
  assert.equal(batteryPart({}), "");
});

test("[RAB-3] a genuine measured zero still renders", () => {
  // The guard must distinguish "measured 0" from "not measured". A run that
  // really consumed nothing is a fact worth showing; suppressing it would trade
  // one wrong render for another.
  assert.equal(batteryPart({ battery_used: 0 }), "review.detail_battery(0)");
});

test("[RAB-4] the renderer still guards null BEFORE the finite check", async () => {
  // Order is the fix: Number(null) is 0, which IS finite, so isFinite alone
  // passes an absent value through. A refactor that reorders these re-opens the
  // bug silently.
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("./review.js", import.meta.url), "utf-8");
  assert.match(src, /job\?\.battery_used != null && Number\.isFinite/);
});
