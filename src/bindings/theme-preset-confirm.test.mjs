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
// THE FLIP HAPPENED. This file was written as a failing proof (CARD9-1 and
// CARD9-2 red against the then-unconditional handler, expected to go green once
// it checked draftDirty and effectiveActiveThemeId). theme.js now does both, so
// all four are ACTIVE regression gates and the old "expected to fail" framing
// above no longer describes them.
//
// The 2026-08-07 W0 v2 census caught what the flip left behind: CARD9-1 was
// green because the fake had no `_confirm`, so the handler's `?.()` bailed
// before reaching setActiveTheme — right answer, wrong reason, and the ACCEPT
// branch (the path a user actually takes) was unreachable from any test. The
// fake now carries a confirm spy, CARD9-1 asserts the prompt and its danger
// flag, and CARD9-1b covers accepting.

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyThemeBindings } from "./theme.js";

// `confirmAnswer` defaults to false — declining — so the existing expectations
// stand, but for the RIGHT reason. Until 2026-08-07 this fake had no `_confirm`
// at all, and the handler's `await this.card._confirm?.(…)` short-circuited to
// undefined: `if (!proceed) return` fired, setActiveTheme was never reached, and
// CARD9-1's "0 calls" passed while proving nothing about the prompt. The accept
// branch was unreachable from any test in the suite. See theme-overwrite-
// confirm.test.mjs's header, which documents the same `?.()` short-circuit as a
// known property of these fixtures.
function makeBinder({ draftDirty, activeThemeId, clickedThemeId, confirmAnswer = false }) {
  const proto = {};
  applyThemeBindings(proto);
  const binder = Object.create(proto);

  const registered = {};
  const setActiveThemeCalls = [];
  const confirmCalls = [];

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
    _confirm: async (message, opts) => {
      confirmCalls.push({ message, opts });
      return confirmAnswer;
    },
    showToast: () => {},
    t: (key) => key,
    esc: (s) => s,
    _scheduleRender: () => {},
  };
  // Same technique as the CARD-5 proof: stub the collaborator method the
  // handler calls on `this` (the binder), not on card -- inert, not a
  // reimplementation of anything under test.
  binder._refreshThemeFromBackend = async () => {};
  // The binder's OWN `t` — the handler builds the prompt message with
  // `this.t(...)`, not `this.card.t(...)`, mirroring how VacuumCardBindings
  // delegates to the host. This was missing too, and hidden by the SAME
  // short-circuit: in `a?.b(c)`, JS does not evaluate `c` when `a?.b` is nullish,
  // so with no `_confirm` the `this.t(...)` argument was never reached either.
  // One missing property was concealing a second.
  binder.t = (key) => key;

  binder._bindThemePresets();
  const handler = registered["[data-theme-preset]:click"];
  const fire = () => handler({ currentTarget: { dataset: { themePreset: clickedThemeId } } });

  return { binder, fire, setActiveThemeCalls, confirmCalls };
}

test("[CARD9-1] a DIRTY draft PROMPTS, and declining does not activate", async () => {
  const { fire, setActiveThemeCalls, confirmCalls } = makeBinder({
    draftDirty: true,
    activeThemeId: "midnight",
    clickedThemeId: "sunset",
    confirmAnswer: false,
  });

  await fire();

  // The prompt itself is the contract. Asserting only "0 calls" cannot tell a
  // working guard from a missing `_confirm`, which is precisely how this test
  // passed while the handler was never reaching setActiveTheme for the wrong
  // reason. Replacing the confirm block with a bare `if (draftDirty) return;`
  // satisfies a 0-calls assertion perfectly, and makes the theme unswitchable.
  assert.equal(confirmCalls.length, 1, "a dirty draft was discarded with no confirmation prompt");
  assert.equal(
    confirmCalls[0].message,
    "bind_theme.discard_draft_confirm",
    "the discard prompt does not use the i18n key — a raw or wrong string would ship untranslated"
  );
  assert.equal(confirmCalls[0].opts?.danger, true, "the discard prompt lost its danger styling");
  assert.equal(
    setActiveThemeCalls.length,
    0,
    "DECLINING the discard prompt still activated the theme and threw the draft away"
  );
});

test("[CARD9-1b] a DIRTY draft ACCEPTING the prompt does activate", async () => {
  // The accept branch was unreachable from any test in the suite: with no
  // `_confirm` on the fake, `?.()` returned undefined and `if (!proceed) return`
  // always fired. So "confirm and proceed" — the path a user actually takes —
  // had never once been executed.
  const { fire, setActiveThemeCalls, confirmCalls } = makeBinder({
    draftDirty: true,
    activeThemeId: "midnight",
    clickedThemeId: "sunset",
    confirmAnswer: true,
  });

  await fire();

  assert.equal(confirmCalls.length, 1, "the prompt was skipped for a dirty draft");
  assert.equal(
    setActiveThemeCalls.length,
    1,
    "ACCEPTING the discard prompt did not activate the theme — the switch is impossible while dirty"
  );
  assert.equal(setActiveThemeCalls[0].themeId, "sunset");
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
