// Run: node --test src/theme-tokens/user-floors.test.mjs
//
// Guards src/theme-tokens/user-floors.js — editor controls minted for a drop-in material.
//
// Coverage:
//   [UF-FLOOR-1] one colour + one opacity control per layer, keys minted by rule
//   [UF-FLOOR-2] keys come from tokenFor, NOT from the label — a renamed label cannot
//                move a key (the key is the shared-artifact identity)
//   [UF-FLOOR-3] NO -opacity-card token is minted (it would shadow the global master)
//   [UF-FLOOR-4] every token carries the material's own group heading
//   [UF-FLOOR-5] an unusable material yields nothing rather than a half group
//   [UF-FLOOR-6] multi-word suffixes humanise for the LABEL only

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  buildUserFloorTokens,
  buildUserFloorTokenRegistry,
  buildUserFloorGroupOrder,
  userFloorGroupLabel,
} from "./user-floors.js";
import { tokenFor } from "../textures/user-materials.js";

const material = (over = {}) => ({
  id: "slate",
  name: "Slate",
  entry: {
    layers: [
      { role: "base", colorDefault: "#555B60", opacityDefault: 0.95 },
      { role: "cut-a", colorDefault: "#A8641F", opacityDefault: 0.48 },
    ],
  },
  ...over,
});

test("[UF-FLOOR-1] one colour + one opacity control per layer", () => {
  const toks = buildUserFloorTokens(material());
  assert.equal(toks.length, 4);
  const keys = toks.map((t) => t.key);
  assert.deepEqual(keys, [
    "--evcc-floor-slate-base", "--evcc-floor-slate-base-opacity",
    "--evcc-floor-slate-cut-a", "--evcc-floor-slate-cut-a-opacity",
  ]);
});

test("[UF-FLOOR-2] keys come from the shared rule, not from the label", () => {
  // A renamed label must not move a key: the key is what every shared theme stores.
  const a = buildUserFloorTokens(material());
  const b = buildUserFloorTokens(material({ name: "Something Else Entirely" }));
  assert.deepEqual(a.map((t) => t.key), b.map((t) => t.key));
  assert.equal(a[0].key, tokenFor("slate", "base", "color"));
  assert.equal(a[1].key, tokenFor("slate", "base", "opacity"));
});

test("[UF-FLOOR-3] no -opacity-card token is minted", () => {
  const toks = buildUserFloorTokens(material());
  const offenders = toks.filter((t) => String(t.key).endsWith("-opacity-card"));
  assert.deepEqual(offenders, [],
    "a per-material -opacity-card would shadow --evcc-floor-texture-opacity-card");
});

test("[UF-FLOOR-4] every token carries the material's own group", () => {
  const toks = buildUserFloorTokens(material());
  const group = userFloorGroupLabel(material());
  assert.equal(group, "Floor Textures — Slate");
  for (const t of toks) assert.equal(t.group, group);
  assert.deepEqual(buildUserFloorGroupOrder([material()]), [group]);
});

test("[UF-FLOOR-5] an unusable material yields nothing, not a half group", () => {
  assert.deepEqual(buildUserFloorTokens(null), []);
  assert.deepEqual(buildUserFloorTokens({ id: "x" }), []);
  assert.deepEqual(buildUserFloorTokens({ id: "x", entry: { layers: [] } }), []);
  assert.deepEqual(buildUserFloorTokens({ entry: { layers: [{ role: "base" }] } }), []);
  assert.deepEqual(buildUserFloorGroupOrder([{ id: "x" }]), []);
});

test("[UF-FLOOR-6] multi-word suffixes humanise for the label only", () => {
  const toks = buildUserFloorTokens(material());
  const cut = toks.find((t) => t.key === "--evcc-floor-slate-cut-a");
  assert.equal(cut.label, "Cut A Color");
  assert.equal(cut.key, "--evcc-floor-slate-cut-a", "the key must keep the raw suffix");
});

test("[UF-FLOOR-7] the registry flattens every material in order", () => {
  const all = buildUserFloorTokenRegistry([
    material(),
    material({ id: "bamboo", name: "Bamboo", entry: { layers: [{ role: "grain" }] } }),
  ]);
  assert.equal(all.length, 6);
  assert.equal(all[4].key, "--evcc-floor-bamboo-grain");
  assert.deepEqual(buildUserFloorTokenRegistry(null), []);
});
