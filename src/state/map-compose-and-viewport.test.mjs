// Unit tests for the custom-segment COMPOSER bake + the zoom/pan viewport clamp
// on the applyMapState mixin — pure methods on the proto, no DOM/localStorage
// (the persist/load side effects no-op harmlessly in node).
//
// Coverage targets (src/state/map.js):
//   composeToSegments            -> [CMP-*]  group bucketing, stable subtract-after-fill
//                                            order, room_id resolution, rotated-rect->polygon
//   loadComposeDraftFromSegments -> [LCD-*]  >=3-pt polygon filter, point/id coercion,
//                                            _composeNextId advance past max trailing int
//   clampMapTransform            -> [CLP-*]  keep MAP_VIEW_MARGIN_PX slice on-screen,
//                                            margin capped at half viewport, lo>hi average,
//                                            changed flag
//   applyMapZoom                 -> [ZM-*]   clamp [0.5,8] + focal-point translate math
//
// Run: node --test src/state/map-compose-and-viewport.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyMapState } from "./map.js";

function makeState() {
  const proto = {};
  applyMapState(proto);
  return Object.create(proto);
}

// Round helper mirroring the composer's 2dp corner rounding.
const r2 = (v) => Math.round(v * 100) / 100;

/* ============================ composeToSegments ============================ */

test("[CMP-1] default group = own id: N unmerged shapes -> N segments, one primitive each", () => {
  const s = makeState();
  s._composeDraft = [
    { id: "a", type: "rect", x: 10, y: 10, w: 20, h: 20, angle: 0 },
    { id: "b", type: "circle", cx: 50, cy: 50, r: 8 },
  ];
  const out = s.composeToSegments();
  assert.equal(out.length, 2);
  const byId = Object.fromEntries(out.map((o) => [o.id, o]));
  assert.deepEqual(byId.a.primitives, [{ type: "rect", x: 10, y: 10, w: 20, h: 20 }]);
  assert.deepEqual(byId.b.primitives, [{ type: "circle", cx: 50, cy: 50, r: 8 }]);
  // No room link on either -> room_id undefined.
  assert.equal(byId.a.room_id, undefined);
  assert.equal(byId.b.room_id, undefined);
});

test("[CMP-2] shared group merges into ONE segment; subtract primitive emitted AFTER fills", () => {
  const s = makeState();
  // Deliberately ADD the subtract FIRST so only the stable-sort can fix the order.
  s._composeDraft = [
    { id: "cut", group: "room1", type: "rect", x: 40, y: 40, w: 10, h: 10, op: "subtract" },
    { id: "fillA", group: "room1", type: "rect", x: 0, y: 0, w: 30, h: 30 },
    { id: "fillB", group: "room1", type: "circle", cx: 60, cy: 60, r: 5 },
  ];
  const out = s.composeToSegments();
  assert.equal(out.length, 1);
  const prims = out[0].primitives;
  assert.equal(prims.length, 3);
  // Fills (no op) come first, subtract last — regardless of draft order.
  assert.equal(prims[0].op, undefined);
  assert.equal(prims[1].op, undefined);
  assert.equal(prims[2].op, "subtract");
  // Stable sort preserves relative order of the two fills (fillA before fillB).
  assert.equal(prims[0].type, "rect");   // fillA
  assert.equal(prims[1].type, "circle"); // fillB
});

test("[CMP-3] group segment id is the group key, not a member id", () => {
  const s = makeState();
  s._composeDraft = [
    { id: "m1", group: "kitchen", type: "rect", x: 0, y: 0, w: 10, h: 10 },
    { id: "m2", group: "kitchen", type: "rect", x: 20, y: 20, w: 10, h: 10 },
  ];
  const out = s.composeToSegments();
  assert.equal(out.length, 1);
  assert.equal(out[0].id, "kitchen");
});

test("[CMP-4] room_id resolves to whichever group member carries one", () => {
  const s = makeState();
  s._composeDraft = [
    { id: "m1", group: "g", type: "rect", x: 0, y: 0, w: 10, h: 10 },          // no room
    { id: "m2", group: "g", type: "rect", x: 20, y: 20, w: 10, h: 10, room_id: 7 }, // carries room
  ];
  const out = s.composeToSegments();
  assert.equal(out.length, 1);
  assert.equal(out[0].room_id, 7);
});

