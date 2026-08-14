// Run: node --test src/state/resolved-entity.test.mjs
//
// live:ENT-10 — the card derived its OWN entity ids.
//
// `batteryLevel()` read `sensor.${objectId}_battery` and `isCharging()` read
// `binary_sensor.${objectId}_charging`, both built from the vacuum's object_id.
// That is the same naming assumption ENT-1/ENT-5 repaired on the Python side —
// a FIFTH copy of it, in a language none of those fixes reach.
//
// Issue #49 is the worked example: the backend resolves
// `sensor.living_room_eufy_clean_x10_pro_omni_battery` and it reads 100, while
// the card derives `sensor.robovac_x10_pro_omni_battery`, which does not exist,
// and draws nothing. The reporter sees "no battery" on an install where battery
// resolution is provably working.
//
// Coverage (RE = Resolved Entity):
//   [RE-1] the resolved id WINS over the derived one
//   [RE-2] no resolved id -> derivation, byte-identical to before
//   [RE-3] charging carries the identical rescue (the neighbouring seam)
//   [RE-4] the source really reads resolved_entities, not just these fakes

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Mirror of the accessors under test. The real ones hang off the card
// prototype, which needs a DOM + hass; the logic being pinned is the
// precedence, so replicate exactly that and pin the source separately [RE-4].
function makeCard({ vacuum, states, resolved }) {
  return {
    vacuumObjectId: () => (vacuum ? vacuum.split(".")[1] : null),
    dashboardSnapshot: () => ({ resolved_entities: resolved || {} }),
    stateOf(id) {
      return states[id];
    },
    resolvedEntity(role) {
      const id = this.dashboardSnapshot()?.resolved_entities?.[role];
      return typeof id === "string" && id ? id : null;
    },
    batteryLevel() {
      const objectId = this.vacuumObjectId();
      const batteryId =
        this.resolvedEntity("battery") ||
        (objectId ? `sensor.${objectId}_battery` : null);
      if (!batteryId) return null;
      const raw = this.stateOf(batteryId);
      if (raw == null || raw === "" || raw === "unavailable" || raw === "unknown") {
        return null;
      }
      const n = Number(raw);
      return Number.isFinite(n) ? n : null;
    },
    isCharging() {
      const objectId = this.vacuumObjectId();
      const chargingId =
        this.resolvedEntity("charging") ||
        (objectId ? `binary_sensor.${objectId}_charging` : null);
      if (!chargingId) return false;
      return this.stateOf(chargingId) === "on";
    },
  };
}

test("[RE-1] issue #49's exact shape: the resolved id wins", () => {
  const card = makeCard({
    vacuum: "vacuum.robovac_x10_pro_omni",
    resolved: { battery: "sensor.living_room_eufy_clean_x10_pro_omni_battery" },
    states: { "sensor.living_room_eufy_clean_x10_pro_omni_battery": "100" },
  });
  assert.equal(card.batteryLevel(), 100);
});

test("[RE-2] no resolved id -> derivation, unchanged", () => {
  const card = makeCard({
    vacuum: "vacuum.alfred",
    resolved: {},
    states: { "sensor.alfred_battery": "72" },
  });
  assert.equal(card.batteryLevel(), 72);
});

test("[RE-2b] a resolved id that has no state must not mask the truth", () => {
  // Falling back to derivation here would be WRONG: the resolver chose this
  // entity, so an unknown reading is unknown, not an invitation to guess again.
  const card = makeCard({
    vacuum: "vacuum.alfred",
    resolved: { battery: "sensor.somewhere_else_battery" },
    states: { "sensor.alfred_battery": "72" },
  });
  assert.equal(card.batteryLevel(), null);
});

test("[RE-3] charging carries the identical rescue", () => {
  const card = makeCard({
    vacuum: "vacuum.robovac_x10_pro_omni",
    resolved: { charging: "binary_sensor.living_room_eufy_clean_x10_pro_omni_charging" },
    states: { "binary_sensor.living_room_eufy_clean_x10_pro_omni_charging": "on" },
  });
  assert.equal(card.isCharging(), true);

  const derived = makeCard({
    vacuum: "vacuum.alfred",
    resolved: {},
    states: { "binary_sensor.alfred_charging": "on" },
  });
  assert.equal(derived.isCharging(), true);
});

test("[RE-4] the shipped source consults resolved_entities", () => {
  // The fakes above prove the PRECEDENCE. This proves the real accessors were
  // actually rewired — a green mirror over unchanged source is the failure mode
  // this pin exists to stop.
  const src = readFileSync(new URL("./core.js", import.meta.url), "utf8");
  assert.match(src, /resolved_entities/, "resolvedEntity() no longer reads the snapshot field");
  assert.match(
    src,
    /resolvedEntity\("battery"\)/,
    "batteryLevel() stopped preferring the resolved id",
  );
  assert.match(
    src,
    /resolvedEntity\("charging"\)/,
    "isCharging() stopped preferring the resolved id",
  );
});
