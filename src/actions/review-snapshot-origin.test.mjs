// Regression: getLearningHistorySnapshot must FORWARD every filter param to the service.
// The origin filter chip was a silent no-op because this wrapper destructured its params
// without `origin`, so it never reached the backend (the snapshot came back with all filters
// null). Guards against a filter key being added to the caller/backend but dropped here.
// Run: node --test src/actions/review-snapshot-origin.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyReviewActions } from "./review.js";

function makeCard() {
  const proto = {};
  applyReviewActions(proto);
  const card = Object.create(proto);
  card._calls = [];
  card.callService = async (domain, service, data) => {
    card._calls.push({ domain, service, data });
    return { response: { ok: true } };
  };
  card.state = { vacuumEntityId: () => "vacuum.alfred" };
  return card;
}

test("[RSO-1] origin is forwarded to the service", async () => {
  const card = makeCard();
  await card.getLearningHistorySnapshot({ vacuum_entity_id: "vacuum.alfred", origin: "external" });
  assert.equal(card._calls.length, 1);
  assert.equal(card._calls[0].data.origin, "external");
});

test("[RSO-2] every filter param is forwarded (no dropped key)", async () => {
  const card = makeCard();
  await card.getLearningHistorySnapshot({
    vacuum_entity_id: "vacuum.alfred", room_slug: "kitchen", profile_key: "p1",
    status: "completed", used_for_learning: true, origin: "internal", limit: 25,
  });
  const d = card._calls[0].data;
  assert.equal(d.room_slug, "kitchen");
  assert.equal(d.profile_key, "p1");
  assert.equal(d.status, "completed");
  assert.equal(d.used_for_learning, true);
  assert.equal(d.origin, "internal");
  assert.equal(d.limit, 25);
});

test("[RSO-3] a blank origin is omitted (Optional)", async () => {
  const card = makeCard();
  await card.getLearningHistorySnapshot({ vacuum_entity_id: "vacuum.alfred", origin: "" });
  assert.equal("origin" in card._calls[0].data, false);
});
