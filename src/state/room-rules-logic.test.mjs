// Unit tests for the pure entity-aware rule logic in room-rules.js — reached through the
// applyRoomRulesState mixin with a proto stub. These cover the descriptor category/operator
// derivation, draft validation (incl. the clean_passes meaningful-change gate), the entity
// search scoring tiers, and the operator-group filtering.
//
// Coverage targets:
//   [RE-*]  ruleEntityDescriptor      — domain+options+state -> category/operators/valueMode
//   [RV-*]  roomRulesDraftIsValid      — entityExists + operator allowed + value-mode + modifier gate
//   [RS-*]  ruleEntitySearchResults    — scoreEntitySearch tiers, min-2 gate, desc sort + tiebreak
//   [OG-*]  ruleOperatorGroups         — filter 5 fixed groups to allowed ops, drop empty
//
// Run: node --test src/state/room-rules-logic.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyRoomRulesState } from "./room-rules.js";

// Build a card stub. `entities` maps entity_id -> { state, attributes }. The mixin's
// descriptor reads this.entity(id); the search reads this.hass.states (same shape).
function makeCard(entities = {}) {
  const proto = {};
  applyRoomRulesState(proto);
  const card = Object.create(proto);
  card.entity = (id) => entities[id] ?? null;
  card.hass = { states: entities };
  return card;
}

/* ============================================================
   [RE-*] ruleEntityDescriptor — category & operator derivation
   ============================================================ */

test("[RE-1] boolean domains (binary_sensor/switch/input_boolean) -> boolean category + BOOLEAN_OPERATORS", () => {
  const card = makeCard({
    "binary_sensor.door": { state: "off", attributes: {} },
    "switch.fan": { state: "on", attributes: {} },
    "input_boolean.away": { state: "off", attributes: {} },
  });
  for (const id of ["binary_sensor.door", "switch.fan", "input_boolean.away"]) {
    const d = card.ruleEntityDescriptor(id);
    assert.equal(d.category, "boolean");
    assert.deepEqual(d.operators, ["is_on", "is_off", "exists", "missing"]);
    // boolean value-mode is always "none" for a value-bearing operator
    assert.equal(d.valueModeForOperator("is_on"), "none");
    assert.equal(d.valueModeForOperator("exists"), "none");
  }
});

test("[RE-2] select/input_select -> enum; enum valueMode is single-select except in/not_in", () => {
  const card = makeCard({
    "select.mode": { state: "eco", attributes: { options: ["eco", "turbo", "max"] } },
  });
  const d = card.ruleEntityDescriptor("select.mode");
  assert.equal(d.category, "enum");
  assert.deepEqual(d.operators, ["equals", "not_equals", "in", "not_in", "exists", "missing"]);
  // options mapped to {value,label}
  assert.deepEqual(d.options, [
    { value: "eco", label: "eco" },
    { value: "turbo", label: "turbo" },
    { value: "max", label: "max" },
  ]);
  assert.equal(d.valueModeForOperator("equals"), "single-select");
  assert.equal(d.valueModeForOperator("in"), "multi-select");
  assert.equal(d.valueModeForOperator("not_in"), "multi-select");
  assert.equal(d.valueModeForOperator("exists"), "none");
});

test("[RE-3] a non-select entity that merely carries an options[] attr is still enum", () => {
  // The `|| options.length` branch: options on any domain force enum.
  const card = makeCard({
    "sensor.picker": { state: "a", attributes: { options: ["a", "b"] } },
  });
  const d = card.ruleEntityDescriptor("sensor.picker");
  assert.equal(d.category, "enum");
});

test("[RE-4] number/input_number -> numeric; numeric valueMode is number; min/max/step parsed", () => {
  const card = makeCard({
    "number.target": {
      state: "21",
      attributes: { min: "5", max: 30, step: "0.5", unit_of_measurement: "°C" },
    },
  });
  const d = card.ruleEntityDescriptor("number.target");
  assert.equal(d.category, "numeric");
  assert.deepEqual(d.operators, ["equals", "not_equals", "gt", "gte", "lt", "lte", "exists", "missing"]);
  assert.equal(d.valueModeForOperator("gt"), "number");
  assert.equal(d.min, 5);
  assert.equal(d.max, 30);
  assert.equal(d.step, 0.5);
  assert.equal(d.unit, "°C");
});

