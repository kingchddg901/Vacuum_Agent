#!/usr/bin/env node
/**
 * Shoot the three standalone Lovelace cards — the README hero shots.
 *
 *   node harness/shoot-cards.mjs [--bundle <name>] [--scale 2] [--out <dir>]
 *
 * Output: docs/screenshots/card-<id>.png   (committed hero shots)
 *         harness/out/cards/<id>.png       (same frames, for eyeballing)
 *         harness/out/cards/_contact-sheet.png
 *
 * The cards are bundled FROM src/ by harness/build.mjs, never read from
 * custom_components/eufy_vacuum/frontend/ — that bundle only changes on
 * `npm run build:deploy`, so shooting it would picture the last deploy while
 * every check stayed green.
 *
 * Determinism: the clock is frozen and animations/transitions are zeroed
 * (--freeze is the default here, unlike the tab shooters), so re-running with
 * nothing changed reproduces the same bytes.
 *
 * A card that fails to mount renders as a small empty box, which passes any
 * check that only asserts a file exists. So each shot is gated on what the live
 * shadow tree actually contains (chips / rooms / manifest steps / height) BEFORE
 * anything is written, and the run exits non-zero if a gate fails.
 */
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";
import { mountHarness, mountCard, cardFixtures } from "./lib/mount-page.mjs";

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
const heroDir = flagValue("--out", join(repo, "docs", "screenshots"));

let bundle = {};
const bundlePath = join(here, "bundles", `${bundleName}.mjs`);
if (existsSync(bundlePath)) bundle = (await import(pathToFileURL(bundlePath).href)).default ?? {};

const reviewDir = join(here, "out", "cards");
mkdirSync(reviewDir, { recursive: true });
mkdirSync(heroDir, { recursive: true });

/**
 * Per-card content floors. Deliberately per-fixture rather than one generic
 * "not empty" rule: the three cards fail EMPTY in three different ways, and a
 * floor low enough to cover all of them would catch none of them.
 *   room      - six chip rows are the card; zero chips means the adapter option
 *               lists never reached it (the one fixture mistake that renders a
 *               plausible-looking but useless card).
 *   dashboard - every room row plus the expanded row's chips.
 *   profile   - the manifest is the card; five steps is the fixture's routine.
 */
const GATES = {
  room: { chips: 13, activeChips: 6, rooms: 0, steps: 0, height: 300 },
  dashboard: { chips: 13, activeChips: 6, rooms: 6, steps: 0, height: 400 },
  profile: { chips: 0, activeChips: 0, rooms: 0, steps: 5, height: 200 },
};

function checkGate(res) {
  const gate = GATES[res.id];
  const fails = [];
  if (!res.ok) fails.push(`did not mount: ${res.error ?? "unknown"}`);
  if (!gate) return fails;
  for (const [key, min] of Object.entries(gate)) {
    if (min && (res[key] ?? 0) < min) fails.push(`${key}=${res[key] ?? 0}, expected >= ${min}`);
  }
  // Rendering artefacts that look fine in a thumbnail and are wrong in a hero.
  for (const bad of ["undefined", "NaN", "[object Object]"]) {
    if (String(res.text ?? "").includes(bad)) fails.push(`rendered "${bad}" in its text`);
  }
  return fails;
}

const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: scale });
await mountHarness(page);
// The cards carry their own dark surfaces with literal fallbacks; emulate dark
// so anything that consults the media query agrees with them.
await page.emulateMedia({ colorScheme: "dark" });

const fixtures = await cardFixtures(page);
const shots = [];
const failures = [];

for (const fixture of fixtures) {
  const res = await mountCard(page, fixture.id, { bundle, freeze: true });
  const fails = checkGate(res);
  if (fails.length) {
    failures.push(`${fixture.id}: ${fails.join("; ")}`);
    console.error(`✗ ${fixture.id} — ${fails.join("; ")}`);
    if (res.stack) console.error(res.stack);
    continue;
  }

  // omitBackground: the card's rounded corners would otherwise carry the harness
  // page colour into a README that has its own. The card's own surface is opaque,
  // so only the corners come out transparent.
  const buf = await page.locator(fixture.element)
    .screenshot({ animations: "disabled", omitBackground: true });
  writeFileSync(join(heroDir, `${fixture.file}.png`), buf);
  writeFileSync(join(reviewDir, `${fixture.id}.png`), buf);
  shots.push({ ...fixture, b64: buf.toString("base64") });
  console.log(
    `✓ ${fixture.id.padEnd(9)} -> ${fixture.file}.png  ` +
    `(${fixture.width}px @${scale}x · chips ${res.chips} · rooms ${res.rooms} · steps ${res.steps})`,
  );
}

if (shots.length) {
  const cells = shots
    .map(
      (s) => `
    <figure style="margin:0">
      <figcaption style="font:12px/1.4 system-ui,sans-serif;color:#cbd2da;padding:4px 2px">${s.label}</figcaption>
      <img src="data:image/png;base64,${s.b64}" style="display:block;width:${s.width}px;border:1px solid #2a2f37">
    </figure>`,
    )
    .join("");
  await page.setContent(
    `<body style="margin:0;background:#0b0d10;display:flex;align-items:flex-start;gap:18px;padding:18px">${cells}</body>`,
    { waitUntil: "domcontentloaded" },
  );
  writeFileSync(join(reviewDir, "_contact-sheet.png"), await page.screenshot({ fullPage: true }));
  console.log("contact sheet -> harness/out/cards/_contact-sheet.png");
}

await browser.close();

if (failures.length) {
  console.error(`\n${failures.length} card(s) did not render enough to be worth shooting.`);
  process.exit(1);
}
