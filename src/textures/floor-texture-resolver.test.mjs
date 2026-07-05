// Run: node --test src/textures/floor-texture-resolver.test.mjs
//
// Coverage (src/textures/floor-texture-resolver.js):
//   [RFT-*]  resolveFloorType    - spec format, legacy combined, aliases, direct keys, fallback.
//   [ROT-*]  normalizeFloorRotationDeg - non-finite -> 0, 0.1° quantise, wrap to [-180,180).

import { test } from "node:test";
import assert from "node:assert/strict";

import { resolveFloorType, normalizeFloorRotationDeg } from "./floor-texture-resolver.js";

/* ---------------------------------------------------------------------------
   resolveFloorType
   --------------------------------------------------------------------------- */

test("[RFT-1] spec format: {floor_type:'carpet', carpet_type} -> low unless explicitly high", () => {
  assert.equal(resolveFloorType({ floor_type: "carpet", carpet_type: "high_pile" }), "carpet_high");
  assert.equal(resolveFloorType({ floor_type: "carpet", carpet_type: "high" }), "carpet_high");
  assert.equal(resolveFloorType({ floor_type: "carpet", carpet_type: "low_pile" }), "carpet_low");
  assert.equal(resolveFloorType({ floor_type: "carpet" }), "carpet_low");          // no carpet_type -> low
  assert.equal(resolveFloorType({ floor_type: "carpet", carpet_type: "" }), "carpet_low");
});

test("[RFT-2] legacy combined carpet forms", () => {
  assert.equal(resolveFloorType({ floor_type: "carpet_low_pile" }), "carpet_low");
  assert.equal(resolveFloorType({ floor_type: "carpet_low" }), "carpet_low");
  assert.equal(resolveFloorType({ floor_type: "carpet_high_pile" }), "carpet_high");
  assert.equal(resolveFloorType({ floor_type: "carpet_high" }), "carpet_high");
});

test("[RFT-3] aliases: hardwood/laminate -> wood, granite -> granite_light", () => {
  assert.equal(resolveFloorType({ floor_type: "hardwood" }), "wood");
  assert.equal(resolveFloorType({ floor_type: "laminate" }), "wood");
  assert.equal(resolveFloorType({ floor_type: "wood" }), "wood");
  assert.equal(resolveFloorType({ floor_type: "granite" }), "granite_light");
  assert.equal(resolveFloorType({ floor_type: "granite_light" }), "granite_light");
});

test("[RFT-4] direct registry keys pass through", () => {
  for (const k of ["tile", "marble", "concrete"]) {
    assert.equal(resolveFloorType({ floor_type: k }), k);
  }
});

test("[RFT-5] case / whitespace insensitive", () => {
  assert.equal(resolveFloorType({ floor_type: "  WOOD  " }), "wood");
  assert.equal(resolveFloorType({ floor_type: "Carpet", carpet_type: "HIGH_PILE" }), "carpet_high");
});

test("[RFT-6] unrecognised / missing -> 'default'", () => {
  assert.equal(resolveFloorType({ floor_type: "linoleum" }), "default");
  assert.equal(resolveFloorType({}), "default");
  assert.equal(resolveFloorType(null), "default");
  assert.equal(resolveFloorType(undefined), "default");
});

/* ---------------------------------------------------------------------------
   normalizeFloorRotationDeg
   --------------------------------------------------------------------------- */

test("[ROT-1] non-finite / missing coerces to 0", () => {
  assert.equal(normalizeFloorRotationDeg(NaN), 0);
  assert.equal(normalizeFloorRotationDeg(Infinity), 0);
  assert.equal(normalizeFloorRotationDeg(-Infinity), 0);
  assert.equal(normalizeFloorRotationDeg(undefined), 0);
});

test("[ROT-2] in-range values pass through unchanged", () => {
  assert.equal(normalizeFloorRotationDeg(0), 0);
  assert.equal(normalizeFloorRotationDeg(90), 90);
  assert.equal(normalizeFloorRotationDeg(-90), -90);
  assert.equal(normalizeFloorRotationDeg(-179.9), -179.9);
});

test("[ROT-3] wraps into [-180, 180) — 180 and 270 fold to the negative half", () => {
  assert.equal(normalizeFloorRotationDeg(180), -180);   // 180 == -180
  assert.equal(normalizeFloorRotationDeg(270), -90);
  assert.equal(normalizeFloorRotationDeg(360), 0);
  assert.equal(normalizeFloorRotationDeg(450), 90);
  assert.equal(normalizeFloorRotationDeg(-180), -180);
  assert.equal(normalizeFloorRotationDeg(-270), 90);
});

test("[ROT-4] quantises to 0.1° so getComputedStyle noise can't churn the cache", () => {
  assert.equal(normalizeFloorRotationDeg(45.0001), 45);   // sub-0.1° noise -> dedup (the point)
  assert.equal(normalizeFloorRotationDeg(45.03), 45);
  assert.equal(normalizeFloorRotationDeg(45.12), 45.1);
  assert.equal(normalizeFloorRotationDeg(45.17), 45.2);
});
