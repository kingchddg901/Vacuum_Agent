/**
 * SEQUENCE-OVERRIDE ROW — the five states, their colours, and their fit.
 *
 * ⚠ WHY THIS FILE EXISTS. Both defects this gate pins reached a user's phone,
 * and NEITHER was reachable by any existing check — not because the checks are
 * weak, but because THE ROW NEVER RENDERED IN THE HARNESS. It needs a
 * `switch.<vac>_clean_order_override` in `hass.states` to draw anything at all
 * (`findOverrideSwitch` returns null otherwise and the renderer returns ""), and
 * no fixture has ever supplied one. So the i18n layout gate swept the Rooms tab
 * at 390px and 500px under a pseudo-long locale and passed — over an empty
 * string. An unrendered surface yields zero findings and reads exactly like a
 * clean one (f/coverage_from_scopes_not_findings).
 *
 * The two defects, both reported by eye from a 390px screen:
 *
 *   COLOUR. The design names three verification states — amber = checked and
 *   WRONG, green = confirmed, grey = could not check — and en.js labels the
 *   strings "Green state" / "Amber state" / "Grey state". None of it was built.
 *   The renderer emitted `is-<kind>` on the row and no stylesheet consumed the
 *   class, so the only colour present came from the toggle's generic
 *   `.evcc-chip.active`, which resolves to `--evcc-accent`. On a theme whose
 *   accent is amber, a CONFIRMED MATCH rendered as a warning. Note what that
 *   means for testing: the class was right, and asserting the class would have
 *   passed. Only the RESOLVED COLOUR can tell these apart, so that is what is
 *   asserted here.
 *
 *   FIT. `.evcc-rooms-inline-actions` had no `flex-wrap`, so two full-width
 *   buttons ran off the right edge and clipped mid-word. `probeLayout` detects
 *   exactly this shape and always could have — it simply never saw the row.
 *
 * So the overflow half deliberately REUSES probeLayout rather than re-measuring
 * here: the gap was never the predicate, only what it was pointed at.
 */
import { test, expect } from "@playwright/test";

import { mountHarness, probeLayout } from "../lib/mount-page.mjs";

const VAC = "vacuum.alfred";
const OBJ = "alfred";

/** The queue the card believes in, for the states that compare against one. */
const QUEUE = [
  { room_id: 1, name: "KITCHEN", enabled: true, order: 1 },
  { room_id: 2, name: "LIVINGROOM", enabled: true, order: 2 },
  { room_id: 3, name: "Bathroom", enabled: true, order: 3 },
];

/**
 * One `hass.states` map.
 *
 * The switch carries `vacuum_entity_id` + `role` because that is how the card
 * finds it — by attribute scan, not by entity id. Home Assistant composed
 * `switch.alfred` rather than `switch.alfred_clean_order_override` on real
 * hardware, and entity ids are sticky, so the id is deliberately NOT the one the
 * card would guess: a fixture that names it predictably would quietly stop
 * exercising the fallback the live box actually depends on.
 */
function states({ on, sensorState, status, order }) {
  return {
    "switch.alfred_seq_toggle_2": {
      entity_id: "switch.alfred_seq_toggle_2",
      state: on ? "on" : "off",
      attributes: { vacuum_entity_id: VAC, role: "clean_order_override" },
    },
    [`sensor.${OBJ}_clean_order`]: {
      entity_id: `sensor.${OBJ}_clean_order`,
      state: sensorState,
      attributes: {
        status,
        order,
        order_names: order.map(
          (id) => QUEUE.find((r) => r.room_id === id)?.name ?? String(id),
        ),
        read_at: "2026-08-24T20:42:38+00:00",
      },
    },
  };
}

/** The five states the row can be in, and the colour each must resolve to. */
const CASES = [
  {
    kind: "path_optimizing",
    seed: { on: false, sensorState: "0", status: "ok", order: [] },
    // Switch off -> the toggle never takes .active, so there is no active chip.
    expect: "no-active-chip",
  },
  {
    kind: "saved",
    seed: { on: false, sensorState: "3", status: "ok", order: [1, 2, 3] },
    expect: "no-active-chip",
  },
  {
    kind: "matching",
    seed: { on: true, sensorState: "3", status: "ok", order: [1, 2, 3] },
    expect: "success",
  },
  {
    kind: "mismatch",
    seed: { on: true, sensorState: "2", status: "ok", order: [1, 2] },
    expect: "warning",
  },
  {
    kind: "unverifiable",
    seed: { on: true, sensorState: "unknown", status: "never_read", order: [] },
    expect: "neutral",
  },
];

