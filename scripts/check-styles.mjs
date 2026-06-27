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
import { readdirSync } from "node:fs";
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

if (failures) { console.error(`FAIL — ${failures} style problem(s).`); process.exit(1); }
console.log("OK — style modules import cleanly and every CSS export is brace-balanced.");
