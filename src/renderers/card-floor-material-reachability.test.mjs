// Run: node --test src/renderers/card-floor-material-reachability.test.mjs
//
// THE SAME MISSING HOP, A FOURTH TIME — so this gates the CARD's view model the way
// state/rooms-floor-material-reachability.test.mjs gates the state layer's.
//
// floor_material has to survive four explicit-field dicts between storage and a pixel:
//
//   RoomConfig
//     -> room entity attributes        room_entities.py      (fixed, [AXT-6/7])
//     -> _normalizeRoom                state/rooms.js        (fixed, [RFMR-1..4])
//     -> _normalizeRoomDisplayData     renderers/rooms.js    (fixed, THIS FILE)
//     -> _renderFloorTextureLayer      floor-texture-surface.js
//
// Each one rebuilds its object field by field, so each is its own silent drop. The
// third was invisible for a particular reason worth keeping: the MAP resolves from the
// state-layer room and was already correct, so the map painted a room's drop-in while
// every ROOM CARD for that same room painted its plain floor_type. Two surfaces
// disagreeing about one room, with no error and both halves individually "working".
//
// resolveFloorType falls through to floor_type for an unknown material BY DESIGN, so a
// dropped field is indistinguishable from a material that is not installed. Nothing
// logs. The card just looks like a card.
//
// Coverage:
//   [CFM-1] the card view model carries floor_material through as floorMaterial
//   [CFM-2] end to end: a normalised room with a drop-in resolves to that material
//   [CFM-3] an UNINSTALLED material still falls through to floor_type (degrade, not flat)
//   [CFM-4] `carpet` stays sourced from floor_type — the safety property is untouched
//   [CFM-5] the drop-in preview card puts the id in the MATERIAL slot, not floor_type

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyRoomsRenderers } from "./rooms.js";
import { applyFloorTextureSurface } from "./floor-texture-surface.js";
import { applyThemePreviewRenderers } from "./theme-preview.js";
import { resolveFloorType } from "../textures/floor-texture-resolver.js";
import { FLOOR_TEXTURE_REGISTRY } from "../textures/floor-texture-registry.js";

const PROBE = "__cfm_probe";

function makeProto() {
  const proto = {};
  applyRoomsRenderers(proto);
  applyFloorTextureSurface(proto);
  return proto;
}

const room = (over = {}) => ({
  id: 1,
  name: "Kitchen",
  enabled: true,
  floor_type: "hardwood",
  ...over,
});

test("[CFM-1] the card view model carries floor_material through", () => {
  const proto = makeProto();
  const out = proto._normalizeRoomDisplayData(room({ floor_material: PROBE }));
  assert.equal(out.floorMaterial, PROBE,
    "the card builds its own object field by field; a field absent here cannot reach " +
    "_renderFloorTextureLayer however correctly it is stored");
  // and the camelCase input spelling is accepted too, as every other field here is
  assert.equal(
    proto._normalizeRoomDisplayData(room({ floorMaterial: PROBE })).floorMaterial,
    PROBE,
  );
  // absent means empty, not undefined, so the resolver's check stays total
  assert.equal(proto._normalizeRoomDisplayData(room()).floorMaterial, "");
});

test("[CFM-2] end to end: a normalised room with a drop-in resolves to it", () => {
  FLOOR_TEXTURE_REGISTRY[PROBE] = { layers: [], masks: [], baseTexture: null };
  try {
    const proto = makeProto();
    const normalized = proto._normalizeRoomDisplayData(room({ floor_material: PROBE }));

    // The surface resolves from the NORMALISED object, which is the hop under test.
    const resolved = resolveFloorType({
      floor_type: normalized.floorType,
      carpet_type: normalized.carpetType,
      floor_material: normalized.floorMaterial,
    });
    assert.equal(resolved, PROBE,
      "normalised-room-in, material-key-out — this is what the card actually does");
  } finally {
    delete FLOOR_TEXTURE_REGISTRY[PROBE];
  }
});

test("[CFM-3] an uninstalled material falls through to floor_type", () => {
  // Deliberate: removing a drop-in must degrade a room to its own floor rather than
  // render it flat, and must leave the stored value alone so reinstalling restores it.
  const proto = makeProto();
  const normalized = proto._normalizeRoomDisplayData(
    room({ floor_material: "not-installed" }));
  assert.equal(
    resolveFloorType({
      floor_type: normalized.floorType,
      carpet_type: normalized.carpetType,
      floor_material: normalized.floorMaterial,
    }),
    "wood",
    "hardwood -> wood, not default",
  );
});

test("[CFM-4] `carpet` stays sourced from floor_type, never the material", () => {
  // The load-bearing separation: floor_type carries the carpet-water-off guarantee, so
  // a material a stranger named must not be able to make a room read as carpet, or
  // stop one reading as carpet.
  const proto = makeProto();

  const carpetRoom = proto._normalizeRoomDisplayData(
    room({ floor_type: "carpet_low_pile", floor_material: PROBE }));
  assert.equal(carpetRoom.carpet, true,
    "a drop-in must not clear the carpet flag");

  const hardRoom = proto._normalizeRoomDisplayData(
    room({ floor_type: "hardwood", floor_material: "carpet-ish-name" }));
  assert.equal(hardRoom.carpet, false,
    "a material NAMED like carpet must not make a hardwood room read as carpet");
});

test("[CFM-5] the drop-in preview card uses the material slot, not floor_type", () => {
  // resolveFloorType honours a drop-in id ONLY in floor_material. Passing one as
  // floor_type walks the shipped vocabulary, matches nothing and yields "default" —
  // a flat card beside controls that move real tokens.
  const proto = makeProto();
  applyThemePreviewRenderers(proto);

  const seen = [];
  const card = Object.create(proto);
  card.t = (k) => k;
  card.tVocabRaw = (_f, v, fb) => fb ?? String(v);
  card.renderRoomCard = (r) => { seen.push(r); return ""; };

  card._renderFloorPreviewCard("slatey", "Slatey", true);
  assert.equal(seen[0].floor_material, "slatey");
  assert.equal(seen[0].floor_type, "", "a drop-in id in floor_type resolves to default");

  // ...while a SHIPPED key still goes in the floor_type slot, where it belongs.
  card._renderFloorPreviewCard("tile", "Tile");
  assert.equal(seen[1].floor_type, "tile");
  assert.equal(seen[1].floor_material, "");
});
