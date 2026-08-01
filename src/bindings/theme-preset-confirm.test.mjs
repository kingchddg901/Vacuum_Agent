// Regression test — CARD-9 (#17:A2-DRAFT-2 card half), theme preset selection
// safety. _bindThemePresets' click handler (src/bindings/theme.js:193-233)
// calls this.card._actions.setActiveTheme(vacuumEntityId, themeId)
// UNCONDITIONALLY the instant any [data-theme-preset] chip is clicked --
// confirmed by reading the handler in full: no reference to state.draftDirty
// (which DOES already exist, state/theme.js:143/332) anywhere in the click
// path, and no comparison of themeId against the current active theme id
// (state.effectiveActiveThemeId(), state/theme.js:279) either. Two required_
// behavior gaps, both currently unmet:
//   (a) a dirty draft's unsaved edits are discarded with no "discard unsaved
//       edits?" prompt at all -- the draft is simply gone once
//       applyThemeActivation() lands.
//   (b) re-clicking the theme that is ALREADY active still fires a real
//       setActiveTheme service call -- not the no-op the backend's own
//       short-circuit implies it should be.
// setActiveTheme itself (actions/theme.js:36) takes no confirm parameter at
// all today -- that plumbing is RP-034's contract (blocked_by), which this
// proof does not require: it asserts the CARD's current behavior is
// unconditional, independent of what shape a future confirm param takes.
//
// Run: node --test src/bindings/theme-preset-confirm.test.mjs
//
// FLIP CONVENTION (mirrors core-service-failure.test.mjs): CARD9-1 and
// CARD9-2 FAIL against current theme.js (setActiveTheme fires with no gate in
// either case) and are expected to PASS once the handler checks draftDirty
// and effectiveActiveThemeId() before acting. CARD9-3 is the control -- a
// clean draft selecting a genuinely different theme must keep working with
// no prompt in either state.

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyThemeBindings } from "./theme.js";

function makeBinder({ draftDirty, activeThemeId, clickedThemeId }) {
  const proto = {};
  applyThemeBindings(proto);
  const binder = Object.create(proto);

  const registered = {};
  const setActiveThemeCalls = [];

  binder.card = {
    _onAll: (selector, event, handler) => {
      registered[`${selector}:${event}`] = handler;
    },
    _state: {
      isDeviceThemeMode: () => false,
      draftDirty,
      effectiveActiveThemeId: () => activeThemeId,
      applyThemeActivation: () => {},
    },
    _actions: {
      setActiveTheme: async (vacuumEntityId, themeId) => {
        setActiveThemeCalls.push({ vacuumEntityId, themeId });
        return { ok: true, active_theme_id: themeId, draft_dirty: false };
      },
    },
    _config: { vacuum_entity_id: "vacuum.alfred" },
    showToast: () => {},
    t: (key) => key,
    esc: (s) => s,
    _scheduleRender: () => {},
  };
  // Same technique as the CARD-5 proof: stub the collaborator method the
  // handler calls on `this` (the binder), not on card -- inert, not a
  // reimplementation of anything under test.
  binder._refreshThemeFromBackend = async () => {};

  binder._bindThemePresets();
  const handler = registered["[data-theme-preset]:click"];
  const fire = () => handler({ currentTarget: { dataset: { themePreset: clickedThemeId } } });

  return { binder, fire, setActiveThemeCalls };
}

test("[CARD9-1] a DIRTY draft discards silently when a different theme is picked", async () => {
  const { fire, setActiveThemeCalls } = makeBinder({
    draftDirty: true,
    activeThemeId: "midnight",
    clickedThemeId: "sunset",
  });

  await fire();

  assert.equal(
    setActiveThemeCalls.length,
    0,
    "setActiveTheme fired immediately for a dirty draft with no discard-confirmation step at all"
  );
});

test("[CARD9-2] re-selecting the theme that is ALREADY active is not a no-op", async () => {
  const { fire, setActiveThemeCalls } = makeBinder({
    draftDirty: false,
    activeThemeId: "midnight",
    clickedThemeId: "midnight",
  });

  await fire();

  assert.equal(
    setActiveThemeCalls.length,
    0,
    "re-clicking the already-active theme still issued a real setActiveTheme call"
  );
});

test("[CARD9-3] a CLEAN draft selecting a genuinely different theme still activates it (control)", async () => {
  const { fire, setActiveThemeCalls } = makeBinder({
    draftDirty: false,
    activeThemeId: "midnight",
    clickedThemeId: "sunset",
  });

  await fire();

  assert.equal(setActiveThemeCalls.length, 1, "a clean, genuinely-different selection must still activate");
  assert.equal(setActiveThemeCalls[0].themeId, "sunset");
});
