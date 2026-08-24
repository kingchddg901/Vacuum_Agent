// Unit tests for the Review tab's PROFILE MATCHER — the surface that turns a
// settings tuple into the profiles that match it.
//
// This exists because the matcher was silently non-functional and no test could see
// it. Two independent defects, found 2026-08-24:
//
//   1. BACKEND. `sensor/profile.py` omitted `catalog=`, so `available_profiles`
//      published `profiles: {}` on every vacuum from 2026-08-07. SAVED profiles
//      therefore had no `definition` to match against. (Pinned python-side by
//      [SE-13].)
//   2. HERE. `reviewProfileMatcherCatalog` merged learning-DISCOVERED profiles into
//      the catalog and then set `definition: null` on every one of them, while
//      `reviewProfileMatcherMatches` drops any entry without a definition. So the
//      discovered half — the whole point of the surface, per its author: "that is
//      where i built the suggestion for new profiles to be surfaced over time, runs
//      you do often but are not default" — could never match. Both the nulling and
//      the filter are present at eae291fa (2026-04-30); the project has 57 pre-git
//      days, so the honest statement is "not present at eae291fa".
//
// Coverage targets (src/state/review.js):
//   PM-1  a DISCOVERED profile matches on its own settings axes
//   PM-2  a SAVED profile still matches (the sensor half)
//   PM-3  a saved definition WINS over a discovered one for the same key
//   PM-4  a non-matching tuple matches nothing (the filter still filters)
//   PM-5  an empty sensor payload does not empty the matcher — the backend
//         regression must not be able to kill the discovered half again
// Run: node --test src/state/review-profile-matcher.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyReviewState } from "./review.js";
import { applyRoomEditorState } from "./room-editor.js";

const TUPLE = Object.freeze({
  clean_mode: "Vacuum",
  fan_speed: "Max",
  water_level: null,
  clean_intensity: "Deep",
  clean_passes: 1,
  edge_mopping: false,
});

// A learning-snapshot filter option, in the shape learningHistoryProfiles reads.
function discovered(key, over = {}) {
  return {
    value: key,
    label: key,
    clean_mode: "Vacuum",
    fan_speed: "Max",
    water_level: null,
    clean_intensity: "Deep",
    clean_passes: 1,
    edge_mopping: false,
    ...over,
  };
}

function makeCard({ sensorProfiles = {}, foundOptions = [], fields = TUPLE } = {}) {
  const proto = {};
  applyRoomEditorState(proto);   // supplies _editorFieldsMatchProfile + comparables
  applyReviewState(proto);
  const card = Object.create(proto);

  card.vacuumEntityId = () => "vacuum.alfred";
  card.attrsOf = () => ({ profiles: sensorProfiles, profile_labels: {} });
  card.learningHistorySnapshot = () => ({ filter_options: { profiles: foundOptions } });
  // room-editor collaborators the comparable-field builder reaches for
  card.isEditorRoomCarpet = () => false;
  card.reviewProfileMatcherFields = () => fields;
  return card;
}

/* =========================================================
   PM-1 — the discovered half, which is the reason the surface exists
   ========================================================= */

test("[PM-1] a DISCOVERED profile matches on its own settings axes", () => {
  // RED BEFORE THE FIX: definition was null, so the filter dropped it.
  const card = makeCard({ foundOptions: [discovered("often_run")] });

  const matches = card.reviewProfileMatcherMatches();

  assert.equal(matches.length, 1, "a discovered profile did not survive to match");
  assert.equal(matches[0].profile_key, "often_run");
  assert.equal(matches[0].discovered, true, "the discovered flag is how a caller tells it from a saved one");
});

test("[PM-5] an EMPTY sensor payload does not empty the matcher", () => {
  // This is the backend regression's shape. Before the card fix, an empty sensor
  // dict meant zero matches no matter what learning had found -- the two defects
  // compounded. Discovered profiles must stand on their own.
  const card = makeCard({ sensorProfiles: {}, foundOptions: [discovered("solo")] });

  assert.equal(card.reviewProfileMatcherMatches().length, 1);
});

/* =========================================================
   PM-2 / PM-3 — the saved half, and precedence between the two
   ========================================================= */

test("[PM-2] a SAVED profile from the sensor still matches", () => {
  const card = makeCard({
    sensorProfiles: {
      vacuum_deep: {
        label: "Deep Vacuum", clean_mode: "Vacuum", fan_speed: "Max",
        water_level: null, clean_intensity: "Deep", clean_passes: 1,
        edge_mopping: false,
      },
    },
  });

  const matches = card.reviewProfileMatcherMatches();

  assert.equal(matches.length, 1);
  assert.equal(matches[0].profile_key, "vacuum_deep");
  assert.notEqual(matches[0].discovered, true, "a sensor profile is not a suggestion");
});

test("[PM-3] a SAVED definition wins over a discovered one for the same key", () => {
  // The saved profile is the authority: it is what the user actually stored. A
  // discovered entry inferred from run history must not shadow it, or a renamed or
  // re-tuned saved profile would silently keep matching its old settings.
  const card = makeCard({
    sensorProfiles: {
      shared_key: {
        label: "Saved", clean_mode: "Vacuum", fan_speed: "Max",
        water_level: null, clean_intensity: "Deep", clean_passes: 1,
        edge_mopping: false,
      },
    },
    foundOptions: [discovered("shared_key", { fan_speed: "Quiet" })],
  });

  const matches = card.reviewProfileMatcherMatches();

  assert.equal(matches.length, 1);
  assert.notEqual(matches[0].discovered, true,
    "the discovered entry overwrote the saved definition");
});

/* =========================================================
   PM-4 — the filter must still filter
   ========================================================= */

test("[PM-4] a tuple that matches nothing returns nothing", () => {
  // Without this, "give every discovered entry a definition" could degrade into
  // "everything matches", which looks like a working matcher and is useless.
  const card = makeCard({
    foundOptions: [discovered("quiet_run", { fan_speed: "Quiet" })],
    fields: { ...TUPLE, fan_speed: "Max" },
  });

  assert.equal(card.reviewProfileMatcherMatches().length, 0);
});

test("[PM-4] a discovered entry with no settings at all cannot match", () => {
  // filter_options can carry a bare {value,label} row. Building a definition out of
  // six nulls must not accidentally equal a real tuple.
  const card = makeCard({ foundOptions: [{ value: "bare", label: "bare" }] });

  assert.equal(card.reviewProfileMatcherMatches().length, 0);
});
