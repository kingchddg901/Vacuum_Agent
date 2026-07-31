// Regression tests — two card accessors that reported the wrong thing because a new
// data source was prepended to a chain without checking it carried the field.
//
// [CENSUS-2] canPauseRun / canResumeRun derived Pause/Resume from the brand vacuum
//   entity's raw `state` string, which describes the ROBOT, not the JOB. During a
//   charge_wait / wait step the job stays "started" but the robot is docked, so both
//   read false and the Pause button vanished for the whole stop (can be an hour).
//   The backend computes can_pause / can_resume in job_control and the card ignored them.
//
// [CENSUS-1] learningBatteryWarning used `a ?? b ?? c`. `??` short-circuits on any
//   non-nullish operand — including an object that lacks the key. job_progress is always
//   emitted and does NOT carry battery_warning, so the two working branches behind it
//   were unreachable and the warning could never render, on any brand, in any run.
//
// Run: node --test src/state/affordance-and-warning.test.mjs
//
// Coverage (AW = Affordance/Warning):
//   [AW-1] Pause is offered during a charge stop (job started, robot docked)
//   [AW-2] Resume is offered when the backend says the job is paused
//   [AW-3] the entity-string fallback still works when job_control is absent (old backend)
//   [AW-4] battery warning renders from the re-anchor payload despite job_progress winning
//   [AW-5] job_progress still wins when it DOES carry the key
//   [AW-6] no source carrying the key -> false, not a throw

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyRoomsState } from "./rooms.js";
import { applyLearningState } from "./learning.js";

function makeCard({ snapshot = null, vacuumState = "docked", reanchored = null, estimate = null } = {}) {
  const proto = {};
  applyRoomsState(proto);
  applyLearningState(proto);
  const card = Object.create(proto);
  card.dashboardSnapshot = () => snapshot;
  card.vacuumState = () => vacuumState;
  card.learningReanchored = () => reanchored;
  card.learningEstimate = () => estimate;
  return card;
}

test("[AW-1] Pause is offered during a charge stop — job started, robot docked", () => {
  const card = makeCard({
    snapshot: { job_control: { can_pause: true, can_resume: false } },
    vacuumState: "docked",          // the robot is charging mid-run
  });
  assert.equal(card.canPauseRun(), true, "Pause disappeared during a charge stop");
  assert.equal(card.canResumeRun(), false);
});

test("[AW-2] Resume is offered when the backend says the job is paused", () => {
  const card = makeCard({
    snapshot: { job_control: { can_pause: false, can_resume: true } },
    vacuumState: "docked",
  });
  assert.equal(card.canResumeRun(), true);
  assert.equal(card.canPauseRun(), false);
});

test("[AW-3] falls back to the entity string when job_control is absent", () => {
  const cleaning = makeCard({ snapshot: {}, vacuumState: "cleaning" });
  assert.equal(cleaning.canPauseRun(), true, "old-backend fallback lost the button");

  const paused = makeCard({ snapshot: {}, vacuumState: "paused" });
  assert.equal(paused.canResumeRun(), true);
});

test("[AW-4] battery warning renders from re-anchor even though job_progress is non-null", () => {
  const card = makeCard({
    // job_progress is ALWAYS emitted and does NOT carry battery_warning
    snapshot: { job_progress: { terminal: false, rooms_completed: 2 } },
    reanchored: { battery_warning: true },
  });
  assert.equal(card.learningBatteryWarning(), true, "the warning is still unreachable");
});

test("[AW-5] job_progress still wins when it DOES carry the key", () => {
  const card = makeCard({
    snapshot: { job_progress: { battery_warning: false } },
    reanchored: { battery_warning: true },
  });
  assert.equal(card.learningBatteryWarning(), false, "source precedence was inverted");
});

test("[AW-6] no source carrying the key returns false rather than throwing", () => {
  const card = makeCard({ snapshot: { job_progress: {} } });
  assert.equal(card.learningBatteryWarning(), false);
});
