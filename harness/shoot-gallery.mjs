#!/usr/bin/env node
/**
 * Render every all-states gallery entry and capture PNGs + a contact
 * sheet. Entries with a `clip` selector are cropped to that element
 * (e.g. the status-dot strip captures just the header).
 *
 *   node harness/shoot-gallery.mjs [--bundle <name>] [--freeze]
 *
 * Output: harness/out/gallery/<id>.png  and  _contact-sheet.png
 */
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";
import { mountHarness } from "./lib/mount-page.mjs";

const here = dirname(fileURLToPath(import.meta.url));

function flagValue(name, fallback) {
  const i = process.argv.indexOf(name);
  if (i === -1) return fallback;
  const v = process.argv[i + 1];
  return v && !v.startsWith("--") ? v : fallback;
}

const bundleName = flagValue("--bundle", "default");
const freeze = process.argv.includes("--freeze");
const width = Number(flagValue("--width", "520")) || 520;

let bundle = {};
const bundlePath = join(here, "bundles", `${bundleName}.mjs`);
if (existsSync(bundlePath)) bundle = (await import(pathToFileURL(bundlePath).href)).default ?? {};

const outDir = join(here, "out", "gallery");
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: 2 });
await mountHarness(page);

const entries = await page.evaluate(() => window.__evcc.gallery);
const shots = [];

for (const entry of entries) {
  // Modal fixtures mount their own host; headless defaults to light, flipping
  // the modal's light-hardening on while the card stays dark. Emulate dark for
  // modal shots so the modal matches the card; leave the rest at the default.
  await page.emulateMedia({ colorScheme: entry.modal ? "dark" : "light" });
  const res = await page.evaluate(
    ([id, b, w]) => window.__evcc.renderGallery(id, { bundle: b, width: w }),
    [entry.id, bundle, width],
  );
  if (!res.ok) {
    console.error(`✗ ${entry.id}: ${res.error}`);
    continue;
  }
  // Playwright's CSS engine pierces open shadow roots, so a clip
  // selector inside the card's shadow DOM resolves directly.
  const target = res.clip ? page.locator(res.clip).first() : page.locator("#evcc-host");
  const buf = await target.screenshot();
  writeFileSync(join(outDir, `${entry.id}.png`), buf);
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
writeFileSync(join(outDir, "_contact-sheet.png"), await page.screenshot({ fullPage: true }));
console.log(`contact sheet -> harness/out/gallery/_contact-sheet.png`);

await browser.close();
