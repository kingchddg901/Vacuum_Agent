// Unit tests for the pure derivation logic in the learning-state mixin. These cover the
// value-selection precedence in endLearningJob (measured actuals vs estimate/reanchored
// fallback, and the short-1-room-run bug it defends against), the job-active status
// membership test, the room-estimate reduce + count fallback, and the multi-source
// timeline / remaining / completed / banner derivations. All are pure over stubbed state.
// Run: node --test src/state/learning-derive.test.mjs
//
// Coverage targets:
//   [EXJ-*]  endLearningJob        — actual-vs-fallback total_minutes & rooms_completed,
//                                     summary-built guard, short-run completedRooms fallback
//   [DJA-*]  _dashboardJobIsActive — terminal boolean else status membership, empty->false
//   [RE-*]   setRoomEstimates / roomEstimateCount — reduce skip-null-id + room_count fallback
//   [RR-*]   learningRoomsRemainingCount — ids -> reanchored -> timeline !completed
//   [RC-*]   learningRoomsCompletedCount — ids -> reanchored -> completedRooms
//   [ALL-*]  learningAllCompleted  — terminal -> all_completed -> empty-nextRoom
//   [BAN-*]  learningLiveBannerRoom — current_room_id -> timeline.current -> nextRoom
//   [TL-*]   learningRoomTimeline  — dashboard -> planned -> reanchored/estimate
//   [CHG-*]  liveChargeStatus      — charge_* extraction, null when not charging, numeric null-safe
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyLearningState } from "./learning.js";

function makeState() {
  const proto = {};
  applyLearningState(proto);
  return Object.create(proto);
}

/* ============================================================
   liveChargeStatus — [CHG-*]
   ============================================================ */

test("[CHG-1] liveChargeStatus is null without an active charge phase", () => {
  const s = makeState();
  assert.equal(s.liveChargeStatus(), null); // no snapshot at all
  s.setDashboardSnapshot({ job_progress: { charge_phase_active: false } });
  assert.equal(s.liveChargeStatus(), null);
});

test("[CHG-2] liveChargeStatus extracts the charge fields + live battery when active", () => {
  const s = makeState();
  s.batteryLevel = () => 70;
  s.setDashboardSnapshot({ job_progress: {
    charge_phase_active: true, charge_target_percent: 95,
    charge_eta_minutes: 18, charge_from_battery: 62, charge_eta_source: "baseline",
  } });
  assert.deepEqual(s.liveChargeStatus(), {
    targetPercent: 95, etaMinutes: 18, fromBattery: 62, etaSource: "baseline", currentBattery: 70,
  });
});

test("[CHG-3] liveChargeStatus null-safes missing numeric fields (incl. absent battery)", () => {
  const s = makeState();
  s.setDashboardSnapshot({ job_progress: { charge_phase_active: true } });
  assert.deepEqual(s.liveChargeStatus(), {
    targetPercent: null, etaMinutes: null, fromBattery: null, etaSource: null, currentBattery: null,
  });
});

/* ============================================================
   endLearningJob — [EXJ-*]
   ============================================================ */

test("[EXJ-1] measured actuals win over estimate/reanchored predictions", () => {
  const s = makeState();
  s.setLearningEstimate({ total_minutes: 40 });
  s.beginLearningJob(); // reanchored = estimate (40)
  s.setLearningReanchored({ total_minutes: 55 });
  s.pushCompletedLearningRoom({ room_id: 1, actual_duration_minutes: 10 });
  s.pushCompletedLearningRoom({ room_id: 2, actual_duration_minutes: 12 });

  s.endLearningJob({ actual_cleaning_minutes: 33, room_count: 4 });

  const sum = s.learningSummary();
  // actualMinutes 33 finite & >0 -> wins over fallbackTotal 55
  assert.equal(sum.total_minutes, 33);
  // actualRoomCount 4 finite & >0 -> wins over completed.length (2)
  assert.equal(sum.rooms_completed, 4);
  // predicted_total_minutes tracks the fallback (reanchored 55)
  assert.equal(sum.predicted_total_minutes, 55);
});

