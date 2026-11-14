// Run: node --test src/textures/floor-mask-canvas.test.mjs
//
// EVERY SHIPPED MASK IS 2048x2048 — now a CHECKED invariant, not an authoring habit.
//
// WHY IT MATTERS MORE THAN IT USED TO. `_decodeMaskLum` fills at the bitmap's NATIVE
// resolution with a repeat pattern and applies `scale` through `pat.setTransform`, so the
// decoded mask's own width never enters the calculation. A mask authored at another canvas
// therefore changes tile PERIOD and feature SIZE together: it does not error, it does not
// look broken on its own, and two layers of one material from different canvases simply
// desynchronise. The top of `bindings/map.js` said so and then said nothing enforced it.
//
// `MASK_CANVAS_PX` now turns a PHYSICAL sample size into a raster scale:
//
//     scale = sample_m / (MASK_CANVAS_PX * metres_per_canvas_pixel)
//
// so an unpinned canvas no longer merely desynchronises two layers — it makes that
// arithmetic stop describing the mask it is applied to, silently, for every material that
// states a real-world size. The drop-in half of the set is already refused by
// `user_materials.py` (CANVAS); this is the shipped half, which nothing checked.
//
// WHAT WOULD MAKE IT RED: re-export one shipped mask at 1024 or 4096, or add a new one at
// a size `gen_floor_masks.py` did not produce. Ablation-proven by rewriting one PNG's IHDR
// width to 1024 — [FMC-1] named the file and the size.
//
// IT READS TRACKED FILES ONLY. All 18 masks under custom_components/eufy_vacuum/textures/
// are committed (they ship inside the HACS zip, so they have to be), and this walks the
// directory rather than consulting a list — a list is a second place to forget a file.
// No git subprocess: the pinned test container refuses one ("dubious ownership").
//
// Coverage:
//   [FMC-1] every shipped mask PNG is exactly 2048x2048
//   [FMC-2] the directory is non-empty and the walk actually found PNGs (a walk that
//           matched nothing passes every per-file assertion there is)

import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, dirname, relative } from "node:path";
import { fileURLToPath } from "node:url";

// This file is a FENCE, not a replica member: it asserts the shipped value rather
// than re-stating a rule, so moving the canvas turns it red -- which is the point.
const MASK_CANVAS_PX = 2048;   // see RNTA1EGS
const REPO = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const TEXTURES = join(REPO, "custom_components", "eufy_vacuum", "textures");

/** Every .png under `dir`, recursively. */
function pngsUnder(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...pngsUnder(p));
    else if (name.toLowerCase().endsWith(".png")) out.push(p);
  }
  return out;
}

/** `[width, height]` from a PNG's IHDR. The spec fixes IHDR as the first chunk, so these
 *  sit at bytes 16-24 of any valid PNG — the same read `user_materials.png_header` does,
 *  and the reason neither needs an image library. */
function pngSize(path) {
  const b = readFileSync(path);
  assert.ok(b.length >= 24 && b.readUInt32BE(12) !== undefined,
    `${path}: too short to hold an IHDR`);
  assert.equal(b.subarray(12, 16).toString("latin1"), "IHDR",
    `${path}: first chunk is not IHDR — not a PNG this reader understands`);
  return [b.readUInt32BE(16), b.readUInt32BE(20)];
}

test("[FMC-2] the shipped texture set is actually there", () => {
  // A walk that matched nothing passes every per-file assertion in [FMC-1] vacuously,
  // which is the one way this gate could read green while covering zero files.
  const found = pngsUnder(TEXTURES);
  assert.ok(found.length >= 18,
    `expected the shipped mask set under ${TEXTURES}, found ${found.length} PNGs`);
});

test("[FMC-1] every shipped mask is 2048x2048", () => {
  const wrong = [];
  for (const p of pngsUnder(TEXTURES)) {
    const [w, h] = pngSize(p);
    if (w !== MASK_CANVAS_PX || h !== MASK_CANVAS_PX) {
      wrong.push(`${relative(REPO, p)} is ${w}x${h}`);
    }
  }
  assert.deepEqual(wrong, [],
    "a mask at another canvas changes tile period and feature size together, and the "
    + "physical scale path reads MASK_CANVAS_PX as if it described this file:\n  "
    + wrong.join("\n  "));
});
