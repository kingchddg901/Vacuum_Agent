/**
 * [SHL-*] A box-shadow TOKEN RENDERS AS A LAYER LIST.
 *
 * THE FIXTURE IS REAL DATA. The values below were read off a live install's saved theme,
 * not invented: one theme of 31 sets shadows at all, and 5 of its 8 values are stacks.
 * That is why this control is a list rather than five fields, and it is why the spec
 * drives it with a THREE-layer value — the shape a flat control could not express.
 *
 * WHAT A STRING TEST COULD NOT SEE, and so why this is a harness spec: whether the row
 * actually renders N blocks with the parts filled from the stored value, and whether any
 * part carries `data-theme-token`. That last one is the sharp edge — that attribute means
 * "my value IS the token's value", so a single length field carrying it would make the
 * generic input handler overwrite the whole shadow with "2px" on the first blur. It is
 * invisible to every unit test and obvious here.
 *
 * Coverage
 * --------
 * [SHL-1] a 3-layer value renders 3 blocks, with the four lengths split out per layer
 * [SHL-2] a value the control cannot round-trip keeps the plain text box
 * [SHL-3] no shadow part carries data-theme-token
 * [SHL-4] reorder controls exist and are omitted where they would do nothing
 */
import { test, expect } from "@playwright/test";
import { mountHarness } from "../lib/mount-page.mjs";
// NOT imported here. Playwright's loader treats a typeless .js as CommonJS, so a named
// import of shadow-value.js throws at collection -- measured, "No tests found". The real
// formatter is reached IN-PAGE as window.__evcc.formatShadow, which mount-entry.js
// exposes for exactly this reason (the same note sits beside flattenLocale there).

/** Every shadow value the one theme on a live install that sets them actually carries.
 *  "Black One" — 155 tokens, 8 of them shadows, and the only theme with more than one.
 *  Read 2026-11-16 from .storage, read-only. THIS is the differential instrument: as
 *  things change underneath these tokens, the values must not move. */
const BLACK_ONE = {
  "--evcc-drag-shadow": "0 10px 28px rgba(0,0,0,0.68), 0 0 0 1px rgba(201,84,30,0.38)",
  "--evcc-learning-panel-shadow": "0 1px 2px rgba(0,0,0,0.50), 0 4px 12px rgba(0,0,0,0.36)",
  "--evcc-modal-shadow": "0 24px 64px rgba(0,0,0,0.78)",
  "--evcc-queue-current-glow": "0 0 0 1px rgba(201,84,30,0.58), 0 0 18px rgba(201,84,30,0.28)",
  "--evcc-queue-inferred-glow": "0 0 0 1px rgba(94,124,147,0.42)",
  "--evcc-shadow-card": "0 1px 2px rgba(0,0,0,0.62), 0 6px 18px rgba(0,0,0,0.50)",
  "--evcc-shadow-hover":
    "0 2px 4px rgba(0,0,0,0.66), 0 14px 34px rgba(0,0,0,0.58), 0 0 0 1px rgba(201,84,30,0.26)",
  "--evcc-status-dot-shadow": "0 0 8px rgba(201,84,30,0.55)",
};

/** Read 2026-11-16 from the live install. Three layers: two blurs and a 1px ring. */
const REAL_STACK =
  "0 2px 4px rgba(0,0,0,0.66), 0 14px 34px rgba(0,0,0,0.58), 0 0 0 1px rgba(201,84,30,0.26)";
/** A deliberate reference the control must NOT rewrite. */
const REFERENCE = "var(--evcc-shadow-hover, 0 12px 30px rgba(0,0,0,0.28))";

async function probe(page, tokens) {
  await mountHarness(page);
  return page.evaluate((tok) => {
    const res = window.__evcc.renderThemeEditor(
      [{ id: "t1", name: "shadow fixture", tokens: tok, colors: {}, alpha: {} }],
      { width: 1400, activeThemeId: "t1" },
    );
    const root = document
      .getElementById("evcc-host")
      ?.shadowRoot?.querySelector("[data-evcc-view-root]");

    const rowFor = (key) => {
      const anyPart = root?.querySelector(`[data-shadow-token="${key}"]`);
      const row = anyPart ? anyPart.closest(".evcc-token-row") : null;
      const textBox = root?.querySelector(`input[data-theme-token="${key}"]`);
      if (!row) return { mode: textBox ? "text" : "absent", textValue: textBox?.value ?? null };
      const layers = [...row.querySelectorAll(".token-shadow-layer")].map((L) => {
        const part = (p) => L.querySelector(`[data-shadow-part="${p}"]`);
        return {
          x: part("x")?.value, y: part("y")?.value,
          blur: part("blur")?.value, spread: part("spread")?.value,
          color: part("color")?.value, inset: part("inset")?.checked,
          up: !!L.querySelector('[data-shadow-move="up"]'),
          down: !!L.querySelector('[data-shadow-move="down"]'),
          remove: !!L.querySelector("[data-shadow-remove]"),
        };
      });
      return {
        mode: "layers",
        layers,
        addButtons: row.querySelectorAll("[data-shadow-add]").length,
        // THE SHARP EDGE: a part carrying data-theme-token would be eaten by the
        // generic handler. Count them inside this row.
        partsWithTokenAttr: row.querySelectorAll("[data-shadow-part][data-theme-token]").length,
      };
    };

    return {
      ok: res.ok === true,
      error: res.error ? String(res.error) : null,
      stack: rowFor("--evcc-shadow-hover"),
      reference: rowFor("--evcc-shadow-card"),
    };
  }, tokens);
}

