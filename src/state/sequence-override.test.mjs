// Sequence-override row derivation — five states + the "unverifiable" third
// verification signal that stops an infra failure from locking Start.
//
// Run: node --test src/state/sequence-override.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { deriveSequenceRowState, findCleanOrderSensor } from "./sequence-override.js";

const _sensor = (order, order_names, state = String(order.length), status = "ok") => ({
  state,
  attributes: { order, order_names, status },
});
const _switch = (on) => ({ state: on ? "on" : "off" });
const _room = (id, name, on = true) => ({ room_id: id, name, on });

test("[SEQ-1] no switch entity -> absent (renders nothing)", () => {
  const s = deriveSequenceRowState({
    switchState: null,
    sensorState: _sensor([1, 2], ["Kitchen", "Study"]),
    queueRooms: [_room(1, "Kitchen")],
  });
  assert.equal(s.kind, "absent");
});

test("[SEQ-2] switch off + empty device order -> path_optimizing", () => {
  const s = deriveSequenceRowState({
    switchState: _switch(false),
    sensorState: _sensor([], []),
    queueRooms: [_room(1, "Kitchen"), _room(2, "Study")],
  });
  assert.equal(s.kind, "path_optimizing");
  assert.equal(s.overrideOn, false);
});

test("[SEQ-3] switch off + saved order -> saved (name-annotated)", () => {
  const s = deriveSequenceRowState({
    switchState: _switch(false),
    sensorState: _sensor([27, 25, 23], ["Kitchen", "Hallway", "Study"]),
    queueRooms: [_room(1, "R1")],
  });
  assert.equal(s.kind, "saved");
  assert.deepEqual(s.deviceOrder, [27, 25, 23]);
  assert.deepEqual(s.deviceNames, ["Kitchen", "Hallway", "Study"]);
});

test("[SEQ-4] switch on + orders match -> matching (green)", () => {
  const s = deriveSequenceRowState({
    switchState: _switch(true),
    sensorState: _sensor([27, 25], ["Kitchen", "Study"]),
    queueRooms: [_room(27, "Kitchen"), _room(25, "Study")],
  });
  assert.equal(s.kind, "matching");
});

test("[SEQ-5] switch on + orders differ -> mismatch (amber, needs Apply)", () => {
  // A common shape: user reordered rooms on the card but has not applied yet.
  const s = deriveSequenceRowState({
    switchState: _switch(true),
    sensorState: _sensor([27, 25], ["Kitchen", "Study"]),
    queueRooms: [_room(25, "Study"), _room(27, "Kitchen")],
  });
  assert.equal(s.kind, "mismatch");
  assert.deepEqual(s.deviceOrder, [27, 25]);
  assert.deepEqual(s.queueOrder, [25, 27]);
});

test("[SEQ-5b] switch on + different LENGTHS -> mismatch (not just element compare)", () => {
  // The subset case worth pinning: without a length check, a queue prefix that
  // matches the device would read as "matching" even though the device is
  // missing the tail. Same defect the on-device sequence writer already guards
  // against (a saved sequence only ORDERS, never restricts membership — but if
  // we compare naively we could still LIE about it here).
  const s = deriveSequenceRowState({
    switchState: _switch(true),
    sensorState: _sensor([27, 25], ["Kitchen", "Study"]),
    queueRooms: [_room(27, "Kitchen"), _room(25, "Study"), _room(23, "Extra")],
  });
  assert.equal(s.kind, "mismatch");
});

test("[SEQ-6] sensor unavailable -> unverifiable (grey, Start stays unlocked)", () => {
  // The third verification state, load-bearing per the finding: an infra failure
  // must never lock Start. Falls back to post-hoc order comparison.
  for (const rawState of ["unknown", "unavailable"]) {
    const s = deriveSequenceRowState({
      switchState: _switch(true),
      sensorState: { state: rawState, attributes: { status: "unavailable" } },
      queueRooms: [_room(27, "Kitchen")],
    });
    assert.equal(s.kind, "unverifiable", `expected unverifiable for state=${rawState}`);
  }
});

test("[SEQ-6b] sensor never_read -> unverifiable (distinct from empty order)", () => {
  // never_read means "we have not read the device yet" — different fact from
  // "the device has no order saved". Collapsing them would show
  // 'path_optimizing' the first time a user opens the card, which is dishonest.
  const s = deriveSequenceRowState({
    switchState: _switch(false),
    sensorState: { state: "unknown", attributes: { status: "never_read", order: [] } },
    queueRooms: [_room(27, "Kitchen")],
  });
  assert.equal(s.kind, "unverifiable");
});

