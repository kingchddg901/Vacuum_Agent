// Regression tests — a FAILED fetch must not be rendered as a confident empty result.
//
// The card stored fetched collections as bare values, so "never loaded", "failed" and
// "genuinely empty" collapsed into the same state. The renderers then asserted the
// strongest reading of it: "No saved zones yet.", "No saved profiles yet.", and every room
// card drawn as healthy. The user is told something false and given no way to know.
//
// The correct pattern already existed four lines away in the same file — refreshRoomProfiles
// guards `if (!payload) return null;` — and three sibling fetch sites did not adopt it.
//
// Card audit FE-ERR-4/5/6/9.
// Run: node --test src/actions/fetch-failure-tristate.test.mjs
//
// Coverage (TS = TriState):
//   [TS-1] getSavedZones returns null on failure, [] only for a genuinely empty map
//   [TS-2] a failed saved-zones fetch does NOT overwrite the existing library
//   [TS-3] a failed run-profiles fetch does NOT wipe the library
//   [TS-4] a failed trouble-rooms fetch does NOT latch "loaded" (warnings can return)
//   [TS-5] a failed filter refresh rolls the chip back to its previous value

import { test } from "node:test";
import assert from "node:assert/strict";

import { applySavedZonesActions } from "./saved-zones.js";

function makeCard(serviceResult) {
  const proto = {};
  applySavedZonesActions(proto);
  const card = Object.create(proto);
  card.callService = async () => serviceResult;
  card.state = { vacuumEntityId: () => "vacuum.alfred" };
  return card;
}

test("[TS-1] getSavedZones distinguishes failure from an empty map", async () => {
  const failed = makeCard(null);            // callService returns null on failure
  assert.equal(
    await failed.getSavedZones({ vacuum_entity_id: "vacuum.alfred", map_id: "1" }),
    null,
    "a failed fetch reported an empty zone library"
  );

  const empty = makeCard({ response: { saved_zones: [] } });
  assert.deepEqual(
    await empty.getSavedZones({ vacuum_entity_id: "vacuum.alfred", map_id: "1" }),
    [],
    "a genuinely empty map should still report []"
  );

  const populated = makeCard({ response: { saved_zones: [{ zone_id: "z1" }] } });
  assert.deepEqual(
    await populated.getSavedZones({ vacuum_entity_id: "vacuum.alfred", map_id: "1" }),
    [{ zone_id: "z1" }]
  );
});

// The refresh helpers below live on the card element in src/main.js. These model the
// guard contract each one must honour: a null payload leaves stored state untouched.

test("[TS-2] a failed saved-zones fetch leaves the existing library alone", () => {
  let library = [{ zone_id: "kept" }];
  const setLibrary = (v) => { library = v; };

  const refresh = (zones) => {
    if (zones == null) return null;          // the guard
    setLibrary(zones);
    return zones;
  };

  assert.equal(refresh(null), null);
  assert.deepEqual(library, [{ zone_id: "kept" }], "a failure wiped the user's zones");
  refresh([]);
  assert.deepEqual(library, [], "a genuine empty result must still apply");
});

test("[TS-3] a failed run-profiles fetch leaves the library alone", () => {
  let library = { profiles: [{ id: "nightly" }] };
  const refresh = (payload) => {
    if (!payload) return null;               // the guard
    library = payload;
    return payload;
  };

  assert.equal(refresh(null), null);
  assert.deepEqual(library, { profiles: [{ id: "nightly" }] }, "a failure wiped the profiles");
});

test("[TS-4] a failed trouble-rooms fetch does not latch loaded", () => {
  let loaded = false;
  const refresh = (payload) => {
    if (payload) loaded = true;              // the guard — was unconditional
    return payload ?? null;
  };

  refresh(null);
  assert.equal(loaded, false, "one failure permanently suppressed every trouble warning");
  refresh({ rooms: {} });
  assert.equal(loaded, true);
});

test("[TS-5] a failed filter refresh rolls the chip back", async () => {
  const filters = { room: "all" };
  const setFilter = (k, v) => { filters[k] = v; };

  const applyFilter = async (key, value, refresh) => {
    const prev = filters[key];
    setFilter(key, value);
    const applied = await refresh();
    if (applied == null) setFilter(key, prev);
    return applied;
  };

  await applyFilter("room", "kitchen", async () => null);        // refresh fails
  assert.equal(filters.room, "all", "the chip showed a filter the data never applied");

  await applyFilter("room", "kitchen", async () => ({ jobs: [] })); // refresh succeeds
  assert.equal(filters.room, "kitchen");
});

// [TS-6] SOURCE PINS for the three guards TS-2..TS-5 only model — 2026-08-07, W0 v2.
//
// TS-2..TS-5 each build their own local `refresh`/`applyFilter` closure containing
// the guard and then assert that closure. The header calls them models, which is
// honest, but the coverage list above reads as though the shipped helpers are
// covered and they are not: the real guards live on the custom element in
// src/main.js, and only TS-1 (getSavedZones) touches production code at all.
//
// main.js cannot be imported here — it declares `class … extends HTMLElement` and
// calls customElements.define at module scope, so node has no DOM to load it into,
// and nothing in src/**/*.test.mjs imports it. Real behavioural coverage would
// have to run through the harness's mountRealCard (see harness/tests/real-frame).
// Until it does, pin the guards against source: every kill test for this finding
// is literally "delete this line", which is exactly what a source pin catches.
test("[TS-6] the SHIPPED refresh helpers still guard against a failed fetch", async () => {
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("../main.js", import.meta.url), "utf-8");

  // Scope each pin to ITS OWN METHOD. A whole-file `includes` is not a
  // discriminator here: `if (!payload) return null;` appears TWICE, because
  // refreshRoomProfiles carries the same guard — it is the sibling this file's
  // header cites as the pattern that already existed. Deleting the run-profiles
  // one left the room-profiles one behind and a file-wide check stayed green,
  // measuring nothing. Verified by mutation, not assumed.
  const methodBody = (name) => {
    const start = src.indexOf(`async ${name}(`);
    assert.ok(start > 0, `${name} is gone from main.js`);
    const next = src.indexOf("\n  async ", start + 1);
    return src.slice(start, next > 0 ? next : src.length);
  };

  // FE-ERR-4: a failed saved-zones fetch must not overwrite the library with [].
  assert.ok(
    methodBody("refreshSavedZones").includes("if (zones == null) return null;"),
    "refreshSavedZones lost its null guard — a failed fetch renders 'No saved zones yet.' "
    + "and the selection badge and Clean-selected button vanish with no error (FE-ERR-4)",
  );
  // FE-ERR-5: same for run profiles.
  assert.ok(
    methodBody("refreshRunProfiles").includes("if (!payload) return null;"),
    "refreshRunProfiles lost its falsy guard — a failed fetch wipes the profile library "
    + "and drops any profile staged for the next run (FE-ERR-5)",
  );
  // FE-ERR-6: the trouble-rooms LATCH must be conditional. Unconditional, one failed
  // fetch permanently suppresses every chronic-trouble warning for the session —
  // the log stays null, every room card renders healthy, and the latch stops any
  // re-fetch. This is the subtlest of the three and the easiest to "simplify" away.
  assert.ok(
    methodBody("refreshTroubleRoomsLog").includes("if (payload) this._troubleRoomsLogLoaded = true;"),
    "the trouble-rooms loaded-latch is no longer conditional on a successful payload — "
    + "one failed fetch silently suppresses every chronic-trouble warning (FE-ERR-6)",
  );
});
