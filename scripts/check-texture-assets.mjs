#!/usr/bin/env node
/**
 * ============================================================
 * GATE: every shipped texture is referenced, every reference ships
 * ============================================================
 *
 * WHY THIS EXISTS
 * ---------------
 * `custom_components/eufy_vacuum/textures/` is inside the release payload:
 * release.yml zips the contents of custom_components/eufy_vacuum/ whole, minus
 * bytecode. So any file parked in that directory is downloaded by every user,
 * whether or not a renderer ever asks for it — and nothing used to check.
 *
 * It had already happened. `0383410b` (2026-07-04, "re-author carpet + granite as
 * split base+detail masks (fix black rooms)") moved rendering onto the split masks
 * and left the three full-colour source photographs behind:
 *
 *     carpet/texture-floor-carpet-low.png     6,603,900
 *     carpet/texture-floor-carpet-high.png    6,622,009
 *     granite/texture-floor-granite-light.png 6,776,906
 *                                            ----------
 *                                            20,002,815  = 78.1% of texture bytes
 *
 * 68% of the 29,462,699-byte 2.6.1 download, referenced by nothing in the package —
 * the only consumer is scripts/gen_floor_masks.py, which is not shipped either. They
 * now live under authoring/texture-sources/ and this gate is what stops the class
 * recurring: a file that no registry entry names cannot sit in the shipped tree.
 *
 * It is DELIBERATELY BIDIRECTIONAL. "Unreferenced" is the defect above; "missing" is
 * its mirror — a registry entry naming a mask that does not exist renders a material
 * as nothing, which is the state harness [FLOOR-1] exists to catch at render time.
 * Catching it here is cheaper and does not need a browser.
 *
 * THE REGISTRY IS IMPORTED, NOT PARSED. A regex over the module would drift from it
 * silently, which is the same failure shape as the thing being guarded. Importing
 * means the expectation is the real closed set: `layers[].url`, `masks[].url` and
 * `baseTexture`, with the module's own `?v=` cache-bust suffix stripped.
 *
 * USAGE
 *   node scripts/check-texture-assets.mjs        # exit 1 on any finding
 *   npm run check:textures
 * Guarded by scripts/check-texture-assets.test.mjs, which also proves it can fail.
 * ============================================================
 */

import { readdirSync, statSync, existsSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join, resolve, sep } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..");

export const TEXTURES_DIR = join(REPO, "custom_components", "eufy_vacuum", "textures");
const URL_PREFIX = "/eufy_vacuum/textures/";

/** Every texture path the registry can emit, as `<dir>/<file>.png`, deduped. */
export function referencedPaths(registry) {
  const out = new Set();
  const take = (u) => {
    if (typeof u !== "string" || !u) return;
    const noQuery = u.split("?")[0];
    const i = noQuery.indexOf(URL_PREFIX);
    // A url that is not under the textures prefix is not this gate's business.
    if (i < 0) return;
    out.add(noQuery.slice(i + URL_PREFIX.length));
  };
  for (const entry of Object.values(registry || {})) {
    if (!entry || typeof entry !== "object") continue;
    for (const layer of entry.layers || []) take(layer && layer.url);
    for (const mask of entry.masks || []) take(mask && mask.url);
    take(entry.baseTexture);
  }
  return out;
}

/** Every file actually on disk under `dir`, as `<dir>/<file>` relative paths. */
export function filesOnDisk(dir) {
  const out = new Set();
  if (!existsSync(dir)) return out;
  const walk = (abs, rel) => {
    for (const name of readdirSync(abs)) {
      const childAbs = join(abs, name);
      const childRel = rel ? `${rel}/${name}` : name;
      if (statSync(childAbs).isDirectory()) walk(childAbs, childRel);
      else out.add(childRel);
    }
  };
  walk(dir, "");
  return out;
}

/**
 * @returns {{unreferenced: string[], missing: string[], referenced: number, onDisk: number}}
 */
export function checkTextureAssets({ texturesDir = TEXTURES_DIR, registry }) {
  const referenced = referencedPaths(registry);
  const onDisk = filesOnDisk(texturesDir);
  return {
    unreferenced: [...onDisk].filter((f) => !referenced.has(f)).sort(),
    missing: [...referenced].filter((f) => !onDisk.has(f)).sort(),
    referenced: referenced.size,
    onDisk: onDisk.size,
  };
}

/** Load the real registry. Separate so the test can import it without the CLI. */
export async function loadRegistry() {
  const mod = await import(
    pathToFileURL(join(REPO, "src", "textures", "floor-texture-registry.js")).href
  );
  return mod.FLOOR_TEXTURE_REGISTRY;
}

const invokedDirectly =
  process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));

if (invokedDirectly) {
  const registry = await loadRegistry();
  const r = checkTextureAssets({ registry });
  // Print the INPUT, not only the verdict: "0 of 0" and "0 of 18" read identically
  // otherwise, and a gate that matched nothing is not a gate that passed.
  console.log(
    `check-texture-assets: ${r.onDisk} file(s) on disk, ${r.referenced} referenced by the registry`,
  );
  let bad = false;
  if (r.unreferenced.length) {
    bad = true;
    console.error(
      `\nUNREFERENCED — these ship to every user and no renderer loads them:\n  ` +
        r.unreferenced.join("\n  ") +
        `\n\nThe release zip is the contents of custom_components/eufy_vacuum/ taken whole, so a` +
        `\nbuild input stored here is downloaded by everyone. Put generator sources under` +
        `\nauthoring/texture-sources/ (see scripts/gen_floor_masks.py), or reference the file` +
        `\nfrom src/textures/floor-texture-registry.js if it is meant to render.`,
    );
  }
  if (r.missing.length) {
    bad = true;
    console.error(
      `\nMISSING — the registry names these and they are not on disk:\n  ` +
        r.missing.join("\n  ") +
        `\n\nA material whose mask cannot be fetched renders as nothing. Add the file, or drop` +
        `\nthe reference from src/textures/floor-texture-registry.js.`,
    );
  }
  if (bad) process.exit(1);
  console.log("OK — every shipped texture is referenced, and every reference ships.");
}
