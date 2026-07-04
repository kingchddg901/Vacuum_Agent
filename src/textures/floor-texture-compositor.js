/**
 * ============================================================
 * TEXTURES: FLOOR TEXTURE COMPOSITOR
 * ============================================================
 *
 * PURPOSE
 * -------
 * Composite a floor-type's registry layers (grayscale mask × resolved color ×
 * opacity, bottom→top) into ONE opaque RGBA buffer that the map floor-texture
 * view samples per pixel.
 *
 * WHY IT'S ITS OWN (pure) MODULE
 * ------------------------------
 * The card path composites the same layers via CSS (mask-image + background-color
 * + per-layer opacity). The raster/canvas floor view can't lean on CSS — it has to
 * do the mask×color×opacity math itself. That math is pure (no DOM), so it lives
 * here and is unit-tested with synthetic masks; the async PNG→luminance decode
 * (which IS DOM/Image-bound) stays in the binding and hands us plain luminance
 * arrays.
 *
 * MODEL (faithful to the card + FLOOR_TEXTURE_REGISTRY)
 * ----------------------------------------------------
 * Start from an opaque BASE color (the flat room fill the material builds on — the
 * same tint shown when textures are off), then alpha-composite each layer over it:
 *   layerAlpha(texel) = (luminance/255) * layerOpacity   // white mask reveals
 *   out = layerColor*layerAlpha + out*(1-layerAlpha)
 * The result stays fully opaque (a floor is a solid surface), so it can be written
 * straight into the per-room clip with alpha 255.
 * ============================================================
 */

/**
 * @param {number} width
 * @param {number} height
 * @param {[number,number,number]} baseColor Opaque base (flat room fill) RGB 0..255.
 * @param {Array<{lum:(Uint8Array|Uint8ClampedArray|number[]), color:[number,number,number], opacity:number}>} layers
 *   Bottom→top. `lum` = per-texel luminance 0..255, length width*height (white
 *   reveals the layer color). Missing/short `lum` or opacity<=0 → layer skipped.
 * @returns {{width:number,height:number,data:Uint8ClampedArray}} RGBA (alpha 255).
 */
export function compositeFloorTexture(width, height, baseColor, layers) {
  const W = width | 0;
  const H = height | 0;
  const n = Math.max(0, W * H);
  const out = new Uint8ClampedArray(n * 4);

  const br = baseColor?.[0] ?? 0;
  const bg = baseColor?.[1] ?? 0;
  const bb = baseColor?.[2] ?? 0;

  // Seed with the opaque base.
  for (let i = 0; i < n; i++) {
    const o = i * 4;
    out[o] = br;
    out[o + 1] = bg;
    out[o + 2] = bb;
    out[o + 3] = 255;
  }

  for (const layer of layers || []) {
    const lum = layer?.lum;
    if (!lum || lum.length < n) continue;
    const lr = layer.color?.[0] ?? 0;
    const lg = layer.color?.[1] ?? 0;
    const lb = layer.color?.[2] ?? 0;
    const op = Math.max(0, Math.min(1, layer.opacity ?? 1));
    if (op <= 0) continue;

    for (let i = 0; i < n; i++) {
      const a = (lum[i] / 255) * op;
      if (a <= 0) continue;
      const o = i * 4;
      const ia = 1 - a;
      out[o] = lr * a + out[o] * ia;
      out[o + 1] = lg * a + out[o + 1] * ia;
      out[o + 2] = lb * a + out[o + 2] * ia;
      // alpha stays 255 — the floor is opaque.
    }
  }

  return { width: W, height: H, data: out };
}
