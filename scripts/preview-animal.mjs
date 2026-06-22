/**
 * ============================================================
 * PREVIEW ANIMAL  (render a contact sheet of poses)
 * ============================================================
 *
 * Loads the animal-svg framework + a generated animals/<id>.js into real
 * Chromium and screenshots the animal across every pose, into a single contact
 * sheet (harness/out/animals/<id>-contact.png). Used by the intake to attach a
 * preview to the issue/PR, and for authoring (eyeball the look before shipping).
 *
 * The same six poses the framework exposes; battery-state defaults to "good"
 * (drives the eye colour). Run in the pinned Playwright image.
 *
 * Usage: node scripts/preview-animal.mjs <id> [--battery good|mid|warn|low|charging]
 * ============================================================
 */
import { readFileSync, mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..");
const FW_DIR = resolve(REPO, "custom_components/eufy_vacuum/frontend/animal-svg");
const ANIMALS_DIR = resolve(FW_DIR, "animals");
const OUT_DIR = resolve(REPO, "harness/out/animals");

export const PREVIEW_POSES = ["standing", "animating", "curled", "alert", "walking", "warning"];

export async function previewAnimal(id, { poses = PREVIEW_POSES, battery = "good", outDir = OUT_DIR, moduleJs } = {}) {
  const { chromium } = await import("playwright");
  const framework = readFileSync(resolve(FW_DIR, "animal-svg.js"), "utf8");
  const mod = moduleJs ?? readFileSync(resolve(ANIMALS_DIR, `${id}.js`), "utf8");

  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ deviceScaleFactor: 2 });
    const cells = poses
      .map(
        (p) =>
          `<div class="cell"><animal-svg animal="${id}" pose="${p}" battery-state="${battery}" width="200px" height="200px"></animal-svg><span>${p}</span></div>`,
      )
      .join("");
    await page.setContent(
      `<!doctype html><html><head><meta charset="utf8"><style>
        body{margin:0;background:#1a1d22;display:flex;gap:8px;padding:20px;align-items:flex-end;
             font:12px system-ui,sans-serif;color:#9aa0a6}
        .cell{display:flex;flex-direction:column;align-items:center;gap:6px}
      </style></head><body>${cells}</body></html>`,
    );
    await page.addScriptTag({ content: framework });
    await page.addScriptTag({ content: mod });
    // Let the custom elements upgrade + register/re-render, then settle one
    // animation beat so the held-pose frames are stable.
    await page.waitForTimeout(400);

    mkdirSync(outDir, { recursive: true });
    const out = resolve(outDir, `${id}-contact.png`);
    await page.screenshot({ path: out, fullPage: true });
    return out;
  } finally {
    await browser.close();
  }
}

// --- CLI ---------------------------------------------------------------------
if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  const id = process.argv[2];
  const bi = process.argv.indexOf("--battery");
  const battery = bi >= 0 ? process.argv[bi + 1] : "good";
  if (!id) {
    console.error("usage: node scripts/preview-animal.mjs <id> [--battery good|mid|warn|low|charging]");
    process.exit(2);
  }
  const out = await previewAnimal(id, { battery });
  console.log("wrote " + out);
}
