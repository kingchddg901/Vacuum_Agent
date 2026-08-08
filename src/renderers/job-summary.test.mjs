// Run: node --test src/renderers/job-summary.test.mjs
//
// Job Summary modal. The surface that closes the gap between the job JSON and the
// history row: the row said "3 errors" and everything else lived in a file only
// someone who knows it exists would open.
//
// Coverage (JS = Job Summary):
//   [JS-1]  a vanished job closes the modal instead of freezing a stale copy
//   [JS-2]  in-card controls (Exclude/reason chips) do NOT also open the modal
//   [JS-3]  the card body and the error badge open the SAME surface
//   [JS-4]  absent values are OMITTED, never rendered as a confident 0
//   [JS-5]  both cleaning times survive; identical ones collapse to one
//   [JS-6]  per-room battery is never surfaced
//   [JS-7]  an unrecovered fault never claims it stopped the run
//   [JS-8]  a room with settings and no result reads as "not reached"
//   [JS-9]  the recharge line appears only when a recharge is indicated
//   [JS-10] an unlabelled fault falls back to the RAW code

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyJobSummaryState } from "../state/job-summary.js";

/** Minimal state host with the accessors the modal reads. */
function makeState(jobs) {
  const proto = {};
  applyJobSummaryState(proto);
  const state = Object.create(proto);
  state.learningHistoryJobs = () => jobs;
  return state;
}

const JOB = {
  job_id: "job-1",
  origin: "internal",
  run_errors: [
    { code: 1, label_key: "fault.eufy.bumper_stuck", source: "robot", recovered: true },
    { code: 6021, label_key: null, source: "dock", recovered: false },
  ],
  room_detail: [
    { room_id: 5, slug: "kitchen", name: "Kitchen", settings: { fan_speed: "max" },
      cleaning_seconds: 1050, cleaning_wall_seconds: 1065, area_m2: 12.5, has_result: true },
    { room_id: 8, slug: "hall", name: "Hall", settings: { fan_speed: "quiet" },
      cleaning_seconds: null, cleaning_wall_seconds: null, area_m2: null, has_result: false },
  ],
  recharge: { observed: true, count: 1, seconds: 6059, recovered_from_stale_record: true },
};

test("[JS-1] a job that leaves the snapshot closes the modal, not freezes it", () => {
  const state = makeState([JOB]);
  state.openJobSummary("job-1");
  assert.equal(state.activeJobSummary()?.job_id, "job-1");

  // The history snapshot is refetched on a poll. Holding a job OBJECT would keep
  // rendering a copy that no longer exists; holding the id means the lookup fails
  // and the renderer returns "".
  state.learningHistoryJobs = () => [];
  assert.equal(state.activeJobSummary(), null);
  assert.deepEqual(state.jobSummaryFaults(), []);
  assert.deepEqual(state.jobSummaryRooms(), []);
  assert.equal(state.jobSummaryRecharge(), null);
});

test("[JS-9] the recharge line appears only when a recharge is indicated", () => {
  const state = makeState([JOB, { job_id: "clean", recharge: null },
                           { job_id: "zeroed", recharge: { observed: false, count: 0 } }]);
  state.openJobSummary("job-1");
  assert.equal(state.jobSummaryRecharge()?.count, 1);

  // A run that did not recharge must render NOTHING, not "recharged 0 times".
  state.openJobSummary("clean");
  assert.equal(state.jobSummaryRecharge(), null);
  state.openJobSummary("zeroed");
  assert.equal(state.jobSummaryRecharge(), null, "observed:false leaked through");
});

test("[JS-state] malformed payloads yield empty lists rather than throwing", () => {
  for (const bad of [
    { job_id: "b1", run_errors: null, room_detail: "nope" },
    { job_id: "b2", run_errors: [null, 7, "junk"], room_detail: [null, "x"] },
    { job_id: "b3" },
  ]) {
    const state = makeState([bad]);
    state.openJobSummary(bad.job_id);
    assert.ok(Array.isArray(state.jobSummaryFaults()));
    assert.ok(Array.isArray(state.jobSummaryRooms()));
    assert.equal(state.jobSummaryFaults().every((r) => r && typeof r === "object"), true);
  }
});

