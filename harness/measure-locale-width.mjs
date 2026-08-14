/**
 * LOCALE STRESS RANKING — by RENDERED WIDTH, not character count.
 *
 *   node harness/measure-locale-width.mjs [--font opendyslexic] [--top 8]
 *
 * WHY NOT CHARACTERS. Character count answers the wrong question. A locale can
 * be 1.36x English by characters and wrap harmlessly at its spaces, while
 * another produces one unbreakable compound that overflows a chip. And the
 * font changes the answer again: OpenDyslexic's glyphs and tracking are ~66%
 * wider than Arial for the same string, so strings that are merely "long" in a
 * normal face become impossible in the accessible one. Rank what the browser
 * actually paints.
 *
 * WHAT IT REPORTS, per locale:
 *   mean      average rendered-width expansion vs the same key in English
 *   >1.3x     how many strings blow past 1.3x — density pressure
 *   max       the single largest expansion, and which key
 *   absolute  the widest rendered string outright, and which key
 *
 * Absolute width is reported ALONGSIDE expansion on purpose: 1.8x of a tiny
 * word is harmless, while 1.25x of an already-long category name is what
 * breaks a chip. Ranking by expansion alone hides the second case.
 *
 * ALSO PER SCREEN. The locale that is globally worst is not necessarily the one
 * that murders a given view — a dozen brutal strings in the Theme editor matter
 * more than 500 mildly expanded ones spread everywhere. Keys are grouped by
 * their namespace so each screen gets its own ranking.
 */
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { chromium } from "@playwright/test";
import { mountHarness } from "./lib/mount-page.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const REPO = join(here, "..");
const LOCALES = join(REPO, "custom_components/eufy_vacuum/frontend/locales");
const flagValue = (n, d) => { const i = process.argv.indexOf(n); return i === -1 ? d : process.argv[i + 1]; };
const FONT = flagValue("--font", "opendyslexic");
const TOP = Number(flagValue("--top", "8")) || 8;

