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
// EVCC_GENDOC_OUT lets the staleness gate (scripts/check_generated_docs.py) render
// into a scratch directory and diff, instead of writing over the tracked files and
// restoring them — a check that mutates the tree leaves it dirty when it fails.
const OUT = process.env.EVCC_GENDOC_OUT || join(ROOT, "docs", "dev", "reference");
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
  // SORTED BY REPO-RELATIVE POSIX PATH, and the sort is load-bearing.
  //
  // `readdirSync` returns filesystem order, which is not the same on NTFS as on
  // ext4, and each token's consumer list is built in walk order — so this file was
  // never platform-stable. It regenerated differently on Windows and on Linux with
  // no source change at all, which meant every regeneration by a different person
  // produced spurious churn, and CI could never agree with a local run.
  //
  // Nobody could see it until the staleness gate started comparing the two: it
  // failed on nine consecutive pushes, and the "stale" file was correct every time.
  //
  // Sorting the ABSOLUTE paths would not be enough — `\` (0x5C) and `/` (0x2F) sort
  // differently against `-` and `.`, so the platform would still leak in.
  const files = [
    ...walk(join(ROOT, "src"), [".js"]),
    ...walk(join(ROOT, "custom_components/eufy_vacuum/frontend/animal-svg"), [".js"]),
    ...walk(join(ROOT, "custom_components/eufy_vacuum/themes"), [".py"]),
  ].sort((a, b) => (rel(a) < rel(b) ? -1 : rel(a) > rel(b) ? 1 : 0));
  const catalog = new Map(THEME_TOKEN_REGISTRY.map((t) => [t.key, t]));
  const strip = (s) => s.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "));
  const VARG = /var\(\s*(--evcc-[A-Za-z0-9-]+)\s*[,)]/g;
  const DEFG = /(--evcc-[A-Za-z0-9-]+)\s*:/g;
  const SETG = /setProperty\(\s*["'`](--evcc-[A-Za-z0-9-]+)/g;
  // getComputedStyle(...).getPropertyValue("--evcc-x") is a REAL consumer — JS reads
  // the token and acts on it. Missing this reported --evcc-floor-texture-map-rotate
  // as the one dead token in the catalog when bindings/map.js:837 reads it by name.
  const GETG = /getPropertyValue\(\s*["'`](--evcc-[A-Za-z0-9-]+)\s*["'`]/g;
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
    for (GETG.lastIndex = 0; (m = GETG.exec(text)); ) if (catalog.has(m[1])) push(uses, m[1], { file: r, line: lineAt(text, m.index), prop: "getPropertyValue" });
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
  // --- DYNAMICALLY CONSUMED FAMILIES -------------------------------------------
  // A token with no STATIC var() use is NOT dead if its name is BUILT at runtime —
  // the regex scan above cannot follow `var(--evcc-floor-${seg}-map-scale)`. These
  // are the families that do that, each with the site that constructs the name.
  //
  // Reporting these as "no consumer" is actively dangerous: it reads as a third of
  // the catalog being dead, and a cleanup pass acting on it would delete live
  // theming for every animal, every floor material and the whole room palette.
  // Keep this list in step with the `dynamic` sites counted above.
  const DYN_FAMILIES = [
    {
      name: "animal",
      test: (k) => k.includes("-animal-"),
      site: "`src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`",
    },
    {
      name: "floor-material",
      test: (k) => /^--evcc-floor-(tile|wood|marble|concrete|carpet|granite)/.test(k),
      site: "`src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key",
    },
    {
      name: "room-fill",
      test: (k) => /^--evcc-room-fill-\d+$/.test(k),
      site: "`src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)",
    },
  ];
  const dynFamilyOf = (k) => DYN_FAMILIES.find((f) => f.test(k)) || null;
  const bDyn = unused.filter((k) => dynFamilyOf(k));
  const bDead = unused.filter((k) => !dynFamilyOf(k));

  // --- Token CSS coverage: what % of color-property declarations resolve through a
  // theme token vs a raw literal. Same scope as the check-styles theme-lint guard:
  // src/styles/* (minus the token-definition file) + the standalone cards. `strip`
  // blanks comments so literals-in-comments don't count; the ignore-hatch check reads
  // the RAW line (theme-lint-ignore lives in a comment strip() would have erased). ---
  const COLOR_PROP = /(?<![-\w])(color|background(?:-color)?|border(?:-color)?|fill|stroke|outline(?:-color)?|accent-color|caret-color)\s*:\s*([^;{}]+)/g;
  const COLORLIT = /#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(/;
  const CARD_FILES = new Set(["src/room-card.js", "src/cards/dashboard-card.js", "src/cards/profile-card.js", "src/cards/_shared.js"]);
  const covScope = (r) => (r.startsWith("src/styles/") && r !== "src/styles/foundation.js") || CARD_FILES.has(r);
  let covTok = 0, covHatched = 0, covStray = 0;
  for (const f of files) {
    const r = rel(f);
    if (!covScope(r)) continue;
    const rawLines = readFileSync(f, "utf8").split(/\r?\n/);
    const cText = strip(rawLines.join("\n"));
    let cm; COLOR_PROP.lastIndex = 0;
    while ((cm = COLOR_PROP.exec(cText))) {
      const v = cm[2];
      if (v.includes("var(")) { covTok++; continue; }
      if (!COLORLIT.test(v)) continue;   // a keyword (transparent/none/inherit), not a literal
      const ln = lineAt(cText, cm.index) - 1;
      if ((rawLines[ln] || "").includes("theme-lint-ignore")) covHatched++; else covStray++;
    }
  }
  const covN = covTok + covHatched + covStray;
  const covPct = covN ? (covTok / covN * 100) : 100;
  const covReal = (covTok + covStray) ? (covTok / (covTok + covStray) * 100) : 100;

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
  L.push(`- Catalog **${catalog.size}** · consumer \`var()\` uses **${totalUses}**`);
  L.push(`- **${catalog.size - unused.length}** with a STATIC consumer · **${bDyn.length}** consumed DYNAMICALLY (constructed names, below) · **${bDead.length}** with no consumer at all`);
  L.push(`- \`var()\` → non-catalog tokens **${orphan.size}** · dynamic \`var(--evcc-…\${…})\` sites **${dynamic.length}**`);
  L.push("");
  L.push(`> **A token with no STATIC consumer is not dead.** This tracer is a regex scan and cannot `
    + `follow a \`var()\` whose name is built at runtime, so ${bDyn.length} live tokens would otherwise `
    + `read as rot — and deleting them would break theming for every animal, every floor material and `
    + `the whole room palette. The families that construct their names:`);
  for (const f of DYN_FAMILIES) {
    const n = bDyn.filter((k) => f.test(k)).length;
    if (n) L.push(`> - **${n}** \`${f.name}\` — ${f.site}`);
  }
  if (bDead.length) {
    L.push(`>`);
    L.push(`> The **${bDead.length}** below are genuinely unreferenced and worth a look: ${bDead.map((k) => `\`${k}\``).join(", ")}`);
  }
  L.push(`- **Token CSS coverage ${covPct.toFixed(1)}%** — ${covTok}/${covN} color declarations resolve through a token (${covHatched} deliberate \`theme-lint-ignore\`, **${covStray} stray**); **${covReal.toFixed(1)}%** of colors that should be themed. Scope: \`src/styles/*\` (minus token defs) + the standalone cards; guarded by \`scripts/check-styles.mjs\`.`);
  L.push("");
  L.push("---");
  L.push("");
  for (const g of THEME_GROUPS) {
    if (collapse.has(g)) continue;
    const tokens = THEME_GROUP_MAP[g] || [];
    const live = tokens.filter((t) => uses.has(t.key)).length;
    // "0/7 consumed" reads as rot on a family whose names are built at runtime.
    // Split the count so a dynamic family can never be mistaken for a dead one.
    const dyn = tokens.filter((t) => !uses.has(t.key) && dynFamilyOf(t.key)).length;
    const dead = tokens.length - live - dyn;
    const parts = [`${live} static`];
    if (dyn) parts.push(`${dyn} dynamic`);
    if (dead) parts.push(`**${dead} NO CONSUMER**`);
    L.push(`## ${g}  ·  ${parts.join(" + ")} / ${tokens.length}`);
    if (g === animalSub[0]) L.push("\n*(template — Dog/Raccoon/Parrot/Snake mirror it; consumed dynamically in animal-svg/)*");
    L.push("");
    for (const t of tokens) {
      const u = uses.get(t.key) || [];
      const d = (defaults.get(t.key) || []).join(", ") || "—";
      const sp = setp.get(t.key) ? ` · apply ${setp.get(t.key).join(", ")}` : "";
      L.push(`**\`${t.key}\`** — ${t.label} · default ${d}${sp}`);
      if (u.length === 0) {
        const fam = dynFamilyOf(t.key);
        L.push(fam
          ? `- _no STATIC consumer — consumed dynamically (${fam.name}): ${fam.site}_`
          : "- _NO CONSUMER — not referenced anywhere; genuinely worth checking_");
      }
      else for (const s of u) L.push(`- ${s.file}:${s.line}${s.prop ? ` (${s.prop})` : ""}`);
      L.push("");
    }
  }
  L.push("---\n");
  L.push(`## Tokens with no STATIC consumer  ·  ${unused.length}`);
  L.push(`\n**${bDyn.length} of these are consumed DYNAMICALLY and are not dead** — this tracer is a `
    + `regex scan and cannot follow a \`var()\` whose name is built at runtime. Only the final `
    + `section is a concern.\n`);
  for (const f of DYN_FAMILIES) {
    const ks = bDyn.filter((k) => f.test(k));
    if (!ks.length) continue;
    L.push(`### Consumed dynamically — ${f.name}  ·  ${ks.length}`);
    L.push(`\n${f.site}. Working as intended.\n`);
    L.push(ks.map((k) => "`" + k + "`").join(", "));
    L.push("");
  }
  L.push(`### No consumer anywhere  ·  ${bDead.length}`);
  L.push("\nSeeded + exposed in the editor but nothing reads them — no-op editor knobs (wire them up or drop them). THIS is the list a cleanup pass should act on, not the count above.\n");
  if (bDead.length) {
    const byG = {};
    for (const k of bDead) (byG[catalog.get(k).group] ??= []).push(k);
    for (const [g, ks] of Object.entries(byG)) L.push(`- **${g}** (${ks.length}): ${ks.map((k) => "`" + k + "`").join(", ")}`);
  } else L.push("None — every catalog token is consumed, statically or dynamically.");
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
  console.log(`wrote docs/dev/reference/THEME_TOKEN_MAP.md (${THEME_TOKEN_REGISTRY.length} tokens) + THEME_TOKEN_USAGE.md (${totalUses} uses, ${bDead.length} dead, ${orphan.size} orphan, ${covPct.toFixed(1)}% CSS coverage, ${covStray} stray)`);
}
