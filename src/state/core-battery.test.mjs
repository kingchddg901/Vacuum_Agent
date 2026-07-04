// Unit tests for batteryState — the 5-bucket battery banding used by the map's animal
// companion (<animal-svg battery-state>). Bands read battery_level percent, with a hard
// charging override that beats every level band. Thresholds: <=15 low, <=25 warn,
// <=50 mid, else good; unavailable level -> good (least-alarming default).
// Coverage targets:
//   [BAT-1] level bands + exact boundary values (15/25/50 inclusive-lower edges)
//   [BAT-2] charging override beats every level band (incl. low)
//   [BAT-3] battery unavailable (null) -> good; charging still wins over null level
//   [BAT-4] end-to-end through real isCharging()/batteryLevel() reading stubbed hass
//   [BAT-5] non-finite / edge battery_level values fall through to null -> good
// Run: node --test src/state/core-battery.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyCoreState } from "./core.js";

// Band-level harness: stub the two collaborators batteryState() actually reads.
function makeBanded({ charging = false, level = 100 } = {}) {
  const proto = {};
  applyCoreState(proto);
  const card = Object.create(proto);
  card.isCharging = () => charging;
  card.batteryLevel = () => level;
  return card;
}

// End-to-end harness: real isCharging()/batteryLevel()/vacuumObjectId() over a stubbed hass.
function makeWired({ chargingState = "off", batteryAttr } = {}) {
  const proto = {};
  applyCoreState(proto);
  const card = Object.create(proto);
  card.config = { vacuum_entity_id: "vacuum.alfred" };
  card.hass = {
    states: {
      "binary_sensor.alfred_charging": { state: chargingState },
      "vacuum.alfred": { attributes: batteryAttr === undefined ? {} : { battery_level: batteryAttr } },
    },
  };
  return card;
}

test("[BAT-1] level bands + exact inclusive boundaries (15/25/50)", () => {
  // low: <= 15
  assert.equal(makeBanded({ level: 0 }).batteryState(), "low");
  assert.equal(makeBanded({ level: 15 }).batteryState(), "low");   // boundary is low, not warn
  // warn: 15 < level <= 25
  assert.equal(makeBanded({ level: 16 }).batteryState(), "warn");
  assert.equal(makeBanded({ level: 25 }).batteryState(), "warn");  // boundary is warn, not mid
  // mid: 25 < level <= 50
  assert.equal(makeBanded({ level: 26 }).batteryState(), "mid");
  assert.equal(makeBanded({ level: 50 }).batteryState(), "mid");   // boundary is mid, not good
  // good: level > 50
  assert.equal(makeBanded({ level: 51 }).batteryState(), "good");
  assert.equal(makeBanded({ level: 100 }).batteryState(), "good");
});

test("[BAT-2] charging override beats every level band (even low)", () => {
  // Charging must win regardless of how low the level is.
  for (const level of [0, 5, 15, 25, 50, 80, 100]) {
    assert.equal(
      makeBanded({ charging: true, level }).batteryState(),
      "charging",
      `charging should override level=${level}`,
    );
  }
});

test("[BAT-3] null level -> good; charging still wins over a null level", () => {
  assert.equal(makeBanded({ charging: false, level: null }).batteryState(), "good");
  // Override is checked BEFORE the level is even read, so null level + charging = charging.
  assert.equal(makeBanded({ charging: true, level: null }).batteryState(), "charging");
});

test("[BAT-4] end-to-end via real isCharging()/batteryLevel() over stubbed hass", () => {
  // charging sensor on -> charging, whatever the level attr says.
  assert.equal(makeWired({ chargingState: "on", batteryAttr: 12 }).batteryState(), "charging");
  // sensor off + real numeric attr flows through the bands.
  assert.equal(makeWired({ chargingState: "off", batteryAttr: 12 }).batteryState(), "low");
  assert.equal(makeWired({ chargingState: "off", batteryAttr: 20 }).batteryState(), "warn");
  assert.equal(makeWired({ chargingState: "off", batteryAttr: 40 }).batteryState(), "mid");
  assert.equal(makeWired({ chargingState: "off", batteryAttr: 90 }).batteryState(), "good");
  // A non-"on" sensor state (e.g. "unavailable") is treated as not-charging.
  assert.equal(makeWired({ chargingState: "unavailable", batteryAttr: 90 }).batteryState(), "good");
  // Missing battery attr entirely -> batteryLevel() null -> good.
  assert.equal(makeWired({ chargingState: "off" }).batteryState(), "good");
});

test("[BAT-5] non-finite / stringy battery levels resolve via batteryLevel() then band", () => {
  // batteryLevel() coerces with Number(); NaN-producing values -> null -> good.
  assert.equal(makeWired({ chargingState: "off", batteryAttr: "unknown" }).batteryState(), "good");
  assert.equal(makeWired({ chargingState: "off", batteryAttr: "" }).batteryState(), "low"); // Number("")===0 -> finite 0 -> low
  // NOTE: Number(null)===0 (finite), so a literal null attr bands as level 0 -> "low", NOT good.
  assert.equal(makeWired({ chargingState: "off", batteryAttr: null }).batteryState(), "low");
  // A numeric string is a finite number and bands normally.
  assert.equal(makeWired({ chargingState: "off", batteryAttr: "10" }).batteryState(), "low");
  assert.equal(makeWired({ chargingState: "off", batteryAttr: "55" }).batteryState(), "good");
  // Fractional boundary just below 15 is still low; just above is warn.
  assert.equal(makeBanded({ level: 15.0 }).batteryState(), "low");
  assert.equal(makeBanded({ level: 15.01 }).batteryState(), "warn");
});
