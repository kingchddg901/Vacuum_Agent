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
import {
  FLOOR_TEXTURE_REGISTRY,
  tilesAcrossFloor,
} from "./floor-texture-registry.js";

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

// [UM-10] A DROP-IN IS ART UNLESS IT SAYS OTHERWISE, and this is the hop where that
// survives. `tileable` crosses from Python to the registry as a real boolean -- never a
// null -- because the DEFAULT IS DECIDED IN ONE PLACE, on the Python side, and this end
// only carries it. Read truthily and `"false"` tiles; read with `??` and an older
// catalog.json written before the key existed starts tiling every pack on the box.
//
// Measured 2026-11-14 on the five drop-ins installed on the live machine: slate and
// bamboo tile, the three Material Author exports do not. So absence is not a cautious
// default, it is the accurate description of most packs that exist -- and the two that
// do tile say so explicitly rather than being guessed at.
test("[UM-10] tileable crosses the catalogue hop as a strict boolean", () => {
  assert.equal(entryFromCatalogRow(row({ tileable: true })).entry.tileable, true,
    "the claim must reach the registry, which is the only thing the renderer reads");
  assert.equal(entryFromCatalogRow(row({ tileable: false })).entry.tileable, false);

  // THE OLD-CATALOGUE CASE. A catalog.json written before this key existed has no
  // `tileable` at all; `undefined` must mean art. `?? false` would also do it, but `??`
  // is exactly what let `opacity: null` through as 0 in [UM-9] -- so this is pinned.
  const built = entryFromCatalogRow(row({}));
  assert.equal("tileable" in built.entry, true, "the key is always present on the entry");
  assert.equal(built.entry.tileable, false, "an absent key is ART, never tiling");

  // TRUTHY IS NOT THE TEST. Python already refuses anything but the literal true, so
  // these cannot arrive from build_catalog -- but a hand-edited catalog.json can, and
  // this end must not widen what that end narrowed.
  for (const junk of ["true", "false", 1, "yes", [], {}, "0"]) {
    assert.equal(entryFromCatalogRow(row({ tileable: junk })).entry.tileable, false,
      `${JSON.stringify(junk)} is not the literal true and must not make the claim`);
  }
});

// [UM-11] THE ONE LINE THAT DECIDES HOW EVERY FLOOR IS LAID, so it is tested away from
// the render path where it would be invisible among the rest.
//
// The default differs by population on purpose. Shipped masks are authored HERE, against
// this canvas, to wrap -- the wood generator divides plank width into SIZE so whole
// columns meet -- and the map is one continuous floor because of it. A drop-in's author
// knows none of that and cannot: not the map's resolution, not a stranger's room sizes.
// Measured on the five packs installed on the development machine, three of five do not
// tile, and all three are generator exports.
//
// BITE, and each of these is a real way to get it wrong:
//   - drop the userMaterial test  -> all eight SHIPPED types become fitted, re-laying
//                                    every floor on every existing map to fix a problem
//                                    they do not have. This is the expensive one.
//   - `entry.tileable` truthily   -> "false" and 0 tile; the Python side already narrowed
//                                    that and this end must not widen it back.
//   - unknown type returns false  -> a key that is not in the registry at all changes how
//                                    a floor is laid, which is not its business.
test("[UM-11] shipped materials always tile; a drop-in tiles only when it claims to", () => {
  // Every shipped entry, read from the registry rather than listed, so a type added
  // tomorrow is covered tomorrow and not whenever someone remembers this test.
  const shipped = Object.values(FLOOR_TEXTURE_REGISTRY).filter((e) => !e.userMaterial);
  assert.ok(shipped.length >= 8, `expected the shipped set, found ${shipped.length}`);
  for (const e of shipped) {
    assert.equal(tilesAcrossFloor(e), true,
      "a shipped material must keep tiling -- fitting it re-lays every existing map");
  }

  // A drop-in, built through the real catalogue hop: art by default, tiling on the claim.
  assert.equal(tilesAcrossFloor(entryFromCatalogRow(row()).entry), false,
    "a drop-in making no claim is ART");
  assert.equal(tilesAcrossFloor(entryFromCatalogRow(row({ tileable: true })).entry), true,
    "and tiles when it claims to");

  // TRUTHINESS IS NOT THE TEST, and these are hand-built entries ON PURPOSE. Routing junk
  // through entryFromCatalogRow cannot reach this clause -- that hop already narrows to
  // `=== true`, so every junk value arrives as a plain false and `!!false` agrees. Ablating
  // this function to `!!entry.tileable` stayed GREEN until the entries were built directly,
  // which is the whole reason the exported function defends itself: it takes an entry from
  // whoever holds one, and the catalogue hop is not the only way to hold one.
  for (const junk of ["true", "false", 1, "yes", [], {}, "0"]) {
    assert.equal(tilesAcrossFloor({ userMaterial: true, tileable: junk }), false,
      `${JSON.stringify(junk)} is not the literal true`);
  }
  assert.equal(tilesAcrossFloor({ userMaterial: true, tileable: true }), true);
  assert.equal(tilesAcrossFloor({ userMaterial: true }), false, "absent on a drop-in is ART");

  // A MISSING entry keeps the behaviour that existed before any of this. This matters
  // because the drop-in catalogue loads asynchronously: until it lands, its entry is
  // simply absent, and absent must not mean "fit".
  for (const absent of [undefined, null, 0, ""]) {
    assert.equal(tilesAcrossFloor(absent), true);
  }
});
