// Unit tests for the area-label anchor state — the per-room draggable position for the m²
// chip. Accessor (optimistic overlay vs segments data, keyed by room number).
// Run: node --test src/state/area-label-anchor.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyMapState } from "./map.js";

function makeState() {
  const proto = {};
  applyMapState(proto);
  return Object.create(proto);
}

test("[AL-1] areaLabelAnchor: from segments data, keyed by room number (string-coerced)", () => {
  const s = makeState();
  s.mapSegmentsData = () => ({ area_label_anchors: { "5": { pct_x: 30, pct_y: 80 } } });
  assert.deepEqual(s.areaLabelAnchor(5), { pct_x: 30, pct_y: 80 });   // number key -> string lookup
  assert.deepEqual(s.areaLabelAnchor("5"), { pct_x: 30, pct_y: 80 });
  assert.equal(s.areaLabelAnchor(9), null);                           // unset -> null (default centre)
});

test("[AL-2] optimistic overlay overrides the backend; survives until a fresh segments fetch", () => {
  const s = makeState();
  s.mapSegmentsData = () => ({ area_label_anchors: { "5": { pct_x: 30, pct_y: 80 } } });
  s.setAreaLabelAnchorLocal(9, 10, 20);
  assert.deepEqual(s.areaLabelAnchor(9), { pct_x: 10, pct_y: 20 });   // new optimistic anchor
  s.setAreaLabelAnchorLocal("5", 99, 99);
  assert.deepEqual(s.areaLabelAnchor(5), { pct_x: 99, pct_y: 99 });   // overrides backend
});

test("[AL-3] effectiveMapRotation = the rotator's angle: rotates the contain backdrops (VA render + live image), not an uploaded/CV one", () => {
  const s = makeState();
  s.mapRotation = () => 90;
  s.supportsVaRender = () => true;
  // VA self-render active -> rotates (square-safe object-fit:contain canvas)
  s.isVaRenderActive = () => true;
  assert.equal(s.effectiveMapRotation(), 90);
  // live image (not VA) -> rotates
  s.isVaRenderActive = () => false;
  s.useVaRender = () => false;
  s.liveMapImageEntity = () => "camera.x_map";
  assert.equal(s.effectiveMapRotation(), 90);
  // no live image, no VA (uploaded/CV backdrop, maybe stretched) -> stays 0
  s.liveMapImageEntity = () => null;
  assert.equal(s.effectiveMapRotation(), 0);
});
