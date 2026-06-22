// Unit tests for roomIdAtContentPct — the pixel-exact room hit-test for auto-derived click
// targets. A CONTENT-box % point -> the device room id under it, via the render raster (with
// the Y-flip + object-fit:contain letterbox + catch-all filtering).
// Run: node --test src/state/room-hit-test.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyMapState } from "./map.js";

function makeState() {
  const proto = {};
  applyMapState(proto);
  return Object.create(proto);
}

// A 10x10 render-data raster: blocks are [rid, x, y] in the room-outline frame. Each call gets
// a unique version (in prod the version is a sha1 of the raster) so the raster cache can't alias.
let _rdSeq = 0;
function _rd(blocks, over = {}) {
  const buf = new Uint8Array(100);
  for (const [rid, x, y] of blocks) buf[y * 10 + x] = rid << 2;
  let bin = "";
  for (let i = 0; i < buf.length; i++) bin += String.fromCharCode(buf[i]);
  return {
    present: true, room_pixels: btoa(bin), version: `v${++_rdSeq}`,
    width: 10, height: 10, ro_width: 10, ro_height: 10, ro_dx: 0, ro_dy: 0,
    rid_shift: 2, catch_all_rid: 32, flip_y: true, ...over,
  };
}

test("[CT-1] roomIdAtContentPct: pixel-exact device room id (Y-flip, square = no letterbox)", () => {
  const s = makeState();
  s.mapImageSize = () => [10, 10];                 // square -> content% == normalized*100
  const rd = _rd([[5, 2, 2], [7, 8, 8]]);          // room 5 at (2,2), room 7 at (8,8)
  // main (2,2) -> normalize nx .2 ny .7 -> content% (20,70)
  assert.equal(s.roomIdAtContentPct(20, 70, rd), 5);
  // main (8,8) -> normalize nx .8 ny .1 -> content% (80,10)
  assert.equal(s.roomIdAtContentPct(80, 10, rd), 7);
  // an empty cell -> null (byte 0 -> rid 0)
  assert.equal(s.roomIdAtContentPct(50, 50, rd), null);
  // outside the grid / no render data -> null
  assert.equal(s.roomIdAtContentPct(-5, 50, rd), null);
  assert.equal(s.roomIdAtContentPct(20, 70, null), null);
});

test("[CT-2] roomIdAtContentPct: catch-all id (>= 32) and the room-outline offset are honored", () => {
  const s = makeState();
  s.mapImageSize = () => [10, 10];
  // a catch-all cell (rid 32) at (2,2) must read as null, not a room
  assert.equal(s.roomIdAtContentPct(20, 70, _rd([[32, 2, 2]])), null);
  // with an offset (ro_dx/dy): the main-grid pixel shifts into the raster by -dx/-dy
  const rd = _rd([[6, 1, 1]], { ro_dx: 1, ro_dy: 1 });   // raster cell (1,1) == main (2,2)
  assert.equal(s.roomIdAtContentPct(20, 70, rd), 6);     // main (2,2) -> raster (1,1) -> rid 6
});

test("[CT-3] roomIdAtContentPct: a tap in the letterbox bar of a non-square map -> null", () => {
  const s = makeState();
  s.mapImageSize = () => [20, 10];                 // 2:1 -> vertical letterbox bars (offY=25)
  const rd = _rd([[5, 2, 2]], { width: 20, height: 10, ro_width: 20, ro_height: 10 });
  // content y in the top bar (< offY 25) is outside the image -> null
  assert.equal(s.roomIdAtContentPct(50, 10, rd), null);
});

test("[CT-4] roomIdAtContentPct: letterbox aspect falls back to rd dims when mapImageSize() is null (camera-less VA render)", () => {
  const s = makeState();
  s.mapImageSize = () => null;   // VA render with no live-map camera -> map_state_source absent
  // a 20x10 raster (2:1) -> the canvas letterboxes top/bottom (offY 25) by rd.width/height
  const W = 20, H = 10;
  const buf = new Uint8Array(W * H);
  buf[2 * W + 4] = 5 << 2;       // room 5 at raster/main cell (x=4, y=2)
  let bin = "";
  for (let i = 0; i < buf.length; i++) bin += String.fromCharCode(buf[i]);
  const rd = {
    present: true, room_pixels: btoa(bin), version: `ct4-${++_rdSeq}`,
    width: W, height: H, ro_width: W, ro_height: H, ro_dx: 0, ro_dy: 0,
    rid_shift: 2, catch_all_rid: 32, flip_y: true,
  };
  // content (22, 57.5): nx .22 -> px 4 ; ny (57.5-25)/50 = .65 -> flip pyN 9-6.5=2.5 -> py 2 -> room 5
  assert.equal(s.roomIdAtContentPct(22, 57.5, rd), 5);
  // a tap in the TOP letterbox bar (cy 10 < offY 25) is outside the image -> null
  assert.equal(s.roomIdAtContentPct(22, 10, rd), null);
});

test("[CT-5] deviceRoomIdAtContentPct: bbox fallback (no raster) — hit + outside->null", () => {
  const s = makeState();
  s.mapImageSize = () => [10, 10];                  // square -> content% == normalized*100
  s.mapOverlayData = () => null;                    // force fall-through to mapStateSource
  s.mapStateSource = () => ({
    present: true,
    rooms: [
      { number: 5, bbox: [0.0, 0.0, 0.4, 0.4] },    // top-left (normalized, rendered frame)
      { number: 7, bbox: [0.6, 0.6, 1.0, 1.0] },    // bottom-right
    ],
  });
  assert.equal(s.deviceRoomIdAtContentPct(20, 20), 5);    // nx.2 ny.2 -> room 5
  assert.equal(s.deviceRoomIdAtContentPct(80, 80), 7);    // nx.8 ny.8 -> room 7
  assert.equal(s.deviceRoomIdAtContentPct(50, 50), null); // between the rooms -> null
});

test("[CT-6] deviceRoomIdAtContentPct: smallest bbox wins on overlap; not-present -> null", () => {
  const s = makeState();
  s.mapImageSize = () => [10, 10];
  s.mapOverlayData = () => null;
  s.mapStateSource = () => ({ present: true, rooms: [
    { number: 1, bbox: [0.0, 0.0, 1.0, 1.0] },      // whole map
    { number: 2, bbox: [0.1, 0.1, 0.3, 0.3] },      // small, inside room 1
  ] });
  assert.equal(s.deviceRoomIdAtContentPct(20, 20), 2);    // overlap -> smallest (2)
  assert.equal(s.deviceRoomIdAtContentPct(50, 50), 1);    // only the big room
  s.mapStateSource = () => ({ present: false });
  assert.equal(s.deviceRoomIdAtContentPct(20, 20), null); // no live rooms -> null
});