/**
 * Render the Rooms tab with the row present, and report what it drew.
 *
 * Only DATA crosses into the page; the accessor closure is built in-page,
 * because a function cannot survive page.evaluate's structured clone.
 */
function renderRow(page, { seed, width, lang = null, queue = QUEUE }) {
  return page.evaluate(
    ([vid, hassStates, queue, w, lg]) => {
      const res = window.__evcc.render("rooms", {
        width: w,
        freeze: true,
        ...(lg ? { lang: lg } : {}),
        overrides: {
          config: { vacuum_entity_id: vid },
          hass: { states: hassStates },
          getRoomsForActiveMap: () => queue,
        },
      });
      const root = document.getElementById("evcc-host")?.shadowRoot;
      const row = root?.querySelector(".evcc-sequence-override") ?? null;

      // Resolve the palette THROUGH THE DOCUMENT rather than hard-coding hexes,
      // so the assertion states "this is the success colour" and stays true when
      // the palette moves. A probe element is the only way to turn a var() into
      // the same rgb() form getComputedStyle reports for `color`.
      const probe = document.createElement("span");
      row?.appendChild(probe);
      const resolve = (expr) => {
        if (!row) return null;
        probe.style.color = expr;
        return getComputedStyle(probe).color;
      };
      const palette = {
        success: resolve("var(--evcc-sem-success)"),
        warning: resolve("var(--evcc-sem-warning)"),
        accent: resolve("var(--evcc-accent)"),
      };
      probe.remove();

      const activeChip = row?.querySelector(".evcc-chip.active") ?? null;
      return {
        ok: res.ok,
        error: res.error,
        classes: row ? [...row.classList] : null,
        activeChipColor: activeChip ? getComputedStyle(activeChip).color : null,
        actionsWrap: row
          ? getComputedStyle(row.querySelector(".evcc-rooms-inline-actions")).flexWrap
          : null,
        palette,
      };
    },
    [VAC, states(seed), queue, width, lang],
  );
}

const registerPseudo = (page) =>
  page.evaluate(() => window.__evcc.registerLocale("xx", window.__evcc.makePseudoLong()));

test.describe("sequence-override row @390px", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  for (const c of CASES) {
    test(`${c.kind}: renders, fits, and carries the right colour`, async ({ page }) => {
      await mountHarness(page);
      const res = await renderRow(page, { seed: c.seed, width: 390 });

      expect(res.ok, res.error).toBe(true);

      // 1) THE ROW EXISTS. Guarding this first is the point of the file: every
      //    assertion below is vacuous against the empty string the renderer
      //    returns when no override switch is present, which is precisely the
      //    condition under which every other gate has been passing.
      expect(res.classes, "the row did not render at all").not.toBeNull();
      expect(res.classes).toContain(`is-${c.kind}`);

      // 2) FIT. Same predicate the i18n layout gate uses, finally pointed at
      //    this row. Red if flex-wrap is removed from .evcc-rooms-inline-actions.
      //
      //    GEOMETRY FIRST, DECLARATION SECOND, and the order is deliberate.
      //    "The CSS says wrap" is only a preference unless something also shows
      //    the row WOULD overflow without it; asserted first it short-circuits
      //    and hides whether the geometric check can bite at all. Measure what
      //    the browser paints, then pin the property that makes it so.
      const { shellOverflow, culprits } = await probeLayout(page);
      const list = culprits.map((x) => `      +${x.ov}px  ${x.tag}.${x.cls}  "${x.text}"`).join("\n");
      expect(culprits.length, `${c.kind}: ${culprits.length} element(s) overflow their box:\n${list}`).toBe(0);
      expect(shellOverflow, `${c.kind}: card forces ${shellOverflow}px of horizontal scroll`).toBeLessThanOrEqual(2);
      expect(res.actionsWrap, "the action row must wrap").toBe("wrap");

      // 3) COLOUR — the half that asserting the class name cannot do.
      const { success, warning, accent } = res.palette;
      if (c.expect === "no-active-chip") {
        expect(res.activeChipColor, "switch is off; nothing should be active").toBeNull();
      } else if (c.expect === "success") {
        expect(res.activeChipColor, "a CONFIRMED match must be green").toBe(success);
        // Explicit, because this is the reported bug in its exact form: on the
        // maintainer's theme the accent IS amber, so "green" and "not the
        // accent" were two different facts and only the second one bit.
        expect(res.activeChipColor, "a match must not borrow the theme accent").not.toBe(accent);
      } else if (c.expect === "warning") {
        expect(res.activeChipColor, "a MISMATCH must be amber").toBe(warning);
      } else {
        // Grey: not amber (which would claim "checked and wrong" about a state
        // that was never checked) and not the accent (amber on some themes).
        expect(res.activeChipColor, "unverifiable must not read as a warning").not.toBe(warning);
        expect(res.activeChipColor, "unverifiable must not borrow the accent").not.toBe(accent);
      }
    });
  }
});

