/**
 * I18N LAYOUT GATE — a translated locale must not break the layout.
 *
 * The acceptance bar (from the i18n design doc): no unwanted horizontal scroll,
 * controls stay reachable, long text degrades into taller/wrapped layouts —
 * NOT a byte-identical render. So this gate is PROPERTY-based, not pixel-pinned:
 * render each tab under the pseudo-long locale (every string deliberately
 * widened) and assert nothing escapes its box. The "allowlist" of acceptable
 * clipping is computed from CSS by probeLayout (overflow-x:visible escapes =
 * fail; ellipsize/scroll = intentional), so there is no hand-maintained list to
 * drift.
 *
 * DESKTOP @500px: ACTIVE GATE (green as of the P2 CSS hardening). A regression
 * that reintroduces horizontal overflow under a long-text locale fails here.
 *
 * MOBILE @390px: ACTIVE GATE (green — survived on first run, no CSS needed).
 * Renders the real mobile chrome (mobile header + bottom nav + overflow overlay,
 * data-viewport="mobile") at a phone-sized viewport so the viewport-fixed bottom
 * nav and the max-width:600px media rules are faithful. The mobile bottom nav
 * (icons + labels that wrap under each) and the responsive panel stacking
 * already handle long-text locales; this gate keeps it that way. Verified
 * faithful (bottom nav renders ~2.8k chars) + eyeballed. See project_i18n_rollout.md.
 */
import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

import { mountHarness, renderTab, probeLayout, VIEW_ORDER } from "../lib/mount-page.mjs";

const registerPseudo = (page) =>
  page.evaluate(() => window.__evcc.registerLocale("xx", window.__evcc.makePseudoLong()));

function assertNoOverflow(view, { shellOverflow, culprits }) {
  const list = culprits.map((c) => `      +${c.ov}px  ${c.tag}.${c.cls}  "${c.text}"`).join("\n");
  // 1) The card must not force horizontal scroll on itself.
  expect(shellOverflow, `${view}: card forces ${shellOverflow}px of horizontal scroll`).toBeLessThanOrEqual(2);
  // 2) No element may let its content escape its box (overflow-x:visible).
  expect(culprits.length, `${view}: ${culprits.length} element(s) overflow their box:\n${list}`).toBe(0);
}

test.describe("i18n layout gate: pseudo-long @500px (desktop)", () => {
  for (const view of VIEW_ORDER) {
    test(`${view} survives pseudo-long`, async ({ page }) => {
      await mountHarness(page);
      await registerPseudo(page);
      const res = await renderTab(page, view, { width: 500, freeze: true, lang: "xx" });
      expect(res.ok, res.error).toBe(true);
      assertNoOverflow(view, await probeLayout(page));
    });
  }
});

test.describe("i18n layout gate: pseudo-long @390px (mobile)", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  for (const view of VIEW_ORDER) {
    test(`${view} survives pseudo-long (mobile chrome)`, async ({ page }) => {
      await mountHarness(page);
      await registerPseudo(page);
      // ACCEPTED RED (2026-08-07): map_config overflows three
      // `.evcc-map-variant-label` spans by ~10px at 390px under pseudo-long ONLY.
      // The gate is deliberately harder than any language: expand() inflates a
      // 4-char word to 13 ("Dark" -> "Dark lAngerer"), a 3.25x stretch. Measured
      // against REAL catalogues at the same width, every shipped locale is clean
      // with room to spare -- nl/ru/fr/it/de/tr/pt/es/cs/pl all report
      // scroll=-2, culprits=0 -- and the longest real string for that label
      // (nl "Achtergrondafbeelding", 21 chars) still fits. Chris: keep the gate
      // hard, mark this known. German is the hardest case he will actually run,
      // and it is pinned GREEN below.
      // test.fail(), not skip: Playwright errors if it starts PASSING, so fixing
      // the 10px forces this marker to be removed rather than rotting here.
      if (view === "map_config") {
        test.fail(true, "accepted: ~10px on 3 map-variant labels under 3.25x pseudo inflation; every real locale is clean (see the de gate below)");
      }
      const res = await renderTab(page, view, { width: 390, freeze: true, lang: "xx", mobile: true });
      expect(res.ok, res.error).toBe(true);
      assertNoOverflow(view, await probeLayout(page));
    });
  }
});

