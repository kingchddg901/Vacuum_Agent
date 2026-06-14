#!/usr/bin/env node
/**
 * Screenshot the card's THEME PICKER (Themes tab) with a faithful, real-state
 * fixture — the facet filter bar, search, Browse-gallery link, and per-card tag
 * chips. The harness stub null-object can't exercise the filter, so this uses
 * window.__evcc.renderThemePresets (real VacuumCardState seeded with a library).
 *
 *   node harness/build.mjs && node harness/shoot-theme-picker.mjs
 *   -> harness/out/theme-picker/*.png
 *
 * Library = the bundled core themes + a few generated ones (from gallery/themes/),
 * so the Source facet shows; the host is themed with Core Slate.
 */
import { chromium } from "@playwright/test";
import { readFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { mountHarness } from "./lib/mount-page.mjs";

const repo = join(dirname(fileURLToPath(import.meta.url)), "..");
const THEMES = join(repo, "gallery", "themes");
const OUT = join(repo, "harness", "out", "theme-picker");
mkdirSync(OUT, { recursive: true });

const load = (slug) => JSON.parse(readFileSync(join(THEMES, `${slug}.json`), "utf8")).theme;
const themes = [
  "core-slate", "forest-night", "soft-carbon", "warm-light", "high-contrast", "colorblind-safe", "signal",
  "jewel-spiral", "nightfall-coast", "aurora-duet", "orange-aurora", "voltage", "green-airglow",
].map(load);

// Seed one theme with free-text vibe tags so the editor shot has chips to show.
const tagged = themes.find((t) => t.id === "theme_jewel_spiral");
if (tagged) tagged.tags = ["aurora", "cosmic"];

const slate = load("core-slate");
const bundle = { ...(slate.colors || {}), ...(slate.tokens || {}) };

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 820, height: 1300 }, deviceScaleFactor: 2 });
await mountHarness(page);

const draw = (opts = {}) =>
  page.evaluate(([t, o]) => window.__evcc.renderThemePresets(t, o), [
    themes,
    { bundle, activeThemeId: "theme_core_slate", height: 560, ...opts },
  ]);

const shots = [
  { name: "all", opts: {} }, // collapsed filters + scrollable grid (the default)
  { name: "filters-open", opts: { filtersOpen: true } },
  { name: "dark-purple", opts: { filtersOpen: true, facets: { accent: ["purple"], mode: ["dark"] } } },
  { name: "colorblind-safe", opts: { filtersOpen: true, facets: { a11y: ["colorblind-safe"] } } },
  { name: "search-aurora", opts: { search: "aurora" } },
  { name: "tag-editor", opts: { editId: "theme_jewel_spiral" } },
];

for (const s of shots) {
  const res = await draw(s.opts);
  if (!res.ok) {
    console.error(`FAILED ${s.name}: ${res.error}\n${res.stack || ""}`);
    await browser.close();
    process.exit(1);
  }
  await page.screenshot({ path: join(OUT, `${s.name}.png`), fullPage: true });
  console.log(`${s.name}: ${res.shown.length} theme(s) -> harness/out/theme-picker/${s.name}.png`);
}

await browser.close();
