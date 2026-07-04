// Run: node --test src/renderers/mapping-review-outlier.test.mjs
//
// Coverage targets — computeJobBoundsOutlier (extracted from _renderJobBoundsEntry):
//   [MRO-1] outlier on each of the 4 sides (max_x / min_x / max_y / min_y)
//   [MRO-2] within-tolerance run is NOT flagged on any side
//   [MRO-3] the 10% tolerance is exclusive (> / <, not >= / <=) at the boundary
//   [MRO-4] no baseline: empty others / single-run / all-others-excluded → no flags
//   [MRO-5] excluded target run → short-circuit, no flags regardless of position
//   [MRO-6] union bbox spans ALL other runs (min of mins, max of maxes)
//   [MRO-7] isOutlier is the OR of the four side flags; multiple sides can co-flag

import { test } from "node:test";
import assert from "node:assert/strict";

import { computeJobBoundsOutlier } from "./mapping-review.js";

// A tight baseline whose span is exactly 100 on each axis → tolerance = 10 on each axis.
// Two runs so the union is unambiguous: [0..100] x [0..100].
const baseline = () => [
  { min_x: 0, max_x: 100, min_y: 0, max_y: 100 },
  { min_x: 0, max_x: 100, min_y: 0, max_y: 100 },
];

test("[MRO-1] flags an outlier on each side independently", () => {
  // max_x: 100 + 10 tolerance → boundary at 110; 111 exceeds.
  let f = computeJobBoundsOutlier({ min_x: 50, max_x: 111, min_y: 50, max_y: 60 }, baseline());
  assert.equal(f.max_x, true);
  assert.equal(f.min_x, false);
  assert.equal(f.max_y, false);
  assert.equal(f.min_y, false);
  assert.equal(f.isOutlier, true);

  // min_x: 0 - 10 tolerance → boundary at -10; -11 undershoots.
  f = computeJobBoundsOutlier({ min_x: -11, max_x: 50, min_y: 50, max_y: 60 }, baseline());
  assert.deepEqual(
    { max_x: f.max_x, min_x: f.min_x, max_y: f.max_y, min_y: f.min_y },
    { max_x: false, min_x: true, max_y: false, min_y: false },
  );

  // max_y: boundary at 110; 111 exceeds.
  f = computeJobBoundsOutlier({ min_x: 50, max_x: 60, min_y: 50, max_y: 111 }, baseline());
  assert.deepEqual(
    { max_x: f.max_x, min_x: f.min_x, max_y: f.max_y, min_y: f.min_y },
    { max_x: false, min_x: false, max_y: true, min_y: false },
  );

  // min_y: boundary at -10; -11 undershoots.
  f = computeJobBoundsOutlier({ min_x: 50, max_x: 60, min_y: -11, max_y: 60 }, baseline());
  assert.deepEqual(
    { max_x: f.max_x, min_x: f.min_x, max_y: f.max_y, min_y: f.min_y },
    { max_x: false, min_x: false, max_y: false, min_y: true },
  );
});

test("[MRO-2] a run comfortably inside every tolerance band is not an outlier", () => {
  // All edges well within [-10 .. 110] on both axes.
  const f = computeJobBoundsOutlier({ min_x: 5, max_x: 95, min_y: 20, max_y: 80 }, baseline());
  assert.equal(f.isOutlier, false);
  assert.equal(f.max_x, false);
  assert.equal(f.min_x, false);
  assert.equal(f.max_y, false);
  assert.equal(f.min_y, false);
});

test("[MRO-3] tolerance is strict/exclusive at the boundary", () => {
  // Exactly at the +10 / -10 boundary: NOT flagged (uses > and <, not >= / <=).
  let f = computeJobBoundsOutlier({ min_x: -10, max_x: 110, min_y: -10, max_y: 110 }, baseline());
  assert.equal(f.isOutlier, false, "edges landing exactly on the tolerance boundary are within tolerance");

  // A hair past the boundary: flagged.
  f = computeJobBoundsOutlier({ min_x: -10.0001, max_x: 110.0001, min_y: 50, max_y: 60 }, baseline());
  assert.equal(f.max_x, true);
  assert.equal(f.min_x, true);
  assert.equal(f.max_y, false);
  assert.equal(f.min_y, false);
  assert.equal(f.isOutlier, true);
});

