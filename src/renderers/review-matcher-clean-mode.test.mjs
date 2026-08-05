// Run: node --test src/renderers/review-matcher-clean-mode.test.mjs
//
// CC-5 — the review profile-matcher's clean-mode chip row compared a
// DISPLAY-canonicalised value against the raw option token.
// setReviewProfileMatcherField stores _canonicalCleanModeDisplay(value)
// ("Vacuum and mop"); the option carries the adapter's declared token
// ("vacuum_mop"). String equality between those is never true, so the chip the
// user had just clicked rendered INACTIVE while the matcher was in fact
// filtering on it.
//
// Same display-label-vs-canonical-token split as GitHub issue #48.
//
// Coverage (RMC = Review Matcher Clean mode):
//   [RMC-1] the exact live pairing matches (the bug)
//   [RMC-2] every spelling of the mop mode agrees with every other
//   [RMC-3] genuinely different modes still do NOT match
//   [RMC-4] non-clean_mode fields keep plain string equality
//   [RMC-5] the comparator survives a missing card/state (raw fallback)

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyRoomEditorState } from "../state/room-editor.js";

function stateWithComparator() {
  const proto = {};
  applyRoomEditorState(proto);
  return Object.create(proto);
}

/** The comparator, transcribed from renderers/review.js. */
function matcherFor(key, card) {
  const canonical = key === "clean_mode"
    ? (value) =>
        card?._state?._canonicalCleanModeCompare?.(value) ??
        String(value ?? "").trim().toLowerCase().replace(/[\s+_-]+/g, "")
    : (value) => String(value ?? "");
  return (a, b) => canonical(a) === canonical(b);
}

const CARD = { _state: stateWithComparator() };

test("[RMC-1] the live pairing that never matched now matches", () => {
  const matches = matcherFor("clean_mode", CARD);
  // option.value from the adapter vs the display form the store writes.
  assert.equal("vacuum_mop" === "Vacuum and mop", false, "premise: raw equality fails");
  assert.equal(matches("vacuum_mop", "Vacuum and mop"), true);
});

test("[RMC-2] every spelling of the mop mode agrees", () => {
  const matches = matcherFor("clean_mode", CARD);
  const spellings = ["vacuum_mop", "vacuum mop", "Vacuum and mop", "vacuum_and_mop", "VACUUM-MOP"];
  for (const a of spellings) {
    for (const b of spellings) {
      assert.equal(matches(a, b), true, `${a} !== ${b}`);
    }
  }
});

test("[RMC-3] genuinely different modes still do not match", () => {
  const matches = matcherFor("clean_mode", CARD);
  assert.equal(matches("vacuum", "Vacuum and mop"), false, "vacuum-only matched the mop mode");
  assert.equal(matches("mop", "vacuum_mop"), false, "mop-only matched vacuum+mop");
  assert.equal(matches("vacuum", "mop"), false);
});

test("[RMC-4] other fields keep plain string equality", () => {
  const matches = matcherFor("fan_speed", CARD);
  assert.equal(matches("max", "max"), true);
  // No canonicalisation is applied, so these stay distinct — clean_mode is the
  // only field with the two-vocabulary problem, and widening it silently would
  // make unrelated values collide.
  assert.equal(matches("Max", "max"), false);
});

test("[RMC-5] a missing card/state still compares sensibly", () => {
  const matches = matcherFor("clean_mode", undefined);
  assert.equal(matches("vacuum_mop", "Vacuum and mop"), false,
    "the fallback cannot know the alias table…");
  assert.equal(matches("vacuum_mop", "vacuum mop"), true,
    "…but must still absorb separator/case spelling");
});
