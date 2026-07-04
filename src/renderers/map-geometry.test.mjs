// Run: node --test src/renderers/map-geometry.test.mjs
//
// Coverage targets (pure geometry helpers in src/renderers/map.js):
//   [PC-N] _polygonCentroid  — signed-area centroid, degenerate |area|<1e-10 vertex-average fallback
//   [SZ-N] _savedZoneBbox    — [minX,minY,maxX,maxY] from >=3 finite normalized points, else null
//   [OT-N] _overlayTransform — object-fit:contain letterbox scale sx/sy + centering offset (proto method,
//                              reached transitively via the exported applyMapRenderers mixin)
//
// _polygonCentroid / _savedZoneBbox are module-private functions given a minimal named `export`
// (add-export policy). _overlayTransform stays a proto method — zero source change — mixed onto a
// bare object and called with a fake `state` (it uses no `this`).

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  _polygonCentroid,
  _savedZoneBbox,
  applyMapRenderers,
} from "./map.js";

// Mix the renderer methods onto a bare object so we can reach the proto-scoped _overlayTransform
// without constructing the whole card. It reads only state.mapImageSize() and pure math.
const proto = {};
applyMapRenderers(proto);
const overlayTransform = (size) =>
  proto._overlayTransform.call(proto, { mapImageSize: () => size });

const approx = (a, b, eps = 1e-9) =>
  assert.ok(Math.abs(a - b) <= eps, `expected ${a} ≈ ${b}`);

/* ===================== _polygonCentroid ===================== */

test("[PC-1] unit square centroid is its geometric center (0.5, 0.5)", () => {
  const sq = [[0, 0], [1, 0], [1, 1], [0, 1]];
  const [cx, cy] = _polygonCentroid(sq);
  approx(cx, 0.5);
  approx(cy, 0.5);
});

test("[PC-2] centroid is translation-equivariant (square shifted +10,+20)", () => {
  const sq = [[10, 20], [11, 20], [11, 21], [10, 21]];
  const [cx, cy] = _polygonCentroid(sq);
  approx(cx, 10.5);
  approx(cy, 20.5);
});

test("[PC-3] right triangle centroid is the average of its 3 vertices (1/3 rule)", () => {
  // For a triangle the true area-centroid equals the vertex mean: ((0+6+0)/3, (0+0+3)/3).
  const tri = [[0, 0], [6, 0], [0, 3]];
  const [cx, cy] = _polygonCentroid(tri);
  approx(cx, 2);   // 6/3
  approx(cy, 1);   // 3/3
});

test("[PC-4] winding orientation does not change the result (area sign cancels)", () => {
  const cw  = [[0, 0], [0, 1], [1, 1], [1, 0]];   // reverse of the CCW square
  const [cx, cy] = _polygonCentroid(cw);
  approx(cx, 0.5);
  approx(cy, 0.5);
});

test("[PC-5] degenerate collinear points fall back to the vertex average", () => {
  // Zero signed area (all on y=0) -> |area|<1e-10 branch -> mean of x, mean of y.
  const line = [[0, 0], [2, 0], [4, 0]];
  const [cx, cy] = _polygonCentroid(line);
  approx(cx, 2);   // (0+2+4)/3
  approx(cy, 0);
  // Sanity: this is NOT the divide-by-zero NaN path.
  assert.ok(Number.isFinite(cx) && Number.isFinite(cy));
});

test("[PC-6] all-identical points (zero area) fall back to that same point, not NaN", () => {
  const dot = [[7, 9], [7, 9], [7, 9]];
  const [cx, cy] = _polygonCentroid(dot);
  approx(cx, 7);
  approx(cy, 9);
});

test("[PC-7] concave (L-shaped) polygon centroid sits inside the mass, not the vertex mean", () => {
  // An L made of a 2x2 square minus its top-right 1x1 quadrant (area 3). The true
  // area-centroid (5/6, 5/6) differs from the naive 6-vertex mean (0.75, 0.75) — proves
  // the signed-area weighting is actually used, not a plain average.
  const L = [[0, 0], [2, 0], [2, 1], [1, 1], [1, 2], [0, 2]];
  const [cx, cy] = _polygonCentroid(L);
  approx(cx, 5 / 6);
  approx(cy, 5 / 6);
  const vertexMeanX = (0 + 2 + 2 + 1 + 1 + 0) / 6;   // 1.0 — distinct from 5/6
  assert.notEqual(Number(cx.toFixed(6)), Number(vertexMeanX.toFixed(6)));
});

/* ===================== _savedZoneBbox ===================== */

test("[SZ-1] bbox spans min/max of a 3+ point normalized geometry", () => {
  const zone = { geometry: [[0.2, 0.1], [0.8, 0.3], [0.5, 0.9]] };
  assert.deepEqual(_savedZoneBbox(zone), [0.2, 0.1, 0.8, 0.9]);
});