// W0 v2 (2026-08-07): the HAPPY path of both list accessors was unmeasured across
// the WHOLE node suite. The two assertion sites above only ever saw an empty list
// — JS-1 checks `[]` after the job leaves the snapshot, and JS-state's `.every()`
// is vacuously true on the malformed fixtures' `[]`. Meanwhile the JOB fixture has
// carried two faults and two rooms all along, asserted nowhere.
// Measured, not assumed: renaming `run_errors` -> `runErrors` in
// state/job-summary.js:66 left 935/935 node tests GREEN, with the modal's entire
// fault section rendering nothing. Same for `room_detail` at :73.
test("[JS-11] the fault and room lists actually carry the job's rows through", () => {
  const state = makeState([JOB]);
  state.openJobSummary("job-1");

  // Faults: both rows, in order, with the fields the modal reads. label_key is
  // deliberately null on the second — the raw-code fallback (JS-10) depends on
  // that reaching the renderer rather than being filtered out here.
  assert.deepEqual(state.jobSummaryFaults(), JOB.run_errors);
  assert.equal(state.jobSummaryFaults().length, 2);
  assert.equal(state.jobSummaryFaults()[0].label_key, "fault.eufy.bumper_stuck");
  assert.equal(state.jobSummaryFaults()[1].label_key, null);
  assert.equal(state.jobSummaryFaults()[1].source, "dock");

  // Rooms: both rows, including the not-reached one whose absent values JS-4/JS-8
  // rely on being present-but-null rather than dropped.
  assert.deepEqual(state.jobSummaryRooms(), JOB.room_detail);
  assert.deepEqual(state.jobSummaryRooms().map((r) => r.slug), ["kitchen", "hall"]);
  assert.equal(state.jobSummaryRooms()[0].cleaning_seconds, 1050);
  assert.equal(state.jobSummaryRooms()[1].has_result, false);
  assert.equal(state.jobSummaryRooms()[1].area_m2, null);
});

test("[JS-external] an app-started run is identified so its thinner modal reads as expected", () => {
  const state = makeState([{ job_id: "x", origin: "external" }, { job_id: "y", origin: null }]);
  state.openJobSummary("x");
  assert.equal(state.jobSummaryIsExternal(), true);
  state.openJobSummary("y");
  assert.equal(state.jobSummaryIsExternal(), false);
});

/* ---------------------------------------------------------------------------
 * The in-card control guard, transcribed from bindings/job-summary.js.
 * The job card became clickable, and the Exclude/reason controls inside it do NOT
 * stop propagation — verified in the source, and an earlier draft of that file
 * claimed the opposite. Without this guard, excluding a job also opens the modal.
 * ------------------------------------------------------------------------- */
const INTERACTIVE_INSIDE_CARD =
  "[data-review-action],[data-review-reason-chip],button,a,input,select,textarea,label";

function fromInnerControl(event) {
  const target = event.target;
  if (!target || typeof target.closest !== "function") return false;
  const hit = target.closest(INTERACTIVE_INSIDE_CARD);
  return !!hit && hit !== event.currentTarget;
}

/** Fake element whose closest() answers from a declared match. */
function fakeEvent({ match = null, currentTarget = { card: true } } = {}) {
  const target = { closest: (sel) => (match && sel === INTERACTIVE_INSIDE_CARD ? match : null) };
  return { target, currentTarget };
}

test("[JS-2] clicking Exclude or a reason chip does NOT open the modal", () => {
  for (const control of [{ tag: "exclude" }, { tag: "chip" }]) {
    assert.equal(fromInnerControl(fakeEvent({ match: control })), true,
      "an in-card control leaked through and would open the modal");
  }
});

test("[JS-2b] a click on the card body itself still opens it", () => {
  assert.equal(fromInnerControl(fakeEvent({ match: null })), false);
  // The card is the currentTarget; if closest() returns the card itself that is
  // NOT an inner control and must not be swallowed.
  const card = { card: true };
  assert.equal(fromInnerControl(fakeEvent({ match: card, currentTarget: card })), false);
});