test("[EXJ-2] duration_minutes is the second-choice actuals key when actual_cleaning_minutes absent", () => {
  const s = makeState();
  s.setLearningEstimate({ total_minutes: 40 });
  s.setLearningReanchored({ total_minutes: 50 });
  s.endLearningJob({ duration_minutes: 27 });
  assert.equal(s.learningSummary().total_minutes, 27);
});

test("[EXJ-3] no/zero override -> fallback total (reanchored preferred over estimate)", () => {
  const s = makeState();
  s.setLearningEstimate({ total_minutes: 40 });
  s.setLearningReanchored({ total_minutes: 50 });
  s.endLearningJob(); // no override
  // fallbackTotal = reanchored.total_minutes (50) preferred over estimate (40)
  assert.equal(s.learningSummary().total_minutes, 50);

  const s2 = makeState();
  s2.setLearningEstimate({ total_minutes: 40 });
  // reanchored null -> estimate.total_minutes used
  s2.endLearningJob({ actual_cleaning_minutes: 0 }); // 0 is not > 0 -> fallback
  assert.equal(s2.learningSummary().total_minutes, 40);
});

test("[EXJ-4] short-1-room-run: measured room_count rescues an empty completedRooms array", () => {
  // The documented bug: completedRooms can be [] on a fast 1-room run because the
  // room_finished event beat learningJobActive. The EVENT_JOB_FINISHED room_count
  // override must still report 1, not 0.
  const s = makeState();
  s.setLearningEstimate({ total_minutes: 12 });
  s.setLearningCompletedRooms([]); // empty despite a room having finished
  s.endLearningJob({ actual_cleaning_minutes: 11, room_count: 1 });
  const sum = s.learningSummary();
  assert.equal(sum.rooms_completed, 1);       // override rescues it (not 0)
  assert.equal(sum.total_minutes, 11);
});

test("[EXJ-5] rooms_completed falls back to completedRooms.length when no/zero override count", () => {
  const s = makeState();
  s.setLearningReanchored({ total_minutes: 30 });
  s.setLearningCompletedRooms([
    { room_id: 1, actual_duration_minutes: 5 },
    { room_id: 2, actual_duration_minutes: 6 },
    { room_id: 3, actual_duration_minutes: 7 },
  ]);
  // room_count 0 is not > 0 -> fall back to completed.length (3)
  s.endLearningJob({ actual_cleaning_minutes: 18, room_count: 0 });
  assert.equal(s.learningSummary().rooms_completed, 3);
});

test("[EXJ-6] summary-built guard: no estimate/reanchored/completed/override -> summary null", () => {
  const s = makeState();
  // clean state: estimate null, reanchored null, completedRooms [], no override
  s.endLearningJob();
  assert.equal(s.learningSummary(), null);
  assert.equal(s.hasLearningSummary(), false);
});

test("[EXJ-7] summary built when ONLY an override is present (no estimate/reanchored)", () => {
  const s = makeState();
  s.endLearningJob({ actual_cleaning_minutes: 9, room_count: 2 });
  const sum = s.learningSummary();
  assert.ok(sum);                                  // actualOverride truthy -> summary built
  assert.equal(sum.total_minutes, 9);
  assert.equal(sum.rooms_completed, 2);
  // no reanchored/estimate -> fallbackTotal 0 -> predicted stays null
  assert.equal(sum.predicted_total_minutes, null);
  assert.equal(sum.final_payload, null);
});

test("[EXJ-8] endLearningJob clears live-job state but preserves the estimate", () => {
  const s = makeState();
  s.setLearningEstimate({ total_minutes: 20 });
  s.beginLearningJob();
  s.setLearningReanchored({ total_minutes: 25, battery_warning: true });
  s.setLearningNextRoom({ room_id: 5 });
  s.pushCompletedLearningRoom({ room_id: 1, actual_duration_minutes: 8 });

  s.endLearningJob();

  const sum = s.learningSummary();
  assert.equal(sum.battery_warning, true);          // pulled off reanchored
  assert.deepEqual(sum.final_payload, { total_minutes: 25, battery_warning: true });
  // live-job state wiped
  assert.equal(s.learningJobActive(), false);
  assert.equal(s.learningReanchored(), null);
  assert.deepEqual(s.learningCompletedRooms(), []);
  assert.equal(s.learningNextRoom(), null);
  // estimate preserved
  assert.deepEqual(s.learningEstimate(), { total_minutes: 20 });
});

