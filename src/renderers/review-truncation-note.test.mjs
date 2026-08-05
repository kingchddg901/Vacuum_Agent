// Run: node --test src/renderers/review-truncation-note.test.mjs
//
// REV-5 — the run list is cut to `limit` (50) while the headline stat shows the
// count taken BEFORE the cut. So the panel read "127 runs" over a list of 50
// with nothing saying so, and a cap the user cannot see is indistinguishable
// from there being nothing more to see.
//
// Coverage (RTN = Run Truncation Note):
//   [RTN-1] truncated -> the note names BOTH numbers
//   [RTN-2] not truncated -> no note at all (no noise on the common path)
//   [RTN-3] the note falls back to the rendered row count if the payload omits one
//   [RTN-4] the renderer still gates on jobs_truncated

import { test } from "node:test";
import assert from "node:assert/strict";

/** The note predicate, transcribed from renderers/review.js. */
function note(summary, jobs = [], t = (k, v) => `${k}:${JSON.stringify(v)}`) {
  return summary?.jobs_truncated === true
    ? t("review.runs_truncated", {
        shown: Number(summary?.returned_job_count ?? jobs.length),
        total: Number(summary?.filtered_job_count ?? 0),
      })
    : "";
}

test("[RTN-1] a truncated list names both numbers", () => {
  const out = note({ jobs_truncated: true, returned_job_count: 50, filtered_job_count: 127 });
  assert.match(out, /review\.runs_truncated/);
  assert.match(out, /"shown":50/);
  assert.match(out, /"total":127/);
});

test("[RTN-2] an untruncated list shows no note", () => {
  for (const summary of [
    { jobs_truncated: false, filtered_job_count: 12 },
    { filtered_job_count: 12 },
    {},
    null,
  ]) {
    assert.equal(note(summary), "", `spurious note for ${JSON.stringify(summary)}`);
  }
});

test("[RTN-3] a missing returned_job_count falls back to the rendered rows", () => {
  // Forward-compat: an older backend that flags truncation without the new
  // count must still produce an honest note rather than "showing 0".
  const out = note({ jobs_truncated: true, filtered_job_count: 90 }, new Array(50));
  assert.match(out, /"shown":50/);
  assert.match(out, /"total":90/);
});

test("[RTN-4] the renderer still gates the note on jobs_truncated", async () => {
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("./review.js", import.meta.url), "utf-8");
  assert.match(src, /summary\?\.jobs_truncated === true/);
  assert.match(src, /review\.runs_truncated/);
});
