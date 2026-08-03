// Regression tests — CARD-9(3), import rejected-keys surfacing at BOTH
// import entry points.
//
// Before this fix:
//   (a) the paste-JSON modal's confirm-theme-import handler checked
//       result?.ok === false (inline error) but never looked at
//       result.rejected on a SUCCESSFUL-but-partial import — it silently
//       closed the modal as if nothing was skipped.
//   (b) the file-Upload full-import branch was worse: it never even
//       captured importTheme's return value, so it showed a plain "imported"
//       success toast regardless of ok:false OR rejected keys.
//
// Both call sites now funnel through two shared bindings/theme.js helpers:
//   _handleFullImportResult(result, {onRefusal, successToastKey, successVars})
//   _surfaceRejectedImportKeys(result)
// so a partial import behaves identically no matter which entry point the
// user used. This file tests the shared helpers directly (no DOM needed —
// this is where the actual decision logic lives) AND the paste-JSON modal's
// real click-handler wiring via a minimal fake DOM host (per the codebase's
// own note: _bindThemeJsonModalHost binds via host.querySelectorAll on a
// passed-in host node, not via card._onAll, so it needs a
// querySelectorAll-capable stand-in rather than the _onAll-recording-map
// stub theme-preset-confirm.test.mjs uses). The file-Upload branch's own
// click/file-input dance is DOM-driven (document.createElement, a real File)
// and isn't exercised here — no `document` global exists in this test
// environment, and it now just delegates to the same tested helper.
//
// Run: node --test src/bindings/theme-import-rejected.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyThemeBindings } from "./theme.js";

/* =========================================================
   Shared binder scaffold
   ========================================================= */

function makeBinder() {
  const proto = {};
  applyThemeBindings(proto);
  const binder = Object.create(proto);

  const toasts = [];
  const refreshCalls = [];

  binder.t = (key, vars) => (vars ? `${key}|${JSON.stringify(vars)}` : key);
  binder.esc = (s) => String(s);
  binder.card = {
    showToast: (message, opts) => toasts.push({ message, ...opts }),
  };
  binder._refreshThemeFromBackend = async () => { refreshCalls.push(true); };

  return { binder, toasts, refreshCalls };
}

/* =========================================================
   A. _handleFullImportResult — the shared outcome handler
   ========================================================= */

test("[CARD9-IMP-1] ok:false calls onRefusal, refreshes nothing, shows no toast, returns false", async () => {
  const { binder, toasts, refreshCalls } = makeBinder();
  const refusals = [];

  const imported = await binder._handleFullImportResult(
    { ok: false, reason: "invalid_payload" },
    { onRefusal: (r) => refusals.push(r.reason), successToastKey: "bind_theme.theme_imported_from", successVars: { fileName: "x.json" } }
  );

  assert.equal(imported, false);
  assert.deepEqual(refusals, ["invalid_payload"]);
  assert.equal(refreshCalls.length, 0, "a refused import still refreshed the library");
  assert.equal(toasts.length, 0, "a refused import showed a toast here — refusal toasts are centralized in _callThemeService");
});

test("[CARD9-IMP-2] ok:true with no `rejected` and no successToastKey (paste-modal clean import): silent success, no toast", async () => {
  const { binder, toasts, refreshCalls } = makeBinder();

  const imported = await binder._handleFullImportResult({ ok: true, theme_id: "t1" }, {});

  assert.equal(imported, true);
  assert.equal(refreshCalls.length, 1);
  assert.deepEqual(toasts, [], "a clean import produced rejected-keys noise (control case)");
});

test("[CARD9-IMP-3] ok:true WITH `rejected` and no successToastKey (paste-modal partial import): one info toast naming count + keys", async () => {
  const { binder, toasts } = makeBinder();

  await binder._handleFullImportResult({ ok: true, theme_id: "t1", rejected: ["foo", "bar"] }, {});

  assert.equal(toasts.length, 1, "the partial import's dropped keys were silently swallowed");
  assert.equal(toasts[0].kind, "info");
  assert.match(toasts[0].message, /^bind_theme\.import_rejected_keys\|/);
  assert.match(toasts[0].message, /"count":2/);
  assert.match(toasts[0].message, /"keys":"foo, bar"/);
});

test("[CARD9-IMP-4] ok:true WITH `rejected` and a successToastKey (Upload partial import): BOTH the success toast and the rejected-keys toast fire, in order", async () => {
  const { binder, toasts } = makeBinder();

  await binder._handleFullImportResult(
    { ok: true, theme_id: "t1", rejected: ["foo"] },
    { successToastKey: "bind_theme.theme_imported_from", successVars: { fileName: "backup.json" } }
  );

  assert.equal(toasts.length, 2, "Upload's success toast and the rejected-keys toast didn't both surface");
  assert.equal(toasts[0].kind, "success");
  assert.match(toasts[0].message, /^bind_theme\.theme_imported_from\|.*backup\.json/);
  assert.equal(toasts[1].kind, "info");
  assert.match(toasts[1].message, /^bind_theme\.import_rejected_keys\|/);
});

