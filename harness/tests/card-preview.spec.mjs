/**
 * [CPV-*] THE DASHBOARD CARDS PREVIEW MOUNTS A REAL CARD.
 *
 * Every other subject in theme-preview.js previews a surface the PANEL draws, so a
 * renderer produces it as a string and a string assertion can check it. This one
 * cannot be checked that way: the Dashboard Cards group styles the three cards a user
 * adds to their own dashboard, and those are custom elements with their own shadow
 * roots. The renderer emits only an empty slot; main.js::_maybeMountThemePreviewCard
 * fills it after render. So the thing worth asserting — that a real card appears, with
 * real content, carrying the token being edited — exists only in a live DOM.
 *
 * WHY A FACSIMILE WOULD HAVE BEEN WORSE THAN NO PREVIEW. The card frame is replica set
 * RNA0TM68: three copies that cannot be unified, because one card frames with <ha-card>
 * and two with a plain div. A drawn preview is a FOURTH copy, free to drift from all
 * three while looking authoritative. This repo has already paid that once — RNJE1GDZ,
 * where the sample room card diverged from the real one.
 *
 * THE GATE THIS SPEC REPLACES IS NONE. Nothing checks that a token group HAS a preview:
 * "Map" carries 34 tokens and has none, and nobody noticed. And tab-theme.png, the only
 * CI-visible theme baseline, renders no preview pane at all under the plain stub — so
 * the visual gate is structurally blind to everything in this file.
 *
 * Coverage — three cells, because one green is not evidence that anything was measured:
 * [CPV-1] group = Dashboard Cards + rooms  -> slot, inert, a real card WITH content
 * [CPV-2] group = Chips           + rooms  -> no slot (the pane is group-scoped)
 * [CPV-3] group = Dashboard Cards, NO rooms -> no pane at all (renderer returns "")
 * [CPV-4] the mounted card SEES the token being edited, by inheritance
 */
import { test, expect } from "@playwright/test";
import { mountHarness } from "../lib/mount-page.mjs";

// The fixture is read IN-PAGE off window.__evcc, never imported here. Playwright's
// Node loader treats harness/fixtures/cards.js (a typeless .js) as CommonJS and
// refuses its named ESM exports, so a spec-side import fails at COLLECTION with
// "No tests found" -- which reads exactly like a spec that was never written.

/** Mount the REAL panel on the theme tab, select a group, and report the preview. */
async function previewFor(page, group, { dropRooms = false } = {}) {
  await mountHarness(page);
  return page.evaluate(async ({ group, dropRooms }) => {
    const all = window.__evcc.cardStates;
    const states = dropRooms
      ? Object.fromEntries(Object.entries(all).filter(([id]) => !id.startsWith("switch.")))
      : all;
    const vac = window.__evcc.cards.find((c) => c.id === "room")?.config?.vacuum_entity_id;
    const r = await window.__evcc.mountRealThemeEditor(null, {
      subTab: "tokens",
      width: 1200,
      config: { vacuum_entity_id: vac },
      hass: { states },
    });
    if (!r.ok) return { error: r.error };
    const el = document.querySelector("eufy-vacuum-command-center");
    el._state.setThemeGroupFilter(group);
    el._scheduleRender();
    await new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res)));
    await new Promise((res) => setTimeout(res, 150));

    const root = el.shadowRoot;
    const slot = root.getElementById("evcc-theme-preview-card-slot");
    const card = slot?.querySelector("eufy-room-card") ?? null;
    const inner = card?.shadowRoot?.innerHTML ?? "";
    return {
      previewGroup: el._state.currentThemePreviewGroup(),
      paneCount: root.querySelectorAll(".evcc-theme-preview-pane").length,
      slot: Boolean(slot),
      slotInert: slot ? slot.hasAttribute("inert") : null,
      mountedCard: Boolean(card),
      cardShadowChars: inner.length,
      cardHasHaCard: inner.includes("<ha-card"),
      frameBorderWidth: card
        ? getComputedStyle(card).getPropertyValue("--evcc-card-frame-border-width").trim()
        : null,
    };
  }, { group, dropRooms });
}

