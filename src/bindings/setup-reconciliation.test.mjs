// CARD-7/RP-019 (Gap 3) — the reconcile-room Update/Dismiss bindings.
// Scaffold mirrors theme-overwrite-confirm.test.mjs's pattern: a bare proto
// mixin via applySetupBindings(proto), card._onAll recording handlers into a
// local map instead of touching real DOM, and card._state/_actions/_config/
// showToast stubbed as plain functions/values. t/tRaw are stubbed on the
// BINDER (this.t/this.tRaw inside the handlers resolve to the binder, same
// as every other _bindSetup handler in this file).
//
// Proves (packet's TEST section):
//   - the plan_token round-trip: the EXACT token received in the reviews
//     payload (reconciliation.plan_token) is the EXACT token sent back to
//     reconcileRoom on BOTH Update (migrate) and Dismiss (ignore) — the
//     design doc sends it on both.
//   - the stale plan_changed catch path re-renders State B from fresh data
//     (discoverRooms + getSetupStatus) rather than dead-ending on a generic
//     error, and NEVER auto-confirms the refreshed plan.
//   - a non-plan_changed failure (plan_token_required / unknown) does NOT
//     attempt recovery — it surfaces as an ordinary error.
//   - the silent recovery's own failure sets the manual re-discover fallback
//     flag (design's literal fallback), and the manual re-discover button
//     reuses the same recovery path.
//
// Run: node --test src/bindings/setup-reconciliation.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";

import { applySetupBindings } from "./setup.js";

const VAC = "vacuum.alfred";

function makeBinder({
  reconciliation = { map_id: "1", plan_token: "tok-abc123", has_changes: true, reviews: [] },
  reconcileRoomImpl = null,
  discoverRoomsImpl = null,
} = {}) {
  const proto = {};
  applySetupBindings(proto);
  const binder = Object.create(proto);

  const registered = {};
  const stateCalls = { loading: [], resolved: [], staleNote: [], refreshFailed: [], error: [] };
  const reconcileRoomCalls = [];
  const discoverRoomsCalls = [];
  const getSetupStatusCalls = [];
  const toasts = [];

  binder.t = (key, vars) => (vars ? `${key}|${JSON.stringify(vars)}` : key);
  binder.tRaw = (key, vars) => (vars ? `${key}|${JSON.stringify(vars)}` : key);

  let currentStatus = { vacuums: [{ vacuum_entity_id: VAC, reconciliation }] };

  binder.card = {
    _config: { vacuum_entity_id: VAC },
    _onAll: (selector, event, handler) => { registered[`${selector}:${event}`] = handler; },
    _scheduleRender: () => {},
    showToast: (msg) => toasts.push(msg),
    _state: {
      setupStatus: () => currentStatus,
      setSetupStatus: (s) => { currentStatus = s; },
      setSetupReconcileLoading: (v) => stateCalls.loading.push(v),
      setSetupReconcileStaleNote: (v) => stateCalls.staleNote.push(v),
      setSetupReconcileRefreshFailed: (v) => stateCalls.refreshFailed.push(v),
      setSetupReconcileResolved: (token, result) => stateCalls.resolved.push({ token, result }),
      setSetupError: (e) => stateCalls.error.push(e),
    },
    _actions: {
      reconcileRoom: async (vacuumEntityId, mapId, action, planToken) => {
        reconcileRoomCalls.push({ vacuumEntityId, mapId, action, planToken });
        if (reconcileRoomImpl) return reconcileRoomImpl({ vacuumEntityId, mapId, action, planToken });
        return { vacuum_entity_id: vacuumEntityId, map_id: mapId, action, migrated_room_count: 1, id_remap: {}, dropped: [] };
      },
      discoverRooms: async (vacuumEntityId, mapId) => {
        discoverRoomsCalls.push({ vacuumEntityId, mapId });
        if (discoverRoomsImpl) return discoverRoomsImpl({ vacuumEntityId, mapId });
      },
      getSetupStatus: async () => {
        getSetupStatusCalls.push(true);
        return currentStatus;
      },
    },
  };

  binder._bindSetup();

  return {
    binder,
    fireUpdate: () => registered["[data-action='setup-reconcile-update']:click"](),
    fireDismiss: () => registered["[data-action='setup-reconcile-dismiss']:click"](),
    fireRediscover: () => registered["[data-action='setup-reconcile-rediscover']:click"](),
    stateCalls, reconcileRoomCalls, discoverRoomsCalls, getSetupStatusCalls, toasts,
    setStatus: (s) => { currentStatus = s; },
  };
}

/* ---- plan_token round-trip -------------------------------------------------- */

test("[CARD7-B1] Update sends the EXACT plan_token it received", async () => {
  const { fireUpdate, reconcileRoomCalls } = makeBinder({
    reconciliation: { map_id: "3", plan_token: "tok-XYZ789", has_changes: true, reviews: [] },
  });

  await fireUpdate();

  assert.equal(reconcileRoomCalls.length, 1);
  assert.deepEqual(reconcileRoomCalls[0], {
    vacuumEntityId: VAC, mapId: "3", action: "migrate", planToken: "tok-XYZ789",
  });
});

test("[CARD7-B2] Dismiss ALSO sends the EXACT plan_token it received (design sends it on both)", async () => {
  const { fireDismiss, reconcileRoomCalls } = makeBinder({
    reconciliation: { map_id: "3", plan_token: "tok-XYZ789", has_changes: true, reviews: [] },
  });

  await fireDismiss();

  assert.equal(reconcileRoomCalls.length, 1);
  assert.deepEqual(reconcileRoomCalls[0], {
    vacuumEntityId: VAC, mapId: "3", action: "ignore", planToken: "tok-XYZ789",
  });
});