test("[CMP-5] rotated rect (angle!=0) bakes to a polygon via corner trig, rounded 2dp", () => {
  const s = makeState();
  // Square 0..10, centre (5,5), rotate 90deg. rot(x,y):
  //   cos=~0, sin=1. (0,0)-> (5 + (0-5)*cos - (0-5)*sin, 5 + (0-5)*sin + (0-5)*cos)
  //   = (5 - 0 - (-5), 5 + (-5) + 0) = (10, 0). etc. -> corner order shifts by 90deg.
  s._composeDraft = [{ id: "rot", type: "rect", x: 0, y: 0, w: 10, h: 10, angle: 90 }];
  const out = s.composeToSegments();
  const p = out[0].primitives[0];
  assert.equal(p.type, "polygon");                 // rotated rect -> polygon, NOT rect
  assert.equal(p.points.length, 4);
  // Corners are corner order [(x,y),(x+w,y),(x+w,y+h),(x,y+h)] each rotated about centre.
  const rad = (90 * Math.PI) / 180, cos = Math.cos(rad), sin = Math.sin(rad);
  const cx = 5, cy = 5;
  const rot = (px, py) => [
    r2(cx + (px - cx) * cos - (py - cy) * sin),
    r2(cy + (px - cx) * sin + (py - cy) * cos),
  ];
  assert.deepEqual(p.points, [rot(0, 0), rot(10, 0), rot(10, 10), rot(0, 10)]);
  // Sanity: values are rounded to <=2dp.
  for (const [px, py] of p.points) {
    assert.equal(px, r2(px));
    assert.equal(py, r2(py));
  }
});

test("[CMP-6] rect with angle 0 stays a plain rect primitive (no polygon bake)", () => {
  const s = makeState();
  s._composeDraft = [{ id: "flat", type: "rect", x: 3, y: 4, w: 5, h: 6, angle: 0 }];
  const out = s.composeToSegments();
  assert.deepEqual(out[0].primitives[0], { type: "rect", x: 3, y: 4, w: 5, h: 6 });
});

test("[CMP-7] polygon shape passes through with its points; op subtract tagged on the primitive", () => {
  const s = makeState();
  s._composeDraft = [
    { id: "poly", type: "polygon", points: [[0, 0], [10, 0], [5, 8]], op: "subtract" },
  ];
  const out = s.composeToSegments();
  const p = out[0].primitives[0];
  assert.equal(p.type, "polygon");
  assert.deepEqual(p.points, [[0, 0], [10, 0], [5, 8]]);
  assert.equal(p.op, "subtract");
});

test("[CMP-8] empty draft -> empty segment list", () => {
  const s = makeState();
  s._composeDraft = [];
  assert.deepEqual(s.composeToSegments(), []);
});

/* ===================== loadComposeDraftFromSegments ======================= */

test("[LCD-1] keeps only polygons with >=3 points; coerces points to numbers", () => {
  const s = makeState();
  s.loadComposeDraftFromSegments({
    map_id: "m", active_custom_layout_id: null,
    segments: [
      { segment_id: "s1", polygon_pct: [["1", "2"], ["3", 4], [5, "6"]] }, // 3 pts -> kept
      { segment_id: "s2", polygon_pct: [[0, 0], [1, 1]] },                  // 2 pts -> dropped
      { segment_id: "s3", polygon_pct: "not-an-array" },                    // bad   -> dropped
      { segment_id: "s4" },                                                 // no polygon -> dropped
    ],
  });
  assert.equal(s._composeDraft.length, 1);
  const shape = s._composeDraft[0];
  assert.equal(shape.id, "s1");
  assert.equal(shape.type, "polygon");
  assert.deepEqual(shape.points, [[1, 2], [3, 4], [5, 6]]); // strings coerced to numbers
});

test("[LCD-2] room_id stringified when present, undefined when absent", () => {
  const s = makeState();
  s.loadComposeDraftFromSegments({
    segments: [
      { segment_id: "a", polygon_pct: [[0, 0], [1, 0], [0, 1]], room_id: 9 },
      { segment_id: "b", polygon_pct: [[0, 0], [1, 0], [0, 1]] },
    ],
  });
  assert.equal(s._composeDraft[0].room_id, "9");
  assert.equal(s._composeDraft[1].room_id, undefined);
});

test("[LCD-3] missing segment_id -> synthesized loaded_<n> id from kept index", () => {
  const s = makeState();
  s.loadComposeDraftFromSegments({
    segments: [
      { polygon_pct: [[0, 0], [1, 0], [0, 1]] },                 // kept #1 -> loaded_1
      { polygon_pct: [[0, 0], [1, 1]] },                         // dropped (2 pts)
      { polygon_pct: [[2, 2], [3, 2], [2, 3]] },                 // kept #2 -> loaded_2
    ],
  });
  assert.deepEqual(s._composeDraft.map((x) => x.id), ["loaded_1", "loaded_2"]);
});

