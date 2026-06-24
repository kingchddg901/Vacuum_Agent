/**
 * ============================================================
 * I18N GATE — translate() contract + key cross-check
 * ============================================================
 *
 * One repeatable check for the card's i18n layer, run after every conversion
 * wave (and ideally in CI). It has two independent parts:
 *
 *   A. CONTRACT — exercises src/i18n/index.js `translate()` directly, asserting
 *      the behaviour the renderers depend on: locale -> base-language -> English
 *      -> key fallback, `{name}` interpolation, and — most importantly — TRUST
 *      MODEL B, where a (possibly community-contributed) catalog STRING is
 *      HTML-escaped by default and only the audited `raw` path keeps markup.
 *      The adversarial case is explicit: a locale value carrying `<script>` must
 *      come back neutralized, because locales ride the same untrusted-intake
 *      path as themes/animals. The visual harness only proves the English
 *      catalog renders byte-identical; it never sees a foreign locale or a
 *      hostile string, so this is where that boundary is actually verified.
 *
 *   B. KEYS — a static scan tying the two halves of the catalog together:
 *      every literal `t("…")` / `tRaw("…")` key used in src/ MUST exist in
 *      en.js (an orphan renders the raw key in the UI — a real bug, FATAL),
 *      and every en.js key SHOULD be referenced (a dead key is dropped
 *      translator effort — reported, non-fatal, since some keys are resolved
 *      dynamically from a variable and so are listed in DYNAMIC_KEYS).
 *
 * Exit code is non-zero iff a contract assertion fails or an orphan key exists.
 * Framework-free on purpose (node:assert + node:fs) so it runs anywhere node
 * does, with no dev-dependency and no build step.
 *
 * Run:  node scripts/check-i18n.mjs
 *
 * ============================================================
 */

import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, relative } from "node:path";
import { translate, registerLocale } from "../src/i18n/index.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..");
const SRC = join(REPO, "src");

let failures = 0;
const fail = (msg) => { failures += 1; console.error(`  ✗ ${msg}`); };

/* =========================================================
   A. translate() CONTRACT
   ========================================================= */
console.log("A. translate() contract");

// A throwaway locale + a deliberately hostile one, registered only for this run.
registerLocale("xx", {
  "rooms.empty": "Sala xx",
  "rooms.greeting": "Olá {name}",
});
registerLocale("ev", {
  // An attacker-supplied community locale value. Must never reach innerHTML raw.
  "rooms.empty": '<img src=x onerror="alert(1)">&"\'<b>',
});

const check = (label, fn) => {
  try { fn(); console.log(`  ✓ ${label}`); }
  catch (e) { fail(`${label} — ${e.message}`); }
};

// 1. English base resolves (plain text -> escaping is a no-op -> identity).
check("en key resolves to its value", () => {
  assert.equal(translate("en", "rooms.empty"),
    "No rooms yet — open the Setup tab and run Import Active Map (the highlighted button), then Configure Rooms to get started.");
});

// 2. A registered locale wins over English for the same key.
check("registered locale overrides English", () => {
  assert.equal(translate("xx", "rooms.empty"), "Sala xx");
});

// 3. Missing key in a known locale falls back to English.
check("missing locale key falls back to English", () => {
  assert.equal(translate("xx", "common.cancel"), translate("en", "common.cancel"));
});

// 4. Regional code falls back to its base language (xx-YY -> xx).
check("regional code falls back to base language", () => {
  assert.equal(translate("xx-YY", "rooms.empty"), "Sala xx");
});

// 5. Entirely unknown language falls back to English.
check("unknown language falls back to English", () => {
  assert.equal(translate("zz", "rooms.empty"), translate("en", "rooms.empty"));
});

// 6. Missing English key renders the key itself (a VISIBLE miss, never blank).
check("missing key renders the key (visible miss)", () => {
  assert.equal(translate("en", "does.not.exist"), "does.not.exist");
});

// 7. null/undefined language defaults to English (no throw).
check("null language defaults to English", () => {
  assert.equal(translate(null, "rooms.empty"), translate("en", "rooms.empty"));
  assert.equal(translate(undefined, "rooms.empty"), translate("en", "rooms.empty"));
});

