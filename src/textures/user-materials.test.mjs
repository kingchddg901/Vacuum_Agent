// Run: node --test src/textures/user-materials.test.mjs
//
// Guards src/textures/user-materials.js — catalogue rows to registry entries.
//
// Coverage:
//   [UM-1] token names are MINTED by rule, never read from the catalogue
//   [UM-2] a borrowed layer resolves to the SHIPPED textures path, not the drop-in's
//   [UM-3] the declared primary layer becomes baseTexture (what the SVG surface shows)
//   [UM-4] with no declared primary, layer 0 is used — matching getPrimaryTextureUrl
//   [UM-5] NO per-material -opacity-card token is emitted (it would shadow the global)
//   [UM-6] a shipped key is never overwritten by a drop-in
//   [UM-7] a malformed row is skipped, not merged half-built
//   [UM-8] a missing/failed catalogue fetch yields [], not a throw
//   [UM-9] an UNDECLARED scale/opacity (catalogue null) falls back, it does not become 0

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  entryFromCatalogRow,
  mergeUserMaterials,
  fetchUserMaterialCatalog,
  tokenFor,
} from "./user-materials.js";

const row = (over = {}) => ({
  id: "slate",
  name: "Slate",
  family: "stone",
  dir: "slate",
  opacity: 0.99,
  layers: [
    { suffix: "base", color: "#555B60", opacity: 0.95, borrowed: false, path: "face.png", primary: false },
    { suffix: "cleft", color: "#272C31", opacity: 0.58, borrowed: false, path: "cleft.png", primary: true },
  ],
  presets: [],
  ...over,
});

test("[UM-1] token names are minted by rule from the id and suffix", () => {
  const built = entryFromCatalogRow(row());
  assert.equal(built.entry.layers[0].colorToken, "--evcc-floor-slate-base");
  assert.equal(built.entry.layers[0].opacityToken, "--evcc-floor-slate-base-opacity");
  assert.equal(built.entry.layers[1].colorToken, "--evcc-floor-slate-cleft");
  // the rule is exported so there is exactly one place it lives
  assert.equal(tokenFor("slate", "cleft", "opacity"), "--evcc-floor-slate-cleft-opacity");
});

test("[UM-2] a borrowed layer resolves to the shipped textures path", () => {
  const built = entryFromCatalogRow(row({
    id: "bamboo", dir: "bamboo",
    layers: [
      { suffix: "base", color: "#C2A266", opacity: 0.39, borrowed: true,
        path: "wood/wood-directional-depth-mask.png", primary: false },
      { suffix: "grain", color: "#6B4F2A", opacity: 0.72, borrowed: false,
        path: "grain.png", primary: false },
    ],
  }));
  assert.equal(built.entry.layers[0].url,
    "/eufy_vacuum/textures/wood/wood-directional-depth-mask.png");
  assert.equal(built.entry.layers[1].url, "/eufy_vacuum/user_materials/bamboo/grain.png");
});

test("[UM-3] the declared primary layer becomes baseTexture", () => {
  // The SVG polygon surface shows this ONE image untinted. Slate's layer 0 is a flat
  // field, so defaulting to it would paint a blank wash.
  const built = entryFromCatalogRow(row());
  assert.equal(built.entry.baseTexture, "/eufy_vacuum/user_materials/slate/cleft.png");
});

test("[UM-4] with no declared primary, layer 0 is used", () => {
  const r = row();
  r.layers = r.layers.map((l) => ({ ...l, primary: false }));
  const built = entryFromCatalogRow(r);
  assert.equal(built.entry.baseTexture, "/eufy_vacuum/user_materials/slate/face.png");
});

test("[UM-5] no per-material -opacity-card token is emitted", () => {
  // It sits ABOVE the global --evcc-floor-texture-opacity-card master in the render's
  // var() fallback chain, so defining it per material would shadow that global for
  // anyone who set it. The entry's own opacityDefault is the right home.
  const built = entryFromCatalogRow(row());
  const all = JSON.stringify(built.entry);
  assert.ok(!all.includes("-opacity-card"),
    `a -opacity-card token leaked into the entry: ${all}`);
  assert.equal(built.entry.opacityDefault, 0.99);
});

test("[UM-6] a shipped key is never overwritten by a drop-in", () => {
  const registry = { wood: { layers: [], masks: [], baseTexture: null, shipped: true } };
  const res = mergeUserMaterials(registry, [row({ id: "wood", dir: "wood" })]);
  assert.deepEqual(res.added, []);
  assert.deepEqual(res.skipped, ["wood"]);
  assert.equal(registry.wood.shipped, true, "the shipped entry was replaced");
});

test("[UM-7] a malformed row is skipped, not merged half-built", () => {
  const registry = {};
  const res = mergeUserMaterials(registry, [
    row(),
    { id: "broken" },                                   // no layers
    { id: "alsobroken", layers: [{ suffix: "x" }] },     // layer with no path
  ]);
  assert.deepEqual(res.added, ["slate"]);
  assert.equal(res.skipped.length, 2);
  assert.deepEqual(Object.keys(registry), ["slate"]);
});

test("[UM-8] a failed catalogue fetch yields [] rather than throwing", async () => {
  assert.deepEqual(await fetchUserMaterialCatalog(async () => { throw new Error("offline"); }), []);
  assert.deepEqual(await fetchUserMaterialCatalog(async () => ({ ok: false })), []);
  assert.deepEqual(await fetchUserMaterialCatalog(async () => ({ ok: true, json: async () => ({}) })), []);
  assert.deepEqual(
    await fetchUserMaterialCatalog(async () => ({ ok: true, json: async () => [row()] })),
    [row()],
  );
});

// [UM-9] build_catalog writes an explicit `null` for a top-level scale/opacity the
// descriptor does not declare (user_materials.py:347-348). Number(null) is 0 and 0 IS
// finite, so a bare Number.isFinite test accepted it as a declared zero -- and the card
// multiplies every layer span by that number, so a drop-in rendered untextured on room
// cards while the map (which reads the PER-LAYER opacity instead) rendered it correctly.
//
// BITE: revert `_declared(row.opacity) ?? 0.99` to the bare
// `Number.isFinite(Number(row.opacity)) ? Number(row.opacity) : 0.99` and the first
// assertion reads 0.
test("[UM-9] an undeclared scale/opacity falls back rather than becoming 0", () => {
  const built = entryFromCatalogRow(row({ opacity: null, scale: null }));

  assert.equal(built.entry.opacityDefault, 0.99,
    "catalogue null means UNDECLARED; 0 would make every card layer span invisible");
  assert.equal(built.scale, null, "an undeclared scale stays null, not 0");
  assert.equal(built.entry.mapScale, null, "and never reaches the map as a zero scale");

  // A DECLARED zero is a real value and must survive.
  assert.equal(entryFromCatalogRow(row({ opacity: 0 })).entry.opacityDefault, 0,
    "an explicitly declared 0 is honoured, only null/undefined falls back");

  // A declared number is untouched -- slate and bamboo were never affected.
  assert.equal(entryFromCatalogRow(row({ opacity: 0.99 })).entry.opacityDefault, 0.99);
});