test("[SEQ-7] queue rooms filtered to those actually turned on (off rooms are not queued)", () => {
  // A room the user toggled off should not appear in the comparison — its id is
  // in `queueRooms` but with on:false. Otherwise a disabled room would flip a
  // matching sequence into a spurious mismatch.
  const s = deriveSequenceRowState({
    switchState: _switch(true),
    sensorState: _sensor([27, 25], ["Kitchen", "Study"]),
    queueRooms: [_room(27, "Kitchen"), _room(25, "Study"), _room(23, "Off", false)],
  });
  assert.equal(s.kind, "matching",
    `off rooms leaked into the queue comparison: got ${s.kind}`);
});

test("[SEQ-8] a non-numeric room_id drops its NAME with it — ids and names stay aligned", () => {
  // The bite for the round-2 adversary finding. The first cut filtered
  // Number.isFinite on the id array ONLY, so a single unparseable room_id
  // shifted every later name up by one: the mismatch row then confidently
  // named the wrong rooms. Ids and names are rendered index-by-index, so they
  // must be filtered as pairs.
  const s = deriveSequenceRowState({
    switchState: _switch(true),
    sensorState: _sensor([27, 25], ["Kitchen", "Study"]),
    queueRooms: [
      _room(27, "Kitchen"),
      _room("not-a-number", "Ghost"),   // survives the on-filter, fails isFinite
      _room(25, "Study"),
    ],
  });
  assert.deepEqual(s.queueOrder, [27, 25], "the unparseable id must be dropped");
  assert.deepEqual(s.queueNames, ["Kitchen", "Study"],
    "'Ghost' must be dropped WITH its id — if this reads ['Kitchen','Ghost'] the arrays have desynced");
  assert.equal(s.queueOrder.length, s.queueNames.length,
    "order and names must always be the same length");
  // And with the arrays aligned, the comparison itself is correct.
  assert.equal(s.kind, "matching");
});

test("[SEQ-8b] the same pairing rule holds for the DEVICE side", () => {
  // sensor attributes `order` and `order_names` are parallel arrays from the
  // backend; a bad element in `order` must not shift `order_names`.
  const s = deriveSequenceRowState({
    switchState: _switch(false),
    sensorState: _sensor([27, "junk", 23], ["Kitchen", "Ghost", "Study"]),
    queueRooms: [_room(27, "Kitchen")],
  });
  assert.deepEqual(s.deviceOrder, [27, 23]);
  assert.deepEqual(s.deviceNames, ["Kitchen", "Study"],
    "'Ghost' must be dropped with its id, leaving 23 still labelled 'Study'");
});

test("[SEQ-8c] a name missing from order_names falls back to the id, not to the NEXT name", () => {
  // order_names shorter than order: index 2 has no name. It must fall back to
  // its own id — reading ahead into the array is the desync in another dress.
  const s = deriveSequenceRowState({
    switchState: _switch(false),
    sensorState: _sensor([27, 25, 23], ["Kitchen", "Hallway"]),
    queueRooms: [_room(27, "Kitchen")],
  });
  assert.deepEqual(s.deviceOrder, [27, 25, 23]);
  assert.deepEqual(s.deviceNames, ["Kitchen", "Hallway", "23"]);
});

/* =========================================================
   THE DEADLOCK — canApply on an unverified device
   ========================================================= */

test("[SEQ-9] unverifiable OFFERS Apply when the override is on — the deadlock bite", () => {
  // Found by Chris on the live card, not by any test: the sensor starts
  // `never_read`, never_read forces `unverifiable`, and until 2026-08-24 that
  // state rendered no Apply. Apply is the ONLY writer, so nothing could ever
  // populate the cache — no read -> grey -> no Apply -> no write -> no ack ->
  // no read. The feature was inert on every install.
  const s = deriveSequenceRowState({
    switchState: _switch(true),
    sensorState: { state: "unknown", attributes: { status: "never_read", order: [] } },
    queueRooms: [_room(27, "Kitchen"), _room(25, "Study")],
  });
  assert.equal(s.kind, "unverifiable");
  assert.equal(s.canApply, true,
    "grey means we do not know the device order — it must not mean the user may not act");
});

