// Unit tests for the dashboard card's pure run-launcher logic.
// Run: node --test src/cards/dashboard-dispatch.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { emptyArmed, nextArmed, roomsDisabled, planStart, armedIsValid } from "./dashboard-dispatch.js";

/* =========================================================
   nextArmed — mutual exclusivity (arming is inert)
   ========================================================= */

test("nextArmed: toggling a room arms the rooms source", () => {
  const s = nextArmed(emptyArmed(), { type: "toggleRoom", roomId: 3 });
  assert.equal(s.source, "rooms");
  assert.deepEqual(s.selectedRoomIds, [3]);
  assert.equal(s.profileId, null);
  assert.equal(s.sceneOption, null);
});

test("nextArmed: toggling rooms accumulates and de-selects", () => {
  let s = nextArmed(emptyArmed(), { type: "toggleRoom", roomId: 1 });
  s = nextArmed(s, { type: "toggleRoom", roomId: 2 });
  assert.deepEqual(s.selectedRoomIds, [1, 2]);
  s = nextArmed(s, { type: "toggleRoom", roomId: 1 }); // toggle off
  assert.deepEqual(s.selectedRoomIds, [2]);
  assert.equal(s.source, "rooms");
});

test("nextArmed: de-selecting the last room returns to the neutral state", () => {
  let s = nextArmed(emptyArmed(), { type: "toggleRoom", roomId: 7 });
  s = nextArmed(s, { type: "toggleRoom", roomId: 7 });
  assert.deepEqual(s, emptyArmed());
  assert.equal(s.source, null);
});

test("nextArmed: arming a profile clears any room selection", () => {
  let s = nextArmed(emptyArmed(), { type: "toggleRoom", roomId: 1 });
  s = nextArmed(s, { type: "pickProfile", profileId: "p-abc" });
  assert.equal(s.source, "profile");
  assert.equal(s.profileId, "p-abc");
  assert.deepEqual(s.selectedRoomIds, []);
  assert.equal(s.sceneOption, null);
});

test("nextArmed: arming a scene clears profile and rooms", () => {
  let s = nextArmed(emptyArmed(), { type: "pickProfile", profileId: "p-abc" });
  s = nextArmed(s, { type: "pickScene", option: "Quick Tidy" });
  assert.equal(s.source, "scene");
  assert.equal(s.sceneOption, "Quick Tidy");
  assert.equal(s.profileId, null);
  assert.deepEqual(s.selectedRoomIds, []);
});

test("nextArmed: arming rooms after a scene clears the scene", () => {
  let s = nextArmed(emptyArmed(), { type: "pickScene", option: "Quick Tidy" });
  s = nextArmed(s, { type: "toggleRoom", roomId: 4 });
  assert.equal(s.source, "rooms");
  assert.equal(s.sceneOption, null);
  assert.deepEqual(s.selectedRoomIds, [4]);
});

test("nextArmed: empty profile/scene picks clear to neutral", () => {
  let s = nextArmed(emptyArmed(), { type: "pickProfile", profileId: "p" });
  s = nextArmed(s, { type: "pickProfile", profileId: "" });
  assert.deepEqual(s, emptyArmed());
  s = nextArmed(emptyArmed(), { type: "pickScene", option: "" });
  assert.deepEqual(s, emptyArmed());
});

test("nextArmed: clear resets everything; unknown actions are inert", () => {
  let s = nextArmed(emptyArmed(), { type: "toggleRoom", roomId: 2 });
  assert.deepEqual(nextArmed(s, { type: "clear" }), emptyArmed());
  assert.deepEqual(nextArmed(s, { type: "noop" }), s); // unchanged
  assert.deepEqual(nextArmed(s, undefined), s);
});

test("nextArmed: does not mutate its input", () => {
  const s0 = nextArmed(emptyArmed(), { type: "toggleRoom", roomId: 1 });
  const snapshot = JSON.parse(JSON.stringify(s0));
  nextArmed(s0, { type: "toggleRoom", roomId: 2 });
  assert.deepEqual(s0, snapshot);
});

