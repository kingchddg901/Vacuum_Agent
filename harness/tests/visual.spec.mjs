/**
 * WAVE 3 — VISUAL REGRESSION
 * Render the real card and diff against committed baselines.
 *
 * This is the unit that closes the frontend host-boundary gap the
 * backend tests can't reach (z-index, shadow DOM, layout, flood).
 *
 * Baselines are Linux, generated in the pinned Playwright image
 * (mcr.microsoft.com/playwright:v1.60.0-noble) so they match CI byte
 * for byte. On any other platform the render differs (fonts / AA), so
 * these tests are gated to CI or an explicit VISUAL=1 opt-in (run
 * inside that image). Smoke + completeness still run everywhere.
 *
 * To (re)generate baselines, see harness/README.md:
 *   docker run ... mcr.microsoft.com/playwright:v1.60.0-noble \
 *     bash -lc "npm install && node harness/build.mjs && \
 *       VISUAL=1 npx playwright test -c harness/playwright.config.mjs visual --update-snapshots"
 */
import { test, expect } from "@playwright/test";
import { mountHarness, renderTab, VIEW_ORDER } from "../lib/mount-page.mjs";

const RUN = Boolean(process.env.CI) || Boolean(process.env.VISUAL);

// Mirror of the gallery entry ids in harness/fixtures/gallery.js. The
// "ids in sync" test below fails if these drift, so this stays honest.
const GALLERY_IDS = [
  "rooms-active",
  "review-badges",
  "mapping-badges",
  "external-jobs",
  "external-wizard-step1",
  "external-wizard-step2",
  "metrics-overview",
  "maintenance",
  "room-rules",
  "dot-cleaning",
  "dot-returning",
  "dot-paused",
  "dot-error",
  "dot-docked",
  "dot-charging",
  "dot-offline",
  "dot-unavailable",
  "dot-idle",
];

test.describe("visual regression", () => {
  test.beforeEach(() => {
    test.skip(!RUN, "Linux-only baselines; run in CI or VISUAL=1 inside the Playwright image");
  });

  // Drift guard: the hardcoded GALLERY_IDS must match the live registry.
  test("gallery ids in sync", async ({ page }) => {
    await mountHarness(page);
    const ids = await page.evaluate(() => window.__evcc.gallery.map((g) => g.id));
    expect([...ids].sort()).toEqual([...GALLERY_IDS].sort());
  });

  // Per-tab structural baselines (stub state — empty/default branches).
  for (const view of VIEW_ORDER) {
    test(`tab ${view}`, async ({ page }) => {
      await mountHarness(page);
      const res = await renderTab(page, view, { freeze: true, width: 520 });
      expect(res.ok, res.error).toBe(true);
      await expect(page.locator("#evcc-host")).toHaveScreenshot(`tab-${view}.png`);
    });
  }

  // All-states galleries — the high-value colored-state baselines.
  for (const id of GALLERY_IDS) {
    test(`gallery ${id}`, async ({ page }) => {
      await mountHarness(page);
      // Modal fixtures mount their own host; headless defaults to light, which
      // flips the modal's light-hardening on while the card stays dark. Emulate
      // dark for modal shots so the modal matches the card.
      const isModal = await page.evaluate(
        (gid) => Boolean((window.__evcc.gallery.find((g) => g.id === gid) || {}).modal),
        id,
      );
      await page.emulateMedia({ colorScheme: isModal ? "dark" : "light" });
      const res = await page.evaluate(
        ([gid]) => window.__evcc.renderGallery(gid, { freeze: true, width: 520 }),
        [id],
      );
      expect(res.ok, `${id}: ${res.error}`).toBe(true);
      const target = res.clip ? page.locator(res.clip).first() : page.locator("#evcc-host");
      await expect(target).toHaveScreenshot(`gallery-${id}.png`);
    });
  }
});
