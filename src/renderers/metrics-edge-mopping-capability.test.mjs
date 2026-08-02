// Regression test — CARD-8 (carried CF-9, Q11). _localizedProfile (metrics.js:
// 520-553) surfaces an "Edge Mopping" subtitle chip whenever profile.edge_mopping
// is truthy (line 537: `const edge = Boolean(profile?.edge_mopping);`, line 551:
// `if (edge) sub.push(...)`) with NO capability check at all -- the function
// signature takes only `profile`, nothing that could carry a per-brand
// declaration. Q11's verified sites: this file (537/551) and
// src/renderers/external-jobs.js:284-292 (the assignment editor's edge-mop
// toggle row, same "always rendered" shape -- NOT driven here, time-boxed;
// _renderExtRoomPanel needs a heavier ctx/state harness than this pure-function
// site, left for a follow-up pass).
//
// grepped confirmation: `supports_edge_mopping` has zero matches anywhere
// under src/ -- no capability-gating code path exists yet for this control at
// ALL, on either site. The established pattern for a real capability gate
// already exists elsewhere (dashboard-card.js:308's
// `this._snapshot?.supports_zone_clean === true`), so this is a genuine gap,
// not a naming mismatch.
//
// Run: node --test src/renderers/metrics-edge-mopping-capability.test.mjs
//
// FLIP CONVENTION (mirrors core-service-failure.test.mjs): CARD8-1 FAILS
// against current metrics.js (the subtitle renders on a capability-false
// fixture) and is expected to PASS once _localizedProfile (or its caller)
// checks the per-brand declaration. CARD8-2 is the control -- a
// capability-true fixture must still show the chip, so a fix that
// accidentally goes product-wide (Q11's named caution) is also caught.

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyMetricsRenderers } from "./metrics.js";

function makeCard() {
  const proto = {};
  applyMetricsRenderers(proto);
  const card = Object.create(proto);
  card.tVocabRaw = (field, val, fallback) => fallback;
  card.tRaw = (key) => (key === "room_card.edge_mopping_label" ? "Edge Mopping" : key);
  return card;
}

const BASE_PROFILE = {
  room_label: "Kitchen",
  clean_mode: "vacuum_mop",
  selected_profile_name: "custom",
  resolved_profile_name: "custom",
  clean_passes: 1,
  edge_mopping: true,
};

test("[CARD8-1] edge-mopping subtitle is suppressed when the brand's capability is false", 
  { todo: "wave-7 CARD fix not yet executed - drop this flag as part of the fix" }, () => {
  const card = makeCard();
  // No signal reaches _localizedProfile that could distinguish this fixture
  // from a capability-true one -- the profile carries only what the run
  // itself did, never what the vacuum CAN do.
  const result = card._localizedProfile({ ...BASE_PROFILE, supports_edge_mopping: false });
  assert.ok(
    !result.subtitle.includes("Edge Mopping"),
    `edge-mopping chip rendered ("${result.subtitle}") for a fixture declaring supports_edge_mopping:false`
  );
});

test("[CARD8-2] edge-mopping subtitle still shows when the brand's capability is true (control)", () => {
  const card = makeCard();
  const result = card._localizedProfile({ ...BASE_PROFILE, supports_edge_mopping: true });
  assert.ok(
    result.subtitle.includes("Edge Mopping"),
    "a capability-true fixture lost the chip too -- a fix must not go product-wide (Q11)"
  );
});
