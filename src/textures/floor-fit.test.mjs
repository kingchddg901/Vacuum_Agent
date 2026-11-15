/**
 * [FFIT-*] The geometry a fitted material is drawn with.
 *
 * This is the arithmetic that was inside `_decodeMaskLum`, where it could not be tested:
 * node has no canvas, which is why that function has never had a test and why the whole
 * floor draw is verified only by the visual-regression baselines in CI. Pulled out, the
 * one guarantee everything rests on becomes checkable.
 *
 * THE GUARANTEE: every placement in range still covers the room. `tx`/`ty` are fractions
 * of the slack that exists rather than pixels or percent, so +/-1 runs the mask's edge up
 * to the room's edge and no further. If that holds there is no out-of-range case to
 * detect, clamp or render differently anywhere downstream -- and if it does not, a
 * dragged placement exposes the room's base colour at an edge, silently, on whichever
 * rooms happen to be shaped wrong.
 *
 * Coverage targets
 * ----------------
 * [FFIT-1] cover is EXACT at 0 degrees -- it reduces to max(w/sw, h/sh).
 * [FFIT-2] cover holds at every angle, checked by the room's four corners rather than by
 *          re-deriving the formula the code uses.
 * [FFIT-3] THE GUARANTEE: at tx/ty = +/-1, and at every angle, the room is still covered.
 * [FFIT-4] slack exists at the default scale, because the buffer carries a margin -- so a
 *          placement has somewhere to go without the user having to zoom first.
 * [FFIT-5] scale buys pan range, and a scale below cover cannot produce negative slack.
 * [FFIT-6] junk and absent values fall back to the identity rather than NaN, which would
 *          reach a canvas transform and blank the room with nothing logged.
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { coverFactor, resolveFit } from "./floor-fit.js";

const MASK = 2048;

/** Does the drawn source cover the room rect? Checked in the SOURCE's frame by taking
 *  the room's four corners there -- deliberately NOT by re-using coverFactor, which is
 *  the thing under test. */
function covers(g, { rw, rh, rad }) {
  const hw = g.dw / 2, hh = g.dh / 2;
  const cos = Math.cos(-rad), sin = Math.sin(-rad);
  for (const [px, py] of [[-rw / 2, -rh / 2], [rw / 2, -rh / 2], [rw / 2, rh / 2], [-rw / 2, rh / 2]]) {
    // the room corner, relative to the room centre, rotated INTO the source frame,
    // then shifted by the pan (which is applied in that same frame)
    const x = px * cos - py * sin - g.panX;
    const y = px * sin + py * cos - g.panY;
    if (Math.abs(x) > hw + 1e-9 || Math.abs(y) > hh + 1e-9) return false;
  }
  return true;
}

const ANGLES = [0, 15, 30, 45, 60, 90, 123, 180, 237, 270, 315];
// A buffer is the room's bbox plus 5% a side, so it is 10% larger in each dimension.
const ROOMS = [
  { rw: 320, rh: 256 }, { rw: 480, rh: 88 }, { rw: 30, rh: 30 },
  { rw: 97, rh: 311 }, { rw: 1080, rh: 1080 },
];
const buf = (r) => ({ W: Math.round(r.rw * 1.1), H: Math.round(r.rh * 1.1) });

test("[FFIT-1] at 0 degrees cover is exactly max(w/sw, h/sh)", () => {
  assert.equal(coverFactor(200, 120, MASK, MASK, 0), 200 / MASK);
  assert.equal(coverFactor(120, 200, MASK, MASK, 0), 200 / MASK);
  // a non-square source takes whichever axis needs more
  assert.equal(coverFactor(100, 100, 50, 200, 0), 2);
  assert.equal(coverFactor(0, 0, 0, 0), 0, "a degenerate source yields 0, never NaN");
});

test("[FFIT-2] the cover holds at every angle", () => {
  for (const r of ROOMS) {
    const { W, H } = buf(r);
    for (const deg of ANGLES) {
      const rad = (deg * Math.PI) / 180;
      const g = resolveFit({ W, H, sw: MASK, sh: MASK, rw: r.rw, rh: r.rh, rad });
      assert.ok(g, "geometry must resolve");
      assert.ok(covers(g, { ...r, rad }),
        `${r.rw}x${r.rh} at ${deg} deg is not covered at the default placement`);
    }
  }
});

