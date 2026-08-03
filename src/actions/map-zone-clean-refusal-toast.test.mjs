// Regression test — CARD-1/MZ-2, the second of the two failure-renders-as-
// success paths SYNTH-11's CARD-1 packet names explicitly ("carried CF-5
// (FE-ERR-1 / MZ-2, ...)"). core-refusal-shape.test.mjs's CRS-1 proves the
// GENERIC callService wrapper toasts a {success:false, reason} response, using
// "job_in_progress" (MZ-2's actual reason literal) as its example -- but it
// calls card.callService(...) directly. This file closes the gap by exercising
// MZ-2's OWN real call site, proto.cleanZone (map.js), end to end: draw-a-
// zone -> dispatch -> refused -> toast.
//
// Backend: job_control.py's _handle_start_zone_clean consults get_start_status
// first and, when a job is already running/paused/mid-service, returns
// {success:false, reason:"job_in_progress", start_status_reason, message}
// WITHOUT raising (services.py registers start_zone_clean supports_response=True) --
// this was already correctly reachable through the generic wrapper before this
// pass; this test pins that call site (not just the wrapper shape) so a future
// refactor of cleanZone can't silently drop returnResponse=true / the shape
// match, same as RST-3 pins startCleaning's returnResponse for FE-ERR-1.
//
// Run: node --test src/actions/map-zone-clean-refusal-toast.test.mjs
//
// Coverage (MZT = Map Zone clean Toast):
//   [MZT-1] a start_zone_clean {success:false, reason:"job_in_progress"} refusal
//           raises an error toast naming it
//   [MZT-2] cleanZone is called with returnResponse=true
//   [MZT-3] a genuine dispatch ({success:true}) raises no toast (control)
//   [MZT-4] no vacuum entity -> no service call, no toast (existing guard clause)

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyCoreActions } from "./core.js";
import { applyMapActions } from "./map.js";

function makeCard({ response, vacuumEntityId = "vacuum.alfred" } = {}) {
  const proto = {};
  applyCoreActions(proto);
  applyMapActions(proto);
  const card = Object.create(proto);

  card.toasts = [];
  card.showToast = (message, opts) => card.toasts.push({ message, ...opts });
  card.t = (key, vars) => `T:${key}:${vars?.reason ?? vars?.service ?? ""}`;

  const hassCalls = [];
  card.hass = {
    callService: async (domain, service, data, target, notifyOnError, returnResponse) => {
      hassCalls.push({ domain, service, data, returnResponse });
      return response;
    },
  };

  card.state = {
    vacuumEntityId: () => vacuumEntityId,
    activeMapId: () => "1",
    resetLiveTrail: () => {},
  };

  return { card, hassCalls };
}

test("[MZT-1] a job_in_progress refusal raises an error toast naming the reason", async () => {
  const { card } = makeCard({
    response: {
      success: false,
      reason: "job_in_progress",
      start_status_reason: "active_job_running",
      message: "A job is already running.",
    },
  });

  const result = await card.cleanZone([[0, 0, 1, 1]]);

  assert.equal(card.toasts.length, 1, "the refusal reached no one -- the zone draw looked like it worked");
  assert.equal(card.toasts[0].kind, "error");
  assert.match(card.toasts[0].message, /job_in_progress/);
  assert.equal(result.success, false);
});

test("[MZT-2] cleanZone calls start_zone_clean with returnResponse=true", async () => {
  const { card, hassCalls } = makeCard({ response: { success: true, zones_dispatched: 1 } });
  await card.cleanZone([[0, 0, 1, 1]]);

  const call = hassCalls.find((c) => c.service === "start_zone_clean");
  assert.ok(call, "start_zone_clean was never called");
  assert.equal(call.domain, "eufy_vacuum");
  assert.equal(
    call.returnResponse,
    true,
    "cleanZone must use returnResponse=true -- without it a job_in_progress refusal is indistinguishable from success",
  );
});

test("[MZT-3] a genuine dispatch raises no toast (control)", async () => {
  const { card } = makeCard({ response: { success: true, zones_dispatched: 1 } });
  await card.cleanZone([[0, 0, 1, 1]]);

  assert.deepEqual(card.toasts, [], "a successful zone clean produced an error toast -- the signal is noise");
});

test("[MZT-4] no vacuum entity -> no service call, no toast", async () => {
  const { card, hassCalls } = makeCard({ response: { success: true }, vacuumEntityId: "" });
  const result = await card.cleanZone([[0, 0, 1, 1]]);

  assert.equal(hassCalls.length, 0);
  assert.deepEqual(card.toasts, []);
  assert.equal(result, null);
});
