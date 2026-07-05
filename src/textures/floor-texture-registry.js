/**
 * ============================================================
 * TEXTURES: FLOOR TEXTURE REGISTRY
 * ============================================================
 *
 * PURPOSE
 * -------
 * Static mapping from resolved floor-type keys to their
 * texture layer configuration.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * Each layer has an opacityToken pointing to a theme token and
 * an opacityDefault used as the fallback when the token is
 * unset.  Users tune layers via the theme editor; once a
 * material is dialled in the defaults here can be updated to
 * bake that look in for everyone.
 *
 * Layer DOM order = bottom → top (last entry renders on top).
 *
 * masks[] is kept for backward-compat with the SVG map renderer.
 * baseTexture is kept for getPrimaryTextureUrl().
 *
 * ============================================================
 */

// Base path for all texture assets served from the HA www/ directory.
const _T = "/eufy_vacuum/textures";

// Build-injected cache-bust token (esbuild --define __ASSET_VER__), keyed to the
// texture assets' content. Appended as ?v=<token> to every texture URL below so a
// regenerated mask is fetched fresh instead of served from the 7-day texture cache
// (textures are registered cache_headers=True). Falls back to "dev" when running
// unbundled (build:dev/watch/tests).
const _ASSET_VER = (typeof __ASSET_VER__ !== "undefined") ? __ASSET_VER__ : "dev";
const _Q = `?v=${_ASSET_VER}`;

/* === FLOOR TEXTURE REGISTRY === */

