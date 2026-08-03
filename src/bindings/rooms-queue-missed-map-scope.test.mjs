// Regression test — CARD-5 (#16:A4-STATE-4 card half), BINDING side. The
// action-layer proof (src/actions/rooms-retry-missed-map-scope.test.mjs,
// RMS-1/2/3) proves retryMissedRooms itself refuses on a map mismatch. This
// file proves the "queue-missed-rooms" click handler wired in
// src/bindings/rooms.js's _bindRoomActions:
//   (a) passes the incomplete-run log's OWN map_id through as
//       retryMissedRooms' second argument (log?.map_id ?? null) -- not
//       omitted, not the active map, not anything else;
//   (b) on a {queued:false, reason:"map_mismatch"} result, does NOT clear
//       the incomplete-run log or the start/cancel confirmations (so the
//       banner survives and the user can switch maps and retry), does NOT
//       call refreshDashboardSnapshot, and does NOT show a generic
//       success/fail toast (retryMissedRooms already fired the map_mismatch
//       toast itself via showServiceRefusalToast) -- it only schedules a
//       re-render;
//   (c) on any OTHER result (a match, or a legacy log with no map_id) keeps
//       the exact pre-fix behavior: clear the log + confirmations, refresh
//       the dashboard snapshot, and show the requeued/could-not-retry toast.
//
// TECHNIQUE: same as the CARD-5 action proof and
// theme-preset-confirm.test.mjs ("Same technique as the CARD-5 proof") --
// stub `card.$` to return a distinct marker object per selector and
// `card._on`/`card._onAll` to record handlers keyed by `${selector}:${event}`,
// call the REAL `_bindRooms()` (which wires ~15 handlers across
// _bindRoomToggles / _bindRoomActions / _bindQueueChipActions in one shot),
// then pull out and fire specifically the "[data-action='queue-missed-rooms']"
// handler. Every OTHER handler _bindRooms wires is registered but never
// fired -- inert, not exercised -- so this stays a narrow proof of the one
// handler under test, not a re-implementation of the whole binding surface.
//
// Run: node --test src/bindings/rooms-queue-missed-map-scope.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyRoomsBindings } from "./rooms.js";

function makeBinder({ logMapId, missedRoomIds, retryResult }) {
  const proto = {};
  applyRoomsBindings(proto);
  const binder = Object.create(proto);

  const registered = {};
  const retryMissedRoomsCalls = [];
  const toasts = [];
  const flags = {
    incompleteRunLogCleared: false,
    startConfirmationCleared: false,
    cancelRunConfirmationCleared: false,
    refreshCalled: false,
    scheduleRenderCalled: false,
  };

  binder.card = {
    // $ returns a distinct marker per selector; _on/_onAll record the
    // handler keyed by "selector:event" so a specific one can be pulled out
    // and fired without needing every other handler to be individually
    // functional.
    $: (selector) => ({ __sel: selector }),
    _on: (el, event, handler) => {
      registered[`${el?.__sel ?? String(el)}:${event}`] = handler;
    },
    _onAll: (selector, event, handler) => {
      registered[`${selector}:${event}`] = handler;
    },
    // _bindQueueChipActions reads this.card.shadowRoot?.querySelectorAll(...)
    // -- left undefined so the optional chain yields [] and it no-ops safely.
    shadowRoot: undefined,
    _state: {
      incompleteRunLog: () => (logMapId !== undefined ? { map_id: logMapId } : null),
      incompleteRunMissedRoomIds: () => missedRoomIds,
      clearIncompleteRunLog: () => { flags.incompleteRunLogCleared = true; },
      clearStartConfirmation: () => { flags.startConfirmationCleared = true; },
      clearCancelRunConfirmation: () => { flags.cancelRunConfirmationCleared = true; },
      // Read synchronously at BIND time by _bindQueueChipActions (not inside
      // a handler closure) -- must be stubbed or _bindRooms() throws before
      // the handler under test is even registered.
      queueChipLongPressMs: () => 450,
    },
    _actions: {
      retryMissedRooms: async (ids, mapId) => {
        retryMissedRoomsCalls.push({ ids, mapId });
        return retryResult;
      },
    },
    refreshDashboardSnapshot: async () => { flags.refreshCalled = true; },
    showToast: (message, opts) => { toasts.push({ message, ...opts }); },
    _scheduleRender: () => { flags.scheduleRenderCalled = true; },
  };
  // this.t(...) inside the handler resolves against the BINDER (lexical
  // `this` of _bindRoomActions), not card -- same reasoning
  // theme-preset-confirm.test.mjs's header note documents.
  binder.t = (key, vars) => `T:${key}:${vars?.count ?? ""}`;

  binder._bindRooms();
  const handler = registered["[data-action='queue-missed-rooms']:click"];
  assert.ok(handler, "queue-missed-rooms handler was never registered by _bindRooms()");

  return { fire: () => handler(), retryMissedRoomsCalls, toasts, flags };
}

