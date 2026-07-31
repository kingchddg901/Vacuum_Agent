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

import { applyCoreActions } from "./core.js";

function makeCard({ fail = false, response = undefined, withToast = true, withT = true } = {}) {
  const proto = {};
  applyCoreActions(proto);
  const card = Object.create(proto);
  card.toasts = [];
  card.hass = {
    callService: async () => {
      if (fail) throw new Error("service unavailable");
      return response;
    },
  };
  if (withToast) {
    card.showToast = (message, opts) => card.toasts.push({ message, ...opts });
  }
  if (withT) {
    card.t = (key, vars) => `T:${key}:${vars?.service ?? ""}`;
  }
  return card;
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

test("[CSF-5] a card with no toast host does not throw", async () => {
  const card = makeCard({ fail: true, withToast: false });
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
