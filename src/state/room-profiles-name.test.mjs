// Unit tests for the room-profile library pure logic in room-profiles.js.
// Coverage targets:
//   [RP-1..RP-6] makeRoomProfileName — label -> slug ("custom_<slug>" / "custom_profile"),
//                rename-to-self short-circuit, and the numeric _2/_3 collision suffix.
//   [RP-7..RP-9] roomProfilesList — protected-first, then case-insensitive localeCompare by label.
//   [RP-10]      customRoomProfiles — roomProfilesList() minus the protected names.
// Run: node --test src/state/room-profiles-name.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyRoomProfilesState } from "./room-profiles.js";

// A card stub carrying the real room-profiles mixin. `profiles` is a map of
// name -> profile object; `protectedNames` seeds the protected list. We drive the
// real state object so isProtectedRoomProfile / roomProfilesLibrary run for real.
function makeCard(profiles = {}, protectedNames = []) {
  const proto = {};
  applyRoomProfilesState(proto);
  const card = Object.create(proto);
  card._roomProfilesState = {
    profile_count: Object.keys(profiles).length,
    protected_profile_names: protectedNames.map((n) => String(n)),
    profiles,
  };
  return card;
}

// A normalized-ish profile record; only name + label are load-bearing for these targets.
const prof = (name, label = name) => ({ name, label });

// ---- makeRoomProfileName ---------------------------------------------------

test("[RP-1] makeRoomProfileName: slug lowercases, non-alnum -> _, trims + collapses", () => {
  const card = makeCard();
  // Mixed case + spaces + punctuation -> lowercased, runs of non-alnum collapse to one _.
  assert.equal(card.makeRoomProfileName("Kids' Room"), "custom_kids_room");
  assert.equal(card.makeRoomProfileName("Living   Room!!!"), "custom_living_room");
  // Leading/trailing non-alnum is stripped (no leading/trailing underscore in the slug).
  assert.equal(card.makeRoomProfileName("  --Attic--  "), "custom_attic");
  // Digits survive; a "/" between tokens is a single separator.
  assert.equal(card.makeRoomProfileName("Zone 3 / A"), "custom_zone_3_a");
});

test("[RP-2] makeRoomProfileName: empty / all-punctuation label -> 'custom_profile'", () => {
  const card = makeCard();
  assert.equal(card.makeRoomProfileName(""), "custom_profile");
  assert.equal(card.makeRoomProfileName("   "), "custom_profile");
  assert.equal(card.makeRoomProfileName("!!!"), "custom_profile"); // slug collapses to ""
  // null / undefined coerce to "" -> the empty-slug fallback.
  assert.equal(card.makeRoomProfileName(null), "custom_profile");
  assert.equal(card.makeRoomProfileName(undefined), "custom_profile");
});

test("[RP-3] makeRoomProfileName: free base name is returned as-is", () => {
  const card = makeCard({ custom_kitchen: prof("custom_kitchen") });
  // "office" doesn't collide with the one existing profile -> plain base name.
  assert.equal(card.makeRoomProfileName("Office"), "custom_office");
});

test("[RP-4] makeRoomProfileName: collision appends the first free numeric suffix (_2, _3...)", () => {
  const card = makeCard({
    custom_den: prof("custom_den"),
    custom_den_2: prof("custom_den_2"),
    // note: _3 is FREE, _4 is taken -> the walk must stop at _3, not skip to _5.
    custom_den_4: prof("custom_den_4"),
  });
  assert.equal(card.makeRoomProfileName("Den"), "custom_den_3");
});

test("[RP-5] makeRoomProfileName: walks contiguous suffixes until the first gap", () => {
  const card = makeCard({
    custom_den: prof("custom_den"),
    custom_den_2: prof("custom_den_2"),
    custom_den_3: prof("custom_den_3"),
  });
  // _2 and _3 taken, _4 is the first free slot.
  assert.equal(card.makeRoomProfileName("Den"), "custom_den_4");
});

test("[RP-6] makeRoomProfileName: rename-to-self keeps the current name (no _2 bump)", () => {
  const card = makeCard({ custom_den: prof("custom_den") });
  // Editing the existing 'custom_den' profile with a label that re-slugs to itself:
  // the current-name short-circuit returns it instead of colliding to custom_den_2.
  assert.equal(card.makeRoomProfileName("Den", "custom_den"), "custom_den");
  assert.equal(card.makeRoomProfileName("  Den  ", "  custom_den  "), "custom_den"); // both trimmed
  // But a DIFFERENT current name doesn't rescue a real collision -> suffix bump.
  assert.equal(card.makeRoomProfileName("Den", "custom_other"), "custom_den_2");
  // current === base but base is otherwise free is still fine (idempotent).
  const free = makeCard();
  assert.equal(free.makeRoomProfileName("Den", "custom_den"), "custom_den");
});

// ---- roomProfilesList ------------------------------------------------------

test("[RP-7] roomProfilesList: protected profiles sort ahead of custom ones", () => {
  const card = makeCard(
    {
      // library insertion order deliberately puts a custom profile first.
      custom_zebra: prof("custom_zebra", "Zebra"),
      vacuum: prof("vacuum", "Vacuum"),
      mop: prof("mop", "Mop"),
    },
    ["vacuum", "mop"] // protected
  );
  const names = card.roomProfilesList().map((p) => p.name);
  // Protected block first (Mop < Vacuum by label), then the custom Zebra.
  assert.deepEqual(names, ["mop", "vacuum", "custom_zebra"]);
});

test("[RP-8] roomProfilesList: within a protection tier, case-insensitive label localeCompare", () => {
  const card = makeCard(
    {
      a: prof("a", "banana"),
      b: prof("b", "Apple"),
      c: prof("c", "cherry"),
    },
    [] // none protected -> single tier, pure label sort
  );
  const labels = card.roomProfilesList().map((p) => p.label);
  // "Apple" beats "banana" despite the capital A (sensitivity: base).
  assert.deepEqual(labels, ["Apple", "banana", "cherry"]);
});

test("[RP-9] roomProfilesList: empty library -> empty array (no throw)", () => {
  const card = makeCard({}, ["vacuum"]);
  assert.deepEqual(card.roomProfilesList(), []);
});

// ---- customRoomProfiles ----------------------------------------------------

test("[RP-10] customRoomProfiles: sorted list minus the protected names", () => {
  const card = makeCard(
    {
      vacuum: prof("vacuum", "Vacuum"),
      custom_beta: prof("custom_beta", "Beta"),
      custom_alpha: prof("custom_alpha", "Alpha"),
    },
    ["vacuum"]
  );
  const custom = card.customRoomProfiles().map((p) => p.name);
  // 'vacuum' is dropped; remaining two are label-sorted (Alpha before Beta).
  assert.deepEqual(custom, ["custom_alpha", "custom_beta"]);
  // All-protected library -> no custom profiles at all.
  const allProt = makeCard({ vacuum: prof("vacuum") }, ["vacuum"]);
  assert.deepEqual(allProt.customRoomProfiles(), []);
});