test("[CARD7-B3] a successful Update records the resolved token = the token that was sent (end-to-end round trip)", async () => {
  const { fireUpdate, reconcileRoomCalls, stateCalls } = makeBinder({
    reconciliation: { map_id: "1", plan_token: "tok-roundtrip", has_changes: true, reviews: [] },
  });

  await fireUpdate();

  assert.equal(stateCalls.resolved.length, 1);
  assert.equal(stateCalls.resolved[0].token, reconcileRoomCalls[0].planToken);
  assert.equal(stateCalls.resolved[0].token, "tok-roundtrip");
});

test("[CARD7-B3b] a successful Dismiss also records the resolved token", async () => {
  const { fireDismiss, stateCalls } = makeBinder({
    reconciliation: { map_id: "1", plan_token: "tok-dismiss-rt", has_changes: true, reviews: [] },
  });

  await fireDismiss();

  assert.equal(stateCalls.resolved.length, 1);
  assert.equal(stateCalls.resolved[0].token, "tok-dismiss-rt");
});

/* ---- stale plan_token (plan_changed) recovery ------------------------------ */

test("[CARD7-B4] a plan_changed refusal silently re-runs discovery and re-polls status instead of dead-ending on a generic error", async () => {
  const freshStatus = {
    vacuums: [{ vacuum_entity_id: VAC, reconciliation: { map_id: "1", plan_token: "tok-FRESH", has_changes: true, reviews: [] } }],
  };
  let refreshed = false;
  const { fireUpdate, stateCalls, discoverRoomsCalls, getSetupStatusCalls, setStatus } = makeBinder({
    reconciliation: { map_id: "1", plan_token: "tok-STALE", has_changes: true, reviews: [] },
    reconcileRoomImpl: async () => {
      throw new Error("Could not reconcile room: plan_changed");
    },
    discoverRoomsImpl: async () => {
      refreshed = true;
      setStatus(freshStatus);
    },
  });

  await fireUpdate();

  assert.equal(discoverRoomsCalls.length, 1, "discover_rooms was not re-run on plan_changed");
  assert.deepEqual(discoverRoomsCalls[0], { vacuumEntityId: VAC, mapId: "1" });
  assert.ok(refreshed, "discoverRooms implementation never ran");
  assert.equal(getSetupStatusCalls.length, 1, "status was not re-polled after the refresh");
  assert.equal(stateCalls.staleNote.at(-1), true, "the one-line stale-map note was not shown");
  assert.equal(stateCalls.refreshFailed.at(-1), false);
  // NEVER auto-confirms the refreshed plan: no reconcile_room call fired from
  // the recovery path itself, and nothing was marked "resolved".
  assert.equal(stateCalls.resolved.length, 0, "the refreshed plan must not be auto-confirmed");
  // A generic error toast must NOT have been shown for this recoverable case.
  assert.equal(stateCalls.error.filter((e) => e != null).length, 0);
});

test("[CARD7-B5] a NON-plan_changed failure (plan_token_required) does not attempt recovery — surfaces as an ordinary error", async () => {
  const { fireUpdate, stateCalls, discoverRoomsCalls } = makeBinder({
    reconcileRoomImpl: async () => {
      throw new Error("Could not reconcile room: plan_token_required");
    },
  });

  await fireUpdate();

  assert.equal(discoverRoomsCalls.length, 0, "recovery must only trigger for plan_changed");
  // The handler resets staleNote to false on every attempt (belt-and-braces
  // clearing of a PRIOR note) — what must never happen is it being set true,
  // which would falsely claim a fresh-map recovery happened.
  assert.ok(!stateCalls.staleNote.includes(true), "no recovery ran, so the stale-map note must never turn on");
  const lastError = stateCalls.error.filter((e) => e != null).at(-1);
  assert.match(lastError, /bind_setup\.failed_reconcile_update/);
});

test("[CARD7-B5b] an unrelated failure (network error, no recognizable reason) also surfaces as an ordinary error, not a dead end", async () => {
  const { fireDismiss, stateCalls, discoverRoomsCalls } = makeBinder({
    reconcileRoomImpl: async () => {
      throw new Error("network timeout");
    },
  });

  await fireDismiss();

  assert.equal(discoverRoomsCalls.length, 0);
  const lastError = stateCalls.error.filter((e) => e != null).at(-1);
  assert.match(lastError, /bind_setup\.failed_reconcile_dismiss/);
});

test("[CARD7-B6] when the silent recovery itself fails, the manual re-discover fallback flag is set (design's literal fallback)", async () => {
  const { fireUpdate, stateCalls } = makeBinder({
    reconcileRoomImpl: async () => {
      throw new Error("Could not reconcile room: plan_changed");
    },
    discoverRoomsImpl: async () => {
      throw new Error("offline");
    },
  });

  await fireUpdate();

  assert.equal(stateCalls.refreshFailed.at(-1), true);
  assert.equal(stateCalls.staleNote.at(-1), false);
  assert.equal(stateCalls.resolved.length, 0);
});

test("[CARD7-B7] the manual re-discover button reuses the same recovery path (fresh discover + status re-poll)", async () => {
  const { fireRediscover, discoverRoomsCalls, getSetupStatusCalls, stateCalls } = makeBinder({
    reconciliation: { map_id: "2", plan_token: "tok-stuck", has_changes: true, reviews: [] },
  });

  await fireRediscover();

  assert.equal(discoverRoomsCalls.length, 1);
  assert.deepEqual(discoverRoomsCalls[0], { vacuumEntityId: VAC, mapId: "2" });
  assert.equal(getSetupStatusCalls.length, 1);
  assert.equal(stateCalls.staleNote.at(-1), true);
});