// 8. TRUST MODEL B — a hostile catalog string is HTML-escaped by default.
check("hostile locale string is escaped (trust model B)", () => {
  const out = translate("ev", "rooms.empty");
  assert.ok(!out.includes("<img"), "raw <img survived escaping");
  assert.ok(!out.includes("<b>"), "raw <b> survived escaping");
  assert.equal(out, "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;&amp;&quot;&#39;&lt;b&gt;");
});

// 9. raw:true (the tRaw path) keeps authored markup intact.
check("raw option preserves markup", () => {
  const out = translate("ev", "rooms.empty", undefined, { raw: true });
  assert.equal(out, '<img src=x onerror="alert(1)">&"\'<b>');
});

// 10. Interpolation: {name} is replaced; the VALUE is inserted raw (the caller
//     escapes user data at the sink — the var XSS boundary is unchanged).
check("interpolation replaces {name}; value inserted raw", () => {
  assert.equal(translate("xx", "rooms.greeting", { name: "Ada" }), "Olá Ada");
  assert.equal(translate("xx", "rooms.greeting", { name: "<b>" }), "Olá <b>");
});

// 11. A missing interpolation var leaves its placeholder untouched.
check("missing interpolation var leaves placeholder", () => {
  assert.equal(translate("xx", "rooms.greeting", {}), "Olá {name}");
});

/* =========================================================
   B. KEY CROSS-CHECK (used in src  <->  defined in en.js)
   ========================================================= */
console.log("\nB. key cross-check");

// Keys resolved from a variable (not a literal), so the literal scan can't see
// them. They are referenced dynamically and must be exempt from the dead check.
// mobile-shell.js builds `mobile.tab_<id>` at render time from the view list.
const DYNAMIC_KEYS = new Set([
  "mobile.tab_dock", "mobile.tab_learning_review", "mobile.tab_map_bounds",
  "mobile.tab_map_config", "mobile.tab_room_rules", "mobile.tab_rooms",
  "mobile.tab_setup", "mobile.tab_stats", "mobile.tab_theme", "mobile.tab_upkeep",
]);

// Collect every literal t()/tRaw() key across src/, skipping the i18n module.
const USE = /\.t(?:Raw)?\("([^"]+)"/g;
const used = new Map();
const walk = (dir) => {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) { walk(p); continue; }
    if (!p.endsWith(".js")) continue;
    if (p.includes(`${join("src", "i18n")}`)) continue;
    const txt = readFileSync(p, "utf8");
    for (const m of txt.matchAll(USE)) {
      if (!used.has(m[1])) used.set(m[1], relative(REPO, p));
    }
  }
};
walk(SRC);

// Defined keys = top-level "key": entries in en.js.
const enTxt = readFileSync(join(SRC, "i18n", "en.js"), "utf8");
const defined = new Set([...enTxt.matchAll(/^\s*"([^"]+)":/gm)].map((m) => m[1]));

const orphans = [...used.keys()].filter((k) => !defined.has(k)).sort();
const dead = [...defined].filter((k) => !used.has(k) && !DYNAMIC_KEYS.has(k)).sort();

console.log(`  defined: ${defined.size}   used(literal): ${used.size}   dynamic-exempt: ${DYNAMIC_KEYS.size}`);

if (orphans.length === 0) {
  console.log("  ✓ no orphan keys (every used key exists in en.js)");
} else {
  for (const k of orphans) fail(`orphan key "${k}" used in ${used.get(k)} but missing from en.js`);
}

if (dead.length === 0) {
  console.log("  ✓ no dead keys");
} else {
  console.log(`  ⚠ ${dead.length} dead key(s) in en.js (defined, never referenced):`);
  for (const k of dead) console.log(`      - ${k}`);
}

/* ========================================================= */
console.log("");
if (failures > 0) {
  console.error(`FAIL — ${failures} problem(s).`);
  process.exit(1);
}
console.log("OK — i18n contract holds and all used keys are defined.");