test("[RE-5] sensor category splits on state: finite-numeric -> numeric, else text", () => {
  const numeric = makeCard({ "sensor.temp": { state: "22.5", attributes: {} } });
  assert.equal(numeric.ruleEntityDescriptor("sensor.temp").category, "numeric");
  const textual = makeCard({ "sensor.weather": { state: "sunny", attributes: {} } });
  const t = textual.ruleEntityDescriptor("sensor.weather");
  assert.equal(t.category, "text");
  assert.deepEqual(t.operators, ["equals", "not_equals", "in", "not_in", "exists", "missing"]);
  assert.equal(t.valueModeForOperator("equals"), "text");
});

test("[RE-6] unknown domain with on/off state -> boolean (state-based fallback)", () => {
  // e.g. a light: not in any explicit list, but state is on/off -> boolean.
  const card = makeCard({ "light.lamp": { state: "ON", attributes: {} } });
  const d = card.ruleEntityDescriptor("light.lamp");
  assert.equal(d.category, "boolean");
});

test("[RE-7] unknown domain with an arbitrary state -> text (has-id fallback)", () => {
  const card = makeCard({ "device_tracker.phone": { state: "home", attributes: {} } });
  const d = card.ruleEntityDescriptor("device_tracker.phone");
  assert.equal(d.category, "text");
});

test("[RE-8] empty / missing entity -> unknown category, ALL_OPERATORS, entityExists false", () => {
  const card = makeCard({});
  const empty = card.ruleEntityDescriptor("");
  assert.equal(empty.category, "unknown");
  assert.equal(empty.entityExists, false);
  assert.deepEqual(empty.operators, [
    "is_on", "is_off", "exists", "missing",
    "equals", "not_equals", "gt", "gte", "lt", "lte", "in", "not_in",
  ]);
  // unknown category -> value-bearing operator falls to "text"
  assert.equal(empty.valueModeForOperator("equals"), "text");

  // A domain-shaped id that isn't in hass: exists=false, but domain still classifies it.
  const missing = card.ruleEntityDescriptor("switch.nope");
  assert.equal(missing.entityExists, false);
  assert.equal(missing.category, "boolean"); // domain drives category even when absent
});

test("[RE-9] descriptor accepts a draft object or falls back to _roomRulesDraft.entity_id", () => {
  const card = makeCard({ "switch.a": { state: "on", attributes: {} } });
  // object form
  assert.equal(card.ruleEntityDescriptor({ entity_id: "switch.a" }).entityExists, true);
  // null arg -> reads this._roomRulesDraft.entity_id
  card._roomRulesDraft = { entity_id: "switch.a" };
  assert.equal(card.ruleEntityDescriptor(null).entityExists, true);
});

test("[RE-10] entityLabel prefers friendly_name, currentState mirrors state", () => {
  const card = makeCard({
    "sensor.temp": { state: "19", attributes: { friendly_name: "Living Room Temp" } },
  });
  const d = card.ruleEntityDescriptor("sensor.temp");
  assert.equal(d.entityLabel, "Living Room Temp");
  assert.equal(d.currentState, "19");
});

/* ============================================================
   [RV-*] roomRulesDraftIsValid
   ============================================================ */

test("[RV-1] null draft or blank entity_id -> invalid", () => {
  const card = makeCard({});
  assert.equal(card.roomRulesDraftIsValid(), false); // no draft
  card._roomRulesDraft = { entity_id: "   ", operator: "is_on" };
  assert.equal(card.roomRulesDraftIsValid(), false); // whitespace entity
});

test("[RV-2] entity must exist and operator must be allowed for its category", () => {
  const card = makeCard({ "switch.fan": { state: "on", attributes: {} } });
  // entity doesn't exist
  card._roomRulesDraft = { entity_id: "switch.ghost", operator: "is_on", kind: "blocker" };
  assert.equal(card.roomRulesDraftIsValid(), false);
  // exists but operator not in BOOLEAN_OPERATORS (gt is numeric-only)
  card._roomRulesDraft = { entity_id: "switch.fan", operator: "gt", kind: "blocker" };
  assert.equal(card.roomRulesDraftIsValid(), false);
  // exists + allowed no-value operator -> valid
  card._roomRulesDraft = { entity_id: "switch.fan", operator: "is_on", kind: "blocker" };
  assert.equal(card.roomRulesDraftIsValid(), true);
});

