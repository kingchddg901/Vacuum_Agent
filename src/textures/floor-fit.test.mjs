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
 * [FFIT-8] an arrow pressed on a ROTATED map moves the mask the way the screen reads,
 *          proven by composing with the CSS matrix rather than by restating the table.
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { coverFactor, resolveFit, normalizeFit, screenDeltaToCanvas,
         MIN_FIT_SCALE, MAX_FIT_SCALE, supersampleFactor, SUPERSAMPLE_TARGET_PX } from "./floor-fit.js";

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

  // BELOW COVER the room is deliberately not filled, but the pan must stay ALIVE --
  // collapsing its travel to zero there is what made the arrows dead while the readout
  // still read `x -1.00`. Slack is a DISTANCE (|dw - bw| / 2), so it is never negative
  // (which would invert the pan) and never zero merely for being under cover.
  //
  // This clause used to assert `small.panX === 0` WITHOUT PASSING tx -- so panX was
  // `0 * slack` and the assertion held for any slack whatsoever. It could not have failed
  // for the reason it gave. tx is passed now, which is the whole point.
  const small = resolveFit({ W, H, sw: MASK, sh: MASK, rw: r.rw, rh: r.rh, scale: 0.25, tx: -1 });
  assert.ok(small.slackX > 0 && small.slackY > 0, "a sub-cover mask still has somewhere to go");
  assert.ok(small.panX < 0, "and tx = -1 actually moves it");
  assert.ok(small.dw < r.rw, "precondition: this scale really is below cover");
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

test("[FFIT-7] the pan is alive at EVERY scale in the legal range, and junk cannot widen it", () => {
  // THE REAL DEFECT, off the live box: a placement saved at 0.30x with the pan at its
  // stops drew a room 9/10 bare AND `x -1.00` moved the mask not at all. Two symptoms,
  // one cause -- slack was `max(0, dw - bw)`, which is zero for every scale under cover.
  //
  // The first fix floored the SCALE at 1 so that state was unreachable. That was wrong
  // for this control: zooming out is how a material gets inspected, because a room is a
  // few hundred canvas pixels and a 2048 mask arrives heavily downsampled. So the range
  // is back and the GEOMETRY carries the guarantee instead.
  const r = ROOMS[0], { W, H } = buf(r);
  const fit = (over) => resolveFit({ W, H, sw: MASK, sh: MASK, rw: r.rw, rh: r.rh, ...over });

  for (const scale of [MIN_FIT_SCALE, 0.3, 0.5, 0.95, 1, 1.5, MAX_FIT_SCALE]) {
    const g = fit({ scale, tx: -1, ty: 1 });
    assert.ok(g.slackX > 0 && g.slackY > 0, `scale ${scale}: slack collapsed`);
    assert.ok(g.panX < 0 && g.panY > 0, `scale ${scale}: the arrows cannot move the mask`);
    // Never negative -- that would invert the pan and send the mask the wrong way.
    assert.ok(g.slackX >= 0 && g.slackY >= 0, `scale ${scale}: slack went negative`);
  }

  // The sub-cover range really is sub-cover, or the loop above proves nothing.
  assert.ok(fit({ scale: 0.3 }).dw < r.rw, "0.3 must actually fail to cover");
  assert.ok(fit({ scale: 1 }).dw >= r.rw, "...and 1 must cover");

  // ABLATION: the OLD slack formula must fail the loop, or this test would have passed
  // on the shipped bug. Recomputed here from the same inputs rather than mocked.
  const g = fit({ scale: 0.3, tx: -1 });
  const bw = r.rw;                                  // rad 0, so the room's extent is its width
  assert.equal(Math.max(0, (g.dw - bw) / 2), 0, "the old formula gave zero slack here");
  assert.ok(g.slackX > 0, "...and the new one does not -- that difference IS the fix");

  // The bounds, and the stops.
  assert.deepEqual(normalizeFit({ tx: -9, ty: 9, scale: 99 }),
    { tx: -1, ty: 1, scale: MAX_FIT_SCALE });
  assert.equal(normalizeFit({ scale: 0.01 }).scale, MIN_FIT_SCALE);

  // ABSENT STAYS ABSENT. Writing a default here would turn "never placed" into "placed at
  // the default" and lose the distinction the storage layer keeps with _UNSET.
  assert.deepEqual(normalizeFit({}), {});
  assert.deepEqual(normalizeFit({ tx: 0.5 }), { tx: 0.5 }, "no scale key invented");
  for (const junk of [null, undefined, [], [1], "x", 7]) {
    assert.deepEqual(normalizeFit(junk), {}, `${JSON.stringify(junk) ?? String(junk)} is not a fit`);
  }
  // A non-finite value is dropped, not clamped to a bound -- NaN would survive Math.min.
  assert.deepEqual(normalizeFit({ scale: NaN, tx: "abc" }), {});
});

