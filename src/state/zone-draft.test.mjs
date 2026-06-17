// Unit tests for zoneDraftToNormalizedRect — the pct-draft → normalized-image-rect
// conversion with the object-fit:contain letterbox correction. The live map renders
// inside a forced-square container, so a non-square camera image is letterboxed: a
// box at 50% of the container is NOT at 50% of the image. Verified against the real
// X10 camera (360x301).
// Run: node --test src/state/zone-draft.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyMapState } from "./map.js";

function makeState(draft) {
  const proto = {};
  applyMapState(proto);
  const s = Object.create(proto);
  if (draft !== undefined) s._zoneDraft = draft;
  return s;
}

const approx = (a, b, eps = 1e-3) => Math.abs(a - b) <= eps;

test("[ZD-1] square image: pct maps straight to normalized (no letterbox)", () => {
  const s = makeState({ x: 25, y: 40, w: 25, h: 20 });
  const r = s.zoneDraftToNormalizedRect({ width: 500, height: 500 });
  assert.deepEqual(r.map((v) => +v.toFixed(4)), [0.25, 0.4, 0.5, 0.6]);
});

test("[ZD-2] wide image (360x301): a draft over the contained image -> full [0,0,1,1]", () => {
  // imgPctH = 100*301/360 = 83.611; offY = 8.194; offX = 0, imgPctW = 100.
  const s = makeState({ x: 0, y: 8.194444, w: 100, h: 83.611111 });
  const r = s.zoneDraftToNormalizedRect({ width: 360, height: 301 });
  assert.ok(approx(r[0], 0) && approx(r[1], 0));
  assert.ok(approx(r[2], 1) && approx(r[3], 1));
});

test("[ZD-3] wide image: top-left corner X maps directly, Y is letterbox-corrected", () => {
  // Box top-left at container (20%, 50%); assert its normalized top-left corner.
  const s = makeState({ x: 20, y: 50, w: 20, h: 20 });
  const r = s.zoneDraftToNormalizedRect({ width: 360, height: 301 });
  assert.ok(approx(r[0], 0.2));               // x: 20/100
  assert.ok(approx(r[1], 0.5, 2e-3));         // y: (50-8.194)/83.611 = 0.5
});

test("[ZD-4] tall image (300x400) letterboxes horizontally", () => {
  // imgPctW = 100*300/400 = 75; offX = 12.5; imgPctH = 100, offY = 0.
  // Box top-left at the image's left edge (12.5%, 0%).
  const s = makeState({ x: 12.5, y: 0, w: 20, h: 20 });
  const r = s.zoneDraftToNormalizedRect({ width: 300, height: 400 });
  assert.ok(approx(r[0], 0) && approx(r[1], 0));
});

test("[ZD-5] corners clamp to [0,1] and order min<max regardless of drag direction", () => {
  const s = makeState({ x: 90, y: 95, w: -120, h: -120 }); // up-left, past the edges
  const r = s.zoneDraftToNormalizedRect({ width: 360, height: 301 });
  assert.ok(r[0] >= 0 && r[1] >= 0 && r[2] <= 1 && r[3] <= 1);
  assert.ok(r[0] <= r[2] && r[1] <= r[3]);
});

test("[ZD-6] no draft or bad dims -> null", () => {
  assert.equal(makeState().zoneDraftToNormalizedRect({ width: 360, height: 301 }), null);
  assert.equal(
    makeState({ x: 0, y: 0, w: 10, h: 10 }).zoneDraftToNormalizedRect(null),
    null,
  );
  assert.equal(
    makeState({ x: 0, y: 0, w: 10, h: 10 }).zoneDraftToNormalizedRect({ width: 0, height: 0 }),
    null,
  );
});

test("[ZD-7] a box drawn entirely inside a letterbox bar -> null (degenerate)", () => {
  // 360x301 wide image -> top bar is y in [0, 8.194]. A box there collapses in Y.
  const s = makeState({ x: 20, y: 0, w: 30, h: 5 });
  assert.equal(s.zoneDraftToNormalizedRect({ width: 360, height: 301 }), null);
});

test("[ZD-8] canDrawZone requires support + live backdrop + rotation 0", () => {
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
  s = base(); s.mapRotation = () => 90;
  assert.equal(s.canDrawZone(), false);
});
