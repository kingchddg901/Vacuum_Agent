// Run: node --test scripts/check-texture-assets.test.mjs
//
// Guards scripts/check-texture-assets.mjs — the gate that stops an unreferenced file
// sitting in the shipped textures/ directory (20,002,815 bytes of generator source
// photos shipped to every user from 2026-07-04 until 2026-11-12 because nothing looked).
//
// [CTA-1] is the gate itself, run against the real tracked tree. The rest exist because
// a gate nobody has reddened is a preference: each names the exact input that breaks it.
// The synthetic arms use a temp directory, so none of them depends on repo state.
//
// Coverage (scripts/check-texture-assets.mjs):
//   [CTA-1] the real shipped tree is clean, and the counts are non-zero
//   [CTA-2] a file on disk that no registry entry names  -> reported as unreferenced
//   [CTA-3] a registry reference with no file on disk    -> reported as missing
//   [CTA-4] the module's own `?v=` cache-bust suffix is stripped before comparing
//   [CTA-5] a url outside the /eufy_vacuum/textures/ prefix is ignored, not mis-flagged
//   [CTA-6] nested subdirectories are walked (masks live one level down, per material)

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import {
  checkTextureAssets,
  referencedPaths,
  filesOnDisk,
  loadRegistry,
  TEXTURES_DIR,
} from "./check-texture-assets.mjs";

const U = "/eufy_vacuum/textures/";

/** A throwaway textures tree. Returns its path; caller removes it. */
function fixtureDir(files) {
  const root = mkdtempSync(join(tmpdir(), "evcc-tex-"));
  for (const rel of files) {
    const parts = rel.split("/");
    if (parts.length > 1) mkdirSync(join(root, ...parts.slice(0, -1)), { recursive: true });
    writeFileSync(join(root, ...parts), "x");
  }
  return root;
}

const entry = (urls) => ({ layers: urls.map((u) => ({ url: u })) });

test("[CTA-1] the real shipped textures tree has no unreferenced or missing files", async () => {
  const registry = await loadRegistry();
  const r = checkTextureAssets({ registry });

  // Print the INPUT as well as the verdict: a pass over an empty set is not a pass,
  // and "0 unreferenced of 0 files" reads identically to "0 of 18" without this.
  assert.ok(r.onDisk > 0, `no texture files found on disk at ${TEXTURES_DIR} — the probe cannot bite`);
  assert.ok(r.referenced > 0, "the registry referenced no textures at all — import or shape changed");

  assert.deepEqual(
    r.unreferenced,
    [],
    `files shipping to every user that no renderer loads: ${r.unreferenced.join(", ")}. ` +
      `Generator sources belong under authoring/texture-sources/.`,
  );
  assert.deepEqual(
    r.missing,
    [],
    `registry references with no file on disk: ${r.missing.join(", ")}. ` +
      `That material renders as nothing.`,
  );
});

test("[CTA-2] a file no registry entry names is reported — the defect this gate exists for", () => {
  const dir = fixtureDir(["wood/wood-grain-mask.png", "carpet/texture-floor-carpet-low.png"]);
  try {
    const r = checkTextureAssets({
      texturesDir: dir,
      registry: { wood: entry([`${U}wood/wood-grain-mask.png`]) },
    });
    assert.deepEqual(r.unreferenced, ["carpet/texture-floor-carpet-low.png"]);
    assert.deepEqual(r.missing, []);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("[CTA-3] a referenced mask absent from disk is reported — the mirror defect", () => {
  const dir = fixtureDir(["wood/wood-grain-mask.png"]);
  try {
    const r = checkTextureAssets({
      texturesDir: dir,
      registry: {
        wood: entry([`${U}wood/wood-grain-mask.png`, `${U}wood/wood-seam-mask.png`]),
      },
    });
    assert.deepEqual(r.missing, ["wood/wood-seam-mask.png"]);
    assert.deepEqual(r.unreferenced, []);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("[CTA-4] the ?v= cache-bust suffix is stripped — otherwise EVERY file reads unreferenced", () => {
  // The registry appends `?v=<asset-ver>` to every url at module load. Comparing the
  // raw url against a filename would make the gate fire on all 18 shipped masks at
  // once, which is the shape of a gate that gets deleted rather than fixed.
  const dir = fixtureDir(["wood/wood-grain-mask.png"]);
  try {
    const r = checkTextureAssets({
      texturesDir: dir,
      registry: { wood: entry([`${U}wood/wood-grain-mask.png?v=abc123`]) },
    });
    assert.deepEqual(r.unreferenced, []);
    assert.deepEqual(r.missing, []);
    assert.equal(r.referenced, 1);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("[CTA-5] a url outside the textures prefix is ignored, not counted or flagged", () => {
  const refs = referencedPaths({
    wood: entry([`${U}wood/wood-grain-mask.png`, "/eufy_vacuum/frontend/fonts/x.woff2", "", null]),
  });
  assert.deepEqual([...refs], ["wood/wood-grain-mask.png"]);
});

test("[CTA-6] nested per-material subdirectories are walked", () => {
  const dir = fixtureDir(["a/one.png", "b/c/two.png", "top.png"]);
  try {
    assert.deepEqual([...filesOnDisk(dir)].sort(), ["a/one.png", "b/c/two.png", "top.png"]);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("[CTA-7] masks[] and baseTexture are read, not only layers[]", () => {
  const refs = referencedPaths({
    carpet_low: {
      layers: [{ url: `${U}carpet/carpet-low-base-mask.png` }],
      masks: [{ url: `${U}carpet/carpet-low-detail-mask.png` }],
      baseTexture: `${U}carpet/carpet-low-base-mask.png?v=dev`,
    },
  });
  assert.deepEqual(
    [...refs].sort(),
    ["carpet/carpet-low-base-mask.png", "carpet/carpet-low-detail-mask.png"],
  );
});
