// Run: node --test harness/lib/stub-state-name.test.mjs
//
// Coverage targets — harness/fixtures/stub-state.js :: makeNullObject
//   [SSN-1] `.name` absorbs to "" like every other read, at any depth
//   [SSN-2] the other primitive coercions still absorb
//   [SSN-3] `prototype` is still forwarded — it is non-configurable on a function
//
// WHY. The stub is a Proxy over `function nullObject() {}`, and its get trap forwarded
// `name` to the target. `name` is the field a PROFILE, a ROOM, a ZONE and a THEME all
// use, so any absorbed object rendered the literal text "nullObject" — visible in the
// Run Profiles panel of the rooms-active contact sheet, which is published to the public
// theme gallery. Every other coercion in that trap already returns an empty value;
// `name` was swept in with `prototype`/`constructor`, which have a real reason to be
// forwarded and which `name` does not share: it is configurable, so the trap may return
// whatever it likes.
//
// THE INPUT THAT MAKES [SSN-1] RED: restore `case "name":` to the Reflect.get group.
// `o.name` goes back to "nullObject" and the gallery preview prints it again.

import { test } from "node:test";
import assert from "node:assert/strict";

import { makeNullObject } from "../fixtures/stub-state.js";

test("[SSN-1] .name absorbs to an empty string, at any depth", () => {
  const o = makeNullObject(null);
  assert.equal(o.name, "", "a bare .name must not leak the target function's name");
  assert.equal(o.profile.name, "", "nested reads absorb the same way");
  assert.equal(o.a.b.c.name, "", "depth does not reintroduce it");
  assert.notEqual(o.name, "nullObject");
});

test("[SSN-2] the other coercions still absorb", () => {
  const o = makeNullObject(null);
  assert.equal(String(o), "");
  assert.equal(Number(o), 0);
  assert.equal(o.length, 0);
  assert.equal(JSON.stringify({ v: o }), '{"v":null}');
  assert.equal(o.then, undefined, "must never be thenable");
  assert.deepEqual([...o], [], "iterating yields nothing");
});

test("[SSN-3] prototype is still forwarded", () => {
  // Non-configurable on a function. Forwarding it is the conservative choice and the
  // reason the three were grouped in the first place — `name` just did not belong.
  const o = makeNullObject(null);
  assert.equal(typeof o.prototype, "object");
});

test("[SSN-4] the access census still records the path", () => {
  // The stub's other job is recording what the card touched; absorbing `name` must not
  // cost that.
  const seen = new Set();
  const o = makeNullObject(seen, "state");
  void o.profile.name;
  assert.ok([...seen].some((p) => p.includes("profile")), `census missed it: ${[...seen]}`);
});