/* ============================================================
   _dashboardJobIsActive — [DJA-*]
   ============================================================ */

test("[DJA-1] terminal boolean short-circuits: !terminal", () => {
  const s = makeState();
  s.setDashboardSnapshot({ job_progress: { terminal: false, status: "completed" } });
  assert.equal(s._dashboardJobIsActive(), true);   // terminal false wins over status
  s.setDashboardSnapshot({ job_progress: { terminal: true, status: "cleaning" } });
  assert.equal(s._dashboardJobIsActive(), false);  // terminal true wins over active status
});

test("[DJA-2] no terminal boolean -> active status normalizes to active, terminal set inactive", () => {
  const s = makeState();
  s.setDashboardSnapshot({ job_progress: { status: "cleaning" } });
  assert.equal(s._dashboardJobIsActive(), true);
  for (const status of ["complete", "completed", "finished", "idle", "terminal", "not_started", "inactive"]) {
    s.setDashboardSnapshot({ job_progress: { status } });
    assert.equal(s._dashboardJobIsActive(), false, `status "${status}" should read inactive`);
  }
});

test("[DJA-3] status is trimmed + lowercased before membership test", () => {
  const s = makeState();
  s.setDashboardSnapshot({ job_progress: { status: "  COMPLETED  " } });
  assert.equal(s._dashboardJobIsActive(), false);
  s.setDashboardSnapshot({ job_progress: { status: "  Cleaning  " } });
  assert.equal(s._dashboardJobIsActive(), true);
});

test("[DJA-4] empty/absent status and missing progress -> false", () => {
  const s = makeState();
  s.setDashboardSnapshot({ job_progress: { status: "" } });
  assert.equal(s._dashboardJobIsActive(), false);   // empty status -> false
  s.setDashboardSnapshot({ job_progress: {} });
  assert.equal(s._dashboardJobIsActive(), false);   // no status field -> "" -> false
  s.setDashboardSnapshot({}); // no job_progress
  assert.equal(s._dashboardJobIsActive(), false);
  s.setDashboardSnapshot(null);
  assert.equal(s._dashboardJobIsActive(), false);
});

/* ============================================================
   setRoomEstimates / roomEstimateCount — [RE-*]
   ============================================================ */

test("[RE-1] setRoomEstimates reduces rooms[] to a room_id-keyed map, skipping null ids", () => {
  const s = makeState();
  s.setRoomEstimates({
    rooms: [
      { room_id: 3, minutes: 5 },
      { room_id: null, minutes: 9 },      // skipped
      { minutes: 4 },                      // no room_id -> skipped (== null)
      { room_id: 7, minutes: 6 },
    ],
  });
  const est = s.roomEstimates();
  assert.deepEqual(Object.keys(est).sort(), ["3", "7"]);
  assert.deepEqual(est["3"], { room_id: 3, minutes: 5 });
  assert.equal(s.hasRoomEstimates(), true);
  assert.deepEqual(s.roomEstimateForRoom("7"), { room_id: 7, minutes: 6 });
});

test("[RE-2] room_id 0 is a valid key (not == null)", () => {
  const s = makeState();
  s.setRoomEstimates({ rooms: [{ room_id: 0, minutes: 1 }] });
  assert.deepEqual(Object.keys(s.roomEstimates()), ["0"]);
});

test("[RE-3] roomEstimateCount prefers explicit room_count, else key count", () => {
  const s = makeState();
  // explicit room_count present -> used verbatim (even if != key count)
  s.setRoomEstimates({ room_count: 9, rooms: [{ room_id: 1 }, { room_id: 2 }] });
  assert.equal(s.roomEstimateCount(), 9);

  // room_count absent -> Number(undefined ?? keyLen) via `|| 0` stores keyLen (2)
  const s2 = makeState();
  s2.setRoomEstimates({ rooms: [{ room_id: 1 }, { room_id: 2 }] });
  assert.equal(s2.roomEstimateCount(), 2);
});