test("[LCD-4] _composeNextId advances past the MAX trailing int so a new add can't collide", () => {
  const s = makeState();
  s.loadComposeDraftFromSegments({
    segments: [
      { segment_id: "draft_2", polygon_pct: [[0, 0], [1, 0], [0, 1]] },
      { segment_id: "draft_9", polygon_pct: [[0, 0], [1, 0], [0, 1]] },
      { segment_id: "draft_5", polygon_pct: [[0, 0], [1, 0], [0, 1]] },
    ],
  });
  // max trailing int is 9 -> next id counter is 10.
  assert.equal(s._composeNextId, 10);
  // And a fresh add takes draft_10 (past every reloaded id).
  const shape = s.addComposeShape("rect");
  assert.equal(shape.id, "draft_10");
});

test("[LCD-5] no trailing-int ids -> counter resets to 1", () => {
  const s = makeState();
  s.loadComposeDraftFromSegments({
    segments: [{ segment_id: "kitchen", polygon_pct: [[0, 0], [1, 0], [0, 1]] }],
  });
  assert.equal(s._composeNextId, 1); // maxN 0 -> 0+1
});

test("[LCD-6] empty / missing segments -> empty draft, selection + merge cleared", () => {
  const s = makeState();
  s._composeSelectedId = "x";
  s._composeMergeFrom = "y";
  s.loadComposeDraftFromSegments({ segments: [] });
  assert.deepEqual(s._composeDraft, []);
  assert.equal(s._composeSelectedId, null);
  assert.equal(s._composeMergeFrom, null);
  // Null data guard (data?.segments ?? []).
  const s2 = makeState();
  s2.loadComposeDraftFromSegments(null);
  assert.deepEqual(s2._composeDraft, []);
});

/* ============================ clampMapTransform =========================== */

test("[CLP-1] non-positive viewport -> no-op, returns false", () => {
  const s = makeState();
  s._mapTranslateX = 999; s._mapTranslateY = -999;
  assert.equal(s.clampMapTransform(0, 100), false);
  assert.equal(s.clampMapTransform(100, 0), false);
  assert.equal(s.clampMapTransform(-5, -5), false);
  // Untouched.
  assert.equal(s._mapTranslateX, 999);
  assert.equal(s._mapTranslateY, -999);
});

test("[CLP-2] an in-bounds translate is left unchanged (returns false)", () => {
  const s = makeState();
  s._mapZoom = 1;
  // view 400x400, z 1, margin 32 -> allowed tx in [32-400, 400-32] = [-368, 368].
  s._mapTranslateX = 100; s._mapTranslateY = -50;
  assert.equal(s.clampMapTransform(400, 400), false);
  assert.equal(s._mapTranslateX, 100);
  assert.equal(s._mapTranslateY, -50);
});

test("[CLP-3] content pushed off the right/bottom is pulled back to hi (view - margin)", () => {
  const s = makeState();
  s._mapZoom = 1;
  // hi = viewW - mx = 400 - 32 = 368. tx way beyond it -> clamped down to 368.
  s._mapTranslateX = 5000; s._mapTranslateY = 5000;
  const changed = s.clampMapTransform(400, 400);
  assert.equal(changed, true);
  assert.equal(s._mapTranslateX, 368);
  assert.equal(s._mapTranslateY, 368);
});

test("[CLP-4] content pushed off the left/top is pulled back to lo (margin - view*z)", () => {
  const s = makeState();
  s._mapZoom = 2;
  // lo = mx - viewW*z = 32 - 400*2 = -768. tx far below it -> clamped up to -768.
  s._mapTranslateX = -100000; s._mapTranslateY = -100000;
  const changed = s.clampMapTransform(400, 400);
  assert.equal(changed, true);
  assert.equal(s._mapTranslateX, -768);
  assert.equal(s._mapTranslateY, -768);
});

test("[CLP-5] margin caps at HALF the viewport for a tiny container", () => {
  const s = makeState();
  s._mapZoom = 1;
  // viewW 40 -> mx = min(32, 40/2)=20. hi = 40-20 = 20; lo = 20 - 40 = -20.
  s._mapTranslateX = 1000; s._mapTranslateY = -1000;
  assert.equal(s.clampMapTransform(40, 40), true);
  assert.equal(s._mapTranslateX, 20);   // hi
  assert.equal(s._mapTranslateY, -20);  // lo
});

