// Shared scaffolding for ACTION-layer tests. Not a test file itself (no `.test.mjs`
// suffix), so `node --test "src/**/*.test.mjs"` does not pick it up.
//
// WHY THIS EXISTS — read before "simplifying" it back.
// Every toast/refusal test here used to build its subject as `Object.create(proto)`
// after calling `applyCoreActions(proto)`, then attach `showToast` and `t` straight
// onto that object. Those mocks agreed with the CALLER — core.js does call
// `this.showToast(this.t(...))` — but not with the real callee: the shipping
// `VacuumCardActions` owned neither method, so `?.` swallowed every call and the
// entire service-failure / service-refusal toast surface (plus the whole
// `service_reasons.*` namespace) was inert in production while these tests reported
// green. R3-BUG-1.
//
// So: construct the REAL VacuumCardActions against a fake HOST. The delegation
// (actions -> card._renderers.t / card.showToast) is then part of what is under test,
// and removing it fails these specs instead of silently passing them.

import { VacuumCardActions } from "./index.js";

/**
 * Wrap a service payload the way Home Assistant ACTUALLY delivers it.
 *
 * `hass.callService(domain, service, data, target, notifyOnError, true)` resolves to an
 * ENVELOPE -- `{context, response}` -- never the bare payload. Measured on the live panel
 * 2026-09-13: `Object.keys(result)` came back `["context","response"]`.
 *
 * Every fake at this seam used to return the payload BARE, which is a fixture agreeing with
 * the CALLER instead of the callee, and it is the whole reason a refusal check that could
 * never fire had six green tests over it for months. Wrap every `hass.callService` fake with
 * this, so the action layer is fed the shape production feeds it.
 *
 * `undefined` passes through: that is what HA returns when returnResponse is false.
 *
 * @param {*} payload - the service handler's own return value.
 * @returns {{context: object, response: *}|undefined}
 */
export function envelope(payload) {
  if (payload === undefined) return undefined;
  return { context: { id: "01TESTCTX", parent_id: null, user_id: null }, response: payload };
}

/**
 * A stand-in for the host element (main.js's card, or the map-host shim). Exposes the
 * two surfaces the action layer delegates to: `showToast` and `_renderers`.
 */
export function makeHost() {
  const toasts = [];
  return {
    toasts,
    showToast: (message, opts) => { toasts.push({ message, ...opts }); },
    _renderers: {
      // Marks translated output so a spec can prove the string went through i18n
      // rather than a hardcoded English literal.
      t: (key, vars) => `T:${key}:${vars?.reason ?? vars?.service ?? ""}`,
      escapeHtml: (value) => String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;"),
    },
  };
}

/**
 * Build a real VacuumCardActions wired to a fake host.
 *
 * @param {object}   [opts]
 * @param {object}   [opts.hass]  - fake hass ({ callService }).
 * @param {object}   [opts.state] - fake VacuumCardState.
 * @param {object}   [opts.host]  - pass `null` to model an actions object built with NO
 *                                  host, which is what production looked like before the
 *                                  fix: every toast silently dropped.
 * @returns {VacuumCardActions} with `.host` and `.toasts` aliased on for assertions
 *   (neither is read by production code).
 */
export function makeActions({ hass, state, host = makeHost() } = {}) {
  const actions = new VacuumCardActions(hass, state, host ?? undefined);
  actions.host = host;
  actions.toasts = host ? host.toasts : [];
  return actions;
}
