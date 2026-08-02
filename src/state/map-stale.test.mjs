// Unit tests for CARD-2 clause 1 (RP-027's hold contract): the map-stale
// selectors that drive the dim treatment + "last seen" badge.
// Run: node --test src/state/map-stale.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyMapState } from "./map.js";

function makeState() {
  const proto = {};
  applyMapState(proto);
  return Object.create(proto);
}

test("[MS-1] no snapshot -> not stale, no stale_since", () => {
  const s = makeState();
  s.dashboardSnapshot = () => null;
  assert.equal(s.isMapStale(), false);
  assert.equal(s.mapStaleSince(), null);
});

test("[MS-2] a fresh (non-held) map_state_source -> not stale", () => {
  const s = makeState();
  s.dashboardSnapshot = () => ({ map_state_source: { present: true } });
  assert.equal(s.isMapStale(), false);
  assert.equal(s.mapStaleSince(), null);
});

test("[MS-3] a held result -> stale true, stale_since surfaced", () => {
  const s = makeState();
  s.dashboardSnapshot = () => ({
    map_state_source: {
      present: true, stale: true, stale_since: "2026-08-01T12:00:00+00:00", stale_reason: "live_map_absent",
    },
  });
  assert.equal(s.isMapStale(), true);
  assert.equal(s.mapStaleSince(), "2026-08-01T12:00:00+00:00");
});

test("[MS-4] stale_since is only surfaced while actually stale (defense in depth vs a stale backend leftover)", () => {
  const s = makeState();
  s.dashboardSnapshot = () => ({
    map_state_source: { present: true, stale: false, stale_since: "2026-08-01T12:00:00+00:00" },
  });
  assert.equal(s.isMapStale(), false);
  assert.equal(s.mapStaleSince(), null);
});
