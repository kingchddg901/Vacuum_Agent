// Regression test — CARD-5 (#16:A4-STATE-4 card half), "missed-rooms retry is
// map-scoped". retryMissedRooms (src/actions/rooms.js) now takes a SECOND,
// optional parameter, recordedMapId -- the map_id the incomplete-run log was
// recorded against. When it is provided and disagrees with the currently
// active map (this.state.activeMapId()), the function refuses outright via
// showServiceRefusalToast("map_mismatch") and returns
// {queued: false, reason: "map_mismatch"} WITHOUT touching any room. When it
// is omitted (legacy logs / direct callers with no recorded map_id) or it
// agrees with the active map, the existing enable/disable toggle loop runs
// unchanged.
//
// WHY THIS MATTERS: room ids are small per-map integers
// (1-11, [[project_current_room_attribution]] convention), so a user who
// switched maps between an incomplete run and clicking "retry" can have the
// SAME id collide with an unrelated room on the new active map. Every toggle
// goes through {force:true}, deliberately bypassing the composer lock for
// this "post-run recovery" path, so nothing else in the call chain would
// refuse a wrong-map write either -- confirmed by reading toggleRoomEnabled
// (rooms.js): force skips its ONLY guard (hasActiveRun), and it has no
// map-identity check of its own. The binding that invokes this
// (src/bindings/rooms.js, "queue-missed-rooms") now passes the incomplete-run
// log's own map_id through as recordedMapId, and on a map_mismatch result
// leaves the log + confirmations in place (no clear, no generic toast --
// retryMissedRooms already fired the map_mismatch toast itself) so the
// banner stays up and the user can switch maps and retry.
//
// Run: node --test src/actions/rooms-retry-missed-map-scope.test.mjs
//
// FLIP CONVENTION (mirrors core-service-failure.test.mjs): RMS-1 is now a
// real, enforced assertion (the `{ todo: ... }` flag has been removed) --
// it proves a genuine map mismatch refuses and toggles nothing. RMS-2 is the
// control proving a matching recordedMapId still retries normally with no
// refusal toast. RMS-3 is the backward-compat control proving that OMITTING
// recordedMapId entirely (legacy callers / logs that predate this fix) is
// still trusted and proceeds normally -- omission must never become an
// accidental fail-closed for old data.

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyRoomsActions } from "./rooms.js";
import { makeActions } from "./_test-host.mjs";

function makeCard({ activeMapId, activeMapRooms }) {
  // Real VacuumCardActions + a fake host, so `t`/`showToast` come from the class's own
  // delegation rather than being attached here — see _test-host.mjs (R3-BUG-1).
  const card = makeActions({});
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

  const result = await card.retryMissedRooms([3], "A"); // recorded on map A, active map is B

  const wrongMapToggles = card._toggleCalls.filter((c) => c.mapId === "B");
  assert.equal(
    wrongMapToggles.length,
    0,
    `retryMissedRooms silently toggled ${wrongMapToggles.length} room(s) on map B ` +
      `(the wrong map) using room ids recorded against map A: ` +
      JSON.stringify(wrongMapToggles)
  );

  assert.deepEqual(result, { queued: false, reason: "map_mismatch" });

  assert.equal(card.toasts.length, 1, "a map mismatch must raise exactly one refusal toast");
  assert.equal(card.toasts[0].kind, "error");
  assert.match(card.toasts[0].message, /map_mismatch/);
});

test("[RMS-2] the recorded map is still the active map (control -- normal retry unaffected)", async () => {
  const card = makeCard({
    activeMapId: "A",
    activeMapRooms: [
      { id: 3, mapId: "A", enabled: false, name: "Garage (map A)" },
      { id: 7, mapId: "A", enabled: true, name: "Office (map A)" },
    ],
  });

  await card.retryMissedRooms([3], "A"); // recorded on map A, active map is also A -- a match

  const enableCall = card._toggleCalls.find((c) => c.mapId === "A" && c.roomId === 3);
  assert.ok(enableCall, "the matching-map retry never re-enabled the missed room at all");
  assert.equal(enableCall.currentEnabled, false);
  assert.equal(enableCall.opts.force, true);

  assert.deepEqual(card.toasts, [], "no refusal toast on a genuine map match (control)");
});

test("[RMS-3] omitting recordedMapId entirely is trusted, not fail-closed (backward-compat control)", async () => {
  // Legacy incomplete-run logs (or any direct caller) that predate this fix
  // carry no recorded map_id at all. Omitting the second argument must NOT
  // become an accidental way to disable retry for that old data -- it must
  // keep trusting the active map exactly like pre-fix behavior, the same as
  // RMS-1's fixture (map "B" active) but with no recordedMapId supplied.
  const card = makeCard({
    activeMapId: "B",
    activeMapRooms: [
      { id: 3, mapId: "B", enabled: false, name: "Garage (map B)" },
      { id: 7, mapId: "B", enabled: true, name: "Office (map B)" },
    ],
  });

  await card.retryMissedRooms([3]); // no second argument at all -- undefined

  const enableCall = card._toggleCalls.find((c) => c.mapId === "B" && c.roomId === 3);
  assert.ok(enableCall, "omitting recordedMapId must still proceed with the normal retry toggle");
  assert.equal(enableCall.currentEnabled, false);
  assert.equal(enableCall.opts.force, true);

  assert.deepEqual(card.toasts, [], "omitting recordedMapId must not raise a refusal toast");
});
