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

function hashTextures(dir) {
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
const outfile = deploy
  ? "custom_components/eufy_vacuum/frontend/eufy-vacuum-command-center.js"
  : "dist/eufy-vacuum-command-center.js";

const assetVer = hashTextures(TEXTURES_DIR);

await esbuild.build({
  entryPoints: ["src/all-cards.js"],
  bundle: true,
  minify: true,
  format: "esm",
  target: "es2020",
  define: { __ASSET_VER__: JSON.stringify(assetVer) },
  outfile,
});

console.log(`built ${outfile}  (texture asset ver ${assetVer})`);
