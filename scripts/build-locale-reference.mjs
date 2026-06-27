#!/usr/bin/env node
/**
 * Generate the English locale REFERENCE — custom_components/eufy_vacuum/frontend/
 * locales/en.reference.jsonc — from src/i18n/en.js.
 *
 * English is bundled into the card and is NEVER loaded as an external locale
 * (loadDroppedLocales refuses en.json; .jsonc isn't indexed at all). But English
 * is the SOURCE of every translation, and the nested locale JSONs are pure data
 * with no context. This reference restores it: the full nested key structure +
 * the English value + the disambiguating `// context` comment for each string,
 * so a translator (or a drop-in author) can copy it, translate the values, drop
 * the comments, and save as <code>.json. Re-run after editing en.js.
 *
 * Usage: node scripts/build-locale-reference.mjs   (or npm run build:locale-reference)
 */
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";
import { isPluralLeaf } from "../src/i18n/flatten.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..");
const EN_JS = join(REPO, "src", "i18n", "en.js");
const OUT = join(REPO, "custom_components", "eufy_vacuum", "frontend", "locales", "en.reference.jsonc");

// 1. Values straight from the module (authoritative).
const { en } = await import(pathToFileURL(EN_JS).href);

// 2. Context comments: per source line, capture the trailing `,  // comment`.
//    Anchored on the entry's trailing comma so a `//` inside a value can't be
//    mistaken for a comment. Multi-line plural entries simply get no comment.
const comments = {};
for (const line of readFileSync(EN_JS, "utf8").split(/\r?\n/)) {
  const m = line.match(/^\s*"([^"]+)":\s*.+?,\s+\/\/\s(.+?)\s*$/);
  if (m) comments[m[1]] = m[2].trim();
}

// 3. Nest the flat keys by dotted path (values are leaves; plural objects stay atomic).
const isObj = (v) => v != null && typeof v === "object" && !Array.isArray(v);
const isLeaf = (v) => typeof v === "string" || isPluralLeaf(v);
const nested = {};
for (const [key, value] of Object.entries(en)) {
  const path = key.split(".");
  let node = nested;
  for (let i = 0; i < path.length - 1; i++) {
    if (!isObj(node[path[i]]) || isPluralLeaf(node[path[i]])) node[path[i]] = {};
    node = node[path[i]];
  }
  node[path[path.length - 1]] = value;
}

// 4. Emit JSONC with 2-space indent + inline context comments on each leaf.
function emit(node, path, indent) {
  const pad = "  ".repeat(indent);
  const entries = Object.entries(node);
  return entries
    .map(([k, v], i) => {
      const full = [...path, k].join(".");
      const comma = i < entries.length - 1 ? "," : "";
      if (isLeaf(v)) {
        const ctx = comments[full] ? `  // ${comments[full]}` : "";
        return `${pad}${JSON.stringify(k)}: ${JSON.stringify(v)}${comma}${ctx}`;
      }
      return `${pad}${JSON.stringify(k)}: {\n${emit(v, [...path, k], indent + 1)}\n${pad}}${comma}`;
    })
    .join("\n");
}

const HEADER = `// English reference — AUTO-GENERATED from src/i18n/en.js. DO NOT EDIT BY HAND.
//
// The SOURCE for every translation: the full nested key structure, the English
// value, and the disambiguating context (the // comments) for each string.
// English is bundled into the card and is NEVER loaded from here — this file is
// purely the translator's reference + copy-from template.
//
// To translate: copy this file, translate the string values, delete the //
// comments, and save as "<code>.json" (e.g. de.json) — drop it into
// config/eufy_vacuum/locales/ and restart, or contribute it to the repo.
`;

writeFileSync(OUT, `${HEADER}\n{\n${emit(nested, [], 1)}\n}\n`, "utf8");
console.log(
  `wrote en.reference.jsonc — ${Object.keys(en).length} keys, ${Object.keys(comments).length} with context`,
);
