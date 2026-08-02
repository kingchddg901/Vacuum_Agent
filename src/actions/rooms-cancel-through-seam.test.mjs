// Regression tests for the card-cancel bypass — the card's Cancel button sent the stock
// HA `vacuum.return_to_base` directly instead of the integration's `cancel_active_job`.
//
// The robot obeyed, so a cancel LOOKED like it worked. But the integration was never told
// the run ended early: the tracker kept believing the job was live, and when the robot
// reached the dock the finalizer saw "docked, no phases left" and wrote
// `status: completed` / `was_cancelled: false` / `used_for_learning: true`. Truncated room
// times were then learned as honest ones, and no incomplete-run log entry was ever written.
//
// Caught by LIVE OBSERVATION, not by an audit: alfred job_2026-08-01T23-48-48 recorded a
// user-cancelled run as completed. `cancel_active_job` had ZERO callers anywhere in src/.
//
// The asymmetry is the defect's shape: the card STARTS jobs through the integration
// (`start_selected_rooms`) and CANCELLED them around it. `cancel_active_job` performs the
// return-to-base itself, so this is a replacement, not a second command — and it is the
// only entry into RP-010's cancel chokepoint (single-flight latch, watchdog stop, and the
// terminal-state confirm before the record is written).
//
// Run: node --test src/actions/rooms-cancel-through-seam.test.mjs
//
// Coverage (CTS = Cancel Through Seam):
//   [CTS-1] cancelActiveRun calls eufy_vacuum.cancel_active_job
//   [CTS-2] it NEVER calls vacuum.return_to_base (the bypass must not come back)
//   [CTS-3] it passes vacuum_entity_id, and map_id when the card knows it
//   [CTS-4] map_id is omitted (not sent null) when unknown — server resolves the active map
//   [CTS-5] no vacuum entity → no service call at all
//   [CTS-6] confirmation state is still cleared (behavior preserved)
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyRoomsActions } from "./rooms.js";

function makeCard(overrides = {}) {
  const proto = {};
  applyRoomsActions(proto);
  const card = Object.create(proto);

  const calls = { callService: [], clearedCancel: 0, clearedStart: 0 };

  card.state = {
    vacuumEntityId: () => "vacuum.alfred",
    activeMapId: () => "12",
    clearCancelRunConfirmation: () => { calls.clearedCancel += 1; },
    clearStartConfirmation: () => { calls.clearedStart += 1; },
    getRoomsForActiveMap: () => [],
    ...(overrides.state ?? {}),
  };

  card.callService = async (...args) => { calls.callService.push(args); };
  card.callHA = async () => {};

  return { card, calls };
}

test("[CTS-1] cancelActiveRun goes through eufy_vacuum.cancel_active_job", async () => {
  const { card, calls } = makeCard();
  await card.cancelActiveRun();

  assert.equal(calls.callService.length, 1);
  const [domain, service] = calls.callService[0];
  assert.equal(domain, "eufy_vacuum");
  assert.equal(service, "cancel_active_job");
});

test("[CTS-2] cancelActiveRun never calls vacuum.return_to_base", async () => {
  const { card, calls } = makeCard();
  await card.cancelActiveRun();

  // The whole defect: docking the robot without telling the job tracker. Any future
  // refactor that reintroduces a bare dock command here must fail loudly.
  const bypassed = calls.callService.some(
    ([domain, service]) => domain === "vacuum" && service === "return_to_base"
  );
  assert.equal(bypassed, false, "cancel must not send a bare dock command");
});

test("[CTS-3] passes vacuum_entity_id and map_id when known", async () => {
  const { card, calls } = makeCard();
  await card.cancelActiveRun();

  const [, , data] = calls.callService[0];
  assert.equal(data.vacuum_entity_id, "vacuum.alfred");
  assert.equal(data.map_id, "12");
});

test("[CTS-4] omits map_id entirely when the card does not know it", async () => {
  const { card, calls } = makeCard({ state: { activeMapId: () => null } });
  await card.cancelActiveRun();

  const [, , data] = calls.callService[0];
  // services.yaml marks map_id optional ("leave blank to use the current active map"),
  // so the key must be ABSENT rather than present-and-null.
  assert.equal("map_id" in data, false);
  assert.equal(data.vacuum_entity_id, "vacuum.alfred");
});

test("[CTS-5] no vacuum entity → no service call", async () => {
  const { card, calls } = makeCard({ state: { vacuumEntityId: () => "" } });
  await card.cancelActiveRun();

  assert.equal(calls.callService.length, 0);
  assert.equal(calls.clearedCancel, 0);
});

test("[CTS-6] confirmation state is still cleared", async () => {
  const { card, calls } = makeCard();
  await card.cancelActiveRun();

  assert.equal(calls.clearedCancel, 1);
  assert.equal(calls.clearedStart, 1);
});