export const FLOOR_TEXTURE_REGISTRY = {

  tile: {
    opacityDefault: 1,
    layers: [
      {
        url:            `${_T}/tile/tile-mask.png`,
        role:           "base",
        colorToken:     "--evcc-floor-tile-base",
        colorDefault:   "#D4AF37",
        opacityToken:   "--evcc-floor-tile-face-opacity",
        opacityDefault: 0.87,
      },
      {
        url:            `${_T}/tile/grout-mask.png`,
        role:           "grout",
        colorToken:     "--evcc-floor-tile-grout",
        colorDefault:   "#121212",
        opacityToken:   "--evcc-floor-tile-grout-opacity",
        opacityDefault: 0.95,
      },
      {
        url:            `${_T}/tile/pure-tile-grout.png`,
        role:           "accent",
        colorToken:     "--evcc-floor-tile-accent",
        colorDefault:   "#f0f0f5",
        opacityToken:   "--evcc-floor-tile-line-opacity",
        opacityDefault: 0.39,
      },
    ],
    masks: [
      { url: `${_T}/tile/tile-mask.png`       },
      { url: `${_T}/tile/grout-mask.png`      },
      { url: `${_T}/tile/pure-tile-grout.png` },
    ],
    baseTexture: null,
  },

  wood: {
    opacityDefault: 0.99,
    layers: [
      {
        url:            `${_T}/wood/wood-directional-depth-mask.png`,
        role:           "base",
        colorToken:     "--evcc-floor-wood-base",
        colorDefault:   "#7A4010cf",
        opacityToken:   "--evcc-floor-wood-depth-opacity",
        opacityDefault: 0.43,
      },
      {
        url:            `${_T}/wood/wood-grain-mask.png`,
        role:           "base",
        colorToken:     "--evcc-floor-wood-base",
        colorDefault:   "#7A4010cf",
        opacityToken:   "--evcc-floor-wood-grain-opacity",
        opacityDefault: 0.84,
      },
      {
        url:            `${_T}/wood/wood-seam-mask.png`,
        role:           "accent",
        colorToken:     "--evcc-floor-wood-accent",
        colorDefault:   "#e89754",
        opacityToken:   "--evcc-floor-wood-seam-opacity",
        opacityDefault: 0.78,
      },
    ],
    masks: [
      { url: `${_T}/wood/wood-grain-mask.png`             },
      { url: `${_T}/wood/wood-seam-mask.png`              },
      { url: `${_T}/wood/wood-directional-depth-mask.png` },
    ],
    baseTexture: null,
  },

  marble: {
    opacityDefault: 0.9,
    layers: [
      {
        url:            `${_T}/marble/marble-base-mask.png`,
        role:           "base",
        colorToken:     "--evcc-floor-marble-base",
        colorDefault:   "#e9e8e8",
        opacityToken:   "--evcc-floor-marble-base-opacity",
        opacityDefault: 0.97,
      },
      {
        url:            `${_T}/marble/marble-micro-texture-mask.png`,
        role:           "micro",
        colorToken:     "--evcc-floor-marble-micro",
        colorDefault:   "#080707",
        opacityToken:   "--evcc-floor-marble-micro-opacity",
        opacityDefault: 1,
      },
      // VEINS — two tiers. Every property = master + per-layer offset, so the
      // master rides both tiers while the offsets preserve the delta. MINOR
      // recedes on all three axes (fainter / softer / hazier color) = atmospheric
      // perspective, so it reads as depth rather than a competing vein system.
      {
        url:            `${_T}/marble/marble-vein-major.png`,
        role:           "vein-major",
        colorToken:     "--evcc-floor-marble-accent",                       // master vein color
        colorDefault:   "#D4AF3773",
        opacityToken:   "--evcc-floor-marble-vein-major-opacity-eff",       // computed, not exposed
        opacityDefault: "clamp(0,calc(var(--evcc-floor-marble-vein-opacity,0.5) + var(--evcc-floor-marble-vein-major-opacity,0)),1)",
        blurToken:      "--evcc-floor-marble-vein-major-blur-eff",
        blurDefault:    "max(0px,calc(var(--evcc-floor-marble-vein-blur,0px) + var(--evcc-floor-marble-vein-major-blur,0px)))",
      },
      {
        url:            `${_T}/marble/marble-vein-minor.png`,
        role:           "vein-minor",
        // minor color = master receded in OKLCH: lighter + desaturated + cooler
        colorToken:     "--evcc-floor-marble-vein-minor-color-eff",
        colorDefault:   "oklch(from var(--evcc-floor-marble-accent,#D4AF3773) calc(l + var(--evcc-floor-marble-vein-minor-light,0.06)) calc(c * var(--evcc-floor-marble-vein-minor-chroma,0.65)) calc(h + var(--evcc-floor-marble-vein-minor-hue,6)) / alpha)",
        opacityToken:   "--evcc-floor-marble-vein-minor-opacity-eff",
        opacityDefault: "clamp(0,calc(var(--evcc-floor-marble-vein-opacity,0.5) + var(--evcc-floor-marble-vein-minor-opacity,-0.12)),1)",
        blurToken:      "--evcc-floor-marble-vein-minor-blur-eff",
        blurDefault:    "max(0px,calc(var(--evcc-floor-marble-vein-blur,0px) + var(--evcc-floor-marble-vein-minor-blur,1.5px)))",
      },
    ],
    masks: [
      { url: `${_T}/marble/marble-vein-major.png`         },
      { url: `${_T}/marble/marble-vein-minor.png`         },
      { url: `${_T}/marble/marble-micro-texture-mask.png` },
      { url: `${_T}/marble/marble-base-mask.png`          },
    ],
    baseTexture: null,
  },

  concrete: {
    opacityDefault: 1,
    layers: [
      {
        url:            `${_T}/concrete/concrete-broad-mask.png`,
        role:           "base",
        colorToken:     "--evcc-floor-concrete-base",
        colorDefault:   "#eceaea",
        opacityToken:   "--evcc-floor-concrete-broad-opacity",
        opacityDefault: 1,
      },
      {
        url:            `${_T}/concrete/concrete-micro-mask.png`,
        role:           "accent",
        colorToken:     "--evcc-floor-concrete-accent",
        colorDefault:   "#121111",
        opacityToken:   "--evcc-floor-concrete-micro-opacity",
        opacityDefault: 0.62,
      },
    ],
    masks: [
      { url: `${_T}/concrete/concrete-micro-mask.png` },
      { url: `${_T}/concrete/concrete-broad-mask.png` },
    ],
    baseTexture: null,
  },

  // SPLIT (2026-07-04): re-authored from the single full-colour photo into a broad BASE
  // mask + a bold DETAIL (weave) mask via scripts/gen_floor_masks.py, so the material reads
  // on the map instead of collapsing to black. Base colour lifted off near-black to a real
  // carpet tone; the detail layer paints the lighter pile/weave. See the floor-texture doc.
  carpet_low: {
    opacityDefault: 0.9,
    layers: [
      {
        url:            `${_T}/carpet/carpet-low-base-mask.png`,
        role:           "base",
        colorToken:     "--evcc-floor-carpet-low-base",
        colorDefault:   "#3f362e",
        opacityToken:   "--evcc-floor-carpet-low-base-opacity",
        opacityDefault: 1,
      },
      {
        url:            `${_T}/carpet/carpet-low-detail-mask.png`,
        role:           "accent",
        colorToken:     "--evcc-floor-carpet-low-weave",
        colorDefault:   "#7c6f60",
        opacityToken:   "--evcc-floor-carpet-low-weave-opacity",
        opacityDefault: 0.55,
      },
    ],
    masks: [
      { url: `${_T}/carpet/carpet-low-base-mask.png`   },
      { url: `${_T}/carpet/carpet-low-detail-mask.png` },
    ],
    baseTexture: `${_T}/carpet/carpet-low-base-mask.png`,
  },

  carpet_high: {
    opacityDefault: 0.9,
    layers: [
      {
        url:            `${_T}/carpet/carpet-high-base-mask.png`,
        role:           "base",
        colorToken:     "--evcc-floor-carpet-high-base",
        colorDefault:   "#2f2a26",
        opacityToken:   "--evcc-floor-carpet-high-base-opacity",
        opacityDefault: 1,
      },
      {
        url:            `${_T}/carpet/carpet-high-detail-mask.png`,
        role:           "accent",
        colorToken:     "--evcc-floor-carpet-high-weave",
        colorDefault:   "#5c5248",
        opacityToken:   "--evcc-floor-carpet-high-weave-opacity",
        opacityDefault: 0.5,
      },
    ],
    masks: [
      { url: `${_T}/carpet/carpet-high-base-mask.png`   },
      { url: `${_T}/carpet/carpet-high-detail-mask.png` },
    ],
    baseTexture: `${_T}/carpet/carpet-high-base-mask.png`,
  },

  granite_light: {
    opacityDefault: 1,
    layers: [
      {
        url:            `${_T}/granite/granite-base-mask.png`,
        role:           "base",
        colorToken:     "--evcc-floor-granite-light-base",
        colorDefault:   "#9c9a96",   // LIGHT granite — base was near-black, hence the black room
        opacityToken:   "--evcc-floor-granite-light-base-opacity",
        opacityDefault: 1,
      },
      {
        url:            `${_T}/granite/granite-detail-mask.png`,
        role:           "accent",
        colorToken:     "--evcc-floor-granite-light-aggregate",
        colorDefault:   "#46443f",   // dark aggregate grains over the light stone
        opacityToken:   "--evcc-floor-granite-light-aggregate-opacity",
        opacityDefault: 0.6,
      },
    ],
    masks: [
      { url: `${_T}/granite/granite-base-mask.png`   },
      { url: `${_T}/granite/granite-detail-mask.png` },
    ],
    baseTexture: `${_T}/granite/granite-base-mask.png`,
  },

  default: {
    opacityDefault: 0.85,
    layers:      [],
    masks:       [],
    baseTexture: null,
  },
};

// Append the cache-bust token to every texture URL — one place, so both the card
// renderer (layer.url) and getPrimaryTextureUrl / SVG map patterns (masks,
// baseTexture) pick it up. Runs once at module load.
for (const _entry of Object.values(FLOOR_TEXTURE_REGISTRY)) {
  for (const _layer of _entry.layers) if (_layer.url) _layer.url += _Q;
  for (const _mask  of _entry.masks)  if (_mask.url)  _mask.url  += _Q;
  if (_entry.baseTexture) _entry.baseTexture += _Q;
}

/**
 * Returns the primary texture image URL for a resolved floor type key.
 * Preference order: baseTexture → first layer → first mask → null.
 * Used by the SVG map renderer to fill room polygons with a <pattern>.
 *
 * @param {string} floorType - Canonical floor type key (e.g. "tile", "wood").
 * @returns {string|null} Absolute path to the primary texture PNG, or null if none.
 */
export function getPrimaryTextureUrl(floorType) {
  const entry = FLOOR_TEXTURE_REGISTRY[floorType];
  if (!entry) return null;
  if (entry.baseTexture)   return entry.baseTexture;
  if (entry.layers.length) return entry.layers[0].url;
  if (entry.masks.length)  return entry.masks[0].url;
  return null;
}
