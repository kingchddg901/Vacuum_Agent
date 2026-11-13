/**
 * ============================================================
 * TEXTURES: DROP-IN MATERIALS — catalogue → registry entries
 * ============================================================
 *
 * PURPOSE
 * -------
 * Turn `catalog.json` (written at startup by
 * `custom_components/eufy_vacuum/user_materials.py`) into entries of exactly the shape
 * `FLOOR_TEXTURE_REGISTRY` holds, so the three renderers cannot tell a dropped-in
 * material from a shipped one.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * This module does NOT validate. The backend already did, against the files themselves —
 * canvas, bit depth and colour type read out of each PNG's IHDR rather than believed from
 * the descriptor. Re-checking here would be a second opinion with less evidence (the card
 * cannot stat a file), and two validators drifting apart is worse than one. What this does
 * is SHAPE: catalogue rows in, registry entries out.
 *
 * TOKEN NAMES ARE MINTED BY RULE, never carried in the catalogue:
 *
 *     --evcc-floor-<id>-<suffix>            colour
 *     --evcc-floor-<id>-<suffix>-opacity    opacity
 *
 * matching the shipped convention (`--evcc-floor-wood-base`,
 * `--evcc-floor-tile-grout-opacity`). This matters more than it looks: the 53
 * `--evcc-floor-*` literals in `src/theme-tokens/floor-textures.js` are hand-authored, and
 * renaming a registry key does NOT rename them — the token literal is the irreversible
 * commitment, not the key. Minting means the RULE is what gets committed to, once.
 *
 * ⚠ DO NOT emit a per-material `-opacity-card` token. It sits ABOVE the global
 * `--evcc-floor-texture-opacity-card` master in the render's `var()` fallback chain
 * (`renderers/floor-texture-surface.js`), so defining it per material would shadow that
 * global for anyone who set it. The entry-level `opacityDefault` is the right home for a
 * material's own card opacity — see the warning in
 * `docs/dev/frontend/floor-texture-map-view.md` § Theme-editor tokens + the seed.
 *
 * THE PRIMARY LAYER. The SVG polygon surface reads `getPrimaryTextureUrl()` only — one
 * image, untinted, as a `<pattern>` fill. Every shipped material's primary is its
 * STRUCTURAL mask (tile faces, plank depth, marble base), so defaulting to layer 0 is
 * wrong for a material whose first layer is a flat field: slate's face mask is a uniform
 * 235 and that surface would show a blank wash. A layer may mark itself `primary`.
 * ============================================================
 */

const CATALOG_URL = "/eufy_vacuum/user_materials/catalog.json";
const ASSET_BASE = "/eufy_vacuum/user_materials";
const SHIPPED_BASE = "/eufy_vacuum/textures";

/** `--evcc-floor-<id>-<suffix>` — the one naming rule, in one place. */
export function tokenFor(id, suffix, kind) {
  const seg = `--evcc-floor-${id}-${suffix}`;
  return kind === "opacity" ? `${seg}-opacity` : seg;
}

/**
 * One catalogue row → one registry entry.
 *
 * @param {object} row - as written by user_materials.build_catalog
 * @param {string} [assetVer] - the build's cache-bust token, appended like the shipped
 *   registry does. A drop-in asset arrives AFTER the build, so this token cannot describe
 *   it; the dir is served `cache_headers=False` for exactly that reason and the suffix is
 *   carried only so the URL shape matches.
 * @returns {{key:string, entry:object, presets:Array}|null}
 */
