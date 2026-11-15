// Run: node --test src/renderers/map-floor-placement.test.mjs
//
// [MFP-*] WHICH ROOM THE PLACEMENT CONTROL IS FOR.
//
// This exists because the control was attached to three surfaces in a row that could not
// show it, and the last of those was this gate. It keyed on a single selected SVG
// SEGMENT -- and the development map has ZERO segments. Its rooms come from the
// `room_pixels` raster rids (ten of them in `room_names`), so the polygon layer is empty,
// nothing there is selectable, and the panel could never appear however correct every
// layer behind it was. Measured in the running card before the fix: segments 0,
// selectedSegmentIds [], renderData present 256x245, panel absent from the DOM.
//
// The common thread in all three misses was checking that a MECHANISM EXISTED rather than
// that it could FIRE ON REAL DATA. So [MFP-1] is written to fail if this ever consults
// segments again: the state it is handed throws from every segment accessor.
//
// Coverage
// --------
// [MFP-1] a fitted room resolves from the ROOM ALONE -- the state's segment API throws
// [MFP-2] a TILED material yields null: it shares one map-space grid, nothing to place
// [MFP-3] no material, "default", or a missing room yields null rather than a dead control
// [MFP-4] the draft wins over the saved placement, and `dirty` says which is in force
// [MFP-5] the saved placement survives when no draft is open -- the reload case

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyMapRenderers } from "./map.js";
import { FLOOR_TEXTURE_REGISTRY } from "../textures/floor-texture-registry.js";
import { mergeUserMaterials } from "../textures/user-materials.js";

const FITTED = "test-fitted-pack";
const TILES = "test-tiling-pack";

// Registered once into the real registry, through the real catalogue hop, so the test
// asks the same question the renderer does rather than a hand-built lookalike.
mergeUserMaterials(FLOOR_TEXTURE_REGISTRY, [
  {
    id: FITTED, name: "Fitted", layers: [{ suffix: "base", path: "a.png", color: "#888", opacity: 1 }],
  },
  {
    id: TILES, name: "Tiling", tileable: true,
    layers: [{ suffix: "base", path: "b.png", color: "#888", opacity: 1 }],
  },
]);

function makeRenderer() {
  const proto = {};
  applyMapRenderers(proto);
  return Object.create(proto);
}

/** A state with NO segment support at all -- every segment accessor throws. A raster map
 *  genuinely has none; this makes "it quietly fell back to segments" impossible to pass. */
function makeState({ draft = null } = {}) {
  const boom = (name) => () => { throw new Error(`segment API used: ${name}`); };
  return {
    floorFitDraft: () => draft,
    mapSegments: boom("mapSegments"),
    selectedSegmentIds: boom("selectedSegmentIds"),
    roomIdForSegment: boom("roomIdForSegment"),
  };
}

const room = (over = {}) => ({
  id: 1, name: "Bryan's Room",
  floor_type: "carpet_low_pile",
  floor_material: FITTED,
  ...over,
});

test("[MFP-1] a fitted room resolves from the ROOM alone, with no segments anywhere", () => {
  const r = makeRenderer();
  const target = r._floorPlacementTarget(makeState(), room());
  assert.ok(target, "a fitted material on a real room must yield a target");
  assert.equal(target.roomId, "1");
  assert.equal(target.roomName, "Bryan's Room");
  // The state above throws from every segment accessor. Reaching for one -- which is
  // exactly what the shipped gate did -- turns this red rather than silently working
  // on maps that happen to have segments and failing on the ones that do not.
});

test("[MFP-2] a TILED material yields null, not a control that cannot move anything", () => {
  const r = makeRenderer();
  assert.equal(r._floorPlacementTarget(makeState(), room({ floor_material: TILES })), null);
  // ...and a SHIPPED type, which always tiles.
  assert.equal(r._floorPlacementTarget(makeState(), room({ floor_material: "", floor_type: "hardwood" })), null);
});

test("[MFP-3] no room, no material and 'default' all yield null", () => {
  const r = makeRenderer();
  const st = makeState();
  for (const absent of [null, undefined, {}]) {
    assert.equal(r._floorPlacementTarget(st, absent), null, `${String(absent)} is not a room`);
  }
  assert.equal(r._floorPlacementTarget(st, room({ floor_material: "default", floor_type: "" })), null);
  assert.equal(r._floorPlacementTarget(st, room({ id: null, room_id: null })), null,
    "a room with no id cannot be keyed and must not produce a target");
});

test("[MFP-4] the draft wins over the saved placement, and dirty says which", () => {
  const r = makeRenderer();
  const saved = { tx: 0.4, ty: -0.2, scale: 1.3 };
  const draft = { tx: 0.46, ty: -0.2, scale: 1.3 };

  const clean = r._floorPlacementTarget(makeState(), room({ floor_fit: saved }));
  assert.deepEqual(clean.fit, saved);
  assert.equal(clean.dirty, false, "no draft open means nothing to save");

  const dirty = r._floorPlacementTarget(makeState({ draft }), room({ floor_fit: saved }));
  assert.deepEqual(dirty.fit, draft, "the draft is what the floor is drawing");
  assert.deepEqual(dirty.saved, saved, "...and the saved value is still reported");
  // No longer "what offers Save and Cancel" -- the panel AUTO-SAVES on adjust and has
  // neither button. `dirty` is still load-bearing INSIDE the resolver (it is what
  // picks draft over saved) and is reported so a caller can say which value is in
  // force; it no longer gates a control.
  assert.equal(dirty.dirty, true, "a draft is open, so the draft is what is in force");

  // An EMPTY draft is a real placement -- "back to centred" -- not an absent one.
  const reset = r._floorPlacementTarget(makeState({ draft: {} }), room({ floor_fit: saved }));
  assert.deepEqual(reset.fit, {}, "Centre must not fall back to the saved placement");
  assert.equal(reset.dirty, true);
});

test("[MFP-5] with no draft, the SAVED placement is what the control shows", () => {
  // The reload case. It is only here because the stored value spent three fixes being
  // invisible: dropped by a map rebuild, then absent from the entity attributes the card
  // builds its rooms from. By the time it reaches this function it must simply be used.
  const r = makeRenderer();
  const t = r._floorPlacementTarget(makeState(), room({ floor_fit: { tx: 1, scale: 1.5 } }));
  assert.deepEqual(t.fit, { tx: 1, scale: 1.5 });
  assert.equal(t.dirty, false);

  // A SUB-COVER scale is legal and is reported AS STORED -- zooming out below cover is how
  // a material gets inspected, so 0.30 is a real placement, not one to be corrected.
  const sub = r._floorPlacementTarget(makeState(), room({ floor_fit: { tx: -1, scale: 0.3 } }));
  assert.equal(sub.fit.scale, 0.3, "a sub-cover placement is honoured, not lifted");

  // ...but `fit` IS normalised, so a value outside the range the control can author is
  // reported at the bound, matching what the draw actually paints. `saved` still reports
  // the raw stored value, because "what is in storage" is a different question from "what
  // is on screen", and conflating them is how a readout comes to contradict the floor
  // under it.
  const absurd = r._floorPlacementTarget(makeState(), room({ floor_fit: { tx: -9, scale: 0.01 } }));
  assert.equal(absurd.fit.scale, 0.25, "below the bound it reports at the bound");
  assert.equal(absurd.fit.tx, -1, "and the pan clamps to its stop");
  assert.equal(absurd.saved.scale, 0.01, "while `saved` still tells the truth about storage");

  // A room that was never placed shows the default rather than undefined.
  assert.deepEqual(r._floorPlacementTarget(makeState(), room()).fit, {});
});
