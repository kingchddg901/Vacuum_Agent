// Unit tests for the standalone cards' chip row — specifically WHICH chip renders
// as selected. The standalone room card and dashboard card share chipRow(); the
// panel has its own renderer with its own canonicalizer on the state proto, which
// the cards cannot reach. That gap is why these two were the copies left behind
// when the panel was converted for issue #48.
//
// Coverage targets (src/cards/_shared.js):
//   CHIP-1 clean_mode matches across display-label vs token spellings
//   CHIP-2 a DIFFERENT mode still does not match (the fold is not a wildcard)
//   CHIP-3 non-mode fields keep plain case-insensitive identity (brand vocabulary
//          is not core's to canonicalize)
// Run: node --test src/cards/shared-chips.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { chipRow, canonicalCleanMode } from "./_shared.js";

const MODE_OPTIONS = [
  { value: "vacuum",     label: "Vacuum" },
  { value: "mop",        label: "Mop" },
  { value: "vacuum_mop", label: "Vacuum and mop" },
];

const tVocab = (_field, _value, label) => label;

/** The option values whose rendered chip carries the `active` class. */
function activeValues(fieldKey, options, currentVal) {
  const html = chipRow("L", fieldKey, options, currentVal, tVocab);
  return options
    .filter((opt) => {
      const marker = `data-value="${opt.value}"`;
      const idx = html.indexOf(marker);
      if (idx === -1) return false;
      // The class attribute precedes data-value on the same button.
      return html.lastIndexOf("chip active", idx) > html.lastIndexOf("<button", idx);
    })
    .map((opt) => opt.value);
}

test("[CHIP-1] the stored DISPLAY label selects the token option", () => {
  // ISSUE #48. chipRow compared `currentVal.toLowerCase() === opt.value.toLowerCase()`
  // for every field. The room switch attribute holds what the editor saved — the
  // display label "Vacuum and mop" — while the option value is the adapter token
  // "vacuum_mop", so ALL THREE chips rendered inactive and a correctly configured
  // room read as having no cleaning mode selected.
  //
  // The card contradicted itself while doing it: isMopMode two lines up uses a
  // substring fold and returned true, so the Water Level and Edge Mopping rows
  // rendered normally beside a mode row with nothing chosen.
  for (const stored of ["vacuum_mop", "Vacuum and mop", "vacuum & mop", "VACUUM_MOP"]) {
    assert.deepEqual(
      activeValues("clean_mode", MODE_OPTIONS, stored),
      ["vacuum_mop"],
      `stored ${stored!== undefined ? JSON.stringify(stored) : stored} should select vacuum_mop`,
    );
  }
});

test("[CHIP-2] a different mode does not match — the fold is not a wildcard", () => {
  // The guard against fixing CHIP-1 with something that matches everything, which
  // would light every chip and be a worse lie than lighting none.
  assert.deepEqual(activeValues("clean_mode", MODE_OPTIONS, "Vacuum"), ["vacuum"]);
  assert.deepEqual(activeValues("clean_mode", MODE_OPTIONS, "Mop"), ["mop"]);
  // Unknown brand mode: nothing selected is the honest answer.
  assert.deepEqual(activeValues("clean_mode", MODE_OPTIONS, "Sweep"), []);
});

test("[CHIP-3] non-mode fields keep plain case-insensitive identity", () => {
  // fan_speed is a BRAND's word. Core has no canonical form for it, so the fold is
  // scoped to clean_mode — canonicalizing every field would impose a framework
  // opinion on vocabulary the adapter owns.
  const fanOptions = [{ value: "Max", label: "Max" }, { value: "Standard", label: "Standard" }];
  assert.deepEqual(activeValues("fan_speed", fanOptions, "max"), ["Max"]);
  assert.deepEqual(activeValues("fan_speed", fanOptions, "Turbo"), []);
});

test("[CHIP-4] canonicalCleanMode mirrors the backend owner's alias table", () => {
  // profiles/room_profiles.py::canonical_clean_mode is the other half. The two are
  // different languages and cannot share code, so they are pinned to each other
  // here: if an alias is added to one, add it to the other.
  for (const spelling of [
    "vacuum and mop", "vacuum & mop", "vacuum+mop", "vac & mop", "vacmop",
    "Vacuum and mop", "VACUUM_MOP",
  ]) {
    assert.equal(canonicalCleanMode(spelling), "vacuum_mop", spelling);
  }
  // Unknown values pass through lowercased so a brand mode survives.
  assert.equal(canonicalCleanMode("Sweep"), "sweep");
  assert.equal(canonicalCleanMode(""), "");
  assert.equal(canonicalCleanMode(null), "");
});