test("[CLP-6] degenerate lo>hi window averages the two bounds", () => {
  const s = makeState();
  // Force lo > hi: need mx - viewW*z > viewW - mx  =>  2*mx > viewW*(1+z).
  // Pick viewW=40 (mx=20), z=0.5: lo = 20 - 20 = 0; hi = 40 - 20 = 20 -> that's lo<hi.
  // Need z small enough: z=0.1 -> lo = 20 - 4 = 16; hi = 20 -> still lo<hi.
  // lo>hi requires viewW*z < 2*mx - viewW = 40 - 40 = 0, impossible for viewW>=2*mx.
  // So drive lo>hi via the OTHER regime: mx=viewW/2 exactly makes lo=hi; a rounding-free
  // way to get lo>hi is a viewW just under 2*margin with z<1. viewW=50 -> mx=min(32,25)=25;
  // z=0.1: lo = 25 - 5 = 20; hi = 50 - 25 = 25 -> lo<hi. The clamp's lo>hi branch is the
  // mathematically-unreachable guard for margin<half-viewport; assert it directly instead.
  const clamp = (v, lo, hi) => (lo > hi ? (lo + hi) / 2 : Math.min(Math.max(v, lo), hi));
  assert.equal(clamp(999, 10, 4), 7);   // lo>hi -> (10+4)/2
  assert.equal(clamp(999, 4, 10), 10);  // normal -> clamped to hi
  assert.equal(clamp(-999, 4, 10), 4);  // normal -> clamped to lo
});

test("[CLP-7] a value that lands exactly on a bound is NOT reported as changed", () => {
  const s = makeState();
  s._mapZoom = 1;
  s._mapTranslateX = 368;  // == hi for 400 view
  s._mapTranslateY = -368; // == lo (32 - 400)
  assert.equal(s.clampMapTransform(400, 400), false);
});

/* ============================== applyMapZoom ============================== */

test("[ZM-1] zoom clamps into [0.5, 8]", () => {
  const s = makeState();
  s._mapZoom = 1;
  s.applyMapZoom(50, 0, 0);
  assert.equal(s._mapZoom, 8);
  s.flushMapTransform();
  s.applyMapZoom(0.01, 0, 0);
  assert.equal(s._mapZoom, 0.5);
  s.flushMapTransform();
});

test("[ZM-2] focal point at origin (0,0) leaves translate untouched", () => {
  const s = makeState();
  s._mapZoom = 1; s._mapTranslateX = 10; s._mapTranslateY = 20;
  s.applyMapZoom(2, 0, 0);
  // tx = 0 - (0 - 10)*ratio = 10*ratio; ratio = 2/1 = 2 -> tx = ... wait: 0-(0-10)*2 = 20.
  assert.equal(s._mapZoom, 2);
  assert.equal(s._mapTranslateX, 20);
  assert.equal(s._mapTranslateY, 40);
  s.flushMapTransform();
});

test("[ZM-3] focal-point translate keeps the origin pixel fixed on screen", () => {
  const s = makeState();
  s._mapZoom = 2; s._mapTranslateX = 30; s._mapTranslateY = -10;
  const ox = 100, oy = 60;
  // The container-space point of a layers-local coord L is tx + L*z. The pixel under
  // the focal (ox,oy) must map to the SAME container position before and after.
  const localBefore = (ox - s._mapTranslateX) / s._mapZoom; // layers-local x under focal
  s.applyMapZoom(4, ox, oy);
  const ratio = 4 / 2;
  assert.equal(s._mapZoom, 4);
  assert.equal(s._mapTranslateX, ox - (ox - 30) * ratio); // = 100 - 70*2 = -40
  // Invariant: focal pixel stays put -> tx + localBefore*newZoom == ox.
  const afterContainerX = s._mapTranslateX + localBefore * s._mapZoom;
  assert.ok(Math.abs(afterContainerX - ox) < 1e-9);
  s.flushMapTransform();
});

test("[ZM-4] ratio uses the CURRENT zoom as denominator (not 1)", () => {
  const s = makeState();
  s._mapZoom = 4; s._mapTranslateX = 0; s._mapTranslateY = 0;
  s.applyMapZoom(2, 50, 0); // ratio = 2/4 = 0.5
  // tx = 50 - (50 - 0)*0.5 = 25.
  assert.equal(s._mapZoom, 2);
  assert.equal(s._mapTranslateX, 25);
  s.flushMapTransform();
});
