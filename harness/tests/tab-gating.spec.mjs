/**
 * HARNESS — capability tab gating.
 *
 * The desktop header (renderHeader) hides the Base Station + Map Bounds nav tabs
 * when the adapter reports no dock / no CV map (snapshot supports_base_station /
 * supports_map_bounds → state.supportsBaseStation()/supportsMapBounds()). This
 * mounts the REAL renderHeader via the harness and asserts the buttons appear by
 * default (Eufy-safe: stub leaves the accessors unstubbed → default-shown) and
 * disappear when the accessors return false (the Roborock S6 case). The mobile
 * shell uses the SAME isViewAvailable() predicate, so this also guards that path.
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
      mapping_review: has("mapping_review"),
    };
  });
}

test.describe("capability tab gating (desktop header)", () => {
  test("shows Base Station + Map Bounds by default (Eufy-safe)", async ({ page }) => {
    await mountHarness(page);
    const res = await renderTab(page, "rooms");
    expect(res.ok, res.error).toBe(true);

    const nav = await navState(page);
    expect(nav.base_station).toBe(true);
    expect(nav.mapping_review).toBe(true);
    // Ungated tabs are always present.
    expect(nav.rooms).toBe(true);
    expect(nav.setup).toBe(true);
  });

  test("hides Base Station + Map Bounds when capabilities are false (S6)", async ({ page }) => {
    await mountHarness(page);
    // Override fns must be defined IN-PAGE (page.evaluate can't serialize them).
    const res = await page.evaluate(() => window.__evcc.render("rooms", {
      overrides: {
        supportsBaseStation: () => false,
        supportsMapBounds: () => false,
      },
    }));
    expect(res.ok, res.error).toBe(true);

    const nav = await navState(page);
    expect(nav.base_station).toBe(false);
    expect(nav.mapping_review).toBe(false);
    // Only the two gated tabs go; everything else stays.
    expect(nav.rooms).toBe(true);
    expect(nav.setup).toBe(true);
  });

  test("hides only Base Station when just the dock is absent", async ({ page }) => {
    await mountHarness(page);
    const res = await page.evaluate(() => window.__evcc.render("rooms", {
      overrides: { supportsBaseStation: () => false },
    }));
    expect(res.ok, res.error).toBe(true);

    const nav = await navState(page);
    expect(nav.base_station).toBe(false);
    expect(nav.mapping_review).toBe(true); // CV map still present
    expect(nav.rooms).toBe(true);
  });
});
