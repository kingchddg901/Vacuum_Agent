// Render-path tests for the live charge status (slice c / b fix). The banner must render
// gated ONLY on liveChargeStatus() — during a charge_wait phase resolved_rooms is [], so the
// room timeline is empty and shouldShowLiveQueue() is false; the old placement inside
// renderLearningProgressList went dark exactly then. These pin that renderLearningChargeStatus
// depends on NONE of the room-queue gates.
// Run: node --test src/renderers/learning-charge-status.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyLearningRenderers } from "./learning.js";

function makeRenderer(charge) {
  const proto = {};
  applyLearningRenderers(proto);
  const r = Object.create(proto);
  r.t = (key, vars = {}) => `${key}:${JSON.stringify(vars)}`;
  r.escapeHtml = (s) => String(s);
  r._formatLearningMinutes = (m) => `${m}m`;
  // NOTE: state deliberately has ONLY liveChargeStatus — no learningRoomTimeline,
  // no shouldShowLiveQueue. If the render touched those it would throw.
  return { r, state: { liveChargeStatus: () => charge } };
}

test("[CHGR-1] empty when not charging", () => {
  const { r, state } = makeRenderer(null);
  assert.equal(r.renderLearningChargeStatus(state), "");
});

test("[CHGR-2] renders the banner gated only on charge (no queue/timeline dependency)", () => {
  const { r, state } = makeRenderer({ targetPercent: 95, etaMinutes: 18, fromBattery: 62 });
  const html = r.renderLearningChargeStatus(state);
  assert.match(html, /evcc-learning-charge-banner/);
  assert.match(html, /learning\.charging_to_eta:/); // eta variant chosen
  assert.match(html, /95/);                          // target
  assert.match(html, /18m/);                         // formatted eta
  assert.match(html, /learning\.charging_from:/);    // from-battery fragment
  assert.match(html, /62/);
});

test("[CHGR-3] uses the no-eta key and drops the from fragment when null", () => {
  const { r, state } = makeRenderer({ targetPercent: 100, etaMinutes: null, fromBattery: null });
  const html = r.renderLearningChargeStatus(state);
  assert.match(html, /learning\.charging_to:/);      // base key, not _eta
  assert.doesNotMatch(html, /charging_to_eta/);
  assert.doesNotMatch(html, /charging_from/);
});
