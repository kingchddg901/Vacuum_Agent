// Unit tests for LearningController's two PURE progress methods:
//   - getRoomProgressSnapshot(roomId): per-room live snapshot. Prefers the backend
//     timeline entry (state.learningTimelineEntryForRoom) when it carries real
//     progress; otherwise falls back to the local reanchored/estimate room_timeline
//     with a currentRoomStartedAt-driven elapsed for the current room.
//   - _computeProgressPercent(): overall smooth % = (completedRoomMinutes +
//     min(elapsedInCurrentRoom, currentRoomEstimatedMinutes)) / totalEstimatedMinutes,
//     floored, clamped [0,99]; total<=0 -> 0; elapsed clamped >=0.
//
// Coverage targets:
//   [LRN-1..6]  getRoomProgressSnapshot  (backend path: has-progress gate, percent
//               100-when-completed / floor+clamp / current-0 fallback, estimated &
//               remaining derivation, skipped/running_long flags)
//   [LRN-7..11] getRoomProgressSnapshot  (local path: missing entry -> null,
//               completed 100%, not-current stub, current-room elapsed math, precedence
//               reanchored-over-estimate)
//   [LRN-12..16] _computeProgressPercent (blend, current-room cap, total<=0 -> 0,
//               null startedAt -> 0 elapsed, floor+clamp to 99)
//
// The two methods only read `this.card._state.*` (stubbed), `this._jobProgress.*`
// (set directly), and Date.now(). No hass / timer / subscription side effects are
// touched, so a bare prototype instance reaches them.
//
// Run: node --test src/controllers/learning-controller-progress.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { LearningController } from "./learning-controller.js";

// --- harness ---------------------------------------------------------------

// A minimal controller: prototype methods, hand-set _jobProgress + a stub card._state.
// `state` overrides supply only the methods the target actually calls.
function makeController({ state = {}, jobProgress = {} } = {}) {
  const lc = Object.create(LearningController.prototype);
  lc._jobProgress = {
    totalEstimatedMinutes: 0,
    completedRoomMinutes: 0,
    currentRoomStartedAt: null,
    currentRoomEstimatedMinutes: 0,
    percent: 0,
    ticker: null,
    ...jobProgress,
  };
  lc.card = { _state: state };
  return lc;
}

// A state stub whose learningTimelineEntryForRoom returns `backendEntry` and whose
// reanchored/estimate timelines are supplied directly.
function makeState({ backendEntry, reanchoredTimeline, estimateTimeline } = {}) {
  return {
    learningTimelineEntryForRoom: () =>
      backendEntry === undefined ? null : backendEntry,
    learningReanchored: () =>
      reanchoredTimeline === undefined ? null : { room_timeline: reanchoredTimeline },
    learningEstimate: () =>
      estimateTimeline === undefined ? null : { room_timeline: estimateTimeline },
  };
}

// =========================================================================
// getRoomProgressSnapshot — BACKEND path
// =========================================================================

test("[LRN-1] backend entry with progress_percent: floored + clamped to 99, flags passed through", () => {
  const lc = makeController({
    state: makeState({
      backendEntry: {
        current: true,
        completed: false,
        skipped: false,
        running_long: true,
        progress_percent: 42.9,
        minutes: 10,
        elapsed_minutes: 4.3,
        remaining_minutes: 5.7,
      },
    }),
  });
  const snap = lc.getRoomProgressSnapshot(3);
  assert.equal(snap.isCurrent, true);
  assert.equal(snap.isCompleted, false);
  assert.equal(snap.isSkipped, false);
  assert.equal(snap.isRunningLong, true);         // running_long flag surfaced
  assert.equal(snap.percent, 42);                 // 42.9 -> floor 42, within [0,99]
  assert.equal(snap.elapsedMinutes, 4.3);
  assert.equal(snap.estimatedMinutes, 10);        // minutes wins
  assert.equal(snap.remainingMinutes, 5.7);
});

