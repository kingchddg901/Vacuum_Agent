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
 *   RULED 2026-11-16 — the committed `tab-theme.png` BASELINE MAY STAY BLIND, and
 *   this note exists so a fresh code walk stops here instead of re-opening it.
 *   Under the plain stub that baseline renders header, nav and the action-button
 *   row: no sub-tabs, no group filter chips, no token rows, no preview pane. It
 *   therefore cannot see a token group being added — measured, when "Dashboard
 *   Cards" landed with 7 tokens and a new preview, that baseline did not move by
 *   a pixel. Chris's call, and his reason is about the surface rather than the
 *   effort: the theme tab's content "can change often depending on what is
 *   selected or not", so a single pixel baseline of it would either pin one
 *   arbitrary selection or churn on every editor change. What covers that tab is
 *   property-based and lives elsewhere — `[TPC-*]` for preview coverage,
 *   `[CDN-*]`/`[CFS-*]` for the cards it previews, and the second describe block
 *   below for every group rendering at all. Do not propose widening this
 *   baseline; propose a property gate, or nothing.
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
 * IN CI SINCE 2026-11-16, and this paragraph used to say the opposite. `card-visual.yml`
 * named three filters (`visual device-theme gallery-completeness`) and so ran three of
 * the seventeen spec files; this one was not among them, which is why it could sit red
 * for eight commits. That step now runs the whole suite, so this file is gated on every
 * push touching src/ or harness/. The unit-level gate for the same defect is
 * `src/renderers/theme-preview-room-card-state.test.mjs`, which `node-tests.yml` runs too.
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

    // ONE SUBJECT CANNOT BE MEASURED BY A STRING SWEEP, and the reason is structural
    // rather than an exemption of convenience. Every other preview is a renderer that
    // returns markup; "Dashboard Cards" returns a SLOT, which main.js's post-render
    // hook fills with a real mounted <eufy-room-card>. This sweep calls the harness's
    // string `render()`, so no mount hook ever runs.
    //
    // Handing it a stub hass would be WORSE than exempting it: paneLen would then count
    // the empty slot div, the row would pass, and the sweep would report coverage of a
    // preview it had not rendered — the exact shape of vacuous pass this whole file is
    // about. It is gated instead by [CPV-1..6] in card-preview.spec.mjs, which mount the
    // real panel and assert a populated card, and by [TPC-1] which proves the registry
    // entry exists at all.
    //
    // THE THREE PER-CARD SUBGROUPS ARE HERE FOR THE PARENT'S REASON, not a new one:
    // they route to the same slot-emitting method, and main.js decides which of the
    // three cards to mount from the group that is showing. The group names are written
    // out rather than imported from PER_CARD_GROUP deliberately -- mount-entry.js
    // records that Playwright's Node loader does not resolve theme-tokens/index.js's
    // `export let`, and the `stale` check below is what stops these drifting: an
    // exemption for a group that is no longer registered is red.
    const NOT_STRING_RENDERABLE = new Map([
      ["Dashboard Cards", "emits a mount slot; the card is attached after render, so a " +
        "string render has nothing to measure. Covered by [CPV-1..6]."],
      ["Dashboard Cards — Room", "same mount slot as its parent; mounts a room card."],
      ["Dashboard Cards — Dashboard Mode", "same mount slot as its parent; mounts the " +
        "Dashboard Mode card."],
      ["Dashboard Cards — Profile", "same mount slot as its parent; mounts the Profile card."],
    ]);

    // Hygiene: an exemption for a group that is no longer on the roster is a standing
    // excuse for a problem that may not exist any more.
    const stale = [...NOT_STRING_RENDERABLE.keys()].filter((g) => !report.groups.includes(g));
    expect(stale, "exempted groups that are not in the preview registry any more").toEqual([]);

    const empty = report.rows
      .filter((r) => r.paneLen === 0 && !NOT_STRING_RENDERABLE.has(r.group))
      .map((r) => r.group);
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
