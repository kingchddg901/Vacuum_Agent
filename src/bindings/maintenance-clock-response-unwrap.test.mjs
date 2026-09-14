// Run: node --test src/bindings/maintenance-clock-response-unwrap.test.mjs
//
// Coverage targets — src/bindings/maintenance.js
//   [MCU-1] the LIVE envelope `{context, response:{candidates}}` reaches the picker
//   [MCU-2] the bare `{candidates}` compatibility arm still reaches it
//   [MCU-3] a transport failure (null) sets the error — it must NOT read as "no counters"
//   [MCU-4] a genuinely empty list is an empty list, not an error
//   [MCU-5] a `{status:"error"}` refusal on save is a refusal, not a save
//
// WHY THIS EXISTS. A `supports_response` service comes back from `hass.callService` as
// `{context, response}`. Measured on the live panel 2026-09-13: the backend returned SIX
// candidates and the modal rendered "No suitable counter found on this vacuum", because the
// binding read `result.candidates` off the envelope. All 86 response-reading call sites in
// src/actions/ already spell it `result?.response ?? result`; these two — the first in
// src/bindings/ — did not. The shorter copy is the bug.
//
// THE INPUT THAT MAKES [MCU-1] RED: restore `result?.candidates ?? []`. The envelope carries
// nothing at that depth, so the picker is handed [] and shows its empty state over a full list.

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyMaintenanceBindings } from "./maintenance.js";

/** A bindings object with just enough card surface to exercise the two service paths. */
function makeBindings(serviceResult) {
  const proto = {};
  applyMaintenanceBindings(proto);

  const calls = { candidates: [], errors: [], renders: 0, services: [], refreshes: 0, pending: [] };
  const ctx = Object.create(proto);
  ctx.t = (key, vars) => `T(${key}${vars ? ":" + JSON.stringify(vars) : ""})`;
  ctx.card = {
    _scheduleRender: () => { calls.renders += 1; },
    refreshDashboardSnapshot: async () => { calls.refreshes += 1; },
    _actions: {
      callNamedService: async (name, data, wantsResponse) => {
        calls.services.push({ name, data, wantsResponse });
        return typeof serviceResult === "function" ? serviceResult(name) : serviceResult;
      },
    },
    _state: {
      vacuumEntityId: () => "vacuum.robin",
      setMaintenanceClockCandidates: (list) => { calls.candidates.push(list); },
      setMaintenanceClockPickerError: (msg) => { calls.errors.push(msg); },
      setMaintenanceClockPending: (id) => { calls.pending.push(id); },
    },
  };
  return { ctx, calls };
}

test("[MCU-1] the live {context, response} envelope reaches the picker", async () => {
  const six = Array.from({ length: 6 }, (_, i) => ({ entity_id: `sensor.c${i}` }));
  const { ctx, calls } = makeBindings({ context: { id: "01J" }, response: { candidates: six } });

  await ctx._fetchMaintenanceClockCandidates();

  assert.deepEqual(calls.candidates, [six], "the six candidates must survive the unwrap");
  assert.deepEqual(calls.errors, [], "a successful fetch must not set an error");
  assert.equal(calls.services[0].name, "eufy_vacuum.get_maintenance_source_candidates");
  assert.equal(calls.services[0].wantsResponse, true, "the service must be asked FOR a response");
});

test("[MCU-2] a bare {candidates} payload still reaches the picker", async () => {
  const one = [{ entity_id: "sensor.total_cleaning_time" }];
  const { ctx, calls } = makeBindings({ candidates: one });

  await ctx._fetchMaintenanceClockCandidates();

  assert.deepEqual(calls.candidates, [one], "the `?? result` compatibility arm must still work");
  assert.deepEqual(calls.errors, []);
});

test("[MCU-3] a transport failure is an ERROR, never an empty list", async () => {
  // The renderer distinguishes `null` (still asking) from `[]` (nothing to offer). Handing it
  // an empty list here would state, falsely, that the vacuum owns no usable counter.
  for (const failure of [null, undefined]) {
    const { ctx, calls } = makeBindings(failure);
    await ctx._fetchMaintenanceClockCandidates();
    assert.deepEqual(calls.candidates, [], `${failure} must not set a candidate list`);
    assert.equal(calls.errors.length, 1, `${failure} must set exactly one error`);
    assert.match(calls.errors[0], /get_maintenance_source_candidates/);
  }
});

test("[MCU-4] a genuinely empty list is an empty list, not an error", async () => {
  const { ctx, calls } = makeBindings({ context: {}, response: { candidates: [] } });
  await ctx._fetchMaintenanceClockCandidates();
  assert.deepEqual(calls.candidates, [[]]);
  assert.deepEqual(calls.errors, [], "the backend answered; that is not a failure");
});

/** A host stub: one candidate row, and `_on` hands us the click handler it would attach. */
function makeHost(ctx, calls) {
  const row = { dataset: { entityId: "sensor.robin_total_cleaning_time" } };
  let clickHandler = null;
  ctx.card._on = (el, event, handler) => {
    if (el === row && event === "click") clickHandler = handler;
  };
  const host = {
    querySelectorAll: (sel) => (sel.includes("select-maintenance-clock") ? [row] : []),
    querySelector: () => null,
  };
  ctx._bindMaintenanceModalHost(host);
  assert.equal(typeof clickHandler, "function", "the row must have been bound");
  return () => clickHandler();
}

test("[MCU-5] a {status:'error'} refusal on save is a refusal, not a save", async () => {
  // set_entity_override ANSWERS a refusal ({status:"error", reason:"runtime_unavailable"})
  // rather than raising, so a null-only check closes over a choice that was never stored.
  const { ctx, calls } = makeBindings({
    context: {},
    response: { status: "error", reason: "runtime_unavailable" },
  });
  const click = makeHost(ctx, calls);

  await click();

  assert.equal(calls.errors.length, 1, "the refusal must be surfaced");
  assert.match(calls.errors[0], /set_entity_override/);
  assert.equal(calls.refreshes, 0, "a refused save must not refresh as though it took");
  assert.equal(calls.pending.at(-1), "", "the pending marker must be cleared either way");
});

test("[MCU-5b] a real save refreshes and re-reads, and sets no error", async () => {
  const { ctx, calls } = makeBindings((name) =>
    name === "eufy_vacuum.set_entity_override"
      ? { context: {}, response: { status: "success", role: "maintenance_clock" } }
      : { context: {}, response: { candidates: [{ entity_id: "sensor.x", is_current: true }] } }
  );
  const click = makeHost(ctx, calls);

  await click();

  assert.deepEqual(calls.errors, [], "a successful save must set no error");
  assert.equal(calls.refreshes, 1, "the dashboard must re-read so every row picks up the source");
  assert.deepEqual(
    calls.candidates.at(-1),
    [{ entity_id: "sensor.x", is_current: true }],
    "the list must re-read so the current-selection marker moves"
  );
});