test("[RV-3] number value-mode requires a finite numeric value", () => {
  const card = makeCard({ "number.target": { state: "20", attributes: {} } });
  const base = { entity_id: "number.target", kind: "blocker", operator: "gt" };
  card._roomRulesDraft = { ...base, value: "" };
  assert.equal(card.roomRulesDraftIsValid(), false);
  card._roomRulesDraft = { ...base, value: "abc" };
  assert.equal(card.roomRulesDraftIsValid(), false);
  card._roomRulesDraft = { ...base, value: "25" };
  assert.equal(card.roomRulesDraftIsValid(), true);
  card._roomRulesDraft = { ...base, value: 0 }; // 0 is finite -> valid
  assert.equal(card.roomRulesDraftIsValid(), true);
});

test("[RV-4] multi-select value-mode requires a non-empty list", () => {
  const card = makeCard({ "select.mode": { state: "eco", attributes: { options: ["eco", "max"] } } });
  const base = { entity_id: "select.mode", kind: "blocker", operator: "in" };
  card._roomRulesDraft = { ...base, value: [] };
  assert.equal(card.roomRulesDraftIsValid(), false);
  card._roomRulesDraft = { ...base, value: "  ,  " }; // normalizes to []
  assert.equal(card.roomRulesDraftIsValid(), false);
  card._roomRulesDraft = { ...base, value: ["eco"] };
  assert.equal(card.roomRulesDraftIsValid(), true);
  card._roomRulesDraft = { ...base, value: "eco, max" }; // csv -> non-empty
  assert.equal(card.roomRulesDraftIsValid(), true);
});

test("[RV-5] text value-mode (single-select on enum equals) requires a trimmed non-empty string", () => {
  const card = makeCard({ "select.mode": { state: "eco", attributes: { options: ["eco"] } } });
  const base = { entity_id: "select.mode", kind: "blocker", operator: "equals" };
  card._roomRulesDraft = { ...base, value: "   " };
  assert.equal(card.roomRulesDraftIsValid(), false);
  card._roomRulesDraft = { ...base, value: null };
  assert.equal(card.roomRulesDraftIsValid(), false);
  card._roomRulesDraft = { ...base, value: "eco" };
  assert.equal(card.roomRulesDraftIsValid(), true);
});

test("[RV-6] no-value operators skip the value check entirely", () => {
  const card = makeCard({ "sensor.temp": { state: "19", attributes: {} } });
  // exists is allowed for numeric sensor, needs no value even though value is null
  card._roomRulesDraft = { entity_id: "sensor.temp", kind: "blocker", operator: "exists", value: null };
  assert.equal(card.roomRulesDraftIsValid(), true);
});

test("[RV-7] modifier kind requires >=1 meaningful change", () => {
  const card = makeCard({ "switch.fan": { state: "on", attributes: {} } });
  const base = { entity_id: "switch.fan", operator: "is_on", kind: "modifier" };
  // no changes -> invalid
  card._roomRulesDraft = { ...base, effect: { changes: {} } };
  assert.equal(card.roomRulesDraftIsValid(), false);
  // null-valued change is not meaningful -> invalid
  card._roomRulesDraft = { ...base, effect: { changes: { fan_speed: null } } };
  assert.equal(card.roomRulesDraftIsValid(), false);
  // a real change -> valid
  card._roomRulesDraft = { ...base, effect: { changes: { fan_speed: "max" } } };
  assert.equal(card.roomRulesDraftIsValid(), true);
});

test("[RV-8] clean_passes meaningful-change gate: only 1 or 2 count", () => {
  const card = makeCard({ "switch.fan": { state: "on", attributes: {} } });
  const base = { entity_id: "switch.fan", operator: "is_on", kind: "modifier" };
  // clean_passes = 3 is NOT a meaningful change (and it's the only change) -> invalid
  card._roomRulesDraft = { ...base, effect: { changes: { clean_passes: 3 } } };
  assert.equal(card.roomRulesDraftIsValid(), false);
  // clean_passes = 0 -> invalid
  card._roomRulesDraft = { ...base, effect: { changes: { clean_passes: 0 } } };
  assert.equal(card.roomRulesDraftIsValid(), false);
  // clean_passes = 1 -> valid (string "1" also coerces via Number)
  card._roomRulesDraft = { ...base, effect: { changes: { clean_passes: 1 } } };
  assert.equal(card.roomRulesDraftIsValid(), true);
  card._roomRulesDraft = { ...base, effect: { changes: { clean_passes: "2" } } };
  assert.equal(card.roomRulesDraftIsValid(), true);
  // a non-meaningful clean_passes ALONGSIDE a real change -> still valid (other change carries it)
  card._roomRulesDraft = { ...base, effect: { changes: { clean_passes: 3, fan_speed: "max" } } };
  assert.equal(card.roomRulesDraftIsValid(), true);
});

