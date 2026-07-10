// Unit tests for the run-profile STEPS editor draft state in src/state/run-profiles.js — the
// charge-step / room-group authoring buffer the editor UI drives. Rides on the pure helpers in
// steps-order.js; here we cover the draft wiring + the "capture current room setup" snapshot +
// that editing an existing profile clones (never mutates) the stored steps.
// Run: node --test src/state/run-profiles-steps.test.mjs
//
// Coverage:
//   [RPS-1] fresh draft — empty, collapsed steps
//   [RPS-2] addDraftChargeStep — appends charge (default 95) + expands
//   [RPS-3] captureCurrentRoomsAsDraftGroup — snapshots ENABLED rooms (snake_case) + expands
//   [RPS-4] capture is a no-op when nothing enabled
//   [RPS-5] remove / move / setChargeTarget mutate the draft
//   [RPS-6] _normalizeRunProfile surfaces steps + has_charge_steps
//   [RPS-7] editing an existing profile loads a CLONED steps draft (no profile mutation)
//   [RPS-8..11] pendingStepRunProfileId — the "Start should run steps" gate (applied + has_charge_steps)
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyRunProfilesState } from "./run-profiles.js";

function makeState(rooms = []) {
  const proto = {};
  applyRunProfilesState(proto);
  const s = Object.create(proto);
  s.getRoomsForActiveMap = () => rooms;
  return s;
}

const rg = (...ids) => ({ type: "room_group", rooms: ids.map((room_id) => ({ room_id })) });
const cw = (t) => ({ type: "charge_wait", target_battery_percent: t });
const wait = (m) => ({ type: "wait", wait_minutes: m });
const types = (arr) => arr.map((x) => x.type);

test("[RPS-1] a fresh draft has empty, collapsed steps", () => {
  const s = makeState();
  assert.deepEqual(s.runProfileDraftSteps(), []);
  assert.equal(s.isDraftStepsExpanded(), false);
});

test("[RPS-2] addDraftChargeStep appends a charge (default 95) and expands", () => {
  const s = makeState();
  s._setDraftSteps([rg(1)]);
  s.addDraftChargeStep();
  assert.deepEqual(types(s.runProfileDraftSteps()), ["room_group", "charge_wait"]);
  assert.equal(s.runProfileDraftSteps()[1].target_battery_percent, 95);
  assert.equal(s.isDraftStepsExpanded(), true);
});

test("[RPS-3] captureCurrentRoomsAsDraftGroup snapshots enabled rooms (snake_case) + expands", () => {
  const s = makeState([
    { id: 1, enabled: true, cleanMode: "mop" },
    { id: 2, enabled: false, cleanMode: "vacuum" },
  ]);
  assert.equal(s.captureCurrentRoomsAsDraftGroup(), true);
  const steps = s.runProfileDraftSteps();
  assert.deepEqual(types(steps), ["room_group"]);
  assert.deepEqual(steps[0].rooms.map((r) => r.room_id), [1]);
  assert.equal(steps[0].rooms[0].clean_mode, "mop");
  assert.equal(s.isDraftStepsExpanded(), true);
});

test("[RPS-4] capture is a no-op when nothing is enabled", () => {
  const s = makeState([{ id: 1, enabled: false }]);
  assert.equal(s.captureCurrentRoomsAsDraftGroup(), false);
  assert.deepEqual(s.runProfileDraftSteps(), []);
});

test("[RPS-5] remove / move / setChargeTarget mutate the draft", () => {
  const s = makeState();
  s._setDraftSteps([rg(1), cw(95), rg(2)]);
  s.setDraftChargeTarget(1, 80);
  assert.equal(s.runProfileDraftSteps()[1].target_battery_percent, 80);
  s.moveDraftStep(1, -1); // charge up one
  assert.deepEqual(types(s.runProfileDraftSteps()), ["charge_wait", "room_group", "room_group"]);
  s.removeDraftStep(0);
  assert.deepEqual(types(s.runProfileDraftSteps()), ["room_group", "room_group"]);
});

test("[RPS-6] _normalizeRunProfile surfaces steps + has_charge_steps", () => {
  const s = makeState();
  const n = s._normalizeRunProfile({ id: "p1", name: "P", steps: [rg(1), cw(95)], has_charge_steps: true });
  assert.deepEqual(types(n.steps), ["room_group", "charge_wait"]);
  assert.equal(n.has_charge_steps, true);
});

test("[RPS-7] editing a profile loads a CLONED steps draft (no profile mutation)", () => {
  const s = makeState();
  s.setRunProfilesLibrary({ profiles: [{ id: "p1", name: "P", steps: [rg(1), cw(95)], has_charge_steps: true }] });
  s.selectRunProfile("p1");
  s.openSelectedRunProfileEditor();
  assert.equal(s.isDraftStepsExpanded(), true);
  s.setDraftChargeTarget(1, 50);
  assert.equal(s.selectedRunProfile().steps[1].target_battery_percent, 95); // original untouched
  assert.equal(s.runProfileDraftSteps()[1].target_battery_percent, 50);
});

