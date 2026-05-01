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
  g.number("--evcc-floor-textures-card-enabled",      "Card Textures Enabled (0/1)"),
  g.number("--evcc-floor-textures-map-enabled",       "Map Textures Enabled (0/1)"),
  g.number("--evcc-floor-texture-opacity-card",       "Card Texture Opacity (all)"),
  g.number("--evcc-floor-texture-opacity-map",        "Map Texture Opacity (all)"),

  /* === TILE === */
  gt.color(  "--evcc-floor-tile-base",                "Tile Base Color"),
  gt.color(  "--evcc-floor-tile-grout",               "Tile Grout Color"),
  gt.color(  "--evcc-floor-tile-accent",              "Tile Accent Color"),
  gt.number( "--evcc-floor-tile-opacity-card",        "Tile Card Opacity"),
  gt.number( "--evcc-floor-tile-face-opacity",        "Tile Face Layer Opacity"),
  gt.number( "--evcc-floor-tile-grout-opacity",       "Tile Grout Layer Opacity"),
  gt.number( "--evcc-floor-tile-line-opacity",        "Tile Grout Line Layer Opacity"),

  /* === WOOD === */
  gw.color(  "--evcc-floor-wood-base",                "Wood Base Color"),
  gw.color(  "--evcc-floor-wood-accent",              "Wood Accent Color"),
  gw.number( "--evcc-floor-wood-opacity-card",        "Wood Card Opacity"),
  gw.number( "--evcc-floor-wood-depth-opacity",       "Wood Depth Layer Opacity"),
  gw.number( "--evcc-floor-wood-grain-opacity",       "Wood Grain Layer Opacity"),
  gw.number( "--evcc-floor-wood-seam-opacity",        "Wood Seam Layer Opacity"),

  /* === MARBLE === */
  gm.color(  "--evcc-floor-marble-base",              "Marble Base Color"),
  gm.color(  "--evcc-floor-marble-micro",             "Marble Micro Color"),
  gm.color(  "--evcc-floor-marble-accent",            "Marble Accent Color"),
  gm.number( "--evcc-floor-marble-opacity-card",      "Marble Card Opacity"),
  gm.number( "--evcc-floor-marble-base-opacity",      "Marble Base Layer Opacity"),
  gm.number( "--evcc-floor-marble-micro-opacity",     "Marble Micro Layer Opacity"),
  gm.number( "--evcc-floor-marble-vein-opacity",      "Marble Vein Layer Opacity"),

  /* === CONCRETE === */
  gc.color(  "--evcc-floor-concrete-base",            "Concrete Base Color"),
  gc.color(  "--evcc-floor-concrete-accent",          "Concrete Accent Color"),
  gc.number( "--evcc-floor-concrete-opacity-card",    "Concrete Card Opacity"),
  gc.number( "--evcc-floor-concrete-broad-opacity",   "Concrete Broad Layer Opacity"),
  gc.number( "--evcc-floor-concrete-micro-opacity",   "Concrete Micro Layer Opacity"),

  /* === CARPET LOW === */
  gl.color(  "--evcc-floor-carpet-low-base",          "Carpet Low Base Color"),
  gl.color(  "--evcc-floor-carpet-low-accent",        "Carpet Low Accent Color"),
  gl.number( "--evcc-floor-carpet-low-opacity-card",  "Carpet Low Card Opacity"),
  gl.number( "--evcc-floor-carpet-low-texture-opacity","Carpet Low Texture Layer Opacity"),

  /* === CARPET HIGH === */
  gh.color(  "--evcc-floor-carpet-high-base",         "Carpet High Base Color"),
  gh.color(  "--evcc-floor-carpet-high-accent",       "Carpet High Accent Color"),
  gh.number( "--evcc-floor-carpet-high-opacity-card", "Carpet High Card Opacity"),
  gh.number( "--evcc-floor-carpet-high-texture-opacity","Carpet High Texture Layer Opacity"),

  /* === GRANITE LIGHT === */
  gg.color(  "--evcc-floor-granite-light-base",       "Granite Base Color"),
  gg.color(  "--evcc-floor-granite-light-accent",     "Granite Accent Color"),
  gg.number( "--evcc-floor-granite-light-opacity-card","Granite Card Opacity"),
  gg.number( "--evcc-floor-granite-light-texture-opacity","Granite Texture Layer Opacity"),
];
