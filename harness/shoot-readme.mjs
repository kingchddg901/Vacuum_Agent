#!/usr/bin/env node
/**
 * Shoot the committed README panel screenshots — one full-tab capture per view.
 *
 *   node harness/shoot-readme.mjs [--bundle <name>] [--scale 2] [--width 920] [--out <dir>]
 *                                 [--only <id,id>] [--dry-run]
 *
 * Output: docs/screenshots/<file>.png    (the committed shots the README embeds)
 *         harness/out/readme/<file>.png  (the same frames, for eyeballing)
 *         harness/out/readme/_contact-sheet.png
 *
 * Everything renders FROM src/, through harness/build.mjs, exactly as the other
 * shooters do. Pointing this at custom_components/eufy_vacuum/frontend/ would
 * picture whatever was last deployed (that bundle only changes on
 * `npm run build:deploy`) while every check stayed green.
 *
 * Determinism: the clock is frozen and animations/transitions are zeroed for every
 * shot, and no fixture derives from wall-clock or randomness — so re-running with
 * nothing changed reproduces the same bytes.
 *
 * THE GATE. A tab that rendered its EMPTY state screenshots perfectly: right
 * chrome, right active tab, right theme, nothing in it. That is the failure mode
 * this file exists to prevent, so nothing is written until the shot's fixture-
 * declared floor is met against the LIVE shadow tree — element counts for the
 * selectors that ARE the view, substrings that must be present, a height floor,
 * zero `.evcc-empty` nodes, the expected tab actually marked active, and no
 * `undefined` / `NaN` / `[object Object]` in the rendered text. A shot that misses
 * is reported and skipped, its previous PNG left untouched, and the run exits
 * non-zero. See harness/fixtures/readme-shots.js for the per-shot floors.
 */
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync, readFileSync, existsSync, readdirSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";
import { mountHarness } from "./lib/mount-page.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, "..");

function flagValue(name, fallback) {
  const i = process.argv.indexOf(name);
  if (i === -1) return fallback;
  const v = process.argv[i + 1];
  return v && !v.startsWith("--") ? v : fallback;
}

const bundleName = flagValue("--bundle", "default");
const scale = Number(flagValue("--scale", "2")) || 2;
// 920 CSS px @2x = 1840 px wide, matching the widest of the shots this replaces
// (base-station / learning-review / themes were all ~1840) while rendering at a
// desktop panel width the layout is actually designed around.
const width = Number(flagValue("--width", "920")) || 920;
const heroDir = flagValue("--out", join(repo, "docs", "screenshots"));
const only = flagValue("--only", "");
const dryRun = process.argv.includes("--dry-run");

let bundle = {};
const bundlePath = join(here, "bundles", `${bundleName}.mjs`);
if (existsSync(bundlePath)) bundle = (await import(pathToFileURL(bundlePath).href)).default ?? {};

const reviewDir = join(here, "out", "readme");
mkdirSync(reviewDir, { recursive: true });
if (!dryRun) mkdirSync(heroDir, { recursive: true });

/* -------------------------------------------------------------------------
   The theme library, for the three Themes shots.
   The Themes tab is a view OF the shipped theme collection, so it is seeded
   with the real gallery/themes exports rather than invented ones — a made-up
   library would picture presets no install has.
   ------------------------------------------------------------------------- */
const THEME_DIR = join(repo, "gallery", "themes");
const themes = readdirSync(THEME_DIR)
  .filter((f) => f.endsWith(".json"))
  .sort()
  .map((f) => JSON.parse(readFileSync(join(THEME_DIR, f), "utf8")).theme)
  .filter((t) => t && t.id);
const activeThemeId = themes.find((t) => t.id === "theme_core_slate")?.id ?? themes[0]?.id ?? null;

/* -------------------------------------------------------------------------
   Gate evaluation. Fixture declares the floor; this decides pass/fail.
   ------------------------------------------------------------------------- */
const RENDER_ARTEFACTS = ["undefined", "NaN", "[object Object]"];

