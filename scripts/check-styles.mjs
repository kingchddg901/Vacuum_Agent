#!/usr/bin/env node
/**
 * Guard against the bug that broke the live card: each src/styles/*.js CSS
 * template literal must be whole. A stray backtick INSIDE one (e.g. `.is-open`
 * in a comment) closes the literal early; esbuild then bundles a TRUNCATED CSS
 * string — every rule after the backtick silently vanishes, with no build error
 * (it stays valid JS). That dropped the nav + header padding + the view-stage's
 * overflow:auto (dead scroll) on prod.
 *
 * Detection (false-positive-free, handles modules with several literals):
 *  - IMPORT each module. A stray backtick splits the literal; the spliced-in
 *    "CSS as JS" almost always fails to evaluate -> import throws (this is how
 *    the real bug was caught).
 *  - Every string export must be brace-balanced (a truncated CSS string is not).
 *
 * Run before every build (wired into `build` / `build:deploy`).
 */
import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const DIR = join(HERE, "..", "src", "styles");

let failures = 0;
const fail = (msg) => { failures += 1; console.error(`  ✗ ${msg}`); };

/* ---------------------------------------------------------------------------
 * BACKTICK LOCATOR — run BEFORE the import, because the import only tells you
 * that something broke, not where.
 *
 * The import check below is the real guard and catches this. What it cannot do
 * is point at it: a stray backtick ends the literal, everything after it parses
 * as JS, and the failure surfaces as e.g. "Unexpected identifier 'display'" —
 * an error naming a token that has nothing to do with the mistake, often
 * hundreds of lines away. Four separate times in one session that message cost
 * minutes of hunting for a one-character error.
 *
 * These modules are static CSS strings, so the rule is simple and exact: a
 * backtick inside a CSS COMMENT is always wrong. Writing `--evcc-thing` or
 * `display: table` in an explanatory comment is the natural habit that causes
 * it, and there is no legitimate reason for one there.
 *
 * Reported with file:line and the offending line, so the fix is immediate.
 * ------------------------------------------------------------------------- */
/* A backtick in a JS docblock OUTSIDE the literal is perfectly legal — the
   first version of this check flagged five of them. So it has to know where it
   is, which needs a scanner rather than a regex: JS comment, string, template
   literal, and CSS comment INSIDE a template are four different contexts and
   only the last makes a backtick an error. */
function strayBacktickLines(src) {
  const hits = [];
  let i = 0, line = 1;
  let inTemplate = false, inCssComment = false, interp = 0;
  const at = (s) => src.startsWith(s, i);

  while (i < src.length) {
    const c = src[i];
    if (c === "\n") { line += 1; i += 1; continue; }

    if (!inTemplate) {
      if (at("//")) { while (i < src.length && src[i] !== "\n") i += 1; continue; }
      if (at("/*")) { i += 2; while (i < src.length && !at("*/")) { if (src[i] === "\n") line += 1; i += 1; } i += 2; continue; }
      if (c === "'" || c === '"') { const q = c; i += 1; while (i < src.length && src[i] !== q) { if (src[i] === "\\") i += 1; i += 1; } i += 1; continue; }
      if (c === "`") { inTemplate = true; i += 1; continue; }
      i += 1; continue;
    }

    // Inside the template literal.
    if (src[i] === "\\") { i += 2; continue; }
    if (at("${")) { interp += 1; i += 2; continue; }
    if (interp > 0) {
      if (c === "}") interp -= 1;
      i += 1; continue;
    }
    if (at("/*")) { inCssComment = true; i += 2; continue; }
    if (at("*/")) { inCssComment = false; i += 2; continue; }
    if (c === "`") {
      if (inCssComment) hits.push(line);   // THE BUG: ends the literal early
      else inTemplate = false;             // the legitimate closing backtick
      i += 1; continue;
    }
    i += 1;
  }
  return hits;
}

