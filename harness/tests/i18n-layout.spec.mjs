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
 * OPT-IN until P2 CSS lands. This gate is RED today — the first pseudo-long run
 * shows the desktop tab strip (.evcc-nav) overflows on every tab and
 * map_config's button rows run off the panel. It defines the P2 target; enable
 * it with I18N_LAYOUT=1 while doing the CSS hardening, and PROMOTE it into the
 * default VISUAL suite (delete the skip below) once it is green. Kept out of the
 * default run so a known-red target doesn't break the green suite prematurely.
 * See memory/project_i18n_rollout.md.
 */
import { test, expect } from "@playwright/test";
import { mountHarness, renderTab, probeLayout, VIEW_ORDER } from "../lib/mount-page.mjs";

const OPT_IN = Boolean(process.env.I18N_LAYOUT);
const WIDTH = 500;

test.describe("i18n layout gate: pseudo-long must not break the layout", () => {
  test.skip(!OPT_IN, "opt-in (I18N_LAYOUT=1) until P2 CSS greens it");

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
