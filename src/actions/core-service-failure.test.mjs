// Regression tests — a failed service call must reach the USER, not just the console.
//
// callService passes `notifyOnError: false` to hass.callService, which suppresses Home
// Assistant's own error toast. That makes THIS helper responsible for telling the user, and
// until now it did not: every failure was console.error'd and resolved to `null`. Because
// every service call in the card funnels through here, a failed start, a refused zone clean
// and a fetch that could not run all rendered as ordinary empty/idle states.
//
// Root cause of the card audit's FE-ERR-1..9 and MZ-2 cluster.
// Run: node --test src/actions/core-service-failure.test.mjs
//
// Coverage (CSF = Core Service Failure):
//   [CSF-1] a throwing service call raises an ERROR toast naming the service
//   [CSF-2] it still returns null, so every existing null-check keeps working
//   [CSF-3] a SUCCESSFUL call raises no toast (the signal must stay meaningful)
//   [CSF-4] a response-capable call returns the payload untouched
//   [CSF-5] a card without a toast host does not throw (best-effort, never fatal)
//   [CSF-6] the message routes through i18n, not a hardcoded English literal

import { test } from "node:test";
import assert from "node:assert/strict";

import { makeActions } from "./_test-host.mjs";

// Builds the REAL VacuumCardActions against a fake host — see _test-host.mjs for why
// this must not go back to attaching showToast/t onto a bare prototype (R3-BUG-1).
function makeCard({ fail = false, response = undefined, withHost = true } = {}) {
  return makeActions({
    host: withHost ? undefined : null,
    hass: {
      callService: async () => {
        if (fail) throw new Error("service unavailable");
        return response;
      },
    },
  });
}

test("[CSF-1] a failed service call raises an error toast naming the service", async () => {
  const card = makeCard({ fail: true });
  await card.callService("eufy_vacuum", "start_room_clean", { x: 1 });
  assert.equal(card.toasts.length, 1, "the user was told nothing about the failure");
  assert.equal(card.toasts[0].kind, "error");
  assert.match(card.toasts[0].message, /start_room_clean/);
});

test("[CSF-2] a failed call still returns null (existing null-checks keep working)", async () => {
  const card = makeCard({ fail: true });
  const result = await card.callService("eufy_vacuum", "start_room_clean");
  assert.equal(result, null);
});

test("[CSF-3] a successful call raises no toast", async () => {
  const card = makeCard({ fail: false });
  await card.callService("eufy_vacuum", "start_room_clean");
  assert.deepEqual(card.toasts, [], "a success produced an error toast — the signal is noise");
});

test("[CSF-4] a response-capable call returns its payload untouched", async () => {
  const card = makeCard({ fail: false, response: { ok: true, rooms: [1, 2] } });
  const result = await card.callService("eufy_vacuum", "get_rooms", {}, true);
  assert.deepEqual(result, { ok: true, rooms: [1, 2] });
});

test("[CSF-5] an actions object built with no host does not throw", async () => {
  const card = makeCard({ fail: true, withHost: false });
  const result = await card.callService("eufy_vacuum", "start_room_clean");
  assert.equal(result, null, "reporting the error must never be fatal");
});

test("[CSF-6] the message routes through i18n rather than a hardcoded literal", async () => {
  const card = makeCard({ fail: true });
  await card.callService("eufy_vacuum", "start_room_clean");
  assert.match(
    card.toasts[0].message,
    /^T:common\.service_failed:/,
    "the toast bypassed the translator"
  );
});

// R3-BUG-1. The five specs above all previously passed against a mock with showToast/t
// attached directly, while the shipping class owned neither and every toast was a silent
// no-op. This one names the defect: the surfaces core.js calls must exist ON
// VacuumCardActions, and must reach the host — not be supplied by the test.
test("[CSF-7] VacuumCardActions itself owns the toast surfaces and routes them to its host", async () => {
  const { makeHost } = await import("./_test-host.mjs");
  const { VacuumCardActions } = await import("./index.js");

  const host = makeHost();
  // Constructed exactly as main.js and cards/vacuum-map-host.js construct it.
  const actions = new VacuumCardActions({ callService: async () => { throw new Error("down"); } }, null, host);

  assert.equal(typeof actions.showToast, "function", "actions cannot surface anything to the user");
  assert.equal(typeof actions.t, "function", "actions cannot translate — toasts would be raw keys");
  assert.equal(typeof actions.esc, "function", "actions cannot escape raw backend text at the sink");
  // The methods must be inherited, not properties a caller bolted on.
  assert.ok(!Object.hasOwn(actions, "showToast"), "showToast was attached, not inherited — that is the mock, not the class");
  assert.ok(!Object.hasOwn(actions, "t"), "t was attached, not inherited — that is the mock, not the class");

  await actions.callService("eufy_vacuum", "start_room_clean");
  assert.equal(host.toasts.length, 1, "the failure never reached the HOST's toast stack");
  assert.equal(host.toasts[0].kind, "error");
});

test("[CSF-8] a refusal reason routes through service_reasons and reaches the host", async () => {
  const card = makeCard({ fail: false, response: { success: false, reason: "job_in_progress" } });
  await card.callService("eufy_vacuum", "start_selected_rooms", {}, true);
  assert.equal(card.toasts.length, 1, "the refusal was swallowed");
  assert.match(card.toasts[0].message, /^T:common\.service_refused:/);
});

test("[CSF-9] an UNKNOWN reason code is escaped before it reaches the toast sink", async () => {
  // The sink interpolates `message` directly (renderers/toasts.js), and t() inserts
  // interpolated values RAW — so a raw backend code carrying markup must be escaped on
  // the way in. Reason codes are backend-controlled slugs today; this pins the sink
  // contract rather than waiting for one that isn't.
  const card = makeCard({ fail: false, response: { success: false, reason: "<img src=x>" } });
  await card.callService("eufy_vacuum", "start_selected_rooms", {}, true);
  assert.doesNotMatch(card.toasts[0].message, /<img/, "raw markup reached the innerHTML sink");
  assert.match(card.toasts[0].message, /&lt;img/, "the code should be escaped, not dropped");
});
