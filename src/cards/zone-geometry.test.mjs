// Unit tests for the card's pure zone-clean geometry. Ported from the panel's
// src/state/zone-draft.test.mjs (the math is lifted verbatim) so the card's reuse is
// proven independently. Verified against the real X10 camera (360x301).
// Run: node --test src/cards/zone-geometry.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  rectToNormalized, draftsToNormalizedRects, unrotatePct, normRotation,
} from "./zone-geometry.js";

const approx = (a, b, eps = 1e-3) => Math.abs(a - b) <= eps;

test("[ZG-1] square image: pct maps straight to normalized (no letterbox)", () => {
  const r = rectToNormalized({ x: 25, y: 40, w: 25, h: 20 }, { width: 500, height: 500 });
  assert.deepEqual(r.map((v) => +v.toFixed(4)), [0.25, 0.4, 0.5, 0.6]);
});

test("[ZG-2] wide image (360x301): a rect over the contained image -> full [0,0,1,1]", () => {
  const r = rectToNormalized({ x: 0, y: 8.194444, w: 100, h: 83.611111 }, { width: 360, height: 301 });
  assert.ok(approx(r[0], 0) && approx(r[1], 0));
  assert.ok(approx(r[2], 1) && approx(r[3], 1));
});

test("[ZG-3] wide image: X maps directly, Y is letterbox-corrected", () => {
  const r = rectToNormalized({ x: 20, y: 50, w: 20, h: 20 }, { width: 360, height: 301 });
  assert.ok(approx(r[0], 0.2));
  assert.ok(approx(r[1], 0.5, 2e-3));
});

test("[ZG-4] tall image (300x400) letterboxes horizontally", () => {
  const r = rectToNormalized({ x: 12.5, y: 0, w: 20, h: 20 }, { width: 300, height: 400 });
  assert.ok(approx(r[0], 0) && approx(r[1], 0));
});

test("[ZG-5] corners clamp to [0,1] and order min<max regardless of drag direction", () => {
  const r = rectToNormalized({ x: 90, y: 95, w: -120, h: -120 }, { width: 360, height: 301 });
  assert.ok(r[0] >= 0 && r[1] >= 0 && r[2] <= 1 && r[3] <= 1);
  assert.ok(r[0] <= r[2] && r[1] <= r[3]);
});

test("[ZG-6] no rect or bad dims -> null", () => {
  assert.equal(rectToNormalized(null, { width: 360, height: 301 }), null);
  assert.equal(rectToNormalized({ x: 0, y: 0, w: 10, h: 10 }, null), null);
  assert.equal(rectToNormalized({ x: 0, y: 0, w: 10, h: 10 }, { width: 0, height: 0 }), null);
});

test("[ZG-7] a rect drawn entirely inside a letterbox bar -> null (degenerate)", () => {
  assert.equal(rectToNormalized({ x: 20, y: 0, w: 30, h: 5 }, { width: 360, height: 301 }), null);
});

test("[ZG-8] draftsToNormalizedRects converts all + drops degenerate", () => {
  const drafts = [
    { x: 25, y: 40, w: 25, h: 20 }, // valid
    { x: 20, y: 0, w: 30, h: 5 },   // degenerate (top letterbox bar)
  ];
  const rects = draftsToNormalizedRects(drafts, { width: 360, height: 301 }, 0);
  assert.equal(rects.length, 1);
  assert.equal(rects[0].length, 4);
});

test("[ZG-9] draftsToNormalizedRects un-rotates the drawn rect at 90deg", () => {
  // unrotatePct(.,.,90)=[fy,100-fx]: (25,40)->(40,75), (50,60)->(60,50) ->
  // {x:40,y:50,w:20,h:25} -> square 500 normalized [0.4,0.5,0.6,0.75].
  const [r] = draftsToNormalizedRects([{ x: 25, y: 40, w: 25, h: 20 }], { width: 500, height: 500 }, 90);
  assert.ok(approx(r[0], 0.4) && approx(r[1], 0.5));
  assert.ok(approx(r[2], 0.6) && approx(r[3], 0.75));
});

test("[ZG-10] unrotatePct: 0/90/180/270 corner mapping", () => {
  assert.deepEqual(unrotatePct(25, 40, 0), [25, 40]);
  assert.deepEqual(unrotatePct(25, 40, 90), [40, 75]);
  assert.deepEqual(unrotatePct(25, 40, 180), [75, 60]);
  assert.deepEqual(unrotatePct(25, 40, 270), [60, 25]);
});

test("[ZG-11] normRotation snaps to the nearest quarter turn", () => {
  assert.equal(normRotation(0), 0);
  assert.equal(normRotation(89), 90);
  assert.equal(normRotation(-90), 270);
  assert.equal(normRotation(360), 0);
  assert.equal(normRotation(405), 90);
});
