// Run: node --test src/renderers/review-error-badge.test.mjs
//
// Backlog item "Card: surface captured run errors (run_errors)". The backend has
// carried error evidence end to end for both origins — the dispatched finalizer
// and the app-started ingest write the SAME keys onto `outcome` on purpose — and
// nothing displayed it. A run that hit a fault looked identical in the review
// list to one that ran clean.
//
// Coverage (REB = REview error Badge):
//   [REB-1] had_errors with a count -> a warning badge naming the count
//   [REB-2] had_errors with no usable count -> the countless fallback badge
//   [REB-3] a measured duration rides the TOOLTIP, not the badge text
//   [REB-4] an UNMEASURED duration produces no tooltip — never "0s"
//   [REB-5] a clean run gets no badge at all (control)

import { test } from "node:test";
import assert from "node:assert/strict";

/** Minimal renderer host: only what the badge block touches. */
function badgesFor(job) {
  const pushed = [];
  const host = {
    t: (key, vars = {}) =>
      `${key}${Object.keys(vars).length ? `(${JSON.stringify(vars)})` : ""}`,
  };

  // The block under test, transcribed from renderers/review.js. Kept in step by
  // [REB-6] below, which asserts the source still contains it.
  if (job?.had_errors === true) {
    const errorCount = Number(job?.error_count);
    const errorSeconds = Number(job?.total_error_seconds);
    pushed.push({
      text: Number.isFinite(errorCount) && errorCount > 0
        ? host.t("review.badge_errors_count", { count: errorCount })
        : host.t("review.badge_errors"),
      cls: "evcc-review-badge--warning",
      title: Number.isFinite(errorSeconds) && errorSeconds > 0
        ? host.t("review.badge_errors_seconds", { seconds: Math.round(errorSeconds) })
        : null,
    });
  }
  return pushed;
}

test("[REB-1] a run with errors gets a warning badge naming the count", () => {
  const [badge] = badgesFor({ had_errors: true, error_count: 3 });
  assert.ok(badge, "a run that hit faults rendered identically to a clean one");
  assert.equal(badge.cls, "evcc-review-badge--warning");
  assert.match(badge.text, /badge_errors_count/);
  assert.match(badge.text, /"count":3/);
});

test("[REB-2] errors with no usable count fall back to the countless badge", () => {
  for (const job of [
    { had_errors: true },
    { had_errors: true, error_count: 0 },
    { had_errors: true, error_count: null },
  ]) {
    const [badge] = badgesFor(job);
    assert.ok(badge, `no badge for ${JSON.stringify(job)}`);
    assert.equal(badge.text, "review.badge_errors");
  }
});

test("[REB-3] a measured duration rides the tooltip, not the badge text", () => {
  const [badge] = badgesFor({ had_errors: true, error_count: 2, total_error_seconds: 41.6 });
  assert.match(badge.text, /badge_errors_count/, "the duration leaked into the badge label");
  assert.match(badge.title, /badge_errors_seconds/);
  assert.match(badge.title, /"seconds":42/, "seconds should be rounded for display");
});

test("[REB-4] an UNMEASURED duration produces no tooltip, never 0s", () => {
  // The app-started ingest omits total_error_seconds deliberately — it has no
  // per-phase timings to derive it from. Rendering "0s" would assert the run
  // spent no time in error, a stronger claim than "we did not measure it".
  for (const job of [
    { had_errors: true, error_count: 1 },
    { had_errors: true, error_count: 1, total_error_seconds: null },
    { had_errors: true, error_count: 1, total_error_seconds: 0 },
  ]) {
    const [badge] = badgesFor(job);
    assert.equal(badge.title, null, `unmeasured duration rendered: ${JSON.stringify(job)}`);
  }
});

test("[REB-5] a clean run gets no badge (control)", () => {
  for (const job of [
    { had_errors: false, error_count: 0 },
    {},
    { had_errors: "false" },      // string, not the boolean the backend sends
  ]) {
    assert.deepEqual(badgesFor(job), [], `spurious badge for ${JSON.stringify(job)}`);
  }
});

test("[REB-6] the renderer still contains the block this file transcribes", async () => {
  // A transcribed block can drift from its original silently. This is the cheap
  // guard: the real source must still push the badge on had_errors, and must
  // still gate the tooltip on a finite positive duration.
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("./review.js", import.meta.url), "utf-8");

  assert.match(src, /job\?\.had_errors === true/);
  assert.match(src, /review\.badge_errors_count/);
  assert.match(src, /Number\.isFinite\(errorSeconds\) && errorSeconds > 0/);
});
