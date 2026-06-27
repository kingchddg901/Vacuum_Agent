#!/usr/bin/env node
/**
 * Guard against the bug that broke the live card: each src/styles/*.js module is
 * ONE CSS template literal, and a stray backtick INSIDE it (e.g. `.is-open` in a
 * comment) closes the literal early. esbuild then bundles a truncated CSS string
 * — every rule after the backtick silently vanishes, with NO build or lint error
 * (it stays valid JS). That dropped the nav + header padding + the view-stage's
 * overflow:auto (dead scroll) on prod.
 *
 * Two checks per module:
 *  1. After the template-literal opener (`= \``), the ONLY backtick allowed is the
 *     closer — exactly one. More than one = stray backtick(s) truncating the CSS.
 *  2. The imported CSS string must be brace-balanced.
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
  const path = join(DIR, f);
  const txt = readFileSync(path, "utf8");

  // 1. Stray-backtick check — count backticks AFTER the first `= \`` opener.
  //    (Backticks in a JSDoc comment BEFORE the export are fine — excluded.)
  const opener = txt.match(/=\s*`/);
  if (opener) {
    const afterOpener = txt.slice(opener.index + opener[0].length);
    const ticks = (afterOpener.match(/`/g) || []).length;
    if (ticks !== 1) {
      fail(`${f}: ${ticks} backtick(s) after the template opener (expected 1 = the closer) — a stray backtick truncates the CSS.`);
    }
  }

  // 2. Import + brace balance on the largest string export (the CSS).
  try {
    const mod = await import(pathToFileURL(path).href);
    const css = Object.values(mod)
      .filter((v) => typeof v === "string")
      .sort((a, b) => b.length - a.length)[0];
    if (css) {
      let depth = 0;
      for (const c of css) { if (c === "{") depth += 1; else if (c === "}") depth -= 1; }
      if (depth !== 0) fail(`${f}: CSS brace imbalance (${depth}).`);
    }
  } catch (e) {
    fail(`${f}: failed to import (likely a broken template literal): ${e.message}`);
  }
}

if (failures) { console.error(`FAIL — ${failures} style problem(s).`); process.exit(1); }
console.log("OK — style modules: no stray backticks, CSS brace-balanced.");
