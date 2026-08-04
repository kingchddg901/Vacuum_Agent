// Run: node --test src/bindings/room-editor-save-rejection.test.mjs
//
// Coverage targets — src/bindings/room-editor.js :: _roomEditorSaveWasRejected
//   [RSR-1] a refusal is detected across every shape the backend can send
//   [RSR-2] the message prefers the backend's own words over the generic key
//   [RSR-3] a SUCCESS is not mistaken for a refusal, and clears a stale error
//   [RSR-4] a refusal sets the error and schedules a render (so the modal shows it)
//
// A6-AGX-2 Half B. update_room_fields can return {ok:false,
// reason:"invalid_access_graph"}; both room-editor save bindings awaited it,
// ignored the result and closed the modal — so a refused edit looked exactly
// like a saved one and reverted on the next snapshot with nothing shown.

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyRoomEditorBindings } from "./room-editor.js";

/** A bindings object with just enough card/state surface to exercise the check. */
function makeBindings() {
  const proto = {};
  applyRoomEditorBindings(proto);

  const calls = { errors: [], renders: 0 };
  const ctx = Object.create(proto);
  ctx.tRaw = (key) => `T(${key})`;
  ctx.card = {
    _scheduleRender: () => { calls.renders += 1; },
    _state: {
      setRoomEditorSaveError: (msg) => { calls.errors.push(msg); },
    },
  };
  return { ctx, calls };
}

test("[RSR-1] every refusal shape the backend can send is detected", () => {
  for (const result of [
    { ok: false },
    { updated: false },
    { error: "invalid_access_graph" },
    { reason: "invalid_access_graph" },
  ]) {
    const { ctx } = makeBindings();
    assert.equal(
      ctx._roomEditorSaveWasRejected(result),
      true,
      `not detected: ${JSON.stringify(result)}`
    );
  }
});

test("[RSR-2] the backend's own words beat the generic fallback", () => {
  // issues[] wins — it is the most specific thing the backend returns
  const a = makeBindings();
  a.ctx._roomEditorSaveWasRejected({
    ok: false,
    reason_detail: "detail",
    issues: [{ message: "Room 3 already has two ways in." }],
  });
  assert.equal(a.calls.errors.at(-1), "Room 3 already has two ways in.");

  // then reason_detail
  const b = makeBindings();
  b.ctx._roomEditorSaveWasRejected({ ok: false, reason_detail: "detail", reason: "code" });
  assert.equal(b.calls.errors.at(-1), "detail");

  // and only with nothing at all do we fall back to the translated generic
  const c = makeBindings();
  c.ctx._roomEditorSaveWasRejected({ ok: false });
  assert.equal(c.calls.errors.at(-1), "T(bind_room_editor.save_rejected)");
});

test("[RSR-3] a success is not a refusal, and clears a stale error", () => {
  for (const result of [
    { ok: true, updated: true },
    { updated: true },
    {},
    undefined,
    null,
  ]) {
    const { ctx, calls } = makeBindings();
    assert.equal(
      ctx._roomEditorSaveWasRejected(result),
      false,
      `false positive on: ${JSON.stringify(result)}`
    );
    // a previous refusal must not linger on the next successful save
    assert.deepEqual(calls.errors, [null]);
  }
});

test("[RSR-4] a refusal renders, so the message actually reaches the modal", () => {
  const { ctx, calls } = makeBindings();
  ctx._roomEditorSaveWasRejected({ ok: false, reason: "invalid_access_graph" });
  assert.equal(calls.renders, 1, "without a render the error is set but never drawn");
  assert.equal(calls.errors.length, 1);
  assert.notEqual(calls.errors[0], null);
});