for (const f of readdirSync(DIR).filter((n) => n.endsWith(".js") && !n.endsWith(".test.js"))) {
  const src = readFileSync(join(DIR, f), "utf8");
  const lines = src.split("\n");
  for (const line of strayBacktickLines(src)) {
    fail(
      `${f}:${line}: BACKTICK INSIDE A CSS COMMENT — it ends the template literal, ` +
      `truncating every rule after it.\n      ${(lines[line - 1] || "").trim()}\n      ` +
      `Fix: drop the backticks (write display:table, not the quoted form).`,
    );
  }
}

// anchor: CN50N9K4
for (const f of readdirSync(DIR).filter((n) => n.endsWith(".js") && !n.endsWith(".test.js"))) {
  let mod;
  try {
    mod = await import(pathToFileURL(join(DIR, f)).href);
  } catch (e) {
    fail(`${f}: failed to import — a stray backtick or broken template literal: ${e.message}`);
    continue;
  }
  for (const [name, val] of Object.entries(mod)) {
    if (typeof val !== "string") continue;
    let depth = 0;
    for (const c of val) { if (c === "{") depth += 1; else if (c === "}") depth -= 1; }
    if (depth !== 0) fail(`${f} (${name}): CSS brace imbalance (${depth}) — likely a truncated template literal.`);
  }
}

// anchor: CNDPYTCV
/* ---------------------------------------------------------------------------
 * THEME-LINT — no hardcoded color literal assigned to a CSS property in a rule
 * body. Every color must resolve through a theme token: `var(--evcc-*, fallback)`.
 * This is the guard that would have caught the profile card rendering off-theme
 * (raw --primary-color) and the map highlights ignoring a re-themed --evcc-accent.
 *
 *  - Scans the canonical CSS (src/styles/*) + the standalone cards' local CSS.
 *  - WHITELIST: the token DEFINITION file(s) — their literals ARE the defaults
 *    the tokens resolve to (that's the one correct place for a raw color).
 *  - A `var(...)` on the declaration = a themed value with a fallback = OK.
 *  - box-shadow / text-shadow are excluded (shadows are conventionally fixed).
 *  - ESCAPE HATCH: `theme-lint-ignore` in a comment on the line whitelists a
 *    deliberately theme-independent color (a legibility casing that must read
 *    over ANY room color, a fixed dark pill, a prefers-color-scheme override).
 * ------------------------------------------------------------------------- */
const REPO = join(HERE, "..");
// SCOPE: the canonical panel CSS (src/styles/*, minus the token DEFINITION file
// whose literals ARE the defaults) PLUS the standalone cards' local CSS. Every
// color must resolve through a theme token; deliberately theme-independent colors
// (map labels/pills/casing that must read over ANY room color, scrims, a
// prefers-color-scheme block) carry an explicit /* theme-lint-ignore */.
const TOKEN_DEF_FILES = new Set(["foundation.js"]);  // literals here = token defaults
const LINT_TARGETS = [
  ...readdirSync(DIR)
    .filter((n) => n.endsWith(".js") && !n.endsWith(".test.js") && !TOKEN_DEF_FILES.has(n))
    .map((n) => join("src", "styles", n)),
  join("src", "room-card.js"),
  join("src", "cards", "dashboard-card.js"),
  join("src", "cards", "profile-card.js"),
  join("src", "cards", "_shared.js"),
];
// A color property + its value. Negative lookbehind keeps `--evcc-border-*`
// TOKEN names (preceded by `-`) from matching the `border` property.
const COLOR_PROP = /(?<![-\w])(color|background(?:-color)?|border(?:-color)?|fill|stroke|outline(?:-color)?|accent-color|caret-color)\s*:\s*([^;{}]+)/g;
const COLOR_LIT = /#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(/;

