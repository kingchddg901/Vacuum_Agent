// Run: node --test src/state/rooms-floor-rotation.test.mjs
//
// floor_rotation is the third field to cross these dicts, and the lesson from the first
// two is that BOTH ENDS CAN BE CORRECT while the value never arrives. So this tests the
// hop and the paint key, not the storage.
//
// It is per ROOM rather than per material on purpose: rotation describes the HOUSE. The
// planks in a hallway and a living room routinely run different ways, and the
// --evcc-floor-<type>-map-rotate token that already existed could never express that —
// every room sharing a material turned together.
//
// Coverage:
//   [RFR-1] _normalizeRoom carries attrs.floor_rotation through
//   [RFR-2] it defaults to 0 — a number, never undefined or NaN
//   [RFR-3] junk coerces to 0 rather than poisoning the paint key with NaN
//   [RFR-4] it is independent of floor_type and floor_material
//   [RFR-5] two rooms sharing a material but not an angle paint separately

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyRoomsState } from "./rooms.js";
import { normalizeFloorRotationDeg } from "../textures/floor-texture-resolver.js";

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

test("[RFR-1] _normalizeRoom carries attrs.floor_rotation through", () => {
  const card = makeState();
  assert.equal(card._normalizeRoom(attrs({ floor_rotation: 90 }), true).floor_rotation, 90);
  // negative and fractional angles survive — the data is a free float even though
  // today's control only offers quarter turns
  assert.equal(card._normalizeRoom(attrs({ floor_rotation: -37.5 }), true).floor_rotation, -37.5);
});

test("[RFR-2] it defaults to 0, a number", () => {
  const card = makeState();
  const room = card._normalizeRoom(attrs(), true);
  assert.equal(room.floor_rotation, 0);
  assert.equal(typeof room.floor_rotation, "number");
});

test("[RFR-3] junk coerces to 0 rather than poisoning the paint key", () => {
  // The map's paint key is `${floorType}|${degrees}`. A NaN there would stringify to
  // "tile|NaN" — a key that never matches a decoded texture and never errors, so the
  // room would silently paint flat forever.
  const card = makeState();
  for (const junk of ["", "abc", null, undefined, {}, NaN]) {
    const room = card._normalizeRoom(attrs({ floor_rotation: junk }), true);
    assert.equal(room.floor_rotation, 0, `floor_rotation ${JSON.stringify(junk)} -> 0`);
    assert.ok(Number.isFinite(room.floor_rotation));
  }
});

test("[RFR-4] it is independent of floor_type and floor_material", () => {
  const card = makeState();
  const room = card._normalizeRoom(
    attrs({ floor_rotation: 180, floor_material: "slate" }), true);
  assert.equal(room.floor_type, "tile");
  assert.equal(room.floor_material, "slate");
  assert.equal(room.floor_rotation, 180);
});

test("[RFR-5] two rooms sharing a material but not an angle paint separately", () => {
  // The whole point of per-room. If the paint key did not carry the angle, these two
  // would collapse onto one cache entry and the second room would take the first's
  // rotation — which is exactly what a per-MATERIAL token does.
  const card = makeState();
  const hall = card._normalizeRoom(
    attrs({ room_id: 1, room_name: "Hall", floor_material: "slate", floor_rotation: 0 }), true);
  const living = card._normalizeRoom(
    attrs({ room_id: 2, room_name: "Living", floor_material: "slate", floor_rotation: 90 }), true);

  const key = (r) => `${r.floor_material}|${normalizeFloorRotationDeg(r.floor_rotation)}`;
  assert.notEqual(key(hall), key(living));
  assert.equal(key(hall), "slate|0");
  assert.equal(key(living), "slate|90");
});
