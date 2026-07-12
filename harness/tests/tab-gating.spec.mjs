/**
 * HARNESS — capability tab gating.
 *
 * The desktop header (renderHeader) hides the Base Station nav tab when the
 * adapter reports no dock (snapshot supports_base_station →
 * state.supportsBaseStation()). This mounts the REAL renderHeader via the harness
 * and asserts the button appears by default (Eufy-safe: stub leaves the accessor
 * unstubbed → default-shown) and disappears when the accessor returns false (the
 * Roborock S6 no-dock case). The mobile shell uses the SAME isViewAvailable()
 * predicate, so this also guards that path.
 *
 * (The Map Bounds nav tab this file also used to cover was removed with the
 * mapping split — see docs/dev/11-mapping-system.md §7.)
 */
import { test, expect } from "@playwright/test";
import { mountHarness, renderTab } from "../lib/mount-page.mjs";

function navState(page) {
  return page.evaluate(() => {
    const sr = document.getElementById("evcc-host")?.shadowRoot;
    const has = (view) => Boolean(sr?.querySelector(`.evcc-nav-tab[data-view="${view}"]`));
    return {
      rooms: has("rooms"),
      setup: has("setup"),
      base_station: has("base_station"),
    };
  });
}

test.describe("capability tab gating (desktop header)", () => {
  test("shows Base Station by default (Eufy-safe)", async ({ page }) => {
    await mountHarness(page);
    const res = await renderTab(page, "rooms");
    expect(res.ok, res.error).toBe(true);

    const nav = await navState(page);
    expect(nav.base_station).toBe(true);
    // Ungated tabs are always present.
    expect(nav.rooms).toBe(true);
    expect(nav.setup).toBe(true);
  });

  test("hides Base Station when the dock is absent (S6)", async ({ page }) => {
    await mountHarness(page);
    // Override fns must be defined IN-PAGE (page.evaluate can't serialize them).
    const res = await page.evaluate(() => window.__evcc.render("rooms", {
      overrides: {
        supportsBaseStation: () => false,
      },
    }));
    expect(res.ok, res.error).toBe(true);

    const nav = await navState(page);
    expect(nav.base_station).toBe(false);
    // Only the gated tab goes; everything else stays.
    expect(nav.rooms).toBe(true);
    expect(nav.setup).toBe(true);
  });
});