test("[CARD9-IMP-5] ok:true, no `rejected`, WITH a successToastKey (Upload clean import, control): only the success toast fires", async () => {
  const { binder, toasts } = makeBinder();

  await binder._handleFullImportResult(
    { ok: true, theme_id: "t1" },
    { successToastKey: "bind_theme.theme_imported_from", successVars: { fileName: "backup.json" } }
  );

  assert.equal(toasts.length, 1);
  assert.equal(toasts[0].kind, "success");
});

/* =========================================================
   B. Paste-JSON modal's real click handler (_bindThemeJsonModalHost)
   ========================================================= */

function makeFakeHost() {
  const elements = {};
  const ensure = (selector) => {
    if (!elements[selector]) {
      elements[selector] = {
        value: "",
        textContent: "",
        hidden: true,
        _listeners: {},
        addEventListener(event, handler) { this._listeners[event] = handler; },
      };
    }
    return elements[selector];
  };
  const host = {
    querySelector: (selector) => elements[selector] || null,
    querySelectorAll: (selector) => [ensure(selector)],
  };
  const fire = async (selector, event = "click") => {
    const handler = elements[selector]?._listeners[event];
    if (!handler) throw new Error(`no ${event} listener bound for ${selector}`);
    await handler();
  };
  return { host, ensure, fire };
}

function makeModalBinder({ importResult }) {
  const { binder, toasts, refreshCalls } = makeBinder();
  const importCalls = [];
  const closeCalls = [];
  const renderCalls = [];

  binder.card._actions = {
    importTheme: async (payload) => { importCalls.push(payload); return importResult; },
  };
  binder.card._state = { closeThemeJsonModal: () => closeCalls.push(true) };
  binder.card._scheduleRender = () => renderCalls.push(true);

  return { binder, toasts, refreshCalls, importCalls, closeCalls, renderCalls };
}

test("[CARD9-IMP-6] paste-modal: a successful import with rejected keys closes the modal, refreshes, AND surfaces the rejected-keys toast", async () => {
  const { binder, toasts, refreshCalls, closeCalls, renderCalls } = makeModalBinder({
    importResult: { ok: true, theme_id: "t1", rejected: ["--not-namespaced"] },
  });
  const { host, ensure, fire } = makeFakeHost();
  ensure("[data-theme-json-area]").value = JSON.stringify({ theme: { name: "Imported" } });

  binder._bindThemeJsonModalHost(host);
  await fire("[data-action='confirm-theme-import']");

  assert.equal(closeCalls.length, 1, "the modal never closed on a successful import");
  assert.equal(refreshCalls.length, 1);
  assert.equal(renderCalls.length, 1);
  assert.equal(toasts.length, 1);
  assert.equal(toasts[0].kind, "info");
  assert.match(toasts[0].message, /"keys":"--not-namespaced"/);
});

test("[CARD9-IMP-7] paste-modal: a refused import (ok:false) shows the inline error, never closes the modal, never refreshes", async () => {
  const { binder, toasts, refreshCalls, closeCalls } = makeModalBinder({
    importResult: { ok: false, reason: "missing_theme" },
  });
  const { host, ensure, fire } = makeFakeHost();
  ensure("[data-theme-json-area]").value = JSON.stringify({ not_a_theme: true });
  const errEl = ensure("[data-theme-json-error]"); // must exist BEFORE the handler's own host.querySelector() lookup

  binder._bindThemeJsonModalHost(host);
  await fire("[data-action='confirm-theme-import']");

  assert.equal(errEl.hidden, false, "the inline error never surfaced");
  assert.match(errEl.textContent, /missing_theme/);
  assert.equal(closeCalls.length, 0, "the modal closed despite a refused import");
  assert.equal(refreshCalls.length, 0);
  assert.equal(toasts.length, 0, "a toast fired here — refusal toasts are centralized in _callThemeService, not this handler");
});

test("[CARD9-IMP-8] paste-modal: a clean successful import (no rejected keys) closes the modal with no rejected-keys toast (control)", async () => {
  const { binder, toasts, closeCalls } = makeModalBinder({
    importResult: { ok: true, theme_id: "t1" },
  });
  const { host, ensure, fire } = makeFakeHost();
  ensure("[data-theme-json-area]").value = JSON.stringify({ theme: { name: "Imported" } });

  binder._bindThemeJsonModalHost(host);
  await fire("[data-action='confirm-theme-import']");

  assert.equal(closeCalls.length, 1);
  assert.deepEqual(toasts, []);
});
