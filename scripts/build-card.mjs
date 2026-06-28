#!/usr/bin/env node
/**
 * Build the Lovelace card bundle, injecting a cache-bust token derived from the
 * texture assets' CONTENT. The token is appended (?v=<token>) to every texture
 * URL by the registry, so:
 *   - a texture change → new hash → browsers fetch the new asset immediately
 *     (no fighting the 7-day cache_headers=True served-texture cache)
 *   - no texture change → same hash → assets stay cached, no churn
 *
 * Usage:
 *   node scripts/build-card.mjs            → dist/ (local check)
 *   node scripts/build-card.mjs --deploy   → custom_components/.../frontend/ (shipped bundle)
 */
import * as esbuild from "esbuild";
import { createHash } from "node:crypto";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const TEXTURES_DIR = "custom_components/eufy_vacuum/textures";
const LOCALES_DIR = "custom_components/eufy_vacuum/frontend/locales";

// Content hash of a directory tree: name + bytes of every file. Used as a
// cache-bust token so a CHANGE to the assets yields a new ?v=<hash> URL (browsers
// + HA's service worker fetch fresh) while UNCHANGED assets keep one stable URL
// (stay cached, no churn). Same scheme for textures and for the runtime locale
// catalogs (which are fetched at runtime, NOT bundled, so they need their own bust).
function hashDir(dir) {
  const h = createHash("sha1");
  const walk = (d) => {
    for (const name of readdirSync(d).sort()) {
      const p = join(d, name);
      const st = statSync(p);
      if (st.isDirectory()) walk(p);
      else {
        h.update(name);          // name matters (URL changes if a file is renamed)
        h.update(readFileSync(p)); // content matters (URL changes if a file is edited)
      }
    }
  };
  walk(dir);
  return h.digest("hex").slice(0, 10);
}

const deploy = process.argv.includes("--deploy");
const outDir = deploy ? "custom_components/eufy_vacuum/frontend" : "dist";

const assetVer = hashDir(TEXTURES_DIR);
const localeVer = hashDir(LOCALES_DIR);

const shared = {
  bundle: true,
  minify: true,
  format: "esm",
  target: "es2020",
  // Lazy runtime loads of already-served bundles (the map host, the animal-svg
  // manifest) import by their /eufy_vacuum/frontend/ URL. Mark that prefix external
  // so esbuild leaves the dynamic import() as a runtime URL instead of trying to
  // resolve/bundle it (the map host is a BUILD OUTPUT, not a source file).
  external: ["/eufy_vacuum/frontend/*"],
  define: { __ASSET_VER__: JSON.stringify(assetVer), __LOCALE_VER__: JSON.stringify(localeVer) },
};

// THREE self-contained ESM bundles (no code-splitting):
//   1. the sidebar PANEL (command-center),
//   2. the always-loaded standalone CARDS bundle (room-card + dashboard card),
//   3. the heavy MAP HOST (the full map subsystem).
// The cards bundle does NOT import the map host statically — the dashboard card loads
// it on demand via a dynamic import of its ABSOLUTE served URL
// (/eufy_vacuum/frontend/eufy-vacuum-map.js), the same external-dynamic-import pattern
// main.js already uses for animal-svg. So the map's ~1MB graph loads only when show_map
// is on, and the always-loaded cards bundle stays lean. Self-contained bundles avoid
// the shared-chunk fragility of esbuild splitting; the duplicated common code is the
// price of a lazy, independently-cacheable map module.
await esbuild.build({ ...shared, entryPoints: ["src/all-cards.js"], outfile: `${outDir}/eufy-vacuum-command-center.js` });
await esbuild.build({ ...shared, entryPoints: ["src/cards-standalone.js"], outfile: `${outDir}/eufy-vacuum-cards.js` });
await esbuild.build({ ...shared, entryPoints: ["src/cards/vacuum-map-host.js"], outfile: `${outDir}/eufy-vacuum-map.js` });

console.log(`built command-center + cards + map-host bundles  (texture asset ver ${assetVer}, locale ver ${localeVer})`);