/**
 * THE FIT GATE PROPER — pseudo-long @390px.
 *
 * ⚠ THE ENGLISH CASES ABOVE CANNOT PROVE THE WRAP. Measured: with flex-wrap
 * ablated, probeLayout finds ZERO overflow at 390px in English — the two buttons
 * genuinely fit — so up there "the action row must wrap" is a DECLARATION with
 * nothing behind it, satisfied by the CSS saying so rather than by anything the
 * browser paints. That is a preference, not a claim.
 *
 * The row still overflowed on a real phone, because rendered width is not
 * viewport width: a larger accessibility font, or a locale that renders these
 * labels ~1.3x wider, pushes the same two buttons past the edge at the same
 * 390px. The pseudo-long locale is this project's standing stand-in for exactly
 * that pressure, and it is what the i18n layout gate already stresses every
 * other view with. So the fit claim is made HERE, where removing flex-wrap
 * produces real, measured overflow.
 */
test.describe("sequence-override row: pseudo-long @390px", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  for (const c of CASES) {
    test(`${c.kind} survives pseudo-long without overflowing`, async ({ page }) => {
      await mountHarness(page);
      await registerPseudo(page);
      const res = await renderRow(page, { seed: c.seed, width: 390, lang: "xx" });

      expect(res.ok, res.error).toBe(true);
      expect(res.classes, "the row did not render at all").not.toBeNull();

      const { shellOverflow, culprits } = await probeLayout(page);
      const list = culprits.map((x) => `      +${x.ov}px  ${x.tag}.${x.cls}  "${x.text}"`).join("\n");
      expect(culprits.length, `${c.kind}: ${culprits.length} element(s) overflow their box:\n${list}`).toBe(0);
      expect(shellOverflow, `${c.kind}: card forces ${shellOverflow}px of horizontal scroll`).toBeLessThanOrEqual(2);
    });
  }
});

/**
 * [SEQ-ORDER-0] A room whose order is ZERO must not be reshuffled to the end.
 *
 * ⚠ RED BEFORE THE FIX. The panel re-sorted an already-sorted list with
 * `Number(a?.order) || 999999`, and `0 || 999999` is 999999 — so the FIRST room in
 * the queue sorted LAST, and the row reported a permanent mismatch against a device
 * order that was in fact correct. Apply could never clear it: Apply writes the
 * BACKEND's order, the device echoes it back, and the comparison reshuffled it again
 * on the next render.
 *
 * Order 0 is not exotic. `number.py` sets the room-order Number's minimum to 0 and
 * its value defaults to 0 when the key is absent, so a fresh room can sit there.
 * Every other case in this file seeds 1..3, which is exactly why none of them could
 * see this.
 */
test.describe("sequence-override row: order 0 @390px", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  const ZERO_QUEUE = [
    { room_id: 7, name: "KITCHEN", enabled: true, order: 0 },
    { room_id: 8, name: "LIVINGROOM", enabled: true, order: 1 },
    { room_id: 9, name: "Bathroom", enabled: true, order: 2 },
  ];

  test("a queue starting at order 0 still reads as matching", async ({ page }) => {
    await mountHarness(page);
    const res = await renderRow(page, {
      // The device reports exactly the queue's order. Anything but `matching` means
      // the card reordered the queue behind its own comparison.
      seed: { on: true, sensorState: "3", status: "ok", order: [7, 8, 9] },
      width: 390,
      queue: ZERO_QUEUE,
    });

    expect(res.ok, res.error).toBe(true);
    expect(res.classes, "the row did not render at all").not.toBeNull();
    expect(res.classes, "order 0 was treated as 'no order' and sorted last").toContain("is-matching");
  });
});
