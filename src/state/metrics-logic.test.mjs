// Unit tests for pure logic in the Metrics-view card state mixin (applyMetricsState).
// Coverage targets:
//   [MET-*] findMetricsSaveCandidate — pick the profile row that a Save button acts on:
//     source "found" -> found_profiles, anything else -> room_profiles; match on BOTH
//     profile_key AND room_slug; null on empty key or no match. Guards the documented
//     footgun where two rooms share a profile_key (must not save the wrong room's row).
// Run: node --test src/state/metrics-logic.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyMetricsState } from "./metrics.js";

function makeState(snapshot) {
  const proto = {};
  applyMetricsState(proto);
  const card = Object.create(proto);
  // The real methods findMetricsSaveCandidate delegates to (metricsFoundProfiles /
  // metricsRoomProfiles) both read metricsSnapshot(); drive them via setMetricsSnapshot
  // so we exercise the REAL list-getters, not stubs.
  if (snapshot !== undefined) card.setMetricsSnapshot(snapshot);
  return card;
}

// A representative snapshot: same profile_key ("quick") appears in two rooms in each list,
// and the two lists differ so we can prove source-routing picks the right one.
function snap() {
  return {
    found_profiles: [
      { profile_key: "quick", room_slug: "kitchen", tag: "F-kitchen-quick" },
      { profile_key: "quick", room_slug: "den", tag: "F-den-quick" },
      { profile_key: "deep", room_slug: "kitchen", tag: "F-kitchen-deep" },
    ],
    room_profiles: [
      { profile_key: "quick", room_slug: "kitchen", tag: "R-kitchen-quick" },
      { profile_key: "quick", room_slug: "den", tag: "R-den-quick" },
      { profile_key: "deep", room_slug: "den", tag: "R-den-deep" },
    ],
  };
}

test("[MET-1] source 'found' reads found_profiles; matches on BOTH key AND slug", () => {
  const s = makeState(snap());
  assert.equal(s.findMetricsSaveCandidate("found", "quick", "kitchen").tag, "F-kitchen-quick");
  assert.equal(s.findMetricsSaveCandidate("found", "quick", "den").tag, "F-den-quick");
  assert.equal(s.findMetricsSaveCandidate("found", "deep", "kitchen").tag, "F-kitchen-deep");
});

test("[MET-2] any non-'found' source reads room_profiles (default branch)", () => {
  const s = makeState(snap());
  // explicit "room"
  assert.equal(s.findMetricsSaveCandidate("room", "quick", "kitchen").tag, "R-kitchen-quick");
  // unrecognized source string still falls to the room_profiles branch (only "found" diverges)
  assert.equal(s.findMetricsSaveCandidate("profile", "deep", "den").tag, "R-den-deep");
  assert.equal(s.findMetricsSaveCandidate("", "quick", "den").tag, "R-den-quick");
});

test("[MET-3] key+slug BOTH must match — the shared-key footgun the code defends against", () => {
  const s = makeState(snap());
  // "quick" exists for kitchen AND den; asking for den must NOT return kitchen's row.
  const r = s.findMetricsSaveCandidate("found", "quick", "den");
  assert.equal(r.room_slug, "den");
  assert.equal(r.tag, "F-den-quick");
  // right key, wrong slug (no such combo in the list) -> null, not a lax key-only match.
  assert.equal(s.findMetricsSaveCandidate("found", "quick", "bedroom"), null);
  // right slug, wrong key -> null.
  assert.equal(s.findMetricsSaveCandidate("found", "nope", "kitchen"), null);
});

test("[MET-4] empty / null profileKey short-circuits to null (never scans)", () => {
  const s = makeState(snap());
  assert.equal(s.findMetricsSaveCandidate("found", "", "kitchen"), null);
  assert.equal(s.findMetricsSaveCandidate("room", null, "kitchen"), null);
  assert.equal(s.findMetricsSaveCandidate("found", undefined, "kitchen"), null);
});

test("[MET-5] roomSlug defaults to '' — matches a row whose room_slug is empty/absent", () => {
  const s = makeState({
    room_profiles: [
      { profile_key: "global", room_slug: "" },        // empty slug
      { profile_key: "global2" },                        // absent slug -> coerced to ""
      { profile_key: "global", room_slug: "kitchen" },
    ],
  });
  // roomSlug omitted -> defaults to "" -> matches the empty-slug row, not the kitchen one.
  assert.equal(s.findMetricsSaveCandidate("room", "global").room_slug, "");
  // absent room_slug on the row is coerced to "" and matches the "" default too.
  assert.equal(s.findMetricsSaveCandidate("room", "global2").profile_key, "global2");
});

test("[MET-6] no snapshot -> lists are [] -> null (never throws)", () => {
  const s = makeState();               // no snapshot set at all
  assert.equal(s.findMetricsSaveCandidate("found", "quick", "kitchen"), null);
  assert.equal(s.findMetricsSaveCandidate("room", "quick", "kitchen"), null);
});

test("[MET-7] wrong-list isolation: a match only in the OTHER list still yields null", () => {
  // "deep"/"kitchen" is only in found_profiles; "deep"/"den" only in room_profiles.
  const s = makeState(snap());
  // found source, ask for the room-only combo -> null (doesn't cross lists)
  assert.equal(s.findMetricsSaveCandidate("found", "deep", "den"), null);
  // room source, ask for the found-only combo -> null
  assert.equal(s.findMetricsSaveCandidate("room", "deep", "kitchen"), null);
});

test("[MET-8] first matching row wins when duplicates share key+slug (find semantics)", () => {
  const s = makeState({
    found_profiles: [
      { profile_key: "dup", room_slug: "hall", tag: "first" },
      { profile_key: "dup", room_slug: "hall", tag: "second" },
    ],
  });
  assert.equal(s.findMetricsSaveCandidate("found", "dup", "hall").tag, "first");
});

test("[MET-9] numeric room_slug on the row is string-coerced before compare", () => {
  const s = makeState({
    room_profiles: [{ profile_key: "k", room_slug: 3, tag: "num-slug" }],
  });
  // caller passes the string "3"; row holds number 3 -> String() on both sides matches.
  assert.equal(s.findMetricsSaveCandidate("room", "k", "3").tag, "num-slug");
  // and a genuinely different slug still misses.
  assert.equal(s.findMetricsSaveCandidate("room", "k", "4"), null);
});
