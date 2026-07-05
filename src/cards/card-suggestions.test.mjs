import { test } from "node:test";
import assert from "node:assert/strict";

import { isManagedVacuum, dashboardSuggestion, roomSuggestion } from "./card-suggestions.js";

// A MANAGED vacuum has companion entities (map-overlays sensor + per-room switches)
// that carry a `vacuum_entity_id` attribute pointing back at it.
function managedHass(vac = "vacuum.alfred") {
  return {
    states: {
      [vac]: { state: "docked", attributes: {} },
      "sensor.alfred_map_overlays": { state: "ok", attributes: { vacuum_entity_id: vac } },
      "switch.alfred_kitchen": { state: "on", attributes: { vacuum_entity_id: vac, room_id: 3 } },
      "switch.alfred_hall": { state: "on", attributes: { vacuum_entity_id: vac, room_id: 5 } },
    },
  };
}

// An UNMANAGED vacuum exists in HA but nothing of ours points at it (another brand).
function unmanagedHass(vac = "vacuum.roomba") {
  return { states: { [vac]: { state: "docked", attributes: {} } } };
}

test("[CS-1] isManagedVacuum: true only when a companion entity carries vacuum_entity_id", () => {
  assert.equal(isManagedVacuum(managedHass(), "vacuum.alfred"), true);
  assert.equal(isManagedVacuum(unmanagedHass(), "vacuum.roomba"), false);
});

test("[CS-2] isManagedVacuum: false for non-vacuum domain, missing id, or absent hass", () => {
  const hass = managedHass();
  assert.equal(isManagedVacuum(hass, "light.kitchen"), false);   // picker fires for every domain
  assert.equal(isManagedVacuum(hass, "vacuum.other"), false);    // a different, unmanaged vacuum
  assert.equal(isManagedVacuum(hass, ""), false);
  assert.equal(isManagedVacuum(hass, undefined), false);
  assert.equal(isManagedVacuum(null, "vacuum.alfred"), false);
  assert.equal(isManagedVacuum({}, "vacuum.alfred"), false);
});

test("[CS-3] dashboardSuggestion: custom:-prefixed config with vacuum_entity_id for OUR vacuums", () => {
  assert.deepEqual(
    dashboardSuggestion(managedHass(), "vacuum.alfred", "vacuum-agent-dashboard"),
    { config: { type: "custom:vacuum-agent-dashboard", vacuum_entity_id: "vacuum.alfred" } }
  );
  // Never suggest for an unmanaged vacuum or a non-vacuum entity.
  assert.equal(dashboardSuggestion(unmanagedHass(), "vacuum.roomba", "vacuum-agent-dashboard"), null);
  assert.equal(dashboardSuggestion(managedHass(), "light.kitchen", "vacuum-agent-dashboard"), null);
});

test("[CS-4] roomSuggestion: pre-fills the vacuum's first room_id", () => {
  assert.deepEqual(
    roomSuggestion(managedHass(), "vacuum.alfred", "eufy-room-card"),
    { config: { type: "custom:eufy-room-card", vacuum_entity_id: "vacuum.alfred", room_id: 3 } }
  );
  assert.equal(roomSuggestion(unmanagedHass(), "vacuum.roomba", "eufy-room-card"), null);
});

test("[CS-5] roomSuggestion: managed via sensor but no room switches → room_id null (still valid)", () => {
  const hass = {
    states: {
      "vacuum.alfred": { state: "docked", attributes: {} },
      "sensor.alfred_map_overlays": { state: "ok", attributes: { vacuum_entity_id: "vacuum.alfred" } },
    },
  };
  assert.deepEqual(
    roomSuggestion(hass, "vacuum.alfred", "eufy-room-card"),
    { config: { type: "custom:eufy-room-card", vacuum_entity_id: "vacuum.alfred", room_id: null } }
  );
});
