/**
 * I18N RTL LAYOUT GATE — a right-to-left locale must flip cleanly.
 *
 * The pseudo-long gate (i18n-layout.spec.mjs) proves the card survives text
 * EXPANSION (synthetic max-width strings, strictly wider than German) but it
 * renders LTR. RTL is a different failure mode: the direction flip exercises
 * every physical-vs-logical CSS choice — a stray `margin-left` / `padding-right`
 * / `left:` that should have been `*-inline-start` renders fine LTR and only
 * misplaces or overflows once `dir="rtl"` inherits into the shadow tree. The
 * check-styles RTL lint catches physical properties in SOURCE; this catches the
 * RENDERED consequence, and the two together are the belt-and-braces for RTL.
 *
 * This gate renders each tab under the REAL Arabic and Hebrew catalogs with the
 * host flipped to RTL (mount-entry stamps dir via applyDir, exactly as
 * src/main.js does), then asserts — with the same property-based probe as the
 * pseudo-long gate — that nothing escapes its box and the card forces no
 * horizontal scroll. It also asserts the host actually carries dir="rtl", so the
 * gate can never pass by silently rendering an LTR layout.
 */
import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { mountHarness, renderTab, probeLayout, VIEW_ORDER } from "../lib/mount-page.mjs";

const here = dirname(fileURLToPath(import.meta.url));

// Read the shipped locale JSON in Node (fs) and hand the parsed NESTED object to
// the page; the flatten-against-English step runs IN-PAGE via window.__evcc so
// this spec never imports en.js/flatten.js (Playwright's loader treats a
// typeless .js as CJS and rejects their ESM `export const`). Mirrors the runtime
// load path (harness/shoot-locales.mjs) otherwise.
const nestedFor = (code) =>
  JSON.parse(
    readFileSync(
      join(here, "..", "..", "custom_components", "eufy_vacuum", "frontend", "locales", `${code}.json`),
      "utf8",
    ),
  );

// Flatten + register the locale inside the page (needs window.__evcc → call
// AFTER mountHarness).
const registerRtl = (page, lang, nested) =>
  page.evaluate(([l, n]) => {
    const { flat } = window.__evcc.flattenLocale(n, window.__evcc.en);
    window.__evcc.registerLocale(l, flat);
  }, [lang, nested]);

function assertNoOverflow(view, lang, { shellOverflow, culprits }) {
  const list = culprits.map((c) => `      +${c.ov}px  ${c.tag}.${c.cls}  "${c.text}"`).join("\n");
  expect(shellOverflow, `${view} (${lang}): card forces ${shellOverflow}px of horizontal scroll under RTL`).toBeLessThanOrEqual(2);
  expect(culprits.length, `${view} (${lang}): ${culprits.length} element(s) overflow their box under RTL:\n${list}`).toBe(0);
}

for (const lang of ["ar", "he"]) {
  const nested = nestedFor(lang);

  test.describe(`i18n RTL layout gate: ${lang} @500px (desktop)`, () => {
    for (const view of VIEW_ORDER) {
      test(`${view} flips RTL and survives`, async ({ page }) => {
        await mountHarness(page);
        await registerRtl(page, lang, nested);
        const res = await renderTab(page, view, { width: 500, freeze: true, lang });
        expect(res.ok, res.error).toBe(true);

        // Fidelity guard: the host must actually be RTL, or the gate is vacuous.
        const dir = await page.evaluate(() => document.getElementById("evcc-host").getAttribute("dir"));
        expect(dir, `${view} (${lang}): host did not flip to dir="rtl"`).toBe("rtl");

        assertNoOverflow(view, lang, await probeLayout(page));
      });
    }
  });

  test.describe(`i18n RTL layout gate: ${lang} @390px (mobile)`, () => {
    test.use({ viewport: { width: 390, height: 844 } });

    for (const view of VIEW_ORDER) {
      test(`${view} flips RTL and survives (mobile chrome)`, async ({ page }) => {
        await mountHarness(page);
        await registerRtl(page, lang, nested);
        const res = await renderTab(page, view, { width: 390, freeze: true, lang, mobile: true });
        expect(res.ok, res.error).toBe(true);
        assertNoOverflow(view, lang, await probeLayout(page));
      });
    }
  });
}

// ============================================================================
// POPULATED views under RTL — the same empty-scope hole as i18n-layout, and it
// bites HARDER here.
//
// All 36 gates above render through `renderTab`, i.e. the generic recording
// null-object stub, so a collection-driven view renders its EMPTY STATE. Six of
// the nine VIEW_ORDER views are placeholders under it. What this spec exists to
// catch is a stray PHYSICAL `margin-left` / `padding-right` surviving inside a
// room card, a rule row, a metrics cell or the preset grid — in its RENDERED
// consequence, which is the half `check-styles`' source lint cannot see. Those
// are exactly the components that were never in the DOM.
//
// Measured before committing: every fixture below flips to dir="rtl" and reports
// zero culprits under both ar and he, so nothing is being papered over — but zero
// findings from an unmeasured scope reads identically to zero from a clean one,
// which is the whole thesis of the census that produced this.
//
// Row selectors are the same measured discriminators as i18n-layout: each is 0
// under the stub and > 0 with the fixture, so an emptied fixture fails loudly
// instead of quietly restoring the hole.
const RTL_POPULATED = [
  ["rooms-active", ".evcc-room-row"],
  ["room-rules", ".evcc-rule-card"],
  ["metrics-overview", ".evcc-metrics-card-header"],
  ["review-badges", ".evcc-review-job-card"],
  ["maintenance", ".evcc-maintenance-card"],
  ["run-profiles-unsupported-break", ".evcc-run-profiles-step"],
];

for (const lang of ["ar", "he"]) {
  const nested = nestedFor(lang);

  for (const [width, chrome] of [[390, true], [500, false]]) {
    test.describe(`i18n RTL layout gate: ${lang} POPULATED @${width}px${chrome ? " (mobile)" : ""}`, () => {
      if (chrome) test.use({ viewport: { width: 390, height: 844 } });

      for (const [fixture, rowSel] of RTL_POPULATED) {
        test(`${fixture} flips RTL and survives with real data`, async ({ page }) => {
          await mountHarness(page);
          await registerRtl(page, lang, nested);
          const res = await page.evaluate(
            ([id, o]) => window.__evcc.renderGallery(id, o),
            [fixture, { width, freeze: true, lang, mobile: chrome }],
          );
          expect(res.ok, res.error).toBe(true);

          const dir = await page.evaluate(() => document.getElementById("evcc-host").getAttribute("dir"));
          expect(dir, `${fixture} (${lang}): host did not flip to dir="rtl"`).toBe("rtl");

          const rows = await page.evaluate(
            (sel) => document.getElementById("evcc-host").shadowRoot.querySelectorAll(sel).length,
            rowSel);
          expect(rows,
            `${fixture} rendered no ${rowSel} — the fixture is empty, so this gate measures nothing`)
            .toBeGreaterThan(0);

          assertNoOverflow(`${fixture} @${width}`, lang, await probeLayout(page));
        });
      }
    });
  }
}
