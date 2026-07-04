// Unit tests for the pure maintenance-tab logic in src/state/maintenance.js.
// Covers the two upkeep-lookup / reset-guard helpers that back the Maintenance modal:
//   - findUpkeepItem: case-insensitive/trimmed match across the merged
//     maintenance_items + replacement_items lists, with an OPTIONAL entity_id
//     third-match that only fires when BOTH the query and the candidate have one.
//   - canInvokeMaintenanceReset: the AND-gate the reset button reads before firing.
//
// Coverage targets:
//   [MNT-1..5] findUpkeepItem  — merge, normalize (case/trim), entity_id conditional, empties
//   [MNT-6..9] canInvokeMaintenanceReset — the full boolean AND-gate + edge inputs
//
// Run: node --test src/state/maintenance-logic.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyMaintenanceState } from "./maintenance.js";

// Build a card-like object off the mixin, then stub dashboardUpkeep() with a
// canned upkeep payload (the only external read findUpkeepItem performs).
function makeCard(upkeep) {
  const proto = {};
  applyMaintenanceState(proto);
  const card = Object.create(proto);
  if (upkeep !== undefined) card.dashboardUpkeep = () => upkeep;
  return card;
}

// ---------------------------------------------------------------------------
// findUpkeepItem
// ---------------------------------------------------------------------------

test("[MNT-1] findUpkeepItem: matches by kind+component across BOTH lists (merged)", () => {
  const brush = { kind: "replace", component: "brush", entity_id: null };
  const filter = { kind: "clean", component: "filter", entity_id: null };
  const card = makeCard({
    maintenance_items: [filter],
    replacement_items: [brush],
  });
  // hit in maintenance_items
  assert.equal(card.findUpkeepItem("clean", "filter"), filter);
  // hit in replacement_items (merged in after maintenance_items)
  assert.equal(card.findUpkeepItem("replace", "brush"), brush);
  // no match -> null
  assert.equal(card.findUpkeepItem("clean", "nozzle"), null);
});

test("[MNT-2] findUpkeepItem: kind+component compared case-insensitively AND trimmed", () => {
  const item = { kind: "Replace", component: "  Side-Brush " };
  const card = makeCard({ maintenance_items: [item], replacement_items: [] });
  // query is upper/spaced, candidate is mixed-case/padded -> still matches
  assert.equal(card.findUpkeepItem("  REPLACE ", "side-brush"), item);
  assert.equal(card.findUpkeepItem("replace", "SIDE-BRUSH"), item);
  // wrong component -> null (kind alone is not enough)
  assert.equal(card.findUpkeepItem("replace", "main-brush"), null);
});

test("[MNT-3] findUpkeepItem: entity_id is a 3rd match ONLY when both query+item have one", () => {
  const a = { kind: "replace", component: "brush", entity_id: "sensor.brush_a" };
  const b = { kind: "replace", component: "brush", entity_id: "sensor.brush_b" };
  const card = makeCard({ maintenance_items: [a, b], replacement_items: [] });

  // Both provided + present -> disambiguates to the matching entity (case-insensitive).
  assert.equal(card.findUpkeepItem("replace", "brush", "SENSOR.BRUSH_B"), b);
  // Query has no entity_id -> the extra clause is skipped -> first kind+component wins (a).
  assert.equal(card.findUpkeepItem("replace", "brush"), a);
  assert.equal(card.findUpkeepItem("replace", "brush", null), a);
  // Query entity_id present but doesn't match either -> the two-key filter still
  // gates: for each candidate the entity mismatch fails it, so overall -> null.
  assert.equal(card.findUpkeepItem("replace", "brush", "sensor.brush_z"), null);
});

test("[MNT-4] findUpkeepItem: entity clause skipped when the CANDIDATE has no entity_id", () => {
  // Candidate lacks entity_id: `itemEntityId` is null, so `normalizedEntityId && itemEntityId`
  // short-circuits false -> the entity clause never rejects it. A query entity_id is ignored.
  const item = { kind: "empty", component: "dustbin", entity_id: null };
  const card = makeCard({ maintenance_items: [item], replacement_items: [] });
  assert.equal(card.findUpkeepItem("empty", "dustbin", "sensor.anything"), item);
});