test.describe("box-shadow layer list", () => {
  test("[SHL-1..4] a real stacked value becomes editable layers", async ({ page }) => {
    const r = await probe(page, {
      "--evcc-shadow-hover": REAL_STACK,
      "--evcc-shadow-card": REFERENCE,
    });
    expect(r.ok, `renderThemeEditor failed: ${r.error}`).toBe(true);

    /* ---- [SHL-1] three layers, parts split out ---- */
    expect(r.stack.mode, "the stacked value should have rendered layer blocks").toBe("layers");
    expect(r.stack.layers.length, "a 3-layer value must render 3 blocks").toBe(3);

    // Layer 2 is a blur; layer 3 is the 1px RING. The difference between them lives
    // entirely in blur-vs-spread, which is exactly what a flat control conflates.
    expect(r.stack.layers[1]).toMatchObject({ x: "0", y: "14px", blur: "34px", spread: "" });
    expect(r.stack.layers[2]).toMatchObject({ x: "0", y: "0", blur: "0", spread: "1px" });
    expect(r.stack.layers[2].color).toBe("rgba(201,84,30,0.26)");
    expect(r.stack.layers.every((L) => L.inset === false)).toBe(true);
    expect(r.stack.addButtons, "exactly one Add layer button per row").toBe(1);

    /* ---- [SHL-3] the sharp edge ---- */
    expect(
      r.stack.partsWithTokenAttr,
      "a shadow part carrying data-theme-token would let the generic input handler " +
      "overwrite the whole shadow with one length",
    ).toBe(0);

    /* ---- [SHL-4] reorder controls where they mean something ---- */
    expect(r.stack.layers.map((L) => L.up), "no Move-up on the first layer").toEqual([false, true, true]);
    expect(r.stack.layers.map((L) => L.down), "no Move-down on the last layer").toEqual([true, true, false]);
    expect(r.stack.layers.every((L) => L.remove), "every layer is removable").toBe(true);

    /* ---- [SHL-2] a reference keeps the text box ---- */
    expect(
      r.reference.mode,
      "a var() reference must NOT be decomposed - rewriting it would destroy the link",
    ).toBe("text");
    expect(r.reference.textValue).toBe(REFERENCE);
  });
});

test("[SHL-5] every shadow 'Black One' stores survives a round trip through the UI", async ({ page }) => {
  // THE DIFFERENTIAL INSTRUMENT, and Chris's point about why his box is useful: one theme
  // on a real install sets 8 shadows, and it is the only theme that sets more than one.
  // So those 8 strings are the population this control has to not break. The invariant is
  // the strongest one available without a session: read the value into the fields, read
  // the fields back out through the SHIPPED formatter, and get the same string.
  //
  // THE RED INPUT is any change under these tokens that alters a stored value on the way
  // through the editor -- a dropped spread, a normalised colour, a lost layer. None of
  // that reddens a single unit test, because the unit tests feed the parser directly and
  // never go through the DOM.
  await mountHarness(page);
  const r = await page.evaluate((tokens) => {
    const res = window.__evcc.renderThemeEditor(
      [{ id: "t1", name: "Black One", tokens, colors: {}, alpha: {} }],
      { width: 1400, activeThemeId: "t1" },
    );
    const root = document
      .getElementById("evcc-host")
      ?.shadowRoot?.querySelector("[data-evcc-view-root]");

    const out = {};
    for (const key of Object.keys(tokens)) {
      const anyPart = root?.querySelector(`[data-shadow-token="${key}"]`);
      if (!anyPart) {
        const tb = root?.querySelector(`input[data-theme-token="${key}"]`);
        out[key] = { mode: tb ? "text" : "absent", value: tb?.value ?? null };
        continue;
      }
      const row = anyPart.closest(".evcc-token-row");
      const layers = [...row.querySelectorAll(".token-shadow-layer")].map((L) => {
        const p = (n) => L.querySelector(`[data-shadow-part="${n}"]`);
        return {
          inset: !!p("inset")?.checked,
          x: p("x")?.value ?? "", y: p("y")?.value ?? "",
          blur: p("blur")?.value ?? "", spread: p("spread")?.value ?? "",
          color: p("color")?.value ?? "",
        };
      });
      // The SHIPPED formatter, reached in-page. A copy of the join written here would be
      // comparing the UI against the test's idea of the rule.
      out[key] = { mode: "layers", layerCount: layers.length,
                   recomposed: window.__evcc.formatShadow(layers) };
    }
    return { ok: res.ok === true, error: res.error ? String(res.error) : null, out };
  }, BLACK_ONE);

  expect(r.ok, `renderThemeEditor failed: ${r.error}`).toBe(true);

  // SAMPLE CHECK: all 8 must have reached the layer control. If any fell back to a text
  // box the assertions below would pass trivially for it while the control did nothing.
  const modes = Object.fromEntries(Object.entries(r.out).map(([k, v]) => [k, v.mode]));
  expect(modes, "every one of Black One's shadows must get the layer control").toEqual(
    Object.fromEntries(Object.keys(BLACK_ONE).map((k) => [k, "layers"])),
  );

  for (const [key, stored] of Object.entries(BLACK_ONE)) {
    expect(r.out[key].recomposed, `${key} did not survive the round trip`).toBe(stored);
  }

  // The measured layer mix, so this cannot quietly become eight single-layer values.
  expect(Object.values(r.out).map((v) => v.layerCount).sort()).toEqual([1, 1, 1, 2, 2, 2, 2, 3]);
});
