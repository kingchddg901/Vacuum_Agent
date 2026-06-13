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

const esc = (s) =>
  String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/** Per-theme detail page: the renders grouped into sections (galleries vs
 *  tabs) plus the ingest report. Written as <name>/index.html so the top
 *  index links to it. */
function writeThemePage(dir, themeName, scope, report, shots) {
  const galleries = shots.filter((s) => !s.id.startsWith("tab-"));
  const tabs = shots.filter((s) => s.id.startsWith("tab-"));
  const section = (title, list) =>
    !list.length
      ? ""
      : `    <section>
      <h2>${esc(title)}</h2>
      <div class="grid">
${list
  .map(
    (s) => `        <figure>
          <figcaption>${esc(s.id)}</figcaption>
          <a href="${esc(s.id)}.png"><img loading="lazy" src="${esc(s.id)}.png" alt="${esc(s.id)}"></a>
        </figure>`,
  )
  .join("\n")}
      </div>
    </section>`;
  const skipped = report.skippedKeys.length ? esc(report.skippedKeys.join(", ")) : "none";
  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(themeName)} — EVCC theme preview</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; background:#0b0d10; color:#e6e9ee; font:15px/1.5 system-ui,-apple-system,sans-serif; }
  header { padding:24px 24px 12px; border-bottom:1px solid #1c222a; }
  header .back { color:#5aa9ff; text-decoration:none; font-size:.85rem; }
  header h1 { margin:8px 0 4px; font-size:1.5rem; }
  .meta { color:#8b94a0; font-size:.84rem; margin:0 0 2px; }
  .meta a { color:#5aa9ff; }
  main { padding:8px 24px 48px; }
  section h2 { font-size:1.02rem; margin:26px 0 12px; color:#cbd2da; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:18px; }
  figure { margin:0; }
  figcaption { font:12px/1.4 ui-monospace,SFMono-Regular,monospace; color:#8b94a0; padding:0 0 5px; }
  img { display:block; width:100%; height:auto; border:1px solid #232a32; border-radius:8px; background:#0b0d10; }
  footer { padding:0 24px 36px; color:#6b7480; font-size:.8rem; }
</style>
</head>
<body>
  <header>
    <a class="back" href="../index.html">← all themes</a>
    <h1>${esc(themeName)}</h1>
    <p class="meta">scope: ${scope.length ? esc(scope.join(", ")) : "full"} · ${report.keyCount} tokens · ${report.clamped} clamped · ${report.skippedKeys.length} skipped</p>
    <p class="meta">skipped keys: ${skipped} · <a href="ingest-report.json">ingest report</a> · <a href="_contact-sheet.png">contact sheet</a></p>
  </header>
  <main>
${section("All-states galleries", galleries)}
${section("Card tabs", tabs)}
  </main>
  <footer>The real card recolored by this export, rendered through the harness ingest gate.</footer>
</body>
</html>
`;
  writeFileSync(join(dir, "index.html"), html);
}

/** Write a self-contained static gallery index over the rendered themes. */
function writeIndex(entries) {
  const cards = entries
    .map((e) => {
      const dir = encodeURIComponent(e.name);
      const meta = `${e.scope.length ? esc(e.scope.join(", ")) : "full"} · ${e.report.keyCount} tokens`;
      return `      <article class="card">
        <a class="thumb" href="${dir}/index.html"><img loading="lazy" src="${dir}/thumb.png" alt="${esc(e.themeName)} room card"></a>
        <h2><a href="${dir}/index.html">${esc(e.themeName)}</a></h2>
        <p class="meta">${meta}</p>
      </article>`;
    })
    .join("\n");

  const repoSlug = process.env.GITHUB_REPOSITORY || "kingchddg901/Vacuum_Agent";
  const submitUrl = `https://github.com/${repoSlug}/issues/new?template=theme-submission.yml`;

  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EVCC theme gallery</title>
<style>
  :root { color-scheme: dark; }
  body { margin: 0; background: #0b0d10; color: #e6e9ee; font: 15px/1.5 system-ui, -apple-system, sans-serif; }
  header { padding: 28px 24px 8px; }
  header h1 { margin: 0 0 4px; font-size: 1.4rem; }
  header p { margin: 0; color: #99a2ad; }
  a.submit { display: inline-block; margin-top: 12px; padding: 8px 16px; border: 1px solid #2f6dd0; border-radius: 8px; background: #173455; color: #cfe2ff; text-decoration: none; font-size: 0.9rem; font-weight: 600; }
  a.submit:hover { background: #1d4474; }
  main { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 18px; padding: 20px 24px 40px; }
  .card { background: #14181d; border: 1px solid #232a32; border-radius: 12px; padding: 12px 12px 10px; }
  .card h2 { margin: 10px 0 2px; font-size: 1.08rem; }
  .card h2 a { color: inherit; text-decoration: none; }
  .card .thumb { display: block; }
  .meta { margin: 0; color: #8b94a0; font-size: 0.8rem; }
  .card img { display: block; width: 100%; height: auto; border-radius: 8px; border: 1px solid #232a32; background: #0b0d10; }
  .links { margin: 8px 0 0; font-size: 0.8rem; }
  .links a, header a { color: #5aa9ff; }
  footer { padding: 0 24px 36px; color: #6b7480; font-size: 0.8rem; }
  footer code { color: #99a2ad; }
</style>
</head>
<body>
  <header>
    <h1>EVCC theme gallery</h1>
    <p>${entries.length} theme${entries.length === 1 ? "" : "s"} rendered through the harness ingest gate — each is the real card recolored by a committed export. Click a theme to open its full preview.</p>
    <p><a class="submit" href="${submitUrl}">+ Submit a theme</a> <a class="submit" href="docs/">📖 Documentation</a></p>
  </header>
  <main>
${cards}
  </main>
  <footer>Generated by <code>harness/preview.mjs</code>. Add a theme by committing its export to <code>gallery/themes/</code>.</footer>
</body>
</html>
`;
  mkdirSync(OUT, { recursive: true });
  writeFileSync(join(OUT, "index.html"), html);
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

  writeThemePage(outDir, envelope.theme?.name || name, scope, report, shots);

  processed.push({ name, themeName: envelope.theme?.name || name, scope, report });
  console.log(
    `✓ ${name}: ${report.keyCount} keys, scope=[${scope.join(",") || "full"}], ` +
      `${report.clamped} clamped, ${report.skippedKeys.length} skipped -> harness/out/preview/${name}/`,
  );
}

if (processed.length) {
  writeIndex(processed);
  console.log(`index -> harness/out/preview/index.html (${processed.length} theme${processed.length === 1 ? "" : "s"})`);
}

await browser.close();
