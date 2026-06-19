// Unit tests for the hidden-regions state — the per-map masks the user draws to hide map
// noise. Accessor (optimistic overlay vs segments data), draw mode, the draw gate, and the
// draw->store rect conversion. Run: node --test src/state/hidden-regions.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyMapState } from "./map.js";

function makeState() {
  const proto = {};
  applyMapState(proto);
  return Object.create(proto);
}

test("[HR-1] hiddenRegions: empty, from segments data, then optimistic overlay wins", () => {
  const s = makeState();
  s.mapSegmentsData = () => ({ hidden_regions: [[0.1, 0.1, 0.2, 0.2]] });
  assert.deepEqual(s.hiddenRegions(), [[0.1, 0.1, 0.2, 0.2]]);   // from the backend segments
  s.setHiddenRegionsOptimistic([[0.5, 0.5, 0.6, 0.6]]);
  assert.deepEqual(s.hiddenRegions(), [[0.5, 0.5, 0.6, 0.6]]);   // optimistic overrides
  s.clearHiddenRegionsOptimistic();
  assert.deepEqual(s.hiddenRegions(), [[0.1, 0.1, 0.2, 0.2]]);   // cleared -> back to segments
  s.mapSegmentsData = () => ({});
  assert.deepEqual(s.hiddenRegions(), []);                       // nothing -> []
});

test("[HR-2] hide-draw mode toggles", () => {
  const s = makeState();
  assert.equal(s.hideDrawMode(), false);
  s.setHideDrawMode(true);
  assert.equal(s.hideDrawMode(), true);
  s.setHideDrawMode(false);
  assert.equal(s.hideDrawMode(), false);
});

test("[HR-3] canDrawHideArea: overlay-aligned backdrop + image size + rotation 0", () => {
  const s = makeState();
  s.overlaysAligned = () => true;
  s.mapImageSize = () => [360, 300];
  s.mapRotation = () => 0;
  assert.equal(s.canDrawHideArea(), true);
  s.mapRotation = () => 90;
  assert.equal(s.canDrawHideArea(), false);                      // rotated -> letterbox swap
  s.mapRotation = () => 0;
  s.mapImageSize = () => null;
  assert.equal(s.canDrawHideArea(), false);                      // no dims for the transform
  s.mapImageSize = () => [360, 300];
  s.overlaysAligned = () => false;
  assert.equal(s.canDrawHideArea(), false);                      // no aligned backdrop to draw on
});

test("[HR-4] draw rect -> normalized image rect (square: pct == normalized; degenerate -> null)", () => {
  const s = makeState();
  assert.deepEqual(
    s._rectToNormalized({ x: 20, y: 30, w: 40, h: 25 }, { width: 100, height: 100 }),
    [0.2, 0.3, 0.6, 0.55]);
  // a tiny drag (< MIN_SIDE) is rejected (a stray click, not a region)
  assert.equal(s._rectToNormalized({ x: 0, y: 0, w: 0.5, h: 0.5 }, { width: 100, height: 100 }), null);
});
