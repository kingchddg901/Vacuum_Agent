// Pure zone-clean coordinate math for the dashboard card's draw-a-box zone layer.
//
// Lifted VERBATIM from the panel's tested map state (src/state/map.js) so the card
// reuses the exact, on-device-verified transforms instead of reimplementing them:
//   - object-fit:contain letterbox correction (a box at 50% of a SQUARE container is
//     NOT 50% of a non-square image),
//   - 90/180/270 un-rotation (draw on a rotated live map → dispatch to the right place),
//   - the normalized [x0,y0,x1,y1] (0-1, top-left origin) shape that the backend
//     eufy_vacuum.start_zone_clean service wants.
// DOM-free + dependency-free so it unit-tests with `node --test`, exactly like
// dashboard-dispatch.js. The draw INTERACTION + zone list live in the card; this is
// only the geometry.

/** Fallback per-clean zone cap, before the snapshot's zone_max loads. */
export const ZONE_MAX_FALLBACK = 10;

/** Snap any degrees to the nearest 0/90/180/270. */
export function normRotation(deg) {
  return (((Math.round(Number(deg) / 90) * 90) % 360) + 360) % 360;
}

/**
 * Map a 0-100 pct pointer in the (unrotated) square box into the rotated content
 * frame. The container is square, so a 90/180/270 turn maps pct corners exactly.
 * Identity at rotation 0.
 */
export function unrotatePct(fx, fy, rot) {
  switch (normRotation(rot)) {
    case 90:  return [fy, 100 - fx];
    case 180: return [100 - fx, 100 - fy];
    case 270: return [100 - fy, fx];
    default:  return [fx, fy];
  }
}

/** Un-rotate a drawn pct rect {x,y,w,h} back to the content frame the device uses. */
export function unrotateRectPct(d, rot) {
  if (!d) return d;
  const [ax, ay] = unrotatePct(d.x, d.y, rot);
  const [bx, by] = unrotatePct(d.x + d.w, d.y + d.h, rot);
  return { x: Math.min(ax, bx), y: Math.min(ay, by), w: Math.abs(bx - ax), h: Math.abs(by - ay) };
}

/**
 * Convert ONE pct rect (0-100 of the SQUARE container) into a normalized
 * [x0,y0,x1,y1] in the live-map IMAGE frame (fractions 0-1, top-left origin),
 * correcting object-fit:contain letterboxing. Returns null for a degenerate rect
 * (drawn entirely inside a letterbox bar, or smaller than MIN_SIDE).
 *
 * @param {{x:number,y:number,w:number,h:number}} d  pct rect
 * @param {{width:number,height:number}} dims        natural px of the live image
 * @returns {number[]|null} [x0,y0,x1,y1] in 0-1, or null
 */
export function rectToNormalized(d, dims) {
  if (!d || !dims) return null;
  const W = dims.width, H = dims.height;
  if (!(W > 0) || !(H > 0)) return null;
  const imgPctW = W >= H ? 100 : (100 * W) / H;
  const imgPctH = H >= W ? 100 : (100 * H) / W;
  const offX = (100 - imgPctW) / 2;
  const offY = (100 - imgPctH) / 2;
  const clamp01 = (v) => Math.min(Math.max(v, 0), 1);
  const toNorm = (px, py) => [
    clamp01((px - offX) / imgPctW),
    clamp01((py - offY) / imgPctH),
  ];
  const [nx0, ny0] = toNorm(Math.min(d.x, d.x + d.w), Math.min(d.y, d.y + d.h));
  const [nx1, ny1] = toNorm(Math.max(d.x, d.x + d.w), Math.max(d.y, d.y + d.h));
  const x0 = Math.min(nx0, nx1), y0 = Math.min(ny0, ny1);
  const x1 = Math.max(nx0, nx1), y1 = Math.max(ny0, ny1);
  const MIN_SIDE = 0.01;
  if (x1 - x0 < MIN_SIDE || y1 - y0 < MIN_SIDE) return null;
  return [x0, y0, x1, y1];
}

/**
 * All drawn pct rects → normalized [x0,y0,x1,y1] rects: each un-rotated to the
 * content frame, then letterbox-corrected; degenerate rects dropped. This is the
 * list the card hands to eufy_vacuum.start_zone_clean.
 *
 * @param {Array<{x,y,w,h}>} drafts
 * @param {{width:number,height:number}} dims  natural px of the live image
 * @param {number} [rot=0]  current map rotation (deg)
 */
export function draftsToNormalizedRects(drafts, dims, rot = 0) {
  return (drafts ?? [])
    .map((d) => rectToNormalized(unrotateRectPct(d, rot), dims))
    .filter(Boolean);
}
