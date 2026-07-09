// Unit tests for the room-editor mixin's pure snap-back-to-preset logic + the
// adapter-driven option-list builder. The editor should NOT stay "custom" when
// the 6 comparable fields land exactly on a known preset (via the vocab bridges
// that collapse vacuum_mop spellings and map profile Quick/Deep <-> editor
// Quick/Narrow); an adapter that declares no options for a role hides the picker.
//
// Coverage targets (src/state/room-editor.js):
//   RE  matchingEditorProfileName / _editorFieldsMatchProfile / _buildComparableProfileFields
//       -> 6-field preset match: snap-back vs stay-custom, carpet-masked mop fields
//   ORD _buildOptionListForRole -> empty adapter -> [] (hide), dedupe by lc value, append current
//   THM _canonicalCleanModeCompare / _canonicalCleanModeDisplay / isMopMode
//       -> collapse vacuum_mop / "Vacuum and mop" / vacuum / mop
//   RAC isEditorRoomCarpet -> carpet===true, else floorType carpet / carpet_* / carpet-*
//   INT _profileIntensityToEditorIntensity / _editorIntensityToComparableProfileIntensity
//       -> Quick/Deep <-> Quick/Narrow, Normal is custom-only
// Run: node --test src/state/room-editor-matching.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyRoomEditorState } from "./room-editor.js";

function makeCard(over = {}) {
  const proto = {};
  applyRoomEditorState(proto);
  const card = Object.create(proto);
  // Sensible defaults; individual tests override the pieces they exercise.
  card._activeRoom = null;
  card.activeEditorRoom = () => card._activeRoom;
  card._fields = null;
  card.editorFields = () => card._fields;
  card._adapterOptions = {};
  card.adapterOptionsFor = (role) => card._adapterOptions[role] ?? [];
  card._profiles = {};
  card.availableEditorProfiles = () => card._profiles;
  Object.assign(card, over);
  return card;
}

/* =========================================================
   THM — clean-mode canonicalization + isMopMode
   ========================================================= */

test("[THM-1] _canonicalCleanModeDisplay collapses every vacuum+mop spelling to one label", () => {
  const c = makeCard();
  for (const raw of ["vacuum_mop", "vacuum mop", "Vacuum and mop", "VACUUM+MOP", "vacuum-and-mop", "  vacuum   mop  "]) {
    assert.equal(c._canonicalCleanModeDisplay(raw), "Vacuum and mop", `display(${raw})`);
  }
  assert.equal(c._canonicalCleanModeDisplay("VACUUM"), "Vacuum");
  assert.equal(c._canonicalCleanModeDisplay("mop"), "Mop");
  // Unknown modes pass through trimmed but with original casing (not lowered).
  assert.equal(c._canonicalCleanModeDisplay("  SmartRun  "), "SmartRun");
  // Nullish -> "" (raw of null/undefined trims to empty and is not a known mode).
  assert.equal(c._canonicalCleanModeDisplay(null), "");
  assert.equal(c._canonicalCleanModeDisplay(undefined), "");
});

test("[THM-2] _canonicalCleanModeCompare folds all vacuum+mop spellings to vacuum_mop", () => {
  const c = makeCard();
  for (const raw of ["vacuum_mop", "Vacuum and mop", "VACUUM+MOP", "vacuum  mop"]) {
    assert.equal(c._canonicalCleanModeCompare(raw), "vacuum_mop", `compare(${raw})`);
  }
  assert.equal(c._canonicalCleanModeCompare("Vacuum"), "vacuum");
  assert.equal(c._canonicalCleanModeCompare("MOP"), "mop");
  // Unknown -> stripped + lowered (separators removed), so display/compare disagree by design.
  assert.equal(c._canonicalCleanModeCompare("Auto Clean"), "autoclean");
  assert.equal(c._canonicalCleanModeCompare(null), "");
});

