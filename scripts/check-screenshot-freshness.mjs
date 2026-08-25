#!/usr/bin/env node
/**
 * DOES ANY COMMITTED SCREENSHOT NOW SHOW TEXT THE PRODUCT NO LONGER HAS?
 *
 * ⚠ WHY THIS EXISTS. `docs/screenshots/translations-hero-profile-card.png` rendered
 * "RUNS AS". `run_profiles.runs_as` became "Runs in this order" three days after that
 * image was committed. The README carried the outdated wording for SIX WEEKS and
 * shipped it in v2.1.0. Nothing noticed, because nothing in this repo compares a PNG
 * to the strings inside it — every gate we have checks code, and a screenshot is not
 * code. It surfaced only when a fresh capture happened to land beside the stale one.
 *
 * The check is not OCR. Each screenshot family declares which i18n keys it renders;
 * this records a fingerprint of those keys' ENGLISH VALUES and fails when they move.
 * It cannot tell you the image is wrong — it tells you the strings under it changed,
 * which is the signal a human needs to go and re-shoot.
 *
 *   node scripts/check-screenshot-freshness.mjs            # the gate
 *   node scripts/check-screenshot-freshness.mjs --update   # after re-shooting
 *
 * KEY SETS ARE DERIVED, NOT HAND-LISTED, wherever that is possible: static `t("…")`
 * literals are extracted from each card's own source, so a card that starts using a
 * new string is covered without anyone remembering to edit the manifest. The one part
 * that cannot be derived is the dynamic call `t(`vocab.${field}.${slug}`)` — the chip
 * labels (Vacuum/Mop, Quiet/Max). Those fields ARE statically declared at the
 * `chipRow(…, "fan_speed", …)` call sites, so the manifest names the four of them as
 * prefixes rather than sweeping all 682 `vocab.*` keys, which would flag every image
 * whenever an unrelated fault vocabulary entry moved.
 *
 * WHAT THIS DELIBERATELY DOES NOT COVER, so nobody reads a green run as more than it
 * is: the maintenance guide PROSE (the numbered care steps and notes inside
 * `Filter_*.png`) is model-aware content that does not live in `en.js`. Only that
 * card's chrome is fingerprinted. A guide-content rewrite will NOT flag those images.
 */
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import { en } from "../src/i18n/en.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
// EVCC_SCREENSHOT_MANIFEST lets the bite test drive this against a throwaway manifest
// carrying a deliberately wrong fingerprint, so it can prove a real change is DETECTED
// without editing en.js — a test that mutates a shipped source leaves the tree dirty
// when it fails, and that one is designed to fail.
const MANIFEST = process.env.EVCC_SCREENSHOT_MANIFEST || join(ROOT, "scripts", "screenshot-i18n-manifest.json");

/** Every static `t("some.key")` literal in a source file. */
function staticKeys(relPath) {
  const src = readFileSync(join(ROOT, relPath), "utf8");
  const out = new Set();
  for (const m of src.matchAll(/\bt\(\s*"([a-z_][a-z0-9_.]*)"/g)) out.add(m[1]);
  return out;
}

/** The full key set a family renders: extracted literals + declared prefixes. */
function keysFor(family) {
  const keys = new Set();
  for (const src of family.sources ?? []) for (const k of staticKeys(src)) keys.add(k);
  for (const p of family.prefixes ?? []) {
    for (const k of Object.keys(en)) if (k.startsWith(p)) keys.add(k);
  }
  // A declared key with no English value is a manifest bug, not a translation change:
  // it would hash as "absent" forever and quietly never fire again.
  return [...keys].filter((k) => typeof en[k] === "string").sort();
}

const short = (s) => createHash("sha1").update(s, "utf8").digest("hex").slice(0, 8);

/** key -> short hash of its English value. Per-key so a failure can NAME what moved. */
function fingerprint(keys) {
  const out = {};
  for (const k of keys) out[k] = short(en[k]);
  return out;
}

const manifest = JSON.parse(readFileSync(MANIFEST, "utf8"));
const update = process.argv.includes("--update");
const problems = [];

for (const [name, family] of Object.entries(manifest.families)) {
  const keys = keysFor(family);
  const now = fingerprint(keys);
  if (update) {
    family.keys = now;
    continue;
  }
  const was = family.keys ?? {};
  const changed = keys.filter((k) => was[k] && was[k] !== now[k]);
  const added = keys.filter((k) => !was[k]);
  const removed = Object.keys(was).filter((k) => !(k in now));
  if (changed.length || added.length || removed.length) {
    problems.push({ name, family, changed, added, removed });
  }
}

if (update) {
  writeFileSync(MANIFEST, JSON.stringify(manifest, null, 2) + "\n", "utf8");
  const n = Object.values(manifest.families).reduce((a, f) => a + Object.keys(f.keys).length, 0);
  console.log(`recorded ${n} key fingerprints across ${Object.keys(manifest.families).length} families`);
  process.exit(0);
}

if (!problems.length) {
  const n = Object.values(manifest.families).reduce((a, f) => a + Object.keys(f.keys ?? {}).length, 0);
  console.log(`OK — ${n} strings unchanged across ${Object.keys(manifest.families).length} screenshot families`);
  process.exit(0);
}

console.error("STALE SCREENSHOTS — the strings under these images have changed.\n");
for (const p of problems) {
  console.error(`  ${p.name}`);
  console.error(`    files: ${p.family.files.join(", ")}`);
  for (const k of p.changed) console.error(`    CHANGED  ${k}  ->  ${JSON.stringify(en[k])}`);
  for (const k of p.added) console.error(`    NEW      ${k}  ->  ${JSON.stringify(en[k])}`);
  for (const k of p.removed) console.error(`    GONE     ${k}`);
  console.error("");
}
console.error("Re-shoot the affected images, then:  node scripts/check-screenshot-freshness.mjs --update");
process.exit(1);