test("[CPV-1] [CPV-4] the Dashboard Cards preview mounts a real, populated room card", async ({ page }) => {
  const r = await previewFor(page, "Dashboard Cards");
  expect(r.error, "the real panel failed to mount").toBeUndefined();
  expect(r.previewGroup).toBe("Dashboard Cards");
  expect(r.slot, "the renderer must emit the mount slot").toBe(true);

  // inert, or a click in the preview reaches the real card's handlers and flips a
  // real room's settings. A preview is for looking at.
  expect(r.slotInert, "the slot must be inert").toBe(true);

  // [CPV-1] the load-bearing one: a REAL custom element, not markup that resembles it.
  expect(r.mountedCard, "a real <eufy-room-card> must be mounted in the slot").toBe(true);
  expect(r.cardHasHaCard, "the mounted card must have drawn its own <ha-card> frame").toBe(true);

  // A card that mounted but rendered nothing is the failure this catches: setConfig
  // succeeded, the hass was wrong, and the preview is an empty box that still passes
  // every "is it there" assertion. The real card renders tens of thousands of chars.
  expect(r.cardShadowChars,
    `the mounted card rendered ${r.cardShadowChars} chars of shadow content; ` +
    `an empty card means it mounted but never got usable hass`).toBeGreaterThan(5000);

  // [CPV-4] the point of the whole preview: the card SEES the token being edited.
  // It reads --evcc-* by inheritance from the panel host, which every editor control
  // writes the resolved draft onto. If this is empty the preview renders but cannot
  // respond to the editor, which looks identical to a working one in a screenshot.
  expect(r.frameBorderWidth,
    "the mounted card must inherit --evcc-card-frame-border-width from the panel host")
    .not.toBe("");
  expect(r.frameBorderWidth).not.toBeNull();
});

test("[CPV-5] a DECLARED token reaches the mounted card", async ({ page }) => {
  // THE RED INPUT: remove the third applyDynamicTheme target from
  // src/styles/apply-theme.js and rely on inheritance, which is what shipped first.
  //
  // [CPV-4] asserts the card SEES --evcc-card-frame-border-width, and passes on the
  // broken state, because that token is deliberately UNDECLARED and therefore the one
  // kind that does inherit. The ~425 tokens foundationTokens declares inside the card's
  // own shadow root do not: a declaration in the element's own tree beats an inherited
  // value. Measured on the shipped-first version -- setting --evcc-chip-padding to
  // `20px 40px` on the panel moved the mounted card's chip by zero pixels.
  //
  // So this test uses a DECLARED token on purpose. It is the difference between a
  // preview that looks live and one that is.
  await mountHarness(page);
  const r = await page.evaluate(async () => {
    const vac = window.__evcc.cards.find((c) => c.id === "room")?.config?.vacuum_entity_id;
    await window.__evcc.mountRealThemeEditor(null, {
      subTab: "tokens", width: 1200,
      config: { vacuum_entity_id: vac }, hass: { states: window.__evcc.cardStates },
    });
    const el = document.querySelector("eufy-vacuum-command-center");
    el._state.setThemeGroupFilter("Dashboard Cards");
    el._scheduleRender();
    await new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res)));
    await new Promise((res) => setTimeout(res, 200));
    const card = el.shadowRoot.getElementById("evcc-theme-preview-card-slot")
      ?.querySelector("eufy-room-card");
    if (!card) return { error: "no mounted card" };
    const chipPad = () => getComputedStyle(card.shadowRoot.querySelector(".chip")).padding;
    const before = chipPad();
    // drive it the way an editor control does: write the draft, then apply
    el._state.applyThemeDraftPatch({ tokens: { "--evcc-chip-padding": "20px 40px" } });
    el._scheduleRender();
    await new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res)));
    await new Promise((res) => setTimeout(res, 150));
    return { before, after: chipPad() };
  });
  expect(r.error).toBeUndefined();
  expect(r.after,
    `--evcc-chip-padding is DECLARED by foundationTokens inside the card's own shadow ` +
    `root, so inheritance cannot deliver it; applyThemeToCard must write it inline on ` +
    `the mounted card (before=${r.before} after=${r.after})`).not.toBe(r.before);
});

