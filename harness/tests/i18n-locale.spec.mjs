/**
 * I18N LOCALE SWITCH — regression guard for the renderers.t language wiring.
 *
 * proto._i18nLanguage must read the language off the card the renderers are
 * bound to (this.card._hass) — render-cycle.js calls `renderers.t(...)` on the
 * VacuumCardRenderers INSTANCE, whose only own field is `this.card`. Reading
 * `this._hass` (undefined on the instance) pinned EVERY renderer string to
 * English regardless of the user's HA language, and NOTHING caught it because
 * the visual harness only ever rendered English and the i18n gate tests
 * translate() directly, bypassing this wiring.
 *
 * This test renders a tab under a registered foreign catalog and asserts the UI
 * actually switches — so a re-break of the wiring fails HERE instead of
 * silently shipping an English-only card to non-English users.
 */
import { test, expect } from "@playwright/test";
import { mountHarness, renderTab } from "../lib/mount-page.mjs";

// A tiny foreign catalog with sentinel values for two keys the rooms tab
// renders (a nav tab label + the empty-state body).
const FOREIGN = {
  "nav.tab_rooms": "ZZ_ROOMS_LABEL",
  "rooms.empty": "ZZ_ROOMS_EMPTY",
};

const shadowHtml = (page) =>
  page.evaluate(() => {
    const host = document.getElementById("evcc-host");
    return host && host.shadowRoot ? host.shadowRoot.innerHTML : "";
  });

test.describe("i18n: renderers resolve the user's language", () => {
  test("a registered locale switches rendered renderer strings", async ({ page }) => {
    await mountHarness(page);
    await page.evaluate((cat) => window.__evcc.registerLocale("zz", cat), FOREIGN);

    const res = await renderTab(page, "rooms", { lang: "zz" });
    expect(res.ok, res.error).toBe(true);

    const html = await shadowHtml(page);
    // Foreign strings must appear → renderers.t read the seeded
    // hass.locale.language, not a hardcoded English.
    expect(html, "renderer string did not switch to the registered locale").toContain("ZZ_ROOMS_LABEL");
    expect(html).toContain("ZZ_ROOMS_EMPTY");
  });

  test("default (no lang) still renders English", async ({ page }) => {
    await mountHarness(page);
    await page.evaluate((cat) => window.__evcc.registerLocale("zz", cat), FOREIGN);

    const res = await renderTab(page, "rooms"); // no lang → stub coerces to English
    expect(res.ok, res.error).toBe(true);

    const html = await shadowHtml(page);
    expect(html, "default render leaked the foreign locale").not.toContain("ZZ_ROOMS_LABEL");
    expect(html, "English fallback missing").toContain("No rooms yet");
  });
});
