// Run: node --test src/styles/surface-card-override.test.mjs
//
// [SCO-*] THE ONE LEAF A HOME ASSISTANT THEME CAN OVERRIDE (issue #83).
//
// WHY THIS FILE EXISTS AT ALL, which is the part worth reading: check-styles.mjs cannot
// see the reference it guards. Its TOKEN_REF (`/var\(\s*(--evcc-[a-z0-9-]+)/g`) matches
// `var(--evcc-surface-card-override, ...)` perfectly well — but LINT_TARGETS is built by
// filtering out TOKEN_DEF_FILES, which is exactly `new Set(["foundation.js"])`
// (check-styles.mjs:139-143), because literals in that file are token DEFAULTS rather
// than un-tokenized colours. So the one file this mechanism lives in is the one file the
// token-lint does not read. check:styles passes while still printing "every --evcc-*
// reference resolves", and that sentence is true of everything it looked at.
//
// Which means a typo in the override name — `--evcc-surface-card-overide` — would ship
// green, and the only symptom would be a theme author's override silently doing nothing:
// the same complaint as #83, caused by us this time. That is what [SCO-1] and [SCO-2]
// are for, and neither is reachable by any existing gate.
//
// THE MECHANISM, in one sentence: an undeclared custom property inherits freely, so a
// theme setting --evcc-surface-card-override on the document reaches foundation's var()
// and wins, while an absent one falls through to the derivation that shipped. The
// override is therefore load-bearing BY ITS ABSENCE — declaring it anywhere, even once,
// even "for completeness", closes the door it exists to open. [SCO-2] is the only thing
// standing between that and a future tidy-up.
//
// Coverage
// --------
// [SCO-1] the declaration reads the override first and derives from surface-base second
// [SCO-2] the override is declared NOWHERE in src/ — the mechanism is its absence
// [SCO-3] the declaration does not reference its own name (a CSS cycle, discarded whole)
// [SCO-4] the 23 read sites are untouched: they still read --evcc-surface-card
// [SCO-5] no OTHER derived surface gained an override — the shipped surface stays one

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const REPO = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const FOUNDATION = readFileSync(join(REPO, "src", "styles", "foundation.js"), "utf8");

const OVERRIDE = "--evcc-surface-card-override";

/** Source with comments stripped — this file's own prose names the token repeatedly. */
function codeOnly(t) {
  return t.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
}

/** Every .js under src/, excluding tests. */
function srcFiles(dir = join(REPO, "src"), out = []) {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) srcFiles(p, out);
    else if (n.endsWith(".js") && !n.includes(".test.")) out.push(p);
  }
  return out;
}

test("[SCO-1] the declaration reads the override first, then derives", () => {
  // THE RED INPUT: reverting to `--evcc-surface-card: var(--evcc-surface-base);`, which
  // is what shipped through 2.6.1 and is what makes an HA theme's value unreachable.
  // Also red on a typo in the override name, which is the failure no other gate can see.
  // The contract is the ORDER, not the exact text. A third rung landed between the two in
  // 2.7.1 -- var(--ha-card-background, ...) -- so that a Home Assistant theme reaches the
  // card frame; see RNT9NEY2 in docs/dev/00c-replicas.md. The override must still come
  // FIRST (an inherited theme value wins) and the derivation LAST (absent one, nothing
  // changes); anything in between is a further fallback and cannot reorder those two.
  const decl = codeOnly(FOUNDATION).match(/--evcc-surface-card:\s*([^;]+);/);
  assert.ok(decl, "--evcc-surface-card must still be declared in foundation.js");
  const body = decl[1].replace(/\s+/g, " ").trim();

  assert.match(body, /^var\(\s*--evcc-surface-card-override\s*,/,
    "the override must be the FIRST rung, or an inherited theme value stops winning. " +
    `Got: ${body}`);
  assert.match(body, /var\(\s*--evcc-surface-base\s*\)\s*\)*\s*$/,
    "--evcc-surface-base must be the LAST rung, or the shipped derivation stops being " +
    `the final fallback and absent-everything changes. Got: ${body}`);

  // THE RED INPUT this replaces: reverting to `var(--evcc-surface-base)` alone, which is
  // what shipped through 2.6.1 and makes an HA theme's value unreachable. Still red, and
  // still red on a typo in the override name -- the failure no other gate can see.
  assert.ok(body.includes("--evcc-surface-card-override"),
    "the override name must appear exactly; a typo silently disables the whole mechanism");
});

