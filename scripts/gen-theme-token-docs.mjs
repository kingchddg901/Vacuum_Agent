#!/usr/bin/env node
/**
 * Generate the Theme Token Reference docs from the LIVE token registry + card CSS.
 *
 * Writes two files into docs/dev/reference/:
 *   - THEME_TOKEN_MAP.md    the catalog: every --evcc-* token by group, with its
 *                           editor label (what it controls), type, and slider range.
 *   - THEME_TOKEN_USAGE.md  the CSS-usage trace: for each token, its default
 *                           declaration and every real consumer var() (file:line +
 *                           CSS property). Multiline-aware (handles var( wrapped
 *                           across lines); scans src/, the animal-svg/ module, and
 *                           the Python preloaded themes. Flags tokens with no
 *                           consumer (dead vs dynamically-consumed) and var() refs
 *                           to non-catalog tokens.
 *
 * Both files are GENERATED — never hand-edit them. Regenerate after adding,
 * removing, or renaming any theme token (this is fast + has no side effects):
 *
 *   node scripts/gen-theme-token-docs.mjs
 *
 * Runs directly on the host (Node) — it imports the live JS registry, so no Docker
 * wrapper (unlike the pytest-bound scripts/update_test_docs.py). Review the diff
 * before committing.
 */
import { THEME_TOKEN_REGISTRY, THEME_GROUPS, THEME_GROUP_MAP }
  from "../src/theme-tokens/index.js";
