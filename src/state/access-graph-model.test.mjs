// Run: node --test src/state/access-graph-model.test.mjs
//
// Coverage targets — Wave A, src/state/access-graph-model.js
//   [AGM-1]  normalizeRefs: scalar, null, mixed types, blanks
//   [AGM-2]  graphFromRooms: grants + EVERY dock room, not just the first
//   [AGM-3]  withEdges / withDockRoom are immutable and never leak a shared array
//   [AGM-4]  withDockRoom yields at most one dock — the builder cannot make two
//   [AGM-5]  claimedTargets: first claimant wins, exclusion honoured
//   [AGM-6]  hasCycle: self-loop, 2-cycle, deep cycle, DAG, dangling edge
//   [AGM-7]  offerableTargets over a DRAFT graph — the builder's call shape
//   [AGM-8]  offerableTargets excludes BOTH dock rooms on a double-dock map
//   [AGM-9]  unplacedRooms: [] with no dock, else rooms with no parent
//   [AGM-10] validateEdit: every card-scoped issue code, and the clean case
//   [AGM-11] validateEdit does NOT enforce completeness (a graph must be
//            buildable one room at a time)
//   [AGM-12] the modal and a builder holding the same graph get the same answer

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  claimedTargets,
  graphFromRooms,
  hasCycle,
  normalizeRefs,
  offerableTargets,
  unplacedRooms,
  validateEdit,
  withDockRoom,
  withEdges,
} from "./access-graph-model.js";

const R = (id, over = {}) => ({
  id,
  mapId: "m1",
  name: `Room ${id}`,
  isDockRoom: false,
  grantsAccessTo: [],
  ...over,
});

test("[AGM-1] normalizeRefs coerces, trims, and drops blanks", () => {
  assert.deepEqual(normalizeRefs(null), []);
  assert.deepEqual(normalizeRefs(undefined), []);
  assert.deepEqual(normalizeRefs(3), ["3"]);              // bare scalar, not a list
  assert.deepEqual(normalizeRefs([1, "2", " 3 "]), ["1", "2", "3"]);
  assert.deepEqual(normalizeRefs(["", "  ", null, 4]), ["4"]);
});

test("[AGM-2] graphFromRooms captures EVERY dock room", () => {
  const plain = graphFromRooms([R(1, { isDockRoom: true, grantsAccessTo: [2] }), R(2)]);
  assert.deepEqual(plain.dockRoomIds, ["1"]);
  assert.deepEqual(plain.grants, { 1: ["2"], 2: [] });

  // Two dock rooms is a state the validator can genuinely observe
  // (multiple_dock_rooms). Collapsing it to one id would hide half of it — and
  // would offer the second dock room as an access target while the map is
  // invalid, which is what made this a list rather than a scalar.
  const doubled = graphFromRooms([
    R(1, { isDockRoom: true }),
    R(2, { isDockRoom: true }),
    R(3),
  ]);
  assert.deepEqual(doubled.dockRoomIds, ["1", "2"]);
});

test("[AGM-3] withEdges / withDockRoom never mutate the input", () => {
  const rooms = [R(1, { grantsAccessTo: [2] }), R(2), R(3)];
  const base = graphFromRooms(rooms);
  const frozenGrants = JSON.stringify(base.grants);

  const next = withEdges(base, 1, [2, 3]);
  assert.deepEqual(next.grants["1"], ["2", "3"]);
  assert.equal(JSON.stringify(base.grants), frozenGrants, "base graph was mutated");
  assert.notEqual(next.grants, base.grants, "grants object is shared, not copied");

  const docked = withDockRoom(base, 1);
  assert.deepEqual(docked.dockRoomIds, ["1"]);
  assert.deepEqual(base.dockRoomIds, [], "base dock list was mutated");

  // And the room fixture itself must be untouched — a shared array reference
  // would let a draft edit rewrite stored state behind the modal's back.
  assert.deepEqual(rooms[0].grantsAccessTo, [2]);
});

test("[AGM-4] withDockRoom yields at most one dock room", () => {
  const base = graphFromRooms([R(1, { isDockRoom: true }), R(2, { isDockRoom: true })]);
  assert.equal(base.dockRoomIds.length, 2);       // representable...

  // ...but not CONSTRUCTIBLE through the builder's entry point.
  assert.deepEqual(withDockRoom(base, 3).dockRoomIds, ["3"]);
  assert.deepEqual(withDockRoom(base, null).dockRoomIds, []);
});

