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

/* Each shot: what it proves, in the label.
   `gallery` renders a gallery fixture; `themeEditor` renders the real theme view
   (renderThemeEditor) because the token editor has no gallery entry — it is built
   in-page from the live THEME_TOKEN_REGISTRY, which a fixture cannot track. */
const SHOTS = [
  {
    id: "rooms-portrait",
    gallery: "rooms-active",
    width: 390, height: 900, mobile: true,
    label: "Rooms — portrait (390px). Compact chrome, 44px touch targets, single-column queue.",
  },
  {
    /* viewportShot: the host screenshot is 2216px of stacked records — an honest
       image that reads as a strip rather than as a phone. The point of this shot
       is "here is the new screen on a phone", so shoot the phone. */
    id: "system-portrait",
    gallery: "setup-system",
    width: 390, height: 900, mobile: true, viewportShot: true,
    label: "Setup → System — 390px. Every role, the entity behind it, and HOW it was chosen. "
      + "The table becomes one stacked record per row, each with its own picker.",
  },
  {
    id: "theme-tokens-portrait",
    themeEditor: { subTab: "tokens" },
    width: 390, height: 900, mobile: true, viewportShot: true,
    label: "Theme → Tokens — 390px. The token editor now runs on a phone: the list scrolls in "
      + "its own pane, the preview and draft footer stay put, and the chrome folds to pay for it.",
  },
  /* NO theme-editor landscape shot, deliberately. At 720x344 the preview, group
     chips, opacity hint, draft footer and bottom nav consume the height before a
     single token row is reachable, so the frame shows an empty editor pane. The
     row count is non-zero (the rows exist, below the fold), which is why a
     tokenRows guard passes on an image that argues the opposite of its caption.
     Landscape is a cramped-but-coherent layout and the honest way to show it is
     rooms-landscape below, which has content at that geometry. */
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

const shots = [];

for (const s of SHOTS) {
  /* Re-mount per shot. mountRealThemeEditor mounts the REAL card and takes the
     `evcc-host` id with it, so a synthetic shot that follows one finds no host
     and dies with "Cannot set properties of null". Re-mounting also clears any
     registered locale, so the catalog is (re)loaded per shot rather than cached. */
  await page.setViewportSize({ width: s.width, height: s.height });
  await mountHarness(page);

  if (s.lang) {
    try {
      const nested = JSON.parse(
        readFileSync(join(repo, "custom_components", "eufy_vacuum", "frontend", "locales", `${s.lang}.json`), "utf8"),
      );
      const { flat } = flattenLocale(nested, en);
      await page.evaluate(([l, cat]) => window.__evcc.registerLocale(l, cat), [s.lang, flat]);
    } catch (e) {
      // A hero shot that quietly renders English is worse than a missing one:
      // it misrepresents the release.
      console.error(`✗ ${s.id}: could not load ${s.lang}.json — ${e.message}`);
      process.exitCode = 1;
      continue;
    }
  }

  const opts = {
    width: s.width, mobile: s.mobile, freeze: true,
    lang: s.lang ?? null, font: s.font ?? null,
  };
  /* The theme editor uses the REAL frame, not the synthetic one. The synthetic
     path never builds main.js's shell, so the scrollbox has no height chain and
     the editor renders as an EMPTY pane — a screenshot that argues the opposite
     of its own caption. theme-mobile-layout.spec.mjs uses the real frame for the
     same reason; this is that decision applied to the shots. */
  /* A theme with NO overrides — which is what a user sees the first time they
     open the editor, and it renders in the card's shipped appearance. Passing
     null would use themeLibraryFixture(), whose values are DELIBERATELY UGLY by
     design (it exists to stress layout with the longest plausible values, cycling
     hex/var()/color-mix() by index). Correct for a gate, and it renders a garish
     unthemed shell that misrepresents the product in a release note. */
  const HERO_THEME = [{ id: "default", name: "Default", tokens: {} }];
  const res = s.themeEditor
    ? await page.evaluate(
        ([themes, o]) => window.__evcc.mountRealThemeEditor(themes, o),
        [HERO_THEME, { width: s.width, ...s.themeEditor }],
      )
    : await page.evaluate(
        ([gid, o]) => window.__evcc.renderGallery(gid, o),
        [s.gallery, opts],
      );
  if (!res.ok) { console.error(`✗ ${s.id}: ${res.error}`); process.exitCode = 1; continue; }
  /* GUARD THE SUBJECT, NOT JUST THE RENDER. These shots exist to prove the token
     list is reachable on a phone, so count the ROWS actually drawn — the registry
     size would be non-zero even for a pane showing nothing, which is exactly how
     the first version of these shots passed while capturing an empty editor. */
  if (s.themeEditor) {
    if (res.viewport !== "mobile") {
      console.error(`✗ ${s.id}: card is in "${res.viewport}" viewport, not mobile — wrong chrome for a phone shot`);
      process.exitCode = 1; continue;
    }
    if (!(res.tokenRows > 0)) {
      console.error(`✗ ${s.id}: editor drew ${res.tokenRows} token rows — the shot would argue the opposite of its caption`);
      process.exitCode = 1; continue;
    }
  }

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