test("[MNT-5] findUpkeepItem: missing/non-array lists and no dashboardUpkeep -> null", () => {
  // dashboardUpkeep absent entirely (optional-chain -> {} default).
  assert.equal(makeCard().findUpkeepItem("replace", "brush"), null);
  // dashboardUpkeep returns null -> ?? {} -> empty groups -> null.
  assert.equal(makeCard(null).findUpkeepItem("replace", "brush"), null);
  // Non-array list fields are ignored (Array.isArray guard) -> null, not a throw.
  const card = makeCard({ maintenance_items: "nope", replacement_items: { x: 1 } });
  assert.equal(card.findUpkeepItem("replace", "brush"), null);
  // Empty arrays -> null.
  assert.equal(
    makeCard({ maintenance_items: [], replacement_items: [] }).findUpkeepItem("k", "c"),
    null,
  );
});

// ---------------------------------------------------------------------------
// canInvokeMaintenanceReset
// ---------------------------------------------------------------------------

test("[MNT-6] canInvokeMaintenanceReset: all three conditions met -> true", () => {
  const card = makeCard();
  assert.equal(
    card.canInvokeMaintenanceReset({
      can_reset: true,
      reset_service: "eufy_vacuum.reset_consumable",
      reset_service_data: { component: "brush" },
    }),
    true,
  );
  // reset_service_data need only be non-null — an empty object still passes.
  assert.equal(
    card.canInvokeMaintenanceReset({
      can_reset: true,
      reset_service: "x.y",
      reset_service_data: {},
    }),
    true,
  );
});

test("[MNT-7] canInvokeMaintenanceReset: can_reset must be STRICTLY boolean true", () => {
  const card = makeCard();
  const base = { reset_service: "x.y", reset_service_data: {} };
  assert.equal(card.canInvokeMaintenanceReset({ ...base, can_reset: true }), true);
  // Truthy-but-not-true values are rejected (=== true guard).
  assert.equal(card.canInvokeMaintenanceReset({ ...base, can_reset: 1 }), false);
  assert.equal(card.canInvokeMaintenanceReset({ ...base, can_reset: "true" }), false);
  assert.equal(card.canInvokeMaintenanceReset({ ...base, can_reset: false }), false);
  assert.equal(card.canInvokeMaintenanceReset({ ...base }), false); // undefined
});

test("[MNT-8] canInvokeMaintenanceReset: reset_service must be a NON-EMPTY string", () => {
  const card = makeCard();
  const base = { can_reset: true, reset_service_data: {} };
  assert.equal(card.canInvokeMaintenanceReset({ ...base, reset_service: "s" }), true);
  assert.equal(card.canInvokeMaintenanceReset({ ...base, reset_service: "" }), false); // empty
  assert.equal(card.canInvokeMaintenanceReset({ ...base, reset_service: 123 }), false); // non-string
  assert.equal(card.canInvokeMaintenanceReset({ ...base, reset_service: null }), false);
  assert.equal(card.canInvokeMaintenanceReset({ ...base }), false); // missing
});

test("[MNT-9] canInvokeMaintenanceReset: reset_service_data must be != null; null item -> false", () => {
  const card = makeCard();
  const base = { can_reset: true, reset_service: "s" };
  // != null accepts falsy-but-defined values (0, "", false).
  assert.equal(card.canInvokeMaintenanceReset({ ...base, reset_service_data: 0 }), true);
  assert.equal(card.canInvokeMaintenanceReset({ ...base, reset_service_data: "" }), true);
  assert.equal(card.canInvokeMaintenanceReset({ ...base, reset_service_data: false }), true);
  // null / undefined data -> false.
  assert.equal(card.canInvokeMaintenanceReset({ ...base, reset_service_data: null }), false);
  assert.equal(card.canInvokeMaintenanceReset({ ...base }), false);
  // Null / undefined item -> optional-chain yields false, no throw.
  assert.equal(card.canInvokeMaintenanceReset(null), false);
  assert.equal(card.canInvokeMaintenanceReset(undefined), false);
});
