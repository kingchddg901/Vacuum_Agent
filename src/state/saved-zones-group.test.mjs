// Unit tests for the saved-zones panel projections in src/state/saved-zones.js.
// savedZonesGrouped() buckets zones under the room they are FILED under (z.room_number),
// emitting one group per room that has zones IN LIVE-MAP ORDER, then a trailing
// "Unassigned" group (room_id:null) for zones whose room_number is null OR points at a
// room not on the current map (re-mapped / deleted). selectedSavedZoneIds() projects the
// transient selection Set onto the saved-zone order the panel shows/dispatches.
//
// Coverage targets:
//   [SZ-*]  savedZonesGrouped   (HIGH)  — grouping, live-map order, Unassigned bucket rules
//   [SEL-*] selectedSavedZoneIds (MED)  — Set -> ordered id list, empty/no-Set fast paths
//
// Run: node --test src/state/saved-zones-group.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applySavedZonesState } from "./saved-zones.js";

function makeState() {
  const proto = {};
  applySavedZonesState(proto);
  return Object.create(proto);
}

// Build a card with a fixed saved-zone list + room list. Rooms drive both membership
// (roomById) and group ORDER. savedZones() is stubbed directly so grouping is isolated
// from the library/map-segments plumbing.
function withCard({ zones = [], rooms = [] } = {}) {
  const s = makeState();
  s.savedZones = () => zones;
  s.getRoomsForActiveMap = () => rooms;
  return s;
}

const groupShape = (g) => ({ room_id: g.room_id, name: g.name, ids: g.zones.map((z) => z.id) });

// ---- savedZonesGrouped -------------------------------------------------------

test("[SZ-1] empty zone list -> [] (no groups, even with rooms present)", () => {
  const s = withCard({ zones: [], rooms: [{ room_id: 1, name: "Kitchen" }] });
  assert.deepEqual(s.savedZonesGrouped(), []);
});

test("[SZ-2] one group per room WITH zones, in live-map room order (not zone order)", () => {
  // Rooms declared 3,1,2 -> groups must come out 3,1,2. Zones interleave rooms.
  const rooms = [
    { room_id: 3, name: "Bath" },
    { room_id: 1, name: "Kitchen" },
    { room_id: 2, name: "Living" },
  ];
  const zones = [
    { id: "a", room_number: 1 },
    { id: "b", room_number: 3 },
    { id: "c", room_number: 2 },
    { id: "d", room_number: 1 },
  ];
  const groups = s_or(withCard({ zones, rooms }).savedZonesGrouped());
  assert.deepEqual(groups, [
    { room_id: 3, name: "Bath", ids: ["b"] },
    { room_id: 1, name: "Kitchen", ids: ["a", "d"] },   // both room-1 zones, in zone order
    { room_id: 2, name: "Living", ids: ["c"] },
  ]);
});

test("[SZ-3] a room with NO zones is skipped (no empty group emitted)", () => {
  const rooms = [
    { room_id: 1, name: "Kitchen" },
    { room_id: 2, name: "Empty" },      // no zones filed here
    { room_id: 3, name: "Bath" },
  ];
  const zones = [
    { id: "z1", room_number: 1 },
    { id: "z3", room_number: 3 },
  ];
  const groups = s_or(withCard({ zones, rooms }).savedZonesGrouped());
  assert.deepEqual(groups, [
    { room_id: 1, name: "Kitchen", ids: ["z1"] },
    { room_id: 3, name: "Bath", ids: ["z3"] },
  ]);
});

test("[SZ-4] null room_number -> trailing Unassigned bucket (room_id null, name null)", () => {
  const rooms = [{ room_id: 1, name: "Kitchen" }];
  const zones = [
    { id: "u1", room_number: null },
    { id: "k1", room_number: 1 },
    { id: "u2", room_number: undefined },   // == null via ==
  ];
  const groups = s_or(withCard({ zones, rooms }).savedZonesGrouped());
  assert.deepEqual(groups, [
    { room_id: 1, name: "Kitchen", ids: ["k1"] },
    { room_id: null, name: null, ids: ["u1", "u2"] },
  ]);
  // Unassigned is LAST.
  assert.equal(groups[groups.length - 1].room_id, null);
});

test("[SZ-5] room_number that is NOT a room on the current map -> Unassigned (re-map/deleted)", () => {
  const rooms = [{ room_id: 1, name: "Kitchen" }];
  const zones = [
    { id: "k", room_number: 1 },
    { id: "ghost", room_number: 99 },   // room 99 not on this map
  ];
  const groups = s_or(withCard({ zones, rooms }).savedZonesGrouped());
  assert.deepEqual(groups, [
    { room_id: 1, name: "Kitchen", ids: ["k"] },
    { room_id: null, name: null, ids: ["ghost"] },
  ]);
});

test("[SZ-6] NO Unassigned group when every zone maps to a live room", () => {
  const rooms = [{ room_id: 1, name: "Kitchen" }, { room_id: 2, name: "Bath" }];
  const zones = [{ id: "a", room_number: 1 }, { id: "b", room_number: 2 }];
  const groups = withCard({ zones, rooms }).savedZonesGrouped();
  assert.equal(groups.length, 2);
  assert.ok(groups.every((g) => g.room_id !== null));
});

test("[SZ-7] string/number room key coerce equal (room_id 1 matches room_number '1')", () => {
  // room.room_id is a number, z.room_number is a string; String() on both must match.
  const rooms = [{ room_id: 1, name: "Kitchen" }];
  const zones = [{ id: "s", room_number: "1" }];
  const groups = s_or(withCard({ zones, rooms }).savedZonesGrouped());
  assert.deepEqual(groups, [{ room_id: 1, name: "Kitchen", ids: ["s"] }]);
  // ... and the reverse: string room_id vs number room_number.
  const rooms2 = [{ room_id: "7", name: "Den" }];
  const zones2 = [{ id: "n", room_number: 7 }];
  const groups2 = s_or(withCard({ zones: zones2, rooms: rooms2 }).savedZonesGrouped());
  assert.deepEqual(groups2, [{ room_id: "7", name: "Den", ids: ["n"] }]);
});