function checkGate(res) {
  const fails = [];
  if (!res.ok) {
    fails.push(`did not render: ${res.error ?? "unknown"}`);
    return fails;
  }
  const gate = res.gate ?? {};
  const m = res.metrics ?? {};

  for (const [selector, min] of Object.entries(gate.selectors ?? {})) {
    const got = m.counts?.[selector] ?? 0;
    if (got < 0) fails.push(`gate selector is not valid CSS: ${selector}`);
    else if (got < min) fails.push(`${selector} × ${got}, expected >= ${min}`);
  }
  for (const needle of gate.text ?? []) {
    if (!String(m.text ?? "").includes(needle)) fails.push(`text is missing "${needle}"`);
  }
  // Not every empty branch renders `.evcc-empty`. The battery tab's per-bucket
  // groups, for instance, print "… — no single-bucket jobs yet" as ordinary table
  // rows, so a fixture that named the attributes wrong produced a table that looked
  // populated and said nothing. `notText` pins those by their own wording.
  for (const needle of gate.notText ?? []) {
    if (String(m.text ?? "").includes(needle)) fails.push(`text contains "${needle}"`);
  }
  if (gate.minHeight && (m.height ?? 0) < gate.minHeight) {
    fails.push(`rendered ${m.height}px tall, expected >= ${gate.minHeight}`);
  }
  // An empty-state node inside the capture means a branch fell back to "no data
  // yet" — the exact render that looks like a working screenshot.
  if (m.emptyStates > 0) fails.push(`${m.emptyStates} empty-state block(s) in the capture`);
  // CLIPPING. <ha-card> is overflow:hidden, so content the shell cannot fit is
  // cropped out of the capture with no other symptom. Bounded shots (the Themes
  // sub-tabs) own a scroll container, so only their horizontal axis is checked.
  if (m.overflowX > 2) fails.push(`shell overflows horizontally by ${m.overflowX}px`);
  if (!res.bounded && m.overflowY > 2) fails.push(`shell is clipped: ${m.overflowY}px below the fold`);
  // Full-tab shots must have the tab they claim marked active; a clipped modal
  // shot has no nav in scope, so it is exempt.
  if (!res.clip && m.activeTab !== res.view && res.view !== "map_config") {
    fails.push(`active tab is "${m.activeTab}", expected "${res.view}"`);
  }
  for (const bad of RENDER_ARTEFACTS) {
    if (String(m.text ?? "").includes(bad)) fails.push(`rendered "${bad}" in its text`);
  }
  return fails;
}

/* ------------------------------------------------------------------------- */

const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: scale });
await mountHarness(page);
// The panel's surfaces are dark with literal fallbacks; emulate dark so anything
// that consults the media query agrees with them (same reason shoot-cards does).
await page.emulateMedia({ colorScheme: "dark" });

const shots = await page.evaluate(() => window.__evcc.readmeShots);
const wanted = only ? new Set(only.split(",").map((s) => s.trim())) : null;

const written = [];
const failures = [];

for (const shot of shots) {
  if (wanted && !wanted.has(shot.id)) continue;

  const res = await page.evaluate(
    ([id, opts]) => window.__evcc.renderReadmeShot(id, opts),
    [shot.id, { bundle, width, data: shot.needsThemes ? { themes, activeThemeId } : {} }],
  );

  const fails = checkGate(res);
  if (fails.length) {
    failures.push(`${shot.id}: ${fails.join("; ")}`);
    console.error(`✗ ${shot.id} — ${fails.join("; ")}`);
    if (res.stack) console.error(res.stack);
    continue;
  }

  // Wait for the backdrop / any decoded image before capturing, so the map shots
  // can't race the plan art and land a blank container.
  await page.evaluate(() => document.fonts?.ready);
  await page.waitForFunction(() => {
    const root = document.getElementById("evcc-host")?.shadowRoot;
    return [...(root?.querySelectorAll("img") ?? [])].every((img) => img.complete);
  }, null, { timeout: 5000 });

  const target = page.locator(res.clip ?? "#evcc-host").first();
  const buf = await target.screenshot({ animations: "disabled" });

  if (!dryRun) writeFileSync(join(heroDir, `${res.file}.png`), buf);
  writeFileSync(join(reviewDir, `${res.file}.png`), buf);
  written.push({ ...shot, b64: buf.toString("base64"), metrics: res.metrics });
  console.log(
    `✓ ${shot.id.padEnd(22)} -> ${res.file}.png  ` +
    `(${res.metrics.width}×${res.metrics.height} CSS @${scale}x)`,
  );
}

if (written.length) {
  const cells = written
    .map(
      (s) => `
    <figure style="margin:0">
      <figcaption style="font:12px/1.4 system-ui,sans-serif;color:#cbd2da;padding:4px 2px">${s.label}</figcaption>
      <img src="data:image/png;base64,${s.b64}" style="display:block;width:520px;border:1px solid #2a2f37">
    </figure>`,
    )
    .join("");
  await page.setContent(
    `<body style="margin:0;background:#0b0d10;display:grid;grid-template-columns:repeat(3,520px);gap:18px;padding:18px;align-items:start">${cells}</body>`,
    { waitUntil: "domcontentloaded" },
  );
  writeFileSync(join(reviewDir, "_contact-sheet.png"), await page.screenshot({ fullPage: true }));
  console.log("contact sheet -> harness/out/readme/_contact-sheet.png");
}

await browser.close();

if (failures.length) {
  console.error(`\n${failures.length} shot(s) did not render enough to be worth shooting; nothing was written for them.`);
  process.exit(1);
}
