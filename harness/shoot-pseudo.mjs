#!/usr/bin/env node
/**
 * Render every tab in English vs the PSEUDO-LONG locale, screenshot both
 * side-by-side, and probe each pseudo render for horizontal overflow — the
 * first "what does a long-text locale do to each tab" look (i18n P1).
 *
 *   node harness/shoot-pseudo.mjs [--width 500]
 *
 * Output: harness/out/pseudo/<tab>.en.png, <tab>.xx.png, _contact.png
 * Prints: a per-tab overflow report (raw, UNFILTERED — the protected-zone
 * allowlist is the next design step) + a proof line that the locale applied.
 */
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { mountHarness, renderTab, VIEW_ORDER } from "./lib/mount-page.mjs";
import { makePseudoLong, PSEUDO_MARKER } from "./lib/pseudo-locale.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const flag = (n, d) => { const i = process.argv.indexOf(n); return i === -1 ? d : process.argv[i + 1]; };
const width = Number(flag("--width", "500")) || 500;
const LANG = "xx";

const outDir = join(here, "out", "pseudo");
mkdirSync(outDir, { recursive: true });

// The overflow probe runs INSIDE the page against #evcc-host's shadow root.
// Raw: it flags every element whose content is wider than its box; the audit
// warns ~86 of these are INTENTIONAL clips (ellipsis/nowrap), so this is a
// triage list to build the protected-zone allowlist from, not a pass/fail gate.
function probe() {
  const host = document.getElementById("evcc-host");
  const root = host && host.shadowRoot;
  if (!root) return { ok: false };
  const items = [];
  for (const el of root.querySelectorAll("*")) {
    const ov = el.scrollWidth - el.clientWidth;
    if (ov > 1 && el.clientWidth > 0) {
      const cls = el.className && el.className.baseVal !== undefined
        ? el.className.baseVal : String(el.className || "");
      items.push({ tag: el.tagName.toLowerCase(), cls, ov, text: (el.textContent || "").trim().slice(0, 36) });
    }
  }
  const shell = root.querySelector(".evcc-shell");
  return {
    ok: true,
    markerPresent: (root.textContent || "").includes("lÄngerêr"),
    shellOverflow: shell ? shell.scrollWidth - host.clientWidth : 0,
    count: items.length,
    items: items.sort((a, b) => b.ov - a.ov).slice(0, 12),
  };
}

const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: 1 });
await mountHarness(page);

// Inject the pseudo-long catalog under LANG so render({lang}) resolves it.
const catalog = makePseudoLong();
await page.evaluate(([lang, cat]) => window.__evcc.registerLocale(lang, cat), [LANG, catalog]);

const rows = [];
let anyMarker = false;
console.log(`\nPSEUDO-LONG layout probe  (marker="${PSEUDO_MARKER}", width=${width}px)\n`);
for (const view of VIEW_ORDER) {
  const en = await renderTab(page, view, { width, freeze: true });
  const enPng = await page.locator("#evcc-host").screenshot();
  writeFileSync(join(outDir, `${view}.en.png`), enPng);

  const xx = await renderTab(page, view, { width, freeze: true, lang: LANG });
  if (!xx.ok) { console.log(`✗ ${view}: ${xx.error}`); continue; }
  const xxPng = await page.locator("#evcc-host").screenshot();
  writeFileSync(join(outDir, `${view}.xx.png`), xxPng);

  const p = await page.evaluate(probe);
  anyMarker = anyMarker || p.markerPresent;
  rows.push({ view, en: enPng.toString("base64"), xx: xxPng.toString("base64") });

  const shellTag = p.shellOverflow > 1 ? `  ⚠ SHELL +${p.shellOverflow}px (horizontal scroll)` : "";
  console.log(`${view.padEnd(16)} switched=${p.markerPresent ? "yes" : "NO "}  overflow-els=${String(p.count).padStart(3)}${shellTag}`);
  for (const it of p.items) {
    console.log(`    +${String(it.ov).padStart(4)}px  ${it.tag}.${(it.cls || "(none)").split(" ")[0].padEnd(28)} "${it.text}"`);
  }
}

// Side-by-side contact sheet: English | pseudo-long, one row per tab.
const cells = rows.map((r) => `
  <div style="display:contents">
    <figcaption style="font:12px/1.4 system-ui;color:#cbd2da;padding:6px 2px;grid-column:1/3;border-top:1px solid #2a2f37">${r.view}</figcaption>
    <img src="data:image/png;base64,${r.en}" style="width:${width}px;border:1px solid #2a2f37">
    <img src="data:image/png;base64,${r.xx}" style="width:${width}px;border:1px solid #5a3a3a">
  </div>`).join("");
await page.setContent(
  `<body style="margin:0;background:#0b0d10;display:grid;grid-template-columns:${width}px ${width}px;gap:8px 16px;padding:16px;align-items:start">` +
  `<div style="grid-column:1/3;font:600 14px system-ui;color:#e1e2e4">English  vs  pseudo-long (xx)</div>${cells}</body>`,
  { waitUntil: "domcontentloaded" });
writeFileSync(join(outDir, "_contact.png"), await page.screenshot({ fullPage: true }));

console.log(`\nLOCALE SWITCH PROOF: ${anyMarker ? "PASS — pseudo text rendered (renderers.t now resolves the user language)" : "FAIL — still English (renderer i18n not wired to language)"}`);
console.log(`screenshots -> harness/out/pseudo/  (_contact.png = side-by-side)\n`);

await browser.close();
