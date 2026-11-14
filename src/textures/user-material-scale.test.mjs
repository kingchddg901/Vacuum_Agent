// Run: node --test src/textures/user-material-scale.test.mjs
//
// A FIELD THAT IS VALIDATED, STORED AND READ BY NOBODY.
//
// `scale` in material.json was accepted by the python validator, written into
// catalog.json, and carried onto the built material from 1a183bb2 — and no renderer
// ever read it. It sat on the OUTER object returned by entryFromCatalogRow, while
// mergeUserMaterials puts only `built.entry` into the registry, and the registry is what
// _resolveFloorScale consults. Every drop-in silently took the global default however
// carefully its descriptor was authored.
//
// It was invisible for an ordinary reason: the slate used to build the feature declares
// 0.05, which IS the global fallback, so the wired and unwired behaviour were identical
// on the only material anyone had. A field's presence reads as coverage; enumerating the
// producer's keys proves nothing about whether a consumer exists.
//
// So these tests assert REACHABILITY and PRECEDENCE, not storage: [UMS-2] drives the
// real resolver, and [UMS-3] uses a value that differs from the global so a dropped
// field cannot pass by coincidence.
//
// Coverage:
//   [UMS-1] a declared scale lands on the REGISTRY ENTRY, which is the part that travels
//   [UMS-2] the map resolver returns the material's own scale, not the global
//   [UMS-3] it is distinguishable from the global default (the test can actually fail)
//   [UMS-4] absent / zero / negative / non-numeric fall through rather than collapse
//   [UMS-5] a theme token still overrides a declared scale
//   [UMS-6] a LAYER's declared scale overrides the material's, for that layer only
//   [UMS-7] an undeclared layer scale follows the material and is never ZERO
//   [UMS-8] a declared layer scale survives the catalogue hop as entry.layers[].mapScale

import { test } from "node:test";
import assert from "node:assert/strict";

import { entryFromCatalogRow, mergeUserMaterials } from "./user-materials.js";
import { FLOOR_TEXTURE_REGISTRY } from "./floor-texture-registry.js";
import { applyMapBindings } from "../bindings/map.js";

const GLOBAL_DEFAULT = 0.05;   // FLOOR_TEXTURE_MASK_SCALE in bindings/map.js
const DECLARED = 0.42;         // deliberately unlike the global and unlike any table row

const row = (over = {}) => ({
  id: "scaley",
  name: "Scaley",
  dir: "scaley",
  layers: [
    { suffix: "base", color: "#555B60", opacity: 0.9, borrowed: false, path: "a.png", primary: true },
  ],
  ...over,
});

/** A card-ish host with just enough surface for _resolveFloorScale. */
function mapProto() {
  const proto = {};
  applyMapBindings(proto);
  return proto;
}

test("[UMS-1] a declared scale lands on the registry ENTRY", () => {
  // The entry is the only part mergeUserMaterials puts into the registry. A value on the
  // outer object is exactly as unreachable as no value at all.
  const built = entryFromCatalogRow(row({ scale: DECLARED }));
  assert.equal(built.entry.mapScale, DECLARED,
    "mapScale must be on .entry — the outer object does not travel");

  const registry = {};
  mergeUserMaterials(registry, [row({ scale: DECLARED })]);
  assert.equal(registry.scaley.mapScale, DECLARED,
    "and it must survive the merge into the registry the resolver reads");
});

test("[UMS-2] the map resolver returns the material's own scale", () => {
  FLOOR_TEXTURE_REGISTRY.scaley = entryFromCatalogRow(row({ scale: DECLARED })).entry;
  try {
    const proto = mapProto();
    const card = Object.create(proto);
    // host omitted: no getComputedStyle path, so this measures the registry hop alone
    assert.equal(card._resolveFloorScale("scaley", null), DECLARED);
  } finally {
    delete FLOOR_TEXTURE_REGISTRY.scaley;
  }
});

test("[UMS-3] the declared value is distinguishable from the global default", () => {
  // The guard against a test that passes on a dropped field: if DECLARED happened to
  // equal the global, [UMS-2] would pass with the wiring removed. This pins that it
  // does not — the exact coincidence that hid the defect on the real slate (0.05).
  assert.notEqual(DECLARED, GLOBAL_DEFAULT);

  FLOOR_TEXTURE_REGISTRY.plainly = { layers: [], masks: [], baseTexture: null };
  try {
    const card = Object.create(mapProto());
    assert.equal(card._resolveFloorScale("plainly", null), GLOBAL_DEFAULT,
      "a material declaring nothing still takes the global, so the two paths differ");
  } finally {
    delete FLOOR_TEXTURE_REGISTRY.plainly;
  }
});

