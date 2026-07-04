// Unit tests for the pure room-graph + start-readiness logic in state/rooms.js.
// These functions are reached through the applyRoomsState(proto) mixin; each test
// builds a bare card object over the proto and stubs only the state the target
// method actually reads (getRoomsForMap / getRoomsForActiveMap / vacuumState /
// dashboard* accessors / _startStatus).
//
// Coverage targets:
//   [RA-*]  validateRoomAccessUpdate + _roomAccessGraphHasCycle +
//           _buildClaimedTargetMap + _buildRoomAccessAdjacency + roomAccessGraph
//           (self_reference, duplicate_edges, missing_room_references,
//            multiple_inbound single-inbound, real DFS cycle, {valid,issues,
//            normalizedGrantsAccessTo} shape + exact issue codes)
//   [SB-*]  _localStartBlockReason precedence + canStartCleaning +
//           startBlockedReason + hasStartWarning + _startStatusFlag
//   [ORD-*] orphanedRooms (empty until a dock room exists, then non-dock rooms
//           nobody grants access to)
//
// Run: node --test src/state/rooms-logic.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyRoomsState } from "./rooms.js";

function makeCard(over = {}) {
  const proto = {};
  applyRoomsState(proto);
  const card = Object.create(proto);
  Object.assign(card, over);
  return card;
}

// A minimal room object as the access-graph helpers read it: { id, name, grantsAccessTo }.
const room = (id, grantsAccessTo = [], extra = {}) => ({
  id,
  name: `Room ${id}`,
  grantsAccessTo,
  ...extra,
});

/* =========================================================
   RA — ACCESS GRAPH VALIDATOR
   ========================================================= */

test("[RA-1] validateRoomAccessUpdate: clean single edge is valid with normalized output", () => {
  const rooms = [room(1, []), room(2, []), room(3, [])];
  const card = makeCard({ getRoomsForMap: () => rooms });
  const res = card.validateRoomAccessUpdate("m", 1, ["2"]);
  assert.equal(res.valid, true);
  assert.deepEqual(res.issues, []);
  assert.deepEqual(res.normalizedGrantsAccessTo, ["2"]);
});

test("[RA-2] self_reference: a room granting access to itself is flagged by code", () => {
  const rooms = [room(1, []), room(2, [])];
  const card = makeCard({ getRoomsForMap: () => rooms });
  const res = card.validateRoomAccessUpdate("m", 1, ["1"]);
  assert.equal(res.valid, false);
  assert.ok(res.issues.some((i) => i.code === "self_reference"));
  // normalized still keeps the self ref (it IS a known room id) — validity comes from issues.
  assert.deepEqual(res.normalizedGrantsAccessTo, ["1"]);
});

test("[RA-3] duplicate_edges: a repeated target is flagged and de-duplicated in roomIds", () => {
  const rooms = [room(1, []), room(2, []), room(3, [])];
  const card = makeCard({ getRoomsForMap: () => rooms });
  const res = card.validateRoomAccessUpdate("m", 1, ["2", "2", "3"]);
  const dup = res.issues.find((i) => i.code === "duplicate_edges");
  assert.ok(dup, "duplicate_edges issue present");
  assert.deepEqual(dup.roomIds, ["2"]);
  assert.equal(res.valid, false);
  // uniqueRefs preserved in normalized order, de-duplicated.
  assert.deepEqual(res.normalizedGrantsAccessTo, ["2", "3"]);
});

test("[RA-4] missing_room_references: targets not on the map are collected in roomIds", () => {
  const rooms = [room(1, []), room(2, [])];
  const card = makeCard({ getRoomsForMap: () => rooms });
  const res = card.validateRoomAccessUpdate("m", 1, ["2", "9"]);
  const miss = res.issues.find((i) => i.code === "missing_room_references");
  assert.ok(miss, "missing_room_references issue present");
  assert.deepEqual(miss.roomIds, ["9"]);
  assert.equal(res.valid, false);
  // normalized drops the unknown ref (filtered by knownRoomIds).
  assert.deepEqual(res.normalizedGrantsAccessTo, ["2"]);
});

