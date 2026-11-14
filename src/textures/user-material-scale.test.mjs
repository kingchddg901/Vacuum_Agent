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
//
// ...and then the raster scale stopped being the only way to size a material. A pack may
// instead declare `sample_m` — how many METRES of real floor one tile of its masks covers
// — and the card derives the scale from the map's own resolution, so the same pack lands
// right on a 5 cm/cell raster and a 2 cm/cell one. [UMS-9..14] cover that path; the block
// above them says what makes each able to fail.
//
//   [UMS-9]  the derived scale round-trips to the sample size it was derived from
//   [UMS-10] a declared sample_m outranks a declared raster scale, where a resolution exists
//   [UMS-11] the sample-m token overrides the declaration; map-scale still beats both
//   [UMS-12] a layer's sample_m outranks its own scale; equal sizes REGISTER
//   [UMS-13] sample_m survives the catalogue hop at material AND layer level
//   [UMS-14] the clamp is a physical limit, and junk derives nothing
//   [UMS-15] a sizing token is readable under BOTH spellings of an underscored id

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

// ---------------------------------------------------------------------------
// THE PHYSICAL PATH. A material may say how much real floor one tile of its masks
// covers -- `sample_m`, in METRES -- and the card derives the raster scale from the
// map's own resolution instead of being handed a number tuned against one map.
//
//   scale = sample_m / (MASK_CANVAS_PX * metres_per_canvas_pixel)
//
// WHAT MAKES THESE ABLE TO FAIL. A raster scale and a derived one are both just numbers,
// so a test that asserts "0.05" proves nothing about WHICH path produced it -- which is
// how the original `scale` defect hid for six months (the only material anyone had
// declared 0.05, the global default, so wired and unwired were identical). Every case
// below therefore uses a sample size whose derived scale is UNLIKE the global, unlike the
// material's own declared scale, and unlike the per-type table -- so a dropped physical
// path lands on a different number, not the same one.
//
//   [UMS-9]  the arithmetic, round-tripped through its own physical meaning
//   [UMS-10] a declared sample_m outranks a declared raster scale -- and only while the
//            map's resolution is known
//   [UMS-11] token precedence: sample-m overrides the declaration, map-scale beats both
//   [UMS-12] a layer's sample_m outranks its own scale AND the material's; two layers
//            declaring the SAME size resolve EQUAL (registration by construction)
//   [UMS-13] sample_m survives the catalogue hop at both levels
//   [UMS-14] the clamp is a real floor and ceiling, and junk never derives

const M_PER_PX = 0.0125;         // a 5 cm/cell raster supersampled 4x -- the measured case
const MASK_PX = 2048;
/** The sample size that derives to `s` at M_PER_PX, so each case states its own intent. */
const sampleFor = (s) => s * MASK_PX * M_PER_PX;
const near = (got, want, what) =>
  assert.ok(Math.abs(got - want) < 1e-9, `${what}: expected ~${want}, got ${got}`);

const DERIVED = 0.31;                   // unlike 0.05 (global), unlike 0.42 (DECLARED),
const DERIVED_M = sampleFor(DERIVED);   // unlike every FLOOR_TEXTURE_MASK_SCALE_BY_TYPE row

test("[UMS-9] the derived scale means what it says it means", () => {
  const card = Object.create(mapProto());

  // The claim is not "this number" but "a tile of this mask covers sample_m of floor".
  // Asserting the round trip is what makes the ARITHMETIC bite rather than a constant:
  // flip the division and 1.28 m derives to 32768, which the clamp then hides at 2.
  for (const metres of [0.6, 1.28, 1.524, 12.0]) {
    const s = card._scaleFromSampleM(metres, M_PER_PX);
    near(s * MASK_PX * M_PER_PX, metres, `${metres} m round trip`);
  }
  near(card._scaleFromSampleM(sampleFor(0.05), M_PER_PX), 0.05,
    "a sample that happens to derive to the global still derives");

  // A MAP WITH NO RESOLUTION DERIVES NOTHING. A hand-drawn or CV backdrop carries no
  // device scale, and inventing one would size every floor against a fiction.
  for (const noRes of [null, undefined, 0, -1, NaN, "0.0125"]) {
    assert.equal(card._scaleFromSampleM(1.28, noRes), null,
      `mPerPx ${JSON.stringify(noRes)} must derive nothing`);
  }
});

test("[UMS-10] a declared sample_m outranks a declared raster scale", () => {
  FLOOR_TEXTURE_REGISTRY.physy = entryFromCatalogRow(
    row({ id: "physy", scale: DECLARED, sample_m: DERIVED_M })).entry;
  try {
    const card = Object.create(mapProto());
    near(card._resolveFloorScale("physy", null, M_PER_PX), DERIVED,
      "with a resolution, the physical fact wins over the tuned number");
    // ...and ONLY while there is a resolution. Without one the material is not left
    // sizeless -- it falls back to exactly the ladder that shipped before.
    assert.equal(card._resolveFloorScale("physy", null, null), DECLARED,
      "no map resolution -> the declared raster scale, unchanged");
    assert.equal(card._resolveFloorScale("physy", null), DECLARED,
      "a caller that passes no resolution at all behaves the same way");
  } finally {
    delete FLOOR_TEXTURE_REGISTRY.physy;
  }
});

