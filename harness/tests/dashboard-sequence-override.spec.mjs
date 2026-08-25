/**
 * THE STANDALONE DASHBOARD CARD's sequence-override row — is it styled at all?
 *
 * ⚠ WHY THIS FILE EXISTS. The `.soro-*` rules lived in `src/styles/rooms.js` from
 * the day the row shipped, and could never apply to this card: `vacuum-agent-
 * dashboard` attaches its OWN shadow root and injects only `CARD_CSS + LANG_CSS`
 * (dashboard-card.js), so the panel's stylesheet cannot reach it. Shadow DOM
 * encapsulation, not a bundler oversight. The row therefore rendered as BARE DIVS
 * on this surface for its entire life, and the only colour on it came from the
 * generic `.chip.active` — i.e. the theme accent, which is amber on the
 * maintainer's theme. That is the exact reported symptom ("amber for a match"),
 * on the surface nobody was looking at.
 *
 * TWO COMMITS "FIXED" IT BY EDITING THE PANEL STYLESHEET, and one of them said so
 * in its message. Nothing went red, because:
 *   * `harness/tests/sequence-override.spec.mjs` mounts the PANEL and asserts on
 *     `.evcc-sequence-override`; it never touches this element.
 *   * `CARD_STATES` carries no `switch.*_clean_order_override` and no
 *     `sensor.*_clean_order`, so even the existing card mounts render the row as
 *     an empty string — `findOverrideSwitch` returns null and the renderer bails.
 *
 * So the assertion here is deliberately the crude one: the row's boxes must have
 * a PAINTED background. An unstyled div computes `rgba(0, 0, 0, 0)`, and that
 * single check is what the last two style commits needed and did not have. The
 * semantic colour is asserted on top of it.
 */
import { test, expect } from "@playwright/test";

import { mountHarness, mountCard } from "../lib/mount-page.mjs";

const VAC = "vacuum.alfred";

/**
 * The two entities the row needs, neither of which the shared fixture carries.
 *
 * The switch id is deliberately NOT `switch.alfred_clean_order_override`: Home
 * Assistant composed the bare device name on real hardware and entity ids are
 * sticky, so the card finds this by attribute scan. A predictably-named fixture
 * would quietly stop exercising the lookup the live card depends on.
 */
function overrideStates({ on, sensorState, status, order, orderNames }) {
  return {
    "switch.alfred_seq_2": {
      entity_id: "switch.alfred_seq_2",
      state: on ? "on" : "off",
      attributes: { vacuum_entity_id: VAC, role: "clean_order_override" },
    },
    "sensor.alfred_clean_order": {
      entity_id: "sensor.alfred_clean_order",
      state: sensorState,
      attributes: { status, order, order_names: orderNames, read_at: null },
    },
  };
}

/** Mount the card, then re-set hass with the override entities merged in. */
async function mountWithRow(page, extra) {
  const mounted = await mountCard(page, "dashboard", { freeze: true });
  expect(mounted.ok, mounted.error).toBe(true);

  return page.evaluate(async (states) => {
    const el = document.querySelector("vacuum-agent-dashboard");
    if (!el) return { ok: false, error: "card element not found" };
    // `hass` is a WRITE-ONLY accessor on these cards (a setter, no getter), so
    // reading el.hass gives undefined and `prev` would be {} — which silently
    // DESTROYS every fixture state on the way back in, leaving no room switches
    // and therefore no row at all. Read the internal the setter wrote to.
    const prev = el._hass || {};
    el.hass = { ...prev, states: { ...(prev.states || {}), ...states } };
    // The card re-renders off the hass setter; give it a frame to land before
    // reading the shadow tree, or every assertion below reads the PREVIOUS render.
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));

    const root = el.shadowRoot;
    const row = root?.querySelector(".sequence-override") ?? null;
    if (!row) return { ok: true, row: null };

    // Resolve the card's own status tokens THROUGH ITS SHADOW ROOT, so the
    // expectation follows the palette instead of hard-coding a hex. These are
    // mapped on :host with literal fallbacks precisely because a standalone card
    // has no --evcc-* in its ancestry.
    const probe = document.createElement("span");
    row.appendChild(probe);
    const resolve = (expr) => { probe.style.background = ""; probe.style.background = expr; return getComputedStyle(probe).backgroundColor; };
    const palette = {
      success: resolve("var(--status-success-bg)"),
      warning: resolve("var(--status-warning-bg)"),
    };
    probe.remove();

    const box = root.querySelector(".soro-green, .soro-amber, .soro-grey");
    return {
      ok: true,
      row: {
        rowBg: getComputedStyle(row).backgroundColor,
        rowBorder: getComputedStyle(row).borderTopWidth,
        boxClass: box ? [...box.classList].find((c) => c.startsWith("soro-")) : null,
        boxBg: box ? getComputedStyle(box).backgroundColor : null,
      },
      palette,
    };
  }, extra);
}

const TRANSPARENT = "rgba(0, 0, 0, 0)";

test.describe("standalone dashboard card: sequence-override row", () => {
  test("the row is STYLED at all — not bare divs", async ({ page }) => {
    await mountHarness(page);
    const res = await mountWithRow(page, overrideStates({
      on: true, sensorState: "2", status: "ok", order: [1, 2], orderNames: ["Kitchen", "Living Room"],
    }));

    expect(res.ok, res.error).toBe(true);
    expect(res.row, "the row did not render — the card fixture is missing the override switch again").not.toBeNull();

    // THE CRUX. `.sequence-override` lived in the panel's stylesheet, so on this
    // element it computed to nothing at all. Transparent here means the rules did
    // not reach this shadow root, whatever any commit message claims.
    expect(res.row.rowBg, "the row container has no background — its rules are not in this shadow root").not.toBe(TRANSPARENT);
    expect(res.row.rowBorder, "the row container has no border").not.toBe("0px");
  });

  test("the verification box carries its semantic colour, not the accent", async ({ page }) => {
    await mountHarness(page);
    const res = await mountWithRow(page, overrideStates({
      on: true, sensorState: "2", status: "ok", order: [1, 2], orderNames: ["Kitchen", "Living Room"],
    }));

    expect(res.ok, res.error).toBe(true);
    expect(res.row, "the row did not render").not.toBeNull();
    expect(res.row.boxClass, "no verification box rendered at all").not.toBeNull();
    expect(res.row.boxBg, "the verification box is unpainted").not.toBe(TRANSPARENT);

    // Whichever state it landed in, its fill must be that state's token — never a
    // colour borrowed from somewhere else.
    const expected = res.row.boxClass === "soro-green" ? res.palette.success
      : res.row.boxClass === "soro-amber" ? res.palette.warning
      : null;
    if (expected) {
      expect(res.row.boxBg, `${res.row.boxClass} must use its own status token`).toBe(expected);
    }
  });
});
