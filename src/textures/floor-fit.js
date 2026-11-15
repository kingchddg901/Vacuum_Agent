/**
 * ============================================================
 * TEXTURES: FITTED-MATERIAL PLACEMENT GEOMETRY
 * ============================================================
 *
 * PURPOSE
 * -------
 * Where a FITTED material's mask lands inside a room's buffer: the cover scale, the
 * centre, and how far a placement may pan before it would stop covering the room.
 *
 * WHY IT IS ITS OWN MODULE
 * ------------------------
 * It is pure arithmetic that lives inside a canvas draw, which is the worst place for
 * it: node has no canvas, so `_decodeMaskLum` has never had a test and cannot easily get
 * one. Taking the geometry out leaves the draw as four canvas calls over numbers that
 * ARE tested, and makes the one guarantee everything else rests on checkable --
 * that every placement in range still covers the room.
 *
 * THE NORMALISATION, which is the whole design
 * --------------------------------------------
 * `tx`/`ty` are NOT pixels and NOT percent. They are fractions of the slack that
 * actually exists: +/-1 pans until the mask's edge reaches the ROOM's edge. Three things
 * fall out of that and none of them is free any other way:
 *
 *   - AT OR ABOVE EXACT COVER (scale >= 1), every value in range still covers the room BY
 *     CONSTRUCTION, so there is no out-of-range case to detect, clamp or render
 *     differently. Below cover the user has explicitly asked not to fill the room -- the
 *     pan still runs edge-to-edge, it simply has a smaller mask to run;
 *   - the stored number keeps its meaning when the raster resolution or the supersample
 *     changes, both of which move with the map and neither of which the user chose;
 *   - a bigger `scale` buys more pan range automatically, because slack is derived
 *     rather than configured.
 *
 * WHAT IS MEASURED AGAINST WHAT
 * -----------------------------
 * The cover is computed against the BUFFER (the room's bounding box plus a margin), so
 * that margin becomes slack to pan into at the default scale. The FREEDOM is measured
 * against the ROOM, because the room is the only part ever sampled -- everything outside
 * it fails the per-pixel rid test in the floor draw and is never read.
 */

/**
 * Cover factor for an axis-aligned box of `w`x`h`, by a source of `sw`x`sh`, at `rad`.
 *
 * Computed in the SOURCE's frame: rotating the box by -rad gives an axis-aligned extent
 * of (w|cos| + h|sin|, w|sin| + h|cos|), and covering THAT covers the box itself. The
 * tempting alternative -- scale until the ROTATED IMAGE's bounding box covers the box --
 * under-scales and leaves the corners empty, because a rect's AABB is larger than the
 * rect. At rad = 0 this reduces exactly to max(w/sw, h/sh).
 */
/**
 * The scale range a PLACEMENT may use.
 *
 * The floor is BELOW exact cover on purpose. This control is also how a material gets
 * LOOKED AT: a room is a few hundred canvas pixels, so a 2048 mask arrives downsampled
 * and zooming out is the only way to see what the mask actually is. Covering the room is
 * what the DEFAULT does, not a rule the control enforces.
 *
 * Below cover the room is deliberately not filled -- bare floor shows through, and that
 * is the user's choice rather than a defect. What is NOT acceptable is what used to come
 * with it: `slackX` floored at 0, so `panX = tx * 0` and the arrows went dead while the
 * readout still read `x -1.00` (measured live at `0.30x`: a room 9/10 bare and a pan of
 * -1.00 that moved nothing). That was the real bug, and it is fixed in `resolveFit` by
 * measuring slack as a DISTANCE, so the pan is alive at every scale in this range --
 * which is what lets this floor go back down safely.
 */
export const MIN_FIT_SCALE = 0.25;
export const MAX_FIT_SCALE = 4;

/**
 * Clamp a placement to the range a placement may legally hold.
 *
 * Exported because TWO callers must agree and they are in different modules: the draft
 * setter (so the control cannot author an illegal placement) and the floor draw (so a
 * placement ALREADY STORED below cover -- which existed before this bound did -- renders
 * covered rather than bare). Centralising the question rather than the numbers: a second
 * copy of `0.25` was exactly how the control and the draw came to disagree.
 *
 * ABSENT STAYS ABSENT. A missing axis is not 0 and a missing scale is not 1: the draw
 * treats absent as its own default, and writing one in here would turn "never placed"
 * into "placed at the default", which is the distinction `_UNSET` exists to keep.
 */
export function normalizeFit(fit) {
  const out = {};
  if (!fit || typeof fit !== "object" || Array.isArray(fit)) return out;
  const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
  for (const [k, lo, hi] of [["tx", -1, 1], ["ty", -1, 1],
                             ["scale", MIN_FIT_SCALE, MAX_FIT_SCALE]]) {
    if (!(k in fit)) continue;
    const n = Number(fit[k]);
    if (Number.isFinite(n)) out[k] = clamp(n, lo, hi);
  }
  return out;
}