test("[RE-4] setRoomEstimates copies through the metadata fields", () => {
  const s = makeState();
  s.setRoomEstimates({
    rooms: [{ room_id: 1 }],
    stats_stale: true,
    stats_rebuilt_at: "t1",
    estimated_at: "t2",
    current_battery: 88,
    map_id: "map_6",
    vacuum_entity_id: "vacuum.alfred",
  });
  assert.equal(s.roomEstimatesStatsStale(), true);
  assert.equal(s.roomEstimatesStatsRebuiltAt(), "t1");
  assert.equal(s.roomEstimatesEstimatedAt(), "t2");
  const meta = s.roomEstimateMeta();
  assert.equal(meta.current_battery, 88);
  assert.equal(meta.map_id, "map_6");
  assert.equal(meta.vacuum_entity_id, "vacuum.alfred");
});

test("[RE-5] empty/missing rooms -> empty map, count 0", () => {
  const s = makeState();
  s.setRoomEstimates({}); // no rooms key
  assert.deepEqual(s.roomEstimates(), {});
  assert.equal(s.hasRoomEstimates(), false);
  assert.equal(s.roomEstimateCount(), 0);
});

/* ============================================================
   learningRoomsRemainingCount — [RR-*]
   ============================================================ */

test("[RR-1] remaining: dashboard remaining_room_ids length wins first", () => {
  const s = makeState();
  s.setDashboardSnapshot({ job_progress: { remaining_room_ids: [1, 2, 3] } });
  s.setLearningReanchored({ rooms_remaining: 99 }); // must be ignored
  assert.equal(s.learningRoomsRemainingCount(), 3);
});

test("[RR-2] remaining: reanchored.rooms_remaining used when no dashboard ids", () => {
  const s = makeState();
  s.setLearningReanchored({ rooms_remaining: 2 });
  assert.equal(s.learningRoomsRemainingCount(), 2);
});

test("[RR-3] remaining: final fallback counts timeline entries that are not completed", () => {
  const s = makeState();
  // no dashboard, reanchored has no rooms_remaining -> timeline !completed filter
  s.setLearningReanchored({
    room_timeline: [
      { room_id: 1, completed: true },
      { room_id: 2, completed: false },
      { room_id: 3 },                    // undefined -> !completed -> counted
    ],
  });
  assert.equal(s.learningRoomsRemainingCount(), 2);
});

/* ============================================================
   learningRoomsCompletedCount — [RC-*]
   ============================================================ */

test("[RC-1] completed: dashboard completed_room_ids length wins first", () => {
  const s = makeState();
  s.setDashboardSnapshot({ job_progress: { completed_room_ids: [1, 2] } });
  s.setLearningReanchored({ rooms_completed: 99 });
  assert.equal(s.learningRoomsCompletedCount(), 2);
});

test("[RC-2] completed: reanchored.rooms_completed then completedRooms.length", () => {
  const s = makeState();
  s.setLearningReanchored({ rooms_completed: 4 });
  assert.equal(s.learningRoomsCompletedCount(), 4);

  const s2 = makeState();
  s2.setLearningCompletedRooms([
    { room_id: 1, actual_duration_minutes: 3 },
    { room_id: 2, actual_duration_minutes: 4 },
  ]);
  assert.equal(s2.learningRoomsCompletedCount(), 2);
});

/* ============================================================
   learningAllCompleted — [ALL-*]
   ============================================================ */

test("[ALL-1] all-completed: dashboard terminal boolean is authoritative", () => {
  const s = makeState();
  s.setDashboardSnapshot({ job_progress: { terminal: true } });
  s.setLearningReanchored({ all_completed: false }); // ignored
  assert.equal(s.learningAllCompleted(), true);
  s.setDashboardSnapshot({ job_progress: { terminal: false } });
  assert.equal(s.learningAllCompleted(), false);
});

test("[ALL-2] all-completed: reanchored.all_completed when no dashboard terminal", () => {
  const s = makeState();
  s.setLearningReanchored({ all_completed: true });
  assert.equal(s.learningAllCompleted(), true);
});

