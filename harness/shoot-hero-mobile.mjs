#!/usr/bin/env node
/**
 * HERO SHOTS — the mobile optimization pass.
 *
 *   node harness/shoot-hero-mobile.mjs [--out <dir>] [--dry-run]
 *
 * A curated set for release notes, not a gate and not a baseline. Each shot
 * exists to show one thing the pass delivered, and the labels say what that is
 * — so the contact sheet reads as an argument rather than as a pile of
 * screenshots.
 *
 * WHY THESE GEOMETRIES. Each one exposed a different class of bug during the
 * pass, which is the only reason it earns a slot:
 *   390x844  portrait — where the token editor had ZERO rows on screen
 *   720x344  landscape — where the card rendered the DESKTOP shell with 390px
 *            of height, and where the editor was 26px tall
 *   320x700  narrow — where the metrics tables needed a sideways scroll
 *
 * Locale/font choices come from harness/measure-locale-width.mjs, which ranks
 * by RENDERED WIDTH in the target font rather than character count: ru is the
 * widest single string and a hostile script, zh-Hans is the worst compressor.
 *
 * Output: <out>/mobile-<id>.png plus harness/out/hero-mobile/_contact-sheet.png
 */
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { mountHarness } from "./lib/mount-page.mjs";
import { en } from "../src/i18n/en.js";
import { flattenLocale } from "../src/i18n/flatten.js";

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, "..");
const flagValue = (n, d) => { const i = process.argv.indexOf(n); return i === -1 ? d : (process.argv[i + 1] || d); };
const dryRun = process.argv.includes("--dry-run");
const heroDir = flagValue("--out", join(repo, "docs", "screenshots"));
const reviewDir = join(here, "out", "hero-mobile");

/* Each shot: what it proves, in the label. */
const SHOTS = [
  {
    id: "rooms-portrait",
    gallery: "rooms-active",
    width: 390, height: 900, mobile: true,
    label: "Rooms — portrait (390px). Compact chrome, 44px touch targets, single-column queue.",
  },
  {
    id: "rooms-landscape",
    gallery: "rooms-active",
    width: 720, height: 344, mobile: true, viewportShot: true,
    label: "Rooms — landscape (720x344). Narrow-OR-SHORT detection: landscape is SHORT, not wide.",
  },
  {
    id: "metrics-narrow",
    gallery: "metrics-overview",
    width: 320, height: 900, mobile: true,
    label: "Metrics — 320px. Tables stack into label/value blocks; no sideways scroll at any width.",
  },
  {
    id: "rooms-opendyslexic",
    gallery: "rooms-opendyslexic",
    width: 390, height: 900, mobile: true, font: "opendyslexic",
    label: "OpenDyslexic — ~66% wider glyphs than Arial, still contained.",
  },
  {
    id: "rooms-russian",
    gallery: "rooms-active",
    width: 390, height: 900, mobile: true, lang: "ru", font: "opendyslexic",
    label: "Russian + OpenDyslexic — the widest single string in any pack, hostile script, accessible face.",
  },
  {
    id: "rooms-chinese",
    gallery: "rooms-active",
    width: 390, height: 900, mobile: true, lang: "zh-Hans",
    label: "Simplified Chinese — the opposite stress: 0.50x English width, layouts that must not collapse.",
  },
];

mkdirSync(reviewDir, { recursive: true });
if (!dryRun) mkdirSync(heroDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage();
await mountHarness(page);

const loaded = new Set();
const shots = [];

for (const s of SHOTS) {
  await page.setViewportSize({ width: s.width, height: s.height });

  if (s.lang && !loaded.has(s.lang)) {
    try {
      const nested = JSON.parse(
        readFileSync(join(repo, "custom_components", "eufy_vacuum", "frontend", "locales", `${s.lang}.json`), "utf8"),
      );
      const { flat } = flattenLocale(nested, en);
      await page.evaluate(([l, cat]) => window.__evcc.registerLocale(l, cat), [s.lang, flat]);
      loaded.add(s.lang);
    } catch (e) {
      // A hero shot that quietly renders English is worse than a missing one:
      // it misrepresents the release.
      console.error(`✗ ${s.id}: could not load ${s.lang}.json — ${e.message}`);
      process.exitCode = 1;
      continue;
    }
  }

  const res = await page.evaluate(
    ([gid, opts]) => window.__evcc.renderGallery(gid, opts),
    [s.gallery, { width: s.width, mobile: s.mobile, freeze: true, lang: s.lang ?? null, font: s.font ?? null }],
  );
  if (!res.ok) { console.error(`✗ ${s.id}: ${res.error}`); process.exitCode = 1; continue; }

  /* A landscape shot has to LOOK landscape. Screenshotting the host element
     captures the card's full CONTENT height — a tall strip that argues the
     opposite of its own caption. Where the viewport SHAPE is the point, shoot
     the viewport. */
  const buf = s.viewportShot
    ? await page.screenshot()
    : await page.locator("#evcc-host").screenshot();
  const file = `mobile-${s.id}`;
  if (!dryRun) writeFileSync(join(heroDir, `${file}.png`), buf);
  writeFileSync(join(reviewDir, `${file}.png`), buf);
  shots.push({ file, label: s.label, b64: buf.toString("base64") });
  console.log(`✓ ${s.id.padEnd(20)} ${s.width}x${s.height}${s.lang ? "  " + s.lang : ""}${s.font ? "  " + s.font : ""}`);
}

/* Contact sheet — the set read as one argument. */
const cells = shots
  .map(
    (s) => `<figure style="margin:0">
      <img src="data:image/png;base64,${s.b64}" style="display:block;width:320px;border:1px solid #2a2f37">
      <figcaption style="font:12px/1.45 system-ui,sans-serif;color:#cbd2da;padding:6px 2px;max-width:320px">${s.label}</figcaption>
    </figure>`,
  )
  .join("");
await page.setViewportSize({ width: 1100, height: 900 });
await page.setContent(
  `<body style="margin:0;background:#0b0d10;display:grid;grid-template-columns:repeat(3,340px);gap:20px;padding:20px;align-items:start">${cells}</body>`,
);
writeFileSync(join(reviewDir, "_contact-sheet.png"), await page.screenshot({ fullPage: true }));
console.log(`\ncontact sheet -> harness/out/hero-mobile/_contact-sheet.png`);
if (!dryRun) console.log(`hero shots    -> ${heroDir}`);

await browser.close();
