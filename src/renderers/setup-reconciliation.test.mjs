// CARD-7/RP-019 — reconciliation review banner rendering (renderers/setup.js's
// renderReconciliationPanel, a closure inside renderSetupView — not exposed as
// its own proto method, so these tests drive the whole renderSetupView() and
// assert on the returned HTML string, following this codebase's existing
// renderer-test convention (see run-profiles-unsupported-position.test.mjs /
// room-estimate-allocated.test.mjs).
//
// Proves (packet's TEST section):
//   - the two/three review kinds route into the correct TWO groups (Gap 1:
//     renamed_and_renumbered folds into "Renamed", not a third group), and
//     the folded row ALSO shows the id change.
//   - State A (has_changes:false) renders nothing.
//   - State C reports `dropped` when non-empty and omits it when empty.
//
// Run: node --test src/renderers/setup-reconciliation.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";

import { applySetupRenderers } from "./setup.js";

const VAC = "vacuum.alfred";

function makeHost() {
  const proto = {};
  applySetupRenderers(proto);
  const host = Object.create(proto);
  host.t = (key, vars) => `T:${key}${vars ? `:${JSON.stringify(vars)}` : ""}`;
  host.tRaw = (key, vars) => `RAW:${key}${vars ? `:${JSON.stringify(vars)}` : ""}`;
  host.escapeHtml = (s) => String(s ?? "");
  return host;
}

/** Minimal vacuum-entry status wired for the save_rooms step to reach the
 * reconciliation banner: one completed add_vacuum step, one completed
 * save_rooms step (no import_active_map step -> importNeeded=false), and one
 * imported map so the "no rooms discovered" early return doesn't fire. */
function makeStatus(reconciliation) {
  return {
    setup_complete: true,
    vacuums: [
      {
        vacuum_entity_id: VAC,
        display_name: "Alfred",
        setup_steps: [
          { id: "add_vacuum", label: "Add vacuum", completed: true, service: "" },
          { id: "save_rooms", label: "Configure rooms", completed: true, service: "" },
        ],
        next_step: null,
        room_drift: { in_sync: true, new_rooms: [], removed_rooms: [], transiently_missing: [], rejected_rooms: [] },
        reconciliation,
        maps: [{ map_id: "1", display_name: "Main", room_count: 2, imported: true, protection: null }],
        has_imported_map: true,
      },
    ],
  };
}

function makeState({ reconciliation, resolvedToken = null, result = null, refreshFailed = false } = {}) {
  return {
    setupStatus: () => makeStatus(reconciliation),
    setupReconcileResolvedToken: () => resolvedToken,
    setupReconcileResult: () => result,
    setupReconcileRefreshFailed: () => refreshFailed,
  };
}

function render(host, opts) {
  const state = makeState(opts);
  const card = { _config: { vacuum_entity_id: VAC }, _hass: null };
  return host.renderSetupView({ state, card });
}

/* ---- kind routing: two groups, three kinds -------------------------------- */