/* ---- collect the catalogs ------------------------------------------------ */
const enSrc = readFileSync(join(REPO, "src/i18n/en.js"), "utf8");
const en = {};
{
  const re = /^\s*"([^"]+)":\s*"((?:[^"\\]|\\.)*)"/gm;
  let m;
  while ((m = re.exec(enSrc)) !== null) en[m[1]] = m[2].replace(/\\"/g, '"');
}

const flat = (o, p = "", out = {}) => {
  for (const [k, v] of Object.entries(o || {})) {
    const key = p ? `${p}.${k}` : k;
    if (v && typeof v === "object" && !Array.isArray(v)) flat(v, key, out);
    else if (typeof v === "string") out[key] = v;
  }
  return out;
};

const packs = {};
for (const f of readdirSync(LOCALES)) {
  if (!f.endsWith(".json") || f.includes("reference") || f === "index.json") continue;
  packs[f.replace(".json", "")] = flat(JSON.parse(readFileSync(join(LOCALES, f), "utf8")));
}

/* ---- measure in a real browser, in the real font -------------------------- */
const browser = await chromium.launch();
const page = await browser.newPage();
await mountHarness(page);

// Render one gallery entry in the target font so its @font-face is loaded and
// applied before anything is measured.
await page.evaluate(
  (font) => window.__evcc.renderGallery("rooms-active", { width: 520, font }),
  FONT,
);
await page.evaluate(() => document.fonts.ready);

const results = await page.evaluate(
  ({ en, packs, font }) => {
    const host = document.getElementById("evcc-host");
    const probe = document.createElement("span");
    probe.style.cssText =
      "position:absolute;left:-99999px;top:0;white-space:pre;font-size:14px;";
    // Match what the card actually paints: its own family stack.
    const shadowEl = host?.shadowRoot?.querySelector(".evcc-shell");
    probe.style.fontFamily = shadowEl
      ? getComputedStyle(shadowEl).fontFamily
      : `${font}, sans-serif`;
    document.body.appendChild(probe);

    const strip = (s) => s.replace(/<[^>]+>/g, "").replace(/\{[^}]*\}/g, "");
    const width = (s) => { probe.textContent = strip(s); return probe.getBoundingClientRect().width; };

    const enWidth = {};
    for (const [k, v] of Object.entries(en)) enWidth[k] = width(v);

    const out = {};
    for (const [lang, pack] of Object.entries(packs)) {
      let sum = 0, n = 0, over = 0, under = 0;
      let minRatio = Infinity, minRatioKey = "";
      let maxRatio = 0, maxRatioKey = "", maxRatioText = "";
      let maxAbs = 0, maxAbsKey = "", maxAbsText = "";
      const byScreen = {};

      for (const [k, v] of Object.entries(pack)) {
        const ew = enWidth[k];
        if (!ew || ew < 30) continue;            // ignore tiny strings; ratios there are noise
        const w = width(v);
        const r = w / ew;
        sum += r; n += 1;
        if (r > 1.3) over += 1;
        if (r < 0.7) under += 1;
        if (r < minRatio) { minRatio = r; minRatioKey = k; }
        if (r > maxRatio) { maxRatio = r; maxRatioKey = k; maxRatioText = strip(v).slice(0, 40); }
        if (w > maxAbs) { maxAbs = w; maxAbsKey = k; maxAbsText = strip(v).slice(0, 40); }

        const screen = k.split(".")[0];
        const s = (byScreen[screen] ??= { sum: 0, n: 0, over: 0, maxAbs: 0, maxAbsKey: "" });
        s.sum += r; s.n += 1;
        if (r > 1.3) s.over += 1;
        if (w > s.maxAbs) { s.maxAbs = w; s.maxAbsKey = k; }
      }

      out[lang] = {
        mean: n ? sum / n : 0, n, over, under, minRatio, minRatioKey,
        maxRatio, maxRatioKey, maxRatioText,
        maxAbs, maxAbsKey, maxAbsText,
        byScreen: Object.fromEntries(
          Object.entries(byScreen).map(([s, v]) => [s, { mean: v.sum / v.n, n: v.n, over: v.over, maxAbs: v.maxAbs, maxAbsKey: v.maxAbsKey }]),
        ),
      };
    }
    probe.remove();
    return out;
  },
  { en, packs, font: FONT },
);

await browser.close();

/* ---- report -------------------------------------------------------------- */
const langs = Object.entries(results);
const p = (n, w = 6) => n.toFixed(3).padStart(w);

console.log(`\nRENDERED WIDTH vs ENGLISH — font: ${FONT}\n`);
console.log("BY AVERAGE EXPANSION  (general density pressure)");
console.log("lang      mean    >1.3x   widest single string");
for (const [lang, r] of [...langs].sort((a, b) => b[1].mean - a[1].mean).slice(0, TOP)) {
  console.log(`${lang.padEnd(8)} ${p(r.mean)}x  ${String(r.over).padStart(4)}   ${Math.round(r.maxAbs)}px  ${r.maxAbsKey}`);
}

console.log("\nBY WIDEST SINGLE STRING  (chips / buttons / headings)");
console.log("lang     widest   key / text");
for (const [lang, r] of [...langs].sort((a, b) => b[1].maxAbs - a[1].maxAbs).slice(0, TOP)) {
  console.log(`${lang.padEnd(8)} ${String(Math.round(r.maxAbs)).padStart(5)}px  ${r.maxAbsKey}  "${r.maxAbsText}"`);
}

/* COMPRESSION IS THE OTHER STRESS, and the CJK packs hand it over for free.
   Expansion breaks things by overflowing; compression breaks things by leaving
   a layout that assumed text would fill it — label columns collapsing to
   nothing, a "last column takes the slack" rule handing almost everything to
   one cell, chips shrinking to pills, truncation that never fires and so is
   never seen to be wrong. */
console.log("\nBY COMPRESSION  (layouts that assumed text would fill the space)");
console.log("lang      mean   <0.7x   narrowest-vs-en example");
for (const [lang, r] of [...langs].sort((a, b) => a[1].mean - b[1].mean).slice(0, TOP)) {
  console.log(`${lang.padEnd(8)} ${p(r.mean)}x  ${String(r.under ?? "-").padStart(4)}   ${r.minRatioKey || ""}`);
}

console.log("\nBY LARGEST SINGLE EXPANSION");
console.log("lang      ratio   key / text");
for (const [lang, r] of [...langs].sort((a, b) => b[1].maxRatio - a[1].maxRatio).slice(0, TOP)) {
  console.log(`${lang.padEnd(8)} ${p(r.maxRatio)}x  ${r.maxRatioKey}  "${r.maxRatioText}"`);
}

/* PER SCREEN — the globally worst locale is not always the one that breaks a
   given view, and a view is what gets shot. */
const screens = new Set();
for (const [, r] of langs) for (const s of Object.keys(r.byScreen)) screens.add(s);
const INTERESTING = [...screens].filter((s) => {
  const total = langs.reduce((a, [, r]) => a + (r.byScreen[s]?.n || 0), 0);
  return total >= 17 * 8;   // skip namespaces too small to rank
});

console.log("\nPER SCREEN — worst locale by average expansion, then by widest string");
console.log("screen                worst-mean          worst-widest");
for (const s of INTERESTING.sort()) {
  const rows = langs.map(([lang, r]) => ({ lang, ...(r.byScreen[s] || {}) })).filter((x) => x.n);
  if (!rows.length) continue;
  const byMean = [...rows].sort((a, b) => b.mean - a.mean)[0];
  const byAbs = [...rows].sort((a, b) => b.maxAbs - a.maxAbs)[0];
  console.log(
    `${s.padEnd(20)}  ${byMean.lang} ${byMean.mean.toFixed(2)}x (${byMean.over} over)   ` +
    `${byAbs.lang} ${Math.round(byAbs.maxAbs)}px`,
  );
}