test("[THM-3] isMopMode true for mop + vacuum_mop + wash, false for vacuum-only", () => {
  const c = makeCard();
  assert.equal(c.isMopMode("Vacuum and mop"), true);   // -> vacuum_mop, includes "mop"
  assert.equal(c.isMopMode("mop"), true);
  assert.equal(c.isMopMode("Mop only"), true);          // -> "moponly", includes "mop"
  assert.equal(c.isMopMode("wash"), true);              // includes "wash"
  assert.equal(c.isMopMode("Vacuum"), false);
  assert.equal(c.isMopMode(""), false);
  assert.equal(c.isMopMode(null), false);
});

/* =========================================================
   INT — profile <-> editor intensity vocabulary bridge
   ========================================================= */

test("[INT-1] _profileIntensityToEditorIntensity: Quick->Quick, Deep->Narrow, Normal stays custom-only", () => {
  const c = makeCard();
  assert.equal(c._profileIntensityToEditorIntensity("Quick"), "Quick");
  assert.equal(c._profileIntensityToEditorIntensity("quick"), "Quick");
  assert.equal(c._profileIntensityToEditorIntensity("DEEP"), "Narrow");
  // "Normal" is manual-only: no preset maps to it, so it passes through unchanged.
  assert.equal(c._profileIntensityToEditorIntensity("Normal"), "Normal");
  // Nullish -> null (value ?? null).
  assert.equal(c._profileIntensityToEditorIntensity(null), null);
  assert.equal(c._profileIntensityToEditorIntensity(undefined), null);
});

test("[INT-2] _editorIntensityToComparableProfileIntensity inverts the bridge (Narrow->deep)", () => {
  const c = makeCard();
  assert.equal(c._editorIntensityToComparableProfileIntensity("Quick"), "quick");
  assert.equal(c._editorIntensityToComparableProfileIntensity("Narrow"), "deep");
  // Round-trip: profile Deep -> editor Narrow -> comparable deep.
  const editor = c._profileIntensityToEditorIntensity("Deep");
  assert.equal(c._editorIntensityToComparableProfileIntensity(editor), "deep");
  // Normal has no preset counterpart -> just lowered.
  assert.equal(c._editorIntensityToComparableProfileIntensity("Normal"), "normal");
  assert.equal(c._editorIntensityToComparableProfileIntensity(null), "");
});

/* =========================================================
   RAC — carpet detection precedence
   ========================================================= */

test("[RAC-1] isEditorRoomCarpet: pre-computed boolean wins over floorType", () => {
  const c = makeCard();
  c._activeRoom = { carpet: true, floorType: "hardwood" };   // boolean beats the string
  assert.equal(c.isEditorRoomCarpet(), true);
  // No active room -> false (guarded).
  c._activeRoom = null;
  assert.equal(c.isEditorRoomCarpet(), false);
});

test("[RAC-2] isEditorRoomCarpet: floorType 'carpet' + every pile variant prefix matches", () => {
  const c = makeCard();
  const carpetLike = ["carpet", "CARPET", "carpet_low", "carpet_high_pile", "carpet-low", "Carpet-High"];
  for (const ft of carpetLike) {
    c._activeRoom = { carpet: false, floorType: ft };
    assert.equal(c.isEditorRoomCarpet(), true, `floorType=${ft}`);
  }
  // Non-carpet floors -> false. "carpetish" is the key trap: it CONTAINS "carpet"
  // but is not "carpet" and has no "carpet_"/"carpet-" separator, so it must NOT match.
  for (const ft of ["hardwood", "tile", "", "not_carpet", "carpetish", "carpeting"]) {
    c._activeRoom = { carpet: false, floorType: ft };
    assert.equal(c.isEditorRoomCarpet(), false, `floorType=${ft}`);
  }
});

/* =========================================================
   RE — _buildComparableProfileFields + preset matching
   ========================================================= */

// A canonical vacuum_quick preset (profile vocabulary).
const VACUUM_QUICK = {
  clean_mode: "vacuum", fan_speed: "Standard", water_level: null,
  clean_intensity: "Quick", clean_passes: 1, edge_mopping: false,
};
// A mopping preset that exercises the mop-only fields.
const MOP_DEEP = {
  clean_mode: "vacuum_mop", fan_speed: "Max", water_level: "High",
  clean_intensity: "Deep", clean_passes: 2, edge_mopping: true,
};