test("[JS-2c] a target with no closest() is handled, not thrown on", () => {
  assert.equal(fromInnerControl({ target: {}, currentTarget: {} }), false);
  assert.equal(fromInnerControl({ target: null, currentTarget: {} }), false);
});

test("[JS-2d] the REAL binding still applies that guard, on both handlers", async () => {
  // JS-2/2b/2c exercise a transcribed copy, so they would happily pass while the
  // shipped binding had the guard removed. This is the half that notices — and it
  // matters because without the guard, excluding a job also opens the modal.
  const fs = await import("node:fs");
  const src = fs.readFileSync(
    new URL("../bindings/job-summary.js", import.meta.url), "utf-8");

  const guards = src.match(/if \(fromInnerControl\(e\)\) return;/g) ?? [];
  assert.equal(guards.length, 2,
    `expected the guard on BOTH the click and keydown handlers, found ${guards.length}`);
  // And the selector must still cover the controls that actually sit in the card.
  for (const sel of ["data-review-action", "data-review-reason-chip", "button"]) {
    assert.ok(src.includes(sel), `guard selector no longer covers ${sel}`);
  }
});

/* ---------------------------------------------------------------------------
 * Source-level guarantees. These read the renderer rather than executing it,
 * because the pieces below are single lines whose ABSENCE is the bug.
 * ------------------------------------------------------------------------- */

test("[JS-3] the row and the error badge open the same surface", async () => {
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("./review.js", import.meta.url), "utf-8");
  // One attribute name, used for the card. A separate error modal would show up
  // here as a second, different action.
  assert.match(src, /data-job-summary-open="\$\{this\.escapeHtml\(jobId\)\}"/);
  assert.ok(!src.includes("open-error-modal"), "a separate error modal appeared");
  // Keyboard reachability: a div behaving as a button must say so.
  assert.match(src, /role="button"/);
  assert.match(src, /tabindex="0"/);
});

test("[JS-4] absent values are omitted, never rendered as a confident zero", async () => {
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("./job-summary.js", import.meta.url), "utf-8");
  // REV-6: Number(null) is 0 AND finite, so isFinite alone let an ABSENT battery
  // render as "Battery 0". The null check must come first.
  assert.match(src, /job\.battery_used != null && Number\.isFinite/);
  // Area and durations are gated on > 0, not merely finite.
  assert.match(src, /Number\.isFinite\(area\) && area > 0/);
});

test("[JS-5] both cleaning times survive, and identical ones do not double up", async () => {
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("./job-summary.js", import.meta.url), "utf-8");
  assert.match(src, /room_cleaning/);
  assert.match(src, /room_elapsed/);
  // They differ on 110 of 113 real entries; when they DO match, showing both is noise.
  assert.match(src, /ws !== cs/);
});

test("[JS-6] per-room battery is never surfaced", async () => {
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("./job-summary.js", import.meta.url), "utf-8");
  // It exists on the row and does not reconcile with the job total (7 of 28 jobs
  // agree). Rendering it would make the modal contradict its own header.
  assert.ok(!/battery_delta/.test(src), "per-room battery reached the modal");
});

test("[JS-7] an unrecovered fault never claims it stopped the run", async () => {
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("./job-summary.js", import.meta.url), "utf-8");
  assert.match(src, /job_summary\.not_recovered/);
  // Nothing in the record establishes causation, so these must not appear.
  for (const forbidden of ["job_stopped", "ended_the_run", "caused_failure"]) {
    assert.ok(!src.includes(forbidden), `${forbidden} asserts a cause we cannot support`);
  }
});

test("[JS-8] a room with settings but no result reads as not reached", async () => {
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("./job-summary.js", import.meta.url), "utf-8");
  assert.match(src, /job_summary\.room_no_result/);
});

test("[JS-10] an unlabelled fault falls back to the raw code", async () => {
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("./job-summary.js", import.meta.url), "utf-8");
  // faultLabel(key, code) already implements the fallback; the modal must pass the
  // CODE through rather than resolving the key alone and rendering a blank.
  assert.match(src, /this\.faultLabel\(f\.label_key, f\.code\)/);
});