test("[RA-5] missing_room: the room being edited no longer exists on the map", () => {
  const rooms = [room(1, []), room(2, [])];
  const card = makeCard({ getRoomsForMap: () => rooms });
  const res = card.validateRoomAccessUpdate("m", 99, ["2"]);
  assert.ok(res.issues.some((i) => i.code === "missing_room"));
  assert.equal(res.valid, false);
});

test("[RA-6] multiple_inbound: a target already claimed by another room can't get a second inbound edge", () => {
  // Room 3 already grants access to room 2 (2 has an inbound from 3). Room 1 tries to also target 2.
  const rooms = [room(1, []), room(2, []), room(3, ["2"])];
  const card = makeCard({ getRoomsForMap: () => rooms });
  const res = card.validateRoomAccessUpdate("m", 1, ["2"]);
  const inbound = res.issues.find((i) => i.code === "multiple_inbound");
  assert.ok(inbound, "multiple_inbound issue present");
  // roomIds = [target, claimant] = ["2","3"].
  assert.deepEqual(inbound.roomIds, ["2", "3"]);
  assert.equal(res.valid, false);
  // Message names both rooms.
  assert.match(inbound.message, /Room 2/);
  assert.match(inbound.message, /Room 3/);
});

test("[RA-7] multiple_inbound EXCLUDES the room being edited (re-saving your own edge is fine)", () => {
  // Room 1 already grants access to room 2. Re-validating room 1 -> ["2"] must NOT
  // report multiple_inbound, because _buildClaimedTargetMap excludes the edited room.
  const rooms = [room(1, ["2"]), room(2, []), room(3, [])];
  const card = makeCard({ getRoomsForMap: () => rooms });
  const res = card.validateRoomAccessUpdate("m", 1, ["2"]);
  assert.equal(res.valid, true);
  assert.deepEqual(res.issues, []);
});

test("[RA-8] cycle: a real DFS cycle is detected only when no other issues fire", () => {
  // Existing: 2 -> 3 -> 1. Adding 1 -> 2 closes the loop 1->2->3->1.
  const rooms = [room(1, []), room(2, ["3"]), room(3, ["1"])];
  const card = makeCard({ getRoomsForMap: () => rooms });
  const res = card.validateRoomAccessUpdate("m", 1, ["2"]);
  assert.ok(res.issues.some((i) => i.code === "cycle"), "cycle detected");
  assert.equal(res.valid, false);
  // The would-be edge is still normalized (validity comes from issues).
  assert.deepEqual(res.normalizedGrantsAccessTo, ["2"]);
});

test("[RA-9] no cycle for a valid DAG chain (1->2->3)", () => {
  // Existing 2 -> 3. Adding 1 -> 2 forms a chain, not a loop.
  const rooms = [room(1, []), room(2, ["3"]), room(3, [])];
  const card = makeCard({ getRoomsForMap: () => rooms });
  const res = card.validateRoomAccessUpdate("m", 1, ["2"]);
  assert.equal(res.valid, true);
  assert.deepEqual(res.issues, []);
  assert.deepEqual(res.normalizedGrantsAccessTo, ["2"]);
});

test("[RA-10] cycle check is gated: when another issue exists, no cycle code is added", () => {
  // Self-reference AND a would-be loop. Because issues.length > 0 the cycle branch is skipped.
  const rooms = [room(1, ["1"]), room(2, ["1"])];
  const card = makeCard({ getRoomsForMap: () => rooms });
  const res = card.validateRoomAccessUpdate("m", 1, ["1"]);
  assert.ok(res.issues.some((i) => i.code === "self_reference"));
  assert.ok(!res.issues.some((i) => i.code === "cycle"), "cycle gated behind issues.length");
});

