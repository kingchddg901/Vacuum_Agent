// Run: node --test src/state/rooms-floor-fit.test.mjs
//
// floor_fit is the FOURTH field to cross these dicts, and it is here because it did not.
//
// The value was clamped correctly, persisted correctly, survived a map rebuild correctly
// and was read back from `.storage` with the right numbers in it -- and it still vanished
// on every reload, because the card does not read the store. It rebuilds its rooms from
// the room switch's ENTITY ATTRIBUTES, and `floor_fit` was not among them. Both ends were
// right and the value never arrived; `room_entities.py` says so in as many words, beside
// the two fields that learned it before this one.
//
// So this tests THE HOP. Not the storage, which was never wrong, and not the geometry,
// which has its own file -- the three steps between a stored dict and the object a
// renderer is handed.
//
// Coverage:
//   [RFF-1] _normalizeRoom carries attrs.floor_fit through
//   [RFF-2] absent is an empty OBJECT -- never undefined, never null
//   [RFF-3] junk shapes degrade to {} rather than reaching the floor draw
//   [RFF-4] the object is COPIED, so a later mutation cannot write back into HA state
//   [RFF-5] it is independent per room, which is the whole point of fitting per room

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyRoomsState } from "./rooms.js";

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
  map_id: "12",
  room_id: 1,
  room_name: "Bryan's Room",
  floor_type: "carpet_low_pile",
  floor_material: "ma-stone-wood-test",
  ...over,
});

test("[RFF-1] _normalizeRoom carries attrs.floor_fit through", () => {
  const card = makeState();
  const fit = { tx: 0.4, ty: -0.2, scale: 1.3 };
  assert.deepEqual(card._normalizeRoom(attrs({ floor_fit: fit }), true).floor_fit, fit);

  // Partial placements are normal -- each control writes one axis, and the renderer
  // treats a missing axis as its default rather than requiring all three.
  assert.deepEqual(
    card._normalizeRoom(attrs({ floor_fit: { scale: 2 } }), true).floor_fit, { scale: 2 });
});

test("[RFF-2] an absent placement is an empty OBJECT, never undefined or null", () => {
  const card = makeState();
  // The floor draw reads `room.floor_fit` and spreads it. An undefined here is not
  // fatal today, but a null is one `?.` away from being, and the whole point of the
  // default being {} is that every consumer can treat it as a placement without asking
  // whether there is one.
  for (const absent of [undefined, null]) {
    const room = card._normalizeRoom(
      absent === undefined ? attrs() : attrs({ floor_fit: absent }), true);
    assert.deepEqual(room.floor_fit, {});
    assert.equal(typeof room.floor_fit, "object");
    assert.ok(room.floor_fit !== null);
  }
});

test("[RFF-3] a junk shape degrades to {} rather than reaching the floor draw", () => {
  // Attributes come off the wire and a stale or hand-edited entity can hold anything.
  // An array is the one that would slip a truthy non-placement through a bare
  // `typeof === "object"` test, which is why it is named here.
  const card = makeState();
  for (const junk of ["{}", 5, true, [], [1, 2], () => {}]) {
    assert.deepEqual(card._normalizeRoom(attrs({ floor_fit: junk }), true).floor_fit, {},
      `${JSON.stringify(junk) ?? String(junk)} is not a placement`);
  }
});

test("[RFF-4] the placement is COPIED out of the attributes, not aliased", () => {
  // `_hass.states` is replaced wholesale on every update, but the attribute object can
  // be shared between renders. Handing the renderer a live reference means a draft
  // merge or a defensive spread could write back into what HA handed us, and the bug
  // would look like a placement that changes without anyone touching it.
  const card = makeState();
  const source = { tx: 0.4 };
  const room = card._normalizeRoom(attrs({ floor_fit: source }), true);
  room.floor_fit.tx = 0.9;
  assert.equal(source.tx, 0.4, "mutating the room must not reach back into the attributes");
});

test("[RFF-5] placements are independent per room", () => {
  // Two rooms sharing a material place it separately -- that is the entire reason a
  // fitted material is fitted PER ROOM rather than tiled across the map.
  const card = makeState();
  const a = card._normalizeRoom(attrs({ room_id: 1, floor_fit: { tx: 1 } }), true);
  const b = card._normalizeRoom(attrs({ room_id: 2, floor_fit: { tx: -1 } }), true);
  assert.equal(a.floor_fit.tx, 1);
  assert.equal(b.floor_fit.tx, -1);
});
