// Regression test — CARD-9(2)/(3) fix #1, theme refusal centralization.
// _callThemeService (actions/theme.js:19ish), the single funnel every one of
// the ~11 theme action methods (setActiveTheme, updateWorkingDraft,
// revertDraft, saveThemeAsNew, overwriteTheme, renameTheme, deleteTheme,
// setThemeTags, exportTheme, importTheme, getThemeLibrary) routes through,
// now inspects the result for the theme services' OWN refusal shape —
// {ok: false, reason: "<code>"} — and calls showServiceRefusalToast ONCE,
// centrally. Before this fix, none of those action methods (or their ~11
// call sites in bindings/theme.js) ever looked at `ok` at all: a refusal
// rode back to the caller identically to success, no toast, nothing (the
// generic {success:false} check in actions/core.js's callService never
// fires for a theme call — theme refusals never carry a `success` field).
//
// Run: node --test src/actions/theme-refusal-toast.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyThemeActions } from "./theme.js";

function makeActions({ response } = {}) {
  const proto = {};
  applyThemeActions(proto);
  const actions = Object.create(proto);

  const refusalCalls = [];
  actions.callService = async () => response;
  actions.showServiceRefusalToast = (reason) => refusalCalls.push(reason);

  return { actions, refusalCalls };
}

test("[TRT-1] an {ok:false, reason} result fires showServiceRefusalToast exactly once with the raw reason", async () => {
  const { actions, refusalCalls } = makeActions({
    response: { ok: false, reason: "theme_not_found", theme_id: "midnight" },
  });

  const result = await actions.overwriteTheme("vacuum.alfred", "midnight");

  assert.equal(refusalCalls.length, 1, "the refusal never reached the user");
  assert.equal(refusalCalls[0], "theme_not_found");
  // The caller still gets the full result back untouched — the toast is a
  // side effect, not a substitute for the return value.
  assert.equal(result.ok, false);
});

test("[TRT-2] a successful {ok:true} result fires no refusal toast", async () => {
  const { actions, refusalCalls } = makeActions({
    response: { ok: true, theme_id: "midnight", active_theme_id: "midnight" },
  });

  await actions.overwriteTheme("vacuum.alfred", "midnight");

  assert.equal(refusalCalls.length, 0, "a success produced a refusal toast — the signal is noise");
});

test("[TRT-3] a response with no `ok` field at all (e.g. getThemeLibrary) fires no refusal toast", async () => {
  const { actions, refusalCalls } = makeActions({
    response: { default_theme_id: "midnight", themes: [], library: {} },
  });

  await actions.getThemeLibrary();

  assert.equal(refusalCalls.length, 0);
});

test("[TRT-4] a null result (genuine call failure, not a refusal) fires no refusal toast", async () => {
  const { actions, refusalCalls } = makeActions({ response: null });

  const result = await actions.setActiveTheme("vacuum.alfred", "midnight");

  assert.equal(refusalCalls.length, 0, "callService's own failure toast already covers this — no double message");
  assert.equal(result, null);
});

// Every reason code CARD-9's background enumerates (RP-034's manager.py) —
// each must reach showServiceRefusalToast with its raw code untouched
// (translation to a sentence happens inside showServiceRefusalToast itself,
// covered separately by check:i18n's key cross-check).
test("[TRT-5] every documented theme reason code is forwarded untouched", async () => {
  const codes = [
    "theme_not_found", "empty_draft", "invalid_payload", "missing_theme",
    "missing_name", "invalid_tokens", "invalid_colors", "invalid_alpha",
    "missing_vacuum", "empty_scope", "no_active_theme",
  ];
  for (const code of codes) {
    const { actions, refusalCalls } = makeActions({ response: { ok: false, reason: code } });
    await actions.importTheme({ theme: { name: "x" } });
    assert.deepEqual(refusalCalls, [code], `reason code "${code}" was not forwarded as-is`);
  }
});