test("[UMS-11] token precedence: sample-m overrides the declaration, map-scale beats both", () => {
  FLOOR_TEXTURE_REGISTRY.physy = entryFromCatalogRow(
    row({ id: "physy", scale: DECLARED, sample_m: DERIVED_M })).entry;
  const realGCS = globalThis.getComputedStyle;
  const style = (map) => { globalThis.getComputedStyle = () => ({
    getPropertyValue: (k) => (k in map ? String(map[k]) : "") }); };
  try {
    const card = Object.create(mapProto());

    // The physical TOKEN beats the physical DECLARATION -- the same relationship the
    // raster token has always had to the raster declaration.
    style({ "--evcc-floor-physy-sample-m": String(sampleFor(0.12)) });
    near(card._resolveFloorScale("physy", {}, M_PER_PX), 0.12, "sample-m token");

    // THE RASTER TOKEN STILL WINS. It is the escape hatch: if the derived size is wrong
    // -- a mask that does not depict what it claims, a map whose resolution is off --
    // one dial has to be guaranteed to win, and it must be the one already documented as
    // the override. The cost is the trap this pins: a map-scale token left over from
    // tuning by eye keeps winning after a sample size arrives, and the floor looks inert.
    style({ "--evcc-floor-physy-sample-m": String(sampleFor(0.12)),
            "--evcc-floor-physy-map-scale": "0.9" });
    assert.equal(card._resolveFloorScale("physy", {}, M_PER_PX), 0.9,
      "map-scale is the escape hatch and outranks the physical path");

    // A junk token falls back to the DECLARATION rather than to the global -- the
    // material still knows its own size.
    style({ "--evcc-floor-physy-sample-m": "wide" });
    near(card._resolveFloorScale("physy", {}, M_PER_PX), DERIVED, "unparseable sample-m token");
  } finally {
    globalThis.getComputedStyle = realGCS;
    delete FLOOR_TEXTURE_REGISTRY.physy;
  }
});

test("[UMS-12] a layer's sample_m outranks its scale, and equal sizes register", () => {
  const card = Object.create(mapProto());

  // Per-layer, the physical declaration beats the layer's own raster one for the same
  // reason it does at material level: the sample size is what the mask IS.
  near(card._resolveLayerScale(0.3, DECLARED, DERIVED_M, M_PER_PX), DERIVED,
    "layer sample_m over layer scale");
  near(card._resolveLayerScale(null, DECLARED, DERIVED_M, M_PER_PX), DERIVED,
    "layer sample_m over the material's resolved scale");
  assert.equal(card._resolveLayerScale(0.3, DECLARED, null, M_PER_PX), 0.3,
    "no layer sample_m -> the layer's own raster scale, exactly as before");
  assert.equal(card._resolveLayerScale(null, DECLARED, null, M_PER_PX), DECLARED,
    "neither -> follow the material");

  // REGISTRATION BY CONSTRUCTION, which is the whole reason per-layer sizing went
  // physical. Plank joints are cut into the very boards whose grain sits under them:
  // same patch of floor, so the same sample size, so the same rate on every map with
  // nobody checking. Under raster scales that held only while two hand-tuned numbers
  // happened to match -- and the one carrying a leftover scale is the realistic case.
  const grain = card._resolveLayerScale(null, DECLARED, 1.524, M_PER_PX);
  const joints = card._resolveLayerScale(0.3, DECLARED, 1.524, M_PER_PX);
  assert.equal(grain, joints,
    "two masks cut from the same area must tile identically even when one also " +
    "carries a leftover raster scale -- otherwise the cut drifts off the boards it cuts");

  // The null-is-not-zero trap, per layer, for the new field as well as the old one.
  for (const absent of [null, undefined, 0, -1, NaN, "1.5"]) {
    assert.equal(card._resolveLayerScale(null, DECLARED, absent, M_PER_PX), DECLARED,
      `layer sample_m ${JSON.stringify(absent)} must fall through, not become a size`);
  }
});

test("[UMS-13] sample_m survives the catalogue hop at both levels", () => {
  // Where `scale` was lost for its first six months: present on the outer object, absent
  // from `.entry`, which is the only part mergeUserMaterials puts into the registry.
  const built = entryFromCatalogRow(row({
    sample_m: 1.524,
    layers: [
      { suffix: "grain", color: "#555B60", opacity: 0.9, borrowed: false, path: "a.png",
        primary: true, sample_m: null },
      { suffix: "joints", color: "#222222", opacity: 0.8, borrowed: false, path: "b.png",
        sample_m: 0.9 },
    ],
  }));
  assert.equal(built.entry.sampleM, 1.524, "the material's size must reach the ENTRY");
  assert.equal(built.entry.layers[0].sampleM, null,
    "an undeclared layer carries null -- NOT 0, which Number(null) would have produced");
  assert.equal(built.entry.layers[1].sampleM, 0.9);

  const registry = {};
  mergeUserMaterials(registry, [row({ sample_m: 1.524 })]);
  assert.equal(registry.scaley.sampleM, 1.524,
    "and must survive the merge into the registry _resolveFloorSampleM reads");
});