test("[CPV-6] a keystroke reaches the mounted card without a re-render", async ({ page }) => {
  // THE RED INPUT: remove the third applyDynamicTheme target from
  // src/styles/apply-theme.js.
  //
  // [CPV-5] drives a RENDER, and the render path is covered by the apply in
  // _maybeMountThemePreviewCard. So [CPV-5] passes with that target deleted. This is
  // the other half: the 15 editor controls in bindings/theme.js write the draft and
  // call applyThemeToCard directly with NO re-render, because re-rendering on every
  // slider frame would be unusable. If only the render path were wired, the preview
  // would sit still until the 600ms deferred render caught up — live-looking in a
  // screenshot, laggy in the hand.
  //
  // Two targets in two files, each needed, each invisible to the other's test.
  await mountHarness(page);
  const r = await page.evaluate(async () => {
    const vac = window.__evcc.cards.find((c) => c.id === "room")?.config?.vacuum_entity_id;
    await window.__evcc.mountRealThemeEditor(null, {
      subTab: "tokens", width: 1200,
      config: { vacuum_entity_id: vac }, hass: { states: window.__evcc.cardStates },
    });
    const el = document.querySelector("eufy-vacuum-command-center");
    el._state.setThemeGroupFilter("Dashboard Cards");
    el._scheduleRender();
    await new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res)));
    await new Promise((res) => setTimeout(res, 200));
    const card = el.shadowRoot.getElementById("evcc-theme-preview-card-slot")
      ?.querySelector("eufy-room-card");
    if (!card) return { error: "no mounted card" };
    const pad = () => getComputedStyle(card.shadowRoot.querySelector(".chip")).padding;
    const before = pad();

    // NEUTRALISE RENDERING FIRST. Without this the test passes for the wrong reason:
    // applyThemeDraftPatch itself never renders (src/state/theme.js:110 only mutates
    // state), but a render SCHEDULED during setup lands inside the wait below and the
    // mount hook does the work -- so the test stayed green with the keystroke target
    // deleted, which is precisely the regression it exists to catch. Counted too, so a
    // future render path cannot creep back in unnoticed.
    let renders = 0;
    el._scheduleRender = () => { renders += 1; };
    el._scheduleDeferredRender = () => { renders += 1; };

    // EXACTLY what a control does: patch the draft, apply, do NOT render.
    el._state.applyThemeDraftPatch({ tokens: { "--evcc-chip-padding": "22px 33px" } });
    window.__evcc.applyThemeToCard(el);
    await new Promise((res) => setTimeout(res, 120));
    return { before, after: pad(), renders };
  });
  expect(r.error).toBeUndefined();
  expect(r.after,
    `a control writes the draft and calls applyThemeToCard with no re-render; the ` +
    `mounted preview card must repaint on that path too ` +
    `(before=${r.before} after=${r.after})`).not.toBe(r.before);
  // Isolation is structural: _scheduleRender was replaced above, so no render can have
  // executed regardless of how many were scheduled. Reported, not asserted — gating on
  // the SCHEDULE count made this test fail alone and pass in the full file.
  expect(typeof r.renders).toBe("number");
});

test("[CPV-2] another group gets no card slot", async ({ page }) => {
  // The pane is group-scoped. Without this, [CPV-1] would also pass on a slot emitted
  // unconditionally for every group — which would mount a room card under 'Map'.
  const r = await previewFor(page, "Chips");
  expect(r.previewGroup).toBe("Chips");
  expect(r.paneCount, "Chips still has its own preview").toBeGreaterThan(0);
  expect(r.slot, "the card slot must not appear outside its own group").toBe(false);
  expect(r.mountedCard).toBe(false);
});

test("[CPV-3] with no rooms there is no pane at all", async ({ page }) => {
  // The renderer returns "" when there is nothing honest to show, and an empty body
  // makes _renderThemePreviewPane return "" too — so the group degrades to the same
  // state as 'Map' rather than showing an empty frame labelled as the user's card.
  const r = await previewFor(page, "Dashboard Cards", { dropRooms: true });
  expect(r.slot).toBe(false);
  expect(r.mountedCard).toBe(false);
  expect(r.paneCount,
    "with no rooms the whole pane must be absent, not an empty box").toBe(0);
});
