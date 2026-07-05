/**
 * ============================================================
 * RENDERERS: FLOOR TEXTURE SURFACE
 * ============================================================
 *
 * PURPOSE
 * -------
 * Renderer mixin that generates floor-texture HTML/SVG for
 * room cards (CSS overlay div) and the map view (SVG patterns
 * + polygon overlays).
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * Mixed onto VacuumCardRenderers.prototype so all renderer
 * modules can call the helpers without importing them directly.
 *
 * Three public methods:
 *   _renderFloorTextureLayer(normalizedRoom)
 *     → HTML string — absolute div injected as first child of
 *       .evcc-room-card; contains one <span> per texture layer
 *
 *   _buildFloorTextureDefs(floorTypes)
 *     → SVG <defs> string — one <pattern> per unique floor type
 *       that has a primary texture URL
 *
 *   _renderFloorTexturePolygon(seg, floorType)
 *     → SVG <polygon> string — texture overlay for one segment
 *
 * Supporting helper (also available to map renderers):
 *   _resolveSegmentFloorType(room) → resolved floor-type key
 *
 * Card rendering approach (mask-image):
 *   Container div: carries base-color background-color inline.
 *     Visible even when textures are disabled — flat material tint.
 *   Child spans: each covers the full container via position:absolute.
 *     background-color — layer tint (base or accent token).
 *     mask-image       — grayscale PNG.
 *     mask-mode        — luminance; white reveals color, black = transparent.
 *                        MUST be set explicitly: raster mask-image defaults to
 *                        mask-mode:alpha (match-source), and our masks have no
 *                        alpha channel, so alpha mode floods the whole field.
 *     --layer-opacity  — per-layer weight from the registry.
 *     CSS calc() in .evcc-ftx-layer gates on global enabled token.
 *
 * ============================================================
 */

import { FLOOR_TEXTURE_REGISTRY, getPrimaryTextureUrl } from "../textures/floor-texture-registry.js";
import { resolveFloorType                              } from "../textures/floor-texture-resolver.js";

/* Deterministic position hash — maps any string seed to an X% Y% offset.
   Uses two separate bit-ranges of the same hash so X and Y are uncorrelated. */
function _texturePosition(seed) {
  const s = String(seed ?? "");
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = (Math.imul(h, 0x01000193)) >>> 0;
  }
  const x = h % 101;
  const y = ((h >>> 13) ^ (h >>> 7)) % 101;
  return `${x}% ${y}%`;
}

/**
 * Mix floor texture surface renderer methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applyFloorTextureSurface(proto) {

  /* =========================================================
     RESOLVE FLOOR TYPE FOR A ROOM OBJECT
     ========================================================= */

  proto._resolveSegmentFloorType = function (room) {
    return resolveFloorType({
      floor_type:  room?.floor_type  ?? room?.floorType  ?? "",
      carpet_type: room?.carpet_type ?? room?.carpetType ?? "",
    });
  };

  /* =========================================================
     CARD TEXTURE LAYER
     ========================================================= */

  proto._renderFloorTextureLayer = function (normalizedRoom) {
    // Room-card textures toggled off hides them on REAL cards — but the theme-preview swatches
    // set forceFloorTexture so the preview still shows each material (tune with cards off).
    if (!(this.card?._state?.roomFloorTextureEnabled?.() ?? true) && !normalizedRoom?.forceFloorTexture) return "";
    const floorType = resolveFloorType({
      floor_type:  normalizedRoom?.floorType  ?? "",
      carpet_type: normalizedRoom?.carpetType ?? "",
    });

    const entry = FLOOR_TEXTURE_REGISTRY[floorType] ?? FLOOR_TEXTURE_REGISTRY.default;

    const opacityFallback = entry.opacityDefault ?? 0.85;
    const opacityVar  = `var(--evcc-floor-${floorType}-opacity-card,var(--evcc-floor-texture-opacity-card,${opacityFallback}))`;
    const positionVar = _texturePosition(normalizedRoom?.id ?? normalizedRoom?.name ?? floorType);

    const spans = entry.layers.map((layer) => {
      const color = `var(${layer.colorToken},${layer.colorDefault})`;
      // No quotes inside url() — double-quotes break the HTML style attribute
      const mask  = `url(${layer.url})`;
      const layerOpacity = `var(${layer.opacityToken},${layer.opacityDefault})`;
      // Force luminance masking inline. A raster mask-image defaults to
      // mask-mode:alpha (via match-source); our masks are alpha-less grayscale
      // PNGs, so under alpha mode every pixel is fully opaque and the tint
      // floods the whole field instead of only the white. Luminance reads
      // brightness — white reveals, black hides. -webkit-mask-source-type
      // covers older WebKit / iOS WebViews that predate standard mask-mode.
      const span =
        `<span class="evcc-ftx-layer" data-role="${layer.role}"` +
        ` style="background-color:${color};mask-image:${mask};-webkit-mask-image:${mask};mask-mode:luminance;-webkit-mask-source-type:luminance;--layer-opacity:${layerOpacity}"></span>`;

      // Optional per-layer blur. CSS applies filter BEFORE mask, so blurring the
      // span itself would blur the flat fill then hard-clip it (sharp edges).
      // Wrapping blurs the already-masked result -> soft edges (used by veins).
      if (!layer.blurToken && !layer.blurDefault) return span;
      const blurVal = `var(${layer.blurToken},${layer.blurDefault ?? "0px"})`;
      return `<span class="evcc-ftx-blur" style="filter:blur(${blurVal});-webkit-filter:blur(${blurVal})">${span}</span>`;
    }).join("");

    return (
      `<div class="evcc-room-texture-layer" data-floor="${floorType}"` +
      ` style="--floor-opacity-card:${opacityVar};--floor-position-card:${positionVar}">${spans}</div>`
    );
  };

  /* =========================================================
     MAP SVG DEFS — ONE PATTERN PER UNIQUE FLOOR TYPE
     ========================================================= */

  proto._buildFloorTextureDefs = function (floorTypes) {
    if (!(this.card?._state?.mapFloorTextureEnabled?.() ?? true)) return ""; // map textures off
    const seen     = new Set();
    const patterns = [];

    for (const ft of floorTypes) {
      if (seen.has(ft)) continue;
      seen.add(ft);

      const url = getPrimaryTextureUrl(ft);
      if (!url) continue;

      patterns.push(
        `<pattern id="evcc-ftx-${ft}" patternUnits="userSpaceOnUse" width="8" height="8">` +
        `<image href="${url}" width="8" height="8" preserveAspectRatio="xMidYMid slice"/>` +
        `</pattern>`
      );
    }

    return patterns.length ? `<defs>${patterns.join("")}</defs>` : "";
  };

  /* =========================================================
     MAP SVG TEXTURE POLYGON — ONE PER SEGMENT
     ========================================================= */

  proto._renderFloorTexturePolygon = function (seg, floorType) {
    if (!(this.card?._state?.mapFloorTextureEnabled?.() ?? true)) return ""; // map textures off
    const polygon = seg.polygon_pct;
    if (!Array.isArray(polygon) || polygon.length < 3) return "";
    if (!getPrimaryTextureUrl(floorType)) return "";

    const points = polygon.map(([x, y]) => `${x},${y}`).join(" ");

    return (
      `<polygon` +
      ` class="evcc-map-texture-polygon"` +
      ` points="${points}"` +
      ` fill="url(#evcc-ftx-${floorType})"` +
      ` data-floor="${floorType}"` +
      `/>`
    );
  };
}