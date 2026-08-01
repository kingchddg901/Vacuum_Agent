// Regression test — CARD-1 (CF-5 root, RF-14's card-side twin), the structured-
// refusal half. core-service-failure.test.mjs covers a THROWING service call
// (an exception HA/the backend raises); this file covers the OTHER shape a
// service call can now return: a NORMAL (non-throwing) response whose payload
// is {success: false, reason: "..."} -- Q9's operational-refusal contract
// (RP-031). callService's own doc comment says it returns "service response or
// null on failure" and inspects nothing about what that response CONTAINS, so
// a refusal payload is handed back to the caller identically to a genuine
// success -- confirmed directly against core.js: `return returnResponse ?
// result : undefined;` (the only line touching a non-throwing result) has no
// branch on result.success at all.
//
// blocked_by RP-031 for EXECUTION (the backend needs to actually emit this
// shape) -- materialization does not require that landing; this test asserts
// against the CARD's own current behavior for a response shaped as RP-031
// already specifies it (Q9, GATE4-application-register.md), independent of
// whether any backend service emits it yet today.
//
// Run: node --test src/actions/core-refusal-shape.test.mjs
//
// Coverage (CRS = Core Refusal Shape):
//   [CRS-1] a {success:false, reason} response raises an error toast naming the reason
//   [CRS-2] the SAME response fires no toast when success is true (signal stays meaningful)
//   [CRS-3] an unmapped/unknown reason code still names itself in the toast (forward-compat)
//
// FLIP CONVENTION (mirrors core-service-failure.test.mjs, which was authored the
// same way): CRS-1 and CRS-3 FAIL against current core.js (no toast fires at
// all for a non-throwing refusal) and are expected to PASS once the wrapper
// inspects returnResponse's payload. CRS-2 is the control -- it holds both
// before and after, so a change that broke the "no noise on success" contract
// would be caught either way.

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyCoreActions } from "./core.js";

function makeCard({ response = undefined, withToast = true, withT = true } = {}) {
  const proto = {};
  applyCoreActions(proto);
  const card = Object.create(proto);
  card.toasts = [];
  card.hass = {
    callService: async () => response,
  };
  if (withToast) {
    card.showToast = (message, opts) => card.toasts.push({ message, ...opts });
  }
  if (withT) {
    card.t = (key, vars) => `T:${key}:${vars?.reason ?? vars?.service ?? ""}`;
  }
  return card;
}

test("[CRS-1] a structured refusal raises an error toast naming the reason", async () => {
  const card = makeCard({ response: { success: false, reason: "job_in_progress" } });
  const result = await card.callService(
    "eufy_vacuum", "start_zone_clean", { x: 1 }, true
  );
  assert.equal(card.toasts.length, 1, "the refusal reached no one -- the caller sees a normal response");
  assert.equal(card.toasts[0].kind, "error");
  assert.match(card.toasts[0].message, /job_in_progress/);
  void result;
});

test("[CRS-2] a genuinely successful response raises no toast", async () => {
  const card = makeCard({ response: { success: true, rooms: [1, 2] } });
  await card.callService("eufy_vacuum", "start_zone_clean", {}, true);
  assert.deepEqual(card.toasts, [], "a success produced an error toast -- the signal is noise");
});

test("[CRS-3] an unmapped reason code still names itself (forward-compat)", async () => {
  const card = makeCard({ response: { success: false, reason: "future_backend_reason_xyz" } });
  await card.callService("eufy_vacuum", "start_zone_clean", {}, true);
  assert.equal(card.toasts.length, 1);
  assert.match(
    card.toasts[0].message,
    /future_backend_reason_xyz/,
    "an unrecognised reason must still surface its own code, never go blank or silent"
  );
});