test("[CARD7-R1] id_changed routes into the Renumbered group only", () => {
  const host = makeHost();
  const reconciliation = {
    has_changes: true,
    plan_token: "tok-renumbered",
    reviews: [{ kind: "id_changed", slug: "kitchen", name: "Kitchen", old_id: 5, new_id: 7 }],
  };
  const html = render(host, { reconciliation });

  assert.match(html, /evcc-setup-reconcile-section renumbered/);
  assert.match(html, /T:setup\.reconcile_renumbered_title:\{"count":1\}/);
  assert.doesNotMatch(html, /evcc-setup-reconcile-section renamed/, "a pure id_changed review must not surface a Renamed section");
  // Structured id-change indicator (old -> new), not a glued sentence.
  assert.match(html, /evcc-setup-reconcile-id-old">5</);
  assert.match(html, /evcc-setup-reconcile-id-new">7</);
});

test("[CARD7-R2] renamed routes into the Renamed group only", () => {
  const host = makeHost();
  const reconciliation = {
    has_changes: true,
    plan_token: "tok-renamed",
    reviews: [{ kind: "renamed", room_id: 5, old_slug: "kitchen", new_slug: "dining", old_name: "Kitchen", new_name: "Dining" }],
  };
  const html = render(host, { reconciliation });

  assert.match(html, /evcc-setup-reconcile-section renamed/);
  assert.match(html, /T:setup\.reconcile_renamed_title:\{"count":1\}/);
  assert.doesNotMatch(html, /evcc-setup-reconcile-section renumbered/, "a pure renamed review must not surface a Renumbered section");
  // New name shown as the room label; old name as a SEPARATE translated caption
  // (never concatenated into one sentence with the room name).
  assert.match(html, /evcc-setup-reconcile-room-name">Dining</);
  assert.match(html, /T:setup\.reconcile_formerly:\{"name":"Kitchen"\}/);
  // No id-change indicator for a pure rename (nothing renumbered).
  assert.doesNotMatch(html, /evcc-setup-reconcile-id-change/);
});

test("[CARD7-R3] renamed_and_renumbered folds into the Renamed group (Gap 1) — NOT a third group — and shows BOTH the name and id change", () => {
  const host = makeHost();
  const reconciliation = {
    has_changes: true,
    plan_token: "tok-both",
    reviews: [{
      kind: "renamed_and_renumbered",
      old_id: 5, new_id: 7,
      old_slug: "kitchen", new_slug: "dining",
      old_name: "Kitchen", new_name: "Dining",
    }],
  };
  const html = render(host, { reconciliation });

  // Folded into "Renamed", exactly like a pure rename — same count-title key.
  assert.match(html, /evcc-setup-reconcile-section renamed/);
  assert.match(html, /T:setup\.reconcile_renamed_title:\{"count":1\}/);
  // No separate third-group title anywhere.
  assert.doesNotMatch(html, /reconcile_[a-z]*_and_renumbered_title/);
  // Row is marked so it can carry the extra id detail, and BOTH the name
  // change and the id change render (this kind's whole point per Gap 1).
  assert.match(html, /evcc-setup-reconcile-row renamed-and-renumbered/);
  assert.match(html, /evcc-setup-reconcile-room-name">Dining</);
  assert.match(html, /T:setup\.reconcile_formerly:\{"name":"Kitchen"\}/);
  assert.match(html, /evcc-setup-reconcile-id-old">5</);
  assert.match(html, /evcc-setup-reconcile-id-new">7</);
});

test("[CARD7-R4] a mix of all three kinds still yields exactly two group counts", () => {
  const host = makeHost();
  const reconciliation = {
    has_changes: true,
    plan_token: "tok-mixed",
    reviews: [
      { kind: "id_changed", slug: "hall", name: "Hall", old_id: 2, new_id: 4 },
      { kind: "renamed", room_id: 9, old_slug: "den", new_slug: "office", old_name: "Den", new_name: "Office" },
      { kind: "renamed_and_renumbered", old_id: 5, new_id: 7, old_slug: "kitchen", new_slug: "dining", old_name: "Kitchen", new_name: "Dining" },
    ],
  };
  const html = render(host, { reconciliation });

  assert.match(html, /T:setup\.reconcile_renumbered_title:\{"count":1\}/, "only the id_changed review counts toward Renumbered");
  assert.match(html, /T:setup\.reconcile_renamed_title:\{"count":2\}/, "renamed + renamed_and_renumbered both count toward Renamed");
});

/* ---- State A: has_changes:false -> render nothing -------------------------- */

test("[CARD7-R5] State A: has_changes:false renders no banner at all", () => {
  const host = makeHost();
  const reconciliation = { has_changes: false, plan_token: "tok-empty", reviews: [] };
  const html = render(host, { reconciliation });

  assert.doesNotMatch(html, /evcc-setup-reconcile-panel/, "no empty state / badge — State A renders nothing");
});

test("[CARD7-R5b] a null reconciliation (no discovery ever cached) also renders nothing", () => {
  const host = makeHost();
  const html = render(host, { reconciliation: null });

  assert.doesNotMatch(html, /evcc-setup-reconcile-panel/);
});

test("[CARD7-R5c] has_changes:false wins over a stuck refreshFailed flag — a fresh status poll's \"no changes\" is authoritative", () => {
  // Reproduces: silent plan_changed recovery fails (refreshFailed=true), then a
  // LATER, unrelated status poll (e.g. main.js's periodic _scheduleSetupStatusRefresh)
  // reports has_changes:false. The stale manual re-discover prompt must not
  // keep showing once the backend itself reports nothing pending.
  const host = makeHost();
  const reconciliation = { has_changes: false, plan_token: "tok-resolved-elsewhere", reviews: [] };
  const html = render(host, { reconciliation, refreshFailed: true });

  assert.doesNotMatch(html, /evcc-setup-reconcile-panel/, "State A must win even with refreshFailed still set");
  assert.doesNotMatch(html, /reconcile_refresh_failed/);
});

test("[CARD7-R5d] refreshFailed still shows the manual re-discover prompt when has_changes is (still) true", () => {
  const host = makeHost();
  const reconciliation = { has_changes: true, plan_token: "tok-stuck", reviews: [] };
  const html = render(host, { reconciliation, refreshFailed: true });

  assert.match(html, /T:setup\.reconcile_refresh_failed/);
  assert.match(html, /T:setup\.reconcile_rediscover_button/);
});

/* ---- State C: dropped reported when non-empty, omitted when empty --------- */

test("[CARD7-R6] State C reports migrated_room_count and the dropped-rooms sentence when dropped is non-empty", () => {
  const host = makeHost();
  const reconciliation = {
    has_changes: true,
    plan_token: "tok-resolved",
    reviews: [{ kind: "id_changed", slug: "hall", name: "Hall", old_id: 2, new_id: 4 }],
  };
  const result = { action: "migrate", migrated_room_count: 3, id_remap: { "2": 4 }, dropped: ["guest-bedroom"] };
  const html = render(host, { reconciliation, resolvedToken: "tok-resolved", result });

  assert.match(html, /T:setup\.reconcile_updated_count:\{"count":3\}/);
  assert.match(html, /RAW:setup\.reconcile_dropped_sentence:\{"count":1,"names":"Guest Bedroom"\}/, "slug prettified to a display name");
  // Resolved — the pending group banner (buttons) must not still be showing.
  assert.doesNotMatch(html, /evcc-setup-reconcile-actions/);
});

test("[CARD7-R7] State C omits the dropped sentence entirely when dropped is empty", () => {
  const host = makeHost();
  const reconciliation = {
    has_changes: true,
    plan_token: "tok-resolved-2",
    reviews: [{ kind: "id_changed", slug: "hall", name: "Hall", old_id: 2, new_id: 4 }],
  };
  const result = { action: "migrate", migrated_room_count: 2, id_remap: { "2": 4 }, dropped: [] };
  const html = render(host, { reconciliation, resolvedToken: "tok-resolved-2", result });

  assert.match(html, /T:setup\.reconcile_updated_count:\{"count":2\}/);
  assert.doesNotMatch(html, /reconcile_dropped_sentence/);
});

test("[CARD7-R8] a resolved DISMISS (action:'ignore') renders nothing — no false 'updated 0 rooms' receipt", () => {
  const host = makeHost();
  const reconciliation = {
    has_changes: true,
    plan_token: "tok-dismissed",
    reviews: [{ kind: "id_changed", slug: "hall", name: "Hall", old_id: 2, new_id: 4 }],
  };
  const result = { action: "ignore", migrated_room_count: 0, id_remap: {}, dropped: [] };
  const html = render(host, { reconciliation, resolvedToken: "tok-dismissed", result });

  assert.doesNotMatch(html, /evcc-setup-reconcile-panel/);
  assert.doesNotMatch(html, /reconcile_updated_count/);
});

test("[CARD7-R9] a STALE resolvedToken (doesn't match the current plan_token) re-shows the pending banner instead of a stale receipt", () => {
  const host = makeHost();
  const reconciliation = {
    has_changes: true,
    plan_token: "tok-fresh",
    reviews: [{ kind: "id_changed", slug: "hall", name: "Hall", old_id: 2, new_id: 4 }],
  };
  // resolvedToken is for a DIFFERENT (older) plan — must not suppress the fresh review.
  const result = { action: "migrate", migrated_room_count: 1, id_remap: {}, dropped: [] };
  const html = render(host, { reconciliation, resolvedToken: "tok-old", result });

  assert.match(html, /evcc-setup-reconcile-actions/, "a fresh unresolved plan must show Update/Dismiss");
  assert.doesNotMatch(html, /T:setup\.reconcile_updated_count/, "the stale local result must not render as if it applied to THIS plan");
});