for (const rel of LINT_TARGETS) {
  let text;
  try { text = readFileSync(join(REPO, rel), "utf8"); } catch { continue; }
  text.split(/\r?\n/).forEach((line, i) => {
    if (line.includes("theme-lint-ignore")) return;
    COLOR_PROP.lastIndex = 0;
    let m;
    while ((m = COLOR_PROP.exec(line))) {
      const value = m[2];
      if (COLOR_LIT.test(value) && !/var\(/.test(value)) {
        fail(`${rel}:${i + 1}: hardcoded color '${m[1]}: ${value.trim()}' — use var(--evcc-*, fallback), or add /* theme-lint-ignore */ if it must be theme-independent`);
      }
    }
  });
}

// anchor: CND7HKR6
/* ---------------------------------------------------------------------------
 * RTL-LINT — no PHYSICAL-direction CSS property. The card renders in Arabic /
 * Hebrew (see i18n isRTL/applyDir), so every left/right-anchored rule must be
 * LOGICAL (inline-start/end) or it won't mirror. This guards the conversion:
 * a new `margin-left` / `text-align: right` / `left:` fails the build.
 *
 *  - Scans the same targets as the theme-lint, MINUS map.js.
 *  - map.js is ALLOWLISTED: the map is spatial (coordinate math, canvas,
 *    positioned overlays, CSS-triangle borders) and is forced `direction: ltr`
 *    on `.evcc-map-view`, so its physical props are correct by construction.
 *  - vacuum-map-host.js IS scanned (its chrome flips; only the map surface is exempt).
 *  - `translateX` is NOT linted — centering (`inset-inline-start:50%` + translateX(-50%))
 *    is direction-neutral and shimmer keyframes are decorative.
 *  - ESCAPE HATCH: `rtl-ignore` in a line comment whitelists a deliberate
 *    physical use (a genuinely spatial offset outside the map).
 * ------------------------------------------------------------------------- */
const MAP_STYLES = join("src", "styles", "map.js");  // spatial — allowlisted from RTL-lint
const RTL_TARGETS = [
  ...LINT_TARGETS.filter((p) => p !== MAP_STYLES),
  join("src", "cards", "vacuum-map-host.js"),
];
// margin/padding/border -left|-right, text-align:left|right, and bare positioning
// left:/right:. Lookbehind (?<![-\w]) keeps the bare rule off compound props
// (border-left) and token names (--evcc-border-left).
const PHYSICAL_DIR = [
  /(?<![-\w])(?:margin|padding|border)-(?:left|right)\s*:/,
  /text-align\s*:\s*(?:left|right)\b/,
  /(?<![-\w])(?:left|right)\s*:/,
];
for (const rel of RTL_TARGETS) {
  let text;
  try { text = readFileSync(join(REPO, rel), "utf8"); } catch { continue; }
  text.split(/\r?\n/).forEach((line, i) => {
    if (line.includes("rtl-ignore")) return;
    for (const re of PHYSICAL_DIR) {
      const m = re.exec(line);
      if (m) {
        fail(`${rel}:${i + 1}: physical-direction CSS '${m[0]}' — use a logical property (inline-start/end, text-align:start/end), or add /* rtl-ignore */ if it must be physical`);
        break;
      }
    }
  });
}

// anchor: CNMF2SNK
/* ---------------------------------------------------------------------------
 * TOKEN-LINT — every `var(--evcc-*)` must resolve to something real.
 *
 * WHY. A token nothing defines still RENDERS, because the reference carries a
 * fallback — so it looks themeable, always falls back, and never appears in the
 * theme editor. It advertises a knob that does not exist. Three shipped that way
 * in one sitting (--evcc-modal-width-lg, --evcc-radius-sm, --evcc-font-mono) and
 * the theme-lint above could not see them: it flags un-tokenized COLOURS, and a
 * var() pointing at nothing is still a var(). Chris caught them by asking, which
 * is not a gate.
 *
 * A reference counts as resolved when it is:
 *   1. declared in CSS anywhere in the card (`--evcc-x: value`), including the
 *      token definition file whose literals ARE the defaults;
 *   2. present in the theme-token INVENTORY (src/theme-tokens/*), which declares
 *      tokens a THEME may supply that the card itself never defines;
 *   3. set at RUNTIME from a renderer, as an inline style="--evcc-x:${v}" — the
 *      map rotation and merged-group stroke are supplied per element, not themed.
 *
 * KNOWN_DANGLING is pre-existing debt, not permission. Entries fail once fixed
 * (see the stale check below), so the list can only ever shrink.
 * ------------------------------------------------------------------------- */
const TOKEN_REF = /var\(\s*(--evcc-[a-z0-9-]+)/g;
const TOKEN_DEF = /(--evcc-[a-z0-9-]+)\s*:/g;

// Sources that can DEFINE a token: all card CSS, plus renderers/cards for the
// inline-style runtime case.
const DEF_SOURCES = [
  ...readdirSync(DIR).filter((n) => n.endsWith(".js")).map((n) => join("src", "styles", n)),
  ...["renderers", "cards", "state", "bindings"].flatMap((d) => {
    const abs = join(REPO, "src", d);
    try {
      return readdirSync(abs).filter((n) => n.endsWith(".js")).map((n) => join("src", d, n));
    } catch { return []; }
  }),
  join("src", "room-card.js"),
];

const known = new Set();
for (const rel of DEF_SOURCES) {
  let text;
  try { text = readFileSync(join(REPO, rel), "utf8"); } catch { continue; }
  for (const m of text.matchAll(TOKEN_DEF)) known.add(m[1]);
}
// The inventory: tokens a theme may supply that the card never declares itself.
try {
  const TT = join(REPO, "src", "theme-tokens");
  for (const n of readdirSync(TT).filter((x) => x.endsWith(".js") && !x.includes(".test."))) {
    const text = readFileSync(join(TT, n), "utf8");
    for (const m of text.matchAll(/--evcc-[a-z0-9-]+/g)) known.add(m[0]);
    for (const m of text.matchAll(/["'`](evcc-[a-z0-9-]+)["'`]/g)) known.add("--" + m[1]);
  }
} catch { /* no inventory — every reference must then be defined in CSS */ }

// Pre-existing dangling references, recorded 2026-08-06. Each is a var() whose
// token nothing defines, so it silently always uses its fallback. Most look like
// near-misses of a real token (--evcc-text vs --evcc-text-primary, --evcc-border
// vs --evcc-border-default). Fix them and DELETE the entry; the stale check below
// makes leaving a fixed entry here a failure, so this list cannot rot upward.
const KNOWN_DANGLING = new Set([
  // EMPTY, and it should stay that way. The 11 entries recorded here on
  // 2026-08-06 were all fixed the same day: two map-overlay tokens and
  // --evcc-space-xs / --evcc-surface-hover were DEFINED (they completed
  // families that already existed), --evcc-on-accent and
  // --evcc-surface-default were renames onto exact-value tokens that were
  // already there, --evcc-font-size-sm and --evcc-shadow-overlay lost their
  // var() because no such family exists, and four were repointed at the real
  // token their fallback had been approximating.
]);

const seenDangling = new Set();
for (const rel of LINT_TARGETS) {
  let text;
  try { text = readFileSync(join(REPO, rel), "utf8"); } catch { continue; }
  text.split(/\r?\n/).forEach((line, i) => {
    if (line.includes("token-lint-ignore")) return;
    TOKEN_REF.lastIndex = 0;
    let m;
    while ((m = TOKEN_REF.exec(line))) {
      const tok = m[1];
      if (known.has(tok)) continue;
      if (KNOWN_DANGLING.has(tok)) { seenDangling.add(tok); continue; }
      fail(
        `${rel}:${i + 1}: var(${tok}) resolves to NOTHING — no CSS definition, ` +
        `not in the theme-token inventory, never set at runtime. It will always ` +
        `use its fallback and will not appear in the theme editor. Define it, ` +
        `use an existing token, or drop the var() for a literal.`
      );
    }
  });
}
// A KNOWN_DANGLING entry that no longer dangles is stale — remove it, or the list
// silently grants permission to reintroduce the token later.
for (const tok of KNOWN_DANGLING) {
  if (!seenDangling.has(tok)) {
    fail(`KNOWN_DANGLING lists ${tok}, but it no longer dangles — delete that entry from check-styles.mjs`);
  }
}

// anchor: CNN7APJJ
if (failures) { console.error(`FAIL — ${failures} style problem(s).`); process.exit(1); }
// anchor: CNCVC9M3
console.log("OK — style modules import cleanly, CSS exports brace-balanced, no un-tokenized colors, no physical-direction (non-RTL) CSS, and every --evcc-* reference resolves.");