test("[AGM-5] claimedTargets: first claimant wins, exclusion honoured", () => {
  const graph = graphFromRooms([
    R(1, { grantsAccessTo: [3] }),
    R(2, { grantsAccessTo: [3, 4] }),
    R(3),
    R(4),
  ]);

  const all = claimedTargets(graph, "");
  assert.equal(all.get("3"), "1");        // room 1 iterated first
  assert.equal(all.get("4"), "2");

  // Excluding the claimant frees the target — this is what lets a room keep
  // editing links it already owns.
  const without1 = claimedTargets(graph, "1");
  assert.equal(without1.get("3"), "2");
  const without2 = claimedTargets(graph, "2");
  assert.equal(without2.get("3"), "1");
  assert.equal(without2.has("4"), false);
});

test("[AGM-6] hasCycle: self-loop, pair, deep chain, DAG, dangling edge", () => {
  const g = (grants) => ({ dockRoomIds: [], grants });

  assert.equal(hasCycle(g({ 1: ["1"] })), true);                       // self-loop
  assert.equal(hasCycle(g({ 1: ["2"], 2: ["1"] })), true);             // 2-cycle
  assert.equal(hasCycle(g({ 1: ["2"], 2: ["3"], 3: ["4"], 4: ["2"] })), true);
  assert.equal(hasCycle(g({ 1: ["2", "3"], 2: ["4"], 3: ["4"], 4: [] })), false);
  assert.equal(hasCycle(g({})), false);

  // A dangling edge is a stale REFERENCE, not a loop. Treating the unknown id
  // as a node would report the wrong fault to the user.
  assert.equal(hasCycle(g({ 1: ["99"] })), false);
});

test("[AGM-7] offerableTargets answers over a pure DRAFT graph", () => {
  // The builder's call shape: nothing is stored, the graph is entirely in hand.
  const rooms = [R(1), R(2), R(3), R(4)];
  let graph = withDockRoom({ dockRoomIds: [], grants: {} }, 1);
  graph = withEdges(graph, 1, [2]);

  // What can room 2 grant to? Not itself, not the dock, not room 2's own parent
  // slot — rooms 3 and 4 are unclaimed and on offer.
  const forTwo = offerableTargets(rooms, graph, 2).map((c) => c.id);
  assert.deepEqual(forTwo, ["3", "4"]);

  // Room 2 is claimed by room 1, so room 3 may not claim it too.
  const forThree = offerableTargets(rooms, graph, 3).map((c) => c.id);
  assert.deepEqual(forThree, ["4"]);

  // Room 1 (the dock) still sees its own selection plus what is free.
  const forOne = offerableTargets(rooms, graph, 1).map((c) => c.id);
  assert.deepEqual(forOne, ["2", "3", "4"]);
});

test("[AGM-8] a double-dock map hides BOTH dock rooms, not just the first", () => {
  // The bug the dockRoomIds list exists to prevent: with a scalar dock id, the
  // second dock room would be offered as an ordinary target on a map that is
  // already invalid, inviting an edit that cannot help.
  const rooms = [R(1, { isDockRoom: true }), R(2, { isDockRoom: true }), R(3), R(4)];
  const graph = graphFromRooms(rooms);

  const offered = offerableTargets(rooms, graph, 3).map((c) => c.id);
  assert.deepEqual(offered, ["4"]);
});

test("[AGM-9] unplacedRooms: silent with no dock, else the rooms with no parent", () => {
  const rooms = [R(1), R(2), R(3)];

  // No dock room -> the whole graph is unset. Listing all three as
  // "unconfigured" is noise, not a to-do list.
  assert.deepEqual(unplacedRooms(rooms, graphFromRooms(rooms)), []);

  const docked = [R(1, { isDockRoom: true, grantsAccessTo: [2] }), R(2), R(3)];
  assert.deepEqual(
    unplacedRooms(docked, graphFromRooms(docked)).map((r) => String(r.id)),
    ["3"]
  );

  // Fully built -> nothing left.
  const complete = [
    R(1, { isDockRoom: true, grantsAccessTo: [2] }),
    R(2, { grantsAccessTo: [3] }),
    R(3),
  ];
  assert.deepEqual(unplacedRooms(complete, graphFromRooms(complete)), []);
});

