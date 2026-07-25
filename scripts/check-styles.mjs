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

if (failures) { console.error(`FAIL — ${failures} style problem(s).`); process.exit(1); }
console.log("OK — style modules import cleanly, CSS exports brace-balanced, no un-tokenized colors, and no physical-direction (non-RTL) CSS.");
