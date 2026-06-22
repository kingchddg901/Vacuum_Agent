#!/usr/bin/env node
/**
 * Render the /animals gallery: for every gallery/animals/*.json, load the REAL
 * animal-svg framework + the generated module and screenshot the animal across
 * all six poses, then write a per-animal detail page + the faceted index.
 *
 *   node harness/preview-animals.mjs
 *
 * Output: harness/out/preview/animals/  — that lands under /animals on the Pages
 * site (the theme gallery owns / ; this is the animal counterpart, folded into
 * the same gallery job in theme-intake.yml).
 *
 * Animals are DATA here: the descriptor was already validated + sanitised at
 * intake, and the module is the codegen of it, so rendering is just the real
 * framework drawing the same companion the card shows.
 */
import { chromium } from "@playwright/test";
import { readFileSync, writeFileSync, mkdirSync, readdirSync, existsSync, copyFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, basename } from "node:path";
import { writeAnimalPage, writeAnimalIndex, filterTokensFor } from "./lib/animal-gallery-html.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, "..");
const FW_DIR = join(repo, "custom_components", "eufy_vacuum", "frontend", "animal-svg");
const ANIMALS_DIR = join(FW_DIR, "animals");
const GALLERY_DIR = join(repo, "gallery", "animals");
const OUT = join(repo, "harness", "out", "preview", "animals");
const POSES = ["standing", "animating", "curled", "alert", "walking", "warning"];

const files = existsSync(GALLERY_DIR)
  ? readdirSync(GALLERY_DIR).filter((f) => f.endsWith(".json")).map((f) => join(GALLERY_DIR, f))
  : [];
if (!files.length) {
  console.log("no animals to preview (looked in gallery/animals/)");
  process.exit(0);
}

const framework = readFileSync(join(FW_DIR, "animal-svg.js"), "utf8");
const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: 2 });
const entries = [];

for (const file of files) {
  const id = basename(file).replace(/\.json$/, "");

  let envelope;
  try {
    envelope = JSON.parse(readFileSync(file, "utf8"));
  } catch (e) {
    console.error(`skip ${id}: invalid JSON (${e.message})`);
    continue;
  }
  const animal = envelope.animal || envelope;
  const jsPath = join(ANIMALS_DIR, `${id}.js`);
  if (!existsSync(jsPath)) {
    console.error(`skip ${id}: no generated module animals/${id}.js`);
    continue;
  }
  const moduleJs = readFileSync(jsPath, "utf8");

  const outDir = join(OUT, id);
  mkdirSync(outDir, { recursive: true });

  const cells = POSES.map(
    (p) => `<div class="cell"><animal-svg animal="${id}" pose="${p}" battery-state="good" width="200px" height="200px"></animal-svg></div>`,
  ).join("");
  await page.setContent(`<!doctype html><body style="margin:0;background:#0b0d10">${cells}</body>`, {
    waitUntil: "domcontentloaded",
  });
  await page.addScriptTag({ content: framework });
  await page.addScriptTag({ content: moduleJs });
  await page.waitForTimeout(400);

  const poses = [];
  const els = page.locator("animal-svg");
  for (let i = 0; i < POSES.length; i++) {
    const buf = await els.nth(i).screenshot();
    const f = `pose-${POSES[i]}.png`;
    writeFileSync(join(outDir, f), buf);
    poses.push({ pose: POSES[i], file: f });
    if (POSES[i] === "standing") writeFileSync(join(outDir, "thumb.png"), buf);
  }

  const download = `${id}.json`;
  copyFileSync(file, join(outDir, download));
  writeAnimalPage(outDir, animal, poses, { download });
  entries.push({ id, animal, filterTokens: filterTokensFor(animal), download });
  console.log(`✓ ${id} (${animal.name}) -> harness/out/preview/animals/${id}/`);
}

if (entries.length) {
  // Companions first, Rainbow Bridge (memorial) grouped at the end; alpha within.
  entries.sort(
    (a, b) =>
      Number(!!a.animal.memorial) - Number(!!b.animal.memorial) ||
      String(a.animal.name).localeCompare(String(b.animal.name)),
  );
  writeAnimalIndex(entries, OUT);
  console.log(`index -> harness/out/preview/animals/index.html (${entries.length} animal${entries.length === 1 ? "" : "s"})`);
}

await browser.close();
