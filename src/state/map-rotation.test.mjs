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

/* =========================================================
   C31 — the frame a drawn zone is un-rotated in
   ========================================================= */

// The divergence state: a VA render is WANTED (useVaRender && supportsVaRender)
// but is NOT active, while a live image is present and the user has turned the
// map. effectiveMapRotation() resolves to 0 — the panel draws the backdrop
// unrotated — but mapRotation() still reports the user's 90.
function divergentState({ rotation = 90 } = {}) {
  const proto = {};
  applyMapState(proto);
  const s = Object.create(proto);
  s.dashboardSnapshot = () => ({ live_map_rotation: rotation });
  s.isVaRenderActive = () => false;      // raster absent
  s.liveMapImageEntity = () => "image.alfred_live_map";
  s.useVaRender = () => true;            // ...but VA is wanted
  s.supportsVaRender = () => true;
  s.zoneDrafts = () => [{ x: 60, y: 10, w: 20, h: 20 }];
  return s;
}

test("[MR-6] the divergence state is real: effective is 0 while raw reports 90", () => {
  const s = divergentState();
  assert.equal(s.mapRotation(), 90, "raw rotation still carries the user's turn");
  assert.equal(s.effectiveMapRotation(), 0,
    "VA wanted but absent renders UNROTATED — this is the frame the user drew on");
});

test("[MR-7] C31: a zone drawn on the unrotated display dispatches where it was drawn", () => {
  // The bite. Reading raw mapRotation() here un-rotates by 90 a rect that was
  // never rotated on screen, sending the robot a quarter-turn away. Square
  // backdrop so the letterbox transform is identity and ONLY the rotation
  // choice can move the numbers.
  const s = divergentState();
  const rects = s.zoneDraftsToNormalizedRects({ width: 1000, height: 1000 });
  assert.equal(rects.length, 1);
  // Drawn at x 60-80, y 10-30 of a square box -> normalized straight through.
  assert.deepEqual(
    rects[0].map((v) => Number(v.toFixed(4))),
    [0.6, 0.1, 0.8, 0.3],
    "the dispatched rect must match the drawn rect; a 90 un-rotation would yield [0.1,0.2,0.3,0.4]",
  );
});

test("[MR-8] when the display IS rotated, the un-rotation still happens", () => {
  // Guards the other direction: the fix must not disable un-rotation for the
  // case it was written for. VA ACTIVE -> effectiveMapRotation follows the raw
  // value, so a rect drawn on the turned display is un-rotated back to content.
  const proto = {};
  applyMapState(proto);
  const s = Object.create(proto);
  s.dashboardSnapshot = () => ({ live_map_rotation: 90 });
  s.isVaRenderActive = () => true;                  // raster present -> rotation applies
  s.zoneDrafts = () => [{ x: 60, y: 10, w: 20, h: 20 }];
  assert.equal(s.effectiveMapRotation(), 90);
  const rects = s.zoneDraftsToNormalizedRects({ width: 1000, height: 1000 });
  assert.deepEqual(
    rects[0].map((v) => Number(v.toFixed(4))),
    [0.1, 0.2, 0.3, 0.4],
    "a rect drawn on a 90-rotated display must be un-rotated into the content frame",
  );
});

test("[MR-9] canDrawHideArea gates on the DISPLAYED rotation, not the raw one", () => {
  // Hide-area has no un-rotation step, so it must refuse whenever the display is
  // turned — but it must NOT refuse when the display is flat and only the raw
  // value is non-zero. That was a false refusal.
  const s = divergentState();
  s.overlaysAligned = () => true;
  s.mapImageSize = () => ({ width: 1000, height: 1000 });
  assert.equal(s.effectiveMapRotation(), 0);
  assert.equal(s.canDrawHideArea(), true,
    "display is flat, so drawing is safe — gating on raw mapRotation() refused this");

  const turned = divergentState();
  turned.overlaysAligned = () => true;
  turned.mapImageSize = () => ({ width: 1000, height: 1000 });
  turned.isVaRenderActive = () => true;   // now the rotation really is applied
  assert.equal(turned.effectiveMapRotation(), 90);
  assert.equal(turned.canDrawHideArea(), false,
    "display is turned and hide-area cannot un-rotate — must refuse");
});
