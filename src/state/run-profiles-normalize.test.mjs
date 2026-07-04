// Unit tests for _normalizeRunProfilesPayload — the tolerant unwrap that turns whatever the
// backend hands the card into a canonical { profiles: Array, library: PlainObject }. It accepts
// a bare array, or an object with `profiles` (preferred) OR `saved_run_profiles` (fallback), and
// hard-guards `library` to a NON-array plain object so downstream detail-merge lookups
// (library[profileId]) can't blow up on an array/null/scalar.
// Run: node --test src/state/run-profiles-normalize.test.mjs
//
// Coverage targets (RNP = Run-profile Normalize Payload):
//   [RNP-1] bare array -> {profiles: <that array>, library: {}}
//   [RNP-2] object with profiles[] -> uses profiles; library defaults to {}
//   [RNP-3] object with only saved_run_profiles[] -> fallback source
//   [RNP-4] profiles precedence: profiles[] wins over saved_run_profiles[]
//   [RNP-5] library guard: only a non-array plain object survives, else {}
//   [RNP-6] non-object / nullish payloads -> {profiles: [], library: {}}
//   [RNP-7] non-array profiles / saved_run_profiles fields -> [] (not coerced)
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyRunProfilesState } from "./run-profiles.js";

function makeCard() {
  const proto = {};
  applyRunProfilesState(proto);
  return Object.create(proto);
}

const norm = (payload) => makeCard()._normalizeRunProfilesPayload(payload);

test("[RNP-1] bare array payload -> profiles is that array (identity), library empty", () => {
  const arr = [{ id: "a" }, { id: "b" }];
  const r = norm(arr);
  assert.deepEqual(r, { profiles: arr, library: {} });
  assert.equal(r.profiles, arr); // returned as-is, not copied
  assert.deepEqual(r.library, {});
});

test("[RNP-1b] empty bare array stays an array, library {}", () => {
  const r = norm([]);
  assert.deepEqual(r.profiles, []);
  assert.ok(Array.isArray(r.profiles));
  assert.deepEqual(r.library, {});
});

test("[RNP-2] object with profiles[] -> uses profiles; missing library defaults to {}", () => {
  const profiles = [{ id: "x" }];
  const r = norm({ profiles });
  assert.equal(r.profiles, profiles);
  assert.deepEqual(r.library, {});
});

test("[RNP-3] object with only saved_run_profiles[] -> fallback source is used", () => {
  const saved = [{ id: "s1" }, { id: "s2" }];
  const r = norm({ saved_run_profiles: saved });
  assert.equal(r.profiles, saved);
  assert.deepEqual(r.library, {});
});

test("[RNP-4] precedence: profiles[] wins over saved_run_profiles[] when both present", () => {
  const profiles = [{ id: "p" }];
  const saved = [{ id: "s" }];
  const r = norm({ profiles, saved_run_profiles: saved });
  assert.equal(r.profiles, profiles);
});

test("[RNP-4b] empty profiles[] still wins over a populated saved_run_profiles[] (Array.isArray short-circuits on the empty array)", () => {
  // Guards the subtle bug: the ternary checks Array.isArray(profiles) FIRST, so an
  // explicitly-empty profiles array beats saved_run_profiles — it is NOT a length check.
  const saved = [{ id: "s" }];
  const r = norm({ profiles: [], saved_run_profiles: saved });
  assert.deepEqual(r.profiles, []);
  assert.notEqual(r.profiles, saved);
});

test("[RNP-5] library guard: a plain object survives untouched", () => {
  const library = { p1: { id: "p1", name: "Deep" } };
  const r = norm({ profiles: [{ id: "p1" }], library });
  assert.equal(r.library, library); // same reference, passed through
});

test("[RNP-5b] library guard: an ARRAY library is rejected -> {} (defends library[id] lookups)", () => {
  const r = norm({ profiles: [], library: [{ id: "p1" }] });
  assert.deepEqual(r.library, {});
  assert.ok(!Array.isArray(r.library));
});

test("[RNP-5c] library guard: null / scalar / undefined library -> {}", () => {
  assert.deepEqual(norm({ profiles: [], library: null }).library, {});
  assert.deepEqual(norm({ profiles: [], library: "nope" }).library, {});
  assert.deepEqual(norm({ profiles: [], library: 42 }).library, {});
  assert.deepEqual(norm({ profiles: [] }).library, {}); // absent
});

test("[RNP-6] non-object / nullish payloads -> empty canonical shape", () => {
  for (const bad of [null, undefined, 0, 42, "string", true, false, NaN]) {
    const r = norm(bad);
    assert.deepEqual(r, { profiles: [], library: {} }, `payload=${String(bad)}`);
  }
});

test("[RNP-7] object with non-array profiles/saved fields -> [] (not coerced or wrapped)", () => {
  // profiles is a non-array (object) and there is no valid saved_run_profiles -> empty list.
  assert.deepEqual(norm({ profiles: { id: "x" } }).profiles, []);
  assert.deepEqual(norm({ profiles: "nope" }).profiles, []);
  // saved_run_profiles non-array likewise contributes nothing.
  assert.deepEqual(norm({ saved_run_profiles: { id: "s" } }).profiles, []);
  // both invalid -> empty, library still {}.
  const r = norm({ profiles: null, saved_run_profiles: 3 });
  assert.deepEqual(r, { profiles: [], library: {} });
});

test("[RNP-7b] non-array profiles falls back to a valid saved_run_profiles[]", () => {
  const saved = [{ id: "s" }];
  const r = norm({ profiles: { not: "array" }, saved_run_profiles: saved });
  assert.equal(r.profiles, saved);
});