test("[UMS-14] the derived scale is clamped, and junk never derives", () => {
  const card = Object.create(mapProto());

  // THE CLAMP IS A PHYSICAL LIMIT, not a sanity guard -- and the metres it maps to are a
  // property of the MAP, not of the function: at M_PER_PX (S=4) a tile spans 0.512..51.2 m,
  // at S=3 it is 0.68..68.3, at S=2 1.02..102. A 30 cm floor tile CANNOT be drawn at any of
  // them -- a 2048 px mask shown in 24 canvas pixels is not a texture any more -- while a
  // 0.6 m slab is fine here and clamps at S=3, which is one material reading two ways on
  // two robots. material_pack_contract.py sweeps that range at pack time so an author hears
  // it there rather than by squinting at a map.
  near(card._scaleFromSampleM(sampleFor(0.02), M_PER_PX), 0.02, "the floor is reachable");
  assert.equal(card._scaleFromSampleM(0.30, M_PER_PX), 0.02, "a 30 cm tile clamps at the floor");
  assert.equal(card._scaleFromSampleM(999, M_PER_PX), 2, "and a 999 m sample at the ceiling");

  for (const bad of [null, undefined, 0, -1, NaN, "1.28", {}, Infinity]) {
    assert.equal(card._scaleFromSampleM(bad, M_PER_PX), null,
      `sample ${JSON.stringify(bad)} must derive nothing`);
  }
});

// A DROP-IN ID MAY CONTAIN AN UNDERSCORE, AND TWO NAMING RULES MEET OVER IT.
//
// Shipped floor types are underscored keys with hyphenated token segments
// (`carpet_low` -> `--evcc-floor-carpet-low-map-scale`), and the sizing/rotation reads
// have always hyphenated to match. A DROP-IN's tokens are minted by `tokenFor` from the
// RAW id, and the python validator scopes a pack's presets to `--evcc-floor-<raw id>-`
// and REFUSES THE WHOLE MATERIAL for a key outside it. So for `cork_dark` -- an id the
// authoring doc blesses by name -- a preset naming the token the card read was rejected
// outright, and one naming the token the namespace demands was accepted and silently
// inert. There was no legal spelling.
//
// The fix reads BOTH, raw first (it is the one `tokenFor` mints). [UMS-15] pins that; the
// bite is an id containing `_`, which no test above this line uses, so none of them could
// ever have failed on it.
test("[UMS-15] a sizing token is readable under both spellings of an underscored id", () => {
  FLOOR_TEXTURE_REGISTRY.cork_dark = entryFromCatalogRow(row({ id: "cork_dark" })).entry;
  const realGCS = globalThis.getComputedStyle;
  const style = (map) => { globalThis.getComputedStyle = () => ({
    getPropertyValue: (k) => (k in map ? String(map[k]) : "") }); };
  try {
    const card = Object.create(mapProto());

    // The spelling a PRESET must use -- the only one the validator will accept.
    style({ "--evcc-floor-cork_dark-map-scale": "0.31" });
    assert.equal(card._resolveFloorScale("cork_dark", {}), 0.31,
      "the raw-id spelling is what tokenFor mints and what a pack preset must use");

    // The spelling that worked before, which some theme in the wild may already carry.
    style({ "--evcc-floor-cork-dark-map-scale": "0.33" });
    assert.equal(card._resolveFloorScale("cork_dark", {}), 0.33,
      "the hyphenated spelling must keep working -- this fix is additive, not a rename");

    // Both set: raw wins, matching every other token that material owns.
    style({ "--evcc-floor-cork_dark-map-scale": "0.31",
            "--evcc-floor-cork-dark-map-scale": "0.33" });
    assert.equal(card._resolveFloorScale("cork_dark", {}), 0.31);

    // Same for the physical token and for rotation.
    style({ "--evcc-floor-cork_dark-sample-m": String(sampleFor(0.17)) });
    near(card._resolveFloorScale("cork_dark", {}, M_PER_PX), 0.17, "sample-m, raw id");
    style({ "--evcc-floor-cork_dark-map-rotate": "37" });
    assert.equal(card._resolveFloorRotation("cork_dark", {}), 37);

    // AND THE SHIPPED CONVENTION IS UNTOUCHED. carpet_low has no raw-id token anywhere;
    // if the dual read had replaced the hyphenation rather than extending it, every
    // shipped multi-word type would have lost its dial.
    FLOOR_TEXTURE_REGISTRY.carpet_low = FLOOR_TEXTURE_REGISTRY.carpet_low
      || { layers: [], masks: [], baseTexture: null };
    style({ "--evcc-floor-carpet-low-map-scale": "0.44" });
    assert.equal(card._resolveFloorScale("carpet_low", {}), 0.44,
      "carpet_low -> carpet-low must still resolve");
  } finally {
    globalThis.getComputedStyle = realGCS;
    delete FLOOR_TEXTURE_REGISTRY.cork_dark;
  }
});
