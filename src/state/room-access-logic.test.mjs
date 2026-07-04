// Unit tests for accessEditableRooms — the chip list the room-access modal renders for the
// "grants access to" picker. It excludes self + dock rooms, HIDES rooms claimed by ANOTHER
// room (single-inbound constraint) UNLESS this room already selected them, and appends any
// selected-but-unknown ids as synthetic "Missing Room N" entries.
//
// Coverage targets:
//   [RAC-1] no active room -> []
//   [RAC-2] excludes self + dock rooms; plain rooms come through as available chips
//   [RAC-3] a room claimed by ANOTHER room is hidden (single-inbound)
//   [RAC-4] a room claimed by another BUT already selected by this room stays visible
//   [RAC-5] this room's OWN claims never self-hide (excludeRoomId = self)
//   [RAC-6] selected id with no matching room -> appended synthetic "Missing Room N"
//   [RAC-7] null/empty grants_access_to normalizes cleanly (no crash, no phantom missing)
//   [RAC-8] shape of each returned chip (id String, missing/available/claimedBy flags)
//
// Run: node --test src/state/room-access-logic.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyRoomAccessState } from "./room-access.js";
import { applyRoomsState } from "./rooms.js";

// Build a card whose proto has BOTH mixins so the real helpers
// (_normalizeRoomReferenceList, _buildClaimedTargetMap) back accessEditableRooms.
function makeCard(rooms, { activeId = null, mapId = "m1", grants = [] } = {}) {
  const proto = {};
  applyRoomsState(proto);
  applyRoomAccessState(proto);
  const card = Object.create(proto);
  // getRoomsForMap is the only external read — stub it to return the fixture rooms
  // for the requested map (and empty for any other map id).
  card.getRoomsForMap = (id) =>
    String(id) === String(mapId) ? rooms : [];
  // Private working state that activeAccessRoom()/roomAccessFields() read.
  card._roomAccessRoomId = activeId;
  card._roomAccessMapId = activeId == null ? null : mapId;
  card._roomAccessFields =
    activeId == null ? null : { is_dock_room: false, grants_access_to: grants };
  return card;
}

// A room fixture entry as getRoomsForMap yields it.
const R = (id, over = {}) => ({
  id,
  mapId: "m1",
  name: `Room ${id}`,
  isDockRoom: false,
  grantsAccessTo: [],
  ...over,
});

test("[RAC-1] no active room -> empty list", () => {
  const card = makeCard([R(1), R(2)], { activeId: null });
  assert.deepEqual(card.accessEditableRooms(), []);
});

test("[RAC-2] excludes self + dock rooms; other plain rooms are available chips", () => {
  const card = makeCard(
    [R(1), R(2), R(3, { isDockRoom: true })],
    { activeId: 1 }
  );
  const rooms = card.accessEditableRooms();
  const ids = rooms.map((r) => r.id);
  assert.deepEqual(ids, ["2"]);            // self(1) excluded, dock(3) excluded
  assert.equal(rooms[0].available, true);
  assert.equal(rooms[0].missing, false);
  assert.equal(rooms[0].claimedBy, null);
  assert.equal(rooms[0].name, "Room 2");
});

test("[RAC-3] a room claimed by ANOTHER room is hidden (single-inbound)", () => {
  // Room 2 grants access to room 3 -> when editing room 1, room 3 is claimed by
  // another room and NOT selected by 1, so it must be hidden.
  const card = makeCard(
    [R(1), R(2, { grantsAccessTo: ["3"] }), R(3)],
    { activeId: 1, grants: [] }
  );
  const ids = card.accessEditableRooms().map((r) => r.id);
  assert.deepEqual(ids, ["2"]);            // 3 is claimed by 2 -> hidden
});

test("[RAC-4] claimed-by-another BUT already selected by this room stays visible", () => {
  // Same claim as RAC-3, but room 1 already selected room 3 -> it must remain
  // (so the user can see/deselect their existing grant even though 2 also claims it).
  const card = makeCard(
    [R(1), R(2, { grantsAccessTo: ["3"] }), R(3)],
    { activeId: 1, grants: ["3"] }
  );
  const rooms = card.accessEditableRooms();
  const ids = rooms.map((r) => r.id).sort();
  assert.deepEqual(ids, ["2", "3"]);       // 3 survives because selected by 1
  const r3 = rooms.find((r) => r.id === "3");
  assert.equal(r3.missing, false);         // it is a real known room, not synthetic
  assert.equal(r3.available, true);
});

test("[RAC-5] this room's OWN claims never self-hide (excludeRoomId = self)", () => {
  // Room 1 (the edited room) grants access to room 2. _buildClaimedTargetMap excludes
  // room 1, so room 2 is NOT seen as claimed-by-another and stays visible even if 1
  // hasn't (re)selected it in the working fields.
  const card = makeCard(
    [R(1, { grantsAccessTo: ["2"] }), R(2), R(3)],
    { activeId: 1, grants: [] }
  );
  const ids = card.accessEditableRooms().map((r) => r.id).sort();
  assert.deepEqual(ids, ["2", "3"]);       // 1's own claim on 2 does not hide 2
});

test("[RAC-6] selected id with no matching room -> synthetic 'Missing Room N' appended", () => {
  const card = makeCard(
    [R(1), R(2)],
    { activeId: 1, grants: ["99"] }        // 99 is not a real room
  );
  const rooms = card.accessEditableRooms();
  assert.deepEqual(rooms.map((r) => r.id), ["2", "99"]);   // real first, missing appended
  const missing = rooms[1];
  assert.equal(missing.id, "99");
  assert.equal(missing.name, "Missing Room 99");
  assert.equal(missing.missing, true);
  assert.equal(missing.available, true);
  assert.equal(missing.claimedBy, null);
});

test("[RAC-7] null / empty / messy grants_access_to normalizes without phantom chips", () => {
  // null grants -> no missing entries; whitespace/empty entries are dropped by normalize.
  const cNull = makeCard([R(1), R(2)], { activeId: 1, grants: null });
  assert.deepEqual(cNull.accessEditableRooms().map((r) => r.id), ["2"]);

  const cMessy = makeCard([R(1), R(2)], { activeId: 1, grants: ["", "  ", 2] });
  const rooms = cMessy.accessEditableRooms();
  // "2" (coerced) matches the real room 2 -> NOT missing; empties produce nothing.
  assert.deepEqual(rooms.map((r) => r.id), ["2"]);
  assert.equal(rooms[0].missing, false);
});

test("[RAC-8] a selected id that also matches a real room is not duplicated as missing", () => {
  // Room 3 is claimed by room 2 AND selected by room 1: it appears exactly once (as the
  // real known room), never also as a synthetic missing entry.
  const card = makeCard(
    [R(1), R(2, { grantsAccessTo: ["3"] }), R(3)],
    { activeId: 1, grants: ["3"] }
  );
  const rooms = card.accessEditableRooms();
  const threes = rooms.filter((r) => r.id === "3");
  assert.equal(threes.length, 1);
  assert.equal(threes[0].missing, false);  // resolved to the real room, not "Missing Room 3"
});

test("[RAC-9] numeric room ids are stringified in the returned chips", () => {
  const card = makeCard([R(1), R(2)], { activeId: 1 });
  const chip = card.accessEditableRooms()[0];
  assert.strictEqual(chip.id, "2");        // String, not number 2
  assert.equal(typeof chip.id, "string");
});