export function entryFromCatalogRow(row, assetVer) {
  if (!row || typeof row !== "object") return null;
  const id = typeof row.id === "string" ? row.id : "";
  if (!id || !Array.isArray(row.layers) || !row.layers.length) return null;

  const q = assetVer ? `?v=${assetVer}` : "";
  const layers = [];
  for (const l of row.layers) {
    if (!l || typeof l.suffix !== "string" || typeof l.path !== "string") return null;
    const url = l.borrowed
      ? `${SHIPPED_BASE}/${l.path}${q}`
      : `${ASSET_BASE}/${row.dir || id}/${l.path}${q}`;
    layers.push({
      url,
      role: l.suffix,
      colorToken: tokenFor(id, l.suffix, "color"),
      colorDefault: String(l.color),
      opacityToken: tokenFor(id, l.suffix, "opacity"),
      opacityDefault: Number(l.opacity),
      primary: l.primary === true,
    });
  }

  const primary = layers.find((l) => l.primary) || layers[0];
  return {
    id,
    key: id,
    name: typeof row.name === "string" && row.name ? row.name : id,
    family: typeof row.family === "string" ? row.family : null,
    scale: Number.isFinite(Number(row.scale)) ? Number(row.scale) : null,
    entry: {
      // NOT a -opacity-card token; see the warning above.
      opacityDefault: Number.isFinite(Number(row.opacity)) ? Number(row.opacity) : 0.99,
      // THE MATERIAL'S OWN FEATURE SCALE, on the ENTRY rather than beside it,
      // because the entry is the only part that reaches the registry -- and the
      // registry is what the map resolver reads. It sat on the outer object from
      // 1a183bb2 until it was wired, which is why every drop-in silently took the
      // global default however carefully its descriptor was authored.
      //
      // A shipped material's equivalent is its FLOOR_TEXTURE_MASK_SCALE_BY_TYPE
      // row; a drop-in cannot be in that table, so it declares instead. null means
      // "not declared" and falls through, which is NOT the same as 0 -- a zero or
      // negative scale would collapse the tiling, so it is refused here rather than
      // clamped into something that looks deliberate.
      mapScale: Number.isFinite(Number(row.scale)) && Number(row.scale) > 0
        ? Number(row.scale)
        : null,
      layers,
      masks: layers.map((l) => ({ url: l.url })),
      baseTexture: primary ? primary.url : null,
      userMaterial: true,   // so a consumer can tell shipped from dropped-in
    },
    presets: Array.isArray(row.presets) ? row.presets : [],
  };
}

/**
 * Merge catalogue rows into a registry IN PLACE, skipping any key already present.
 *
 * Shipped entries always win. The backend already refuses an id that collides with — or
 * prefixes, or is prefixed by — a reserved floor-type name, so a collision here should be
 * impossible; this is the belt. Silently overwriting a shipped material would be the
 * worst outcome, because the card would look correct and render someone else's floor.
 *
 * Returns the BUILT materials as well as the key lists, so the caller does not rebuild
 * them to hand to the token layer — one construction, one source of truth.
 *
 * @returns {{added: string[], skipped: string[], materials: object[]}}
 */
export function mergeUserMaterials(registry, rows, assetVer) {
  const added = [];
  const skipped = [];
  const materials = [];
  for (const row of rows || []) {
    const built = entryFromCatalogRow(row, assetVer);
    if (!built) { skipped.push(String(row && row.id)); continue; }
    if (Object.prototype.hasOwnProperty.call(registry, built.key)) {
      skipped.push(built.key);
      continue;
    }
    registry[built.key] = built.entry;
    added.push(built.key);
    materials.push(built);
  }
  return { added, skipped, materials };
}

/**
 * Fetch the catalogue. Resolves to `[]` on any failure — a missing or unreadable
 * catalogue means "no drop-ins", which is the overwhelmingly common case (the directory
 * is created empty at startup) and must not be an error path.
 */
export async function fetchUserMaterialCatalog(fetchImpl) {
  const f = fetchImpl || (typeof fetch === "function" ? fetch : null);
  if (!f) return [];
  try {
    const res = await f(CATALOG_URL, { cache: "no-store" });
    if (!res || !res.ok) return [];
    const rows = await res.json();
    return Array.isArray(rows) ? rows : [];
  } catch (_e) {
    return [];
  }
}

export const USER_MATERIAL_EVENT = "evcc-user-materials-loaded";

/* ============================================================
   THE LIVE LIST
   The token layer needs to know which materials exist without importing the loader's
   async path, exactly as the animal section reads window.AnimalSVG.list(). Kept here so
   there is ONE list, and so the theme-tokens module can stay synchronous.
   ============================================================ */
let _materials = [];

/** Replace the live list and announce it. Returns the list, for chaining. */
export function setUserMaterials(list) {
  _materials = Array.isArray(list) ? list.filter(Boolean) : [];
  if (typeof document !== "undefined" && document.dispatchEvent) {
    try { document.dispatchEvent(new CustomEvent(USER_MATERIAL_EVENT)); }
    catch (_e) { /* a rebuild that cannot be announced is still a correct list */ }
  }
  return _materials;
}

/** The drop-in materials known to this page. */
export function currentUserMaterials() {
  return _materials;
}
export { CATALOG_URL, ASSET_BASE, SHIPPED_BASE };
