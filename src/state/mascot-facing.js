/**
 * ============================================================
 * STATE: MASCOT FACING (direction-aware sprite mirror)
 * ============================================================
 *
 * PURPOSE
 * -------
 * The map mascot rides the live robot pixel in follow mode. Without a facing
 * cue it "moonwalks" — glides backward while always drawn facing one way. The
 * robot exposes no heading on Eufy (the fork bakes orientation into the rendered
 * image bytes), so we derive travel direction from the CHANGE in the robot
 * anchor between live-pose updates.
 *
 * FRAME
 * -----
 * The anchor is normalized [nx, ny] in the rendered-image frame; _overlayTransform
 * maps it to content-% with NO x/y flip (monotonic), then the content rotator
 * turns the whole map by the display rotation while the sprite counter-rotates to
 * stay upright. So the SCREEN-horizontal travel is the anchor delta rotated by the
 * display rotation:  screen_dx = dnx·cos(rot) − dny·sin(rot)  (CSS rotate() is
 * clockwise in y-down screen coords). We only care about its SIGN.
 *
 * A deadband rejects localization jitter and (at a 90°-rotated map) purely-vertical
 * screen motion, returning 0 = "no confident horizontal move, keep the last facing".
 *
 * ============================================================
 */

/**
 * Screen-horizontal travel sign from an anchor delta, projected through the map's
 * display rotation. +1 = moving screen-right, -1 = screen-left, 0 = within the
 * deadband (no confident horizontal motion — caller should hold the last facing).
 *
 * @param {number} dnx - Δ anchor x (normalized image frame, cur - prev).
 * @param {number} dny - Δ anchor y (normalized image frame, cur - prev).
 * @param {number} rotDeg - display rotation applied to the map content (degrees).
 * @param {number} [deadband=0.004] - min |screen_dx| (normalized) to count as motion.
 * @returns {number} +1 | -1 | 0
 */
export function mascotFacingSign(dnx, dny, rotDeg, deadband = 0.004) {
  const dx = Number(dnx), dy = Number(dny);
  if (!Number.isFinite(dx) || !Number.isFinite(dy)) return 0;
  const r = ((Number(rotDeg) || 0) * Math.PI) / 180;
  const screenDx = dx * Math.cos(r) - dy * Math.sin(r);
  if (Math.abs(screenDx) < (Number(deadband) || 0)) return 0;
  return screenDx > 0 ? 1 : -1;
}

/**
 * Debounced facing commit. A vacuum's primary motion is boustrophedon (tight
 * back-and-forth), so a raw per-sample sign would flip the sprite every poll.
 * We only commit a NEW facing once the same new direction persists for
 * `hold` consecutive confident samples; a 0 (deadband) or same-as-committed
 * sample resets the candidate. Pure: takes + returns the small tracker so the
 * caller owns the state (and it's trivially testable).
 *
 * @param {{committed:number, cand:number, count:number}} prev - tracker (committed
 *   is -1|+1; cand is the pending direction; count is its streak).
 * @param {number} sign - this sample's sign from mascotFacingSign (-1|0|+1).
 * @param {number} [hold=2] - consecutive confident samples required to flip.
 * @returns {{committed:number, cand:number, count:number}} next tracker.
 */
export function commitFacing(prev, sign, hold = 2) {
  const committed = prev && (prev.committed === -1 || prev.committed === 1) ? prev.committed : 1;
  if (sign === 0 || sign === committed) {
    return { committed, cand: 0, count: 0 };            // no move / already facing there
  }
  const cand = prev && prev.cand === sign ? sign : sign;
  const count = (prev && prev.cand === sign ? prev.count : 0) + 1;
  if (count >= (hold || 1)) {
    return { committed: sign, cand: 0, count: 0 };      // sustained → flip
  }
  return { committed, cand, count };                    // still building the streak
}