// REAL DATA: Cyrillic room NAMES with an English UI — the Russian pilot's actual
// situation (no ru catalog ships yet; names flow through as {name} vars). The
// rooms-cyrillic fixture carries realistic names + one long one ("Детская
// комната"). Distinct from pseudo-long (synthetic catalog expansion): this is
// the one case driven by real non-Latin USER data. ABSOLUTE zero-overflow now
// that probeLayout no longer flags the active-job view's deliberate
// negative-margin bleeds (the pre-existing ~4px was a contained tap-target /
// full-bleed bleed, not content overflow).
const renderCyrillic = (page, opts) =>
  page.evaluate((o) => window.__evcc.renderGallery("rooms-cyrillic", o), opts);

// RESOLVED 2026-08-07 — both tests below were marked ACCEPTED RED on 2026-07-12
// for a ~5px `.evcc-saved-zones-header` overflow blamed on the long English
// `saved_zones.subtitle`. That diagnosis was wrong in a way worth recording: the
// overflow was locale-INDEPENDENT (identical +4px in en and de) and had nothing
// to do with text at all. The collapsed chevron carries `transform: rotate(-90deg)`
// and a rotated box reports its ROTATED bounding rect, so a 13px-wide glyph
// measured 20px and pushed past the header's content edge. Fixed by giving it a
// square 1em rotation target (styles/saved-zones.js), and these two are now
// ACTIVE gates. Playwright's "Expected to fail, but passed" is what forced the
// re-look — the self-cleaning property of test.fail() over skip().
test.describe("i18n layout gate: Cyrillic room data", () => {
  test("rooms @500px (desktop)", async ({ page }) => {
    await mountHarness(page);
    const res = await renderCyrillic(page, { width: 500, freeze: true });
    expect(res.ok, res.error).toBe(true);
    assertNoOverflow("rooms-cyrillic", await probeLayout(page));
  });

  test.describe("mobile @390px", () => {
    test.use({ viewport: { width: 390, height: 844 } });
    test("rooms (mobile chrome)", async ({ page }) => {
      await mountHarness(page);
      const res = await renderCyrillic(page, { width: 390, freeze: true, mobile: true });
      expect(res.ok, res.error).toBe(true);
      assertNoOverflow("rooms-cyrillic", await probeLayout(page));
    });
  });
});


// REAL CATALOGUE, hardest shipped language. Chris: "german is the hardest test I
// will run on it." The pseudo gate above stresses at 3.25x, which nothing human
// reaches; this asserts the bar that actually matters -- a language people read,
// at a real phone width, with the real mobile chrome.
//
// Added the same day map_config's pseudo case was marked known-failing, and for
// that reason: silencing a synthetic red without adding a real check would have
// traded a noisy gate for no gate. Measured green on all nine views before being
// committed as a gate, so it lands active rather than red.
const LOCALE_DIR = "custom_components/eufy_vacuum/frontend/locales";
const CATALOGUES = {};
function catalogue(code) {
  if (!CATALOGUES[code]) {
    CATALOGUES[code] = JSON.parse(readFileSync(`${LOCALE_DIR}/${code}.json`, "utf8"));
  }
  return CATALOGUES[code];
}

// Seeding returns the catalogue size so callers can PROVE the locale landed.
// This gate shipped broken on 2026-08-07: it read `.clean` off flattenLocale,
// which returns {flat, coverage} — so it registered `undefined`, rendered
// ENGLISH on all nine views, and passed green for exactly that reason. The
// repo's other two seed sites (i18n-rtl.spec.mjs, shoot-locales.mjs) both
// destructure `.flat`; this was the only one that didn't.
async function seedLocale(page, code) {
  const keys = await page.evaluate(
    ([c, cat]) => {
      const { flat } = window.__evcc.flattenLocale(cat, window.__evcc.en);
      window.__evcc.registerLocale(c, flat);
      return Object.keys(flat || {}).length;
    },
    [code, catalogue(code)],
  );
  // A silently-empty catalogue is the failure mode that made this gate a no-op,
  // so assert the seed itself rather than trusting the render to notice.
  expect(keys, `${code} catalogue failed to flatten (gate would render English)`).toBeGreaterThan(2000);
}

const seedGerman = (page) => seedLocale(page, "de");