test("[RA-11] _roomAccessGraphHasCycle: direct self-loop and disconnected-neighbor handling", () => {
  const card = makeCard();
  // self-loop A -> A is a cycle.
  assert.equal(card._roomAccessGraphHasCycle({ A: ["A"] }), true);
  // simple 2-cycle.
  assert.equal(card._roomAccessGraphHasCycle({ A: ["B"], B: ["A"] }), true);
  // acyclic chain.
  assert.equal(card._roomAccessGraphHasCycle({ A: ["B"], B: ["C"], C: [] }), false);
  // neighbor not present in adjacency is ignored (dangling edge, no crash, no cycle).
  assert.equal(card._roomAccessGraphHasCycle({ A: ["Z"] }), false);
  // empty graph -> no cycle.
  assert.equal(card._roomAccessGraphHasCycle({}), false);
});

test("[RA-12] _buildRoomAccessAdjacency + _normalizeRoomReferenceList coerce/trim/drop empties", () => {
  const card = makeCard();
  const adjacency = card._buildRoomAccessAdjacency([
    room(1, [" 2 ", "", null, 3]),  // trims, drops empty/null, coerces number 3 -> "3"
    room(2, "5"),                   // non-array single value -> ["5"]
    room(3, null),                  // null -> []
  ]);
  assert.deepEqual(adjacency["1"], ["2", "3"]);
  assert.deepEqual(adjacency["2"], ["5"]);
  assert.deepEqual(adjacency["3"], []);
});

test("[RA-13] _buildClaimedTargetMap: excludes the edited room and first claimant wins", () => {
  const card = makeCard();
  const rooms = [room(1, ["4"]), room(2, ["4"]), room(3, ["5"])];
  // Exclude room 1 -> 4 is claimed by room 2 (first remaining claimant), 5 by room 3.
  const claimed = card._buildClaimedTargetMap(rooms, "1");
  assert.equal(claimed.get("4"), "2");
  assert.equal(claimed.get("5"), "3");
  // With no exclusion, room 1 claims 4 first.
  const claimedAll = card._buildClaimedTargetMap(rooms, "");
  assert.equal(claimedAll.get("4"), "1");
});

test("[RA-14] roomAccessGraph: derives requiresAccessFrom (inbound) from grantsAccessTo", () => {
  const rooms = [room(1, ["2", "3"]), room(2, []), room(3, [])];
  const card = makeCard({ getRoomsForActiveMap: () => rooms });
  const graph = card.roomAccessGraph();
  const byId = Object.fromEntries(graph.map((g) => [g.roomId, g]));
  assert.deepEqual(byId["1"].grantsAccessTo, ["2", "3"]);
  assert.deepEqual(byId["1"].requiresAccessFrom, []);
  assert.deepEqual(byId["2"].requiresAccessFrom, ["1"]);
  assert.deepEqual(byId["3"].requiresAccessFrom, ["1"]);
});

/* =========================================================
   ORD — ORPHANED ROOMS
   ========================================================= */

test("[ORD-1] orphanedRooms: empty until a dock room exists", () => {
  const rooms = [room(1, []), room(2, [])]; // no dock room
  const card = makeCard({ getRoomsForActiveMap: () => rooms });
  assert.deepEqual(card.orphanedRooms(), []);
});

test("[ORD-2] orphanedRooms: dock present -> non-dock rooms nobody grants access to", () => {
  // 1 = dock. 1 grants access to 2. 3 is placed by nobody -> orphan. 4 placed by 2.
  const rooms = [
    room(1, ["2"], { isDockRoom: true }),
    room(2, ["4"]),
    room(3, []),
    room(4, []),
  ];
  const card = makeCard({ getRoomsForActiveMap: () => rooms });
  const orphans = card.orphanedRooms().map((r) => r.id);
  // 1 excluded (dock), 2 placed (from 1), 4 placed (from 2), 3 orphaned.
  assert.deepEqual(orphans, [3]);
});

test("[ORD-3] orphanedRooms: the dock room itself is never an orphan even if nobody grants it access", () => {
  const rooms = [
    room(1, ["2"], { isDockRoom: true }), // nobody grants access TO the dock, but it's the dock
    room(2, []),
  ];
  const card = makeCard({ getRoomsForActiveMap: () => rooms });
  assert.deepEqual(card.orphanedRooms(), []); // 1 is dock, 2 is placed -> no orphans
});