test("[RE-1] _buildComparableProfileFields translates a mop preset through the vocab bridges", () => {
  const c = makeCard();
  c._activeRoom = { carpet: false, floorType: "tile" };   // not carpet -> mop fields live
  const cmp = c._buildComparableProfileFields(MOP_DEEP);
  assert.deepEqual(cmp, {
    clean_mode: "Vacuum and mop",   // display-canonicalized
    fan_speed: "Max",
    water_level: "High",            // kept because mopActive
    clean_intensity: "Narrow",      // Deep -> Narrow
    clean_passes: 2,                // Number()-coerced
    edge_mopping: true,
  });
});

test("[RE-2] _buildComparableProfileFields masks water_level + edge_mopping on a carpet room", () => {
  const c = makeCard();
  c._activeRoom = { carpet: true, floorType: "carpet" };   // carpet -> mop fields forced off
  const cmp = c._buildComparableProfileFields(MOP_DEEP);
  assert.equal(cmp.water_level, null);
  assert.equal(cmp.edge_mopping, false);
  // clean_mode label itself is NOT downgraded, only the water/edge fields.
  assert.equal(cmp.clean_mode, "Vacuum and mop");
});

test("[RE-3] _buildComparableProfileFields defaults: missing clean_mode->Vacuum, passes->1", () => {
  const c = makeCard();
  c._activeRoom = { carpet: false, floorType: "tile" };
  const cmp = c._buildComparableProfileFields({});   // empty profile
  assert.equal(cmp.clean_mode, "Vacuum");            // ?? "vacuum" -> display "Vacuum"
  assert.equal(cmp.clean_passes, 1);                 // Number(?? 1)
  assert.equal(cmp.fan_speed, null);
  assert.equal(cmp.clean_intensity, null);           // profile intensity null -> editor null
  // Vacuum-only -> mop fields off even off-carpet.
  assert.equal(cmp.water_level, null);
  assert.equal(cmp.edge_mopping, false);
});

test("[RE-4] _editorFieldsMatchProfile: exact 6-field match returns true, one diverging field false", () => {
  const c = makeCard();
  c._activeRoom = { carpet: false, floorType: "tile" };
  // Editor fields exactly equal to the comparable form of MOP_DEEP.
  const matching = {
    clean_mode: "Vacuum and mop", fan_speed: "Max", water_level: "High",
    clean_intensity: "Narrow", clean_passes: 2, edge_mopping: true,
  };
  assert.equal(c._editorFieldsMatchProfile(matching, MOP_DEEP), true);
  // Flip a single field -> no longer a match.
  assert.equal(c._editorFieldsMatchProfile({ ...matching, fan_speed: "Standard" }, MOP_DEEP), false);
  assert.equal(c._editorFieldsMatchProfile({ ...matching, clean_intensity: "Quick" }, MOP_DEEP), false);
  // Null guards.
  assert.equal(c._editorFieldsMatchProfile(null, MOP_DEEP), false);
  assert.equal(c._editorFieldsMatchProfile(matching, null), false);
});

test("[RE-5] _editorFieldsMatchProfile normalizes spelling + numeric-string across the seam", () => {
  const c = makeCard();
  c._activeRoom = { carpet: false, floorType: "tile" };
  // A field carrying the raw "vacuum_mop" and a string "2" still matches the display/Number form.
  const fields = {
    clean_mode: "vacuum_mop",        // compare-normalizes to same bucket as "Vacuum and mop"
    fan_speed: "Max", water_level: "High",
    clean_intensity: "narrow",       // case-insensitive -> deep
    clean_passes: "2",               // numeric string -> 2
    edge_mopping: "true",            // string "true" -> boolean true
  };
  assert.equal(c._editorFieldsMatchProfile(fields, MOP_DEEP), true);
});

