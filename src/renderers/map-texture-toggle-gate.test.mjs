// Run: node --test src/renderers/map-texture-toggle-gate.test.mjs
//
// [MTG-*] A TOGGLE FOR A LAYER THAT IS NOT DRAWN.
//
// There are three floor-texture gates, one per render path, and they are three different
// buttons — that part is by design and documented in
// docs/dev/frontend/floor-texture-map-view.md:
//
//   room cards        roomFloorTextureEnabled()
//   VA raster canvas  isFloorRenderActive() = isVaRenderActive() && useFloorTexture()
//   SVG polygons      mapFloorTextureEnabled()      <- this button
//
// The bug was the GATE ON THE BUTTON, not the flags. `map-texture-toggle` drives the
// SVG-polygon layer, and that layer only exists where there are SEGMENTS to paint:
// `_renderFloorTexturePolygon` is called over `state.mapSegments()`, which a raster map
// (room_pixels, rids straight off the raster) leaves empty. The button was rendered on
// `mapActive` alone — whether the user is looking at the map, not whether the thing it
// controls is drawn — so on every raster map it sat there inert, beside the ▨ button that
// DOES work, under a near-identical name ("Hide map textures" vs "Toggle floor textures").
// Same shape as the companion row in issue #82.
//
// [MTG-3] IS THE ONE THAT EARNS ITS PLACE. The first version of this fix put
// `&& hasSegmentLayer` on the OUTER block — which also contains the room-labels toggle and
// the configure-map button. That would have hidden three controls on a raster map, two of
// them working, on exactly the maps this repo's own dev box uses. The gate must wrap the
// texture button and nothing else.
//
// Coverage
// --------
// [MTG-1] with segments, the texture toggle renders (the SVG path is live)
// [MTG-2] with none, it does not (a raster map has no polygon layer to toggle)
// [MTG-3] with none, the labels and configure buttons SURVIVE — the regression guard
// [MTG-4] out of map view nothing in the block renders at all

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyRoomsRenderers } from "./rooms.js";
import { applyMapRenderers } from "./map.js";

// The animal picker reads `window.AnimalSVG?.list?.()`. Optional chaining guards the
// PROPERTY, not the `window` reference, so the bare identifier throws in node. Stubbed
// rather than softened in production code, which only ever runs in a browser.
globalThis.window = globalThis.window ?? {};

function makeRenderer() {
  // BOTH mixins, because the toolbar this renders calls across to the map one
  // (`_renderMapAnimalControls`). Stubbing that would let the two drift apart silently —
  // the real card composes them, so the test does too.
  const proto = {};
  applyRoomsRenderers(proto);
  applyMapRenderers(proto);
  const r = Object.create(proto);
  r.t = (k) => k;                       // translate to the KEY, so assertions ignore copy
  r.tVocab = (_g, v, fb) => String(v ?? fb ?? "");
  r.escapeHtml = (v) => String(v ?? "");
  return r;
}

const state = ({ mapActive = true, segments = 0 } = {}) => ({
  isMapViewActive: () => mapActive,
  mapSegments: () => new Array(segments).fill({}),
  mapFloorTextureEnabled: () => true,
  mapRoomLabelsEnabled: () => true,
  roomFloorTextureEnabled: () => true,
  // what the mascot controls read
  mapAnimalEnabled: () => true,
  mapAnimalScale: () => 1,
  mapAnimalFollowsRobot: () => false,
  mapAnimalMoonwalk: () => false,
  mapAnimalSelection: () => "cat",
  isMascotBarCollapsed: () => false,
  vacuumObjectId: () => "robot",
});

const render = (opts) => makeRenderer()._renderRoomsViewToggle(state(opts), {});

test("[MTG-1] with segments the texture toggle renders", () => {
  const html = render({ segments: 6 });
  assert.ok(html.includes("map-texture-toggle"),
    "where the SVG polygon layer is live, its toggle belongs on screen");
});

test("[MTG-2] with no segments it does not render", () => {
  // THE RED INPUT: putting the gate back to `mapActive` alone. A raster map has no
  // segments, so the polygon layer draws nothing and this button controls nothing.
  const html = render({ segments: 0 });
  assert.ok(!html.includes("map-texture-toggle"),
    "a raster map has no polygon layer; a toggle for it is a control for something " +
    "that is not there");
});

test("[MTG-3] with no segments, labels and configure STILL render", () => {
  // THE REGRESSION GUARD, and it is not hypothetical: the first cut of this fix put
  // `&& hasSegmentLayer` on the OUTER block, which also holds these two. On a raster map
  // — which is what this project's own dev box runs — that would have removed the room
  // labels toggle and the way into map config, while every other test still passed.
  const html = render({ segments: 0 });
  assert.ok(html.includes("map-labels-toggle"),
    "room labels work on a raster map and must survive the texture gate");
  assert.ok(html.includes("open-map-config"),
    "map configuration must survive it too — the gate wraps ONE button");
});

test("[MTG-4] out of map view, none of the map controls render", () => {
  const html = render({ mapActive: false, segments: 6 });
  for (const action of ["map-texture-toggle", "map-labels-toggle", "open-map-config"]) {
    assert.ok(!html.includes(action), `${action} is map-view only`);
  }
});
