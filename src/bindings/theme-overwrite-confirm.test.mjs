// Regression tests — CARD-9(2), the Save button's overwrite confirm dialog.
// _bindThemeActions' save-theme click handler (src/bindings/theme.js, the
// "save-theme" case) used to call this.card._actions.overwriteTheme(...)
// UNCONDITIONALLY the instant Save was clicked while a theme was active
// (state.activeThemeId truthy) — no confirm step at all — and silently
// no-op'd (skipped applyThemeActivation, showed nothing) on any {ok:false}
// refusal. This proof covers the new confirm gate + the activation guard;
// the refusal TOAST itself is covered separately by
// actions/theme-refusal-toast.test.mjs (it's shown centrally by
// _callThemeService, actions/theme.js, not by this binding).
//
// Scaffold mirrors theme-preset-confirm.test.mjs (CARD-9(1)'s own tests):
// a bare proto mixin via applyThemeBindings(proto), a binder built with
// Object.create(proto), card._onAll recording handlers into a local map
// instead of touching real DOM, and card._state/_actions/_config/showToast
// stubbed as plain functions/values. t/esc are stubbed directly on the
// BINDER (not card) because, unlike the dirty-draft-discard prompt CARD-9(1)
// tests (which use `_confirm?.()` — a genuinely optional call that
// short-circuits its arguments, including this.t(), when _confirm is
// undefined), this handler calls `this.card._confirm(...)` — NOT optional —
// so this.t()/this.esc() are actually evaluated and must resolve.
//
// Run: node --test src/bindings/theme-overwrite-confirm.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyThemeBindings } from "./theme.js";

function makeBinder({
  activeThemeId = "midnight",
  libraryName = "Midnight",
  confirmResolvesTo = true,
  overwriteResult = { ok: true, active_theme_id: "midnight", theme_id: "midnight" },
} = {}) {
  const proto = {};
  applyThemeBindings(proto);
  const binder = Object.create(proto);

  const registered = {};
  const confirmCalls = [];
  const overwriteCalls = [];
  const applyActivationCalls = [];
  const promptCalls = [];

  binder.t = (key, vars) => (vars ? `${key}|${JSON.stringify(vars)}` : key);
  binder.esc = (s) => String(s);

  binder.card = {
    // $() is called once per data-action to resolve an element BEFORE _on()
    // wires it — tag the stand-in element with the selector so multiple
    // single-element bindings (save-theme, reset-draft, export-theme, …) in
    // the same _bindThemeActions() don't collide under one "click" key.
    $: (selector) => ({ __sel: selector }),
    _on: (el, event, handler) => {
      registered[`${el?.__sel}:${event}`] = handler;
    },
    _onAll: () => {}, // _bindThemeActions also wires [data-action='delete-preset'] via _onAll — inert here
    _state: {
      _ensureThemeState: () => ({
        activeThemeId,
        library: activeThemeId ? { [activeThemeId]: { id: activeThemeId, name: libraryName } } : {},
      }),
      applyThemeActivation: (id, opts) => applyActivationCalls.push({ id, opts }),
    },
    _actions: {
      overwriteTheme: async (vacuumEntityId, themeId) => {
        overwriteCalls.push({ vacuumEntityId, themeId });
        return overwriteResult;
      },
      saveThemeAsNew: async () => ({ ok: true, theme_id: "new-theme" }),
    },
    _config: { vacuum_entity_id: "vacuum.alfred" },
    _confirm: async (message, opts) => {
      confirmCalls.push({ message, opts });
      return confirmResolvesTo;
    },
    _prompt: async (message) => {
      promptCalls.push(message);
      return null; // not exercised by the overwrite path; guards the else-branch
    },
    showToast: () => {},
  };
  binder._refreshThemeFromBackend = async () => {};

  binder._bindThemeActions();
  const fire = () => registered["[data-action='save-theme']:click"]();

  return { binder, fire, confirmCalls, overwriteCalls, applyActivationCalls, promptCalls };
}

test("[CARD9-OW-1] overwrite path shows a confirm dialog naming the TARGET theme by its library name", async () => {
  const { fire, confirmCalls } = makeBinder({ activeThemeId: "midnight", libraryName: "Midnight" });

  await fire();

  assert.equal(confirmCalls.length, 1, "no confirm step at all before overwriting");
  assert.match(confirmCalls[0].message, /^bind_theme\.confirm_overwrite_theme\|/);
  assert.match(confirmCalls[0].message, /"target":"Midnight"/, "the target's LIBRARY name wasn't interpolated");
  assert.equal(confirmCalls[0].opts?.danger, true);
});

test("[CARD9-OW-2] falls back to the raw theme id when the library has no name for it", async () => {
  const { fire, confirmCalls } = makeBinder({ activeThemeId: "sunset", libraryName: "" });

  await fire();

  assert.match(confirmCalls[0].message, /"target":"sunset"/);
});

test("[CARD9-OW-3] cancelling the confirm dialog never calls overwriteTheme", async () => {
  const { fire, overwriteCalls } = makeBinder({ confirmResolvesTo: false });

  await fire();

  assert.equal(overwriteCalls.length, 0, "overwriteTheme fired despite the user cancelling");
});

test("[CARD9-OW-4] accepting the confirm dialog calls overwriteTheme with the vacuum + target theme id", async () => {
  const { fire, overwriteCalls } = makeBinder({ activeThemeId: "midnight", confirmResolvesTo: true });

  await fire();

  assert.equal(overwriteCalls.length, 1);
  assert.deepEqual(overwriteCalls[0], { vacuumEntityId: "vacuum.alfred", themeId: "midnight" });
});

test("[CARD9-OW-5] a refused overwrite (ok:false) does NOT apply activation (its toast is centralized elsewhere)", async () => {
  const { fire, applyActivationCalls } = makeBinder({
    confirmResolvesTo: true,
    overwriteResult: { ok: false, reason: "empty_draft", theme_id: "midnight" },
  });

  await fire();

  assert.equal(applyActivationCalls.length, 0, "activation was applied despite a refused overwrite");
});

test("[CARD9-OW-6] a SUCCESSFUL overwrite still applies activation (control)", async () => {
  const { fire, applyActivationCalls } = makeBinder({
    confirmResolvesTo: true,
    overwriteResult: { ok: true, active_theme_id: "midnight", theme_id: "midnight" },
  });

  await fire();

  assert.equal(applyActivationCalls.length, 1);
  assert.equal(applyActivationCalls[0].id, "midnight");
  assert.equal(applyActivationCalls[0].opts.clearDraft, true);
});

test("[CARD9-OW-7] the 'save as new' path (no active theme) never shows the overwrite confirm (control)", async () => {
  const { fire, confirmCalls, promptCalls } = makeBinder({ activeThemeId: null });

  await fire();

  assert.equal(confirmCalls.length, 0, "the overwrite confirm fired for a brand-new theme save");
  assert.equal(promptCalls.length, 1, "the name prompt didn't fire for the no-active-theme path");
});
