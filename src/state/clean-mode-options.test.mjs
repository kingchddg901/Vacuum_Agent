// Run: node --test src/state/clean-mode-options.test.mjs
//
// Coverage targets — issue #48, the CARD half
//   [CMO-1] the stored DISPLAY label and the adapter TOKEN are one option
//   [CMO-2] a genuinely unknown stored value is still kept re-selectable
//   [CMO-3] non-clean_mode roles keep plain lowercase de-duplication
//   [CMO-4] the canonical compare matches every spelling pair
//
// The card seeds clean_mode through _canonicalCleanModeDisplay, which returns a
// DISPLAY label ("Vacuum and mop"). The adapter declares the TOKEN
// ("vacuum_mop"). _buildOptionListForRole de-duplicated by raw lowercase, so the
// two read as different options: the stored label was appended as an extra chip
// AND — because the renderer compared with === — it was the one that looked
// active, leaving the real option inert. Chris's screenshot shows exactly that:
// "Vacuum and mop" listed twice, the duplicate highlighted.

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyRoomEditorState } from "./room-editor.js";

function makeState({ options, current }) {
  const proto = {};
  applyRoomEditorState(proto);
  const state = Object.create(proto);
  state.adapterOptionsFor = () => options;
  state.editorFields = () => ({ clean_mode: current });
  state.isEditorRoomCarpet = () => false;
  return state;
}

const ADAPTER = [
  { value: "vacuum", label: "Vacuum" },
  { value: "mop", label: "Mop" },
  { value: "vacuum_mop", label: "Vacuum and mop" },
];

test("[CMO-1] the stored display label does not become a duplicate chip", () => {
  const state = makeState({ options: ADAPTER, current: "Vacuum and mop" });
  const opts = state.cleanModeOptions();

  assert.equal(opts.length, 3, `expected 3 options, got ${JSON.stringify(opts)}`);
  const combined = opts.filter(
    (o) => state._canonicalCleanModeCompare(o.value) === "vacuum_mop"
  );
  assert.equal(combined.length, 1, "vacuum+mop must appear exactly once");
  // the surviving entry is the ADAPTER's, so its value round-trips as the token
  assert.equal(combined[0].value, "vacuum_mop");
});

test("[CMO-1b] the surviving option still matches the stored value as ACTIVE", () => {
  // Removing the duplicate is only half the fix: if the active comparison stays
  // a raw ===, the picker renders with NOTHING selected.
  const state = makeState({ options: ADAPTER, current: "Vacuum and mop" });
  const opts = state.cleanModeOptions();
  const active = opts.filter(
    (o) =>
      state._canonicalCleanModeCompare("Vacuum and mop") ===
      state._canonicalCleanModeCompare(o.value)
  );
  assert.equal(active.length, 1, "exactly one chip must read as active");
  assert.equal(active[0].value, "vacuum_mop");
});

test("[CMO-2] an unknown stored value is still kept re-selectable", () => {
  // The legacy fallback exists so a value the adapter no longer declares stays
  // visible for THIS room. Canonicalising must not delete that behaviour.
  const state = makeState({ options: ADAPTER, current: "Scrub" });
  const opts = state.cleanModeOptions();
  assert.ok(
    opts.some((o) => o.value === "Scrub"),
    `unknown stored value was dropped: ${JSON.stringify(opts)}`
  );
});

test("[CMO-3] other roles keep plain lowercase de-duplication", () => {
  const proto = {};
  applyRoomEditorState(proto);
  const state = Object.create(proto);
  state.adapterOptionsFor = () => [
    { value: "Standard", label: "Standard" },
    { value: "standard", label: "dupe" },   // same option, different case
    { value: "Max", label: "Max" },
  ];
  state.editorFields = () => ({ fan_speed: "Max" });

  const opts = state._buildOptionListForRole("fan_speed", "fan_speed");
  assert.deepEqual(opts.map((o) => o.value), ["Standard", "Max"]);
});

test("[CMO-4] the canonical compare folds every spelling pair", () => {
  const proto = {};
  applyRoomEditorState(proto);
  const state = Object.create(proto);
  const c = (v) => state._canonicalCleanModeCompare(v);

  for (const spelling of ["vacuum_mop", "Vacuum and mop", "VACUUM MOP",
                          "vacuum-mop", "vacuum+mop", "vacuummop"]) {
    assert.equal(c(spelling), "vacuum_mop", `not folded: ${spelling}`);
  }
  assert.equal(c("Vacuum"), "vacuum");
  assert.equal(c("MOP"), "mop");
  // an unknown mode passes through rather than being forced into a known bucket
  assert.equal(c("Scrub"), "scrub");
});


// ---------------------------------------------------------------------------
// Water level: "Off" is not offered while mopping
// ---------------------------------------------------------------------------

function makeWaterState({ current, cleanMode, carpet = false }) {
  const proto = {};
  applyRoomEditorState(proto);
  const state = Object.create(proto);
  state.adapterOptionsFor = () => [
    { value: "Off", label: "Off" },
    { value: "Low", label: "Low" },
    { value: "Medium", label: "Medium" },
    { value: "High", label: "High" },
  ];
  state.editorFields = () => ({ water_level: current, clean_mode: cleanMode });
  state.isEditorRoomCarpet = () => carpet;
  return state;
}

test("[WL-1] a mop mode does not offer Off", () => {
  // The backend substitutes the floor-type default for off/empty water on a
  // non-carpet mop room, so offering Off lets the user pick something that is
  // silently overwritten.
  for (const mode of ["Vacuum and mop", "vacuum_mop", "mop", "Mop"]) {
    const state = makeWaterState({ current: "Medium", cleanMode: mode });
    const values = state.waterLevelOptions().map((o) => o.value);
    assert.ok(!values.includes("Off"), `Off offered in ${mode}: ${values}`);
    assert.deepEqual(values, ["Low", "Medium", "High"]);
  }
});

test("[WL-2] a vacuum-only mode still offers Off", () => {
  // The row is normally hidden for vacuum-only, but the option list itself must
  // not lose Off — other callers and the carpet path depend on it.
  const state = makeWaterState({ current: "Off", cleanMode: "Vacuum" });
  assert.deepEqual(
    state.waterLevelOptions().map((o) => o.value),
    ["Off", "Low", "Medium", "High"]
  );
});

test("[WL-3] carpet is untouched by the mop filter", () => {
  const state = makeWaterState({ current: "Off", cleanMode: "Vacuum and mop", carpet: true });
  assert.ok(state.waterLevelOptions().map((o) => o.value).includes("Off"));
});
