// Unit tests for the pure step-mutation helpers in src/state/steps-order.js — the immutable
// derive-next-array primitives the run-profile STEPS editor rides on. They own no card state and
// REPLICA RN4T4MPV -- see profiles/manager.py::normalize_run_profile_steps.
// never touch a room_group's internals (mode-agnostic). Mirrors the backend normalize for save.
// Run: node --test src/state/steps-order.test.mjs
//
// Coverage (src/state/steps-order.js):
//   [STP-clamp]  clampChargeTarget — round, [1,100] clamp, non-finite -> fallback
//   [STP-move]   moveStep — reorder, index clamp, empty, refuses a ZONE at 0 (C40)
//   [STP-ins]    insertChargeStep — insert at index, refuses leading/trailing (CARD-6 clause 1), clamped target
//   [STP-rm]     removeStep — remove, out-of-range no-op, empty
//   [STP-tgt]    setChargeTarget — update charge target, room_group no-op, clamp
//   [STP-has]    stepsHaveRoomGroup / stepsHaveChargeStep
//   [STP-san]    sanitizeStepsForSave — drop empty room_group, drop junk, clamp, strip extras
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  clampChargeTarget,
  moveStep,
  isUnsupportedBreakPosition,
  insertChargeStep,
  removeStep,
  setChargeTarget,
  stepsHaveRoomGroup,
  stepsHaveChargeStep,
  sanitizeStepsForSave,
  roomsToGroupStep,
  clampWaitMinutes,
  insertWaitStep,
  setWaitMinutes,
} from "./steps-order.js";

const rg = (...ids) => ({ type: "room_group", rooms: ids.map((room_id) => ({ room_id })) });
const cw = (t) => ({ type: "charge_wait", target_battery_percent: t });
const types = (arr) => arr.map((s) => s.type);

/* ============================ clampChargeTarget ============================ */

test("[STP-clamp-1] rounds and clamps into [1,100]", () => {
  assert.equal(clampChargeTarget(95), 95);
  assert.equal(clampChargeTarget(95.4), 95);
  assert.equal(clampChargeTarget(0), 1);
  assert.equal(clampChargeTarget(-20), 1);
  assert.equal(clampChargeTarget(150), 100);
});

test("[STP-clamp-2] non-finite falls back (default 95, or supplied)", () => {
  assert.equal(clampChargeTarget("abc"), 95);
  assert.equal(clampChargeTarget(undefined), 95);
  assert.equal(clampChargeTarget(null, 80), 80);
});

/* ============================ moveStep ============================ */

test("[STP-move-1] moves a step to a new position, immutably", () => {
  const steps = [rg(1), cw(95), rg(2)];
  const next = moveStep(steps, 1, 0);
  assert.deepEqual(types(next), ["charge_wait", "room_group", "room_group"]);
  assert.deepEqual(types(steps), ["room_group", "charge_wait", "room_group"]); // original intact
});

test("[STP-move-2] clamps out-of-range indices", () => {
  const steps = [rg(1), rg(2), cw(95)];
  assert.deepEqual(types(moveStep(steps, 0, 99)), ["room_group", "charge_wait", "room_group"]);
  assert.deepEqual(types(moveStep(steps, -5, 0)), ["room_group", "room_group", "charge_wait"]);
});

test("[STP-move-3] empty array is a no-op", () => {
  assert.deepEqual(moveStep([], 0, 1), []);
});

/* ============================ insertChargeStep ============================ */

test("[STP-ins-1] inserts a charge step at the given index", () => {
  const next = insertChargeStep([rg(1), rg(2)], 1);
  assert.deepEqual(types(next), ["room_group", "charge_wait", "room_group"]);
  assert.equal(next[1].target_battery_percent, 95); // default
});

// CARD-6 clause (1): a trailing break has nothing to bracket and would be silently
// skipped, never run -- refused as a no-op (mirrors LB-1's leading case).
test("[STP-ins-2] refuses insert at end when index >= length (trailing break unsupported)", () => {
  const before = [rg(1)];
  const next = insertChargeStep(before, 9, 250);
  assert.deepEqual(types(next), ["room_group"]);
  assert.deepEqual(next, before);
});

/* ============================ removeStep ============================ */

test("[STP-rm-1] removes the step at index", () => {
  assert.deepEqual(types(removeStep([rg(1), cw(95), rg(2)], 1)), ["room_group", "room_group"]);
});

test("[STP-rm-2] out-of-range / empty are safe", () => {
  assert.deepEqual(types(removeStep([rg(1)], 9)), []); // clamps to last -> removes rg(1)
  assert.deepEqual(removeStep([], 0), []);
});

