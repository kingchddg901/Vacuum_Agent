/**
 * [TIN-*] THE TOKEN EDITOR'S FREE-TEXT BOXES SAY WHAT THEY WANT — issue #83.
 *
 * WHAT WAS REPORTED. The reporter opened the theme editor, found rows reading
 * "Frame Shadow · Default", "Header Padding · Default", "Row Padding · Default",
 * "Section Padding · Default" and asked what they did. The honest answer was that the
 * control told him nothing: `placeholder="Default"` states that an empty box uses the
 * default and NOTHING about what may go in it — not the format, not the units, not that
 * blank inherits rather than zeroes. The sliders beside them all show a number and a
 * range; these four showed an empty box.
 *
 * WHY A HARNESS SPEC AND NOT A TEXT ASSERTION. The theme editor is one of the few
 * surfaces in this repo a browser CAN reach: `renderThemeEditor` builds a real
 * VacuumCardState and renders the real token list, so these assertions read the DOM the
 * user reads rather than the source that produces it. A grep for the placeholder string
 * would pass on a row that never rendered.
 *
 * [TIN-3] IS THE ONE THAT MATTERS MOST and it is easy to leave out. A fix that gave
 * EVERY free-text box the length hint would satisfy [TIN-1] and [TIN-2] completely while
 * telling a user editing a gradient that it wants "12px 16px". The `lengths` type exists
 * precisely so the hint can be accurate, and [TIN-3] is what proves the dispatch
 * discriminates instead of blanket-replacing.
 *
 * Coverage
 * --------
 * [TIN-1] a `lengths` token's box carries the length hint
 * [TIN-2] a `shadow` token's box carries the shadow hint
 * [TIN-3] a plain `text` token still carries the generic placeholder
 * [TIN-4] the token list states, once, that these are not HA theme variables
 * [TIN-5] the Unsaved-only checkbox uses a real boolean attribute, not a Lit binding
 */
import { test, expect } from "@playwright/test";
import { mountHarness } from "../lib/mount-page.mjs";

/** Render the real token editor and report everything these five tests need, in one go. */
async function probe(page) {
  await mountHarness(page);
  return page.evaluate(() => {
    const res = window.__evcc.renderThemeEditor(null, { width: 1400 });
    const root = document
      .getElementById("evcc-host")
      ?.shadowRoot?.querySelector("[data-evcc-view-root]");

    const box = (key) => {
      const el = root?.querySelector(`[data-theme-token="${key}"]`);
      if (!el) return null;
      return { tag: el.tagName.toLowerCase(), type: el.type, placeholder: el.getAttribute("placeholder") };
    };

    const cb = root?.querySelector("[data-theme-modified-only]");

    return {
      ok: res.ok === true,
      error: res.error ? String(res.error) : null,
      tokenCount: res.tokenCount ?? null,
      // SAMPLE CHECK: how many token boxes rendered at all. A zero here makes every
      // assertion below vacuous, so it is asserted first.
      renderedTokenInputs: root?.querySelectorAll("[data-theme-token]").length ?? 0,
      lengths: box("--evcc-card-row-padding"),
      lengthsSpace: box("--evcc-space-md"),
      shadow: box("--evcc-card-frame-shadow"),
      plainText: box("--evcc-learning-anim-ease"),
      hintText: [...(root?.querySelectorAll(".evcc-token-hint-sticky") ?? [])]
        .map((e) => e.textContent.trim()).join(" | "),
      checkbox: cb ? { tag: cb.tagName.toLowerCase(), attrs: [...cb.attributes].map((a) => a.name) } : null,
    };
  });
}

test.describe("theme token inputs: the box says what it wants", () => {
  test("[TIN-1..5] placeholders by type, the scope hint, and no Lit binding", async ({ page }) => {
    const r = await probe(page);

    expect(r.ok, `renderThemeEditor failed: ${r.error}`).toBe(true);

    // THE FLOOR. Without this a broken render reports a clean pass having measured
    // nothing — the same shape smoke.spec.mjs exists to warn about.
    expect(
      r.renderedTokenInputs,
      `the token editor rendered ${r.renderedTokenInputs} token inputs (registry: ${r.tokenCount}), ` +
      "so nothing below measured anything",
    ).toBeGreaterThan(20);

    /* ---- [TIN-1] a lengths token ---- */
    expect(r.lengths, "--evcc-card-row-padding did not render a token input").not.toBeNull();
    expect(
      r.lengths.placeholder,
      "a CSS length-list box must show an example, not the bare word 'Default'",
    ).toMatch(/12px\s+16px/);
    // The same must hold for the spacing family one chip away — the identical control,
    // and leaving it out is the partial-guard shape this repo keeps paying for.
    expect(r.lengthsSpace, "--evcc-space-md did not render a token input").not.toBeNull();
    expect(r.lengthsSpace.placeholder).toBe(r.lengths.placeholder);

    /* ---- [TIN-2] a shadow token ---- */
    expect(r.shadow, "--evcc-card-frame-shadow did not render a token input").not.toBeNull();
    expect(
      r.shadow.placeholder,
      "a box that takes a full CSS box-shadow must show one",
    ).toMatch(/\brgba?\(/);

    /* ---- [TIN-3] the discriminator ---- */
    expect(r.plainText, "--evcc-learning-anim-ease did not render a token input").not.toBeNull();
    expect(
      r.plainText.placeholder,
      "a plain text token (an easing, a gradient) must NOT be told it wants CSS lengths — " +
      "that is what the `lengths` type is for",
    ).not.toMatch(/12px|rgba?\(/);
    expect(r.plainText.placeholder).not.toBe(r.lengths.placeholder);
    expect(r.plainText.placeholder).not.toBe(r.shadow.placeholder);

    /* ---- [TIN-4] the scope hint ---- */
    // The reporter was editing HA theme YAML and watching this list for his changes.
    // They could never appear, and nothing said so.
    expect(
      r.hintText,
      "the token list must state once that these are not Home Assistant theme variables",
    ).toMatch(/Home Assistant/i);

    /* ---- [TIN-5] no Lit binding in a string-into-innerHTML renderer ---- */
    // THE RED INPUT: restoring `?checked="${state.modifiedOnly}"`. Measured on a real
    // upgraded ha-checkbox: that leaves `.checked` false and the element carrying an
    // attribute literally named `?checked`, so the box never rendered ticked. These
    // renderers return HTML strings; Lit bindings are inert in them.
    expect(r.checkbox, "the Unsaved-only checkbox did not render").not.toBeNull();
    const litAttrs = r.checkbox.attrs.filter((a) => a.startsWith("?") || a.startsWith("."));
    expect(
      litAttrs,
      `Lit-style attribute bindings are inert here (found: ${litAttrs.join(", ")}) — ` +
      "use a plain boolean attribute",
    ).toEqual([]);
  });
});
