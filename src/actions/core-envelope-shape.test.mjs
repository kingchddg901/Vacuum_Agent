// Run: node --test src/actions/core-envelope-shape.test.mjs
//
// Coverage targets — src/actions/core.js :: callService, the ENVELOPE contract
//   [CES-1] callService returns the UNWRAPPED payload, never {context, response}
//   [CES-2] a null `response` falls back to the ENVELOPE, not to null  (the `?? null` trap)
//   [CES-3] an already-bare payload passes through  (the compatibility arm)
//   [CES-4] a transport failure still returns null  (every existing null-check keeps working)
//   [CES-5] REPLICA RNGP3ZBE parity — callService and cards/_shared.js::callResponse agree
//   [CES-6] the SECOND funnel revives: actions/theme.js sees {ok:false} through the envelope
//   [CES-7] the predicate is NOT widened — the other discriminators stay their funnels' job
//
// WHY THIS FILE EXISTS. `hass.callService(..., returnResponse=true)` resolves to
// `{context, response}`. Measured on the live panel 2026-09-13: Object.keys() came back
// ["context","response"]. callService inspected `result.success` on that ENVELOPE, so the
// refusal branch could never fire — and actions/rooms.js:143 had already DELETED its own
// toast in favour of it (MZ-2), so a blocked start has been completely silent. Six green
// CRS tests sat over the dead branch because every fixture returned the payload bare: a
// fixture agreeing with the CALLER, not the callee.
//
// THE INPUT THAT MAKES [CES-1] RED: drop the unwrap (`const payload = returnResponse ? result
// : undefined`). Every case below that reads a field off the return, and all four refusal
// test files, go red — verified by ablation, 8 red, with every no-toast control still green.

import { test } from "node:test";
import assert from "node:assert/strict";

import { makeActions, envelope } from "./_test-host.mjs";
import { callResponse } from "../cards/_shared.js";

const REFUSAL = { success: false, reason: "job_in_progress" };

function withHass(impl) {
  return makeActions({ hass: { callService: impl } });
}

test("[CES-1] the envelope is unwrapped — callers get the payload", async () => {
  const card = withHass(async () => envelope({ candidates: [1, 2, 3], ok: true }));
  const result = await card.callService("eufy_vacuum", "get_maintenance_source_candidates", {}, true);

  assert.deepEqual(result, { candidates: [1, 2, 3], ok: true });
  assert.equal(result.context, undefined, "the envelope must not survive into caller code");
  assert.equal(result.response, undefined, "double-unwrapping a caller's `?? result` must be a no-op");
});

test("[CES-2] a null response falls back to the ENVELOPE, never to null", async () => {
  // THE `?? null` TRAP. bindings/maintenance.js:205 does `if (result === null)` -> "could not
  // save interval", and bindings/base-station.js:56 does `ok = result !== null`. A handler
  // that returns None gives `response: null`; collapsing that to null reports a save that
  // TOOK as a failure. Falling back to the (truthy) envelope keeps both call sites honest.
  const card = withHass(async () => envelope(null));
  const result = await card.callService("eufy_vacuum", "set_maintenance_interval", {}, true);

  assert.notEqual(result, null, "a null payload must not read as a failed call");
  assert.ok(result, "the fallback value must be truthy");
});

test("[CES-3] an already-bare payload passes straight through", async () => {
  const card = withHass(async () => ({ ok: true, rooms: [7] }));
  assert.deepEqual(
    await card.callService("eufy_vacuum", "whatever", {}, true),
    { ok: true, rooms: [7] }
  );
});

test("[CES-4] a transport failure still returns null", async () => {
  const card = withHass(async () => { throw new Error("socket closed"); });
  assert.equal(await card.callService("eufy_vacuum", "whatever", {}, true), null);
});

test("[CES-5] REPLICA RNGP3ZBE — the two members return the SAME shape", async () => {
  // The anchor in core.js and cards/_shared.js declares one convention across both. The
  // `unwrap response` clause was TRUE of the card twin and FALSE of the panel primary for
  // as long as the entry has existed, and nothing in the repo could see it: callResponse has
  // no test of its own. This is the gate that keeps them from drifting apart again.
  const payload = { ok: true, theme_id: "t1" };
  const hass = { callService: async () => envelope(payload) };

  const panel = await withHass(hass.callService).callService("eufy_vacuum", "get_theme_library", {}, true);
  const card = await callResponse(hass, "eufy_vacuum", "get_theme_library", {});

  assert.deepEqual(panel, card, "the declared replicas must hand callers the same shape");
  assert.deepEqual(panel, payload);
});

test("[CES-6] the SECOND dead funnel revives — theme refusals reach the toast", async () => {
  // actions/theme.js::_callThemeService reads `result.ok === false` at this same level, so it
  // was dead for exactly the same reason. Unwrapping in callService repairs it with no edit
  // of its own — which is the strongest argument for unwrapping here rather than patching
  // only core's own predicate.
  const card = withHass(async () => envelope({ ok: false, reason: "theme_not_found" }));
  const result = await card._callThemeService("import_theme", {});

  assert.equal(card.toasts.length, 1, "the theme funnel must see the refusal");
  assert.match(card.toasts[0].message, /theme_not_found|service_reasons/);
  assert.equal(result.ok, false, "and the caller still receives the payload");
});

test("[CES-7] the central predicate is NOT widened — no double-toast", async () => {
  // The backend emits {ok:false}, {updated:false}, {saved:false}, {status:"error"} and
  // {error:...} as well. Those already have their own funnels — theme.js for `ok`,
  // bindings/room-editor.js::_roomEditorSaveWasRejected for updated/error — and pulling them
  // in here would fire a SECOND toast for one refusal. Fixing the shape is not licence to
  // change the contract.
  for (const payload of [
    { ok: false, reason: "theme_not_found" },
    { updated: false, reason: "invalid_access_graph" },
    { saved: false, reason: "whatever" },
    { status: "error", reason: "runtime_unavailable" },
    { error: "room_not_found" },
  ]) {
    const card = withHass(async () => envelope(payload));
    await card.callService("eufy_vacuum", "some_service", {}, true);
    assert.equal(
      card.toasts.length, 0,
      `${JSON.stringify(payload)} must stay its own funnel's business`
    );
  }

  // ...while the two the central check DOES own still fire, so this is a scope assertion,
  // not a broken predicate.
  const refused = withHass(async () => envelope(REFUSAL));
  await refused.callService("eufy_vacuum", "start_zone_clean", {}, true);
  assert.equal(refused.toasts.length, 1);
});