test("[ORD-4] orphanedRooms(mapId) uses getRoomsForMap for the explicit-map path", () => {
  const activeRooms = [room(1, [], { isDockRoom: true }), room(9, [])];
  const mapRooms = [room(1, [], { isDockRoom: true }), room(7, [])];
  const card = makeCard({
    getRoomsForActiveMap: () => activeRooms,
    getRoomsForMap: (id) => (id === "m2" ? mapRooms : []),
  });
  assert.deepEqual(card.orphanedRooms("m2").map((r) => r.id), [7]);
});

/* =========================================================
   SB — START-BUTTON READINESS
   ========================================================= */

test("[SB-1] _localStartBlockReason: no enabled rooms wins over everything (highest precedence)", () => {
  const card = makeCard({
    getRoomsForActiveMap: () => [room(1)], // enabled defaults falsy -> count 0
    vacuumState: () => "cleaning",         // would be already_cleaning, but no_rooms wins
  });
  assert.equal(card._localStartBlockReason(), "no_rooms_included");
});

test("[SB-2] _localStartBlockReason: precedence already_cleaning > returning > error (rooms present)", () => {
  const enabled = [{ ...room(1), enabled: true }];
  const mk = (state) =>
    makeCard({ getRoomsForActiveMap: () => enabled, vacuumState: () => state });
  assert.equal(mk("cleaning")._localStartBlockReason(), "already_cleaning");
  assert.equal(mk("returning")._localStartBlockReason(), "returning_to_dock");
  assert.equal(mk("error")._localStartBlockReason(), "vacuum_error");
  assert.equal(mk("docked")._localStartBlockReason(), null); // ready
});

test("[SB-3] canStartCleaning: a local block disables start unless a confirmation is armed", () => {
  const enabled = [{ ...room(1), enabled: true }];
  // Local block (cleaning) with no confirmation -> cannot start.
  const blocked = makeCard({
    getRoomsForActiveMap: () => enabled,
    vacuumState: () => "cleaning",
  });
  assert.equal(blocked.canStartCleaning(), false);

  // Same local block but a confirmation token is armed -> the local block is bypassed,
  // and with no jobControl/_startStatus it falls through to `true`.
  const armed = makeCard({
    getRoomsForActiveMap: () => enabled,
    vacuumState: () => "cleaning",
    _startConfirmation: { confirmToken: "tok-123" },
  });
  assert.equal(armed.startRequiresConfirmation(), true);
  assert.equal(armed.canStartCleaning(), true);
});

test("[SB-4] canStartCleaning: dashboardJobControl.can_start overrides the default-true path", () => {
  const enabled = [{ ...room(1), enabled: true }];
  const card = makeCard({
    getRoomsForActiveMap: () => enabled,
    vacuumState: () => "docked",
    dashboardJobControl: () => ({ can_start: false }),
  });
  assert.equal(card.canStartCleaning(), false);

  const cardYes = makeCard({
    getRoomsForActiveMap: () => enabled,
    vacuumState: () => "docked",
    dashboardJobControl: () => ({ can_start: true }),
  });
  assert.equal(cardYes.canStartCleaning(), true);
});

test("[SB-5] canStartCleaning: falls back to _startStatus.blocked flag when no jobControl", () => {
  const enabled = [{ ...room(1), enabled: true }];
  const blocked = makeCard({
    getRoomsForActiveMap: () => enabled,
    vacuumState: () => "docked",
    _startStatus: { blocked: true },
  });
  assert.equal(blocked.canStartCleaning(), false);

  const ok = makeCard({
    getRoomsForActiveMap: () => enabled,
    vacuumState: () => "docked",
    _startStatus: { blocked: false },
  });
  assert.equal(ok.canStartCleaning(), true);
});