test("[LRN-2] backend entry completed: percent snaps to 100 and remaining forced to 0", () => {
  const lc = makeController({
    state: makeState({
      backendEntry: {
        completed: true,
        current: false,
        // progress_percent deliberately low + remaining nonzero — must be overridden
        progress_percent: 30,
        minutes: 8,
        elapsed_minutes: 8,
        remaining_minutes: 3,
      },
    }),
  });
  const snap = lc.getRoomProgressSnapshot(1);
  assert.equal(snap.isCompleted, true);
  assert.equal(snap.percent, 100);                // completed overrides the 30
  assert.equal(snap.remainingMinutes, 0);         // completed forces 0
  assert.equal(snap.estimatedMinutes, 8);
});

test("[LRN-3] backend percent clamps a >=100 raw value down to 99 (not-yet-completed guard)", () => {
  const lc = makeController({
    state: makeState({
      backendEntry: { current: true, completed: false, progress_percent: 150, minutes: 5 },
    }),
  });
  // 150 floored is 150, clamped to 99 — a running room must never read 100.
  assert.equal(lc.getRoomProgressSnapshot(2).percent, 99);
});

test("[LRN-4] backend entry with NO progress signal falls through to local timeline", () => {
  // hasBackendProgress = progressPercent finite OR current OR completed OR remaining.
  // Here all are absent/false, so the backend branch is skipped even though the entry exists.
  const lc = makeController({
    state: makeState({
      backendEntry: { current: false, completed: false, remaining: false }, // no progress_percent
      estimateTimeline: [{ room_id: 9, minutes: 6, completed: false }],
    }),
  });
  const snap = lc.getRoomProgressSnapshot(9);
  // Fell through to local: room 9 is the first !completed -> current room, startedAt null -> elapsed 0.
  assert.equal(snap.isCurrent, true);
  assert.equal(snap.elapsedMinutes, 0);
  assert.equal(snap.estimatedMinutes, 6);
});

test("[LRN-5] backend estimated derives from elapsed+remaining when minutes absent; remaining falls back to estimated", () => {
  const lc = makeController({
    state: makeState({
      backendEntry: {
        current: true,
        completed: false,
        progress_percent: 20,
        // no `minutes` -> estimated = elapsed + remaining = 2 + 3 = 5
        elapsed_minutes: 2,
        remaining_minutes: 3,
      },
    }),
  });
  const snap = lc.getRoomProgressSnapshot(4);
  assert.equal(snap.estimatedMinutes, 5);
  assert.equal(snap.remainingMinutes, 3);         // remaining finite -> used directly
});

test("[LRN-6] backend entry qualified only by `remaining` truthiness; non-finite percent on non-current -> 0", () => {
  // current=false, completed=false, no progress_percent, but remaining truthy -> qualifies.
  const lc = makeController({
    state: makeState({
      backendEntry: {
        current: false,
        completed: false,
        remaining: true,
        minutes: 7,
        // progress_percent absent (NaN) -> percent branch: not completed, not finite -> 0
      },
    }),
  });
  const snap = lc.getRoomProgressSnapshot(5);
  assert.equal(snap.percent, 0);
  assert.equal(snap.isCurrent, false);
  assert.equal(snap.estimatedMinutes, 7);
  // remaining_minutes non-finite, estimated finite (7) -> remaining falls back to estimated
  assert.equal(snap.remainingMinutes, 7);
});

// =========================================================================
// getRoomProgressSnapshot — LOCAL timeline path
// =========================================================================

test("[LRN-7] no backend entry + room not in local timeline -> null", () => {
  const lc = makeController({
    state: makeState({
      backendEntry: undefined,                    // -> null
      estimateTimeline: [{ room_id: 1, minutes: 5, completed: false }],
    }),
  });
  assert.equal(lc.getRoomProgressSnapshot(99), null);
});