test("[BRQ-1] the log's own map_id is passed through as retryMissedRooms' second argument", async () => {
  const { fire, retryMissedRoomsCalls } = makeBinder({
    logMapId: "A",
    missedRoomIds: [3, 7],
    retryResult: { queued: false, reason: "map_mismatch" },
  });

  await fire();

  assert.equal(retryMissedRoomsCalls.length, 1);
  assert.deepEqual(retryMissedRoomsCalls[0].ids, [3, 7]);
  assert.equal(
    retryMissedRoomsCalls[0].mapId,
    "A",
    "the handler must pass the incomplete-run log's OWN map_id through, not the active map or nothing at all"
  );
});

test("[BRQ-2] a map_mismatch result leaves the log + confirmations untouched and shows no generic toast", async () => {
  const { fire, flags, toasts } = makeBinder({
    logMapId: "A",
    missedRoomIds: [3],
    retryResult: { queued: false, reason: "map_mismatch" },
  });

  await fire();

  assert.equal(flags.incompleteRunLogCleared, false, "a mismatch must NOT clear the incomplete-run log -- the banner must survive so the user can switch maps and retry");
  assert.equal(flags.startConfirmationCleared, false);
  assert.equal(flags.cancelRunConfirmationCleared, false);
  assert.equal(flags.refreshCalled, false, "a refused retry must not refresh the dashboard snapshot");
  assert.deepEqual(toasts, [], "the binding must not show its own generic toast -- retryMissedRooms already fired the map_mismatch refusal toast itself");
  assert.equal(flags.scheduleRenderCalled, true, "the handler must still schedule a re-render on refusal");
});

test("[BRQ-3] a genuine match (or a legacy log with no map_id) keeps the pre-fix behavior", async () => {
  const { fire, flags, toasts } = makeBinder({
    logMapId: "A",
    missedRoomIds: [3, 7],
    retryResult: { started: false }, // any non-mismatch result -- e.g. Promise.all's resolved array
  });

  await fire();

  assert.equal(flags.incompleteRunLogCleared, true);
  assert.equal(flags.startConfirmationCleared, true);
  assert.equal(flags.cancelRunConfirmationCleared, true);
  assert.equal(flags.refreshCalled, true);
  assert.equal(toasts.length, 1, "a non-refused retry must still show the requeued/could-not-retry toast");
  assert.equal(flags.scheduleRenderCalled, true);
});

test("[BRQ-4] zero missed rooms clears the log without ever calling retryMissedRooms (control)", async () => {
  const { fire, retryMissedRoomsCalls, flags } = makeBinder({
    logMapId: "A",
    missedRoomIds: [],
    retryResult: null,
  });

  await fire();

  assert.equal(retryMissedRoomsCalls.length, 0, "nothing was reachable anyway -- retryMissedRooms must not even be called");
  assert.equal(flags.incompleteRunLogCleared, true);
  assert.equal(flags.startConfirmationCleared, true);
  assert.equal(flags.cancelRunConfirmationCleared, true);
  assert.equal(flags.scheduleRenderCalled, true);
});
