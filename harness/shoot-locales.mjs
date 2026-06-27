#!/usr/bin/env node
/**
 * Render every tab in each REAL bundled locale (de/fr/es/nl/it/pt/ru) next to
 * English and screenshot them, plus a per-language contact sheet — so the actual
 * translated UI can be eyeballed in context AND checked for layout damage. The
 * pseudo-long gate is synthetic stress; THIS is the real strings users will see.
 *
 *   node harness/shoot-locales.mjs [--width 500] [--mobile] [--langs de,ru]
 *
 * Renders via opts.lang, which the harness pins as config.i18n.locale (the
 * explicit per-dashboard override) so it BYPASSES the draft-gate — i.e. it shows
 * exactly what a user sees when they pick that language from the editor.
 *
 * Output: harness/out/locales/<tab>.<lang>.png + _contact.<lang>.png (en|lang),
 * and a per-tab overflow probe (worst horizontal overflow + a shell-overflow
 * warning if the card forces horizontal scroll). All tab renders run FIRST; the
 * contact sheets are built last (page.setContent replaces the page and would
 * destroy #root for any later render).
 */
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { mountHarness, renderTab, VIEW_ORDER } from "./lib/mount-page.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const flag = (n, d) => { const i = process.argv.indexOf(n); return i === -1 ? d : process.argv[i + 1]; };
const MOBILE = process.argv.includes("--mobile");
const width = Number(flag("--width", MOBILE ? "390" : "500")) || (MOBILE ? 390 : 500);
const ALL_LANGS = ["de", "fr", "es", "nl", "it", "pt", "ru"];
const arg = flag("--langs", "");
const LANGS = arg ? arg.split(",").map((s) => s.trim()).filter(Boolean) : ALL_LANGS;
const suffix = MOBILE ? "-mobile" : "";

const outDir = join(here, "out", "locales");
mkdirSync(outDir, { recursive: true });

// In-page probe: worst real horizontal overflow + whether the shell forces the
// card wider than its host (a horizontal-scroll smell), plus the FULL rendered
// text (collapsed) used to confirm the locale actually switched (differs from en).
function probe() {
  const host = document.getElementById("evcc-host");
  const root = host && host.shadowRoot;
  if (!root) return { ok: false };
  let count = 0, worst = 0, worstEl = null;
  for (const el of root.querySelectorAll("*")) {
    const ov = el.scrollWidth - el.clientWidth;
    if (ov <= 1 || el.clientWidth <= 0) continue;
    const tag = el.tagName.toLowerCase();
    if (tag === "svg" || tag === "img" || tag === "canvas" || tag === "video") continue;
    // Only count REAL escapes — an element that clips/scrolls its own excess
    // (overflow-x != visible) is an INTENTIONAL truncation (e.g. ellipsized
    // hint), not a card-breaking overflow. Mirrors lib/mount-page.probeLayout.
    if (getComputedStyle(el).overflowX !== "visible") continue;
    count++; if (ov > worst) { worst = ov; worstEl = el; }
  }
  const shell = root.querySelector(".evcc-shell");
  const cls = worstEl
    ? (worstEl.className && worstEl.className.baseVal !== undefined ? worstEl.className.baseVal : String(worstEl.className || ""))
    : "";
  return {
    ok: true, count, worst,
    culprit: worstEl ? `${worstEl.tagName.toLowerCase()}.${cls.split(" ")[0] || "(none)"} "${(worstEl.textContent || "").trim().slice(0, 40)}"` : "",
    shellOverflow: shell ? shell.scrollWidth - host.clientWidth : 0,
    text: (root.textContent || "").replace(/\s+/g, " ").trim(),
  };
}

const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: 1 });
if (MOBILE) await page.setViewportSize({ width, height: 844 });
await mountHarness(page);

// 1) English baseline per tab (rendered once, reused in every contact sheet).
const enShot = {}, enText = {};
for (const view of VIEW_ORDER) {
  await renderTab(page, view, { width, freeze: true, mobile: MOBILE });
  const png = await page.locator("#evcc-host").screenshot();
  enShot[view] = png.toString("base64");
  enText[view] = (await page.evaluate(probe)).text;
  writeFileSync(join(outDir, `${view}.en${suffix}.png`), png);
}

// 2) Every language, every tab — render + screenshot + probe. NO setContent yet.
const byLang = {};
for (const lang of LANGS) {
  console.log(`\n===== ${lang} (width=${width}px${MOBILE ? ", mobile" : ""}) =====`);
  byLang[lang] = [];
  for (const view of VIEW_ORDER) {
    const r = await renderTab(page, view, { width, freeze: true, lang, mobile: MOBILE });
    if (!r || !r.ok) { console.log(`✗ ${view}: ${(r && r.error) || "render failed"}`); continue; }
    const png = await page.locator("#evcc-host").screenshot();
    writeFileSync(join(outDir, `${view}.${lang}${suffix}.png`), png);
    const p = await page.evaluate(probe);
    const switched = p.text && p.text !== enText[view];
    const shellTag = p.shellOverflow > 1 ? `  ⚠ SHELL +${p.shellOverflow}px (horizontal scroll)` : "";
    const culpritTag = p.worst > 0 ? `  → ${p.culprit}` : "";
    console.log(`${view.padEnd(16)} switched=${switched ? "yes" : "NO "}  overflow-els=${String(p.count).padStart(3)}  worst=${String(p.worst).padStart(4)}px${shellTag}${culpritTag}`);
    byLang[lang].push({ view, en: enShot[view], loc: png.toString("base64") });
  }
}

// 3) Contact sheets LAST (setContent replaces the page; no renders follow).
for (const lang of LANGS) {
  const rows = byLang[lang] || [];
  if (!rows.length) continue;
  const cells = rows.map((r) => `
    <div style="display:contents">
      <figcaption style="font:12px/1.4 system-ui;color:#cbd2da;padding:6px 2px;grid-column:1/3;border-top:1px solid #2a2f37">${r.view}</figcaption>
      <img src="data:image/png;base64,${r.en}" style="width:${width}px;border:1px solid #2a2f37">
      <img src="data:image/png;base64,${r.loc}" style="width:${width}px;border:1px solid #3a5a3a">
    </div>`).join("");
  await page.setContent(
    `<body style="margin:0;background:#0b0d10;display:grid;grid-template-columns:${width}px ${width}px;gap:8px 16px;padding:16px;align-items:start">` +
    `<div style="grid-column:1/3;font:600 14px system-ui;color:#e1e2e4">English &nbsp; vs &nbsp; ${lang}${suffix}</div>${cells}</body>`,
    { waitUntil: "domcontentloaded" });
  writeFileSync(join(outDir, `_contact.${lang}${suffix}.png`), await page.screenshot({ fullPage: true }));
}

console.log(`\nscreenshots -> harness/out/locales/  (_contact.<lang>.png = English | locale, one row per tab)\n`);
await browser.close();