test("[RE-6] matchingEditorProfileName: snaps back to the matching preset, else null (custom)", () => {
  const c = makeCard();
  c._activeRoom = { carpet: false, floorType: "tile" };
  c._profiles = { vacuum_quick: VACUUM_QUICK, mop_deep: MOP_DEEP };
  // Fields landing exactly on vacuum_quick -> that name (snap-back).
  const quickFields = {
    clean_mode: "Vacuum", fan_speed: "Standard", water_level: null,
    clean_intensity: "Quick", clean_passes: 1, edge_mopping: false,
  };
  assert.equal(c.matchingEditorProfileName(quickFields), "vacuum_quick");
  // Fields on mop_deep -> that name.
  const deepFields = {
    clean_mode: "Vacuum and mop", fan_speed: "Max", water_level: "High",
    clean_intensity: "Narrow", clean_passes: 2, edge_mopping: true,
  };
  assert.equal(c.matchingEditorProfileName(deepFields), "mop_deep");
  // A divergent value (Normal intensity is preset-less) -> stay custom (null).
  assert.equal(c.matchingEditorProfileName({ ...quickFields, clean_intensity: "Normal" }), null);
});

test("[RE-7] matchingEditorProfileName falls back to editorFields() when no arg + null when none set", () => {
  const c = makeCard();
  c._activeRoom = { carpet: false, floorType: "tile" };
  c._profiles = { vacuum_quick: VACUUM_QUICK };
  c._fields = {
    clean_mode: "Vacuum", fan_speed: "Standard", water_level: null,
    clean_intensity: "Quick", clean_passes: 1, edge_mopping: false,
  };
  assert.equal(c.matchingEditorProfileName(), "vacuum_quick");   // pulled from editorFields()
  // No fields at all -> null (guarded before iterating profiles).
  c._fields = null;
  assert.equal(c.matchingEditorProfileName(), null);
});

test("[RE-8] carpet room snaps a mop preset back via the carpet-masked comparable, not the raw preset", () => {
  const c = makeCard();
  c._activeRoom = { carpet: true, floorType: "carpet_low_pile" };
  c._profiles = { mop_deep: MOP_DEEP };
  // On carpet the comparable drops water_level/edge_mopping, so the editor fields that
  // ALSO have them masked (as the carpet UX forces) still match the preset.
  const carpetMaskedFields = {
    clean_mode: "Vacuum and mop", fan_speed: "Max",
    water_level: null, clean_intensity: "Narrow",
    clean_passes: 2, edge_mopping: false,
  };
  assert.equal(c.matchingEditorProfileName(carpetMaskedFields), "mop_deep");
  // The un-masked (off-carpet) field set would NOT match here, since carpet masks the comparable.
  const unmasked = { ...carpetMaskedFields, water_level: "High", edge_mopping: true };
  assert.equal(c.matchingEditorProfileName(unmasked), null);
});

/* =========================================================
   ORD — _buildOptionListForRole
   ========================================================= */

test("[ORD-1] empty adapter options -> [] so the row is hidden (no legacy resurrection)", () => {
  const c = makeCard();
  c._adapterOptions = { clean_mode: [] };
  // Even with a saved current value, an empty adapter list stays empty (hide-the-picker contract).
  c._fields = { clean_mode: "Vacuum" };
  assert.deepEqual(c._buildOptionListForRole("clean_mode", "clean_mode"), []);
  // Unknown role (adapterOptionsFor -> []) also hides.
  assert.deepEqual(c._buildOptionListForRole("nope", "nope"), []);
});

test("[ORD-2] dedupes adapter options by lowercase value, keeping first label + skipping blanks", () => {
  const c = makeCard();
  c._adapterOptions = {
    fan_speed: [
      { value: "Standard", label: "Standard" },
      { value: "standard", label: "DUPLICATE" },   // same lc value -> dropped
      { value: "  ", label: "blank" },              // blank value -> skipped
      { value: "Max", label: "Max Power" },
    ],
  };
  c._fields = { fan_speed: "Max" };   // current already present -> not re-appended
  const out = c._buildOptionListForRole("fan_speed", "fan_speed");
  assert.deepEqual(out, [
    { value: "Standard", label: "Standard" },
    { value: "Max", label: "Max Power" },
  ]);
});