test("[FFIT-3] a placement at the limit still covers the room, at every angle", () => {
  for (const r of ROOMS) {
    const { W, H } = buf(r);
    for (const deg of ANGLES) {
      const rad = (deg * Math.PI) / 180;
      for (const [tx, ty] of [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [-1, -1], [1, -1]]) {
        const g = resolveFit({ W, H, sw: MASK, sh: MASK, rw: r.rw, rh: r.rh, rad, tx, ty });
        assert.ok(covers(g, { ...r, rad }),
          `${r.rw}x${r.rh} at ${deg} deg, pan (${tx},${ty}) stopped covering the room`);
      }
      // ...and beyond the range, which is clamped rather than honoured.
      const far = resolveFit({ W, H, sw: MASK, sh: MASK, rw: r.rw, rh: r.rh, rad, tx: 9, ty: -9 });
      assert.ok(covers(far, { ...r, rad }), "an out-of-range pan must clamp, not expose");
    }
  }
});

test("[FFIT-4] the margin leaves real slack at the default scale", () => {
  for (const r of ROOMS) {
    const { W, H } = buf(r);
    const g = resolveFit({ W, H, sw: MASK, sh: MASK, rw: r.rw, rh: r.rh });
    assert.ok(g.slackX > 0 && g.slackY > 0,
      `${r.rw}x${r.rh}: a placement must have somewhere to go without zooming first `
      + `(slack ${g.slackX.toFixed(2)}, ${g.slackY.toFixed(2)})`);
  }
});

test("[FFIT-5] scale buys pan range, and slack never goes negative", () => {
  const r = ROOMS[0], { W, H } = buf(r);
  const base = resolveFit({ W, H, sw: MASK, sh: MASK, rw: r.rw, rh: r.rh });
  const zoom = resolveFit({ W, H, sw: MASK, sh: MASK, rw: r.rw, rh: r.rh, scale: 2 });
  assert.ok(zoom.slackX > base.slackX && zoom.slackY > base.slackY, "zooming in frees the pan");
  assert.equal(zoom.k, base.k * 2);

  // Below the cover the room genuinely cannot be covered; slack must floor at 0 rather
  // than go negative and invert the pan, which would move the mask the wrong way.
  const small = resolveFit({ W, H, sw: MASK, sh: MASK, rw: r.rw, rh: r.rh, scale: 0.25 });
  assert.ok(small.slackX >= 0 && small.slackY >= 0);
  assert.equal(small.panX, 0, "no slack means no pan, not a negative one");
});

test("[FFIT-6] junk falls back to the identity rather than reaching a transform as NaN", () => {
  const r = ROOMS[0], { W, H } = buf(r);
  const ident = resolveFit({ W, H, sw: MASK, sh: MASK, rw: r.rw, rh: r.rh });
  for (const junk of [NaN, Infinity, -Infinity, "1", null, undefined, {}, []]) {
    const g = resolveFit({
      W, H, sw: MASK, sh: MASK, rw: r.rw, rh: r.rh,
      scale: junk, tx: junk, ty: junk, rad: junk,
    });
    assert.ok(g, `${String(junk)} must still resolve`);
    for (const key of ["k", "dw", "dh", "cx", "cy", "panX", "panY"]) {
      assert.ok(Number.isFinite(g[key]),
        `${key} became ${g[key]} for ${String(junk)} -- a NaN here reaches a canvas `
        + "transform and blanks the room with nothing logged");
    }
    assert.equal(g.k, ident.k, `${String(junk)} must fall back to the identity scale`);
    assert.equal(g.panX, 0);
  }
  assert.equal(resolveFit({ W: 0, H: 0, sw: MASK, sh: MASK }), null, "a degenerate buffer yields null");
  assert.equal(resolveFit({ W, H, sw: 0, sh: 0 }), null, "an undecoded source yields null");
});