test("[LRN-8] local completed room: 100%, elapsed = actual (else estimated), remaining 0", () => {
  const lc = makeController({
    state: makeState({
      estimateTimeline: [
        { room_id: 1, minutes: 5, completed: true, actual_duration_minutes: 6.5 },
        { room_id: 2, minutes: 4, completed: false },
      ],
    }),
  });
  const snap = lc.getRoomProgressSnapshot("1");    // string roomId matches numeric room_id
  assert.equal(snap.isCompleted, true);
  assert.equal(snap.percent, 100);
  assert.equal(snap.elapsedMinutes, 6.5);          // actual wins over estimated
  assert.equal(snap.estimatedMinutes, 5);
  assert.equal(snap.remainingMinutes, 0);
});

test("[LRN-9] local completed room with no actual falls back to estimated for elapsed", () => {
  const lc = makeController({
    state: makeState({
      estimateTimeline: [{ room_id: 7, minutes: 9, completed: true }], // no actual_duration_minutes
    }),
  });
  const snap = lc.getRoomProgressSnapshot(7);
  assert.equal(snap.elapsedMinutes, 9);            // actual NaN -> estimated
});

test("[LRN-10] local not-yet-current room (a later queued room): 0% stub, est/remaining = minutes", () => {
  const lc = makeController({
    state: makeState({
      estimateTimeline: [
        { room_id: 1, minutes: 5, completed: false }, // current (first !completed)
        { room_id: 2, minutes: 4, completed: false }, // queued, not current
      ],
    }),
  });
  const snap = lc.getRoomProgressSnapshot(2);
  assert.equal(snap.isCurrent, false);
  assert.equal(snap.isCompleted, false);
  assert.equal(snap.percent, 0);
  assert.equal(snap.elapsedMinutes, 0);
  assert.equal(snap.estimatedMinutes, 4);
  assert.equal(snap.remainingMinutes, 4);
});

test("[LRN-11] local current room: elapsed from currentRoomStartedAt, percent floor/clamp, remaining=max(0,est-elapsed)", () => {
  // startedAt 3 minutes ago, estimated 10 -> elapsed 3, percent floor(30)=30, remaining 7.
  const startedAt = Date.now() - 3 * 60000;
  const lc = makeController({
    state: makeState({
      estimateTimeline: [{ room_id: 5, minutes: 10, completed: false }],
    }),
    jobProgress: { currentRoomStartedAt: startedAt },
  });
  const snap = lc.getRoomProgressSnapshot(5);
  assert.equal(snap.isCurrent, true);
  assert.equal(snap.estimatedMinutes, 10);
  assert.ok(Math.abs(snap.elapsedMinutes - 3) < 0.05, `elapsed ~3, got ${snap.elapsedMinutes}`);
  assert.equal(snap.percent, 30);                  // floor(3/10*100)
  assert.ok(Math.abs(snap.remainingMinutes - 7) < 0.05, `remaining ~7, got ${snap.remainingMinutes}`);
});

test("[LRN-11b] local current room overshoot: percent clamps to 99, remaining floors at 0", () => {
  // startedAt 20 min ago, estimated 5 -> elapsed 20 -> raw pct 400 clamp 99, remaining max(0,-15)=0.
  const lc = makeController({
    state: makeState({
      reanchoredTimeline: [{ room_id: 5, minutes: 5, completed: false }],
    }),
    jobProgress: { currentRoomStartedAt: Date.now() - 20 * 60000 },
  });
  const snap = lc.getRoomProgressSnapshot(5);
  assert.equal(snap.percent, 99);                  // never 100 for a running room
  assert.equal(snap.remainingMinutes, 0);          // clamped >= 0
});

