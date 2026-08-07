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

test("[RF-6] the mobile shell fills a panel host, and collapses without one", async ({ page }) => {
  // The footer fault, isolated. The mobile nav is deliberately NOT sticky — it sits
  // last in a height:100% flex column (see styles/mobile.js, which explains why an
  // earlier sticky draft was reverted). That design is correct ONLY while the host
  // supplies a definite height: HA panel mode does, a normal dashboard card does not.
  //
  // Without one the shell collapses to content height, so the nav lands wherever the
  // content ends and the view stage never becomes a scroll container — which also
  // leaves the sticky mobile HEADER with nothing to stick against. One cause, both
  // reported symptoms.
  const panel = await mountRealCard(page, {
    width: 390, viewport: { width: 390, height: 780 },
    config: { mobile_shell: true }, hostHeight: "100dvh",
  });
  const pinned = await page.evaluate(() => {
    const sr = document.querySelector("eufy-vacuum-command-center").shadowRoot;
    const nav = sr.querySelector("[data-evcc-bottom-nav-root]");
    return Math.abs(nav.getBoundingClientRect().bottom - window.innerHeight) < 3;
  });
  expect(panel.shellHeight, "the shell did not fill a definite-height host").toBeGreaterThan(700);
  expect(pinned, "the nav is not at the bottom of a filled shell").toBe(true);

  // ...and the height-less host, asserted so the dependency is documented rather
  // than rediscovered. If this ever starts filling, the shell grew its own
  // fallback height and RF-6's first half is the one that matters.
  const bare = await mountRealCard(page, {
    width: 390, viewport: { width: 390, height: 780 },
    config: { mobile_shell: true }, hostHeight: "auto",
  });
  expect(bare.shellHeight, "a height-less host no longer collapses the shell — see the note").toBeLessThan(400);
});

test("[RF-7] the mobile header labels the battery, like the desktop header", async ({ page }) => {
  // HDR-BATT-1 fixed the desktop header only; this sibling rendered a bare "100%"
  // with nothing saying what of, and never applied the low/critical bands.
  await mountRealCard(page, {
    width: 390, config: { mobile_shell: true },
    hass: { states: { "vacuum.alfred": { state: "docked", attributes: { battery_level: 8 } } } },
  });
  const b = await page.evaluate(() => {
    const el = document.querySelector("eufy-vacuum-command-center").shadowRoot
      .querySelector(".evcc-mobile-battery");
    return el ? { text: el.textContent.trim(), cls: el.className } : null;
  });
  if (b) {
    expect(b.text, "the mobile battery rendered a bare percent").toMatch(/\S+\s*\d+%/);
  }
});
