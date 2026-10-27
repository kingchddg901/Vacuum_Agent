// Gate — LOCCOV, "every English key is translated in every shipped pack".
//
// WHY THIS EXISTS, and why card4-untranslated-strings.test.mjs is not it.
//
// `check-i18n.mjs` section C reports each pack's `→ en` fallback count and PASSES
// regardless: a key added to src/i18n/en.js and translated into none of the 17 packs
// renders English for every non-English user with nothing red. `--strict-coverage` does
// fail on it, but nothing in CI runs that mode (measured at 2.5.0, and that is how nine
// English-identical values sat unlisted until a release audit went looking).
// `[CARD4-1]` next door guards exactly three hardcoded keys — a real regression test for
// a real incident, and structurally unable to see a key added after it was written.
//
// So the leak that reached users was not a missing gate, it was a gate scoped to three
// names. This one is scoped to the manifest, which is the only scope that cannot go stale.
//
// It asserts an invariant that is TRUE as shipped: 2773 English keys, 17 packs, 0
// untranslated. Keep it that way by translating a new key in the same commit that adds it.
//
// Run: node --test src/i18n/locale-key-coverage.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { flattenLocale } from "./flatten.js";
import { en as enCatalog } from "./en.js";

const REPO = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const LOCALES_DIR = join(REPO, "custom_components", "eufy_vacuum", "frontend", "locales");

/** Load every shipped pack as `{ code, nested }`. `index.json` is the manifest, not a pack. */
function shippedPacks() {
  return readdirSync(LOCALES_DIR)
    .filter((f) => f.endsWith(".json") && f !== "index.json")
    .map((f) => ({ code: f.slice(0, -5), nested: JSON.parse(readFileSync(join(LOCALES_DIR, f), "utf8")) }));
}

/**
 * The gate itself, as a pure function of (manifest, packs) so that [LOCCOV-2] can run it
 * against inputs it knows are broken. A gate you cannot aim at a known-bad input has not
 * been shown able to fail.
 * @returns {string[]} `code:key` pairs that fall back to English.
 */
function untranslatedPairs(manifest, packs) {
  const pairs = [];
  for (const { code, nested } of packs) {
    const { coverage } = flattenLocale(nested, manifest);
    for (const key of coverage.untranslated) pairs.push(`${code}:${key}`);
  }
  return pairs;
}

test("[LOCCOV-1] every English key is translated in all 17 shipped locale packs", () => {
  const packs = shippedPacks();
  assert.equal(packs.length, 17, `expected 17 shipped packs, found ${packs.length}`);

  const pairs = untranslatedPairs(enCatalog, packs);

  assert.deepEqual(
    pairs,
    [],
    `${pairs.length} locale/key pair(s) silently fall back to English — every non-English ` +
      `user sees English there, and check:i18n's default mode passes anyway. ` +
      `Translate them in this commit, or state the exception in ` +
      `scripts/i18n-accepted-english.json. First few: ${pairs.slice(0, 8).join(", ")}` +
      (pairs.length > 8 ? `, … (+${pairs.length - 8} more)` : "")
  );
});

test("[LOCCOV-2] the coverage check is capable of failing (ablation)", () => {
  const packs = shippedPacks();
  // Measure against the tree's own baseline rather than against zero, so this case still
  // means something while a translation wave is mid-flight and [LOCCOV-1] is legitimately
  // red. What is asserted is the DELTA each injected defect produces.
  const baseline = untranslatedPairs(enCatalog, packs);

  // Shape 1 — a NEW English key no pack has yet. This is what adding a key to en.js and
  // forgetting the packs looks like, and it must light up once per pack.
  const sentinel = "vocab.__loccov_sentinel__.never_translated";
  const withNewKey = untranslatedPairs({ ...enCatalog, [sentinel]: "Sentinel" }, packs);
  const fromSentinel = withNewKey.filter((p) => p.endsWith(`:${sentinel}`));
  assert.equal(
    withNewKey.length - baseline.length,
    packs.length,
    `a new English key present in no pack should add one pair per pack ` +
      `(${packs.length}), added ${withNewKey.length - baseline.length} — the check is ` +
      `blind to the exact mistake it exists to catch`
  );
  assert.equal(
    fromSentinel.length,
    packs.length,
    "every added pair should name the sentinel key"
  );

  // Shape 2 — an EXISTING key removed from ONE pack. A whole-manifest miss and a
  // single-pack regression are different failures; a check that catches only the first
  // would pass a translation silently deleted during an edit.
  const victimKey = "vocab.status.completed";
  const victim = packs[0];
  const pruned = packs.map(({ code, nested }) =>
    code === victim.code
      ? { code, nested: pruneKey(JSON.parse(JSON.stringify(nested)), victimKey) }
      : { code, nested }
  );
  const afterPrune = untranslatedPairs(enCatalog, pruned);
  const added = afterPrune.filter((p) => !baseline.includes(p));
  assert.deepEqual(
    added,
    [`${victim.code}:${victimKey}`],
    `removing ${victimKey} from the ${victim.code} pack should add exactly that one ` +
      `pair, added ${JSON.stringify(added)} — if this is empty the prune did not land ` +
      `(the packs are authored NESTED) and [LOCCOV-1] proves nothing`
  );
});

/** Delete a dotted key from a nested pack, walking only sections that exist. */
function pruneKey(nested, dotted) {
  const parts = dotted.split(".");
  let cur = nested;
  for (let i = 0; i < parts.length - 1; i += 1) {
    if (!cur || typeof cur !== "object" || !(parts[i] in cur)) return nested;
    cur = cur[parts[i]];
  }
  if (cur && typeof cur === "object") delete cur[parts[parts.length - 1]];
  return nested;
}
