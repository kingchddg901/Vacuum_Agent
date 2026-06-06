/**
 * WAVE 1 — HARNESS SMOKE
 * Every tab renders from the stub without throwing.
 *
 * This is a real test, not a proxy: because renderers are pure
 * `render(ctx) -> HTML`, a throw means a renderer reached outside its
 * state/ctx contract (a true global, the DOM) — exactly what we want
 * to catch. The stub's null-object absorbs unknown `state.*` reads, so
 * the only way to throw is a genuine contract breach.
 */
import { test, expect } from "@playwright/test";
import { mountHarness, renderTab, VIEW_ORDER } from "../lib/mount-page.mjs";

test.describe("harness smoke: every tab renders without throwing", () => {
  for (const view of VIEW_ORDER) {
    test(`renders ${view}`, async ({ page }) => {
      const pageErrors = [];
      page.on("pageerror", (e) => pageErrors.push(String(e.stack || e)));

      await mountHarness(page);
      const res = await renderTab(page, view);

      expect(
        res.ok,
        `render(${view}) threw:\n${res.error}\n${res.stack || ""}`,
      ).toBe(true);
      expect(
        pageErrors,
        `uncaught pageerror during ${view}:\n${pageErrors.join("\n")}`,
      ).toEqual([]);

      // It must have rendered real content into the active view-root,
      // not silently produced nothing.
      const viewLen = await page.evaluate(() => {
        const host = document.getElementById("evcc-host");
        const root = host?.shadowRoot?.querySelector("[data-evcc-view-root]");
        return root ? root.innerHTML.trim().length : 0;
      });
      expect(viewLen, `view-root rendered empty for ${view}`).toBeGreaterThan(20);
    });
  }
});
