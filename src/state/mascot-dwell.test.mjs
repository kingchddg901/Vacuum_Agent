// Unit tests for the dwell-debounced mascot room tracker (Wave 3).
// Pure state-machine logic, exercised against a stub state that supplies only
// dashboardLifecycle() (the raw current-room name) + getRoomsForActiveMap().
// Run: node --test src/state/mascot-dwell.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyMapState } from "./map.js";

const ROOMS = [
  { id: 1, name: "Kitchen", slug: "kitchen" },
  { id: 2, name: "Hallway", slug: "hallway" },
  { id: 3, name: "Dining Room", slug: "dining_room" },
];

function makeState(rooms = ROOMS) {
  const proto = {};
  applyMapState(proto);
  const s = Object.create(proto);
  s._currentRoomName = null;
  s.dashboardLifecycle = () => ({ active_cleaning_target: s._currentRoomName });
  s.getRoomsForActiveMap = () => rooms;
  return s;
}

test("[MD-1] commits a room only after N consecutive dwell reads", () => {
  const s = makeState();
  s._currentRoomName = "Kitchen";
  assert.equal(s.mascotDwelledRoomId(), null); // 1 — below threshold
  assert.equal(s.mascotDwelledRoomId(), null); // 2
  assert.equal(s.mascotDwelledRoomId(), 1);    // 3 — commits Kitchen
});

test("[MD-2] a brief flicker to another room does NOT hop; sustained dwell does", () => {
  const s = makeState();
  s._currentRoomName = "Kitchen";
  s.mascotDwelledRoomId(); s.mascotDwelledRoomId();
  assert.equal(s.mascotDwelledRoomId(), 1);    // committed Kitchen
  s._currentRoomName = "Hallway";
  assert.equal(s.mascotDwelledRoomId(), 1);    // 1 Hallway read — holds Kitchen
  assert.equal(s.mascotDwelledRoomId(), 1);    // 2 — still holds
  assert.equal(s.mascotDwelledRoomId(), 2);    // 3 — now commits Hallway
});

test("[MD-3] tracks ANY room incl. transit (slug match), not just job targets", () => {
  const s = makeState();
  s._currentRoomName = "Dining Room";          // matches slug 'dining_room'
  s.mascotDwelledRoomId(); s.mascotDwelledRoomId();
  assert.equal(s.mascotDwelledRoomId(), 3);
});

test("[MD-4] blank / sentinel signal holds the last committed room", () => {
  const s = makeState();
  s._currentRoomName = "Kitchen";
  s.mascotDwelledRoomId(); s.mascotDwelledRoomId();
  assert.equal(s.mascotDwelledRoomId(), 1);
  for (const blank of ["", "unknown", "unavailable", null]) {
    s._currentRoomName = blank;
    assert.equal(s.mascotDwelledRoomId(), 1);  // never snaps away on a blank
  }
});

test("[MD-5] an unmatched name never commits (null before first commit)", () => {
  const s = makeState();
  s._currentRoomName = "Garage";               // not a managed room
  assert.equal(s.mascotDwelledRoomId(), null);
  assert.equal(s.mascotDwelledRoomId(), null);
  assert.equal(s.mascotDwelledRoomId(), null);
});

test("[MD-6] with no native current-room, dwells on the live map source current_room", () => {
  const s = makeState();
  s._currentRoomName = null;                         // brand has no native current-room (Eufy)
  s.mapStateSource = () => ({ present: true, current_room: 2 });  // live-pose room = Hallway (id 2)
  assert.equal(s.mascotDwelledRoomId(), null);       // 1 — below threshold
  assert.equal(s.mascotDwelledRoomId(), null);       // 2
  assert.equal(s.mascotDwelledRoomId(), 2);          // 3 — commits Hallway from the live map source
  // native brand current-room, when present, still wins over the live-pose fallback
  s._currentRoomName = "Kitchen";
  s.mascotDwelledRoomId(); s.mascotDwelledRoomId();
  assert.equal(s.mascotDwelledRoomId(), 1);          // commits Kitchen
});
