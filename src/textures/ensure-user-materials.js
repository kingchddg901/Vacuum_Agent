/**
 * ============================================================
 * TEXTURES: DROP-IN MATERIALS — one load per BUNDLE, from every entry
 * ============================================================
 *
 * WHY THIS EXISTS, AND WHY IT IS NOT A HELPER FOR TIDINESS
 * -------------------------------------------------------
 * The card ships as THREE independently-built esbuild bundles
 * (`scripts/build-card.mjs`): the panel (`all-cards.js`), the always-loaded
 * standalone cards (`cards-standalone.js`), and the full map host
 * (`cards/vacuum-map-host.js`, loaded by a DYNAMIC import of its own served URL
 * from `cards/dashboard-card.js`). Each bundle carries its OWN module instance of
 * `floor-texture-registry.js`, so `FLOOR_TEXTURE_REGISTRY` is three different
 * objects at runtime, not one.
 *
 * Merging the drop-in catalogue in the panel therefore teaches ONLY the panel.
 * That is not a theoretical hazard — it shipped: a drop-in material could be
 * installed, validated, served, listed as a chip and SAVED onto a room, and the
 * map still drew the room's plain floor type, because the map host's registry had
 * never heard of it. Every end was correct; the value simply could not reach the
 * renderer that draws it. `resolveFloorType` falls through to `floor_type` for an
 * unknown material BY DESIGN (a removed drop-in must degrade to the room's own
 * floor rather than render flat), which is exactly why the failure is silent:
 * nothing errors, nothing logs, and the map looks like a map.
 *
 * THE REPO ALREADY SOLVES THIS SHAPE TWICE, and this follows that precedent rather
 * than inventing a third one:
 *
 *   - `ensureFontFacesInDocument()` (live:FONT-1) — "Idempotent; every entry calls
 *     it so the faces exist no matter which bundle loads first."
 *   - `ensureLocalesLoaded()` — same contract, same reason.
 *
 * `cards/vacuum-map-host.js` even carries an ISSUE #65 note about the identical
 * class of bug for TOKENS ("the embed defines NO --evcc-* of its own"), which is
 * the same lesson one layer up: whatever the panel sets up, the embed does not get
 * for free.
 *
 * CONTRACT
 * --------
 *   - Idempotent PER BUNDLE. The module-level promise is the guard, so concurrent
 *     callers share one fetch and a second call after it resolves is free. The
 *     promise is cached rather than a boolean so an early caller and a late one
 *     both get a value they can await.
 *   - NEVER REJECTS. A missing catalogue is the normal state (no drop-ins
 *     installed), so the resolved value is an empty array and the card renders
 *     shipped materials exactly as before. A drop-in failing to load must not take
 *     the map down with it.
 *   - Resolves to the keys ADDED to this bundle's registry, so a caller can decide
 *     whether a re-render is worth scheduling.
 *
 * TOKENS ARE REBUILT HERE TOO, but they are an enhancement rather than a
 * requirement: `renderers/floor-texture-surface.js` writes
 * `var(${layer.colorToken},${layer.colorDefault})`, so an unminted token falls back
 * to the catalogue's own colour and the material still draws. Rebuilding is what
 * makes it THEMEABLE — the editor controls only populate for tokens the registry
 * knows about.
 */

import { FLOOR_TEXTURE_REGISTRY } from "./floor-texture-registry.js";
import {
  fetchUserMaterialCatalog,
  mergeUserMaterials,
  setUserMaterials,
} from "./user-materials.js";
import { rebuildThemeTokens } from "../theme-tokens/index.js";

/** @type {Promise<string[]>|null} */
let _loadPromise = null;

/**
 * Load the drop-in material catalogue into THIS bundle's registry, once.
 *
 * @param {string} [label] - bundle name for warnings, so a console line says which
 *   bundle complained; three bundles can each log the same skip otherwise.
 * @param {Function} [fetchImpl] - injectable fetch, for tests.
 * @returns {Promise<string[]>} the registry keys added (empty when none).
 */
export function ensureUserMaterialsLoaded(label, fetchImpl) {
  if (_loadPromise) return _loadPromise;

  const who = label || "eufy-vacuum";
  _loadPromise = fetchUserMaterialCatalog(fetchImpl)
    .then((rows) => {
      if (!rows || !rows.length) return [];

      const { added, skipped, materials } = mergeUserMaterials(
        FLOOR_TEXTURE_REGISTRY,
        rows,
      );
      if (skipped.length) {
        console.warn(`[${who}] drop-in material(s) skipped:`, skipped.join(", "));
      }
      if (!added.length) return [];

      // ORDER IS LOAD-BEARING. resolvedTheme()'s "0b" seed walks
      // FLOOR_TEXTURE_REGISTRY and seeds colorToken <- colorDefault, gated on
      // THEME_TOKEN_MAP membership. Rebuild first and the tokens exist with
      // nothing to seed from; merge first and the editor controls come up
      // populated with no extra work.
      //
      // rebuildThemeTokens() is called EXPLICITLY rather than relying on the
      // document event setUserMaterials dispatches: the event is a convenience
      // for anything else that changes the list, and correctness must not depend
      // on a listener being attached yet.
      setUserMaterials(materials);
      rebuildThemeTokens();
      return added;
    })
    .catch((err) => {
      console.warn(`[${who}] drop-in materials failed to load:`, err);
      return [];
    });

  return _loadPromise;
}

/**
 * Drop the cached promise. TESTS ONLY — a module-level guard is otherwise
 * un-resettable, which would make the second test in a file assert against the
 * first one's fetch.
 */
export function __resetUserMaterialsLoadForTests() {
  _loadPromise = null;
}
