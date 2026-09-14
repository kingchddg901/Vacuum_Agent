// Run: node --test src/bindings/room-rules-save-reaches-service.test.mjs
//
// Coverage targets
//   [RRS-1] the action EXISTS on VacuumCardActions.prototype  (it did not, since eae291fa)
//   [RRS-2] saveRoomRules sends `rules` through update_room_fields and nothing else
//   [RRS-3] an EMPTY list is sent, not dropped — deleting the last rule must persist a clear
//   [RRS-4] the SAVE binding actually reaches the action  (reachability, not payload shape)
//   [RRS-5] the DELETE binding actually reaches the action, with the rule removed
//   [RRS-6] a backend refusal still stops the drawer closing
//
// WHY. `room-rules-payload.test.mjs` proves `_buildRulePayload` builds the right object and
// stops there — a payload with no sink, the mirror of a service with no callers. The action it
// was handed to was never defined: `saveRoomRules?.()` evaluated to `undefined` at BOTH call
// sites, both refusal guards read false, and the drawer closed with no error while the rule was
// simply absent from the next snapshot. A UI glitch, not a failure, which is why it survived
// from the repo's first commit. `git log -S saveRoomRules -- src/` returns only eae291fa.
//
// THE INPUT THAT MAKES [RRS-1] AND [RRS-4]/[RRS-5] RED: delete `proto.saveRoomRules` from
// actions/rooms.js. The optional call goes back to `undefined`, no service is recorded, and the
// handlers still run to completion — which is precisely the shape of the original bug.

import { test } from "node:test";
import assert from "node:assert/strict";

import { VacuumCardActions } from "../actions/index.js";
import { applyRoomRulesBindings } from "./room-rules.js";

const ROOM = { id: 4, mapId: "1", name: "Kitchen" };
const EXISTING = [
  { id: "r1", entity_id: "binary_sensor.a", kind: "blocker", operator: "is_on" },
  { id: "r2", entity_id: "binary_sensor.b", kind: "blocker", operator: "is_on" },
];

/** A real VacuumCardActions, recording the services it calls. */
function makeActions(serviceResult = { updated: true }) {
  const calls = [];
  const actions = new VacuumCardActions(
    { callService: async (domain, service, data) => {
        calls.push({ domain, service, data });
        return { context: {}, response: serviceResult };
      } },
    { vacuumEntityId: () => "vacuum.robin", activeMapId: () => "1", clearAppliedRunProfile: () => {} },
    { showToast: () => {}, _renderers: { t: (k) => k, tRaw: (k) => k, escapeHtml: (v) => String(v ?? "") } },
  );
  // refreshRoomLearningEstimates fires after a successful write; stub the follow-on read so the
  // recorded calls are just the write under test.
  actions.refreshRoomLearningEstimates = async () => null;
  return { actions, calls };
}

test("[RRS-1] the action exists on the prototype", () => {
  assert.equal(
    typeof VacuumCardActions.prototype.saveRoomRules,
    "function",
    "bindings/room-rules.js has called this at two sites since eae291fa"
  );
});

test("[RRS-2] it sends `rules` through update_room_fields and nothing else", async () => {
  const { actions, calls } = makeActions();
  await actions.saveRoomRules(4, EXISTING);

  assert.equal(calls.length, 1);
  assert.equal(calls[0].service, "update_room_fields");
  assert.deepEqual(calls[0].data, {
    vacuum_entity_id: "vacuum.robin",
    map_id: "1",
    room_id: 4,
    rules: EXISTING,
  });
  // Any extra key here would be a field this writer silently overwrites on every rule save.
  assert.equal(Object.keys(calls[0].data).length, 4);
});

test("[RRS-3] an EMPTY list is sent, not dropped", async () => {
  // Deleting the last rule sends []. The backend guards on `is not None`, not truthiness, so []
  // persists as a clear — bailing on an empty array here would make the last delete a no-op.
  const { actions, calls } = makeActions();
  await actions.saveRoomRules(4, []);
  assert.deepEqual(calls[0].data.rules, []);

  // and a non-array degrades to a clear rather than sending undefined
  const second = makeActions();
  await second.actions.saveRoomRules(4, undefined);
  assert.deepEqual(second.calls[0].data.rules, []);
});

/** Drive the real binding with a fake shadow root; returns the recorded click handlers. */
function bindRules({ actions, serviceRecorder, draftValid = true, mode = "new" } = {}) {
  const proto = {};
  applyRoomRulesBindings(proto);
  const handlers = {};
  const closed = { count: 0 };
  const errors = [];

  const el = (action, ds = {}) => ({ dataset: { ...ds }, __action: action });
  const buttons = {
    "save-rule": [el("save-rule")],
    "delete-rule": [el("delete-rule", { ruleId: "r2" })],
  };

  const ctx = Object.create(proto);
  ctx.t = (k) => k;
  ctx.tRaw = (k) => k;
  ctx.card = {
    shadowRoot: {
      querySelectorAll: (sel) => {
        const hit = Object.keys(buttons).find((a) => sel.includes(a));
        return hit ? buttons[hit] : [];
      },
    },
    _on: (element, event, handler) => {
      if (event === "click" && element?.__action) handlers[element.__action] = handler;
    },
    _scheduleRender: () => {},
    refreshDashboardSnapshot: async () => {},
    _actions: actions,
    _state: {
      roomRulesDraftIsValid: () => draftValid,
      resolvedRoomRulesRoom: () => ROOM,
      roomRulesDraft: () => ({ id: mode === "edit" ? "r1" : null, entity_id: "binary_sensor.c", kind: "blocker", operator: "is_on" }),
      roomRulesDraftMode: () => mode,
      ruleEntityDescriptor: () => ({ valueModeForOperator: () => "text" }),
      roomRulesForRoom: () => EXISTING,
      setRoomRulesSaveError: (m) => { errors.push(m); },
      closeRulesDraft: () => { closed.count += 1; },
    },
  };
  ctx._bindRoomRules();
  return { handlers, closed, errors };
}

test("[RRS-4] the SAVE binding reaches the action", async () => {
  const { actions, calls } = makeActions();
  const { handlers, closed, errors } = bindRules({ actions });

  await handlers["save-rule"]();

  assert.equal(calls.length, 1, "the save must reach a service — it reached none for months");
  assert.equal(calls[0].service, "update_room_fields");
  assert.equal(calls[0].data.rules.length, EXISTING.length + 1, "the new rule must be appended");
  assert.equal(calls[0].data.rules.at(-1).entity_id, "binary_sensor.c");
  assert.equal(closed.count, 1, "a successful save closes the drawer");
  assert.deepEqual(errors, []);
});

test("[RRS-5] the DELETE binding reaches the action with the rule removed", async () => {
  const { actions, calls } = makeActions();
  const { handlers } = bindRules({ actions });

  await handlers["delete-rule"]();

  assert.equal(calls.length, 1, "the delete must reach a service");
  assert.deepEqual(
    calls[0].data.rules.map((r) => r.id),
    ["r1"],
    "r2 was deleted; r1 must survive"
  );
});

test("[RRS-6] a backend refusal keeps the drawer open and surfaces the reason", async () => {
  // The guard at the call site read `result?.ok === false` on `undefined` forever. Now that a
  // real result arrives, it has to actually bite.
  const { actions } = makeActions({ updated: false, reason: "invalid_access_graph" });
  const { handlers, closed, errors } = bindRules({ actions });

  await handlers["save-rule"]();

  assert.equal(closed.count, 0, "a refused save must not close the drawer");
  assert.deepEqual(errors, ["invalid_access_graph"]);
});
