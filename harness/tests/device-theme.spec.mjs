/**
 * Per-device theme resolution (the browser-local theme selection). Drives the
 * REAL VacuumCardState through effectiveActiveThemeId() — the safe fallback chain
 * that a render-only screenshot can't assert. The first case is the regression
 * guard for the "device pin self-wipes before the library loads" blocker.
 *
 * (localStorage is denied at the harness's about:blank origin and the state
 * try/catches it, so persistence is a no-op here — this exercises the in-memory
 * resolution, which is where the bug lived.)
 */
import { test, expect } from "@playwright/test";
import { mountHarness } from "../lib/mount-page.mjs";

test("effectiveActiveThemeId: pin survives pre-load, resolves when loaded, clears only when genuinely stale", async ({ page }) => {
  await mountHarness(page);
  const r = await page.evaluate(() => {
    const S = window.__evcc.VacuumCardState;
    const lib = {
      theme_a: { id: "theme_a", name: "A", colors: {} },
      theme_pin: { id: "theme_pin", name: "Pin", colors: {} },
    };
    const s = new S({}, { vacuum_entity_id: "v1" });
    s.applyThemeActivation("theme_a"); // backend active

    // (1) BEFORE the library loads (still {}), device-pinned to a theme not yet present.
    s.setThemeMode("device");
    s.setDeviceThemeId("theme_pin");
    const preLoad = s.effectiveActiveThemeId();      // must fall back WITHOUT clearing
    const pinAfterPreLoad = s.getDeviceThemeId();

    // (2) library loads WITH the pin -> resolves to the pin.
    s.setThemeLibrary({ library: lib, default_theme_id: "theme_a" });
    const loaded = s.effectiveActiveThemeId();
    const pinStillSet = s.getDeviceThemeId();

    // (3) pin a theme genuinely absent from a LOADED library -> stale -> cleared.
    s.setDeviceThemeId("theme_gone");
    const stale = s.effectiveActiveThemeId();
    const pinAfterStale = s.getDeviceThemeId();

    return { preLoad, pinAfterPreLoad, loaded, pinStillSet, stale, pinAfterStale };
  });

  // (1) the blocker: pre-load falls back to the backend active but KEEPS the pin.
  expect(r.preLoad).toBe("theme_a");
  expect(r.pinAfterPreLoad).toBe("theme_pin");
  // (2) loaded + valid -> resolves to the pin.
  expect(r.loaded).toBe("theme_pin");
  expect(r.pinStillSet).toBe("theme_pin");
  // (3) loaded + stale -> cleared + falls back.
  expect(r.stale).toBe("theme_a");
  expect(r.pinAfterStale).toBeNull();
});