test("[RPS-8] pendingStepRunProfileId is null when nothing is applied", () => {
  assert.equal(makeState().pendingStepRunProfileId(), null);
});

test("[RPS-9] pendingStepRunProfileId returns the id when the applied profile has charge steps", () => {
  const s = makeState();
  s.setRunProfilesLibrary({ profiles: [{ id: "p1", name: "P", steps: [rg(1), cw(95)], has_charge_steps: true }] });
  s.setAppliedRunProfile("p1");
  assert.equal(s.pendingStepRunProfileId(), "p1");
});

test("[RPS-10] pendingStepRunProfileId is null when the applied profile is NOT stepped", () => {
  const s = makeState();
  s.setRunProfilesLibrary({ profiles: [{ id: "p1", name: "P", has_charge_steps: false }] });
  s.setAppliedRunProfile("p1");
  assert.equal(s.pendingStepRunProfileId(), null);
});

test("[RPS-11] clearAppliedRunProfile resets the gate to flat", () => {
  const s = makeState();
  s.setRunProfilesLibrary({ profiles: [{ id: "p1", name: "P", steps: [rg(1), cw(95)], has_charge_steps: true }] });
  s.setAppliedRunProfile("p1");
  s.clearAppliedRunProfile();
  assert.equal(s.pendingStepRunProfileId(), null);
});

// ---- Defect #4f: pendingStepRunProfileId + has_stops must gate on SEQUENCED runs,
//      not charge-only. A WAIT-only or multi-group profile is stepped and MUST route
//      through start_run_profile, or Start flattens it (drops wait + group ordering).

test("[RPS-12] _normalizeRunProfile surfaces has_stops (backend flag wins)", () => {
  const s = makeState();
  // Backend stamps has_stops=true even though there are no charge steps.
  const n = s._normalizeRunProfile({ id: "p1", name: "P", steps: [rg(1), wait(10)], has_stops: true, has_charge_steps: false });
  assert.equal(n.has_stops, true);
  assert.equal(n.has_charge_steps, false); // stays charge-only
});

test("[RPS-13] _normalizeRunProfile derives has_stops from steps when backend omits it", () => {
  const s = makeState();
  // WAIT-only: no backend has_stops → derived true from the wait boundary.
  assert.equal(s._normalizeRunProfile({ id: "p1", name: "P", steps: [rg(1), wait(10)] }).has_stops, true);
  // Multi room_group (no charge/wait): derived true from >1 group.
  assert.equal(s._normalizeRunProfile({ id: "p2", name: "P", steps: [rg(1), rg(2)] }).has_stops, true);
  // Single room_group, no boundaries: flat queue → derived false.
  assert.equal(s._normalizeRunProfile({ id: "p3", name: "P", steps: [rg(1)] }).has_stops, false);
  // No steps at all (legacy rooms-only): derived false.
  assert.equal(s._normalizeRunProfile({ id: "p4", name: "P" }).has_stops, false);
});

test("[RPS-14] backend has_stops=false is honored even when steps would derive true", () => {
  const s = makeState();
  // Explicit backend false must win over the local fallback (null-check, not truthiness).
  const n = s._normalizeRunProfile({ id: "p1", name: "P", steps: [rg(1), wait(10)], has_stops: false });
  assert.equal(n.has_stops, false);
});

test("[RPS-15] pendingStepRunProfileId gates a WAIT-only applied profile (Defect #4f)", () => {
  const s = makeState();
  // charge-only flag is false; only has_stops is true — old gate would flatten this run.
  s.setRunProfilesLibrary({ profiles: [{ id: "p1", name: "P", steps: [rg(1), wait(10)], has_stops: true, has_charge_steps: false }] });
  s.setAppliedRunProfile("p1");
  assert.equal(s.pendingStepRunProfileId(), "p1");
});

test("[RPS-16] pendingStepRunProfileId gates a multi-group applied profile (Defect #4f)", () => {
  const s = makeState();
  // Two room_groups, no charge/wait — sequenced, must route stepped.
  s.setRunProfilesLibrary({ profiles: [{ id: "p1", name: "P", steps: [rg(1), rg(2)] }] });
  s.setAppliedRunProfile("p1");
  assert.equal(s.pendingStepRunProfileId(), "p1");
});

test("[RPS-17] pendingStepRunProfileId stays null for a flat single-group profile", () => {
  const s = makeState();
  s.setRunProfilesLibrary({ profiles: [{ id: "p1", name: "P", steps: [rg(1)], has_stops: false }] });
  s.setAppliedRunProfile("p1");
  assert.equal(s.pendingStepRunProfileId(), null);
});

test("[RPS-18] pendingStepRunProfileId still gates a charge-stepped profile", () => {
  const s = makeState();
  // has_charge_steps=true and no explicit has_stops → derived true (charge_wait boundary).
  s.setRunProfilesLibrary({ profiles: [{ id: "p1", name: "P", steps: [rg(1), cw(95)], has_charge_steps: true }] });
  s.setAppliedRunProfile("p1");
  assert.equal(s.pendingStepRunProfileId(), "p1");
});
