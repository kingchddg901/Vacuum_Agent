// Unit tests for renderStepsManifest — the pure "Runs As" step→HTML helper shared
// by the command-center run-profiles panel and the standalone profile card. These
// pin the per-step-type rendering (charge_wait / wait / room_group), the defaults,
// the room-name lookup + fallback, and the single-vs-mixed clean-mode hint, so the
// two surfaces can't drift.
// Run: node --test src/state/steps-manifest.test.mjs
//
// Coverage targets:
//   [SM-empty]  no/empty/non-array steps -> ""
//   [SM-charge] charge_wait -> ⚡ + target (default 95)
//   [SM-wait]   wait -> ⏱ + minutes (default 30) + unit
//   [SM-room]   room_group -> named rooms via nameById, room_fallback otherwise
//   [SM-mode]   single clean_mode -> mode chip; mixed -> no chip
//   [SM-wrap]   wrapper carries the runs_as label + the ordered list
import { test } from "node:test";
import assert from "node:assert/strict";
import { renderStepsManifest } from "./steps-manifest.js";

// Recognizable stubs: t() echoes the key's leaf (and appends an interpolated id),
// escapeHtml is identity so assertions read the raw values.
const t = (key, vars) => {
  const leaf = String(key).replace("run_profiles.", "");
  if (vars && vars.id != null) return `${leaf}:${vars.id}`;
  return leaf;
};
const escapeHtml = (s) => String(s);
const render = (steps, nameById = {}) => renderStepsManifest({ steps, nameById, t, escapeHtml });

/* ---- [SM-empty] ---- */
test("[SM-empty] no steps / empty / non-array -> empty string", () => {
  assert.equal(render([]), "");
  assert.equal(render(null), "");
  assert.equal(render(undefined), "");
  assert.equal(render("nope"), "");
});

/* ---- [SM-charge] ---- */
test("[SM-charge] charge_wait renders the bolt + target percent", () => {
  const out = render([{ type: "charge_wait", target_battery_percent: 80 }]);
  assert.match(out, /⚡/);
  assert.match(out, /step_charge_to/);
  assert.match(out, /80%/);
  assert.match(out, /evcc-run-profiles-seq-step--charge/);
});

test("[SM-charge] charge_wait defaults to 95 when target missing", () => {
  assert.match(render([{ type: "charge_wait" }]), /95%/);
});

/* ---- [SM-wait] ---- */
test("[SM-wait] wait renders the clock + minutes + unit", () => {
  const out = render([{ type: "wait", wait_minutes: 45 }]);
  assert.match(out, /⏱/);
  assert.match(out, /step_wait/);
  assert.match(out, /45/);
  assert.match(out, /minutes_unit/);
  assert.match(out, /evcc-run-profiles-seq-step--wait/);
});

test("[SM-wait] wait defaults to 30 when minutes missing", () => {
  assert.match(render([{ type: "wait" }]), /\b30\b/);
});

/* ---- [SM-room] ---- */
test("[SM-room] room_group uses nameById for known rooms", () => {
  const out = render(
    [{ type: "room_group", rooms: [{ room_id: 1 }, { room_id: 2 }] }],
    { 1: "Kitchen", 2: "Living Room" }
  );
  assert.match(out, /step_clean/);
  assert.match(out, /Kitchen/);
  assert.match(out, /Living Room/);
});

test("[SM-room] room_group falls back to room_fallback for unknown ids", () => {
  const out = render([{ type: "room_group", rooms: [{ room_id: 9 }] }], {});
  assert.match(out, /room_fallback:9/);
});

test("[SM-room] empty room_group shows the empty-group label", () => {
  const out = render([{ type: "room_group", rooms: [] }]);
  assert.match(out, /step_group_empty/);
});

/* ---- [SM-mode] ---- */
test("[SM-mode] a single shared clean_mode renders a mode chip", () => {
  const out = render(
    [{ type: "room_group", rooms: [{ room_id: 1, clean_mode: "Vacuum" }] }],
    { 1: "Kitchen" }
  );
  assert.match(out, /evcc-run-profiles-seq-mode/);
  assert.match(out, /Vacuum/);
});

test("[SM-mode] mixed clean_modes render NO mode chip", () => {
  const out = render(
    [{ type: "room_group", rooms: [{ room_id: 1, clean_mode: "Vacuum" }, { room_id: 2, clean_mode: "Mop" }] }],
    { 1: "Kitchen", 2: "Bath" }
  );
  assert.doesNotMatch(out, /evcc-run-profiles-seq-mode/);
});

/* ---- [SM-wrap] ---- */
test("[SM-wrap] wrapper carries the runs_as label + ordered list", () => {
  const out = render([{ type: "charge_wait", target_battery_percent: 100 }]);
  assert.match(out, /evcc-run-profiles-sequence/);
  assert.match(out, /runs_as/);
  assert.match(out, /<ol class="evcc-run-profiles-seq-list">/);
});

test("[SM-wrap] steps render in order", () => {
  const out = render([
    { type: "wait", wait_minutes: 10 },
    { type: "room_group", rooms: [{ room_id: 1 }] },
    { type: "charge_wait", target_battery_percent: 90 },
  ], { 1: "Kitchen" });
  const waitAt = out.indexOf("minutes_unit");
  const cleanAt = out.indexOf("Kitchen");
  const chargeAt = out.indexOf("90%");
  assert.ok(waitAt < cleanAt && cleanAt < chargeAt, "steps should render wait -> clean -> charge in order");
});
