/**
 * REAL-FRAME tests — the card's OWN shell, not the harness's synthetic one.
 *
 * Every other spec here renders stub state into the renderers and wraps it in
 * frameHtml(). That is the right default, but it means main.js's frame is never
 * built, so nothing main.js owns can be asserted. Three bugs in one day came from
 * that blind spot: a gallery case byte-identical to its plain twin, a semantic-token
 * claim that could not be verified, and a layout probe shipped unproven.
 *
 * These are deliberately few. The synthetic path stays the default.
 */
import { test, expect } from "@playwright/test";
import { mountRealCard } from "../lib/mount-page.mjs";

test("[RF-1] the real card builds its own shell", async ({ page }) => {
  const r = await mountRealCard(page, { width: 1180, viewport: { width: 1280, height: 800 } });
  expect(r.mounted, "main.js never built .evcc-shell — every assertion below is vacuous without it").toBe(true);
});

test("[RF-2] viewport is decided from the CARD's width, not the window's", async ({ page }) => {
  // The distinction that matters for the mobile fault: Lovelace can hand the card a
  // box narrower or wider than the window, so window.innerWidth is not the input.
  const narrow = await mountRealCard(page, { width: 390, viewport: { width: 1280, height: 800 } });
  expect(narrow.viewport, `a 390px card in a 1280px window must be mobile (host=${narrow.hostWidth})`).toBe("mobile");

  const wide = await mountRealCard(page, { width: 1180, viewport: { width: 390, height: 780 } });
  expect(wide.viewport, `an 1180px card in a 390px window must be desktop (host=${wide.hostWidth})`).toBe("desktop");
});

test("[RF-3] mobile_shell overrides detection in both directions", async ({ page }) => {
  const forcedMobile = await mountRealCard(page, { width: 1180, config: { mobile_shell: true } });
  expect(forcedMobile.viewport).toBe("mobile");

  const forcedDesktop = await mountRealCard(page, { width: 390, config: { mobile_shell: false } });
  expect(forcedDesktop.viewport).toBe("desktop");
});

test("[RF-4] sticky chrome exists ONLY in the mobile shell", async ({ page }) => {
  // Not a style bug when it goes missing — the desktop header is position:relative
  // and there is no desktop bottom nav at all, so a misdetected viewport removes
  // both with nothing wrong in the CSS. This pins that link, which was previously
  // implicit and only discoverable by reading two style files against each other.
  await mountRealCard(page, { width: 390, config: { mobile_shell: true } });
  const mobile = await page.evaluate(() => {
    const sr = document.querySelector("eufy-vacuum-command-center").shadowRoot;
    const h = sr.querySelector(".evcc-mobile-header");
    return {
      hasMobileHeader: Boolean(h),
      headerPosition: h ? getComputedStyle(h).position : null,
      hasBottomNav: Boolean(sr.querySelector(".evcc-mobile-nav, [data-evcc-bottom-nav-root] > *")),
    };
  });
  expect(mobile.hasMobileHeader).toBe(true);
  expect(mobile.headerPosition).toBe("sticky");

  await mountRealCard(page, { width: 1180, config: { mobile_shell: false } });
  const desktop = await page.evaluate(() => {
    const sr = document.querySelector("eufy-vacuum-command-center").shadowRoot;
    const h = sr.querySelector(".evcc-header");
    return { headerPosition: h ? getComputedStyle(h).position : null };
  });
  expect(desktop.headerPosition, "the desktop header is not sticky by design — see RF-4's note").not.toBe("sticky");
});

test("[RF-5] the layout probe is off by default and reports when opted in", async ({ page }) => {
  // The probe that could not be verified at all before this file existed.
  await mountRealCard(page, { width: 390 });
  const off = await page.evaluate(() => {
    const s = document.querySelector("eufy-vacuum-command-center").shadowRoot
      .querySelector("[data-evcc-layout-probe]");
    return { exists: Boolean(s), hidden: s ? s.hidden : null };
  });
  expect(off.exists, "the probe slot is missing from the real frame").toBe(true);
  expect(off.hidden, "a debug probe must not render unless asked for").toBe(true);

  await mountRealCard(page, { width: 390, config: { layout_probe: true } });
  const on = await page.evaluate(() => {
    const s = document.querySelector("eufy-vacuum-command-center").shadowRoot
      .querySelector("[data-evcc-layout-probe]");
    return { hidden: s.hidden, text: s.textContent };
  });
  expect(on.hidden).toBe(false);
  expect(on.text).toMatch(/measured=\d+/);
  expect(on.text).toMatch(/viewport=(mobile|desktop)/);
});