test("[FFIT-8] an arrow moves the mask the way the SCREEN reads it, at every map rotation", () => {
  // The live map is displayed through `.evcc-map-content-rotator`, a CSS rotate(rot) on the
  // canvas's parent. The pad, the handler and the draw were each correct on their own and
  // the mask still slid VERTICALLY when "right" was pressed on a quarter-turned map, which
  // is why this is checked as a ROUND TRIP through the real display transform instead of by
  // asserting the lookup table back at itself -- a mirrored table would satisfy that.

  /** The CSS the rotator actually applies: content (x,y) -> screen. rotate(90deg) is the
   *  measured `matrix(0, 1, -1, 0, 0, 0)`, i.e. (x,y) -> (-y, x). */
  const contentToScreen = (x, y, deg) => {
    const r = (deg * Math.PI) / 180;
    const cos = Math.round(Math.cos(r)), sin = Math.round(Math.sin(r)); // quarter turns only
    return [x * cos - y * sin, x * sin + y * cos];
  };

  const SCREEN = { "right": [1, 0], "left": [-1, 0], "up": [0, -1], "down": [0, 1] };
  for (const rot of [0, 90, 180, 270]) {
    for (const [name, [sx, sy]] of Object.entries(SCREEN)) {
      const [cx, cy] = screenDeltaToCanvas(sx, sy, rot);
      const [bx, by] = contentToScreen(cx, cy, rot);
      assert.deepEqual([bx, by], [sx, sy],
        `at ${rot}deg, "${name}" must still travel ${name} on screen; ` +
        `canvas delta (${cx}, ${cy}) displays as (${bx}, ${by})`);
    }
  }

  // ABLATION: the identity table must NOT satisfy the round trip at a quarter turn, or this
  // test would have passed on the shipped bug.
  const identity = (dx, dy) => [dx, dy];
  const [ix, iy] = contentToScreen(...identity(1, 0), 90);
  assert.notDeepEqual([ix, iy], [1, 0],
    "if the un-rotated delta already displays as 'right' at 90deg this test cannot fail");

  // Rotation is normalised, not trusted: the accessor can hand back 360, a negative, or a
  // float, and an unmatched switch value would silently fall through to the identity --
  // which is precisely the shipped bug, reintroduced quietly.
  assert.deepEqual(screenDeltaToCanvas(1, 0, 360), [1, 0]);
  assert.deepEqual(screenDeltaToCanvas(1, 0, -90), screenDeltaToCanvas(1, 0, 270));
  assert.deepEqual(screenDeltaToCanvas(1, 0, 90.4), screenDeltaToCanvas(1, 0, 90));
  assert.deepEqual(screenDeltaToCanvas(1, 0, null), [1, 0], "absent rotation is identity");
});

test("[FFIT-9] the supersample reaches its stated TARGET, and is self-bounding without a cap", () => {
  // THE INPUT THAT MAKES THIS RED is restoring `Math.min(4, ...)` at the call site, which
  // is what shipped until 2026-11-15. It was a cap stated in the wrong UNIT: the target is
  // an output SIZE in canvas pixels, the cap bounded the MULTIPLIER, and the two disagree
  // for every raster below ~300 texels.
  const near = (got, want, tol, msg) =>
    assert.ok(Math.abs(got - want) <= tol, `${msg}: got ${got}, wanted ~${want} (+-${tol})`);

  // His map, measured on the box 2026-11-15. Under the cap this was 4 -> a 1024 canvas,
  // 15% short of the ~1200 the comment one line above it promised.
  assert.equal(supersampleFactor(256, 245), 5, "a 256-texel raster must reach the target, not stop at 4x");
  near(256 * supersampleFactor(256, 245), SUPERSAMPLE_TARGET_PX, 100, "256 raster canvas");

  // The smaller the raster, the worse the cap missed -- 60 texels reached 240, five times short.
  assert.equal(supersampleFactor(60, 60), 20, "a tiny raster must still reach the target");
  near(60 * supersampleFactor(60, 60), SUPERSAMPLE_TARGET_PX, 100, "60 raster canvas");

  // THE CLAIM THAT DROPPING THE CAP IS SAFE, asserted rather than argued: the formula is
  // self-bounding, so no cap is needed to keep the canvas finite. Sweep the real range.
  let worst = 0, at = 0;
  for (let W = 20; W < 1400; W++) {
    const px = W * supersampleFactor(W, W);
    if (px > worst) { worst = px; at = W; }
  }
  assert.ok(worst <= 1700, `canvas must stay bounded without a cap; worst ${worst} at W=${at}`);
  // 1600 at W=800 -- and W=800 is ABOVE where the old cap ever applied, which is the point:
  // the cap bounded nothing at the top and only undershot at the bottom.
  assert.equal(worst, 1600, "the bound is set by the formula, not by any cap");

  // The long axis governs, so a wide thin raster is not supersampled by its short side.
  assert.equal(supersampleFactor(240, 1200), supersampleFactor(1200, 240), "long axis governs");
  assert.equal(supersampleFactor(1200, 240), 1, "a raster already at target is not upscaled");

  // A raster LARGER than the target is left alone rather than shrunk.
  assert.equal(supersampleFactor(2400, 2400), 1, "never below 1 -- a big raster is not downsampled here");

  // Junk degrades to 1 rather than reaching canvas.width as NaN/0, which would paint nothing.
  for (const [w, h] of [[0, 0], [NaN, NaN], [-5, -5], [null, null], ["x", "x"], [undefined, undefined]]) {
    assert.equal(supersampleFactor(w, h), 1, `${String(w)}x${String(h)} must fall back to 1`);
  }
});