import { readFileSync, readdirSync, writeFileSync, statSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const OUT = join(ROOT, "docs", "dev", "reference");
mkdirSync(OUT, { recursive: true });

const BANNER =
`<!-- GENERATED FILE — DO NOT EDIT BY HAND.
     Source of truth: src/theme-tokens/ (the editor registry) + the card CSS.
     Regenerate after any token add/remove/rename:  node scripts/gen-theme-token-docs.mjs -->

`;

const animalSub = THEME_GROUPS.filter((g) => /^Animal Companion — /.test(g));
const collapse = new Set(animalSub.slice(1));
const range = (t) => (t.min === undefined && t.max === undefined)
  ? "" : `${t.min ?? ""}–${t.max ?? ""}${t.step !== undefined ? ` step ${t.step}` : ""}`;

/* ===================== THEME_TOKEN_MAP.md ===================== */
{
  const tmpl = animalSub[0];
  const L = [];
  L.push("# Theme Token Map");
  L.push("");
  L.push("> Generated reference — part of the [Theme System](../frontend/theme-system.md) docs. "
    + "Companion: [Theme Token CSS-Usage Trace](THEME_TOKEN_USAGE.md).");
  L.push("");
  L.push(`The themeable control-surface tokens exposed in the theme editor: `
    + `**${THEME_TOKEN_REGISTRY.length} tokens** across **${THEME_GROUPS.length} groups**. Each is a `
    + "`--evcc-*` CSS custom property; **Controls** is the editor label (what it styles); **Type** is the "
    + "input kind; bounded scalars list their slider range.");
  L.push("");
  L.push(`The 5 companion sub-groups share one identical ${(THEME_GROUP_MAP[tmpl] || []).length}-token shape — `
    + `only **${tmpl.replace("Animal Companion — ", "")}** is listed in full; `
    + `${animalSub.slice(1).map((s) => s.replace("Animal Companion — ", "")).join(", ")} repeat it with their own \`-<animal>-\` key segment.`);
  L.push("");
  L.push("---");
  L.push("");
  for (const g of THEME_GROUPS) {
    if (collapse.has(g)) continue;
    const tokens = THEME_GROUP_MAP[g] || [];
    L.push(`## ${g}  ·  ${tokens.length}`);
    if (g === tmpl) L.push("\n*(template — repeats per companion)*");
    L.push("");
    L.push("| Token | Controls | Type | Range |");
    L.push("|---|---|---|---|");
    for (const t of tokens) L.push(`| \`${t.key}\` | ${t.label} | ${t.type} | ${range(t)} |`);
    L.push("");
  }
  writeFileSync(join(OUT, "THEME_TOKEN_MAP.md"), BANNER + L.join("\n") + "\n");
}

/* ===================== THEME_TOKEN_USAGE.md ===================== */
{
  function walk(dir, exts, acc = []) {
    try {
      for (const e of readdirSync(dir)) {
        const p = join(dir, e);
        if (statSync(p).isDirectory()) { if (e !== "__pycache__" && e !== "node_modules") walk(p, exts, acc); }
        else if (exts.some((x) => e.endsWith(x)) && e !== "eufy-vacuum-command-center.js") acc.push(p);
      }
    } catch {}
    return acc;
  }
  const rel = (p) => p.slice(ROOT.length + 1).split("\\").join("/");
  const files = [
    ...walk(join(ROOT, "src"), [".js"]),
    ...walk(join(ROOT, "custom_components/eufy_vacuum/frontend/animal-svg"), [".js"]),
    ...walk(join(ROOT, "custom_components/eufy_vacuum/themes"), [".py"]),
  ];
  const catalog = new Map(THEME_TOKEN_REGISTRY.map((t) => [t.key, t]));
  const strip = (s) => s.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "));
  const VARG = /var\(\s*(--evcc-[A-Za-z0-9-]+)\s*[,)]/g;
  const DEFG = /(--evcc-[A-Za-z0-9-]+)\s*:/g;
  const SETG = /setProperty\(\s*["'`](--evcc-[A-Za-z0-9-]+)/g;
  const DYNG = /var\(\s*--evcc-[A-Za-z0-9-]*\$\{/g;
  const PROPRE = /(--[A-Za-z0-9-]+|[A-Za-z][A-Za-z0-9-]*)\s*:\s*$/;
  const push = (m, k, v) => (m.get(k) ?? m.set(k, []).get(k)).push(v);
  const lineAt = (t, i) => { let n = 1; for (let j = 0; j < i; j++) if (t[j] === "\n") n++; return n; };
  const uses = new Map(), defaults = new Map(), setp = new Map(), orphan = new Map(), dynamic = [];

  for (const f of files) {
    const r = rel(f);
    const text = strip(readFileSync(f, "utf8"));
    let m;
    for (DYNG.lastIndex = 0; (m = DYNG.exec(text)); ) dynamic.push(`${r}:${lineAt(text, m.index)}`);
    for (SETG.lastIndex = 0; (m = SETG.exec(text)); ) if (catalog.has(m[1])) push(setp, m[1], `${r}:${lineAt(text, m.index)}`);
    if (r.endsWith(".js")) {
      for (DEFG.lastIndex = 0; (m = DEFG.exec(text)); ) if (catalog.has(m[1])) push(defaults, m[1], `${r}:${lineAt(text, m.index)}`);
    }
    for (VARG.lastIndex = 0; (m = VARG.exec(text)); ) {
      const tok = m[1];
      const idx = m.index;
      const b = Math.max(text.lastIndexOf(";", idx - 1), text.lastIndexOf("{", idx - 1), text.lastIndexOf("}", idx - 1));
      const prop = (PROPRE.exec(text.slice(b + 1, idx)) || [])[1] || "";
      if (tok === prop) continue;
      const ln = lineAt(text, idx);
      if (catalog.has(tok)) push(uses, tok, { file: r, line: ln, prop });
      else if (!/-$/.test(tok)) push(orphan, tok, `${r}:${ln}`);
    }
  }

  const totalUses = [...uses.values()].reduce((n, a) => n + a.length, 0);
  const unused = [...catalog.keys()].filter((k) => !uses.has(k));
  const isFloorPreset = (k) => /^--evcc-floor-(tile|wood|marble|concrete|carpet|granite)/.test(k);
  const isAnimal = (k) => k.includes("-animal-");
  const bDynamic = unused.filter(isFloorPreset);
  const bAnimal = unused.filter((k) => !isFloorPreset(k) && isAnimal(k));
  const bDead = unused.filter((k) => !isFloorPreset(k) && !isAnimal(k));

  const L = [];
  L.push("# Theme Token CSS-Usage Trace");
  L.push("");
  L.push("> Generated reference — part of the [Theme System](../frontend/theme-system.md) docs. "
    + "Companion: [Theme Token Map](THEME_TOKEN_MAP.md).");
  L.push("");
  L.push("For each catalog token (`--evcc-*`): its **default** declaration, every real **consumer** "
    + "`var()` (CSS property + file:line), and JS `setProperty` apply sites. Multiline-aware (handles "
    + "`var(` wrapped across lines); scans `src/`, the `animal-svg/` module, and the Python preloaded "
    + "themes. The self-referential seed (`--evcc-x: var(--evcc-x, fallback)`) is the default, not a use.");
  L.push("");
  L.push(`- Catalog **${catalog.size}** · consumer \`var()\` uses **${totalUses}** · with a consumer **${catalog.size - unused.length}**, with none **${unused.length}**`);
  L.push(`- \`var()\` → non-catalog tokens **${orphan.size}** · dynamic \`var(--evcc-…\${…})\` sites **${dynamic.length}**`);
  L.push("");
  L.push("---");
  L.push("");
  for (const g of THEME_GROUPS) {
    if (collapse.has(g)) continue;
    const tokens = THEME_GROUP_MAP[g] || [];
    const live = tokens.filter((t) => uses.has(t.key)).length;
    L.push(`## ${g}  ·  ${live}/${tokens.length} consumed`);
    if (g === animalSub[0]) L.push("\n*(template — Dog/Raccoon/Parrot/Snake mirror it; consumed dynamically in animal-svg/)*");
    L.push("");
    for (const t of tokens) {
      const u = uses.get(t.key) || [];
      const d = (defaults.get(t.key) || []).join(", ") || "—";
      const sp = setp.get(t.key) ? ` · apply ${setp.get(t.key).join(", ")}` : "";
      L.push(`**\`${t.key}\`** — ${t.label} · default ${d}${sp}`);
      if (u.length === 0) L.push("- _no consumer — only seeded_");
      else for (const s of u) L.push(`- ${s.file}:${s.line}${s.prop ? ` (${s.prop})` : ""}`);
      L.push("");
    }
  }
  L.push("---\n");
  L.push(`## Tokens with no consumer  ·  ${unused.length}`);
  L.push("\nThree kinds — only the last is a concern:\n");
  L.push(`### Consumed dynamically — floor-texture presets  ·  ${bDynamic.length}`);
  L.push("\nBuilt at runtime as `var(--evcc-floor-${floorType}-…)` in `src/renderers/floor-texture-surface.js`. Working as intended.\n");
  L.push(bDynamic.map((k) => "`" + k + "`").join(", ") || "—");
  L.push("");
  L.push(`### Per-animal palette (consumed dynamically in animal-svg/)  ·  ${bAnimal.length}`);
  L.push("\nThe `--evcc-animal-*` tokens are referenced via dynamic `var()` in the shipped animal-svg module; per-animal `--evcc-animal-<name>-*` feed the active companion. Expected.\n");
  L.push(bAnimal.map((k) => "`" + k + "`").join(", ") || "—");
  L.push("");
  L.push(`### Truly dead — no \`var()\` anywhere  ·  ${bDead.length}`);
  L.push("\nSeeded + exposed in the editor but nothing reads them — no-op editor knobs (wire them up or drop them).\n");
  if (bDead.length) {
    const byG = {};
    for (const k of bDead) (byG[catalog.get(k).group] ??= []).push(k);
    for (const [g, ks] of Object.entries(byG)) L.push(`- **${g}** (${ks.length}): ${ks.map((k) => "`" + k + "`").join(", ")}`);
  } else L.push("None — every non-dynamic catalog token has a consumer.");
  L.push("");
  if (orphan.size) {
    L.push("---\n");
    L.push(`## var() → non-catalog tokens  ·  ${orphan.size}\n`);
    L.push("Used in CSS but not in the editor registry (dynamic fragments or intentional internals like `--evcc-grp`).\n");
    for (const [k, sites] of orphan) L.push(`- \`${k}\` — ${sites.slice(0, 8).join(", ")}${sites.length > 8 ? ` …(+${sites.length - 8})` : ""}`);
    L.push("");
  }
  if (dynamic.length) {
    L.push("---\n");
    L.push(`## dynamic var(--evcc-…\${…}) sites  ·  ${dynamic.length}\n`);
    for (const s of dynamic) L.push(`- ${s}`);
    L.push("");
  }
  writeFileSync(join(OUT, "THEME_TOKEN_USAGE.md"), BANNER + L.join("\n") + "\n");
  console.log(`wrote docs/dev/reference/THEME_TOKEN_MAP.md (${THEME_TOKEN_REGISTRY.length} tokens) + THEME_TOKEN_USAGE.md (${totalUses} uses, ${bDead.length} dead, ${orphan.size} orphan)`);
}