/* ============================ setChargeTarget ============================ */

test("[STP-tgt-1] updates a charge step's target (clamped)", () => {
  const next = setChargeTarget([rg(1), cw(95)], 1, 80);
  assert.equal(next[1].target_battery_percent, 80);
  const clamped = setChargeTarget([cw(95)], 0, 999);
  assert.equal(clamped[0].target_battery_percent, 100);
});

test("[STP-tgt-2] no-op on a room_group step", () => {
  const steps = [rg(1), cw(95)];
  const next = setChargeTarget(steps, 0, 50);
  assert.deepEqual(next[0], rg(1)); // unchanged
});

/* ============================ has-* ============================ */

test("[STP-has-1] stepsHaveRoomGroup / stepsHaveChargeStep", () => {
  assert.equal(stepsHaveRoomGroup([cw(95)]), false);
  assert.equal(stepsHaveRoomGroup([rg(1), cw(95)]), true);
  assert.equal(stepsHaveChargeStep([rg(1)]), false);
  assert.equal(stepsHaveChargeStep([rg(1), cw(95)]), true);
});

/* ============================ sanitizeStepsForSave ============================ */

test("[STP-san-1] drops empty room_groups and non-step junk", () => {
  // Trailing rg(2) keeps the charge_wait mid-sequence so this stays a pure junk-drop
  // test -- a trailing break is refused separately (CARD-6 clause 1, see STP-ins-2).
  const dirty = [rg(1), { type: "room_group", rooms: [] }, cw(95), { type: "bogus" }, 42, null, rg(2)];
  assert.deepEqual(types(sanitizeStepsForSave(dirty)), ["room_group", "charge_wait", "room_group"]);
});

test("[STP-san-2] clamps charge targets and strips client-only fields", () => {
  // Trailing room_group keeps the charge_wait mid-sequence -- see STP-san-1 comment.
  const dirty = [
    { type: "room_group", rooms: [{ room_id: 1 }], _uid: "x", extra: 1 },
    { type: "charge_wait", target_battery_percent: 250, _uid: "y" },
    { type: "room_group", rooms: [{ room_id: 2 }] },
  ];
  const clean = sanitizeStepsForSave(dirty);
  assert.deepEqual(clean[0], { type: "room_group", rooms: [{ room_id: 1 }] });
  assert.deepEqual(clean[1], { type: "charge_wait", target_battery_percent: 100 });
  assert.deepEqual(clean[2], { type: "room_group", rooms: [{ room_id: 2 }] });
});

/* ============================ roomsToGroupStep ============================ */

test("[STP-grp-1] snapshots enabled rooms into a snake_case room_group", () => {
  const rooms = [
    { id: 1, enabled: true, cleanMode: "vacuum", fanSpeed: "max", cleanPasses: 2, edgeMopping: false },
    { id: 2, enabled: false, cleanMode: "mop" }, // disabled -> excluded
    { id: 3, enabled: true, cleanMode: "mop", waterLevel: "high" },
  ];
  const step = roomsToGroupStep(rooms);
  assert.equal(step.type, "room_group");
  assert.deepEqual(step.rooms.map((r) => r.room_id), [1, 3]);
  assert.deepEqual(step.rooms[0], {
    room_id: 1, clean_mode: "vacuum", fan_speed: "max", clean_passes: 2, edge_mopping: false,
  });
  assert.deepEqual(step.rooms[1], { room_id: 3, clean_mode: "mop", water_level: "high" });
});

test("[STP-grp-2] omits null/unset fields (they fall through to global at dispatch)", () => {
  const step = roomsToGroupStep([{ id: 5, enabled: true, cleanMode: "vacuum", fanSpeed: null }]);
  assert.deepEqual(step.rooms[0], { room_id: 5, clean_mode: "vacuum" }); // no fan_speed key
  assert.deepEqual(roomsToGroupStep([]).rooms, []);
  assert.deepEqual(roomsToGroupStep(null), { type: "room_group", rooms: [] });
});

/* ============================ wait steps ============================ */

test("[STP-wait-1] clampWaitMinutes rounds/clamps into [1,1440], fallback on empty", () => {
  assert.equal(clampWaitMinutes(30), 30);
  assert.equal(clampWaitMinutes(0), 1);
  assert.equal(clampWaitMinutes(5000), 1440);
  assert.equal(clampWaitMinutes("", 15), 15);
});

