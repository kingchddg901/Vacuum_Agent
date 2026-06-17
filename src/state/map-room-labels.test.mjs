// Unit test for the map room-label visibility toggle (per-vacuum, default on).
// Hides VA's own map labels so they don't stack on a live backdrop (e.g. the
// eufy-clean camera) that already bakes in its own labels. In node there's no
// localStorage, so the getter defaults to true and the in-memory flag flips on
// toggle. Run: node --test src/state/map-room-labels.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyMapState } from "./map.js";

function makeState() {
  const proto = {};
  applyMapState(proto);
  const s = Object.create(proto);
  s.config = { vacuum: "vacuum.alfred" };
  return s;
}

test("[LBL-1] map room labels default on and toggle flips", () => {
  const s = makeState();
  assert.equal(s.mapRoomLabelsEnabled(), true);
  s.toggleMapRoomLabelsEnabled();
  assert.equal(s.mapRoomLabelsEnabled(), false);
  s.toggleMapRoomLabelsEnabled();
  assert.equal(s.mapRoomLabelsEnabled(), true);
});

test("[LBL-2] setMapRoomLabelsEnabled coerces truthiness", () => {
  const s = makeState();
  s.setMapRoomLabelsEnabled(0);
  assert.equal(s.mapRoomLabelsEnabled(), false);
  s.setMapRoomLabelsEnabled("yes");
  assert.equal(s.mapRoomLabelsEnabled(), true);
});
