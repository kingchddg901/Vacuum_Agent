// Run: node --test src/textures/user-materials-every-bundle.test.mjs
//
// THE BUNDLE BOUNDARY IS THE DEFECT SURFACE, so this tests the boundary itself.
//
// scripts/build-card.mjs emits THREE independent esbuild bundles. Each one carries
// its own module instance of floor-texture-registry.js, so FLOOR_TEXTURE_REGISTRY
// is three different objects at runtime. Merging the drop-in catalogue in the panel
// teaches only the panel.
//
// That shipped: a drop-in material could be installed, validated, served, listed as
// a chip and SAVED onto a room, and the map still drew the room's plain floor type —
// because <eufy-vacuum-map> is loaded by a DYNAMIC import of its own bundle
// (cards/dashboard-card.js) whose registry had never heard of it. No error, no log.
// resolveFloorType falls through to floor_type for an unknown material BY DESIGN, so
// the failure renders as a perfectly normal map.
//
// A unit test of the loader cannot see this: the loader was correct. A unit test of
// the renderer cannot see it either: the renderer was correct. Only a test of WHICH
// BUNDLES REACH THE LOADER can, which is what this is — the same lesson as
// rooms-floor-material-reachability.test.mjs one layer out.
//
// It walks the real import graph from each entry point rather than grepping the
// built artifact, so it is deterministic, needs no build, and fails on the SOURCE
// change that would reintroduce the defect.
//
// Coverage:
//   [UMB-1] every entry point's import graph reaches ensure-user-materials.js
//   [UMB-2] ...and actually CALLS ensureUserMaterialsLoaded (importing is not using)
//   [UMB-3] the entry list this asserts over matches build-card.mjs's real entries
//   [UMB-4] the loader is idempotent per module instance — one fetch, many callers
//   [UMB-5] a failing catalogue fetch resolves empty rather than rejecting

import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(HERE, "..");
const REPO = path.resolve(SRC, "..");

const TARGET = path.join(SRC, "textures", "ensure-user-materials.js");

/** Relative import specifiers in a module's source, resolved to absolute paths. */
function importsOf(file) {
  const text = fs.readFileSync(file, "utf8");
  const out = [];
  // static `from "..."`, bare `import "..."`, and dynamic `import("...")`
  const re = /(?:from\s*|import\s*)\(?\s*["'](\.[^"']+)["']/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    const spec = m[1];
    let resolved = path.resolve(path.dirname(file), spec);
    if (!fs.existsSync(resolved) && fs.existsSync(resolved + ".js")) resolved += ".js";
    if (fs.existsSync(resolved) && fs.statSync(resolved).isFile()) out.push(resolved);
  }
  return out;
}

/** Every module reachable from `entry`, following relative imports. */
function graphFrom(entry) {
  const seen = new Set();
  const stack = [entry];
  while (stack.length) {
    const file = stack.pop();
    if (seen.has(file)) continue;
    seen.add(file);
    for (const dep of importsOf(file)) stack.push(dep);
  }
  return seen;
}

// The entries, named here so [UMB-3] can prove this list is not a stale copy.
const ENTRIES = [
  "src/all-cards.js",
  "src/cards-standalone.js",
  "src/cards/vacuum-map-host.js",
];

test("[UMB-1] every entry bundle's import graph reaches the drop-in loader", () => {
  for (const rel of ENTRIES) {
    const entry = path.join(REPO, rel);
    assert.ok(fs.existsSync(entry), `${rel} should exist`);
    const graph = graphFrom(entry);
    assert.ok(
      graph.has(TARGET),
      `${rel} must reach textures/ensure-user-materials.js — without it that ` +
      `bundle's FLOOR_TEXTURE_REGISTRY never learns a drop-in exists, and rooms ` +
      `using one silently render their plain floor_type instead`,
    );
  }
});

test("[UMB-2] each entry graph CALLS the loader, not merely imports it", () => {
  // Importing a module without calling it is exactly the shape that passes a
  // naive "is it wired?" check while changing nothing.
  for (const rel of ENTRIES) {
    const graph = graphFrom(path.join(REPO, rel));
    const calls = [...graph].filter((f) =>
      f !== TARGET && /ensureUserMaterialsLoaded\s*\(/.test(fs.readFileSync(f, "utf8")),
    );
    assert.ok(
      calls.length > 0,
      `${rel} reaches the loader but never calls ensureUserMaterialsLoaded(...)`,
    );
  }
});

test("[UMB-3] the asserted entry list matches build-card.mjs's real entry points", () => {
  // Pins the list against the build. A fourth bundle added later would otherwise
  // be born with this defect and every test here would still pass.
  const build = fs.readFileSync(path.join(REPO, "scripts", "build-card.mjs"), "utf8");
  const found = [...build.matchAll(/entryPoints:\s*\[\s*["']([^"']+)["']/g)].map((m) => m[1]);
  assert.deepEqual(
    [...found].sort(),
    [...ENTRIES].sort(),
    "build-card.mjs's entry points and this test's ENTRIES have diverged — a new " +
    "bundle must also load drop-in materials, or materials silently stop working in it",
  );
});

test("[UMB-4] the loader is idempotent per module instance", async () => {
  const mod = await import("./ensure-user-materials.js");
  mod.__resetUserMaterialsLoadForTests();

  let calls = 0;
  const fakeFetch = async () => {
    calls += 1;
    return { ok: true, json: async () => [] };
  };

  const a = mod.ensureUserMaterialsLoaded("test", fakeFetch);
  const b = mod.ensureUserMaterialsLoaded("test", fakeFetch);
  assert.equal(a, b, "concurrent callers must share ONE in-flight promise");
  await a;
  await mod.ensureUserMaterialsLoaded("test", fakeFetch);
  assert.equal(calls, 1, "the catalogue must be fetched once per bundle, not per caller");

  mod.__resetUserMaterialsLoadForTests();
});

test("[UMB-5] a failing catalogue fetch resolves empty rather than rejecting", async () => {
  // A drop-in failing to load must not take the map down with it, and an
  // unhandled rejection in a connectedCallback is exactly that.
  const mod = await import("./ensure-user-materials.js");
  mod.__resetUserMaterialsLoadForTests();

  const boom = async () => { throw new Error("network is down"); };
  const added = await mod.ensureUserMaterialsLoaded("test", boom);
  assert.deepEqual(added, [], "a failed fetch resolves to no added keys");

  mod.__resetUserMaterialsLoadForTests();
});
