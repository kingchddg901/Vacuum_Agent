// Regression tests — the map-segments slice must follow the ACTIVE MAP, not be fetched
// once for the life of the element.
//
// [MZ-3] _ensureMapSegments gated on presence (`if (mapSegmentsData()) return;`), so after
//   a map switch the slice still held map A while the raster had already been refetched
//   for map B: map A's room outlines drawn over map B's floor plan, map B's own device
//   labels suppressed (the renderer skips them when segments exist), and a tap resolving
//   through map A's segment ids against map B's rooms.
//
//   The panel carried an invalidation for this in its `set hass`; the embedded
//   <eufy-vacuum-map> host did not. The fix lives in the shared fetch helper so BOTH hosts
//   — and any future one — are covered, rather than adding a second copy of the guard.
//
// Run: node --test src/bindings/map-segments-staleness.test.mjs
//
// Coverage (MSS = Map Segments Staleness):
//   [MSS-1] a map switch refetches segments for the new map
//   [MSS-2] the stale slice is CLEARED before the refetch resolves (the visible-bug window)
//   [MSS-3] no refetch when the map has not changed (fetch-once still holds per map)
//   [MSS-4] a switch back to a previously seen map still refetches (no false cache hit)
//   [MSS-5] a concurrent call does not double-fetch

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyMapBindings } from "./map.js";

function makeBinding(initialMapId) {
  const proto = {};
  applyMapBindings(proto);
  const b = Object.create(proto);

  let segments = null;
  let activeMapId = initialMapId;
  const fetched = [];

  b.card = {
    _state: {
      getRoomsForActiveMap: () => [],
      activeMapId: () => activeMapId,
      mapSegmentsData: () => segments,
      setMapSegmentsData: (v) => { segments = v; },
    },
    _actions: {
      getMapSegments: async (id) => { fetched.push(id); segments = { rooms: [`room-of-${id}`] }; },
    },
    _scheduleRender: () => {},
  };
  b._syncSegmentsFromRooms = () => {};
  b.setActiveMap = (id) => { activeMapId = id; };
  b.fetched = fetched;
  b.peekSegments = () => segments;
  return b;
}

test("[MSS-1] a map switch refetches segments for the new map", async () => {
  const b = makeBinding("A");
  await b._ensureMapSegments();
  assert.deepEqual(b.fetched, ["A"]);

  b.setActiveMap("B");
  await b._ensureMapSegments();
  assert.deepEqual(b.fetched, ["A", "B"], "map B kept showing map A's segments");
  assert.deepEqual(b.peekSegments(), { rooms: ["room-of-B"] });
});

test("[MSS-2] the stale slice is cleared before the refetch resolves", async () => {
  const b = makeBinding("A");
  await b._ensureMapSegments();

  let clearedBeforeFetch = false;
  b.card._actions.getMapSegments = async (id) => {
    clearedBeforeFetch = b.peekSegments() === null;
    b.card._state.setMapSegmentsData({ rooms: [`room-of-${id}`] });
  };

  b.setActiveMap("B");
  await b._ensureMapSegments();
  assert.equal(clearedBeforeFetch, true, "map A's rooms kept rendering during the refetch");
});

test("[MSS-3] no refetch when the map has not changed", async () => {
  const b = makeBinding("A");
  await b._ensureMapSegments();
  await b._ensureMapSegments();
  await b._ensureMapSegments();
  assert.deepEqual(b.fetched, ["A"], "fetch-once per map was lost");
});

test("[MSS-4] switching back to a previously seen map still refetches", async () => {
  const b = makeBinding("A");
  await b._ensureMapSegments();
  b.setActiveMap("B");
  await b._ensureMapSegments();
  b.setActiveMap("A");
  await b._ensureMapSegments();
  assert.deepEqual(b.fetched, ["A", "B", "A"]);
  assert.deepEqual(b.peekSegments(), { rooms: ["room-of-A"] });
});

test("[MSS-5] a concurrent call does not double-fetch", async () => {
  const b = makeBinding("A");
  await Promise.all([b._ensureMapSegments(), b._ensureMapSegments()]);
  assert.deepEqual(b.fetched, ["A"]);
});