/**
 * Turn an arrow's SCREEN direction into the CANVAS direction that moves the mask that way.
 *
 * The live map is displayed through `.evcc-map-content-rotator`, a CSS `rotate(rot)` on the
 * canvas's parent (renderers/map.js) -- so the canvas's own +x is not the screen's +x. At a
 * quarter turn the mask therefore slides VERTICALLY when "right" is pressed, with every
 * layer underneath behaving correctly: the pad is `right = (1,0)`, the handler does
 * `tx += dx`, and the draw translates +x. Nothing is swapped anywhere; the display is
 * rotated and the arrows were labelled in the frame the user reads, not the one they act in.
 *
 * This is the SAME defect `unrotatePct` exists for one module over ("a 90/270 drag was
 * previously off by the rotation") -- that one moves a POINT in a 0-100 pct box, this moves
 * a DIRECTION, so the 100-x reflections do not apply and it gets its own function rather
 * than a reinterpreted call to that one.
 *
 * The rotator turns in 90-degree steps only, so this is exact and is a table, not
 * trigonometry. Content->screen is `rotate(+rot)`, i.e. (x,y) -> (-y, x) at 90; this is its
 * inverse. Identity at 0, which is every unrotated map.
 *
 * NOTE what is deliberately NOT undone here: the room's own `floor_rotation`. The draw
 * rotates into the mask's frame BEFORE panning, so a pan runs along the material's own
 * axes -- planks slide lengthwise rather than diagonally. That is a design choice, not an
 * oversight, and undoing it here would silently reverse it.
 */
export function screenDeltaToCanvas(dx, dy, rotDeg) {
  const rot = ((Math.round(Number(rotDeg) || 0) % 360) + 360) % 360;
  switch (rot) {
    case 90:  return [dy, -dx];
    case 180: return [-dx, -dy];
    case 270: return [-dy, dx];
    default:  return [dx, dy];
  }
}

export function coverFactor(w, h, sw, sh, rad = 0) {
  if (!(sw > 0 && sh > 0)) return 0;
  const ac = Math.abs(Math.cos(rad)), as = Math.abs(Math.sin(rad));
  return Math.max((w * ac + h * as) / sw, (w * as + h * ac) / sh);
}

/**
 * Resolve a placement into the numbers a draw needs.
 *
 * @param {object} o
 * @param {number} o.W  buffer width            @param {number} o.H  buffer height
 * @param {number} o.sw source width            @param {number} o.sh source height
 * @param {number} [o.rx] room x inside buffer  @param {number} [o.ry] room y inside buffer
 * @param {number} [o.rw] room width            @param {number} [o.rh] room height
 * @param {number} [o.rad]   rotation, radians
 * @param {number} [o.scale] placement scale, 1 = exact cover of the buffer
 * @param {number} [o.tx]    pan, -1..1 of the available slack
 * @param {number} [o.ty]
 * @returns {{k:number, dw:number, dh:number, cx:number, cy:number,
 *            slackX:number, slackY:number, panX:number, panY:number}|null}
 */
export function resolveFit(o) {
  const { W, H, sw, sh } = o;
  if (!(W > 0 && H > 0 && sw > 0 && sh > 0)) return null;

  const rad = Number.isFinite(o.rad) ? o.rad : 0;
  const rw = o.rw > 0 ? o.rw : W;
  const rh = o.rh > 0 ? o.rh : H;
  const scale = Number.isFinite(o.scale) && o.scale > 0 ? o.scale : 1;
  const tx = Number.isFinite(o.tx) ? Math.min(Math.max(o.tx, -1), 1) : 0;
  const ty = Number.isFinite(o.ty) ? Math.min(Math.max(o.ty, -1), 1) : 0;

  const k = scale * coverFactor(W, H, sw, sh, rad);
  const dw = sw * k, dh = sh * k;

  // The ROOM's extent in the source's frame -- the thing coverage is owed to.
  const ac = Math.abs(Math.cos(rad)), as = Math.abs(Math.sin(rad));
  const bw = rw * ac + rh * as;
  const bh = rw * as + rh * ac;

  // SLACK IS A DISTANCE: how far the mask's edge is from the room's edge. One sentence
  // covers both regimes, which is why `tx = +/-1` keeps its meaning at every scale --
  // above cover the mask OVERHANGS and pans until its edge reaches the room's; below
  // cover it is SMALLER than the room and roams inside until its edge reaches the room's.
  // `Math.abs`, not `Math.max(0, ...)`: the old form was right that slack must never go
  // NEGATIVE (that would invert the pan and move the mask the wrong way), but it bought
  // that by collapsing the whole sub-cover range to zero, which is what killed the arrows.
  // Taking the magnitude gets the same no-inversion guarantee with the travel intact.
  const slackX = Math.abs(dw - bw) / 2;
  const slackY = Math.abs(dh - bh) / 2;

  return {
    k, dw, dh,
    // Centred on the ROOM, not the buffer. They differ only where the buffer was clamped
    // at a canvas edge, and there it is the room that should stay centred.
    cx: (Number.isFinite(o.rx) ? o.rx : 0) + rw / 2,
    cy: (Number.isFinite(o.ry) ? o.ry : 0) + rh / 2,
    slackX, slackY,
    panX: tx * slackX,
    panY: ty * slackY,
  };
}