test("roomsDisabled: true only when a profile or scene is armed", () => {
  assert.equal(roomsDisabled(emptyArmed()), false);
  assert.equal(roomsDisabled(nextArmed(emptyArmed(), { type: "toggleRoom", roomId: 1 })), false);
  assert.equal(roomsDisabled(nextArmed(emptyArmed(), { type: "pickProfile", profileId: "p" })), true);
  assert.equal(roomsDisabled(nextArmed(emptyArmed(), { type: "pickScene", option: "S" })), true);
});

/* =========================================================
   armedIsValid — re-validate armed source against live data
   ========================================================= */

test("armedIsValid: nothing / rooms armed is always valid", () => {
  assert.equal(armedIsValid(emptyArmed(), {}), true);
  const rooms = nextArmed(emptyArmed(), { type: "toggleRoom", roomId: 1 });
  assert.equal(armedIsValid(rooms, { sceneOptions: [], profileIds: [] }), true);
});

test("armedIsValid: scene valid only when the option still exists live", () => {
  const armed = nextArmed(emptyArmed(), { type: "pickScene", option: "Quick Tidy" });
  assert.equal(armedIsValid(armed, { sceneOptions: ["Quick Tidy", "Deep"] }), true);
  assert.equal(armedIsValid(armed, { sceneOptions: ["Deep"] }), false); // removed in app
  assert.equal(armedIsValid(armed, { sceneOptions: [] }), false);
});

test("armedIsValid: profile valid only when the id still exists live", () => {
  const armed = nextArmed(emptyArmed(), { type: "pickProfile", profileId: "p-abc" });
  assert.equal(armedIsValid(armed, { profileIds: ["p-abc", "p-xyz"] }), true);
  assert.equal(armedIsValid(armed, { profileIds: ["p-xyz"] }), false); // deleted
});

/* =========================================================
   planStart — the Start dispatcher (the only producer of calls)
   ========================================================= */

const CTX = {
  vacuumEntityId: "vacuum.alfred",
  mapId: "6",
  sceneEntityId: "select.alfred_scene",
  rooms: [
    { entityId: "switch.alfred_kitchen", roomId: 1, mapId: "6", currentlyOn: false },
    { entityId: "switch.alfred_lounge",  roomId: 2, mapId: "6", currentlyOn: true  },
    { entityId: "switch.alfred_bedroom", roomId: 3, mapId: "6", currentlyOn: false },
  ],
};

test("planStart: nothing armed → no calls (nothing fires before Start)", () => {
  assert.deepEqual(planStart(emptyArmed(), CTX), []);
});

test("planStart: scene armed → a single select.select_option (the run itself)", () => {
  const armed = nextArmed(emptyArmed(), { type: "pickScene", option: "Quick Tidy" });
  const plan = planStart(armed, CTX);
  assert.deepEqual(plan, [
    { domain: "select", service: "select_option",
      data: { entity_id: "select.alfred_scene", option: "Quick Tidy" } },
  ]);
});

test("planStart: scene armed but no scene entity resolved → no calls", () => {
  const armed = nextArmed(emptyArmed(), { type: "pickScene", option: "Quick Tidy" });
  assert.deepEqual(planStart(armed, { ...CTX, sceneEntityId: null }), []);
});

test("planStart: profile armed → start_run_profile with id + map", () => {
  const armed = nextArmed(emptyArmed(), { type: "pickProfile", profileId: "p-abc" });
  assert.deepEqual(planStart(armed, CTX), [
    { domain: "eufy_vacuum", service: "start_run_profile",
      data: { vacuum_entity_id: "vacuum.alfred", profile_id: "p-abc", map_id: "6" } },
  ]);
});

test("planStart: rooms armed → reconcile switches then start_selected_rooms", () => {
  // Select rooms 1 + 2. Room 1 is off (→ turn_on), room 2 already on (no-op),
  // room 3 is off and unselected (no-op). Last call starts the run.
  let armed = nextArmed(emptyArmed(), { type: "toggleRoom", roomId: 1 });
  armed = nextArmed(armed, { type: "toggleRoom", roomId: 2 });
  const plan = planStart(armed, CTX);
  assert.deepEqual(plan, [
    { domain: "switch", service: "turn_on", data: { entity_id: "switch.alfred_kitchen" } },
    { domain: "eufy_vacuum", service: "start_selected_rooms",
      data: { vacuum_entity_id: "vacuum.alfred", map_id: "6" } },
  ]);
});

