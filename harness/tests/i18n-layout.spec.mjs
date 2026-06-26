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
// the one case driven by real non-Latin USER data.
//
// RELATIVE assertion: "does the user's Cyrillic data break the layout WORSE than
// the equivalent ENGLISH data?" We diff rooms-cyrillic against rooms-active (the
// SAME fixture, names the only difference) — a long Cyrillic name pushing a NEW
// element over, or scrolling worse than English, fails. We do NOT assert
// absolute zero: the populated active-job view has a pre-existing,
// name-INDEPENDENT ~4px overflow in its control rows (English has it too), which
// is not a Cyrillic regression and is tracked separately.
async function probeEntry(page, id, opts) {
  const res = await page.evaluate(([gid, o]) => window.__evcc.renderGallery(gid, o), [id, opts]);
  expect(res.ok, `${id}: ${res.error}`).toBe(true);
  return probeLayout(page);
}

function assertCyrillicNoWorseThanEnglish(en, ru) {
  expect(
    ru.shellOverflow,
    `Cyrillic scrolls ${ru.shellOverflow}px vs English ${en.shellOverflow}px`,
  ).toBeLessThanOrEqual(en.shellOverflow + 1);
  const enClasses = new Set(en.culprits.map((c) => c.cls));
  const introduced = ru.culprits.filter((c) => !enClasses.has(c.cls));
  const list = introduced.map((c) => `      +${c.ov}px  ${c.tag}.${c.cls}  "${c.text}"`).join("\n");
  expect(
    introduced.length,
    `Cyrillic introduces overflow English doesn't (likely a long Cyrillic name):\n${list}`,
  ).toBe(0);
}

test.describe("i18n layout gate: Cyrillic room data", () => {
  test("rooms @500px (desktop): no worse than English", async ({ page }) => {
    await mountHarness(page);
    const en = await probeEntry(page, "rooms-active", { width: 500, freeze: true });
    const ru = await probeEntry(page, "rooms-cyrillic", { width: 500, freeze: true });
    assertCyrillicNoWorseThanEnglish(en, ru);
  });

  test.describe("mobile @390px", () => {
    test.use({ viewport: { width: 390, height: 844 } });
    test("rooms: no worse than English (mobile chrome)", async ({ page }) => {
      await mountHarness(page);
      const en = await probeEntry(page, "rooms-active", { width: 390, freeze: true, mobile: true });
      const ru = await probeEntry(page, "rooms-cyrillic", { width: 390, freeze: true, mobile: true });
      assertCyrillicNoWorseThanEnglish(en, ru);
    });
  });
});
