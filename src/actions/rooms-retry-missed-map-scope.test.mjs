// Regression test — CARD-5 (#16:A4-STATE-4 card half), "missed-rooms retry is
// map-scoped". retryMissedRooms (src/actions/rooms.js:187-208) reads
// this.state.getRoomsForActiveMap() -- WHATEVER map happens to be active right
// now -- and matches missedRoomIds (room ids recorded against the map the
// INCOMPLETE run actually happened on) against that map's rooms by bare id.
// Room ids are small per-map integers (1-11, [[project_current_room_attribution]]
// convention), so a user who switched maps between the incomplete run and
// clicking "retry" can have the SAME id collide with an unrelated room on the
// new active map. Every toggle goes through {force:true} (line 200/203,
// deliberately bypassing the composer lock for this "post-run recovery" path),
// so nothing else in the call chain would refuse a wrong-map write either --
// confirmed by reading toggleRoomEnabled (rooms.js:24-31): force skips its
// ONLY guard (hasActiveRun), and it has no map-identity check of its own.
// The binding that invokes this (src/bindings/rooms.js:402-435,
// "queue-missed-rooms") also never compares the log's map_id to the active
// map -- confirmed by reading the handler in full, no map_id reference at all.
//
// Run: node --test src/actions/rooms-retry-missed-map-scope.test.mjs
//
// FLIP CONVENTION (mirrors core-service-failure.test.mjs): RMS-1 FAILS against
// current rooms.js (a wrong-map id collision still fires a force:true toggle)
// and is expected to PASS once retryMissedRooms (or its binding caller) is
// given the log's recorded map_id and refuses on mismatch, mirroring the same
// "indeterminate/mismatch != proceed" shape this session's RP-029 (ZONE-C-1)
// proof already found applied inconsistently elsewhere in the codebase.
// RMS-2 is the control -- a matching map_id must still retry normally.

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyRoomsActions } from "./rooms.js";

function makeCard({ activeMapId, activeMapRooms }) {
  const proto = {};
  applyRoomsActions(proto);
  const card = Object.create(proto);
  const toggleCalls = [];
  // toggleRoomEnabled lives in the same mixin, on the same prototype -- stub
  // it directly rather than reimplementing the composer-lock logic here (the
  // harness must stay inert; this proof is about retryMissedRooms' OWN
  // map-blindness, not about re-deriving toggleRoomEnabled's behaviour).
  card.toggleRoomEnabled = async (mapId, roomId, currentEnabled, opts) => {
    toggleCalls.push({ mapId, roomId, currentEnabled, opts });
    return { started: false };
  };
  card.state = {
    getRoomsForActiveMap: () => activeMapRooms,
    activeMapId: () => activeMapId,
  };
  card._toggleCalls = toggleCalls;
  return card;
}

test("[RMS-1] a missed-room id collides with an unrelated room on a DIFFERENT now-active map", async () => {
  // The incomplete run happened on map "A"; room id 3 there was missed.
  // The user has since switched to map "B", which also happens to have a
  // room id 3 -- an entirely different physical room.
  const card = makeCard({
    activeMapId: "B",
    activeMapRooms: [
      { id: 3, mapId: "B", enabled: false, name: "Garage (map B)" },
      { id: 7, mapId: "B", enabled: true, name: "Office (map B)" },
    ],
  });

  await card.retryMissedRooms([3]); // room id from map A's incomplete log

  const wrongMapToggles = card._toggleCalls.filter((c) => c.mapId === "B");
  assert.equal(
    wrongMapToggles.length,
    0,
    `retryMissedRooms silently toggled ${wrongMapToggles.length} room(s) on map B ` +
      `(the wrong map) using room ids recorded against map A: ` +
      JSON.stringify(wrongMapToggles)
  );
});

test("[RMS-2] the recorded map is still the active map (control -- normal retry unaffected)", async () => {
  const card = makeCard({
    activeMapId: "A",
    activeMapRooms: [
      { id: 3, mapId: "A", enabled: false, name: "Garage (map A)" },
      { id: 7, mapId: "A", enabled: true, name: "Office (map A)" },
    ],
  });

  await card.retryMissedRooms([3]);

  const enableCall = card._toggleCalls.find((c) => c.mapId === "A" && c.roomId === 3);
  assert.ok(enableCall, "the matching-map retry never re-enabled the missed room at all");
  assert.equal(enableCall.currentEnabled, false);
  assert.equal(enableCall.opts.force, true);
});
