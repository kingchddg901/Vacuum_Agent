#!/usr/bin/env node
/**
 * Preview theme EXPORTS (the export/import schema) by running each through the
 * ingest gate and rendering the REAL card with it — the same harness render,
 * recolored by the uploaded theme. Scope drives output:
 *   full theme     -> contact sheet of the all-states galleries
 *   texture-scoped  -> the rooms gallery (where floor textures live)
 *
 *   node harness/preview.mjs [path/to/export.json]   # one export
 *   node harness/preview.mjs                          # scans gallery/themes/*.json
 *
 * Output: harness/out/preview/<name>/  (PNGs + ingest-report.json) plus a
 * self-contained index.html gallery — that directory is what the
 * theme-intake workflow publishes to GitHub Pages.
 *
 * The ingest gate (window.__evcc.ingestTheme) makes this safe on untrusted
 * uploads: malformed/unknown-namespace exports are skipped, every value is
 * clamped, nothing is eval'd.
 */
import { chromium } from "@playwright/test";
import { readFileSync, writeFileSync, mkdirSync, readdirSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, basename } from "node:path";
import { mountHarness, renderTab, VIEW_ORDER } from "./lib/mount-page.mjs";
import { effectiveThemeTags, themeAttribution } from "../src/theme-tags/index.mjs";
import { writeThemePage, writeIndex } from "./lib/gallery-html.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, "..");
const OUT = join(repo, "harness", "out", "preview");
// Full-surface galleries previewed per theme (the dot-* header clips are
// excluded — too small to be theme-expressive). Includes the External Jobs
// subtab + the two review-wizard steps so a theme is shown on the modal too.
const FULL_GALLERIES = [
  "rooms-active",
  "review-badges",
  "mapping-badges",
  "external-jobs",
  "external-wizard-step1",
  "external-wizard-step2",
  "metrics-overview",
  "maintenance",
  "room-rules",
];
// The tabs those galleries are the populated version of — skipped from the plain
// tab tour so the preview carries no empty-stub duplicate.
const GALLERY_TAB_IDS = new Set([
  "rooms",
  "learning_review",
  "mapping_review",
  "metrics",
  "maintenance",
  "room_rules",
]);

function exportsToProcess() {
  const arg = process.argv[2];
  if (arg && arg.trim()) return [arg.trim()];
  const dir = join(repo, "gallery", "themes");
  if (!existsSync(dir)) return [];
  return readdirSync(dir).filter((f) => f.endsWith(".json")).map((f) => join(dir, f));
}

const files = exportsToProcess();
if (!files.length) {
  console.log("no theme exports to preview (looked in gallery/themes/)");
  process.exit(0);
}

const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: 2 });
const processed = [];