test("[ORD-3] appends the CURRENT room's saved value as a legacy fallback when the adapter omits it", () => {
  const c = makeCard();
  c._adapterOptions = { fan_speed: [{ value: "gentle", label: "Gentle" }, { value: "turbo", label: "Turbo" }] };
  c._fields = { fan_speed: "Standard" };   // not in the adapter list -> appended value-as-label
  const out = c._buildOptionListForRole("fan_speed", "fan_speed");
  assert.deepEqual(out[out.length - 1], { value: "Standard", label: "Standard" });
  assert.equal(out.length, 3);
  // A current value that IS already declared (case-insensitively) is NOT duplicated.
  c._fields = { fan_speed: "TURBO" };
  const out2 = c._buildOptionListForRole("fan_speed", "fan_speed");
  assert.equal(out2.length, 2);
  // Missing/blank current value -> nothing appended.
  c._fields = { fan_speed: "" };
  assert.equal(c._buildOptionListForRole("fan_speed", "fan_speed").length, 2);
  c._fields = null;
  assert.equal(c._buildOptionListForRole("fan_speed", "fan_speed").length, 2);
});

test("[ORD-4] label defaults to value when the adapter option omits a label", () => {
  const c = makeCard();
  c._adapterOptions = { clean_intensity: [{ value: "Quick" }, { value: "Narrow", label: null }] };
  c._fields = {};
  const out = c._buildOptionListForRole("clean_intensity", "clean_intensity");
  assert.deepEqual(out, [
    { value: "Quick", label: "Quick" },
    { value: "Narrow", label: "Narrow" },   // null label -> String(value)
  ]);
});

/* =========================================================
   SMOP — settable-mop gating: observe-only tank (Roborock S6) vs
   settable mop (Roborock S7+, supports_water_control) vs Eufy.
   ========================================================= */

function mopCard(snapshot, over = {}) {
  return makeCard({
    dashboardSnapshot: () => snapshot,
    isEditorRoomCarpet: () => false,
    waterLevelOptions: () => [{ value: "off" }, { value: "high" }],
    editorFields: () => ({ clean_mode: "vacuum" }),
    ...over,
  });
}

test("[SMOP-1] supportsSettableMop mirrors supports_water_control (default false)", () => {
  assert.equal(mopCard({ supports_water_control: true }).supportsSettableMop(), true);
  assert.equal(mopCard({ supports_water_control: false }).supportsSettableMop(), false);
  assert.equal(mopCard({}).supportsSettableMop(), false);
  assert.equal(makeCard({ dashboardSnapshot: () => null }).supportsSettableMop(), false);
});

test("[SMOP-2] observe-only mop (S6): water gated on the physical tank, not clean_mode", () => {
  // Tank attached, not settable, clean_mode vacuum -> water shows (the tank drives it).
  assert.equal(mopCard({ mop_active: true, supports_water_control: false }).showWaterLevel(), true);
  // Tank detached -> water hidden even though options exist.
  assert.equal(mopCard({ mop_active: false, supports_water_control: false }).showWaterLevel(), false);
});

test("[SMOP-3] settable mop (S7): water follows clean_mode, NOT the tank sensor", () => {
  // Tank attached but clean_mode vacuum -> water hidden (a dry pass), unlike observe-only.
  const vac = mopCard({ mop_active: true, supports_water_control: true },
    { editorFields: () => ({ clean_mode: "vacuum" }) });
  assert.equal(vac.showWaterLevel(), false);
  // clean_mode vacuum_mop -> water shown regardless of the tank flag.
  const mop = mopCard({ mop_active: true, supports_water_control: true },
    { editorFields: () => ({ clean_mode: "vacuum_mop" }) });
  assert.equal(mop.showWaterLevel(), true);
});