test("planStart: rooms armed → turns OFF an on-switch that is not selected", () => {
  // Select only room 1; room 2 is currently on and must be turned off first.
  const armed = nextArmed(emptyArmed(), { type: "toggleRoom", roomId: 1 });
  const plan = planStart(armed, CTX);
  assert.deepEqual(plan, [
    { domain: "switch", service: "turn_on",  data: { entity_id: "switch.alfred_kitchen" } },
    { domain: "switch", service: "turn_off", data: { entity_id: "switch.alfred_lounge" } },
    { domain: "eufy_vacuum", service: "start_selected_rooms",
      data: { vacuum_entity_id: "vacuum.alfred", map_id: "6" } },
  ]);
});

test("planStart: dirty per-room fields are persisted before the run", () => {
  let armed = nextArmed(emptyArmed(), { type: "toggleRoom", roomId: 3 });
  const ctx = {
    ...CTX,
    rooms: [
      ...CTX.rooms.slice(0, 2),
      { entityId: "switch.alfred_bedroom", roomId: 3, mapId: "6", currentlyOn: false,
        dirty: true, fields: { clean_mode: "mop", clean_passes: 2 } },
    ],
  };
  const plan = planStart(armed, ctx);
  assert.deepEqual(plan[0], {
    domain: "eufy_vacuum", service: "update_room_fields",
    data: { vacuum_entity_id: "vacuum.alfred", map_id: "6", room_id: 3, clean_mode: "mop", clean_passes: 2 },
  });
  // room 2 (on, unselected) is turned off; room 3 (selected, off) turned on; then start.
  assert.equal(plan.at(-1).service, "start_selected_rooms");
  assert.ok(plan.some((c) => c.service === "turn_on" && c.data.entity_id === "switch.alfred_bedroom"));
  assert.ok(plan.some((c) => c.service === "turn_off" && c.data.entity_id === "switch.alfred_lounge"));
});

test("planStart: null fields from a committed-seeded draft are stripped (backend rejects present null)", () => {
  // Regression for DC-1: a vacuum-only room's committed fields carry null
  // fan_speed/water_level/clean_intensity; the backend update_room_fields schema
  // types those as optional strings and rejects a PRESENT null, which would abort
  // the whole Start. The dispatched payload must contain no null values.
  const armed = nextArmed(emptyArmed(), { type: "toggleRoom", roomId: 3 });
  const ctx = {
    ...CTX,
    rooms: [
      ...CTX.rooms.slice(0, 2),
      {
        entityId: "switch.alfred_bedroom", roomId: 3, mapId: "6", currentlyOn: false,
        dirty: true,
        fields: {
          clean_mode: "vacuum", fan_speed: null, water_level: null,
          clean_intensity: null, clean_passes: 1, edge_mopping: false,
        },
      },
    ],
  };
  const update = planStart(armed, ctx).find((c) => c.service === "update_room_fields");
  assert.ok(update, "expected an update_room_fields call");
  // No null/undefined values reach the backend.
  for (const [k, v] of Object.entries(update.data)) {
    assert.ok(v != null, `field ${k} must not be null/undefined in the dispatched payload`);
  }
  // The fields that DO have values survive (incl. falsy-but-valid edge_mopping:false).
  assert.equal(update.data.clean_mode, "vacuum");
  assert.equal(update.data.clean_passes, 1);
  assert.equal(update.data.edge_mopping, false);
  assert.ok(!("fan_speed" in update.data), "null fan_speed stripped");
  assert.ok(!("water_level" in update.data), "null water_level stripped");
  assert.ok(!("clean_intensity" in update.data), "null clean_intensity stripped");
});

test("planStart: rooms armed but selection empty after filtering → no calls", () => {
  // armed claims room 9 which isn't in ctx.rooms.
  const armed = { source: "rooms", selectedRoomIds: [9], profileId: null, sceneOption: null };
  assert.deepEqual(planStart(armed, CTX), []);
});

test("planStart: missing vacuum entity → no calls", () => {
  const armed = nextArmed(emptyArmed(), { type: "pickProfile", profileId: "p" });
  assert.deepEqual(planStart(armed, { ...CTX, vacuumEntityId: undefined }), []);
});