for (const file of files) {
  const name = basename(file).replace(/\.json$/, "");

  // Read as pure data; a parse failure is a skipped (not rendered) upload.
  let envelope;
  try {
    envelope = JSON.parse(readFileSync(file, "utf8"));
  } catch (e) {
    console.error(`skip ${name}: invalid JSON (${e.message})`);
    continue;
  }

  await mountHarness(page); // (re)load the bundle — contact-sheet setContent below replaces it
  const { bundle, scope, report } = await page.evaluate(
    (env) => window.__evcc.ingestTheme(env),
    envelope,
  );
  if (!report.ok) {
    console.error(`skip ${name}: ${report.reason}`);
    continue;
  }

  const outDir = join(OUT, name);
  mkdirSync(outDir, { recursive: true });
  writeFileSync(join(outDir, "ingest-report.json"), JSON.stringify({ scope, ...report }, null, 2));

  // Scope drives what we show. A texture-scoped export only needs the rooms
  // gallery (where floor textures live). A full theme is previewed across the
  // WHOLE card — the all-states galleries PLUS a tab tour — because this is a
  // theme-SHARING preview: a sharer wants their theme on every surface. The
  // galleries ARE the populated rooms / learning-review / mapping-review tabs,
  // so those three plain tabs are skipped (their stub renders are just empty
  // versions of the galleries); the rest are toured, incl. setup.
  const views = scope.length
    ? [{ kind: "gallery", id: "rooms-active" }]
    : [
        ...FULL_GALLERIES.map((id) => ({ kind: "gallery", id })),
        ...VIEW_ORDER.filter((id) => !GALLERY_TAB_IDS.has(id)).map((id) => ({ kind: "tab", id })),
      ];
  const shots = [];
  for (const v of views) {
    let res;
    let clip = null;
    if (v.kind === "gallery") {
      // A modal gallery (the review wizard) mounts its own host; emulate dark so
      // the modal matches the card, and clip the shot to the modal shell.
      const isModal = await page.evaluate(
        (gid) => Boolean((window.__evcc.gallery.find((g) => g.id === gid) || {}).modal),
        v.id,
      );
      await page.emulateMedia({ colorScheme: isModal ? "dark" : "light" });
      res = await page.evaluate(
        ([gid, b]) => window.__evcc.renderGallery(gid, { bundle: b, freeze: true, width: 520 }),
        [v.id, bundle],
      );
      clip = res.clip;
    } else {
      await page.emulateMedia({ colorScheme: "light" });
      res = await renderTab(page, v.id, { bundle, freeze: true, width: 520 });
    }
    if (!res.ok) {
      console.error(`  ${name}/${v.id}: ${res.error}`);
      continue;
    }
    const shotId = v.kind === "tab" ? `tab-${v.id}` : v.id;
    const buf = await (clip ? page.locator(clip).first() : page.locator("#evcc-host")).screenshot();
    writeFileSync(join(outDir, `${shotId}.png`), buf);
    shots.push({ id: shotId, b64: buf.toString("base64") });

    // Index hero: clip a single room card from the rooms render — compact and
    // theme-expressive, so the gallery index stays scannable as it grows.
    if (v.id === "rooms-active") {
      const roomCards = page.locator(".evcc-room-card");
      if (await roomCards.count()) {
        writeFileSync(join(outDir, "thumb.png"), await roomCards.first().screenshot());
      }
    }
  }

  // Per-theme contact sheet (this navigates the page away — we re-mount next iteration).
  const cols = Math.min(shots.length, 3) || 1;
  const cells = shots
    .map(
      (s) => `<figure style="margin:0">
        <figcaption style="font:12px/1.4 system-ui,sans-serif;color:#cbd2da;padding:4px 2px">${s.id}</figcaption>
        <img src="data:image/png;base64,${s.b64}" style="display:block;width:520px;border:1px solid #2a2f37"></figure>`,
    )
    .join("");
  await page.setContent(
    `<body style="margin:0;background:#0b0d10;display:grid;grid-template-columns:repeat(${cols},540px);gap:16px;padding:16px;align-items:start">${cells}</body>`,
    { waitUntil: "domcontentloaded" },
  );
  writeFileSync(join(outDir, "_contact-sheet.png"), await page.screenshot({ fullPage: true }));

  // Tags + attribution: computed from the SAME envelope the card sees, via the
  // shared theme-tags core — so the gallery and the in-card picker agree exactly.
  // (A failed `colorblind-safe` claim is already stripped from `tags`; the gallery
  // never shows why — that feedback belongs to the submission/ingest path.)
  const { tags: themeTags } = effectiveThemeTags(envelope.theme || {});
  const attr = themeAttribution(envelope.theme || {});
  // A theme's filter tokens = its effective tags PLUS its source (community/
  // generated/manual aren't tags, but the Source facet filters on them; `core`
  // is already a derived tag).
  const filterTokens = [...new Set([...themeTags, ...(attr.source ? [attr.source] : [])])];

  writeThemePage(outDir, envelope.theme?.name || name, scope, report, shots, { tags: themeTags, attr });

  processed.push({ name, themeName: envelope.theme?.name || name, scope, report, tags: themeTags, attr, filterTokens });
  console.log(
    `✓ ${name}: ${report.keyCount} keys, scope=[${scope.join(",") || "full"}], ` +
      `${report.clamped} clamped, ${report.skippedKeys.length} skipped -> harness/out/preview/${name}/`,
  );
}

if (processed.length) {
  writeIndex(processed, OUT);
  console.log(`index -> harness/out/preview/index.html (${processed.length} theme${processed.length === 1 ? "" : "s"})`);
}

await browser.close();