test("[LRN-12] reanchored timeline takes precedence over estimate timeline", () => {
  // Same room in both; reanchored marks it completed, estimate marks it current.
  const lc = makeController({
    state: makeState({
      reanchoredTimeline: [{ room_id: 5, minutes: 5, completed: true, actual_duration_minutes: 4 }],
      estimateTimeline: [{ room_id: 5, minutes: 5, completed: false }],
    }),
  });
  const snap = lc.getRoomProgressSnapshot(5);
  assert.equal(snap.isCompleted, true);            // reanchored wins -> completed
  assert.equal(snap.elapsedMinutes, 4);
});

test("[LRN-13] estimated minutes 0 on a current room defaults to 1 (avoids /0), percent computes off that", () => {
  // minutes 0 -> `Number(entry.minutes) || 1` = 1. startedAt 30s ago -> elapsed .5 -> pct floor 50.
  const lc = makeController({
    state: makeState({
      estimateTimeline: [{ room_id: 5, minutes: 0, completed: false }],
    }),
    jobProgress: { currentRoomStartedAt: Date.now() - 30 * 1000 },
  });
  const snap = lc.getRoomProgressSnapshot(5);
  assert.equal(snap.estimatedMinutes, 1);          // 0 -> 1 guard
  assert.equal(snap.percent, 50);                  // floor(.5/1*100)
});

// =========================================================================
// _computeProgressPercent
// =========================================================================

test("[LRN-14] blends completed minutes with capped current-room elapsed, floored", () => {
  // total 20, completed 5, current room started 2 min ago, current est 10 (cap not hit).
  // numerator = 5 + 2 = 7 ; 7/20*100 = 35.
  const lc = makeController({
    jobProgress: {
      totalEstimatedMinutes: 20,
      completedRoomMinutes: 5,
      currentRoomEstimatedMinutes: 10,
      currentRoomStartedAt: Date.now() - 2 * 60000,
    },
  });
  assert.equal(lc._computeProgressPercent(), 35);
});

test("[LRN-15] current-room elapsed is CAPPED at currentRoomEstimatedMinutes (honest progress)", () => {
  // Current room started 30 min ago but its est is only 4 -> capped at 4, not 30.
  // total 20, completed 6 -> numerator 6 + 4 = 10 -> 50%. Without the cap it would exceed 99.
  const lc = makeController({
    jobProgress: {
      totalEstimatedMinutes: 20,
      completedRoomMinutes: 6,
      currentRoomEstimatedMinutes: 4,
      currentRoomStartedAt: Date.now() - 30 * 60000,
    },
  });
  assert.equal(lc._computeProgressPercent(), 50);
});

test("[LRN-16] total <= 0 short-circuits to 0", () => {
  assert.equal(
    makeController({ jobProgress: { totalEstimatedMinutes: 0 } })._computeProgressPercent(),
    0
  );
  assert.equal(
    makeController({ jobProgress: { totalEstimatedMinutes: -5, completedRoomMinutes: 3 } })
      ._computeProgressPercent(),
    0
  );
});

test("[LRN-17] null currentRoomStartedAt -> 0 elapsed, so percent is completed-share only", () => {
  // No current room timing yet: numerator = completed(10) + 0 = 10 ; 10/40*100 = 25.
  const lc = makeController({
    jobProgress: {
      totalEstimatedMinutes: 40,
      completedRoomMinutes: 10,
      currentRoomEstimatedMinutes: 8,
      currentRoomStartedAt: null,
    },
  });
  assert.equal(lc._computeProgressPercent(), 25);
});

test("[LRN-18] overall percent clamps to 99 even when the blend would reach/exceed 100", () => {
  // completed already == total; current adds more -> raw >= 100, must floor-clamp to 99.
  const lc = makeController({
    jobProgress: {
      totalEstimatedMinutes: 10,
      completedRoomMinutes: 10,
      currentRoomEstimatedMinutes: 5,
      currentRoomStartedAt: Date.now() - 5 * 60000,
    },
  });
  assert.equal(lc._computeProgressPercent(), 99);
});
