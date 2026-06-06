#!/usr/bin/env node
/**
 * Render every tab and capture per-tab PNGs + a contact sheet.
 *
 *   node harness/shoot.mjs [--bundle <name>] [--width 500] [--freeze]
 *
 * Output: harness/out/<bundle>/<tab>.png  and  _contact-sheet.png
 * A bundle is any flat `--evcc-*` map under harness/bundles/<name>.js.
 */
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";
import { mountHarness, renderTab, VIEW_ORDER } from "./lib/mount-page.mjs";

const here = dirname(fileURLToPath(import.meta.url));

function flagValue(name, fallback) {
  const i = process.argv.indexOf(name);
  if (i === -1) return fallback;
  const v = process.argv[i + 1];
  return v && !v.startsWith("--") ? v : fallback;
}

const bundleName = flagValue("--bundle", "default");
const width = Number(flagValue("--width", "500")) || 500;
const freeze = process.argv.includes("--freeze");

let bundle = {};
const bundlePath = join(here, "bundles", `${bundleName}.mjs`);
if (existsSync(bundlePath)) {
  bundle = (await import(pathToFileURL(bundlePath).href)).default ?? {};
} else {
  console.warn(`bundle "${bundleName}" not found; using baked defaults`);
}

const outDir = join(here, "out", bundleName);
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: 1 });
await mountHarness(page);

const shots = [];
for (const view of VIEW_ORDER) {
  const res = await renderTab(page, view, { bundle, width, freeze });
  if (!res.ok) {
    console.error(`✗ ${view}: ${res.error}`);
    continue;
  }
  const buf = await page.locator("#evcc-host").screenshot();
  writeFileSync(join(outDir, `${view}.png`), buf);
  shots.push({ view, b64: buf.toString("base64") });
  console.log(`✓ ${view}`);
}

// Contact sheet: a grid of the captured PNGs, screenshotted in one page.
const cells = shots
  .map(
    (s) => `
    <figure style="margin:0">
      <figcaption style="font:12px/1.4 system-ui,sans-serif;color:#cbd2da;padding:4px 2px">${s.view}</figcaption>
      <img src="data:image/png;base64,${s.b64}" style="display:block;width:${width}px;border:1px solid #2a2f37">
    </figure>`,
  )
  .join("");
await page.setContent(
  `<body style="margin:0;background:#0b0d10;display:grid;grid-template-columns:repeat(3,${width}px);gap:16px;padding:16px;align-items:start">${cells}</body>`,
  { waitUntil: "domcontentloaded" },
);
writeFileSync(join(outDir, "_contact-sheet.png"), await page.screenshot({ fullPage: true }));
console.log(`contact sheet -> harness/out/${bundleName}/_contact-sheet.png`);

await browser.close();