test("[SEQ-9b] unverifiable with the override OFF offers nothing — the switch is still the gate", () => {
  // The write refuses with `override_off` server-side, so offering Apply here
  // would render a button whose only outcome is a refusal.
  const s = deriveSequenceRowState({
    switchState: _switch(false),
    sensorState: { state: "unavailable", attributes: { status: "unavailable" } },
    queueRooms: [_room(27, "Kitchen")],
  });
  assert.equal(s.kind, "unverifiable");
  assert.equal(s.canApply, false);
});

test("[SEQ-9c] canApply is explicit on every branch — never undefined", () => {
  // An undefined canApply is falsy, so a missed branch silently hides Apply
  // rather than failing loudly. Pin all six.
  const cases = [
    ["absent",          { switchState: null, sensorState: _sensor([], []), queueRooms: [] }],
    ["path_optimizing", { switchState: _switch(false), sensorState: _sensor([], []), queueRooms: [_room(1, "A")] }],
    ["saved",           { switchState: _switch(false), sensorState: _sensor([27], ["Kitchen"]), queueRooms: [_room(1, "A")] }],
    ["matching",        { switchState: _switch(true), sensorState: _sensor([27], ["Kitchen"]), queueRooms: [_room(27, "Kitchen")] }],
    ["mismatch",        { switchState: _switch(true), sensorState: _sensor([25], ["Study"]), queueRooms: [_room(27, "Kitchen")] }],
  ];
  for (const [expected, input] of cases) {
    const s = deriveSequenceRowState(input);
    assert.equal(s.kind, expected, `expected ${expected}, got ${s.kind}`);
    assert.equal(typeof s.canApply, "boolean",
      `${expected}: canApply must be an explicit boolean, got ${typeof s.canApply}`);
  }
  // And only the two states that can actually write say true.
  assert.equal(deriveSequenceRowState(cases[4][1]).canApply, true, "mismatch can apply");
  assert.equal(deriveSequenceRowState(cases[3][1]).canApply, false, "matching needs no apply");
});

/* ---------------------------------------------------------------------------
 * [SEQ-10] the SENSOR is found when its entity_id is not the conventional one
 * ------------------------------------------------------------------------- */

test("[SEQ-10] findCleanOrderSensor resolves the conventional id first", () => {
  const hass = { states: { "sensor.ivy_clean_order": { entity_id: "sensor.ivy_clean_order", state: "3", attributes: {} } } };
  assert.equal(findCleanOrderSensor(hass, "vacuum.ivy")?.entity_id, "sensor.ivy_clean_order");
});

test("[SEQ-10b] RED IF THE LOCALIZED SENSOR IS UNREACHABLE", () => {
  // A German install: the sensor's name is translated, so HA composed the
  // entity_id from "Reinigungsreihenfolge" and the conventional guess misses.
  // Both surfaces built that id with NO fallback until 2026-08-24, so on the eight
  // packs that localize this name the row sat permanently grey while everything
  // underneath worked. The switch beside it had carried this fallback for days.
  const hass = {
    states: {
      "sensor.ivy_reinigungsreihenfolge": {
        entity_id: "sensor.ivy_reinigungsreihenfolge",
        state: "3",
        attributes: { vacuum_entity_id: "vacuum.ivy", role: "clean_order", status: "ok", order: [1, 2, 3] },
      },
    },
  };
  const found = findCleanOrderSensor(hass, "vacuum.ivy");
  assert.equal(found?.entity_id, "sensor.ivy_reinigungsreihenfolge");
});

test("[SEQ-10c] the scan does not claim another vacuum's sensor", () => {
  const hass = {
    states: {
      "sensor.alfred_reinigungsreihenfolge": {
        entity_id: "sensor.alfred_reinigungsreihenfolge",
        state: "2",
        attributes: { vacuum_entity_id: "vacuum.alfred", role: "clean_order" },
      },
    },
  };
  assert.equal(findCleanOrderSensor(hass, "vacuum.ivy"), null);
});

test("[SEQ-10d] a sensor without the role slug is not claimed", () => {
  // `vacuum_entity_id` alone cannot identify it — every per-room sensor carries one.
  const hass = {
    states: {
      "sensor.ivy_kitchen_cleaning_history": {
        entity_id: "sensor.ivy_kitchen_cleaning_history",
        state: "x",
        attributes: { vacuum_entity_id: "vacuum.ivy" },
      },
    },
  };
  assert.equal(findCleanOrderSensor(hass, "vacuum.ivy"), null);
});
