// Regression test — CARD-1/FE-ERR-1, the flagship finding of SYNTH-11's CARD-1
// packet ("carried CF-5 (FE-ERR-1 / MZ-2, the two failure-renders-as-success
// paths)"). core-refusal-shape.test.mjs proves the GENERIC callService wrapper
// now inspects a non-throwing {success:false, reason} response and toasts it --
// but FE-ERR-1's own real call site, proto.startCleaning (this file), never
// exercised that generic wrapper at all: start_selected_rooms was called with
// returnResponse hardcoded FALSE (job_control.py wasn't a supports_response
// service either), so a refusal at the ACTUAL dispatch -- as opposed to the
// earlier get_start_status pre-check, which can race it (TOCTOU) -- silently
// returned with no toast, no state change beyond a cleared confirmation, and
// nothing telling the user the robot never moved.
//
// The fix spans both sides of the seam: job_control.py's start_selected_rooms
// is now registered supports_response=True and its handler returns the
// manager's payload instead of discarding it; this call site now passes
// returnResponse=true and fires a toast for every blocked reason EXCEPT
// confirmation_required (which already has its own dedicated confirm dialog --
// RST-2 below proves that path stays toast-free, not silently untested).
//
// Distinct from MZ-2 (map.js's cleanZone / start_zone_clean), which already
// returned {success:false} through the response-capable generic wrapper and is
// covered by CRS-1 in core-refusal-shape.test.mjs; see also
// map-zone-clean-refusal-toast.test.mjs for MZ-2's own explicit real-call-site
// test.
//
// Run: node --test src/actions/rooms-start-refusal-toast.test.mjs
//
// Coverage (RST = Rooms Start Toast):
//   [RST-1] a start_selected_rooms {started:false, reason} refusal (a reason
//           OTHER than confirmation_required) raises an error toast naming it
//   [RST-2] {started:false, reason:"confirmation_required"} raises NO toast --
//           it opens the dedicated confirm dialog instead (state.setStartConfirmation)
//   [RST-3] start_selected_rooms is called with returnResponse=true (the
//           hardcoded-false bug, reintroduced, must fail this loudly)
//   [RST-4] a genuine start ({started:true}) raises no toast (control)

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyCoreActions } from "./core.js";
import { applyRoomsActions } from "./rooms.js";

function makeCard({ startResponse, getStartStatusResponse = { blocked: false, reason: "ready" } } = {}) {
  const proto = {};
  applyCoreActions(proto);
  applyRoomsActions(proto);
  const card = Object.create(proto);

  card.toasts = [];
  card.showToast = (message, opts) => card.toasts.push({ message, ...opts });
  card.t = (key, vars) => `T:${key}:${vars?.reason ?? vars?.service ?? ""}`;

  const hassCalls = [];
  card.hass = {
    callService: async (domain, service, data, target, notifyOnError, returnResponse) => {
      hassCalls.push({ domain, service, data, returnResponse });
      if (service === "get_start_status") return getStartStatusResponse;
      if (service === "start_selected_rooms") return startResponse;
      return undefined;
    },
  };

  const stateCalls = { setStartConfirmation: 0, clearStartConfirmation: 0 };
  card.state = {
    vacuumEntityId: () => "vacuum.alfred",
    activeMapId: () => "1",
    batteryLevel: () => 80,
    strictOrder: () => false,
    resetLiveTrail: () => {},
    setStartStatus: () => {},
    clearCancelRunConfirmation: () => {},
    setStartConfirmation: () => { stateCalls.setStartConfirmation += 1; },
    clearStartConfirmation: () => { stateCalls.clearStartConfirmation += 1; },
    // Only reached past a genuine (non-blocked) start -- RST-3/RST-4 exercise that path.
    setLearningEstimate: () => {},
    setLearningReanchored: () => {},
    setLearningCompletedRooms: () => {},
    setLearningNextRoom: () => {},
    setLearningJobActive: () => {},
    beginLearningJob: () => {},
    learningReanchored: () => null,
  };
  card.runLearningEstimate = async () => null;

  return { card, hassCalls, stateCalls };
}

test("[RST-1] a blocked start (not confirmation_required) raises an error toast naming the reason", async () => {
  const { card } = makeCard({
    startResponse: { started: false, reason: "job_paused", message: "A tracked job is paused." },
  });

  const result = await card.startCleaning();

  assert.equal(card.toasts.length, 1, "the refusal reached no one -- the caller sees a normal response");
  assert.equal(card.toasts[0].kind, "error");
  assert.match(card.toasts[0].message, /job_paused/);
  assert.equal(result.started, false);
});

test("[RST-2] confirmation_required raises NO toast -- the dedicated dialog owns it", async () => {
  const { card, stateCalls } = makeCard({
    startResponse: {
      started: false,
      reason: "confirmation_required",
      message: "Confirm the reduced run.",
      confirm_token: "tok-1",
    },
  });

  const result = await card.startCleaning();

  assert.deepEqual(card.toasts, [], "confirmation_required has its own dialog -- a toast here would double up the UI");
  assert.equal(stateCalls.setStartConfirmation, 1);
  assert.equal(stateCalls.clearStartConfirmation, 0);
  assert.equal(result.reason, "confirmation_required");
});

test("[RST-3] start_selected_rooms is called with returnResponse=true", async () => {
  const { card, hassCalls } = makeCard({ startResponse: { started: true } });
  await card.startCleaning();

  const startCall = hassCalls.find((c) => c.service === "start_selected_rooms");
  assert.ok(startCall, "start_selected_rooms was never called");
  assert.equal(
    startCall.returnResponse,
    true,
    "start_selected_rooms must use returnResponse=true (job_control.py is now supports_response=True) " +
      "-- FE-ERR-1's whole fix depends on this; a regression back to false makes every refusal " +
      "at the real dispatch invisible again",
  );
});

test("[RST-4] a genuine start raises no toast (control)", async () => {
  const { card } = makeCard({ startResponse: { started: true, job_id: "j1" } });
  await card.startCleaning();

  assert.deepEqual(card.toasts, [], "a genuine start produced an error toast -- the signal is noise");
});
