// Run: node --test src/bindings/setup-floor-fit.test.mjs
//
// PLACEMENT — the card side of floor_fit: where a FITTED material sits in a room.
//
// A drop-in that makes no `tileable` claim is scaled to cover its room ONCE rather than
// tiled, so which part of it you see is a choice somebody has to make. These controls
// are that choice. They sit beside the rotation chips and follow the same three rules —
// absent means leave it alone, explicit means set, never gates approval — but two things
// differ in ways that are silent when you get them wrong:
//
//   * an EMPTY object is a REAL value: "back to centred, exact cover". Deleting the
//     room's entry instead would mean "leave whatever is stored alone", which is the
//     opposite of what a reset asks for, and the button would appear to work while
//     changing nothing on the next save.
//   * a placement is MERGED, not replaced. Each control moves one axis, so a pan after a
//     zoom has to keep the zoom. Replacing would silently undo whichever was set first,
//     and only on the second interaction.
//
// The arithmetic lives in the RENDERER, which holds the current value and the chosen
// step, so each button carries the absolute result it would produce. The handler merges
// a patch rather than applying a delta: a stale DOM then writes a stale value, which is
// visible, in preference to compounding an increment, which is not.
//
// Coverage (SFF = Setup Floor Fit):
//   [SFF-1] the nudge handler merges the patch and re-renders
//   [SFF-2] a second patch on a different axis keeps the first
//   [SFF-3] reset writes an EMPTY object rather than deleting the entry
//   [SFF-4] the step button changes the step, and nothing else
//   [SFF-5] a malformed patch is ignored rather than writing NaN into the draft
//   [SFF-6] save sends floor_fits alongside the other maps
//   [SFF-7] the action wrapper forwards it, and OMITS the key when nothing was touched
//   [SFF-8] the REAL state merges rather than replaces  (SFF-2 only tests the harness)
//   [SFF-9] the REAL state clamps into the renderable range as it writes
//  [SFF-10] the REAL reset writes {} and the room survives into the save map

import { test } from "node:test";
import assert from "node:assert/strict";

import { applySetupBindings } from "./setup.js";
import { applySetupActions } from "../actions/setup.js";
import { applySetupState } from "../state/setup.js";

const VAC = "vacuum.alfred";
const MAP = "12";

