/**
 * ============================================================
 * STATE: LEARNING
 * ============================================================
 *
 * PURPOSE
 * -------
 * Card-local learning system state for estimate consumption,
 * live reanchoring, next-room banner updates, and queue-
 * independent per-room estimate access.
 *
 * This file owns:
 * - pre-job estimate payload storage
 * - live reanchored estimate storage
 * - completed room accumulation
 * - job-active tracking
 * - next-room banner payload storage
 * - post-job summary snapshot storage
 * - queue-independent room estimate storage
 * - room estimate metadata (stale/rebuilt/estimated_at)
 * - learning state lifecycle helpers
 *
 *
 * WHAT THIS FILE SHOULD NOT CONTAIN
 * ----------------------------------
 * - service calls
 * - event subscriptions
 * - rendering
 * - click bindings
 *
 *
 * HOW THIS FILE FITS INTO THE SYSTEM
 * -----------------------------------
 * Mixed onto VacuumCardState via applyLearningState(proto).
 *
 * This state is intentionally card-local. The integration is the
 * source of truth for learning models and estimate generation,
 * while the card stores the latest estimate/reanchor payloads
 * needed for rendering and mid-job updates.
 *
 *
 * CARD STATE MACHINE
 * ------------------
 * state = {
 *   estimate: null,          // full payload from run_learning_estimate
 *   reanchored: null,        // latest payload from reanchor_learning_timeline
 *   completedRooms: [],      // all completed rooms so far in this job
 *   nextRoom: null,          // latest get_next_room result
 *   jobActive: false,
 *   summary: null,           // post-job summary snapshot
 *
 *   roomEstimates: {},       // { [room_id]: entry } from get_room_learning_estimates
 *   roomEstimateMeta: {
 *     stats_stale: false,
 *     stats_rebuilt_at: null,
 *     estimated_at: null,
 *     room_count: 0,
 *     current_battery: null,
 *     map_id: null,
 *     vacuum_entity_id: null,
 *   },
 * }
 *
 * ============================================================
 */

