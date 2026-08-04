// Run: node --test src/state/access-issue-label.test.mjs
//
// Coverage targets — A6-AGX-4, src/state/access-issue-label.js
//   [AIL-1] a known backend code resolves to the translated sentence with params
//   [AIL-2] list params are joined by the LOCALE's separator, not a hard-coded one
//   [AIL-3] an unknown code falls back to the backend's prose, never a bare key
//   [AIL-4] card-scoped issues prefer room_access.issue.card.* (the code collision)
//   [AIL-5] a card-scoped code with no card key falls back to the shared key
//   [AIL-6] junk input never throws and never renders "undefined"

import { test } from "node:test";
import assert from "node:assert/strict";

import { accessIssueLabel } from "./access-issue-label.js";

/** A translate stub with the card's real contract: a miss returns the key. */
function makeT(table) {
  return (key, vars = {}) => {
    if (!(key in table)) return key;
    return String(table[key]).replace(
      /\{(\w+)\}/g,
      (whole, name) => (name in vars ? String(vars[name]) : whole)
    );
  };
}

const EN = {
  "room_access.issue.list_separator": ", ",
  "room_access.issue.self_reference": "{room} cannot grant access to itself.",
  "room_access.issue.cycle_detected": "Access links create a loop: {rooms}.",
  "room_access.issue.missing_room": "{room} still references missing room {missing_room}.",
  "room_access.issue.multiple_inbound": "{room} is granted access by more than one room ({sources}).",
  "room_access.issue.card.missing_room": "This room no longer exists on the active map.",
  "room_access.invalid_graph": "Invalid room access graph.",
};

test("[AIL-1] a known code resolves with its params", () => {
  const label = accessIssueLabel(
    { code: "self_reference", params: { room: "Kitchen" }, message: "EN PROSE" },
    makeT(EN)
  );
  assert.equal(label, "Kitchen cannot grant access to itself.");
});

test("[AIL-2] list params use the locale's separator", () => {
  const issue = { code: "cycle_detected", params: { rooms: ["Hall", "Kitchen", "Hall"] } };

  assert.equal(
    accessIssueLabel(issue, makeT(EN)),
    "Access links create a loop: Hall, Kitchen, Hall."
  );

  // A locale that joins differently must be honoured — this is the whole reason
  // the backend ships the list unjoined.
  const ja = makeT({ ...EN, "room_access.issue.list_separator": "、" });
  assert.equal(
    accessIssueLabel(issue, ja),
    "Access links create a loop: Hall、Kitchen、Hall."
  );
});

test("[AIL-3] an unknown code falls back to prose, never a bare key", () => {
  const label = accessIssueLabel(
    { code: "some_future_issue", message: "A newer backend said this." },
    makeT(EN)
  );
  assert.equal(label, "A newer backend said this.");
  assert.ok(!label.includes("room_access.issue."), "a raw key must never reach the user");
});

test("[AIL-4] card-scoped issues win over the backend key with the same code", () => {
  // The collision this scoping exists for: the backend's missing_room means
  // "references a room that is gone"; the card's means "the room you are
  // editing is gone". Same code, different sentence.
  const backend = accessIssueLabel(
    { code: "missing_room", params: { room: "Hall", missing_room: "Study" } },
    makeT(EN)
  );
  assert.equal(backend, "Hall still references missing room Study.");

  const card = accessIssueLabel(
    { code: "missing_room", scope: "card", params: {} },
    makeT(EN)
  );
  assert.equal(card, "This room no longer exists on the active map.");
});

test("[AIL-5] a card-scoped code with no card key uses the shared one", () => {
  // multiple_inbound has no card.* entry in this table, so it must degrade to
  // the shared key rather than falling all the way to prose.
  const label = accessIssueLabel(
    { code: "multiple_inbound", scope: "card", params: { room: "Hall", sources: ["A", "B"] } },
    makeT(EN)
  );
  assert.equal(label, "Hall is granted access by more than one room (A, B).");
});

test("[AIL-6] junk never throws and never renders undefined", () => {
  const t = makeT(EN);
  assert.equal(accessIssueLabel(null, t), "");
  assert.equal(accessIssueLabel(undefined, t), "");
  assert.equal(accessIssueLabel("a plain string", t), "a plain string");
  // no code, no message -> the generic, not an empty box
  assert.equal(accessIssueLabel({}, t), "Invalid room access graph.");
  // no translate function at all must not throw
  assert.equal(accessIssueLabel({ code: "x", message: "raw" }, undefined), "raw");
  for (const out of [
    accessIssueLabel({ code: "self_reference", params: null }, t),
    accessIssueLabel({ code: "cycle_detected", params: { rooms: [] } }, t),
  ]) {
    assert.ok(!String(out).includes("undefined"), `leaked undefined: ${out}`);
  }
});
