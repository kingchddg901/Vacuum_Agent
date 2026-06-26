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
 * ACTIVE GATE (desktop @500px). Green as of the P2 CSS hardening: the tab strip
 * wraps (shell.js flex-wrap), filter-chip rows wrap their labels (foundation.js),
 * and map_config's composer buttons wrap (map.js). A regression that reintroduces
 * horizontal overflow under a long-text locale fails here. Still TODO (a future
 * addition, not yet asserted): a mobile-width run (stub isMobileViewport + frame
 * data-viewport) and a Cyrillic room-name fixture. See project_i18n_rollout.md.
 */
import { test, expect } from "@playwright/test";
import { mountHarness, renderTab, probeLayout, VIEW_ORDER } from "../lib/mount-page.mjs";

const WIDTH = 500;

test.describe("i18n layout gate: pseudo-long must not break the layout", () => {
  for (const view of VIEW_ORDER) {
    test(`${view} @${WIDTH}px survives pseudo-long`, async ({ page }) => {
      await mountHarness(page);
      // Generate + register the pseudo-long catalog IN-PAGE (the bundle resolves
      // en.js via esbuild; importing it Node-side trips Playwright's CJS loader).
      await page.evaluate(() => window.__evcc.registerLocale("xx", window.__evcc.makePseudoLong()));

      const res = await renderTab(page, view, { width: WIDTH, freeze: true, lang: "xx" });
      expect(res.ok, res.error).toBe(true);

      const { shellOverflow, culprits } = await probeLayout(page);
      const list = culprits.map((c) => `      +${c.ov}px  ${c.tag}.${c.cls}  "${c.text}"`).join("\n");

      // 1) The card must not force horizontal scroll on itself.
      expect(
        shellOverflow,
        `${view}: card forces ${shellOverflow}px of horizontal scroll`,
      ).toBeLessThanOrEqual(2);

      // 2) No element may let its content escape its box (overflow-x:visible).
      expect(
        culprits.length,
        `${view}: ${culprits.length} element(s) overflow their box:\n${list}`,
      ).toBe(0);
    });
  }
});
