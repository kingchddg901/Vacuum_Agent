// Regression tests for Defect #8 — post-apply room mutations must DROP the pending applied
// stepped run profile so a subsequent Start runs the FLAT just-edited/reordered selection
// instead of silently re-routing to the SAVED step sequence (which discards the edit/reorder).
//
// toggleRoomEnabled already cleared it; updateRoomFields (the shared path for saveRoomEditor /
// applyRoomProfile / saveRoomTransition / saveRoomAccess) and persistRoomOrdering did NOT.
// Read-only paths must NOT clear.
// Run: node --test src/actions/rooms-clear-applied.test.mjs
//
// Coverage (RCA = Rooms Clear Applied):
//   [RCA-1] updateRoomFields clears the applied run profile (mutation path)
//   [RCA-2] persistRoomOrdering clears the applied run profile (mutation path)
//   [RCA-3] toggleRoomEnabled still clears (behavior preserved)
//   [RCA-4] updateRoomFields no-ops (no clear) when required context is missing
//   [RCA-5] a read-only pull (refreshRoomLearningEstimates) does NOT clear
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyRoomsActions } from "./rooms.js";

// Build a card-like `this` with a spy-able state + stubbed HA plumbing. `calls.cleared`
// counts clearAppliedRunProfile() invocations so we can assert clear-vs-no-clear precisely.
function makeCard(overrides = {}) {
  const proto = {};
  applyRoomsActions(proto);
  const card = Object.create(proto);

  const calls = { cleared: 0, callService: [], callHA: [] };

  card.state = {
    _cleared: () => calls.cleared,
    clearAppliedRunProfile: () => { calls.cleared += 1; },
    vacuumEntityId: () => "vacuum.alfred",
    activeMapId: () => "map_6",
    batteryLevel: () => 80,
    // used by clearQueue / selectAll / retry — harmless defaults
    getRoomsForActiveMap: () => overrides.rooms ?? [],
    findRoomSwitchEntityId: () => "switch.room",
    findRoomOrderNumberEntityId: () => "number.room_order",
    _findRoomSwitchEntities: () => [],
    setRoomEstimates: () => {},
    ...(overrides.state ?? {}),
  };

  // Return a response object so updateRoomFields proceeds into the refresh branch.
  card.callService = async (...args) => { calls.callService.push(args); return { response: { ok: true } }; };
  card.callHA = async (...args) => { calls.callHA.push(args); };

  return { card, calls };
}

test("[RCA-1] updateRoomFields clears the applied run profile", async () => {
  const { card, calls } = makeCard();
  await card.updateRoomFields(3, { clean_mode: "vacuum" });
  assert.equal(calls.cleared, 1);
});

test("[RCA-2] persistRoomOrdering clears the applied run profile", async () => {
  const { card, calls } = makeCard();
  await card.persistRoomOrdering([{ id: 1 }, { id: 2 }]);
  assert.equal(calls.cleared, 1);
});

test("[RCA-3] toggleRoomEnabled still clears (behavior preserved)", async () => {
  const { card, calls } = makeCard();
  await card.toggleRoomEnabled("map_6", 5, false);
  assert.equal(calls.cleared, 1);
});

test("[RCA-4] updateRoomFields no-ops (no clear, no service call) when context missing", async () => {
  const { card, calls } = makeCard({ state: { activeMapId: () => "" } });
  const r = await card.updateRoomFields(3, { clean_mode: "vacuum" });
  assert.equal(r, null);
  assert.equal(calls.cleared, 0);
  assert.equal(calls.callService.length, 0);
});

test("[RCA-5] a read-only estimate pull does NOT clear the applied profile", async () => {
  const { card, calls } = makeCard();
  await card.refreshRoomLearningEstimates();
  assert.equal(calls.cleared, 0);
});
