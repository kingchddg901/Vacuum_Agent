#!/usr/bin/env node
/**
 * Render every all-states gallery entry and capture PNGs + a contact
 * sheet. Entries with a `clip` selector are cropped to that element
 * (e.g. the status-dot strip captures just the header).
 *
 *   node harness/shoot-gallery.mjs [--bundle <name>] [--freeze]
 *                                   [--mobile] [--width N]
 *                                   [--lang de] [--font opendyslexic]
 *
 * LOCALE + FONT are the stress axes. Rank which to shoot with
 * harness/measure-locale-width.mjs — it ranks by RENDERED WIDTH in the target
 * font, which is not the same order as character count and differs per screen.
 *
 * Output: harness/out/gallery/<id>.png  and  _contact-sheet.png
 *         (suffixed .<lang> / .<font> when those flags are used, so a stress
 *          run never overwrites the plain baseline shots)
 */
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync, existsSync, readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";
import { mountHarness } from "./lib/mount-page.mjs";
import { en } from "../src/i18n/en.js";
import { flattenLocale } from "../src/i18n/flatten.js";

const here = dirname(fileURLToPath(import.meta.url));

function flagValue(name, fallback) {
  const i = process.argv.indexOf(name);
  if (i === -1) return fallback;
  const v = process.argv[i + 1];
  return v && !v.startsWith("--") ? v : fallback;
}

const bundleName = flagValue("--bundle", "default");
const freeze = process.argv.includes("--freeze");
/* --mobile renders the MOBILE SHELL, not merely a narrow desktop one. Without
   it, --width 390 gives a desktop shell squeezed into 390px: a wrapped top tab
   strip and no bottom nav — which looks mobile-ish and is not, so the compact
   chrome, the 44px tap floors and the stacked layouts all go unphotographed.
   renderGallery has always accepted this; nothing passed it. */
const mobile = process.argv.includes("--mobile");
const lang = flagValue("--lang", "");
const font = flagValue("--font", "");
const width = Number(flagValue("--width", mobile ? "390" : "520")) || (mobile ? 390 : 520);

let bundle = {};
const bundlePath = join(here, "bundles", `${bundleName}.mjs`);
if (existsSync(bundlePath)) bundle = (await import(pathToFileURL(bundlePath).href)).default ?? {};

const outDir = join(here, "out", "gallery");
const tag = [lang, font].filter(Boolean).join(".");
const named = (base) => (tag ? `${base}.${tag}` : base);
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: 2 });
await mountHarness(page);

/* The bundle ships English only, so a foreign catalog has to be injected the
   way the real card loads one at runtime — same path shoot-locales uses. */
if (lang) {
  try {
    const nested = JSON.parse(
      readFileSync(join(here, "..", "custom_components", "eufy_vacuum", "frontend", "locales", `${lang}.json`), "utf8"),
    );
    const { flat } = flattenLocale(nested, en);
    await page.evaluate(([l, cat]) => window.__evcc.registerLocale(l, cat), [lang, flat]);
    console.log(`locale ${lang} registered (${Object.keys(flat).length} keys)`);
  } catch (e) {
    // Loudly, not silently: a stress run that quietly renders English proves
    // nothing and looks like a pass.
    console.error(`✗ could not load ${lang}.json — ABORTING rather than shooting English: ${e.message}`);
    process.exit(1);
  }
}

const entries = await page.evaluate(() => window.__evcc.gallery);
const shots = [];

for (const entry of entries) {
  // Modal fixtures mount their own host; headless defaults to light, flipping
  // the modal's light-hardening on while the card stays dark. Emulate dark for
  // modal shots so the modal matches the card; leave the rest at the default.
  await page.emulateMedia({ colorScheme: entry.modal ? "dark" : "light" });
  const res = await page.evaluate(
    ([id, b, w, m, l, f]) =>
      window.__evcc.renderGallery(id, { bundle: b, width: w, mobile: m, lang: l || null, font: f || null }),
    [entry.id, bundle, width, mobile, lang, font],
  );
  if (!res.ok) {
    console.error(`✗ ${entry.id}: ${res.error}`);
    continue;
  }
  // Playwright's CSS engine pierces open shadow roots, so a clip
  // selector inside the card's shadow DOM resolves directly.
  const target = res.clip ? page.locator(res.clip).first() : page.locator("#evcc-host");
  const buf = await target.screenshot();
  writeFileSync(join(outDir, `${named(entry.id)}.png`), buf);
  shots.push({ id: entry.id, label: res.label, b64: buf.toString("base64") });
  console.log(`✓ ${entry.id}`);
}

const cells = shots
  .map(
    (s) => `
    <figure style="margin:0">
      <figcaption style="font:12px/1.4 system-ui,sans-serif;color:#cbd2da;padding:4px 2px">${s.label}</figcaption>
      <img src="data:image/png;base64,${s.b64}" style="display:block;width:${width}px;border:1px solid #2a2f37">
    </figure>`,
  )
  .join("");
await page.setContent(
  `<body style="margin:0;background:#0b0d10;display:grid;grid-template-columns:repeat(2,${width + 20}px);gap:18px;padding:18px;align-items:start">${cells}</body>`,
  { waitUntil: "domcontentloaded" },
);
writeFileSync(join(outDir, `${named("_contact-sheet")}.png`), await page.screenshot({ fullPage: true }));
console.log(`contact sheet -> harness/out/gallery/_contact-sheet.png`);

await browser.close();
