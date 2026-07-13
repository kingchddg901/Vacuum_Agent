// Render-path tests for the live zone banner. Like charge/wait, a zone phase has no current
// room, so the banner must render gated ONLY on liveZoneStatus() — never on the room queue.
// Run: node --test src/renderers/learning-zone-status.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyLearningRenderers } from "./learning.js";

function makeRenderer(zone) {
  const proto = {};
  applyLearningRenderers(proto);
  const r = Object.create(proto);
  r.t = (key, vars = {}) => `${key}:${JSON.stringify(vars)}`;
  r.escapeHtml = (s) => String(s);
  r._formatLearningMinutes = (m) => `${m}m`;
  // state deliberately has ONLY liveZoneStatus — no room-queue accessors.
  return { r, state: { liveZoneStatus: () => zone } };
}

test("[ZNR-1] empty when not in a zone phase", () => {
  const { r, state } = makeRenderer(null);
  assert.equal(r.renderLearningZoneStatus(state), "");
});

test("[ZNR-2] renders the zone banner with names + eta variant", () => {
  const { r, state } = makeRenderer({ names: ["stove", "sink"], etaMinutes: 5 });
  const html = r.renderLearningZoneStatus(state);
  assert.match(html, /evcc-learning-zone-banner/);
  assert.match(html, /learning\.cleaning_zone_eta:/);   // eta variant chosen
  assert.match(html, /stove, sink/);                    // joined names
  assert.match(html, /5m/);                             // formatted eta
});

test("[ZNR-3] no eta -> base key; empty names -> zone fallback", () => {
  const { r, state } = makeRenderer({ names: [], etaMinutes: null });
  const html = r.renderLearningZoneStatus(state);
  assert.match(html, /learning\.cleaning_zone:/);       // base key, not _eta
  assert.doesNotMatch(html, /cleaning_zone_eta/);
  assert.match(html, /rooms\.zone_fallback/);           // fallback name when none resolve
});
