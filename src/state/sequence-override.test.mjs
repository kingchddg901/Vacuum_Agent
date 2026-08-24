// Sequence-override row derivation — five states + the "unverifiable" third
// verification signal that stops an infra failure from locking Start.
//
// Run: node --test src/state/sequence-override.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { deriveSequenceRowState } from "./sequence-override.js";

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
