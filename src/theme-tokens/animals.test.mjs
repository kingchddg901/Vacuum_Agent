// Unit tests for the per-animal theme-token shape — specifically that the editor only lists the
// tokens an animal ACTUALLY themes (derived from its live `colors` block), so a memorial like
// Mittens (baked-literal fur, only `--animal-eye` dynamic) doesn't surface 8 inert palette no-ops.
// Run: node --test src/theme-tokens/animals.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";

// Stub the live animal registry the module reads at build time (window.AnimalSVG.get(name).colors).
const _FULL_PALETTE = {
  "--animal-fur": "", "--animal-fur-shadow": "", "--animal-fur-highlight": "",
  "--animal-eye": "", "--animal-pupil": "", "--animal-nose": "",
  "--animal-whisker": "", "--animal-ear-inner": "", "--animal-white-tip": "",
};
const _DEFS = {
  mittens: { colors: { "--animal-eye": "98 40% 42%" }, memorial: true },  // baked fur; a tribute
  cat: { colors: _FULL_PALETTE },
};
globalThis.window = {
  AnimalSVG: { get(name) { return _DEFS[name]; } },   // undefined for an unregistered name
};

const { buildAnimalTokenSets, buildAnimalGroupOrder } = await import("./animals.js");

const keysFor = (name) =>
  buildAnimalTokenSets([name]).perAnimal[0].tokens.map((t) => t.key);

test("[AN-1] Mittens exposes only its live tokens — eye base + 5 battery bands, no baked palette", () => {
  const keys = keysFor("mittens");
  assert.deepEqual(keys.slice().sort(), [
    "--evcc-animal-mittens-eye",
    "--evcc-animal-mittens-eye-charging",
    "--evcc-animal-mittens-eye-good",
    "--evcc-animal-mittens-eye-low",
    "--evcc-animal-mittens-eye-mid",
    "--evcc-animal-mittens-eye-warn",
  ].sort());
  for (const dead of ["fur", "fur-shadow", "fur-highlight", "pupil", "nose", "whisker", "ear-inner", "white-tip"]) {
    assert.ok(!keys.includes(`--evcc-animal-mittens-${dead}`), `should omit inert token ${dead}`);
  }
});

test("[AN-2] a full-palette animal (cat) still exposes all 14 tokens", () => {
  assert.equal(keysFor("cat").length, 14);
});

test("[AN-3] registry miss (animal not loaded yet) falls back to the full 14 — safe default", () => {
  assert.equal(keysFor("wolf").length, 14);   // window.AnimalSVG.get('wolf') === undefined
});

test("[AN-4] memorials group under 'Rainbow Bridge'; regulars under 'Animal Companion'", () => {
  const { perAnimal } = buildAnimalTokenSets(["cat", "mittens"]);
  const groupFor = (frag) =>
    perAnimal.find((g) => g.tokens.some((t) => t.key.includes(frag)))?.group;
  assert.equal(groupFor("mittens"), "Rainbow Bridge — Mittens");
  assert.equal(groupFor("cat"), "Animal Companion — Cat");
  // Tribute section comes after the everyday companions, with its heading-only parent.
  assert.deepEqual(buildAnimalGroupOrder(["cat", "mittens"]), [
    "Animal Companion",
    "Animal Companion — Cat",
    "Rainbow Bridge",
    "Rainbow Bridge — Mittens",
  ]);
});