test("[SZ-8] room_number 0 is a real key (not treated as null) when room 0 is on the map", () => {
  // z.room_number == 0 must NOT fall into Unassigned: the guard is `== null`, not falsy.
  const rooms = [{ room_id: 0, name: "Zero" }, { room_id: 1, name: "Kitchen" }];
  const zones = [{ id: "z", room_number: 0 }, { id: "k", room_number: 1 }];
  const groups = s_or(withCard({ zones, rooms }).savedZonesGrouped());
  assert.deepEqual(groups, [
    { room_id: 0, name: "Zero", ids: ["z"] },
    { room_id: 1, name: "Kitchen", ids: ["k"] },
  ]);
});

test("[SZ-9] no rooms at all (getRoomsForActiveMap absent) -> every zone Unassigned", () => {
  // getRoomsForActiveMap missing exercises the `?.() ?? []` fallback -> roomById empty.
  const s = makeState();
  s.savedZones = () => [
    { id: "a", room_number: 1 },
    { id: "b", room_number: null },
  ];
  // deliberately DO NOT set s.getRoomsForActiveMap
  const groups = s.savedZonesGrouped();
  assert.deepEqual(groups.map(groupShape), [
    { room_id: null, name: null, ids: ["a", "b"] },
  ]);
});

test("[SZ-10] a null zone entry is bucketed as Unassigned (z?. optional chain, no throw)", () => {
  const rooms = [{ room_id: 1, name: "Kitchen" }];
  const zones = [null, { id: "k", room_number: 1 }];
  // Use the RAW groups here (not s_or): the null zone is bucketed by ref, and asserting
  // over the live object proves the `z?.room_number` optional chain didn't throw.
  const groups = withCard({ zones, rooms }).savedZonesGrouped();
  assert.deepEqual(groupShape(groups[0]), { room_id: 1, name: "Kitchen", ids: ["k"] });
  assert.equal(groups[1].room_id, null);
  assert.equal(groups[1].zones.length, 1);
  assert.equal(groups[1].zones[0], null);   // the null entry filed into Unassigned
});

test("[SZ-11] group.zones are the LIVE zone objects (same refs, filed order preserved)", () => {
  const rooms = [{ room_id: 5, name: "Office" }];
  const z1 = { id: "x", room_number: 5, extra: 1 };
  const z2 = { id: "y", room_number: 5, extra: 2 };
  const groups = withCard({ zones: [z1, z2], rooms }).savedZonesGrouped();
  assert.equal(groups[0].zones[0], z1);   // identity, not a copy
  assert.equal(groups[0].zones[1], z2);
});

// ---- selectedSavedZoneIds ----------------------------------------------------

test("[SEL-1] no selection Set at all -> [] (fast path, never touches savedZones)", () => {
  const s = makeState();
  let called = false;
  s.savedZones = () => { called = true; return []; };
  // _savedZoneSelection undefined
  assert.deepEqual(s.selectedSavedZoneIds(), []);
  assert.equal(called, false, "should short-circuit before reading savedZones()");
});

test("[SEL-2] empty selection Set -> [] (size 0 fast path)", () => {
  const s = withCard({ zones: [{ id: "a", room_number: 1 }] });
  s._savedZoneSelection = new Set();
  assert.deepEqual(s.selectedSavedZoneIds(), []);
});

test("[SEL-3] projects selection onto savedZones() order, filtering non-selected", () => {
  // savedZones order c,a,b ; selection {a,b} -> ids come out in list order [a,b], not Set order.
  const s = withCard({
    zones: [{ id: "c", room_number: 1 }, { id: "a", room_number: 1 }, { id: "b", room_number: 2 }],
  });
  s._savedZoneSelection = new Set(["b", "a"]);   // insertion order b,a
  assert.deepEqual(s.selectedSavedZoneIds(), ["a", "b"]);   // list order wins
});

test("[SEL-4] selected id no longer in savedZones() is dropped (stale id not carried)", () => {
  const s = withCard({ zones: [{ id: "a", room_number: 1 }] });
  s._savedZoneSelection = new Set(["a", "gone"]);
  assert.deepEqual(s.selectedSavedZoneIds(), ["a"]);
});

test("[SEL-5] numeric zone ids match string-keyed selection (String(z.id) coercion)", () => {
  // Set holds string ids (that's how toggleSavedZoneSelection stores them); z.id is numeric.
  const s = withCard({ zones: [{ id: 10, room_number: 1 }, { id: 20, room_number: 1 }] });
  s._savedZoneSelection = new Set(["20"]);
  assert.deepEqual(s.selectedSavedZoneIds(), ["20"]);   // returned as strings
});

test("[SEL-6] selectedSavedZoneCount mirrors selectedSavedZoneIds().length", () => {
  const s = withCard({
    zones: [{ id: "a", room_number: 1 }, { id: "b", room_number: 1 }, { id: "c", room_number: 1 }],
  });
  s._savedZoneSelection = new Set(["a", "c", "stale"]);
  assert.equal(s.selectedSavedZoneCount(), 2);
  assert.equal(s.selectedSavedZoneCount(), s.selectedSavedZoneIds().length);
});

// small helper: map groups to their comparable shape, guarding against undefined
function s_or(groups) {
  return groups.map(groupShape);
}
