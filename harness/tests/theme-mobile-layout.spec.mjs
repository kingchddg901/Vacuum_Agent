/**
 * LAYOUT GATE — theme editor at phone width.
 *
 * WHY THIS EXISTS
 * ---------------
 * e6bc123 made the Theme view picking-only on mobile, so the Palette/Tokens
 * editors were never REACHABLE below 600px and no gate covered them there. The
 * MOBILE_TOKEN_EDITOR test build (renderers/theme.js) makes them reachable —
 * which means it made a surface live at a width nothing measures. The existing
 * POPULATED @390 block in i18n-layout.spec.mjs covers rooms / room_rules /
 * metrics / learning_review / maintenance, and deliberately not theme.
 *
 * WHAT IT ASSERTS, AND WHY IT IS NOT probeLayout ALONE
 * ----------------------------------------------------
 * The first version of this gate failed on probeLayout's per-element overflow
 * and on shellOverflow. Both were the wrong signal, and the view proved it:
 *
 *              signal | 390 broken | 500 working | 390 fixed
 *       shellOverflow |          0 |           0 |         0
 *  alpha-shell culprits|        454 |         454 |       454
 *     right-edge bleed |         30 |           0 |         0
 *
 * .evcc-shell is overflow:hidden, so content wider than the card is CLIPPED,
 * not overflowed — the card was visibly cut off (search box, preview copy and
 * "Save Changes" all sliced) while every overflow-based number read clean. A
 * gate that cannot tell broken from working is worse than no gate, because it
 * reads as coverage.
 *
 * So the gate FAILS on right-edge bleed, the only signal that separates the
 * two, and keeps per-element overflow as a SECOND assertion minus known
 * deliberate overhangs. That second check is not decoration: it is what caught
 * .evcc-chip-icon resolving to 12.5px around a 20px glyph — every footer icon
 * overflowing its own box, invisible on screen because overflow-x is visible.
 *
 * If MOBILE_TOKEN_EDITOR is reverted to false this test still passes (the view
 * degrades to the presets grid, which already fits), so it is safe to keep
 * either way — and it is REQUIRED if the flag ever ships on.
 */
import { test, expect } from "@playwright/test";
import { mountHarness, probeLayout, probeBleed } from "../lib/mount-page.mjs";

/**
 * Boxes that report scrollWidth > clientWidth ON PURPOSE.
 *
 * Keep this list SHORT and justified. Every entry is a place the second
 * assertion has been told to look away, so an unjustified one silently buys
 * back the blindness this gate was rewritten to remove.
 */
const DELIBERATE_OVERHANG = [
  // .token-alpha-shell — the % bubble is centred on the slider thumb
  // (translateX(-50%)), so at either end of the range half of it sits past the
  // rail end. overflow-x is visible, nothing is clipped, and the pill reads
  // correctly on-device in every locale checked. 454 of these were the entire
  // output of this gate while the view was BOTH broken and working, which is
  // exactly what proved the old assertion could not tell them apart.
  "token-alpha-shell",
];

for (const width of [390, 500]) {
  test.describe(`theme editor layout @${width}px`, () => {
    test.use({ viewport: { width, height: 900 } });

    for (const tab of ["tokens", "palette"]) {
      test(`theme/${tab} fits the card`, async ({ page }) => {
        await mountHarness(page);
        // REAL frame, not the synthetic one. The synthetic path never builds
        // main.js's own shell / ResizeObserver / mobile chrome, and the codebase
        // already attributes "a layout probe that shipped unproven" to that gap.
        // A mobile layout gate is a question ABOUT the frame, so it must use the
        // frame the user actually gets.
        const res = await page.evaluate(
          (o) => window.__evcc.mountRealThemeEditor(null, o),
          { width, subTab: tab },
        );
        expect(res.ok, res.error).toBe(true);

        // GUARD THE FIXTURE, NOT JUST THE LAYOUT.
        // The first version of this gate used renderTab, whose STUB state supplies
        // no theme data: the editor body rendered EMPTY, probeLayout reported a
        // clean 388px shell, and four tests passed having measured nothing — while
        // the real device clipped the search box, the preview copy and the footer.
        // A layout gate that cannot see its own subject is worse than no gate.
        // So assert the editor is actually populated before believing any verdict.
        expect(res.viewport,
          `card did not enter the mobile viewport at ${width}px — the mobile chrome ` +
          `under test is not active`).toBe("mobile");
        expect(res.scrollbox,
          `theme/${tab} rendered no .evcc-theme-editor-scrollbox — the fixture is not ` +
          `driving the editor, so this gate measures nothing`).toBeGreaterThan(0);
        expect(res.tokenRows,
          `theme/${tab} rendered 0 token rows out of ${res.tokenCount} registry tokens — ` +
          `empty editor, nothing measured`).toBeGreaterThan(0);

        // PRIMARY — nothing may stick out past the card's right edge. This is
        // the symptom a user sees, and the only signal that moved when the
        // view went from broken to fixed.
        const bleed = await probeBleed(page);
        const bleedLines = bleed.origins
          .map((o) => `  +${o.past}px past  w=${o.width}  ${o.tag}.${o.cls}  ${JSON.stringify(o.text)}`)
          .join("\n");
        expect(
          bleed.origins.length,
          `theme/${tab} @${width}: ${bleed.total} element(s) extend past the ` +
          `${bleed.shellWidth}px card edge. Bleed ORIGINS (a box wider than its ` +
          `parent — everything under one has just inherited the width):\n${bleedLines}`,
        ).toBe(0);

        // SECONDARY — a box holding more than it can show. Not the primary
        // signal, but it is what found the icon-box defect, so it stays.
        const probe = await probeLayout(page);
        const unexpected = (probe.culprits || [])
          .filter((c) => !DELIBERATE_OVERHANG.some((d) => (c.cls || "").includes(d)));
        const overLines = unexpected
          .map((c) => `  +${c.ov}px  ${c.tag}.${c.cls}  ${JSON.stringify(c.text)}`)
          .join("\n");
        expect(
          unexpected.length,
          `theme/${tab} @${width}: box(es) hold more content than they can show, ` +
          `beyond the ${DELIBERATE_OVERHANG.length} known deliberate overhang(s). ` +
          `shellOverflow=${probe.shellOverflow}px:\n${overLines}`,
        ).toBe(0);
      });
    }
  });
}
