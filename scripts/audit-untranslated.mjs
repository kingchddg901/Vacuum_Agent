/**
 * Value-equals-English audit. check:i18n proves every key is PRESENT (0 -> en
 * fallback); this finds keys whose translated value was left IDENTICAL to the
 * English source — the untranslated-leak class (e.g. de "theme.tab_themes" =
 * "Themes" instead of "Themen"). Many matches are legitimate (proper nouns,
 * jargon kept on purpose, true cognates, symbols/numbers) — this only surfaces
 * candidates; a human/triage pass decides which are real leaks.
 *
 * Run: node scripts/audit-untranslated.mjs
 */
import { en } from "../src/i18n/en.js";
import { flattenLocale } from "../src/i18n/flatten.js";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const LOCALES_DIR = join(HERE, "..", "custom_components", "eufy_vacuum", "frontend", "locales");
const CODES = ["de", "fr", "es", "nl", "it", "pt", "ru"];
// Prints the per-locale candidate COUNTS to stdout always; pass an output dir to
// also dump the full per-locale TSVs there (e.g. node scripts/audit-untranslated.mjs ./out).
const OUT = process.argv[2] || null;

// Obvious non-leaks to pre-filter from the candidate list (still listed in a
// separate "ignored" bucket so nothing is hidden): pure symbols/numbers, single
// chars, placeholder-only values.
const isTrivial = (v) =>
  v.trim() === "" ||
  /^[\d\s.,:%×x°/+\-—–·#()]*$/.test(v) ||          // numbers / punctuation / units only
  v.length <= 1 ||
  /^\{[^}]+\}$/.test(v.trim());                      // a lone {placeholder}

const summary = [];
for (const code of CODES) {
  const raw = JSON.parse(readFileSync(join(LOCALES_DIR, `${code}.json`), "utf8"));
  const { flat } = flattenLocale(raw, en);

  const candidates = [];
  const trivial = [];
  for (const key of Object.keys(en)) {
    const ev = en[key];
    if (typeof ev !== "string") continue;            // skip plural objects
    const lv = flat[key];
    if (typeof lv !== "string") continue;
    if (lv !== ev) continue;                          // translated -> fine
    (isTrivial(ev) ? trivial : candidates).push([key, ev]);
  }

  candidates.sort((a, b) => a[0].localeCompare(b[0]));
  if (OUT) {
    const lines = candidates.map(([k, v]) => `${k}\t${v}`).join("\n");
    writeFileSync(join(OUT, `untranslated-${code}.tsv`), `key\tvalue(==en)\n${lines}\n`, "utf8");
  }
  summary.push(`${code}: ${candidates.length} candidate(s) value==en  (+${trivial.length} trivial symbol/number skipped)`);
}

console.log(summary.join("\n"));
console.log(
  "\nCandidates are value==English, NOT confirmed leaks — most are correct cognates / kept jargon /\n" +
  "proper nouns / format strings. Triage each by hand (or per-language) before changing anything.",
);
if (OUT) console.log(`Per-locale TSVs written to ${OUT}`);