test("[AGM-10] validateEdit raises each card-scoped code, and passes a clean edit", () => {
  const rooms = [R(1), R(2), R(3)];
  const graph = graphFromRooms(rooms);
  const codes = (result) => result.issues.map((i) => i.code);

  const ok = validateEdit(rooms, graph, 1, [2, 3]);
  assert.equal(ok.valid, true);
  assert.deepEqual(ok.issues, []);
  assert.deepEqual(ok.normalizedGrantsAccessTo, ["2", "3"]);

  assert.deepEqual(codes(validateEdit(rooms, graph, 1, [1])), ["self_reference"]);
  assert.deepEqual(codes(validateEdit(rooms, graph, 1, [2, 2])), ["duplicate_edges"]);
  assert.deepEqual(codes(validateEdit(rooms, graph, 1, [99])), ["missing_room_references"]);
  assert.deepEqual(codes(validateEdit(rooms, graph, 99, [1])), ["missing_room"]);

  // Every card-raised issue must be scoped, or accessIssueLabel resolves it
  // against the BACKEND key, whose sentence interpolates params it lacks.
  for (const proposal of [[1], [2, 2], [99]]) {
    for (const issue of validateEdit(rooms, graph, 1, proposal).issues) {
      assert.equal(issue.scope, "card", `unscoped: ${issue.code}`);
    }
  }

  const claimed = graphFromRooms([R(1, { grantsAccessTo: [3] }), R(2), R(3)]);
  const inbound = validateEdit(rooms, claimed, 2, [3]);
  assert.deepEqual(codes(inbound), ["multiple_inbound"]);
  assert.deepEqual(inbound.issues[0].params, { target: "Room 3", claimant: "Room 1" });

  const chain = graphFromRooms([R(1, { grantsAccessTo: [2] }), R(2, { grantsAccessTo: [3] }), R(3)]);
  assert.deepEqual(codes(validateEdit(rooms, chain, 3, [1])), ["cycle"]);
});

test("[AGM-11] validateEdit does not enforce completeness", () => {
  // A graph has to be buildable one room at a time. If a save were refused
  // because the map is not yet fully linked, the first edge could never be
  // saved and the graph could never be built at all. Completeness is enforced
  // at queue-build time instead.
  const rooms = [R(1), R(2), R(3), R(4)];
  const graph = graphFromRooms(rooms);      // no dock room, nothing linked

  const first = validateEdit(rooms, graph, 1, [2]);
  assert.equal(first.valid, true, "the very first edge must be savable");

  const codes = first.issues.map((i) => i.code);
  assert.ok(!codes.includes("missing_dock_room"));
  assert.ok(!codes.includes("missing_dependency"));
  assert.ok(!codes.includes("unreachable_from_dock"));
});

test("[AGM-12] modal-shaped and builder-shaped calls agree on the same graph", () => {
  // The whole reason the question moved out of the prototype: the modal asks
  // with "stored graph + this room's draft", the builder asks with its draft.
  // Given the same resulting graph they must answer identically.
  const rooms = [R(1, { isDockRoom: true, grantsAccessTo: [2] }), R(2), R(3), R(4)];

  // Modal shape: stored state, overlay room 2's unsaved draft of [3].
  const modalGraph = withEdges(graphFromRooms(rooms), 2, [3]);

  // Builder shape: the same tree assembled from nothing.
  let builderGraph = withDockRoom({ dockRoomIds: [], grants: {} }, 1);
  builderGraph = withEdges(builderGraph, 1, [2]);
  builderGraph = withEdges(builderGraph, 2, [3]);
  builderGraph = withEdges(builderGraph, 3, []);
  builderGraph = withEdges(builderGraph, 4, []);

  for (const roomId of [1, 2, 3, 4]) {
    assert.deepEqual(
      offerableTargets(rooms, modalGraph, roomId).map((c) => c.id),
      offerableTargets(rooms, builderGraph, roomId).map((c) => c.id),
      `offerableTargets disagreed for room ${roomId}`
    );
    assert.deepEqual(
      validateEdit(rooms, modalGraph, roomId, [4]).issues.map((i) => i.code),
      validateEdit(rooms, builderGraph, roomId, [4]).issues.map((i) => i.code),
      `validateEdit disagreed for room ${roomId}`
    );
  }

  assert.deepEqual(
    unplacedRooms(rooms, modalGraph).map((r) => String(r.id)),
    unplacedRooms(rooms, builderGraph).map((r) => String(r.id))
  );
});
