// Run: node --test src/bindings/setup-floor-material.test.mjs
//
// SELECTION — the card side of floor_material.
//
// floor_type stays a closed eight-value vocabulary because it carries the
// carpet-water-off guarantee (profiles/room_profiles.py::no_water_value, plus
// startswith("carpet") at fourteen sites). floor_material is the second field and
// selects a LOOK only, so its semantics differ in ways that are easy to get wrong and
// silent when you do:
//
//   * "" is a REAL value — the "none" chip — meaning "clear it". The floor-type handler
//     guards `if (!floorType) return;`, and copying that guard here would make clearing
//     impossible while looking correct.
//   * an ABSENT room means "leave it alone", so only rooms the user touched are sent;
//     sending every room would let this view overwrite what the room editor set.
//   * the action wrapper destructures a FIXED argument list and builds the payload by
//     hand, so a parameter it does not name is dropped in silence — no error, no log,
//     and the service never sees it.
//
// Coverage (SFM = Setup Floor Material):
//   [SFM-1] the chip handler records the id and re-renders
//   [SFM-2] the "none" chip's empty string is recorded, not discarded
//   [SFM-3] save sends floor_materials alongside floor_types
//   [SFM-4] save OMITS floor_materials entirely when nothing was touched
//   [SFM-5] the action wrapper forwards it into the service payload
//   [SFM-6] the wrapper omits the key when the map is empty

import { test } from "node:test";
import assert from "node:assert/strict";

import { applySetupBindings } from "./setup.js";
import { applySetupActions } from "../actions/setup.js";

const VAC = "vacuum.alfred";
const MAP = "6";

function makeBinder({ materials = {} } = {}) {
  const proto = {};
  applySetupBindings(proto);
  const binder = Object.create(proto);

  const registered = {};
  const recorded = { ...materials };
  const calls = { save: [], render: 0 };

  binder.t = (k) => k;
  binder.tRaw = (k) => k;
  binder.card = {
    _config: { vacuum_entity_id: VAC },
    _onAll: (sel, ev, h) => { registered[`${sel}:${ev}`] = h; },
    _scheduleRender: () => { calls.render += 1; },
    showToast: () => {},
    t: (k) => k,
    _state: {
      setSetupRoomFloorMaterial: (roomId, m) => { recorded[String(roomId)] = m; },
      setSetupRoomFloorType: () => {},
      setupRoomEditorEnabledIds: () => [1],
      setupRoomEditorFloorTypesMap: () => ({ 1: "tile" }),
      setupRoomEditorFloorMaterialsMap: () => ({ ...recorded }),
      setSetupRoomEditorSaving: () => {},
      setSetupError: () => {},
      markSetupMapConfigured: () => {},
      closeSetupRoomEditor: () => {},
      setSetupStatus: () => {},
    },
    _actions: {
      saveSetupRooms: (...args) => { calls.save.push(args); return {}; },
      getSetupStatus: () => ({}),
    },
  };
  return { binder, registered, recorded, calls };
}

/** Register the handlers by invoking whichever binding entry point exists. */
function bind(binder) {
  for (const name of ["bindSetupEvents", "bindSetup", "applyBindings", "bind"]) {
    if (typeof binder[name] === "function") { binder[name](); return name; }
  }
  const fn = Object.getOwnPropertyNames(Object.getPrototypeOf(binder))
    .find((n) => /setup/i.test(n) && typeof binder[n] === "function");
  if (!fn) throw new Error("no setup binding entry point found");
  binder[fn]();
  return fn;
}

const click = (registered, sel, dataset) =>
  registered[`${sel}:click`]({ currentTarget: { dataset } });

test("[SFM-1] the chip handler records the chosen material and re-renders", () => {
  const { binder, registered, recorded, calls } = makeBinder();
  bind(binder);
  click(registered, "[data-action='setup-set-floor-material']",
    { roomId: "1", floorMaterial: "slate" });
  assert.equal(recorded["1"], "slate");
  assert.ok(calls.render > 0, "the chip must re-render so the active state moves");
});

test("[SFM-2] the \"none\" chip's empty string is recorded, not discarded", () => {
  // The floor-type handler guards on a truthy value. Copying that guard here would
  // make the none chip a no-op — it would look selectable and do nothing.
  const { binder, registered, recorded } = makeBinder({ materials: { 1: "slate" } });
  bind(binder);
  click(registered, "[data-action='setup-set-floor-material']",
    { roomId: "1", floorMaterial: "" });
  assert.equal(recorded["1"], "", "an explicit empty must CLEAR, not be ignored");
});

test("[SFM-3] save sends floor_materials alongside floor_types", async () => {
  const { binder, registered, calls } = makeBinder({ materials: { 1: "slate" } });
  bind(binder);
  await registered["[data-action='setup-save-rooms']:click"](
    { currentTarget: { dataset: { mapId: MAP } } });
  assert.equal(calls.save.length, 1);
  const [, , , floorTypes, floorMaterials] = calls.save[0];
  assert.deepEqual(floorTypes, { 1: "tile" });
  assert.deepEqual(floorMaterials, { 1: "slate" });
});

test("[SFM-4] save passes an empty map when nothing was touched", async () => {
  const { binder, registered, calls } = makeBinder();
  bind(binder);
  await registered["[data-action='setup-save-rooms']:click"](
    { currentTarget: { dataset: { mapId: MAP } } });
  const [, , , , floorMaterials] = calls.save[0];
  assert.deepEqual(floorMaterials, {},
    "untouched rooms must not be sent — absent means 'leave it alone'");
});

/* ---------------------------------------------------------------------------
   The action wrapper — the layer that drops a parameter in silence.
   --------------------------------------------------------------------------- */

function makeActions() {
  const proto = {};
  applySetupActions(proto);
  const actor = Object.create(proto);
  const sent = [];
  actor.callService = async (domain, service, data) => { sent.push({ domain, service, data }); return {}; };
  return { actor, sent };
}

test("[SFM-5] the action wrapper forwards floor_materials into the payload", async () => {
  const { actor, sent } = makeActions();
  await actor.saveSetupRooms(VAC, MAP, [1], { 1: "tile" }, { 1: "slate" });
  assert.equal(sent.length, 1);
  assert.deepEqual(sent[0].data.floor_materials, { 1: "slate" });
  assert.deepEqual(sent[0].data.floor_types, { 1: "tile" });
});

test("[SFM-6] the wrapper omits the key entirely when nothing was chosen", async () => {
  const { actor, sent } = makeActions();
  await actor.saveSetupRooms(VAC, MAP, [1], { 1: "tile" }, {});
  assert.ok(!("floor_materials" in sent[0].data),
    "an empty map must not widen the payload — absent already means 'unchanged'");

  const again = makeActions();
  await again.actor.saveSetupRooms(VAC, MAP, [1], { 1: "tile" });
  assert.ok(!("floor_materials" in again.sent[0].data),
    "an omitted argument must not become floor_materials: undefined");
});