function makeBinder({ fits = {} } = {}) {
  const proto = {};
  applySetupBindings(proto);
  const binder = Object.create(proto);

  const registered = {};
  const recorded = JSON.parse(JSON.stringify(fits));
  const calls = { save: [], render: 0, step: [] };

  binder.t = (k) => k;
  binder.card = {
    _config: { vacuum_entity_id: VAC },
    _onAll: (sel, ev, h) => { registered[`${sel}:${ev}`] = h; },
    _scheduleRender: () => { calls.render += 1; },
    showToast: () => {},
    t: (k) => k,
    _state: {
      // The real merge/clamp lives in state/setup.js; mirrored here so the binding's
      // own contract -- that it passes a PATCH through -- is what is under test.
      setSetupRoomFloorFit: (roomId, patch) => {
        const key = String(roomId);
        recorded[key] = { ...(recorded[key] || {}), ...patch };
      },
      resetSetupRoomFloorFit: (roomId) => { recorded[String(roomId)] = {}; },
      setSetupRoomEditorFloorFitStep: (n) => { calls.step.push(n); },
      setupRoomEditorFloorFitsMap: () => JSON.parse(JSON.stringify(recorded)),
      setSetupRoomFloorMaterial: () => {},
      setSetupRoomFloorType: () => {},
      setupRoomEditorEnabledIds: () => [1],
      setupRoomEditorFloorTypesMap: () => ({ 1: "tile" }),
      setupRoomEditorFloorMaterialsMap: () => ({}),
      setupRoomEditorFloorRotationsMap: () => ({}),
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

function bind(binder) {
  for (const name of ["bindSetupEvents", "bindSetup", "applyBindings", "bind"]) {
    if (typeof binder[name] === "function") { binder[name](); return; }
  }
  const fn = Object.getOwnPropertyNames(Object.getPrototypeOf(binder))
    .find((n) => /setup/i.test(n) && typeof binder[n] === "function");
  if (!fn) throw new Error("no setup binding entry point found");
  binder[fn]();
}

const click = (registered, sel, dataset) =>
  registered[`${sel}:click`]({ currentTarget: { dataset } });

const NUDGE = "[data-action='setup-nudge-floor-fit']";
const RESET = "[data-action='setup-reset-floor-fit']";
const STEP = "[data-action='setup-set-floor-fit-step']";

test("[SFF-1] the nudge handler merges the patch and re-renders", () => {
  const { binder, registered, recorded, calls } = makeBinder();
  bind(binder);
  click(registered, NUDGE, { roomId: "1", fitPatch: '{"tx":0.06,"ty":0}' });
  assert.deepEqual(recorded["1"], { tx: 0.06, ty: 0 });
  assert.ok(calls.render > 0, "the floor must repaint or the control reads as dead");
});

test("[SFF-2] a second patch on another axis keeps the first", () => {
  // Each control moves one axis. Replacing instead of merging would undo whichever was
  // set first, and only on the SECOND interaction -- which is why this is its own case.
  const { binder, registered, recorded } = makeBinder();
  bind(binder);
  click(registered, NUDGE, { roomId: "1", fitPatch: '{"scale":1.5}' });
  click(registered, NUDGE, { roomId: "1", fitPatch: '{"tx":0.14,"ty":-0.14}' });
  assert.deepEqual(recorded["1"], { scale: 1.5, tx: 0.14, ty: -0.14 },
    "a pan after a zoom must keep the zoom");
});

test("[SFF-3] reset writes an EMPTY object, it does not delete the entry", () => {
  // Absent means "leave whatever is stored alone" -- the opposite of a reset. Deleting
  // would make the button appear to work and change nothing on the next save.
  const { binder, registered, recorded } = makeBinder({ fits: { 1: { tx: 0.5, scale: 2 } } });
  bind(binder);
  click(registered, RESET, { roomId: "1" });
  assert.ok("1" in recorded, "the room must STAY in the map so the clear is transmitted");
  assert.deepEqual(recorded["1"], {});
});

test("[SFF-4] the step button changes the step and touches no placement", () => {
  const { binder, registered, recorded, calls } = makeBinder({ fits: { 1: { tx: 0.5 } } });
  bind(binder);
  click(registered, STEP, { fitStep: "7" });
  assert.deepEqual(calls.step, ["7"]);
  assert.deepEqual(recorded["1"], { tx: 0.5 }, "choosing a step must not move anything");
});

test("[SFF-5] a malformed patch is ignored rather than written through", () => {
  // The patch crosses the DOM as a string, so it is the one value here that can arrive
  // unparseable. A NaN written into the draft would reach a canvas transform and blank
  // the room with nothing logged.
  const { binder, registered, recorded } = makeBinder({ fits: { 1: { tx: 0.5 } } });
  bind(binder);
  for (const bad of ["{oops", "", "null", "3", '"tx"', undefined]) {
    click(registered, NUDGE, { roomId: "1", fitPatch: bad });
  }
  assert.deepEqual(recorded["1"], { tx: 0.5 }, "a bad patch must leave the draft alone");
  click(registered, NUDGE, { fitPatch: '{"tx":1}' });   // no roomId at all
  assert.deepEqual(Object.keys(recorded), ["1"], "a patch with no room must write nothing");
});

test("[SFF-6] save sends floor_fits alongside the other maps", async () => {
  const { binder, registered, calls } = makeBinder({ fits: { 1: { tx: 0.5, scale: 2 } } });
  bind(binder);
  await registered["[data-action='setup-save-rooms']:click"](
    { currentTarget: { dataset: { mapId: MAP } } });
  assert.equal(calls.save.length, 1);
  const [, , , , , , floorFits] = calls.save[0];
  assert.deepEqual(floorFits, { 1: { tx: 0.5, scale: 2 } },
    "the action wrapper destructures a FIXED list -- a seventh argument it does not "
    + "name is dropped in silence, with no error and no log");
});

test("[SFF-7] the wrapper forwards floor_fits, and omits the key when untouched", async () => {
  const proto = {};
  applySetupActions(proto);
  const actions = Object.create(proto);
  const sent = [];
  actions.callService = (domain, service, payload) => { sent.push(payload); return {}; };

  await actions.saveSetupRooms(VAC, MAP, [1], { 1: "tile" }, {}, {}, { 1: { tx: 0.5 } });
  assert.deepEqual(sent[0].floor_fits, { 1: { tx: 0.5 } });

  // An EMPTY OUTER map means "nothing to say" and the key is omitted -- but note the
  // inner value has the opposite sense: `{1: {}}` means "room 1 back to centred", which
  // is a real instruction and must survive.
  await actions.saveSetupRooms(VAC, MAP, [1], { 1: "tile" }, {}, {}, {});
  assert.ok(!("floor_fits" in sent[1]), "an empty map must not widen the payload");

  await actions.saveSetupRooms(VAC, MAP, [1], { 1: "tile" }, {}, {}, { 1: {} });
  assert.deepEqual(sent[2].floor_fits, { 1: {} },
    "an explicit empty placement is a CLEAR and must be transmitted");
});


/* ------------------------------------------------------------------------------
   AGAINST THE REAL STATE.

   [SFF-2] asserts the merge, and cannot catch it regressing: the binder harness above
   stubs `setSetupRoomFloorFit` and re-implements the merge inside the fake, so it is
   the fake under test there. These three go at the real thing. The binding half is
   still worth its own cases -- what it does is pass a PATCH through, and that is what
   those check -- but the behaviour the user feels lives here.
   ------------------------------------------------------------------------------ */

function makeState() {
  const proto = {};
  applySetupState(proto);
  return Object.create(proto);
}

test("[SFF-8] the real state MERGES a patch, it does not replace the placement", () => {
  const st = makeState();
  st.setSetupRoomFloorFit(1, { scale: 1.5 });
  st.setSetupRoomFloorFit(1, { tx: 0.14 });
  st.setSetupRoomFloorFit(1, { ty: -0.06 });
  assert.deepEqual(st.setupRoomFloorFit(1), { scale: 1.5, tx: 0.14, ty: -0.06 },
    "three controls, three axes -- each must survive the next");

  // Rooms are independent, and the key is normalised so 1 and "1" are one room.
  st.setSetupRoomFloorFit("2", { tx: 1 });
  assert.deepEqual(st.setupRoomFloorFit(2), { tx: 1 });
  assert.equal(st.setupRoomFloorFit(1).tx, 0.14, "room 2 must not disturb room 1");
});

test("[SFF-9] the real state clamps as it writes, and ignores what it cannot read", () => {
  // Clamped HERE as well as in the backend because the renderer reads this draft while
  // the editor is open -- the save is not the only consumer, and an unclamped draft
  // would preview something the save would not keep.
  const st = makeState();
  st.setSetupRoomFloorFit(1, { tx: 9, ty: -9, scale: 100 });
  assert.deepEqual(st.setupRoomFloorFit(1), { tx: 1, ty: -1, scale: 4 });

  st.setSetupRoomFloorFit(1, { tx: NaN, ty: "nope", scale: undefined });
  assert.deepEqual(st.setupRoomFloorFit(1), { tx: 1, ty: -1, scale: 4 },
    "an unreadable value leaves the axis alone rather than zeroing it");

  st.setSetupRoomFloorFit(1, {});
  assert.deepEqual(st.setupRoomFloorFit(1), { tx: 1, ty: -1, scale: 4 },
    "an empty PATCH is not a reset -- that is what resetSetupRoomFloorFit is for");
});

test("[SFF-10] the real reset writes {} and the room stays in the save map", () => {
  const st = makeState();
  st.setSetupRoomFloorFit(1, { tx: 0.5, scale: 2 });
  st.resetSetupRoomFloorFit(1);
  assert.deepEqual(st.setupRoomFloorFit(1), {});
  assert.deepEqual(st.setupRoomEditorFloorFitsMap(), { 1: {} },
    "the room must reach the service as an explicit empty -- absent would mean "
    + "'leave whatever is stored alone', which is the opposite of a reset");

  // The step is its own thing and a reset must not touch it.
  assert.equal(st.setupRoomEditorFloorFitStep(), 3);
  st.setSetupRoomEditorFloorFitStep(7);
  st.resetSetupRoomFloorFit(1);
  assert.equal(st.setupRoomEditorFloorFitStep(), 7);
  st.setSetupRoomEditorFloorFitStep("nonsense");
  assert.equal(st.setupRoomEditorFloorFitStep(), 3, "junk falls back to the medium step");
});
