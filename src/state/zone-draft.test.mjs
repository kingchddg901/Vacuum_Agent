// Unit tests for the zone-clean coordinate conversion (_rectToNormalized) + the
// multi-zone draft list. _rectToNormalized maps a pct rect (0-100 of the square map
// container) to a normalized image rect with the object-fit:contain letterbox
// correction — a box at 50% of the container is NOT 50% of a non-square image.
// Verified against the real X10 camera (360x301).
// Run: node --test src/state/zone-draft.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyMapState } from "./map.js";

function makeState() {
  const proto = {};
  applyMapState(proto);
  return Object.create(proto);
}

const conv = (rect, dims) => makeState()._rectToNormalized(rect, dims);
const approx = (a, b, eps = 1e-3) => Math.abs(a - b) <= eps;

test("[ZD-1] square image: pct maps straight to normalized (no letterbox)", () => {
  const r = conv({ x: 25, y: 40, w: 25, h: 20 }, { width: 500, height: 500 });
  assert.deepEqual(r.map((v) => +v.toFixed(4)), [0.25, 0.4, 0.5, 0.6]);
});

test("[ZD-2] wide image (360x301): a rect over the contained image -> full [0,0,1,1]", () => {
  // imgPctH = 100*301/360 = 83.611; offY = 8.194; offX = 0, imgPctW = 100.
  const r = conv({ x: 0, y: 8.194444, w: 100, h: 83.611111 }, { width: 360, height: 301 });
  assert.ok(approx(r[0], 0) && approx(r[1], 0));
  assert.ok(approx(r[2], 1) && approx(r[3], 1));
});

test("[ZD-3] wide image: top-left corner X maps directly, Y is letterbox-corrected", () => {
  const r = conv({ x: 20, y: 50, w: 20, h: 20 }, { width: 360, height: 301 });
  assert.ok(approx(r[0], 0.2));               // x: 20/100
  assert.ok(approx(r[1], 0.5, 2e-3));         // y: (50-8.194)/83.611 = 0.5
});

test("[ZD-4] tall image (300x400) letterboxes horizontally", () => {
  // imgPctW = 100*300/400 = 75; offX = 12.5; box at the image's left edge.
  const r = conv({ x: 12.5, y: 0, w: 20, h: 20 }, { width: 300, height: 400 });
  assert.ok(approx(r[0], 0) && approx(r[1], 0));
});

test("[ZD-5] corners clamp to [0,1] and order min<max regardless of drag direction", () => {
  const r = conv({ x: 90, y: 95, w: -120, h: -120 }, { width: 360, height: 301 });
  assert.ok(r[0] >= 0 && r[1] >= 0 && r[2] <= 1 && r[3] <= 1);
  assert.ok(r[0] <= r[2] && r[1] <= r[3]);
});

test("[ZD-6] no rect or bad dims -> null", () => {
  assert.equal(conv(null, { width: 360, height: 301 }), null);
  assert.equal(conv({ x: 0, y: 0, w: 10, h: 10 }, null), null);
  assert.equal(conv({ x: 0, y: 0, w: 10, h: 10 }, { width: 0, height: 0 }), null);
});

test("[ZD-7] a rect drawn entirely inside a letterbox bar -> null (degenerate)", () => {
  // 360x301 wide image -> top bar is y in [0, 8.194]. A box there collapses in Y.
  assert.equal(conv({ x: 20, y: 0, w: 30, h: 5 }, { width: 360, height: 301 }), null);
});

test("[ZD-8] canDrawZone requires support + live backdrop (rotation no longer blocks)", () => {
  const base = () => {
    const s = makeState();
    s.supportsZoneClean = () => true;
    s.isLiveBackdropActive = () => true;
    s.mapRotation = () => 0;
    return s;
  };
  assert.equal(base().canDrawZone(), true);
  let s = base(); s.supportsZoneClean = () => false;
  assert.equal(s.canDrawZone(), false);
  s = base(); s.isLiveBackdropActive = () => false;
  assert.equal(s.canDrawZone(), false);
  // Rotation is handled now (un-rotated at dispatch) — a rotated map still draws.
  s = base(); s.mapRotation = () => 90;
  assert.equal(s.canDrawZone(), true);
});

test("[ZD-9] multi-zone: addZoneDraft accumulates and caps at 10", () => {
  const s = makeState();
  for (let i = 0; i < 12; i++) s.addZoneDraft({ x: i, y: i, w: 5, h: 5 });
  assert.equal(s.zoneCount(), 10);
  assert.equal(s.zoneAtCap(), true);
  assert.equal(s.addZoneDraft({ x: 0, y: 0, w: 5, h: 5 }), false);
  s.removeZoneDraft(0);
  assert.equal(s.zoneCount(), 9);
  s.clearZoneDrafts();
  assert.equal(s.zoneCount(), 0);
});

test("[ZD-10] zoneDraftsToNormalizedRects converts all + drops degenerate", () => {
  const s = makeState();
  s.mapRotation = () => 0;
  s.addZoneDraft({ x: 25, y: 40, w: 25, h: 20 }); // valid
  s.addZoneDraft({ x: 20, y: 0, w: 30, h: 5 });   // degenerate (top letterbox bar)
  const rects = s.zoneDraftsToNormalizedRects({ width: 360, height: 301 });
  assert.equal(rects.length, 1);
  assert.equal(rects[0].length, 4);
});

test("[ZD-11] zoneDraftsToNormalizedRects un-rotates the drawn rect at 90°", () => {
  // A box drawn on a 90°-rotated square map maps to the swapped content region.
  // unrotatePct(.,.,90)=[fy,100-fx]: (25,40)->(40,75), (50,60)->(60,50) ->
  // {x:40,y:50,w:20,h:25} -> square 500 normalized [0.4,0.5,0.6,0.75].
  const s = makeState();
  s.supportsZoneClean = () => true;
  s.isLiveBackdropActive = () => true;
  s.mapRotation = () => 90;
  s.addZoneDraft({ x: 25, y: 40, w: 25, h: 20 });
  const [r] = s.zoneDraftsToNormalizedRects({ width: 500, height: 500 });
  assert.ok(approx(r[0], 0.4) && approx(r[1], 0.5));
  assert.ok(approx(r[2], 0.6) && approx(r[3], 0.75));
});
