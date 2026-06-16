// Unit tests for unrotatePct — maps a pointer position (0-100 pct of the unrotated
// .evcc-map-layers box) into the CONTENT frame inside the rotated
// .evcc-map-content-rotator, so the mascot drag lands/stores correctly on a rotated
// live map. Run: node --test src/state/map-rotation.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyMapState } from "./map.js";

function makeState() {
  const proto = {};
  applyMapState(proto);
  return Object.create(proto);
}

test("[MR-1] rot 0 is identity", () => {
  const s = makeState();
  assert.deepEqual(s.unrotatePct(30, 70, 0), [30, 70]);
  assert.deepEqual(s.unrotatePct(50, 50, 0), [50, 50]);   // centre invariant
});

test("[MR-2] rot 90 (CW): screen top-right -> content top-left; centre invariant", () => {
  const s = makeState();
  assert.deepEqual(s.unrotatePct(90, 10, 90), [10, 10]);
  assert.deepEqual(s.unrotatePct(50, 50, 90), [50, 50]);
});

test("[MR-3] rot 180 mirrors both axes", () => {
  const s = makeState();
  assert.deepEqual(s.unrotatePct(30, 70, 180), [70, 30]);
});

test("[MR-4] rot 270: screen top-right -> content bottom-right", () => {
  const s = makeState();
  assert.deepEqual(s.unrotatePct(90, 10, 270), [90, 90]);
});

test("[MR-5] an odd / out-of-range angle normalizes to the nearest 90", () => {
  const s = makeState();
  assert.deepEqual(s.unrotatePct(90, 10, 95), [10, 10]);   // 95 -> 90
  assert.deepEqual(s.unrotatePct(30, 70, 360), [30, 70]);  // 360 -> 0 (identity)
});