test("[MRO-4] no baseline → never an outlier (empty, single-run, all-excluded)", () => {
  const wild = { min_x: -9999, max_x: 9999, min_y: -9999, max_y: 9999 };

  // Empty others.
  assert.equal(computeJobBoundsOutlier(wild, []).isOutlier, false);
  // Null/undefined others.
  assert.equal(computeJobBoundsOutlier(wild, null).isOutlier, false);
  assert.equal(computeJobBoundsOutlier(wild, undefined).isOutlier, false);
  // Others exist but every one is excluded → filtered to zero → no baseline.
  const allExcluded = [
    { min_x: 0, max_x: 100, min_y: 0, max_y: 100, excluded: true },
    { min_x: 0, max_x: 100, min_y: 0, max_y: 100, excluded: true },
  ];
  assert.equal(computeJobBoundsOutlier(wild, allExcluded).isOutlier, false);
});

test("[MRO-5] an excluded target run short-circuits to no flags", () => {
  const wild = { min_x: -9999, max_x: 9999, min_y: -9999, max_y: 9999, excluded: true };
  const f = computeJobBoundsOutlier(wild, baseline());
  assert.equal(f.isOutlier, false);
  assert.equal(f.max_x, false);
  assert.equal(f.min_x, false);
  assert.equal(f.max_y, false);
  assert.equal(f.min_y, false);
});

test("[MRO-6] baseline is the UNION bbox across all other active runs", () => {
  // Two disjoint-ish runs: union x = [0..200], y = [0..50]. Excluded run is ignored.
  const others = [
    { min_x: 0,   max_x: 100, min_y: 0,  max_y: 50 },
    { min_x: 150, max_x: 200, min_y: 10, max_y: 40 },
    { min_x: -500, max_x: 500, min_y: -500, max_y: 500, excluded: true }, // ignored
  ];
  // Union: x span = 200 → tX = 20 (boundary +220 / -20); y span = 50 → tY = 5 (boundary +55 / -5).
  // A run reaching x=215 is within +220 (not flagged); reaching y=56 exceeds +55 (flagged).
  const f = computeJobBoundsOutlier({ min_x: 5, max_x: 215, min_y: 5, max_y: 56 }, others);
  assert.equal(f.max_x, false, "215 < union max_x(200)+tX(20)=220 → within tolerance");
  assert.equal(f.max_y, true, "56 > union max_y(50)+tY(5)=55 → outlier");
  assert.equal(f.min_x, false);
  assert.equal(f.min_y, false);
  assert.equal(f.isOutlier, true);
});

test("[MRO-7] isOutlier is the OR of the four side flags; sides co-flag", () => {
  // Baseline union [0..100]x[0..100], tol 10. This run blows past THREE edges at once:
  //   max_x: 200 > 110 ✓   min_x: -50 < -10 ✓   min_y: -50 < -10 ✓   max_y: 60 < 110 ✗
  const f = computeJobBoundsOutlier({ min_x: -50, max_x: 200, min_y: -50, max_y: 60 }, baseline());
  assert.equal(f.max_x, true);
  assert.equal(f.min_x, true);
  assert.equal(f.min_y, true);
  assert.equal(f.max_y, false, "max_y=60 stays under the +110 boundary");
  assert.equal(f.isOutlier, true, "isOutlier ORs the side flags");

  // And when every side is within tolerance, isOutlier is false (the OR bottoms out).
  const clean = computeJobBoundsOutlier({ min_x: 10, max_x: 90, min_y: 10, max_y: 90 }, baseline());
  assert.equal(clean.isOutlier, false);
});
