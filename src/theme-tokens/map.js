/**
 * ============================================================
 * THEME TOKENS: MAP
 * ============================================================
 *
 * PURPOSE
 * -------
 * Themeable surfaces of the map view. Currently the centroid room
 * labels — their pill background and text colour. The pill exists so
 * labels stay legible over ANY backdrop (a dark CV map screenshot or
 * an arbitrary custom backdrop image — a near-white sky over green
 * foliage, a blueprint, a photo). The background's alpha is the knob
 * to dial for a given backdrop, which is why it's a tunable token.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * Group file in the same shape as chips/room-cards/etc. Defaults are
 * seeded in the base :host block in styles/index.js and consumed via
 * var() in styles/map.js; only token VALUES persist (flat) on the
 * backend. The group can grow to hold other map surfaces later.
 *
 * ============================================================
 */

import { mapToken } from "./helpers.js";

export const MAP_TOKENS = [
  mapToken.color("--evcc-map-label-bg", "Map Label Background"),
  mapToken.color("--evcc-map-label-text", "Map Label Text"),
  mapToken.color("--evcc-map-label-text-selected", "Map Label Text (Selected)"),
  mapToken.color("--evcc-map-label-order-text", "Map Order Badge Text"),
  mapToken.color("--evcc-map-tooltip-bg", "Map Tooltip Background"),
  mapToken.color("--evcc-map-tooltip-border", "Map Tooltip Border"),
  mapToken.color("--evcc-map-tooltip-text", "Map Tooltip Text"),
  mapToken.color("--evcc-map-tooltip-hint", "Map Tooltip Hint Text"),
  mapToken.color("--evcc-map-compose-selected-stroke", "Composer Selected Outline"),
  mapToken.color("--evcc-map-compose-cut-fill", "Composer Cutout Fill"),
  mapToken.color("--evcc-map-compose-cut-selected-fill", "Composer Cutout Fill (Selected)"),
  mapToken.color("--evcc-map-vertex-selected-glow", "Composer Selected Vertex Glow"),
  // Wave 3c — map_state_source overlay layers (no-go / walls / path / robot / etc.).
  mapToken.color("--evcc-map-ov-current", "Overlay: Current Room"),
  mapToken.color("--evcc-map-ov-nogo", "Overlay: No-Go Zone"),
  mapToken.color("--evcc-map-ov-nomop", "Overlay: No-Mop Zone"),
  mapToken.color("--evcc-map-ov-wall", "Overlay: Virtual Wall"),
  mapToken.color("--evcc-map-ov-zone", "Overlay: Saved Zone"),
  mapToken.color("--evcc-map-ov-path", "Overlay: Cleaning Path"),
  mapToken.color("--evcc-map-ov-robot", "Overlay: Robot Marker"),
  mapToken.color("--evcc-map-ov-dock", "Overlay: Dock Marker"),
  mapToken.color("--evcc-map-ov-obstacle", "Overlay: Obstacle Marker"),
  mapToken.color("--evcc-map-ov-area-text", "Overlay: Area Label Text"),
  // Room-fill palette (docs/dev/themeable-map-palette.md, Phase 1). The map cycles these by
  // room order (SVG) / room id (raster) via roomFillCss/roomFillRgb, each of which supplies the
  // default rainbow as its OWN fallback — so a themeless card is unchanged. Unlike the other map
  // tokens, the defaults are NOT in the styles/index.js :host block; state/theme.js resolvedTheme
  // seeds the same palette so the editor's colour picker has a value to open. A per-room override
  // lands in Phase 2. Count = ROOM_FILL_N in cards/map-room-color.js — keep them in sync.
  mapToken.color("--evcc-room-fill-1",  "Map Room Color 1"),
  mapToken.color("--evcc-room-fill-2",  "Map Room Color 2"),
  mapToken.color("--evcc-room-fill-3",  "Map Room Color 3"),
  mapToken.color("--evcc-room-fill-4",  "Map Room Color 4"),
  mapToken.color("--evcc-room-fill-5",  "Map Room Color 5"),
  mapToken.color("--evcc-room-fill-6",  "Map Room Color 6"),
  mapToken.color("--evcc-room-fill-7",  "Map Room Color 7"),
  mapToken.color("--evcc-room-fill-8",  "Map Room Color 8"),
  mapToken.color("--evcc-room-fill-9",  "Map Room Color 9"),
  mapToken.color("--evcc-room-fill-10", "Map Room Color 10"),
  mapToken.color("--evcc-room-fill-11", "Map Room Color 11"),
  mapToken.color("--evcc-room-fill-12", "Map Room Color 12"),
];
