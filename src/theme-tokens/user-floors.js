/**
 * ============================================================
 * THEME TOKENS: drop-in floor materials
 * ============================================================
 *
 * Mints editor controls for a dropped-in material, so it appears in the theme editor as
 * its own group exactly like a shipped one.
 *
 * This is the floors' half of what `animals.js` already does for companions: the Animal
 * Companion section is built from the live registry and "adding a new animal requires no
 * edits here". Floors were the hand-authored half — `floor-textures.js` carries 53
 * `--evcc-floor-*` LITERALS — which is why a drop-in could not previously have editor
 * controls without someone editing source. Minting by rule is what removes that, and it
 * is also what makes the id the only irreversible commitment: rename a registry key and
 * the hand-authored literals do NOT follow, but a minted name is derived.
 *
 * The naming rule lives in `src/textures/user-materials.js::tokenFor` and is imported,
 * not restated — one rule, one place, or the two halves drift and the editor shows
 * controls that move nothing.
 *
 * ⚠ NO per-material `-opacity-card` token is minted. It sits ABOVE the global
 * `--evcc-floor-texture-opacity-card` master in the render's `var()` fallback chain, so
 * minting one per drop-in would shadow that global for anyone who set it. A material's
 * own card opacity belongs on the registry entry's `opacityDefault`, where the render
 * already reads it. See `docs/dev/frontend/floor-texture-map-view.md`.
 *
 * WHY THE EDITOR THEN POPULATES FOR FREE: `resolvedTheme()`'s "0b" seed block iterates
 * `FLOOR_TEXTURE_REGISTRY` and seeds each `colorToken` ← `colorDefault` and
 * `opacityToken` ← `opacityDefault`, gated on `THEME_TOKEN_MAP` membership. Merge the
 * material into the registry and mint its tokens into the map, and the seed picks it up
 * with no further work.
 * ============================================================
 */

import { makeTypedGroupToken } from "./helpers.js";
import { tokenFor } from "../textures/user-materials.js";

/** "cut-a" → "Cut A", for the control label only. Keys are never derived from this. */
function humanise(suffix) {
  return String(suffix)
    .split("-")
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/** The editor group heading for one drop-in material. */
export function userFloorGroupLabel(material) {
  const name = (material && material.name) || (material && material.id) || "";
  return `Floor Textures — ${name}`;
}

/**
 * Editor tokens for ONE drop-in material.
 *
 * @param {{id:string, name?:string, entry:{layers:Array}}} material
 * @returns {Array} token descriptors, empty if the material is unusable
 */
export function buildUserFloorTokens(material) {
  const id = material && material.id;
  const layers = material && material.entry && material.entry.layers;
  if (typeof id !== "string" || !id || !Array.isArray(layers) || !layers.length) return [];

  const g = makeTypedGroupToken(userFloorGroupLabel(material), "color");
  const out = [];
  for (const layer of layers) {
    const suffix = layer && layer.role;
    if (typeof suffix !== "string" || !suffix) continue;
    const human = humanise(suffix);
    out.push(g.color(tokenFor(id, suffix, "color"), `${human} Color`));
    out.push(g.unit(tokenFor(id, suffix, "opacity"), `${human} Layer Opacity`));
  }
  return out;
}

/** Flat token list for every drop-in, in stable order. */
export function buildUserFloorTokenRegistry(materials) {
  return (Array.isArray(materials) ? materials : []).flatMap(buildUserFloorTokens);
}

/** Group headings in editor order, one per drop-in that produced tokens. */
export function buildUserFloorGroupOrder(materials) {
  return (Array.isArray(materials) ? materials : [])
    .filter((m) => buildUserFloorTokens(m).length)
    .map(userFloorGroupLabel);
}
