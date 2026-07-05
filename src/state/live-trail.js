/**
 * ============================================================
 * STATE: LIVE CLEANING TRAIL (position-derived)
 * ============================================================
 *
 * The eufy-clean fork exposes a trail attribute, but it CAPS/STICKS after roughly one
 * room's worth of movement while the robot's ANCHOR keeps updating. So we build the trail
 * ourselves from the anchor (one point per ~2s live-pose poll):
 *
 *   • CLEANING -> append the anchor (dedup stationary repeats), bounded length,
 *   • DOCKED   -> FREEZE (don't extend) so a mid-clean recharge just pauses the trace and
 *                 it CONTINUES when the robot resumes.
 *
 * The RESET is NOT derived here (a dock is NOT a new clean — a mid-job recharge / strict-
 * order return docks WITHIN a clean and must not split the trace). The card fires
 * ``state.resetLiveTrail()`` from its own clean DISPATCH points (room Start / zone Clean /
 * saved-zone clean), so exactly one trace spans a whole multi-room clean and only a new,
 * card-initiated clean wipes it. (App-started runs don't dispatch through the card, so they
 * continue the previous trace — an accepted limitation.)
 *
 * Pure: takes + returns the trail list so the caller owns the state and it's testable.
 * ============================================================
 */

/**
 * Fold one live-pose sample into the position-built cleaning trail.
 *
 * @param {Array|null} trail - prior trail (list of [x,y]) or null.
 * @param {[number,number]|null} anchor - fresh normalized robot anchor, or null (no pose).
 * @param {boolean} docked - is the robot docked this poll (freeze, don't extend).
 * @param {{max?: number}} [opts] - max point count (oldest drop past it).
 * @returns {Array|null} the next trail.
 */
export function accumulateTrail(trail, anchor, docked, opts = {}) {
  const max = Number.isFinite(opts.max) ? opts.max : 600;
  let t = Array.isArray(trail) ? trail : null;

  if (!Array.isArray(anchor) || anchor.length !== 2) return t;   // no fresh pose -> hold
  if (docked) return t;                                          // docked -> freeze (no extend)

  t = t || [];
  const last = t[t.length - 1];
  if (!last || last[0] !== anchor[0] || last[1] !== anchor[1]) {  // dedup stationary repeats
    t.push([anchor[0], anchor[1]]);
    if (t.length > max) t.shift();                               // bounded memory / draw cost
  }
  return t;
}
