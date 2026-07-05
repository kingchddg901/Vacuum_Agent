/**
 * ============================================================
 * THEME TOKENS: FLOOR TEXTURES
 * ============================================================
 *
 * PURPOSE
 * -------
 * Controls visibility, opacity, and per-material color/layer
 * tuning of floor texture overlays on room cards and the map.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * Global enable/opacity tokens ("Floor Textures") are master
 * controls and fallbacks.  Per-material subgroups override
 * only the tokens they define.
 *
 * Per-layer opacity tokens let power users tune the relative
 * contribution of each mask layer (grain vs seam vs depth etc.)
 * independently.  Once a material looks right those values can
 * be baked back into the registry as new defaults.
 *
 * RANGES BY SEMANTIC KIND
 * -----------------------
 * Bounded scalars use the range-carrying helper methods rather
 * than hand-authored bounds (see helpers.js):
 *   .unit   0-1   opacities, ratios, 0/1 enables (step override)
 *   .blur   0-8px blur radii  (blur offsets override min to -8)
 *   .angle  -180..180  hue shift
 *   .signed -1..1  signed deltas (lighten, offset-from-master)
 * Colors stay .color (unbounded, never clamped). One definition
 * drives both the editor slider and the import clamp.
 *
 * ============================================================
 */

import { makeTypedGroupToken } from "./helpers.js";

const g  = makeTypedGroupToken("Floor Textures",              "number");
const gt = makeTypedGroupToken("Floor Textures — Tile",       "color");
const gw = makeTypedGroupToken("Floor Textures — Wood",       "color");
const gm = makeTypedGroupToken("Floor Textures — Marble",     "color");
const gc = makeTypedGroupToken("Floor Textures — Concrete",   "color");
const gl = makeTypedGroupToken("Floor Textures — Carpet Low", "color");
const gh = makeTypedGroupToken("Floor Textures — Carpet High","color");
const gg = makeTypedGroupToken("Floor Textures — Granite",    "color");

