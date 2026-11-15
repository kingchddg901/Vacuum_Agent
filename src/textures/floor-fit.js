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
 *   - every value in range still covers the room BY CONSTRUCTION, so there is no
 *     out-of-range case to detect, clamp or render differently;
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

  const slackX = Math.max(0, (dw - bw) / 2);
  const slackY = Math.max(0, (dh - bh) / 2);

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
