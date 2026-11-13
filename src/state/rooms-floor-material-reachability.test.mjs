// Run: node --test src/state/rooms-floor-material-reachability.test.mjs
//
// REACHABILITY, not behaviour. floor_material was stored correctly and read correctly
// and still did nothing on the live box, because the value never TRAVELLED between the
// two: three hops in the middle each build their dict from an explicit field list, and
// the new field was in none of them.
//
//   RoomConfig  ->  room entity attributes  ->  _normalizeRoom  ->  resolveFloorType
//                   (room_entities.py)         (THIS FILE)         (tested already)
//
// Both ends had tests. Both passed. The chip rendered and selecting a material changed
// nothing, because `room.floor_material` was always undefined by the time the renderer
// saw it. A test of either end could not have caught that — only a test of the HOP can,
// which is what this is.
//
// The Python hops are fenced by tests/integration/test_room_crud.py (the writer) and
// tests/integration/test_axis_field_translation.py [AXT-6/7] (the attribute dict).
//
// Coverage:
//   [RFMR-1] _normalizeRoom carries attrs.floor_material onto the room object
//   [RFMR-2] it defaults to "" rather than undefined, so the resolver's check is total
//   [RFMR-3] floor_type is unaffected — the two fields are independent
//   [RFMR-4] the normalised room is shaped so resolveFloorType can actually use it

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyRoomsState } from "./rooms.js";
import { resolveFloorType } from "../textures/floor-texture-resolver.js";
import { FLOOR_TEXTURE_REGISTRY } from "../textures/floor-texture-registry.js";

function makeState() {
  const proto = {};
  applyRoomsState(proto);
  const card = Object.create(proto);
  card._config = {};
  card._hass = { states: {} };
  return card;
}

const attrs = (over = {}) => ({
  vacuum_entity_id: "vacuum.alfred",
  map_id: "6",
  room_id: 1,
  room_name: "Kitchen",
  floor_type: "tile",
  ...over,
});

test("[RFMR-1] _normalizeRoom carries attrs.floor_material through", () => {
  const card = makeState();
  const room = card._normalizeRoom(attrs({ floor_material: "slate" }), true);
  assert.equal(room.floor_material, "slate",
    "the field must survive the attrs -> room hop; it did not, and that was the whole defect");
});

test("[RFMR-2] it defaults to \"\" rather than undefined", () => {
  // The resolver tests `material && ...`. undefined would work there by luck, but an
  // explicit "" keeps every consumer's check total rather than relying on falsiness
  // of a missing key.
  const card = makeState();
  const room = card._normalizeRoom(attrs(), true);
  assert.equal(room.floor_material, "");
  assert.notEqual(room.floor_material, undefined);
});

test("[RFMR-3] floor_type is unaffected — the two fields are independent", () => {
  const card = makeState();
  const room = card._normalizeRoom(attrs({ floor_material: "slate" }), true);
  assert.equal(room.floor_type, "tile",
    "appearance must not disturb the field carrying the carpet guarantee");
});

test("[RFMR-4] the normalised room is shaped so resolveFloorType can use it", () => {
  // The hop is only worth anything if what lands is what the consumer reads. This
  // closes the loop end to end on the card side: attributes in, rendered key out.
  FLOOR_TEXTURE_REGISTRY.__rfmr_probe = { layers: [], masks: [], baseTexture: null };
  try {
    const card = makeState();
    const chosen = card._normalizeRoom(attrs({ floor_material: "__rfmr_probe" }), true);
    assert.equal(resolveFloorType(chosen), "__rfmr_probe");

    // and a material that is not installed falls through to the floor type
    const stale = card._normalizeRoom(attrs({ floor_material: "uninstalled" }), true);
    assert.equal(resolveFloorType(stale), "tile");

    const none = card._normalizeRoom(attrs(), true);
    assert.equal(resolveFloorType(none), "tile");
  } finally {
    delete FLOOR_TEXTURE_REGISTRY.__rfmr_probe;
  }
});