test("[SB-6] startBlockedReason: returns the local code, else jobControl message when blocked", () => {
  const enabled = [{ ...room(1), enabled: true }];
  // Local block -> the reason CODE (renderer localizes it).
  const local = makeCard({
    getRoomsForActiveMap: () => enabled,
    vacuumState: () => "returning",
  });
  assert.equal(local.startBlockedReason(), "returning_to_dock");

  // No local block, jobControl says blocked -> its message string.
  const jc = makeCard({
    getRoomsForActiveMap: () => enabled,
    vacuumState: () => "docked",
    dashboardJobControl: () => ({ blocked: true, message: "Bin is full" }),
  });
  assert.equal(jc.startBlockedReason(), "Bin is full");
});

test("[SB-7] startBlockedReason: jobControl blocked with no message falls back to 'start_blocked'", () => {
  const enabled = [{ ...room(1), enabled: true }];
  const card = makeCard({
    getRoomsForActiveMap: () => enabled,
    vacuumState: () => "docked",
    dashboardJobControl: () => ({ blocked: true }),
  });
  assert.equal(card.startBlockedReason(), "start_blocked");
});

test("[SB-8] startBlockedReason: null when a confirmation is required (the confirm flow owns the label)", () => {
  const enabled = [{ ...room(1), enabled: true }];
  const card = makeCard({
    getRoomsForActiveMap: () => enabled,
    vacuumState: () => "cleaning", // would be a local block
    _startConfirmation: { preflight: { requires_confirmation: true } },
  });
  assert.equal(card.startRequiresConfirmation(), true);
  assert.equal(card.startBlockedReason(), null);
});

test("[SB-9] hasStartWarning: suppressed by any local block, else reflects the warning flag", () => {
  const enabled = [{ ...room(1), enabled: true }];
  // Local block present -> no warning surfaced.
  const blocked = makeCard({
    getRoomsForActiveMap: () => enabled,
    vacuumState: () => "cleaning",
    dashboardJobControl: () => ({ warning: true }),
  });
  assert.equal(blocked.hasStartWarning(), false);

  // No local block, warning flag set -> true.
  const warn = makeCard({
    getRoomsForActiveMap: () => enabled,
    vacuumState: () => "docked",
    dashboardJobControl: () => ({ warning: true }),
  });
  assert.equal(warn.hasStartWarning(), true);

  // No warning flag -> false.
  const clean = makeCard({
    getRoomsForActiveMap: () => enabled,
    vacuumState: () => "docked",
    dashboardJobControl: () => ({}),
  });
  assert.equal(clean.hasStartWarning(), false);
});

test("[SB-10] _startStatusFlag: coerces string/number truthy values and honors the accessor precedence", () => {
  // String "true"/"1"/"yes" -> true; other strings -> false; missing -> false.
  const strFlag = makeCard({ _startStatus: { blocked: "true" } });
  assert.equal(strFlag._startStatusFlag("blocked"), true);
  const oneFlag = makeCard({ _startStatus: { blocked: "1" } });
  assert.equal(oneFlag._startStatusFlag("blocked"), true);
  const yesFlag = makeCard({ _startStatus: { blocked: "YES" } });
  assert.equal(yesFlag._startStatusFlag("blocked"), true);
  const noFlag = makeCard({ _startStatus: { blocked: "nope" } });
  assert.equal(noFlag._startStatusFlag("blocked"), false);
  const missing = makeCard({ _startStatus: {} });
  assert.equal(missing._startStatusFlag("blocked"), false);
  // Boolean passes through directly.
  const boolFlag = makeCard({ _startStatus: { warning: true } });
  assert.equal(boolFlag._startStatusFlag("warning"), true);

  // Precedence: dashboardJobControl beats dashboardStartStatus beats _startStatus.
  const prec = makeCard({
    dashboardJobControl: () => ({ blocked: true }),
    dashboardStartStatus: () => ({ blocked: false }),
    _startStatus: { blocked: false },
  });
  assert.equal(prec._startStatusFlag("blocked"), true);
});
