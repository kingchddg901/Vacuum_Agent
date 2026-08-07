// Unit tests for the area-label anchor state — the per-room draggable position for the m²
// chip.
//
// Storage moved to the SAME device-local store the room-NAME label uses. The m² chip used
// to round-trip through a backend service (set_area_label_anchor -> a `label_anchor` field
// on the room record), so one gesture on two adjacent labels stored two ways and failed two
// ways — and the backend half was the fragile one, since neither room writer carried the
// field through RoomConfig (R2-BUG-4). The backend payload is now read ONCE per device to
// seed it, so nobody's dragged layout resets under them.
// Run: node --test src/state/area-label-anchor.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyMapState } from "./map.js";


function makeState() {
  const proto = {};
  applyMapState(proto);
  const s = Object.create(proto);
  s.vacuumObjectId = () => "alfred";
  s.activeMapId = () => "main";
  return s;
}

function resetStorage() {
  globalThis.localStorage = (() => {
    const store = new Map();
    return {
      getItem: (k) => (store.has(k) ? store.get(k) : null),
      setItem: (k, v) => store.set(k, String(v)),
      removeItem: (k) => store.delete(k),
      _dump: () => store,
    };
  })();
}

test("[AL-1] the backend payload SEEDS the device once, then serves locally", () => {
  resetStorage();
  const s = makeState();
  s.mapSegmentsData = () => ({ area_label_anchors: { "5": { pct_x: 30, pct_y: 80 } } });

  assert.deepEqual(s.areaLabelAnchor(5), { pct_x: 30, pct_y: 80 });   // number key -> string lookup
  assert.deepEqual(s.areaLabelAnchor("5"), { pct_x: 30, pct_y: 80 });
  assert.equal(s.areaLabelAnchor(9), null);                           // unset -> default centre

  // ...and it is now genuinely local: a fresh state with NO backend payload still has it.
  const reloaded = makeState();
  reloaded.mapSegmentsData = () => ({});
  assert.deepEqual(reloaded.areaLabelAnchor(5), { pct_x: 30, pct_y: 80 });
});

test("[AL-2] a local drag wins over the seed, and persists", () => {
  resetStorage();
  const s = makeState();
  s.mapSegmentsData = () => ({ area_label_anchors: { "5": { pct_x: 30, pct_y: 80 } } });

  s.setAreaLabelAnchorLocal("5", 99, 99);
  assert.deepEqual(s.areaLabelAnchor(5), { pct_x: 99, pct_y: 99 });

  const reloaded = makeState();
  reloaded.mapSegmentsData = () => ({ area_label_anchors: { "5": { pct_x: 30, pct_y: 80 } } });
  assert.deepEqual(reloaded.areaLabelAnchor(5), { pct_x: 99, pct_y: 99 },
    "the stale backend value came back over a local drag");
});

test("[AL-2b] clearing an anchor STAYS cleared across a reload", () => {
  // The seed marker has to be persisted, not per-session. With an in-memory guard the
  // seed re-runs on the next page load and re-adopts the backend value the user just
  // dragged away — an undo that silently undoes itself.
  resetStorage();
  const s = makeState();
  s.mapSegmentsData = () => ({ area_label_anchors: { "5": { pct_x: 30, pct_y: 80 } } });
  assert.deepEqual(s.areaLabelAnchor(5), { pct_x: 30, pct_y: 80 });

  s.clearAreaLabelAnchor("5");
  assert.equal(s.areaLabelAnchor(5), null);

  const reloaded = makeState();
  reloaded.mapSegmentsData = () => ({ area_label_anchors: { "5": { pct_x: 30, pct_y: 80 } } });
  assert.equal(reloaded.areaLabelAnchor(5), null,
    "the cleared anchor was re-seeded from the stale backend value on reload");
});

test("[AL-4] the seed also reads the dashboard snapshot (the plain dashboard fetches no segments)", () => {
  resetStorage();
  const s = makeState();
  s.mapSegmentsData = () => null;
  s.dashboardSnapshot = () => ({ area_label_anchors: { "7": { pct_x: 12, pct_y: 34 } } });
  assert.deepEqual(s.areaLabelAnchor(7), { pct_x: 12, pct_y: 34 });
});

test("[AL-6] the two label kinds do not share a namespace", () => {
  resetStorage();
  const s = makeState();
  s.setRoomNameAnchorLocal("5", 10, 10);
  s.setAreaLabelAnchorLocal("5", 90, 90);
  assert.deepEqual(s.roomNameAnchor("5"), { x: 10, y: 10 });
  assert.deepEqual(s.areaLabelAnchor("5"), { pct_x: 90, pct_y: 90 });
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
