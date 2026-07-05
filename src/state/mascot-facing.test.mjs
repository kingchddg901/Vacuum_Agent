import { test } from "node:test";
import assert from "node:assert/strict";
import { mascotFacingSign, commitFacing } from "./mascot-facing.js";

/* ---- mascotFacingSign ------------------------------------------------------ */

test("[MF-1] rot 0: +dnx => screen-right (+1), -dnx => screen-left (-1)", () => {
  assert.equal(mascotFacingSign(0.05, 0, 0), 1);
  assert.equal(mascotFacingSign(-0.05, 0, 0), -1);
});

test("[MF-2] deadband: sub-threshold horizontal motion => 0 (hold last facing)", () => {
  assert.equal(mascotFacingSign(0.001, 0, 0), 0);      // < default 0.004
  assert.equal(mascotFacingSign(0, 0, 0), 0);          // stationary
  assert.equal(mascotFacingSign(0.001, 0, 0, 0.0005), 1); // tighter deadband catches it
});

test("[MF-3] rot 90: pure-horizontal content motion projects to VERTICAL screen => 0", () => {
  // At 90deg, content +x moves screen-down; no horizontal component -> deadband.
  assert.equal(mascotFacingSign(0.05, 0, 90), 0);
  // ...and content +y (down) becomes screen-LEFT: screen_dx = -dny*sin(90) = -0.05 -> -1.
  assert.equal(mascotFacingSign(0, 0.05, 90), -1);
  assert.equal(mascotFacingSign(0, -0.05, 90), 1);
});

test("[MF-4] rot 180 inverts screen-horizontal", () => {
  assert.equal(mascotFacingSign(0.05, 0, 180), -1);
  assert.equal(mascotFacingSign(-0.05, 0, 180), 1);
});

test("[MF-5] non-finite deltas are safe (=> 0)", () => {
  assert.equal(mascotFacingSign(NaN, 0, 0), 0);
  assert.equal(mascotFacingSign(0.05, Infinity, 0), 0);
});

/* ---- commitFacing (boustrophedon debounce) --------------------------------- */

const START = { committed: 1, cand: 0, count: 0 };

test("[MF-6] a single opposite sample does NOT flip (needs 2 consecutive)", () => {
  const next = commitFacing(START, -1);
  assert.equal(next.committed, 1);   // still facing right
  assert.equal(next.count, 1);       // streak building
});

test("[MF-7] two consecutive opposite samples flip", () => {
  const a = commitFacing(START, -1);
  const b = commitFacing(a, -1);
  assert.equal(b.committed, -1);
});

test("[MF-8] a back-and-forth wobble never flips (the vacuum boustrophedon case)", () => {
  let t = START;
  for (const s of [-1, 1, -1, 1, -1, 1]) t = commitFacing(t, s);
  assert.equal(t.committed, 1);      // survived the wobble unflipped
});

test("[MF-9] deadband (0) and same-direction samples reset the candidate streak", () => {
  const a = commitFacing(START, -1);       // count 1 toward left
  const b = commitFacing(a, 0);            // deadband -> reset
  assert.equal(b.count, 0);
  const c = commitFacing(b, 1);            // same as committed -> reset
  assert.equal(c.committed, 1);
  assert.equal(c.count, 0);
});

test("[MF-10] hold=1 flips immediately (no debounce)", () => {
  assert.equal(commitFacing(START, -1, 1).committed, -1);
});