/* ============================================================
   [RS-*] ruleEntitySearchResults — scoring tiers & ordering
   ============================================================ */

test("[RS-1] min-2-char gate: 0 or 1 char query returns []", () => {
  const card = makeCard({ "switch.fan": { state: "on", attributes: { friendly_name: "Fan" } } });
  assert.deepEqual(card.ruleEntitySearchResults("s"), []);
  assert.deepEqual(card.ruleEntitySearchResults(""), []);
  assert.deepEqual(card.ruleEntitySearchResults(null), []); // and no draft to fall back on
});

test("[RS-2] scoring tiers: exact-id 100 > exact-name 95 > id-prefix 80 > name-prefix 70 > id-substr 50 > name-substr 40", () => {
  // One matching entity per tier; query chosen so each entity lands in exactly one tier.
  const card = makeCard({
    "switch.kitchen": { state: "on", attributes: { friendly_name: "zzzzz A" } }, // id === query -> 100
    "switch.other1": { state: "on", attributes: { friendly_name: "kitchen" } },  // name === query -> 95
    "switch.kitchenette": { state: "on", attributes: { friendly_name: "zzzzz B" } }, // id startsWith -> 80
    "sensor.q4": { state: "on", attributes: { friendly_name: "kitchen light" } }, // name startsWith -> 70
    "switch.mainkitchenpump": { state: "on", attributes: { friendly_name: "zzzzz C" } }, // id includes -> 50
    "sensor.q6": { state: "on", attributes: { friendly_name: "the kitchen sink" } }, // name includes -> 40
  });
  const res = card.ruleEntitySearchResults("switch.kitchen", 12);
  // The exact-id entity scores 100 and must be first.
  assert.equal(res[0].entity_id, "switch.kitchen");
  assert.equal(res[0].score, 100);
});

test("[RS-3] tier ordering across all six scoring tiers with one query", () => {
  // Note: id-prefix (80) needs the query to prefix the WHOLE entity_id incl. domain,
  // so the id-prefix entity here is "kitchen.pantry" (domain literally "kitchen").
  const card = makeCard({
    "kitchen": { state: "on", attributes: { friendly_name: "zzzzz" } },              // id exact -> 100
    "switch.a": { state: "on", attributes: { friendly_name: "kitchen" } },           // name exact -> 95
    "kitchen.pantry": { state: "on", attributes: { friendly_name: "zzzzz" } },        // id prefix -> 80
    "sensor.temp": { state: "on", attributes: { friendly_name: "kitchen temp" } },   // name prefix -> 70
    "light.mainkitchenlamp": { state: "on", attributes: { friendly_name: "Hall" } }, // id substr -> 50
    "sensor.humidity": { state: "on", attributes: { friendly_name: "the kitchen air" } }, // name substr -> 40
  });
  const res = card.ruleEntitySearchResults("kitchen", 12);
  assert.deepEqual(res.map((r) => r.entity_id), [
    "kitchen",                // 100 id-exact
    "switch.a",               //  95 name-exact
    "kitchen.pantry",         //  80 id-prefix
    "sensor.temp",            //  70 name-prefix
    "light.mainkitchenlamp",  //  50 id-substr
    "sensor.humidity",        //  40 name-substr
  ]);
  assert.deepEqual(res.map((r) => r.score), [100, 95, 80, 70, 50, 40]);
});

