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
 * [FFIT-7] normalizeFit holds the scale at or above exact cover, so a CONTROL cannot
 *          steer into the state [FFIT-5] defends against -- where the room is part bare
 *          and the pan arrows are dead because slack is legitimately 0.
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { coverFactor, resolveFit, normalizeFit, MIN_FIT_SCALE, MAX_FIT_SCALE } from "./floor-fit.js";

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

test("[FFIT-7] normalizeFit floors the scale at exact cover, and that revives the pan", () => {
  // THE REAL CASE, off the live box: a placement saved at 0.30x with tx/ty at the stops.
  // The room drew 9/10 bare and `x -1.00` moved the mask not at all -- the pan was not
  // ignored, it was multiplying a slack of 0. Both symptoms have one cause and one fix.
  const r = ROOMS[0], { W, H } = buf(r);
  const stored = { tx: -1, ty: -1, scale: 0.3 };

  const raw = resolveFit({ W, H, sw: MASK, sh: MASK, rw: r.rw, rh: r.rh, ...stored });
  // `===` not assert.equal: a dead pan is `-1 * 0` = NEGATIVE zero, and strict equal
  // uses Object.is, which separates -0 from 0. The distinction is noise here and the
  // failure it produces ("+ -0 / - 0") reads like a real disagreement.
  assert.ok(raw.panX === 0, "precondition: below cover there is no slack to pan into");
  assert.ok(raw.dw < r.rw, "precondition: below cover the mask is narrower than the room");

  const fixed = resolveFit({ W, H, sw: MASK, sh: MASK, rw: r.rw, rh: r.rh,
                             ...normalizeFit(stored) });
  assert.equal(normalizeFit(stored).scale, MIN_FIT_SCALE, "0.30 is lifted to exact cover");
  assert.ok(fixed.slackX > 0 && fixed.slackY > 0, "and the slack comes back");
  assert.ok(fixed.panX < 0, "so tx = -1 actually moves the mask, and in the right direction");
  assert.ok(fixed.dw >= r.rw && fixed.dh >= r.rh, "and the room is covered again");

  // ABLATION -- the bound has to be able to answer both ways, or it proves nothing.
  assert.notEqual(raw.panX, fixed.panX,
    "if these agree the clamp did nothing and this test cannot fail");

  // The stops and the ceiling.
  assert.deepEqual(normalizeFit({ tx: -9, ty: 9, scale: 99 }),
    { tx: -1, ty: 1, scale: MAX_FIT_SCALE });

  // ABSENT STAYS ABSENT. Writing a default in here would turn "never placed" into
  // "placed at the default" and lose the distinction the storage layer keeps with _UNSET.
  assert.deepEqual(normalizeFit({}), {});
  assert.deepEqual(normalizeFit({ tx: 0.5 }), { tx: 0.5 }, "no scale key invented");
  for (const junk of [null, undefined, [], [1], "x", 7]) {
    assert.deepEqual(normalizeFit(junk), {}, `${JSON.stringify(junk) ?? String(junk)} is not a fit`);
  }
  // A non-finite value is dropped, not clamped to a bound -- NaN would survive Math.min.
  assert.deepEqual(normalizeFit({ scale: NaN, tx: "abc" }), {});
});