export function applyLearningState(proto) {

  /* =========================================================
     INTERNAL ENSURE / RESET
     ========================================================= */

  /** Lazily creates the learning state container on first access. */
  proto._ensureLearningState = function () {
    if (!this._learning) {
      this._learning = {
        estimate: null,
        reanchored: null,
        completedRooms: [],
        nextRoom: null,
        jobActive: false,
        summary: null,
        dashboardSnapshot: null,
        incompleteRunLog: null,
        troubleRoomsLog: null,

        roomEstimates: {},
        roomEstimateMeta: {
          stats_stale: false,
          stats_rebuilt_at: null,
          estimated_at: null,
          room_count: 0,
          current_battery: null,
          map_id: null,
          vacuum_entity_id: null,
        },
      };
    }

    if (!Array.isArray(this._learning.completedRooms)) {
      this._learning.completedRooms = [];
    }

    if (!this._learning.roomEstimates || typeof this._learning.roomEstimates !== "object") {
      this._learning.roomEstimates = {};
    }

    if (!this._learning.roomEstimateMeta || typeof this._learning.roomEstimateMeta !== "object") {
      this._learning.roomEstimateMeta = {
        stats_stale: false,
        stats_rebuilt_at: null,
        estimated_at: null,
        room_count: 0,
        current_battery: null,
        map_id: null,
        vacuum_entity_id: null,
      };
    }

    return this._learning;
  };

  /** Reset all card-local learning state to a clean baseline. */
  proto.clearLearningState = function () {
    this._learning = {
      estimate: null,
      reanchored: null,
        completedRooms: [],
        nextRoom: null,
        jobActive: false,
        summary: null,
        dashboardSnapshot: null,
        incompleteRunLog: null,
        troubleRoomsLog: null,

        roomEstimates: {},
      roomEstimateMeta: {
        stats_stale: false,
        stats_rebuilt_at: null,
        estimated_at: null,
        room_count: 0,
        current_battery: null,
        map_id: null,
        vacuum_entity_id: null,
      },
    };
  };

  /**
   * Reset queue-dependent learning state.
   * RULES: room estimate cache is preserved — it is queue-independent.
   */
  proto.clearLearningJobContext = function () {
    const learning = this._ensureLearningState();

    learning.estimate = null;
    learning.reanchored = null;
    learning.completedRooms = [];
    learning.nextRoom = null;
    learning.jobActive = false;
    learning.summary = null;
  };

  /* =========================================================
     RAW ACCESSORS
     ========================================================= */

  proto.learningState = function () {
    return this._ensureLearningState();
  };

  proto.dashboardSnapshot = function () {
    return this._ensureLearningState().dashboardSnapshot ?? null;
  };

  proto.dashboardJobProgress = function () {
    return this.dashboardSnapshot()?.job_progress ?? null;
  };

  proto.dashboardJobControl = function () {
    return this.dashboardSnapshot()?.job_control ?? null;
  };

  proto.dashboardStartStatus = function () {
    return this.dashboardSnapshot()?.start_status ?? null;
  };

  proto.dashboardLifecycle = function () {
    return this.dashboardSnapshot()?.lifecycle ?? null;
  };

  proto.dashboardUpkeep = function () {
    return this.dashboardSnapshot()?.upkeep ?? null;
  };

  proto.dashboardStatusSummary = function () {
    return this.dashboardSnapshot()?.status_summary ?? null;
  };

  proto.dashboardAttentionSummary = function () {
    return this.dashboardSnapshot()?.attention_summary ?? null;
  };

  proto.dashboardPlannedJobEstimate = function () {
    return this.dashboardSnapshot()?.planned_job_estimate ?? null;
  };

  proto.dashboardPlannedWaterEstimate = function () {
    return this.dashboardPlannedJobEstimate()?.water_estimate ?? null;
  };

  proto.dashboardPlannedWaterRooms = function () {
    const rooms = this.dashboardPlannedWaterEstimate()?.rooms;
    return Array.isArray(rooms) ? rooms : [];
  };

  proto.dashboardPlannedWaterRoomForRoom = function (roomId, roomSlug = null) {
    const wantedId = roomId == null ? null : String(roomId);
    const wantedSlug = roomSlug == null ? null : String(roomSlug).trim().toLowerCase();

    return this.dashboardPlannedWaterRooms().find((entry) => {
      const entryId = entry?.room_id == null ? null : String(entry.room_id);
      const entrySlug = entry?.slug == null ? null : String(entry.slug).trim().toLowerCase();

      if (wantedId != null && entryId === wantedId) return true;
      if (wantedSlug && entrySlug === wantedSlug) return true;
      return false;
    }) ?? null;
  };

  proto.dashboardPlannedJobEstimateAvailable = function () {
    return Boolean(this.dashboardPlannedJobEstimate()?.available);
  };

  proto.dashboardPlannedJobEstimateTotalMinutes = function () {
    const value = Number(this.dashboardPlannedJobEstimate()?.total_minutes);
    return Number.isFinite(value) ? value : null;
  };

  proto.dashboardJobProgressTimeline = function () {
    const timeline = this.dashboardJobProgress()?.timeline;
    return Array.isArray(timeline) ? timeline : [];
  };

  proto._dashboardJobIsActive = function () {
    const progress = this.dashboardJobProgress();
    if (!progress || typeof progress !== "object") return false;

    if (typeof progress.terminal === "boolean") {
      return !progress.terminal;
    }

    const status = String(progress.status ?? "").trim().toLowerCase();
    if (!status) return false;

    return ![
      "complete",
      "completed",
      "finished",
      "idle",
      "terminal",
      "not_started",
      "inactive",
    ].includes(status);
  };

  /* =========================================================
     INCOMPLETE RUN LOG
     ========================================================= */

  proto.incompleteRunLog = function () {
    return this._ensureLearningState().incompleteRunLog ?? null;
  };

  proto.hasIncompleteRunLog = function () {
    const log = this.incompleteRunLog();
    if (!log) return false;
    const missed = log.missed_room_ids;
    return Array.isArray(missed) && missed.length > 0;
  };

  proto.incompleteRunMissedRoomIds = function () {
    const ids = this.incompleteRunLog()?.missed_room_ids;
    return Array.isArray(ids) ? ids : [];
  };

  proto.incompleteRunMissedRooms = function () {
    const rooms = this.incompleteRunLog()?.missed_rooms;
    return Array.isArray(rooms) ? rooms : [];
  };

  proto.setIncompleteRunLog = function (payload) {
    const learning = this._ensureLearningState();
    learning.incompleteRunLog = payload ?? null;
  };

  proto.clearIncompleteRunLog = function () {
    const learning = this._ensureLearningState();
    learning.incompleteRunLog = null;
  };

  /* =========================================================
     TROUBLE ROOMS LOG
     ========================================================= */

  proto.troubleRoomsLog = function () {
    return this._ensureLearningState().troubleRoomsLog ?? null;
  };

  /**
   * Returns true when the log has at least one trouble room.
   */
  proto.hasTroubleRooms = function () {
    const log = this.troubleRoomsLog();
    if (!log || typeof log !== "object") return false;
    const rooms = log.rooms;
    if (!rooms || typeof rooms !== "object") return false;
    return Object.values(rooms).some((r) => r?.is_trouble === true);
  };

  /**
   * Return the trouble-rooms entry for a specific room_id, or null.
   * Accepts numeric or string room_id.
   */
  proto.troubleRoomForRoom = function (roomId) {
    const log = this.troubleRoomsLog();
    if (!log || typeof log !== "object") return null;
    const rooms = log.rooms;
    if (!rooms || typeof rooms !== "object") return null;

    const wantedKey = String(roomId);
    const entry = rooms[wantedKey] ?? null;
    return entry;
  };

  proto.setTroubleRoomsLog = function (payload) {
    const learning = this._ensureLearningState();
    learning.troubleRoomsLog = payload ?? null;
  };

  proto.clearTroubleRoomsLog = function () {
    const learning = this._ensureLearningState();
    learning.troubleRoomsLog = null;
  };

  proto.learningEstimate = function () {
    const learning = this._ensureLearningState();
    return learning.estimate ?? this.dashboardPlannedJobEstimate() ?? null;
  };

  proto.learningReanchored = function () {
    return this._ensureLearningState().reanchored ?? null;
  };

  proto.learningCompletedRooms = function () {
    return [...this._ensureLearningState().completedRooms];
  };

  proto.learningNextRoom = function () {
    return this._ensureLearningState().nextRoom ?? null;
  };

  proto.learningJobActive = function () {
    if (this._dashboardJobIsActive()) return true;
    return Boolean(this._ensureLearningState().jobActive);
  };

  /* =========================================================
     SUMMARY ACCESS
     ========================================================= */

  proto.learningSummary = function () {
    return this._ensureLearningState().summary ?? null;
  };

  proto.hasLearningSummary = function () {
    return Boolean(this._ensureLearningState().summary);
  };

  proto.clearLearningSummary = function () {
    const learning = this._ensureLearningState();
    learning.summary = null;
  };

  /* =========================================================
     ROOM ESTIMATE ACCESS
     ========================================================= */

  proto.roomEstimates = function () {
    return this._ensureLearningState().roomEstimates ?? {};
  };

  proto.roomEstimateMeta = function () {
    return this._ensureLearningState().roomEstimateMeta ?? {};
  };

  proto.hasRoomEstimates = function () {
    return Object.keys(this.roomEstimates()).length > 0;
  };

  proto.roomEstimateForRoom = function (roomId) {
    const wanted = String(roomId);
    const estimates = this.roomEstimates();

    for (const [key, value] of Object.entries(estimates)) {
      if (String(key) === wanted) return value ?? null;
    }

    return null;
  };

  proto.roomEstimatesStatsStale = function () {
    return Boolean(this.roomEstimateMeta().stats_stale);
  };

  proto.roomEstimatesStatsRebuiltAt = function () {
    return this.roomEstimateMeta().stats_rebuilt_at ?? null;
  };

  proto.roomEstimatesEstimatedAt = function () {
    return this.roomEstimateMeta().estimated_at ?? null;
  };

  proto.roomEstimateCount = function () {
    const explicit = Number(this.roomEstimateMeta().room_count);
    if (Number.isFinite(explicit)) return explicit;

    return Object.keys(this.roomEstimates()).length;
  };

  /* =========================================================
     SETTERS / MUTATION
     ========================================================= */

  /**
   * Store the full pre-job estimate response.
   * RULES: full payload must be preserved — reanchor_learning_timeline requires it as input.
   */
  proto.setLearningEstimate = function (payload) {
    const learning = this._ensureLearningState();
    learning.estimate = payload ?? null;
  };

  proto.setDashboardSnapshot = function (payload) {
    const learning = this._ensureLearningState();
    learning.dashboardSnapshot = payload ?? null;
  };

  proto.setLearningReanchored = function (payload) {
    const learning = this._ensureLearningState();
    learning.reanchored = payload ?? null;
  };

  proto.setLearningNextRoom = function (payload) {
    const learning = this._ensureLearningState();
    learning.nextRoom = payload ?? null;
  };

  proto.setLearningJobActive = function (value) {
    const learning = this._ensureLearningState();
    learning.jobActive = Boolean(value);
  };

  proto.setLearningCompletedRooms = function (rooms) {
    const learning = this._ensureLearningState();
    learning.completedRooms = Array.isArray(rooms) ? [...rooms] : [];
  };

  /**
   * Store queue-independent room-level estimates keyed by room_id for O(1) lookup.
   * @param {object} result - full response payload from get_room_learning_estimates
   */
  proto.setRoomEstimates = function (result) {
    const learning = this._ensureLearningState();
    const nextEstimates = {};

    for (const room of result?.rooms ?? []) {
      if (room?.room_id == null) continue;
      nextEstimates[room.room_id] = room;
    }

    learning.roomEstimates = nextEstimates;
    learning.roomEstimateMeta = {
      stats_stale: Boolean(result?.stats_stale),
      stats_rebuilt_at: result?.stats_rebuilt_at ?? null,
      estimated_at: result?.estimated_at ?? null,
      room_count: Number(result?.room_count ?? Object.keys(nextEstimates).length) || 0,
      current_battery: result?.current_battery ?? null,
      map_id: result?.map_id ?? null,
      vacuum_entity_id: result?.vacuum_entity_id ?? null,
    };
  };

  proto.clearRoomEstimates = function () {
    const learning = this._ensureLearningState();
    learning.roomEstimates = {};
    learning.roomEstimateMeta = {
      stats_stale: false,
      stats_rebuilt_at: null,
      estimated_at: null,
      room_count: 0,
      current_battery: null,
      map_id: null,
      vacuum_entity_id: null,
    };
  };

  /**
   * Append one completed-room record for use by reanchor_learning_timeline.
   * @param {{ room_id: number, actual_duration_minutes: number }} entry
   */
  proto.pushCompletedLearningRoom = function (entry) {
    const learning = this._ensureLearningState();
    if (!entry || entry.room_id == null) return;

    const minutes = Number(entry.actual_duration_minutes);
    if (!Number.isFinite(minutes)) return;

    learning.completedRooms.push({
      room_id: entry.room_id,
      actual_duration_minutes: minutes,
    });
  };

  /* =========================================================
     JOB LIFECYCLE HELPERS
     ========================================================= */

  /**
   * Transition into active live-job mode after start_selected_rooms succeeds.
   * RULES: initial live anchor is set to the original estimate.
   */
  proto.beginLearningJob = function () {
    const learning = this._ensureLearningState();

    learning.jobActive = true;
    learning.reanchored = learning.estimate ?? null;
    learning.completedRooms = [];
    learning.nextRoom = null;
    learning.summary = null;
  };

  /**
   * End the live learning job and snapshot a brief summary for post-job UI.
   * RULES: only live-job state is cleared; the estimate is preserved for reference.
   */
  proto.endLearningJob = function (actualOverride = null) {
    const learning = this._ensureLearningState();

    const estimate = learning.estimate;
    const reanchored = learning.reanchored ?? estimate;
    const completed = Array.isArray(learning.completedRooms)
      ? learning.completedRooms
      : [];

    // Authoritative actuals come from the EVENT_JOB_FINISHED payload — they
    // carry the real duration and room_count from the finalized job record.
    // The live `completedRooms` array can be empty on short 1-room runs if
    // the room_finished event arrives before learningJobActive flips true,
    // and `total_minutes` from estimate/reanchored is a *prediction* not the
    // measured outcome. Prefer override values when present.
    const actualMinutes = Number(
      actualOverride?.actual_cleaning_minutes ??
      actualOverride?.duration_minutes
    );
    const actualRoomCount = Number(actualOverride?.room_count);

    const fallbackTotal = Number(
      reanchored?.total_minutes ??
      estimate?.total_minutes ??
      0
    );

    if (estimate || reanchored || completed.length || actualOverride) {
      learning.summary = {
        finished_at: new Date().toISOString(),
        total_minutes: Number.isFinite(actualMinutes) && actualMinutes > 0
          ? actualMinutes
          : (fallbackTotal || 0),
        rooms_completed: Number.isFinite(actualRoomCount) && actualRoomCount > 0
          ? actualRoomCount
          : completed.length,
        predicted_total_minutes: fallbackTotal || null,
        battery_warning: Boolean(reanchored?.battery_warning),

        /*
         * Keep the final resolved payload available for richer
         * post-job rendering later without recomputing.
         */
        final_payload: reanchored ?? estimate ?? null,
      };
    } else {
      learning.summary = null;
    }

    // Clear only live-job state.
    learning.jobActive = false;
    learning.reanchored = null;
    learning.completedRooms = [];
    learning.nextRoom = null;

    /*
     * Preserve estimate so the card can still reference the last
     * known estimate context if needed. A new job / queue change
     * can clear everything explicitly through clearLearningState().
     */
  };

  /* =========================================================
     HIGH-LEVEL FLAGS
     ========================================================= */

  proto.hasLearningEstimate = function () {
    const estimate = this.learningEstimate();
    return Boolean(estimate) && !estimate?.error;
  };

  proto.learningEstimateError = function () {
    return this.learningEstimate()?.error ?? null;
  };

  proto.learningEstimateErrorDetail = function () {
    return this.learningEstimate()?.error_detail ?? null;
  };

  proto.learningStatsStale = function () {
    return Boolean(this.learningEstimate()?.stats_stale);
  };

  proto.learningBatteryWarning = function () {
    const source = this.dashboardJobProgress() ?? this.learningReanchored() ?? this.learningEstimate();
    return Boolean(source?.battery_warning);
  };

  /**
   * Return whether the estimate panel should be rendered.
   * RULES: returns false when the estimate has an error field — callers should show a guidance state instead.
   */
  proto.learningCanRenderEstimatePanel = function () {
    const estimate = this.learningEstimate();
    if (!estimate) return false;
    if (estimate.error) return false;
    return true;
  };

  /* =========================================================
     PRE-JOB SUMMARY HELPERS
     ========================================================= */

  proto.learningTotalMinutes = function () {
    const value = Number(
      this.dashboardPlannedJobEstimateTotalMinutes() ??
      this.learningEstimate()?.total_minutes
    );
    return Number.isFinite(value) ? value : null;
  };

  proto.learningJobEtaAt = function () {
    return (
      this.dashboardJobProgress()?.status_summary?.eta_at ??
      this.dashboardPlannedJobEstimate()?.job_eta_at ??
      this.learningEstimate()?.job_eta_at ??
      null
    );
  };

  proto.learningConfidenceBreakpoint = function () {
    return (
      this.dashboardPlannedJobEstimate()?.confidence_breakpoint ??
      this.learningEstimate()?.confidence_breakpoint ??
      null
    );
  };

  proto.learningRoomTimeline = function () {
    const dashboardTimeline = this.dashboardJobProgressTimeline();
    if (dashboardTimeline.length) return dashboardTimeline;

    const plannedTimeline = this.dashboardPlannedJobEstimate()?.room_timeline;
    if (Array.isArray(plannedTimeline) && plannedTimeline.length) {
      return plannedTimeline;
    }

    const source = this.learningReanchored() ?? this.learningEstimate();
    return Array.isArray(source?.room_timeline) ? source.room_timeline : [];
  };

  /* =========================================================
     LIVE JOB HELPERS
     ========================================================= */

  proto.learningRoomsCompletedCount = function () {
    const completedIds = this.dashboardJobProgress()?.completed_room_ids;
    if (Array.isArray(completedIds)) {
      return completedIds.length;
    }

    const source = this.learningReanchored();
    const direct = Number(source?.rooms_completed);
    if (Number.isFinite(direct)) return direct;

    return this._ensureLearningState().completedRooms.length;
  };

  proto.learningRoomsRemainingCount = function () {
    const remainingIds = this.dashboardJobProgress()?.remaining_room_ids;
    if (Array.isArray(remainingIds)) {
      return remainingIds.length;
    }

    const source = this.learningReanchored();
    const direct = Number(source?.rooms_remaining);
    if (Number.isFinite(direct)) return direct;

    const timeline = this.learningRoomTimeline();
    return timeline.filter((entry) => !entry?.completed).length;
  };

  proto.learningAllCompleted = function () {
    const progress = this.dashboardJobProgress();
    if (progress && typeof progress.terminal === "boolean") {
      return progress.terminal;
    }

    const source = this.learningReanchored();
    if (typeof source?.all_completed === "boolean") {
      return source.all_completed;
    }

    const nextRoom = this.learningNextRoom();
    return Boolean(nextRoom && Object.keys(nextRoom).length === 0);
  };

  proto.learningLiveBannerRoom = function () {
    const currentRoomId = this.dashboardJobProgress()?.current_room_id;
    if (currentRoomId != null) {
      const currentEntry = this.learningTimelineEntryForRoom(currentRoomId);
      if (currentEntry) return currentEntry;
    }

    const currentEntry = this.learningRoomTimeline().find(
      (entry) => Boolean(entry?.current)
    );
    if (currentEntry) return currentEntry;

    return this.learningNextRoom();
  };

  /* =========================================================
     ROOM-LEVEL LOOKUPS
     ========================================================= */

  /**
   * Find one room's entry in the latest learning timeline by room_id.
   * @param {number|string} roomId
   * @returns {object|null}
   */
  proto.learningTimelineEntryForRoom = function (roomId) {
    const wanted = String(roomId);
    return this.learningRoomTimeline().find(
      (entry) => String(entry?.room_id) === wanted
    ) ?? null;
  };
}
