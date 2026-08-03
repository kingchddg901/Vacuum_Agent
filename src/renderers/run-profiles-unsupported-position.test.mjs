// Regression test — CARD-6 clause (1) display half (Q17, carried A5-PP-RP-5),
// the part the verifier caught still missing after the state-layer fix landed:
// insertChargeStep/insertWaitStep now refuse a NEW leading/trailing break, and
// sanitizeStepsForSave strips one silently at save time -- but a LEGACY profile
// (saved before that refusal existed, or hand-edited) can still carry a
// charge_wait/wait already sitting at index 0 or the very end when it is loaded
// into the steps editor. Until now, _renderRunProfileStepsEditor
// (renderers/run-profiles.js) rendered that step as a completely ordinary,
// editable row -- ZERO position-awareness, ZERO strikethrough, ZERO "will be
// skipped" text -- so the user has no on-screen indication it will be silently
// dropped the moment they save. That is exactly the failure mode the packet's
// required_behavior text says must never happen: "a legacy profile carrying one
// renders the step struck-through with 'will be skipped (unsupported
// position)' ... never a silently-shown step that won't run."
//
// Run: node --test src/renderers/run-profiles-unsupported-position.test.mjs
//
// NOTE: the packet's own proof line also calls for a render-harness VISUAL=1
// screenshot check ("draw overlay + struck step"). This sandbox cannot reach
// the Playwright/docker image that check needs, so this file substitutes a
// string-level assertion on the rendered HTML (class + i18n key), matching
// this codebase's existing renderer-test convention (see
// room-estimate-allocated.test.mjs). The VISUAL=1 repin itself is a separate,
// still-open follow-up -- NOT satisfied by this file.

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyRunProfilesRenderers } from "./run-profiles.js";

function makeCard() {
  const proto = {};
  applyRunProfilesRenderers(proto);
  const card = Object.create(proto);
  card.t = (key, vars) => `T:${key}${vars ? `:${JSON.stringify(vars)}` : ""}`;
  card.tVocabRaw = (field, val, fallback) => fallback;
  card.escapeHtml = (s) => String(s);
  card.card = { _state: { savedZones: () => [] } };
  return card;
}

function makeState(steps) {
  return {
    runProfileDraftSteps: () => steps,
    isDraftStepsExpanded: () => true,
    getRoomsForActiveMap: () => [{ id: 1, name: "Kitchen" }, { id: 2, name: "Hall" }],
  };
}

const rg = (...ids) => ({ type: "room_group", rooms: ids.map((room_id) => ({ room_id })) });

test("[RUB-1] a legacy LEADING charge_wait renders struck-through with the unsupported-position note", () => {
  const card = makeCard();
  const steps = [{ type: "charge_wait", target_battery_percent: 80 }, rg(1)];
  const html = card._renderRunProfileStepsEditor(makeState(steps));

  assert.match(
    html,
    /evcc-run-profiles-step--unsupported/,
    "a legacy leading charge_wait renders as an ordinary row -- no strikethrough class at all"
  );
  assert.match(
    html,
    /T:run_profiles\.step_unsupported_position/,
    "no 'will be skipped (unsupported position)' note rendered for the leading break"
  );
});

test("[RUB-2] a legacy TRAILING wait renders struck-through with the unsupported-position note", () => {
  const card = makeCard();
  const steps = [rg(1), { type: "wait", wait_minutes: 30 }];
  const html = card._renderRunProfileStepsEditor(makeState(steps));

  assert.match(html, /evcc-run-profiles-step--unsupported/);
  assert.match(html, /T:run_profiles\.step_unsupported_position/);
});

test("[RUB-3] a MIDDLE charge_wait (control, ordinary supported case) is NOT flagged", () => {
  const card = makeCard();
  const steps = [rg(1), { type: "charge_wait", target_battery_percent: 95 }, rg(2)];
  const html = card._renderRunProfileStepsEditor(makeState(steps));

  assert.doesNotMatch(
    html,
    /evcc-run-profiles-step--unsupported/,
    "an ordinary mid-sequence charge_wait must not be struck-through -- it will actually run"
  );
  assert.doesNotMatch(html, /T:run_profiles\.step_unsupported_position/);
});
