// Unit tests for the custom exclude-reason resolver in the review-state mixin. The exclude
// action sends resolveLearningHistoryExcludeReason(jobId): a preset chip passes its own value,
// while the "custom" chip passes the user's typed (trimmed) text, falling back to the literal
// "custom" when left blank. Backend reason is free-text (cv.string), so any string is valid.
// Run: node --test src/state/review-exclude-reason.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyReviewState } from "./review.js";

function makeState() {
  const proto = {};
  applyReviewState(proto);
  return Object.create(proto);
}

test("[XR-1] a preset reason chip sends its own value unchanged", () => {
  const s = makeState();
  s.setLearningHistoryExcludeReason("j1", "bad_room_attribution");
  assert.equal(s.resolveLearningHistoryExcludeReason("j1"), "bad_room_attribution");
});

test("[XR-2] custom sends the typed text, trimmed", () => {
  const s = makeState();
  s.setLearningHistoryExcludeReason("j1", "custom");
  s.setLearningHistoryCustomReason("j1", "  washed twice today  ");
  assert.equal(s.resolveLearningHistoryExcludeReason("j1"), "washed twice today");
});

test("[XR-3] custom with blank text falls back to the literal 'custom'", () => {
  const s = makeState();
  s.setLearningHistoryExcludeReason("j1", "custom");
  s.setLearningHistoryCustomReason("j1", "   ");
  assert.equal(s.resolveLearningHistoryExcludeReason("j1"), "custom");
});

test("[XR-4] custom text is tracked per-job", () => {
  const s = makeState();
  s.setLearningHistoryExcludeReason("j1", "custom");
  s.setLearningHistoryCustomReason("j1", "reason A");
  s.setLearningHistoryExcludeReason("j2", "custom");
  s.setLearningHistoryCustomReason("j2", "reason B");
  assert.equal(s.resolveLearningHistoryExcludeReason("j1"), "reason A");
  assert.equal(s.resolveLearningHistoryExcludeReason("j2"), "reason B");
});

test("[XR-5] the custom chip is offered in the reason options", () => {
  const s = makeState();
  const values = (s.learningHistoryExcludeReasonOptions() || []).map((o) => o.value);
  assert.ok(values.includes("custom"), "expected a 'custom' exclude-reason option");
});
