/**
 * WAVE 1 — HARNESS SMOKE
 * Every tab renders from the stub without throwing.
 *
 * This is a real test, not a proxy: because renderers are pure
 * `render(ctx) -> HTML`, a throw means a renderer reached outside its
 * state/ctx contract (a true global, the DOM) — exactly what we want
 * to catch. The stub's null-object absorbs unknown `state.*` reads, so
 * the only way to throw is a genuine contract breach.
 *
 * ...AND IT STILL MISSED ONE. The whole Theme view threw on every render for
 * all of 2.4.0 while this file stayed green. The reason is NOT that the
 * assertions were too weak — `render()` here is the harness's own wrapper, not
 * `main.js`'s, and it reports `{ok:false, error}` on a throw, so `res.ok` would
 * have caught it. The reason is that THE CRASH WAS NEVER REACHED:
 *
 *   Under the plain stub the Theme view's BODY renders empty, because the tab
 *   reads `_ensureThemeState()` and `resolvedTheme()` and the fixture
 *   deliberately does not hand-write those (see stub-state.js: transcribing
 *   them would drift from the implementation silently). So the preview pane —
 *   and `renderRoomCard`, where the throw was — never ran. Measured: the theme
 *   view returned ok:true with 4402 characters in the view-root and no
 *   `.evcc-theme-preview-pane` anywhere in it. Those 4402 characters are the
 *   header and footer chrome, and they sailed past `viewLen > 20`.
 *
 * `renderThemeEditor` exists precisely to fix this — its own docstring records
 * the same trap biting the mobile-layout probe, which "reported a clean shell
 * having measured nothing". That lesson was applied there and never propagated
 * here. A guard that EXISTS reads as complete; this is the shoulder just after
 * its window closed. The second describe block below is that propagation, and
 * it is measured in both directions: with the 2.4.0 defect restored, 15 of the
 * 25 registered groups fail — 14 with `Cannot read properties of null (reading
 * 'isBrandDefaultSetting')` and `Learning & Metrics`, the one site that passes a
 * stub object rather than nothing, with `… is not a function`, which is the
 * sharper evidence that BOTH halves of the defect were real. With it fixed, all
 * 25 render and 15 of them produce room cards.
 *
 * NO `data-evcc-view-error` CHECK LIVES IN THIS FILE, deliberately. `main.js`'s
 * try/catch — the only thing that emits that marker — is not on this path at
 * all: `renderTab` calls the harness's own `render()`, which wraps
 * `renderView(ctx)` in its own try/catch and reports `{ok:false, error}`. An
 * assertion on the marker here could never go red, and a check with no failure
 * mode reads as coverage while being none. It lives in `real-frame.spec.mjs`,
 * where `mountRealCard` builds main.js's real frame and the catch genuinely runs.
 *
 * NOT IN CI. `card-visual.yml` runs only `visual device-theme
 * gallery-completeness`, so this file runs when someone runs it. The unit-level
 * gate for the same defect is `src/renderers/theme-preview-room-card-state.test.mjs`,
 * which `node-tests.yml` does run.
 */
import { test, expect } from "@playwright/test";
import { mountHarness, renderTab, VIEW_ORDER } from "../lib/mount-page.mjs";

test.describe("harness smoke: every tab renders without throwing", () => {
  for (const view of VIEW_ORDER) {
    test(`renders ${view}`, async ({ page }) => {
      const pageErrors = [];
      page.on("pageerror", (e) => pageErrors.push(String(e.stack || e)));

      await mountHarness(page);
      const res = await renderTab(page, view);

      expect(
        res.ok,
        `render(${view}) threw:\n${res.error}\n${res.stack || ""}`,
      ).toBe(true);
      expect(
        pageErrors,
        `uncaught pageerror during ${view}:\n${pageErrors.join("\n")}`,
      ).toEqual([]);

      const viewLen = await page.evaluate(() => {
        const host = document.getElementById("evcc-host");
        const root = host?.shadowRoot?.querySelector("[data-evcc-view-root]");
        return root ? root.innerHTML.trim().length : 0;
      });

      // Real content, not silence. NOT SUFFICIENT ALONE — see the header: the
      // theme view cleared this bar for a whole release with its body empty,
      // which is why the second describe block exists.
      expect(viewLen, `view-root rendered empty for ${view}`).toBeGreaterThan(20);
    });
  }
});

/* ========================================================================== *
 * THE THEME PREVIEW PANE, every subject
 * ========================================================================== */

test.describe("theme preview: every subject renders", () => {
  test("every registered preview group renders a non-empty pane", async ({ page }) => {
    await mountHarness(page);

    const report = await page.evaluate(() => {
      // Enumerated from the registry at call time, never hardcoded: the roster
      // is rebuilt when an animal registers, and a frozen list silently stops
      // covering whichever group was added last.
      const groups = window.__evcc.themePreviewGroups();
      const rows = groups.map((g) => {
        // renderThemeEditor, NOT render: it builds the live VacuumCardState the
        // tab needs, so the editor body and the preview column actually exist.
        const res = window.__evcc.renderThemeEditor(null, {
          width: 1400,
          overrides: { currentThemePreviewGroup: () => g },
        });
        const root = document.getElementById("evcc-host")?.shadowRoot
          ?.querySelector("[data-evcc-view-root]");
        const body = root?.querySelector(".evcc-theme-preview-body");
        return {
          group: g,
          ok: res.ok === true,
          error: res.error ? String(res.error) : null,
          paneLen: body?.innerHTML.trim().length ?? 0,
          // Room cards are the specimen that crashed in 2.4.0, so the sweep has
          // to prove it actually rendered some — see the assertion below.
          roomCards: root?.querySelectorAll(".evcc-theme-preview-body .evcc-room-card").length ?? 0,
        };
      });
      return { groups, rows };
    });

    // A FLOOR ON THE ROSTER. Without this, an empty or broken registry makes
    // every assertion below vacuously true and the sweep reports a clean pass
    // having rendered nothing — the same shape of lie this file is here about.
    expect(
      report.groups.length,
      "the preview registry came back (near-)empty, so this sweep measured nothing",
    ).toBeGreaterThan(10);

    const failed = report.rows.filter((r) => !r.ok);
    expect(
      failed.map((r) => `${r.group}: ${r.error}`),
      "preview subjects threw",
    ).toEqual([]);

    const empty = report.rows.filter((r) => r.paneLen === 0).map((r) => r.group);
    expect(empty, "preview subjects rendered an EMPTY pane body").toEqual([]);

    // THE DECLARATION-PROVING ASSERTION. Every check above passes if the preview
    // stops rendering room cards altogether — which is exactly the state that
    // hid the 2.4.0 crash. 2.4.0's defect lived in `renderRoomCard`, reachable
    // only through this grid, so the sweep must show it went there.
    const withCards = report.rows.filter((r) => r.roomCards > 0);
    expect(
      withCards.length,
      "NO preview subject rendered a room card. The sweep ran but never reached " +
      "renderRoomCard, which is the code path that broke in 2.4.0 — so this " +
      "spec is currently incapable of catching that class of defect. Fix the " +
      "fixture, do not relax this.",
    ).toBeGreaterThan(5);
  });
});