test("[ALL-3] all-completed: empty-object nextRoom means done, non-empty means not", () => {
  const s = makeState();
  s.setLearningNextRoom({}); // empty object -> all completed
  assert.equal(s.learningAllCompleted(), true);

  const s2 = makeState();
  s2.setLearningNextRoom({ room_id: 5 }); // has keys -> not done
  assert.equal(s2.learningAllCompleted(), false);

  const s3 = makeState();
  // nextRoom null -> Boolean(null && ...) -> false
  assert.equal(s3.learningAllCompleted(), false);
});

/* ============================================================
   learningRoomTimeline — [TL-*]
   ============================================================ */

test("[TL-1] timeline: dashboard timeline wins over planned + reanchored", () => {
  const s = makeState();
  s.setDashboardSnapshot({
    job_progress: { timeline: [{ room_id: 1 }] },
    planned_job_estimate: { room_timeline: [{ room_id: 9 }] },
  });
  s.setLearningReanchored({ room_timeline: [{ room_id: 5 }] });
  assert.deepEqual(s.learningRoomTimeline(), [{ room_id: 1 }]);
});

test("[TL-2] timeline: planned_job_estimate.room_timeline is 2nd when dashboard empty", () => {
  const s = makeState();
  s.setDashboardSnapshot({
    job_progress: { timeline: [] },
    planned_job_estimate: { room_timeline: [{ room_id: 2 }, { room_id: 3 }] },
  });
  s.setLearningReanchored({ room_timeline: [{ room_id: 5 }] });
  assert.deepEqual(s.learningRoomTimeline(), [{ room_id: 2 }, { room_id: 3 }]);
});

test("[TL-3] timeline: reanchored then estimate when no dashboard/planned", () => {
  const s = makeState();
  s.setLearningReanchored({ room_timeline: [{ room_id: 7 }] });
  assert.deepEqual(s.learningRoomTimeline(), [{ room_id: 7 }]);

  const s2 = makeState();
  // reanchored null -> falls to estimate
  s2.setLearningEstimate({ room_timeline: [{ room_id: 8 }] });
  assert.deepEqual(s2.learningRoomTimeline(), [{ room_id: 8 }]);
});

test("[TL-4] timeline: nothing anywhere -> []", () => {
  const s = makeState();
  assert.deepEqual(s.learningRoomTimeline(), []);
});

/* ============================================================
   learningLiveBannerRoom — [BAN-*]
   ============================================================ */

test("[BAN-1] banner: dashboard current_room_id maps to its timeline entry (priority 1)", () => {
  const s = makeState();
  s.setDashboardSnapshot({
    job_progress: {
      current_room_id: 2,
      timeline: [{ room_id: 1 }, { room_id: 2, name: "Kitchen" }],
    },
  });
  s.setLearningNextRoom({ room_id: 9 }); // must be ignored
  assert.deepEqual(s.learningLiveBannerRoom(), { room_id: 2, name: "Kitchen" });
});

test("[BAN-2] banner: current_room_id with no matching timeline entry falls to timeline.current", () => {
  const s = makeState();
  // current_room_id 5 has no timeline entry -> currentEntry null -> try find(current)
  s.setDashboardSnapshot({
    job_progress: {
      current_room_id: 5,
      timeline: [{ room_id: 1 }, { room_id: 3, current: true, name: "Hall" }],
    },
  });
  assert.deepEqual(s.learningLiveBannerRoom(), { room_id: 3, current: true, name: "Hall" });
});

test("[BAN-3] banner: no current_room_id -> the timeline entry flagged current (priority 2)", () => {
  const s = makeState();
  s.setLearningReanchored({
    room_timeline: [{ room_id: 1 }, { room_id: 2, current: true }],
  });
  assert.deepEqual(s.learningLiveBannerRoom(), { room_id: 2, current: true });
});

test("[BAN-4] banner: no current anywhere -> falls back to nextRoom (priority 3)", () => {
  const s = makeState();
  s.setLearningReanchored({ room_timeline: [{ room_id: 1 }, { room_id: 2 }] });
  s.setLearningNextRoom({ room_id: 4, name: "Next up" });
  assert.deepEqual(s.learningLiveBannerRoom(), { room_id: 4, name: "Next up" });

  const s2 = makeState();
  // nothing at all -> nextRoom null
  assert.equal(s2.learningLiveBannerRoom(), null);
});