test("[RS-4] score tie broken by entity_id localeCompare (ascending)", () => {
  const card = makeCard({
    "switch.zebra": { state: "on", attributes: { friendly_name: "kitchen" } }, // name exact -> 95
    "switch.alpha": { state: "on", attributes: { friendly_name: "kitchen" } }, // name exact -> 95
  });
  const res = card.ruleEntitySearchResults("kitchen", 12);
  assert.equal(res.length, 2);
  assert.equal(res[0].score, 95);
  assert.equal(res[1].score, 95);
  // tie -> alpha before zebra
  assert.deepEqual(res.map((r) => r.entity_id), ["switch.alpha", "switch.zebra"]);
});

test("[RS-5] non-matching entities dropped; limit clamps result count (>=1)", () => {
  const card = makeCard({
    "switch.kitchen1": { state: "on", attributes: { friendly_name: "" } },
    "switch.kitchen2": { state: "on", attributes: { friendly_name: "" } },
    "switch.kitchen3": { state: "on", attributes: { friendly_name: "" } },
    "light.bedroom": { state: "on", attributes: { friendly_name: "Bedroom" } }, // no "kitchen" -> dropped
  });
  const two = card.ruleEntitySearchResults("kitchen", 2);
  assert.equal(two.length, 2);
  assert.ok(two.every((r) => r.entity_id.includes("kitchen")));
  // limit clamp is Math.max(1, Number(limit) || 12): 0 is falsy -> default 12 -> all 3 kept.
  assert.equal(card.ruleEntitySearchResults("kitchen", 0).length, 3);
  // a negative limit is truthy -> Number(-5)||12 = -5 -> Math.max(1,-5) = 1.
  assert.equal(card.ruleEntitySearchResults("kitchen", -5).length, 1);
  // a non-numeric limit -> NaN is falsy -> default 12 -> all 3.
  assert.equal(card.ruleEntitySearchResults("kitchen", "abc").length, 3);
});

test("[RS-6] query falls back to the draft entity_id when arg omitted", () => {
  const card = makeCard({ "switch.kitchen": { state: "on", attributes: {} } });
  card._roomRulesDraft = { entity_id: "switch.kitchen" };
  const res = card.ruleEntitySearchResults(); // no arg -> uses draft
  assert.equal(res.length, 1);
  assert.equal(res[0].entity_id, "switch.kitchen");
  assert.equal(res[0].score, 100); // exact-id
  assert.equal(res[0].domain, "switch");
});

/* ============================================================
   [OG-*] ruleOperatorGroups — filter the 5 fixed groups
   ============================================================ */

test("[OG-1] boolean entity keeps only State + Existence groups", () => {
  const card = makeCard({ "switch.fan": { state: "on", attributes: {} } });
  const groups = card.ruleOperatorGroups("switch.fan");
  assert.deepEqual(groups.map((g) => g.label), ["State", "Existence"]);
  assert.deepEqual(groups[0].operators.map((o) => o.value), ["is_on", "is_off"]);
  assert.deepEqual(groups[1].operators.map((o) => o.value), ["exists", "missing"]);
});

test("[OG-2] numeric entity keeps Existence + Equality + Numeric, drops State + List", () => {
  const card = makeCard({ "number.target": { state: "20", attributes: {} } });
  const groups = card.ruleOperatorGroups("number.target");
  assert.deepEqual(groups.map((g) => g.label), ["Existence", "Equality", "Numeric"]);
  assert.deepEqual(
    groups.find((g) => g.label === "Numeric").operators.map((o) => o.value),
    ["gt", "gte", "lt", "lte"],
  );
});

test("[OG-3] enum entity keeps Existence + Equality + List, drops State + Numeric", () => {
  const card = makeCard({ "select.mode": { state: "eco", attributes: { options: ["eco"] } } });
  const groups = card.ruleOperatorGroups("select.mode");
  assert.deepEqual(groups.map((g) => g.label), ["Existence", "Equality", "List"]);
  assert.deepEqual(
    groups.find((g) => g.label === "List").operators.map((o) => o.value),
    ["in", "not_in"],
  );
});

test("[OG-4] unknown entity (ALL_OPERATORS) keeps all 5 groups; empty groups never appear", () => {
  const card = makeCard({});
  const groups = card.ruleOperatorGroups(""); // unknown -> ALL_OPERATORS
  assert.deepEqual(groups.map((g) => g.label), ["State", "Existence", "Equality", "Numeric", "List"]);
  // every surviving group has at least one operator
  assert.ok(groups.every((g) => g.operators.length > 0));
});