test("[SZ-2] fewer than 3 points -> null (before any per-point filtering)", () => {
  assert.equal(_savedZoneBbox({ geometry: [[0, 0], [1, 1]] }), null);
  assert.equal(_savedZoneBbox({ geometry: [] }), null);
});

test("[SZ-3] missing / non-array geometry -> null", () => {
  assert.equal(_savedZoneBbox({}), null);
  assert.equal(_savedZoneBbox(null), null);
  assert.equal(_savedZoneBbox(undefined), null);
  assert.equal(_savedZoneBbox({ geometry: "not-an-array" }), null);
});

test("[SZ-4] non-finite and malformed points are skipped; survivors must still number >=3", () => {
  // 4 raw points, 1 malformed (wrong length) + 1 with NaN coord -> 2 valid -> null.
  const zone = {
    geometry: [[0.1, 0.2], [0.3], [NaN, 0.4], [0.5, 0.6]],
  };
  assert.equal(_savedZoneBbox(zone), null);
});

test("[SZ-5] with enough valid survivors the bbox ignores the skipped junk points", () => {
  const zone = {
    geometry: [
      [0.1, 0.5],
      [0.9, 0.2],
      "garbage",           // not an array -> skipped
      [Infinity, 0.7],     // non-finite -> skipped
      [0.4, 0.8],
    ],
  };
  // Survivors: (0.1,0.5), (0.9,0.2), (0.4,0.8) -> 3 valid.
  assert.deepEqual(_savedZoneBbox(zone), [0.1, 0.2, 0.9, 0.8]);
});

test("[SZ-6] string-numeric coords are coerced via Number()", () => {
  const zone = { geometry: [["0.2", "0.1"], ["0.6", "0.4"], ["0.3", "0.9"]] };
  assert.deepEqual(_savedZoneBbox(zone), [0.2, 0.1, 0.6, 0.9]);
});

test("[SZ-7] a 3-length point is rejected (strict length !== 2), dropping below 3 survivors", () => {
  const zone = { geometry: [[0.1, 0.2, 0.9], [0.3, 0.4], [0.5, 0.6]] };
  // First point has length 3 -> skipped -> only 2 survivors -> null.
  assert.equal(_savedZoneBbox(zone), null);
});

/* ===================== _overlayTransform ===================== */

test("[OT-1] unknown size -> identity (assumes square: sx=sy=100, no offset)", () => {
  const t = overlayTransform(undefined);
  assert.equal(t.sx, 100);
  assert.equal(t.sy, 100);
  approx(t.tx(0), 0);
  approx(t.tx(1), 100);
  approx(t.ty(0), 0);
  approx(t.ty(1), 100);
});

test("[OT-2] exact square -> identity, no letterbox bars", () => {
  const t = overlayTransform([512, 512]);
  assert.equal(t.sx, 100);
  assert.equal(t.sy, 100);
  approx(t.tx(0.5), 50);
  approx(t.ty(0.5), 50);
});

test("[OT-3] landscape (W>H) letterboxes vertically: full width, shrunk+centered height", () => {
  // 200x100 -> sy = 100*H/W = 50, offY = 25. x maps full; y sits in a centered band.
  const t = overlayTransform([200, 100]);
  assert.equal(t.sx, 100);
  approx(t.sy, 50);
  approx(t.tx(0), 0);
  approx(t.tx(1), 100);
  approx(t.ty(0), 25);   // top bar
  approx(t.ty(0.5), 50); // center stays centered
  approx(t.ty(1), 75);   // bottom bar
});

test("[OT-4] portrait (H>W) letterboxes horizontally: full height, shrunk+centered width", () => {
  // 100x200 -> sx = 100*W/H = 50, offX = 25. y maps full; x sits in a centered band.
  const t = overlayTransform([100, 200]);
  approx(t.sx, 50);
  assert.equal(t.sy, 100);
  approx(t.tx(0), 25);
  approx(t.tx(0.5), 50);
  approx(t.tx(1), 75);
  approx(t.ty(0), 0);
  approx(t.ty(1), 100);
});

test("[OT-5] non-positive / malformed size falls to the identity branch", () => {
  approx(overlayTransform([0, 100]).sx, 100);        // zero width -> guard fails -> identity
  approx(overlayTransform([200, 0]).sy, 100);        // zero height -> identity
  approx(overlayTransform([200]).sx, 100);           // wrong length -> identity
  approx(overlayTransform("nope").sx, 100);          // non-array -> identity
});

test("[OT-6] transform is invertible with the letterbox offset (round-trips a mid point)", () => {
  const t = overlayTransform([400, 100]);   // sy = 25, offY = 37.5
  approx(t.sy, 25);
  approx(t.ty(0), 37.5);
  approx(t.ty(1), 62.5);
  // A normalized 0.5 must land exactly at container-center 50 regardless of aspect.
  approx(t.tx(0.5), 50);
  approx(t.ty(0.5), 50);
});