test.describe("i18n layout gate: REAL German @390px (mobile)", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  // The seed assertion above catches an EMPTY catalogue; this catches a
  // catalogue that registers but never reaches the renderer (a resolve/pin
  // regression). Together they mean this describe cannot silently degrade
  // into a second English run again.
  test("the gate actually renders German", async ({ page }) => {
    await mountHarness(page);
    await seedGerman(page);
    const read = () => page.evaluate(() =>
      document.getElementById("evcc-host").shadowRoot
        .querySelector(".evcc-maintenance-panel-title")?.textContent.trim());

    await renderTab(page, "maintenance", { width: 390, freeze: true, mobile: true });
    expect(await read()).toBe("Maintenance Overview");
    await renderTab(page, "maintenance", { width: 390, freeze: true, lang: "de", mobile: true });
    expect(await read()).toBe("Wartungsübersicht");
  });

  for (const view of VIEW_ORDER) {
    test(`${view} survives real German`, async ({ page }) => {
      await mountHarness(page);
      await seedGerman(page);
      const res = await renderTab(page, view, { width: 390, freeze: true, lang: "de", mobile: true });
      expect(res.ok, res.error).toBe(true);
      assertNoOverflow(`${view} [de]`, await probeLayout(page));
    });
  }
});

// THE CARD GRID. renderTab mounts the generic stub, whose maintenance data is
// EMPTY — so every gate above walks a "No upkeep items need attention" empty
// state and the densest text component in the panel had never been measured in
// any locale. That is how the German clip below reached a user's phone with a
// full-green i18n suite: an unmeasured scope reports zero culprits and reads
// exactly like a clean one.
//
// The gallery fixture already carries four real items + the station-water card,
// so drive it the way the Cyrillic gate above does. Both locales, because this
// was never German-only: at 390px English clipped "Replace Soon" by 4.5px and
// German clipped "Warnung" -> "Warn" by 7.4px and "Niedrig" by 15.9px.
// Fixed by letting .evcc-maintenance-card-header WRAP, with a min-width floor on
// the title. The first attempt (min-width:0 + overflow-wrap:anywhere, no wrap)
// fixed the clip and introduced a worse regression — see the RU note below.
test.describe("i18n layout gate: maintenance CARDS @390px (mobile)", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  // RU and NL are here for a reason, not for coverage theatre: NL has the
  // longest status in any shipped locale ("Binnenkort vervangen", 128px on a
  // 165px card) and RU is where the first fix REGRESSED -- min-width:0 let the
  // title shrink to 5px and overflow-wrap:anywhere rendered "Фильтр" as a
  // one-character-per-line vertical column. probeLayout reported that as CLEAN,
  // because a character column overflows nothing. So this gate asserts the
  // TITLE BOX, not just overflow -- the assertion probeLayout cannot make.
  for (const lang of [null, "de", "nl", "ru"]) {
    test(`maintenance cards survive ${lang ?? "english"}`, async ({ page }) => {
      await mountHarness(page);
      if (lang) await seedLocale(page, lang);
      const res = await page.evaluate(
        (o) => window.__evcc.renderGallery("maintenance", o),
        { width: 390, freeze: true, lang, mobile: true },
      );
      expect(res.ok, res.error).toBe(true);
      // Guard the fixture itself: if the gallery entry ever loses its items
      // this gate would go quietly green on an empty grid — the exact bug above.
      const cards = await page.evaluate(() =>
        document.getElementById("evcc-host").shadowRoot
          .querySelectorAll(".evcc-maintenance-card").length);
      expect(cards, "gallery fixture rendered no maintenance cards").toBeGreaterThan(3);
      assertNoOverflow(`maintenance-cards [${lang ?? "en"}]`, await probeLayout(page));

      // The title box itself. A starved flex item plus overflow-wrap:anywhere
      // degrades into a vertical character column that overflows NOTHING, so
      // assertNoOverflow above is blind to it by construction.
      const titles = await page.evaluate(() => {
        const root = document.getElementById("evcc-host").shadowRoot;
        return [...root.querySelectorAll(".evcc-maintenance-card-title")].map((t) => {
          const cs = getComputedStyle(t);
          const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.2;
          const r = t.getBoundingClientRect();
          return { text: t.textContent.trim().slice(0, 24), w: Math.round(r.width), lines: Math.round(r.height / lh) };
        });
      });
      // Assert the SYMPTOM, not the CSS rule. A width threshold here would be
      // tautological — min-width:7ch guarantees it — so it would only re-state
      // the implementation. Line count is implementation-independent: "Фильтр"
      // rendered as six stacked characters is six lines, and no sane title in
      // any language needs more than three on a 165px card.
      const towers = titles.filter((t) => t.lines > 3);
      expect(towers, `title collapsed into a character column: ${JSON.stringify(towers)}`).toEqual([]);
    });
  }
});

