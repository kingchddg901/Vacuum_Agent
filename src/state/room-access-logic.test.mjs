// Unit tests for accessEditableRooms — the chip list the room-access modal renders for the
// "grants access to" picker. It excludes self, does not OFFER the dock room, HIDES rooms
// claimed by ANOTHER room (single-inbound constraint) — but both of those last two yield to
// an edge this room has ALREADY selected — and appends any selected-but-unknown ids as
// synthetic missing entries.
//
// A6-AGX-6 changed two things here: the dock exclusion became conditional on
// not-already-selected (it was unconditional, while the claimed-by-another rule two lines
// below it always had that escape hatch — the asymmetry was the bug), and the synthetic
// missing entry stopped carrying an English name.
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
//   [RAC-10] a dock room ALREADY selected by this room stays visible and removable
//   [RAC-11] ... and never falls through to the synthetic-missing list
//   [RAC-12] an unselected dock room is still not offered (the offer rule is unchanged)
//   [RAC-13] isDockRoom is carried onto the chip so the renderer can mark it
//   [RAC-14] the synthetic missing entry carries a code + params, never English prose
//   [RAC-15] the no-active-room refusal is CARD-scoped, so it resolves to the card sentence
//
// Run: node --test src/state/room-access-logic.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyRoomAccessState } from "./room-access.js";
import { applyRoomsState } from "./rooms.js";
import { accessIssueLabel } from "./access-issue-label.js";
import { translate } from "../i18n/index.js";

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
  // A6-AGX-6: no English here any more — see [RAC-14]. State modules hold no `t`.
  assert.equal(missing.name, null);
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

test("[RAC-10] a dock room already selected by this room stays visible", () => {
  // The stored edge room 1 -> dock room 3 predates the rule that stopped offering the
  // dock as a target. Hiding it is what turned a live room into an unrecoverable
  // "missing" chip: the same filter kept room 3 out of the list, so once removed it
  // could never be selected again.
  const card = makeCard(
    [R(1), R(2), R(3, { isDockRoom: true })],
    { activeId: 1, grants: ["3"] }
  );
  const rooms = card.accessEditableRooms();
  assert.deepEqual(rooms.map((r) => r.id), ["2", "3"]);
  const dock = rooms.find((r) => r.id === "3");
  assert.equal(dock.missing, false);       // a REAL room, not a ghost
  assert.equal(dock.available, true);      // and clickable, so the edge can be removed
  assert.equal(dock.name, "Room 3");       // under its own name
});

test("[RAC-11] a selected dock room never also appears as a synthetic missing entry", () => {
  const card = makeCard(
    [R(1), R(3, { isDockRoom: true })],
    { activeId: 1, grants: ["3"] }
  );
  const rooms = card.accessEditableRooms();
  assert.equal(rooms.length, 1);
  assert.equal(rooms[0].missing, false);
  assert.equal(rooms.filter((r) => r.missing).length, 0);
});

test("[RAC-12] an UNSELECTED dock room is still not offered as a target", () => {
  // The fix is narrow on purpose: it only preserves an edge that already exists. A dock
  // room nobody points at must stay out of the picker.
  const card = makeCard(
    [R(1), R(2), R(3, { isDockRoom: true })],
    { activeId: 1, grants: ["2"] }
  );
  assert.deepEqual(card.accessEditableRooms().map((r) => r.id), ["2"]);
});

test("[RAC-13] isDockRoom is carried onto the chip", () => {
  const card = makeCard(
    [R(1), R(2), R(3, { isDockRoom: true })],
    { activeId: 1, grants: ["3"] }
  );
  const rooms = card.accessEditableRooms();
  assert.equal(rooms.find((r) => r.id === "3").isDockRoom, true);
  assert.equal(rooms.find((r) => r.id === "2").isDockRoom, false);   // Boolean, not undefined
});

test("[RAC-14] the synthetic missing entry carries a code + params, not English", () => {
  const card = makeCard([R(1)], { activeId: 1, grants: ["99"] });
  const missing = card.accessEditableRooms()[0];
  assert.equal(missing.name, null);
  assert.equal(missing.nameCode, "room_access.missing_room");
  assert.deepEqual(missing.nameParams, { id: "99" });
  assert.equal(missing.isDockRoom, false);
});

test("[RAC-15] the no-active-room refusal resolves to the CARD sentence, not the backend one", () => {
  // A6-AGX-4 introduced scope: "card" to split the two meanings of `missing_room`
  // and converted the six emitters in state/rooms.js — this seventh one was missed.
  // Unscoped, it fell through to the BACKEND key, whose sentence interpolates {room}
  // and {missing_room}: params this issue does not carry, so the user was shown
  // "{room} still references missing room {missing_room}." with the braces intact.
  const card = makeCard([R(1), R(2)], { activeId: null });
  const [issue] = card.roomAccessValidation().issues;
  assert.equal(issue.scope, "card");

  const label = accessIssueLabel(issue, (k, v) => translate("en", k, v));
  assert.equal(label, "This room no longer exists on the active map.");
  assert.ok(!label.includes("{"), `unfilled placeholder reached the user: ${label}`);
});