test("[UMS-4] absent / zero / negative / non-numeric fall through", () => {
  // null means "not declared" and must not be confused with 0: a zero or negative scale
  // would collapse the tiling, so it is refused at the source rather than clamped into
  // something that looks deliberate.
  for (const bad of [undefined, null, 0, -1, NaN, {}, "abc"]) {
    const built = entryFromCatalogRow(row({ scale: bad }));
    assert.equal(built.entry.mapScale, null, `scale ${JSON.stringify(bad)} must not be kept`);
  }
  // A NUMERIC STRING coerces, deliberately and consistently with `opacity` directly
  // above it. The python validator emits a real float so this cannot arrive through the
  // real path, but the two numeric fields must not disagree about what they accept.
  assert.equal(entryFromCatalogRow(row({ scale: "0.3" })).entry.mapScale, 0.3);
  // ...and a material with no usable declaration resolves to the global, not to 0.
  FLOOR_TEXTURE_REGISTRY.zeroey = entryFromCatalogRow(row({ scale: 0 })).entry;
  try {
    const card = Object.create(mapProto());
    assert.equal(card._resolveFloorScale("zeroey", null), GLOBAL_DEFAULT);
  } finally {
    delete FLOOR_TEXTURE_REGISTRY.zeroey;
  }
});

test("[UMS-5] a theme token still overrides a declared scale", () => {
  // The declaration is a DEFAULT, not a lock — tuning by eye has to stay possible.
  FLOOR_TEXTURE_REGISTRY.scaley = entryFromCatalogRow(row({ scale: DECLARED })).entry;
  const realGCS = globalThis.getComputedStyle;
  globalThis.getComputedStyle = () => ({ getPropertyValue: (k) =>
    k === "--evcc-floor-scaley-map-scale" ? "0.9" : "" });
  try {
    const card = Object.create(mapProto());
    assert.equal(card._resolveFloorScale("scaley", {}), 0.9);
  } finally {
    globalThis.getComputedStyle = realGCS;
    delete FLOOR_TEXTURE_REGISTRY.scaley;
  }
});

// PER-LAYER SCALE. Two rates inside ONE material, for masks that are not the same
// physical sample as their siblings. The resolution is deliberately not the same
// precedence as the material's -- see _resolveLayerScale.
//
// BITE for each: [UMS-6] fails if the layer value is ignored or if the clamp is dropped;
// [UMS-7] fails if null is ever coerced with Number() (that would read 0, finite, and
// clamp the whole floor to 0.02); [UMS-8] fails if the field is dropped at the catalogue
// hop, which is where `scale` was lost for its first six months.
test("[UMS-6] a layer's declared scale overrides the material's", () => {
  const proto = mapProto();
  const card = Object.create(proto);

  assert.equal(card._resolveLayerScale(0.3, DECLARED), 0.3,
    "a positive layer scale wins over whatever the material settled on");
  assert.equal(card._resolveLayerScale(9, DECLARED), 2,
    "and is clamped to the same max as the material's — a layer cannot escape the range");
  assert.equal(card._resolveLayerScale(0.001, DECLARED), 0.02,
    "clamped at the bottom too");
});

test("[UMS-7] an undeclared layer scale follows the material, never zero", () => {
  const proto = mapProto();
  const card = Object.create(proto);

  // build_catalog writes an explicit null for every layer that declares no scale.
  for (const absent of [null, undefined, 0, -1, "0.3", NaN]) {
    assert.equal(card._resolveLayerScale(absent, DECLARED), DECLARED,
      `${JSON.stringify(absent)} must fall through to the material, not become a scale`);
  }
});

test("[UMS-8] a declared layer scale survives the catalogue hop", () => {
  const built = entryFromCatalogRow(row({
    layers: [
      { suffix: "base", color: "#555B60", opacity: 0.9, borrowed: false, path: "a.png", scale: null },
      { suffix: "joint", color: "#222222", opacity: 0.8, borrowed: false, path: "b.png", scale: 0.3 },
    ],
  }));
  assert.equal(built.entry.layers[0].mapScale, null,
    "an undeclared layer carries null — NOT 0, which Number(null) would have produced");
  assert.equal(built.entry.layers[1].mapScale, 0.3,
    "a declared one reaches the registry entry the map resolver reads");
});