// ============================================================================
// POPULATED VIEWS — the hole this whole spec had.
//
// Every gate above this line renders through `renderTab`, which mounts the
// generic stub. That stub is a recording null-object: an absorbed accessor
// yields nothing to iterate, so a collection-driven view renders its EMPTY
// STATE. Measured 2026-08-07: SIX of the nine views in VIEW_ORDER are
// placeholders under it — rooms (269 chars, ".evcc-empty: No rooms yet…"),
// room_rules (277 chars), theme ("No themes available."), and the data regions
// of maintenance / metrics / learning_review. The card's PRIMARY view was being
// measured at 223 chars of markup against 34,072 for the real thing.
//
// So 18 pseudo-long assertions and 9 German ones were, for those views,
// asserting a layout property about an empty box — and reporting zero culprits,
// which is indistinguishable from a clean pass. That is how a card-header
// clipping bug reached a user's phone with this suite fully green.
//
// Proof the omission hid REAL measurements rather than hypothetical ones: with
// the fixture data in place, `.evcc-saved-zones-header` reported +4px in every
// locale, while `rooms survives pseudo-long` reported 0 culprits for the same
// view at the same width. (That +4px turned out to be the collapsed chevron's
// rotated bounding box, not text — fixed above.)
//
// These drive the SAME assertion through the gallery fixtures instead, at both
// gate widths, in English and German. All six were measured green before being
// committed, so they land ACTIVE.
// Each entry carries a DATA-ROW selector, measured to be 0 under the generic stub
// and > 0 with the fixture. That measurement is the point: a char-count or
// "no empty-state blocks" guard is not a discriminator here, because rooms-active
// legitimately contains empty sub-panels and room-rules is genuinely compact — and
// `.evcc-metrics-card` renders NINE times under the empty stub, so the obvious
// selector would have passed on a placeholder. Derived by diffing the class tally
// of the stub render against the fixture render, not by guessing.
const POPULATED = [
  ["rooms", "rooms-active", ".evcc-room-row"],
  ["room_rules", "room-rules", ".evcc-rule-card"],
  ["metrics", "metrics-overview", ".evcc-metrics-card-header"],
  ["learning_review", "review-badges", ".evcc-review-job-card"],
  ["maintenance", "maintenance", ".evcc-maintenance-card"],
  ["rooms+profiles", "run-profiles-unsupported-break", ".evcc-run-profiles-step"],
];

for (const [width, chrome] of [[390, true], [500, false]]) {
  test.describe(`i18n layout gate: POPULATED views @${width}px${chrome ? " (mobile)" : ""}`, () => {
    if (chrome) test.use({ viewport: { width: 390, height: 844 } });

    for (const [view, fixture, rowSel] of POPULATED) {
      for (const lang of [null, "de"]) {
        test(`${view} [${lang ?? "en"}] survives with real data`, async ({ page }) => {
          await mountHarness(page);
          if (lang) await seedLocale(page, lang);
          const res = await page.evaluate(
            ([id, o]) => window.__evcc.renderGallery(id, o),
            [fixture, { width, freeze: true, lang, mobile: chrome }],
          );
          expect(res.ok, res.error).toBe(true);
          // Guard the fixture, not just the layout: an emptied gallery entry would
          // restore the exact hole this block closes, silently and green.
          const rows = await page.evaluate(
            (sel) => document.getElementById("evcc-host").shadowRoot.querySelectorAll(sel).length,
            rowSel);
          expect(rows,
            `${fixture} rendered no ${rowSel} — the fixture is empty, so this gate measures nothing`)
            .toBeGreaterThan(0);
          assertNoOverflow(`${fixture} [${lang ?? "en"}] @${width}`, await probeLayout(page));
        });
      }
    }
  });
}