test("[SCO-2] the override is declared NOWHERE — the mechanism is its absence", () => {
  // A declared custom property beats an inherited one. Declaring this token ANYWHERE in
  // our own CSS — including as `--evcc-surface-card-override: initial`, or adding it to
  // the theme-token registry so it shows up in the editor — would close the exact door
  // it exists to open, and the symptom would be indistinguishable from #83 itself.
  const offenders = [];
  for (const p of srcFiles()) {
    const code = codeOnly(readFileSync(p, "utf8"));
    // A DECLARATION is `--token:`; a REFERENCE is `var(--token`. Only the former is fatal.
    const re = new RegExp(OVERRIDE.replace(/-/g, "\\-") + "\\s*:", "g");
    for (const m of code.matchAll(re)) {
      // `var(--x, ...)` cannot produce `--x:` so any match here is a real declaration.
      offenders.push(`${p.slice(REPO.length + 1)} @ ${m.index}`);
    }
  }
  assert.deepEqual(
    offenders,
    [],
    `${OVERRIDE} is DECLARED in: ${offenders.join(", ")}. It must never be declared — ` +
    "an undeclared property inherits from the document, which is the only reason a " +
    "Home Assistant theme can reach it. Declaring it re-closes #83.",
  );
});

test("[SCO-3] the declaration does not reference its own name", () => {
  // The obvious thing to reach for is
  //   --evcc-surface-card: var(--evcc-surface-card, var(--evcc-surface-base));
  // meaning "inherited if set, else derive". CSS treats a var() that reads the property
  // being declared as a cycle and discards the whole declaration, so the token would
  // resolve to nothing and every card surface would fall to its read-site fallback.
  const decl = codeOnly(FOUNDATION).match(/--evcc-surface-card:\s*([^;]+);/);
  assert.ok(decl, "the --evcc-surface-card declaration must exist");
  assert.ok(
    !/var\(\s*--evcc-surface-card\s*[,)]/.test(decl[1]),
    `the declaration's value references its own name (${decl[1].trim()}), which CSS ` +
    "resolves as a cycle and throws out entirely — use the separately-named override",
  );
});

test("[SCO-4] the read sites are untouched and still read --evcc-surface-card", () => {
  // The alternative design moved the derivation into a var() fallback at every read
  // site. This case pins that we did NOT do that: the override is one line, and a line
  // cannot be partially applied, whereas 23 edited read sites can — silently, leaving
  // one surface not honouring the override with everything else green.
  let sites = 0;
  for (const p of srcFiles()) {
    const code = codeOnly(readFileSync(p, "utf8"));
    for (const _ of code.matchAll(/var\(\s*--evcc-surface-card\s*[,)]/g)) sites += 1;
  }
  assert.ok(
    sites > 10,
    `expected the many read sites of --evcc-surface-card to survive, found ${sites} — ` +
    "if this dropped, the derivation was moved into read-site fallbacks after all",
  );
  // And none of them should have been rewritten to read the override directly: the
  // override is an INPUT to the seed, not something the card's CSS consumes.
  let direct = 0;
  for (const p of srcFiles()) {
    if (p.endsWith(join("styles", "foundation.js"))) continue;
    const code = codeOnly(readFileSync(p, "utf8"));
    for (const _ of code.matchAll(new RegExp("var\\(\\s*" + OVERRIDE.replace(/-/g, "\\-"), "g"))) direct += 1;
  }
  assert.equal(
    direct,
    0,
    `${OVERRIDE} is read directly at ${direct} site(s) outside foundation.js. It is an ` +
    "input to the seed, consumed once; reading it elsewhere forks the mechanism.",
  );
});

test("[SCO-5] no other derived surface gained an override", () => {
  // Restraint is on the SHIPPED SURFACE, not on the seam: the same one-line rule
  // generalises to any leaf that earns it. But each one is a permanent public name a
  // theme author must learn, and 29 of them is a second vocabulary nobody asked for.
  // This case makes adding a second one a deliberate edit to a test rather than a quiet
  // accretion — the shape that produced the "Five committed gates" register with eight
  // things under it.
  const overrides = [...codeOnly(FOUNDATION).matchAll(/var\(\s*(--evcc-[a-z0-9-]*-override)\b/g)]
    .map((m) => m[1])
    .sort();
  assert.deepEqual(
    overrides,
    [OVERRIDE],
    `the shipped override surface is exactly one token; found ${overrides.length}: ` +
    `${overrides.join(", ")}. Adding another is fine, but say so here and in the ` +
    "user-facing theming doc, which is the only place a theme author can learn the name.",
  );
});
