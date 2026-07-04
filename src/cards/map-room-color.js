// Themeable map room-fill palette — the single source of truth both render paths resolve
// through (the SVG segment fill in renderers/map.js AND the VA raster in bindings/map.js,
// which were two BYTE-IDENTICAL hardcoded copies). docs/dev/themeable-map-palette.md.
//
// Cascade (one order, defined here once — Phases 1 & 2):
//   per-room override (room.color)  ->  theme token --evcc-room-fill-<N>  ->  default palette below.
// A themeless card with no overrides resolves to the default palette (the old colors), so the
// render is byte-for-byte unchanged until a theme sets a token or a room gets an override.
//
// The SVG folds the override into roomFillCss() (an inline concrete hex short-circuits the var);
// the raster resolves the override separately per rid via roomOverrideRgb() because its palette is
// pre-resolved per slot, not per room. normalizeHex() is the shared gate for BOTH so a bad value
// (garbage / null / cleared) falls straight through to the theme/default layer.
//
// DOM-free except roomFillRgb, which reads a computed custom property for the canvas (the
// raster can't take CSS vars); roomFillCss stays pure so the SVG rides the live CSS cascade.

/** The canonical default room-fill palette (12 colors). Room-fill theme tokens fall back to these. */
export const ROOM_FILL_PALETTE = [
  "#00e5ff", "#ff6b35", "#a3e635", "#e879f9",
  "#fbbf24", "#a78bfa", "#fb7185", "#34d399",
  "#60a5fa", "#f472b6", "#4ade80", "#f97316",
];

export const ROOM_FILL_N = ROOM_FILL_PALETTE.length;

/** Wrap any (possibly negative / fractional) index into a 0..N-1 palette slot. */
function slot(idx) {
  const i = Math.trunc(Number(idx) || 0);
  return ((i % ROOM_FILL_N) + ROOM_FILL_N) % ROOM_FILL_N;
}

/** The 1-based theme-token name for palette slot `idx` (0-based, wraps). */
export function roomFillTokenName(idx) {
  return `--evcc-room-fill-${slot(idx) + 1}`;
}

/** The default hex for palette slot `idx` (0-based, wraps). */
export function roomFillDefault(idx) {
  return ROOM_FILL_PALETTE[slot(idx)];
}

/**
 * Normalize a user/stored room-override color to a canonical `#rrggbb` (lowercased), or null for
 * anything that isn't a valid hex (null, "", garbage, a cleared override). Accepts `#rgb`, `#rrggbb`,
 * and the leading-`#`-less forms. This is the single gate for the per-room layer of the cascade —
 * a null result means "no override," so resolution falls through to the theme token / default.
 */
export function normalizeHex(value) {
  if (typeof value !== "string") return null;
  let s = value.trim().toLowerCase();
  if (!s) return null;
  if (s[0] !== "#") s = `#${s}`;
  if (/^#[0-9a-f]{6}$/.test(s)) return s;
  if (/^#[0-9a-f]{3}$/.test(s)) {
    return `#${s[1]}${s[1]}${s[2]}${s[2]}${s[3]}${s[3]}`;
  }
  return null;
}

/**
 * The value for an inline `--seg-color` on an SVG room polygon. Cascade: a valid per-room
 * `override` wins (a concrete hex, so CSS ignores the token); else the theme token if set, else
 * the default hex. CSS resolves the token/default live, so a theme change needs no re-render; an
 * override change DOES need a re-render (it's baked into the inline value), which the render loop
 * already does when room data changes.
 *
 * @param {number} idx        0-based palette slot (wraps)
 * @param {string} [override] the room's per-room color (room.color); ignored if not a valid hex
 */
export function roomFillCss(idx, override) {
  const hex = normalizeHex(override);
  if (hex) return hex;
  return `var(${roomFillTokenName(idx)}, ${roomFillDefault(idx)})`;
}

/** Parse #rgb / #rrggbb to [r,g,b]; grey fallback for anything else (a non-hex token value). */
export function hexToRgb(hex) {
  const h = String(hex == null ? "" : hex).replace("#", "").trim();
  if (/^[0-9a-fA-F]{6}$/.test(h)) {
    const n = parseInt(h, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  if (/^[0-9a-fA-F]{3}$/.test(h)) {
    const n = parseInt(h.split("").map((c) => c + c).join(""), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  return [128, 128, 128];
}

/**
 * The RGB triple for palette slot `idx` for the VA raster (a canvas takes no CSS vars, so we
 * read the resolved token off a DOM node that inherits it — pass the canvas). Falls back to the
 * default palette when the token is unset (themeless) or unreadable. Resolve ONCE per render
 * (N reads) and index the result per pixel — never call this per pixel.
 *
 * @param {number} idx    0-based palette slot (wraps)
 * @param {Element} [host] a mounted node that inherits the theme tokens (e.g. the render canvas)
 * @returns {[number,number,number]}
 */
export function roomFillRgb(idx, host) {
  let hex = roomFillDefault(idx);
  try {
    if (host && typeof getComputedStyle === "function") {
      const v = getComputedStyle(host).getPropertyValue(roomFillTokenName(idx)).trim();
      if (v) hex = v;
    }
  } catch (_e) { /* detached node / no CSSOM — keep the default */ }
  return hexToRgb(hex);
}

/**
 * The RGB triple for a per-room override color, or null if the value isn't a valid hex. This is the
 * raster's entry point for the per-room layer: build a `rid -> rgb` map once from the rooms' colors,
 * then per pixel use `override ?? palette[slot]` so the cascade (override > token > default) holds
 * on the canvas too. Returns null (not grey) for a missing/invalid override so the caller falls
 * through to the palette instead of painting a fallback grey.
 *
 * @param {string} value the room's per-room color (room.color)
 * @returns {[number,number,number]|null}
 */
export function roomOverrideRgb(value) {
  const hex = normalizeHex(value);
  return hex ? hexToRgb(hex) : null;
}