test("[STP-wait-2] insertWaitStep / setWaitMinutes", () => {
  const a = insertWaitStep([rg(1), rg(2)], 1, 45);
  assert.deepEqual(types(a), ["room_group", "wait", "room_group"]);
  assert.equal(a[1].wait_minutes, 45);
  assert.equal(setWaitMinutes(a, 1, 90)[1].wait_minutes, 90);
  assert.deepEqual(setWaitMinutes(a, 0, 90)[0], rg(1)); // no-op on a non-wait step
});

test("[STP-wait-3] sanitizeStepsForSave keeps wait steps (clamped, stripped)", () => {
  // Trailing rg(2) keeps the wait mid-sequence -- a trailing wait is refused
  // separately (CARD-6 clause 1, see STP-ins-2).
  const clean = sanitizeStepsForSave([rg(1), { type: "wait", wait_minutes: 5000, _uid: "x" }, rg(2)]);
  assert.deepEqual(clean[1], { type: "wait", wait_minutes: 1440 });
});

test("[STP-zone-1] sanitizeStepsForSave keeps zone steps (dedup ids, strip extras) — else editing a profile drops the zone", () => {
  const clean = sanitizeStepsForSave([
    rg(1),
    { type: "zone", zone_ids: ["z1", "z1", " z2 ", ""], _uid: "x" },
  ]);
  assert.deepEqual(clean[1], { type: "zone", zone_ids: ["z1", "z2"] });
  // a zone with no valid ids is dropped
  assert.deepEqual(sanitizeStepsForSave([rg(1), { type: "zone", zone_ids: [] }]).length, 1);
});

/* ====================== C40 — a leading zone ====================== */

// The backend refuses a profile whose first step is a zone (leading_zone_unsupported):
// apply_run_profile anchors each derived break by the rooms emitted before it, and a
// leading zone has emitted none, so it is silently skipped and never runs. These pin the
// card half of RN4T4MPV — if the editor can still compose one, the pair has diverged and
// the user builds something the service then rejects.

test("[STP-move] moveStep refuses to land a zone at index 0 (C40)", () => {
  const steps = [
    { type: "room_group", rooms: [{ room_id: 1 }] },
    { type: "zone", zone_ids: ["stove"] },
  ];
  const next = moveStep(steps, 1, 0);
  assert.deepEqual(
    next,
    steps,
    "a zone was moved to position 0 — the backend will refuse the save, so the editor must not offer the move"
  );
});

test("[STP-move] moveStep still reorders a zone anywhere else (C40 must not over-reach)", () => {
  const steps = [
    { type: "room_group", rooms: [{ room_id: 1 }] },
    { type: "room_group", rooms: [{ room_id: 2 }] },
    { type: "zone", zone_ids: ["stove"] },
  ];
  const next = moveStep(steps, 2, 1);
  assert.equal(next[1].type, "zone", "a legal mid-sequence move was blocked");
  assert.equal(next[0].type, "room_group");
});

test("[STP-move] a lone zone may still be moved to 0 — it is already there (C40)", () => {
  const steps = [{ type: "zone", zone_ids: ["stove"] }];
  assert.deepEqual(moveStep(steps, 0, 0), steps);
});

test("[STP-unsup] isUnsupportedBreakPosition flags a legacy leading zone (C40)", () => {
  const steps = [
    { type: "zone", zone_ids: ["stove"] },
    { type: "room_group", rooms: [{ room_id: 1 }] },
  ];
  assert.equal(
    isUnsupportedBreakPosition(steps, 0),
    true,
    "a stored leading zone must render struck-through, not as an ordinary about-to-run step — the refusal only guards NEW saves"
  );
  assert.equal(
    isUnsupportedBreakPosition(steps, 1),
    false,
    "the room_group after it is perfectly fine"
  );
});

test("[STP-unsup] a zone elsewhere is NOT flagged (C40 must not over-reach)", () => {
  const steps = [
    { type: "room_group", rooms: [{ room_id: 1 }] },
    { type: "zone", zone_ids: ["stove"] },
  ];
  assert.equal(isUnsupportedBreakPosition(steps, 1), false);
});

test("[STP-san] sanitizeStepsForSave does NOT strip a leading zone (C40)", () => {
  // isUnsupportedBreakPosition flags it; sanitize must still keep it, or editing and
  // saving a legacy profile would silently DELETE the zone — trading a silent drop at
  // apply for a silent loss at save. sanitize's shift/pop loops match charge/wait only.
  const out = sanitizeStepsForSave([
    { type: "zone", zone_ids: ["stove"] },
    { type: "room_group", rooms: [{ room_id: 1 }] },
  ]);
  assert.equal(out.length, 2, "the leading zone was stripped on save");
  assert.equal(out[0].type, "zone");
});
