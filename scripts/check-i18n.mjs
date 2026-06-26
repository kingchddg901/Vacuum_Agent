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
 *      and every en.js key MUST be reachable from source — proven three ways
 *      (literal call, key-as-data-value, or a `t(`…${…}…`)` template extracted
 *      from the code), never a hand-maintained allowlist. A key reachable by
 *      none is a dead key (dropped translator effort, reported).
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
  // A hostile PLURAL form — escaping must apply to the selected form too.
  "rooms.count_rooms": { other: '<b>{count}</b>' },
});
// A real multi-form language (Russian: one/few/many/other) drives the
// Intl.PluralRules selection path; "de" has the key absent (English-object
// fallback); "pl" supplies only `other` (in-entry fallback when the chosen
// category is missing).
registerLocale("ru", {
  "rooms.count_rooms": {
    one: "{count} комната", few: "{count} комнаты",
    many: "{count} комнат", other: "{count} комнаты",
  },
});
registerLocale("pl", { "rooms.count_rooms": { other: "pokoje: {count}" } });

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

// --- Plurals (object-valued keys + Intl.PluralRules) ---------------------

// 12. English picks `one` for count===1 and `other` otherwise (CLDR English).
check("plural: English selects one vs other by count", () => {
  assert.equal(translate("en", "rooms.count_rooms", { count: 1 }), "1 room");
  assert.equal(translate("en", "rooms.count_rooms", { count: 5 }), "5 rooms");
  assert.equal(translate("en", "rooms.count_rooms", { count: 0 }), "0 rooms");
});

// 13. A real multi-form language selects the right CLDR category via Intl —
//     Russian: 1->one, 2->few, 5->many, 21->one (n%10==1 && n%100!=11).
check("plural: Intl.PluralRules drives multi-form selection (ru)", () => {
  assert.equal(translate("ru", "rooms.count_rooms", { count: 1 }), "1 комната");
  assert.equal(translate("ru", "rooms.count_rooms", { count: 2 }), "2 комнаты");
  assert.equal(translate("ru", "rooms.count_rooms", { count: 5 }), "5 комнат");
  assert.equal(translate("ru", "rooms.count_rooms", { count: 21 }), "21 комната");
});

// 14. A plural key called WITHOUT count falls to the `other` form (never blank).
check("plural: missing count falls to 'other'", () => {
  assert.equal(translate("en", "rooms.count_rooms"), "{count} rooms");
});

// 15. Partial locale (only `other`) uses its own `other` when the chosen
//     category is absent; a locale missing the key entirely falls to English.
check("plural: in-entry + cross-locale fallback", () => {
  assert.equal(translate("pl", "rooms.count_rooms", { count: 1 }), "pokoje: 1");
  assert.equal(translate("de", "rooms.count_rooms", { count: 1 }), "1 room");
  assert.equal(translate("de", "rooms.count_rooms", { count: 3 }), "3 rooms");
});

// 16. TRUST MODEL B holds for the SELECTED plural form — a hostile form is
//     escaped, and the count var is still inserted after escaping.
check("plural: selected form is escaped (trust model B)", () => {
  const out = translate("ev", "rooms.count_rooms", { count: 5 });
  assert.ok(!out.includes("<b>"), "raw <b> survived escaping in a plural form");
  assert.equal(out, "&lt;b&gt;5&lt;/b&gt;");
});

/* =========================================================
   B. KEY CROSS-CHECK (used in src  <->  defined in en.js)
   ========================================================= */
console.log("\nB. key cross-check");

// REACHABILITY IS DERIVED FROM SOURCE — not a hand-maintained allowlist. A defined
// key counts as referenced if the code uses it one of three PROVABLE ways:
//   (1) a literal `t("KEY")` / `tRaw("KEY")` call (also the orphan source);
//   (2) the full key appears as a quoted string anywhere in src — i.e. it's a
//       DATA VALUE handed to t() through a variable (registry `titleKey:"…"`, a
//       nav `labelKey:"mobile.tab_…"`, etc.);
//   (3) it matches a `t(`…${…}…`)` TEMPLATE found in src, each `${…}` standing in
//       for one key segment (map.variant_${k}_label, maintenance.status_${s}, …).
// Because the template patterns are extracted from the code, deleting a
// construction site automatically un-exempts its keys — there is no trusted list.
const LIT = /\.t(?:Raw)?\("([^"]+)"/g;          // t("literal")
const TMPL = /\.t(?:Raw)?\(`([^`]+)`/g;          // t(`tmpl ${var}`)
const SKIP_I18N = `${join("src", "i18n")}`;

// Build a regex from a t(`…`) template: literal segments stay literal, each ${…}
// becomes one [A-Za-z0-9_] key segment. A template with no namespace anchor (no "."
// in its leading literal) is REJECTED so a pathologically dynamic `${a}.${b}` can
// never silently exempt the whole catalog.
const templateToRegex = (tmpl) => {
  const parts = tmpl.split(/\$\{[^}]*\}/);
  if (!parts[0].includes(".")) return null;
  const esc = parts.map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  return new RegExp(`^${esc.join("[A-Za-z0-9_]+")}$`);
};

const used = new Map();      // literal-used KEY -> file
const tmplRegexes = [];      // one regex per accepted t(`…`) template
let allSrc = "";             // concatenated src (for quoted-string reachability)
const walk = (dir) => {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) { walk(p); continue; }
    if (!p.endsWith(".js") || p.includes(SKIP_I18N)) continue;
    const txt = readFileSync(p, "utf8");
    allSrc += `${txt}\n`;
    for (const m of txt.matchAll(LIT)) if (!used.has(m[1])) used.set(m[1], relative(REPO, p));
    for (const m of txt.matchAll(TMPL)) { const rx = templateToRegex(m[1]); if (rx) tmplRegexes.push(rx); }
  }
};
walk(SRC);

// Defined keys = top-level "key": entries in en.js.
const enTxt = readFileSync(join(SRC, "i18n", "en.js"), "utf8");
const defined = new Set([...enTxt.matchAll(/^\s*"([^"]+)":/gm)].map((m) => m[1]));

// A defined key is reachable iff one of the three provable forms references it.
const stringPresent = (k) => allSrc.includes(`"${k}"`) || allSrc.includes(`'${k}'`);
const templateMatch = (k) => tmplRegexes.some((rx) => rx.test(k));
const reachable = (k) => used.has(k) || stringPresent(k) || templateMatch(k);

const orphans = [...used.keys()].filter((k) => !defined.has(k)).sort();
const dead = [...defined].filter((k) => !reachable(k)).sort();
// "dynamic" = reachable but NOT via a literal t("…") — i.e. proven by data value or template.
const dynamicReached = [...defined].filter((k) => !used.has(k) && reachable(k)).length;

console.log(`  defined: ${defined.size}   literal-used: ${used.size}   reached via data/template: ${dynamicReached}   (templates: ${tmplRegexes.length})`);

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
