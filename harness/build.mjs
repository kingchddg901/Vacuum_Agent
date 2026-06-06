/**
 * Bundle the headless mount entry for Playwright.
 *   node harness/build.mjs   ->   harness/dist/mount.js (IIFE, browser)
 *
 * Same esbuild path as scripts/build-card.mjs, minus minification and
 * the deploy target. `__ASSET_VER__` is defined because the bundled
 * texture registry references it (cache-bust token in the real build).
 */
import * as esbuild from "esbuild";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, "..");

await esbuild.build({
  entryPoints: [join(here, "mount-entry.js")],
  bundle: true,
  format: "iife",
  platform: "browser",
  target: "es2020",
  define: { __ASSET_VER__: JSON.stringify("harness") },
  outfile: join(here, "dist", "mount.js"),
  absWorkingDir: repo,
  logLevel: "info",
});

console.log("built harness/dist/mount.js");