export const FLOOR_TEXTURE_TOKENS = [

  /* === GLOBAL MASTER CONTROLS === */
  g.unit("--evcc-floor-textures-card-enabled",      "Card Textures Enabled (0/1)", { step: 1 }),
  g.unit("--evcc-floor-textures-map-enabled",       "Map Textures Enabled (0/1)",  { step: 1 }),
  g.unit("--evcc-floor-texture-opacity-card",       "Card Texture Opacity (all)"),
  g.unit("--evcc-floor-texture-opacity-map",        "Map Texture Opacity (all)"),
  // Rotates the whole map texture grid relative to the map (e.g. to make wood planks /
  // tile grout run the way they actually do in the home). Map-only; 0 = as-authored.
  g.angle("--evcc-floor-texture-map-rotate",        "Map Texture Rotation (deg)"),

  /* === TILE === */
  gt.color( "--evcc-floor-tile-base",                "Tile Base Color"),
  gt.color( "--evcc-floor-tile-grout",               "Tile Grout Color"),
  gt.color( "--evcc-floor-tile-accent",              "Tile Grout Line Color"),
  gt.unit(  "--evcc-floor-tile-opacity-card",        "Tile Card Opacity"),
  gt.unit(  "--evcc-floor-tile-face-opacity",        "Tile Base Layer Opacity"),
  gt.unit(  "--evcc-floor-tile-grout-opacity",       "Tile Grout Layer Opacity"),
  gt.unit(  "--evcc-floor-tile-line-opacity",        "Tile Grout Line Layer Opacity"),

  /* === WOOD === */
  gw.color( "--evcc-floor-wood-base",                "Wood Base Color"),
  gw.color( "--evcc-floor-wood-accent",              "Wood Grain & Seam Color"),
  gw.unit(  "--evcc-floor-wood-opacity-card",        "Wood Card Opacity"),
  gw.unit(  "--evcc-floor-wood-depth-opacity",       "Wood Depth Layer Opacity"),
  gw.unit(  "--evcc-floor-wood-grain-opacity",       "Wood Grain Layer Opacity"),
  gw.unit(  "--evcc-floor-wood-seam-opacity",        "Wood Seam Layer Opacity"),

  /* === MARBLE === */
  gm.color( "--evcc-floor-marble-base",              "Marble Base Color"),
  gm.color( "--evcc-floor-marble-micro",             "Marble Micro Color"),
  gm.color( "--evcc-floor-marble-accent",            "Marble Vein Color"),
  gm.unit(  "--evcc-floor-marble-opacity-card",      "Marble Card Opacity"),
  gm.unit(  "--evcc-floor-marble-base-opacity",      "Marble Base Layer Opacity"),
  gm.unit(  "--evcc-floor-marble-micro-opacity",     "Marble Micro Layer Opacity"),
  /* veins — master rides both tiers; per-layer offsets preserve the delta */
  gm.unit(   "--evcc-floor-marble-vein-opacity",       "Marble Vein Opacity (master)"),
  gm.blur(   "--evcc-floor-marble-vein-blur",          "Marble Vein Blur (master, px)"),
  gm.signed( "--evcc-floor-marble-vein-major-opacity", "Marble Major Vein Opacity +/-"),
  gm.signed( "--evcc-floor-marble-vein-minor-opacity", "Marble Minor Vein Opacity +/-"),
  gm.signed( "--evcc-floor-marble-vein-major-blur",    "Marble Major Vein Blur +/- (px)", { min: -8, max: 8, step: 0.5 }),
  gm.signed( "--evcc-floor-marble-vein-minor-blur",    "Marble Minor Vein Blur +/- (px)", { min: -8, max: 8, step: 0.5 }),
  gm.signed( "--evcc-floor-marble-vein-minor-light",   "Marble Minor Vein Lighten (L+)"),
  gm.unit(   "--evcc-floor-marble-vein-minor-chroma",  "Marble Minor Vein Saturation (xC)", { max: 2 }),
  gm.angle(  "--evcc-floor-marble-vein-minor-hue",     "Marble Minor Vein Hue Shift (deg)"),

  /* === CONCRETE === */
  gc.color( "--evcc-floor-concrete-base",            "Concrete Base Color"),
  gc.color( "--evcc-floor-concrete-accent",          "Concrete Micro Color"),
  gc.unit(  "--evcc-floor-concrete-opacity-card",    "Concrete Card Opacity"),
  gc.unit(  "--evcc-floor-concrete-broad-opacity",   "Concrete Base Layer Opacity"),
  gc.unit(  "--evcc-floor-concrete-micro-opacity",   "Concrete Micro Layer Opacity"),

  /* === CARPET LOW === (split: base + bold weave) */
  gl.color( "--evcc-floor-carpet-low-base",           "Carpet Low Base Color"),
  gl.color( "--evcc-floor-carpet-low-weave",          "Carpet Low Weave Color"),
  gl.unit(  "--evcc-floor-carpet-low-opacity-card",   "Carpet Low Card Opacity"),
  gl.unit(  "--evcc-floor-carpet-low-base-opacity",   "Carpet Low Base Layer Opacity"),
  gl.unit(  "--evcc-floor-carpet-low-weave-opacity",  "Carpet Low Weave Layer Opacity"),

  /* === CARPET HIGH === (split: base + bold weave) */
  gh.color( "--evcc-floor-carpet-high-base",          "Carpet High Base Color"),
  gh.color( "--evcc-floor-carpet-high-weave",         "Carpet High Weave Color"),
  gh.unit(  "--evcc-floor-carpet-high-opacity-card",  "Carpet High Card Opacity"),
  gh.unit(  "--evcc-floor-carpet-high-base-opacity",  "Carpet High Base Layer Opacity"),
  gh.unit(  "--evcc-floor-carpet-high-weave-opacity", "Carpet High Weave Layer Opacity"),

  /* === GRANITE LIGHT === (split: base + bold aggregate) */
  gg.color( "--evcc-floor-granite-light-base",             "Granite Base Color"),
  gg.color( "--evcc-floor-granite-light-aggregate",        "Granite Aggregate Color"),
  gg.unit(  "--evcc-floor-granite-light-opacity-card",     "Granite Card Opacity"),
  gg.unit(  "--evcc-floor-granite-light-base-opacity",     "Granite Base Layer Opacity"),
  gg.unit(  "--evcc-floor-granite-light-aggregate-opacity","Granite Aggregate Layer Opacity"),
];
