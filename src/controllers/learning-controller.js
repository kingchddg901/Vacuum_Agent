// Event-driven learning controller: subscribes to vacuum events, reanchors ETAs, tracks live job progress.

export class LearningController {

  /**
   * @param {EufyVacuumCommandCenter} card - root card element owning this controller
   */
  constructor(card) {
    this.card = card;
    this._unsubRoomCompleted = null;
    this._unsubRoomStarted = null;
    this._unsubRoomFinished = null;
    this._unsubJobFinished = null;
    this._roomEstimateRequestSeq = 0;
    this._lastRoomEstimateMapId = null;
    this._lastRoomEstimateVacuumEntityId = null;
    this._jobProgressResetTimer = null;
    this._boundsExitPollTimer = null;

    this._jobProgress = {
      totalEstimatedMinutes: 0,
      completedRoomMinutes: 0,
      currentRoomStartedAt: null,
      currentRoomEstimatedMinutes: 0,
      percent: 0,
      ticker: null,
    };
  }

  /** Clear the post-job summary panel and trigger a re-render. */
  dismissLearningSummary() {
    const state = this.card?._state;
    if (!state) return;

    state.clearLearningSummary();
    this.card._scheduleRender();
  }

  /* =========================================================
     CONNECT / DISCONNECT
     ========================================================= */

  /**
   * Subscribe to vacuum events for this card's configured vacuum.
   * Safe to call multiple times — exits early when already subscribed.
   */
  connect() {
    if (
      this._unsubRoomCompleted ||
      this._unsubRoomStarted ||
      this._unsubRoomFinished ||
      this._unsubJobFinished
    ) return;

    const hass = this.card?._hass;
    if (!hass?.connection?.subscribeEvents) return;

    this._subscribeEvent(
      "eufy_vacuum_room_completed",
      "_unsubRoomCompleted",
      (event) => this._handleRoomCompleted(event)
    );
    this._subscribeEvent(
      "eufy_vacuum_room_started",
      "_unsubRoomStarted",
      (event) => this._handleRoomStarted(event)
    );
    this._subscribeEvent(
      "eufy_vacuum_room_finished",
      "_unsubRoomFinished",
      (event) => this._handleRoomFinished(event)
    );
    this._subscribeEvent(
      "eufy_vacuum_job_finished",
      "_unsubJobFinished",
      (event) => this._handleJobFinished(event)
    );
  }

  _subscribeEvent(eventType, key, handler) {
    const hass = this.card?._hass;
    if (!hass?.connection?.subscribeEvents) return;

    const subscription = hass.connection.subscribeEvents(handler, eventType);

    Promise.resolve(subscription)
      .then((unsubscribe) => {
        this[key] = typeof unsubscribe === "function" ? unsubscribe : null;
      })
      .catch((error) => {
        this[key] = null;
        console.warn(
          `[eufy-vacuum-command-center] Failed to subscribe to ${eventType}.`,
          error
        );
      });
  }

  /** Tear down all event subscriptions and timers when the card leaves the DOM. */
  disconnect() {
    if (typeof this._unsubRoomCompleted === "function") {
      this._unsubRoomCompleted();
    }
    if (typeof this._unsubRoomStarted === "function") {
      this._unsubRoomStarted();
    }
    if (typeof this._unsubRoomFinished === "function") {
      this._unsubRoomFinished();
    }
    if (typeof this._unsubJobFinished === "function") {
      this._unsubJobFinished();
    }

    this._unsubRoomCompleted = null;
    this._unsubRoomStarted = null;
    this._unsubRoomFinished = null;
    this._unsubJobFinished = null;

    this._stopBoundsExitPoll();
    this._stopProgressTicker();

    if (this._jobProgressResetTimer) {
      clearTimeout(this._jobProgressResetTimer);
      this._jobProgressResetTimer = null;
    }
  }

  /* =========================================================
     EVENT FLOW
     ========================================================= */

  /**
   * Consume a room-completed event and reanchor the learning timeline.
   * RULES: ignores events for other vacuums; requires an active job; passes ALL completed rooms on reanchor.
   */
  async _handleRoomCompleted(event) {
    const data = event?.data ?? {};
    const vacuumEntityId = this.card?._config?.vacuum_entity_id;

    if (!vacuumEntityId) return;
    if (data.vacuum_entity_id !== vacuumEntityId) return;
    if (!this.card?._state?.learningJobActive?.()) return;

    const roomId = data.room_id;
    const durationSeconds = Number(data.duration_seconds);

    if (roomId == null || !Number.isFinite(durationSeconds)) return;

    this.card._state.pushCompletedLearningRoom({
      room_id: roomId,
      actual_duration_minutes: durationSeconds / 60,
    });

    this._jobProgress.completedRoomMinutes += durationSeconds / 60;
    this._jobProgress.currentRoomStartedAt = Date.now();

    const timeline =
      this.card._state.learningReanchored?.()?.room_timeline ??
      this.card._state.learningEstimate?.()?.room_timeline;

    const nextRoom = timeline?.find((r) => !r.completed);

    this._jobProgress.currentRoomEstimatedMinutes = nextRoom?.minutes ?? 0;

    await this._reanchorTimeline();
    this._checkBoundsExitPolling();
  }

  async _handleRoomStarted(event) {
    const data = event?.data ?? {};
    const vacuumEntityId = this.card?._config?.vacuum_entity_id;

    if (!vacuumEntityId) return;
    if (data.vacuum_entity_id !== vacuumEntityId) return;

    this._stopBoundsExitPoll();
    await this.card?.refreshDashboardSnapshot?.();
    this.card?._scheduleRender?.();
  }

  async _handleRoomFinished(event) {
    const data = event?.data ?? {};
    const vacuumEntityId = this.card?._config?.vacuum_entity_id;

    if (!vacuumEntityId) return;
    if (data.vacuum_entity_id !== vacuumEntityId) return;

    this._stopBoundsExitPoll();
    await this.card?.refreshDashboardSnapshot?.();
    this._checkBoundsExitPolling();
    this.card?._scheduleRender?.();
  }

  async _handleJobFinished(event) {
    const data = event?.data ?? {};
    const vacuumEntityId = this.card?._config?.vacuum_entity_id;

    if (!vacuumEntityId) return;
    if (data.vacuum_entity_id !== vacuumEntityId) return;

    await this.card?.refreshDashboardSnapshot?.();

    // Pass the authoritative actuals from the event so the post-job summary
    // banner shows real duration / room count even when the live tracker
    // missed events (common on short 1-room jobs).
    this.card?._state?.endLearningJob?.({
      duration_minutes: data.duration_minutes,
      actual_cleaning_minutes: data.actual_cleaning_minutes,
      room_count: data.room_count,
    });
    this.endJobProgress();

    // Reload the incomplete run log in case this job was cancelled/failed.
    // Also reload the trouble rooms log — job finalization may have updated
    // per-room miss/run counts.
    // Fire-and-forget — we don't need to await before re-rendering.
    this.card?.refreshIncompleteRunLog?.();
    this.card?.refreshTroubleRoomsLog?.();

    this.card?._scheduleRender?.();
  }

  /**
   * Recompute remaining ETAs after one or more rooms complete.
   * RULES: original_estimate must be the full original; completed_rooms must be cumulative.
   */
  async _reanchorTimeline() {
    const state = this.card?._state;
    const actions = this.card?._actions;

    if (!state || !actions) return;

    const originalEstimate = state.learningEstimate();
    if (!originalEstimate) return;

    const completedRooms = state.learningCompletedRooms();
    const currentBattery = state.batteryLevel();

    const result = await actions.reanchorLearningTimeline({
      original_estimate: originalEstimate,
      completed_rooms: completedRooms,
      reanchor_at: new Date().toISOString(),
      current_battery: Number.isFinite(currentBattery) ? currentBattery : undefined,
    });

    if (!result) return;

    state.setLearningReanchored(result);

    if (result?.total_minutes) {
      this._jobProgress.totalEstimatedMinutes = result.total_minutes;
    }

    const nextRoom = result?.room_timeline?.find((r) => !r.completed);
    this._jobProgress.currentRoomEstimatedMinutes = nextRoom?.minutes ?? 0;

    await this._refreshNextRoom();
    this.card._scheduleRender();
  }

  /** Resolve the next-room banner payload from the latest reanchored estimate. */
  async _refreshNextRoom() {
    const state = this.card?._state;
    const actions = this.card?._actions;

    if (!state || !actions) return;

    const reanchored = state.learningReanchored();
    if (!reanchored) {
      state.setLearningNextRoom(null);
      return;
    }

    const result = await actions.getNextLearningRoom({
      reanchored_estimate: reanchored,
    });

    state.setLearningNextRoom(result && Object.keys(result).length ? result : {});
  }
  
  /* =========================================================
     JOB PROGRESS
     ========================================================= */

  /**
   * Seed the real-time progress model from the original estimate when a job starts.
   * @param {object} estimate - full payload from run_learning_estimate
   */
  startJobProgress(estimate) {
    if (!estimate) return;

    if (this._jobProgressResetTimer) {
      clearTimeout(this._jobProgressResetTimer);
      this._jobProgressResetTimer = null;
    }

    this._jobProgress.totalEstimatedMinutes = Number(estimate.total_minutes) || 0;
    this._jobProgress.completedRoomMinutes = 0;
    this._jobProgress.currentRoomStartedAt = Date.now();

    const firstRoom = estimate.room_timeline?.[0];
    this._jobProgress.currentRoomEstimatedMinutes = Number(firstRoom?.minutes) || 0;
    this._jobProgress.percent = 0;

    this._stopProgressTicker();
    this._startProgressTicker();
  }

  /**
   * Snap progress to 100%, then clear after a brief delay so the completion state is visible.
   */
  endJobProgress() {
    this._stopProgressTicker();

    if (this._jobProgressResetTimer) {
      clearTimeout(this._jobProgressResetTimer);
      this._jobProgressResetTimer = null;
    }

    this._jobProgress.percent = 100;
    this.card._scheduleRender();

    this._jobProgressResetTimer = setTimeout(() => {
      this._jobProgress.percent = 0;
      this._jobProgressResetTimer = null;
      this.card._scheduleRender();
    }, 3000);
  }

  /* =========================================================
     BOUNDS-EXIT POLL
     =========================================================
     When the backend reports awaiting_bounds_exit: true the room
     timing threshold has elapsed but the robot is still inside
     the room's bounds (cleaning slower than expected).  No room
     event will fire until the robot actually leaves, so we poll
     the snapshot every 5 s until we see the room roll over.
     The poll stops immediately when room_started or room_finished
     fires, or when the job ends.
     ========================================================= */

  _checkBoundsExitPolling() {
    const awaiting = this.card?._state?.dashboardJobProgress?.()?.awaiting_bounds_exit;
    if (awaiting) {
      this._startBoundsExitPoll();
    } else {
      this._stopBoundsExitPoll();
    }
  }

  _startBoundsExitPoll() {
    if (this._boundsExitPollTimer) return;   // already running
    this._boundsExitPollTimer = setInterval(async () => {
      await this.card?.refreshDashboardSnapshot?.();
      this.card?._scheduleRender?.();
      // Re-check after each refresh — stop if the room has rolled
      if (!this.card?._state?.dashboardJobProgress?.()?.awaiting_bounds_exit) {
        this._stopBoundsExitPoll();
      }
    }, 5000);
  }

  _stopBoundsExitPoll() {
    if (this._boundsExitPollTimer) {
      clearInterval(this._boundsExitPollTimer);
      this._boundsExitPollTimer = null;
    }
  }

  /** Start the 1-second interval that smoothly advances the progress bar. */
  _startProgressTicker() {
    if (this._jobProgress.ticker) {
      clearInterval(this._jobProgress.ticker);
    }

    this._jobProgress.ticker = setInterval(() => {
      this._jobProgress.percent = this._computeProgressPercent();
      this.card._scheduleRender();
    }, 1000);
  }

  /** Clear the progress-bar tick interval. */
  _stopProgressTicker() {
    if (this._jobProgress.ticker) {
      clearInterval(this._jobProgress.ticker);
      this._jobProgress.ticker = null;
    }
  }

  /**
   * Compute smooth progress by blending completed-room actuals with capped in-room elapsed time.
   * WHY capped: elapsed never overshoots the current room's estimated share, keeping progress honest.
   */
  _computeProgressPercent() {
    const total = this._jobProgress.totalEstimatedMinutes;
    if (!total || total <= 0) return 0;

    const completedMinutes = this._jobProgress.completedRoomMinutes;

    const elapsedInCurrentMs = this._jobProgress.currentRoomStartedAt
      ? Date.now() - this._jobProgress.currentRoomStartedAt
      : 0;

    const elapsedInCurrentMinutes = Math.max(0, elapsedInCurrentMs / 60000);

    const cappedCurrentMinutes = Math.min(
      elapsedInCurrentMinutes,
      this._jobProgress.currentRoomEstimatedMinutes
    );

    const numerator = completedMinutes + cappedCurrentMinutes;
    const percent = (numerator / total) * 100;

    return Math.min(Math.max(Math.floor(percent), 0), 99);
  }

  /**
   * Return a live progress snapshot for one room: current/completed state, elapsed, estimated, remaining, percent.
   * @param {number|string} roomId
   * @returns {{ isCompleted, isCurrent, percent, elapsedMinutes, estimatedMinutes, remainingMinutes }|null}
   */
  getRoomProgressSnapshot(roomId) {
    const backendEntry = this.card?._state?.learningTimelineEntryForRoom?.(roomId);

    if (backendEntry) {
      const progressPercent = Number(backendEntry.progress_percent);
      const elapsedMinutes = Number(backendEntry.elapsed_minutes);
      const remainingMinutes = Number(backendEntry.remaining_minutes);
      const estimatedMinutes = Number(
        backendEntry.minutes ??
        (
          Number.isFinite(elapsedMinutes) && Number.isFinite(remainingMinutes)
            ? elapsedMinutes + remainingMinutes
            : null
        )
      );

      const hasBackendProgress =
        Number.isFinite(progressPercent) ||
        Boolean(backendEntry.current) ||
        Boolean(backendEntry.completed) ||
        Boolean(backendEntry.remaining);

      if (hasBackendProgress) {
        return {
          isCompleted: Boolean(backendEntry.completed),
          isCurrent: Boolean(backendEntry.current),
          percent: Boolean(backendEntry.completed)
            ? 100
            : Number.isFinite(progressPercent)
              ? Math.max(0, Math.min(99, Math.floor(progressPercent)))
              : backendEntry.current
                ? 0
                : 0,
          elapsedMinutes: Number.isFinite(elapsedMinutes) ? elapsedMinutes : 0,
          estimatedMinutes: Number.isFinite(estimatedMinutes) ? estimatedMinutes : null,
          remainingMinutes: Boolean(backendEntry.completed)
            ? 0
            : Number.isFinite(remainingMinutes)
              ? remainingMinutes
              : Number.isFinite(estimatedMinutes)
                ? estimatedMinutes
                : null,
        };
      }
    }

    const timeline =
      this.card._state.learningReanchored?.()?.room_timeline ??
      this.card._state.learningEstimate?.()?.room_timeline ??
      [];

    const entry = timeline.find((r) => String(r.room_id) === String(roomId));
    if (!entry) return null;

    if (entry.completed) {
      const actual = Number(entry.actual_duration_minutes);
      const estimated = Number(entry.minutes);

      return {
        isCompleted: true,
        isCurrent: false,
        percent: 100,
        elapsedMinutes: Number.isFinite(actual) ? actual : estimated,
        estimatedMinutes: Number.isFinite(estimated) ? estimated : null,
        remainingMinutes: 0,
      };
    }

    const currentRoom = timeline.find((r) => !r.completed);
    if (currentRoom?.room_id !== entry.room_id) {
      return {
        isCompleted: false,
        isCurrent: false,
        percent: 0,
        elapsedMinutes: 0,
        estimatedMinutes: Number(entry.minutes) || null,
        remainingMinutes: Number(entry.minutes) || null,
      };
    }

    const elapsed = this._jobProgress.currentRoomStartedAt
      ? Math.max(0, (Date.now() - this._jobProgress.currentRoomStartedAt) / 60000)
      : 0;

    const estimated = Number(entry.minutes) || 1;
    const percent = Math.min(Math.max(Math.floor((elapsed / estimated) * 100), 0), 99);
    const remainingMinutes = Math.max(0, estimated - elapsed);

    return {
      isCompleted: false,
      isCurrent: true,
      percent,
      elapsedMinutes: elapsed,
      estimatedMinutes: estimated,
      remainingMinutes,
    };
  }

  /**
   * Return overall job progress percent, preferring the backend value over the local ticker.
   * @returns {number} 0–100
   */
  getJobProgressPercent() {
    const backendPercent = Number(this.card?._state?.dashboardJobProgress?.()?.progress_percent);
    if (Number.isFinite(backendPercent)) {
      return Math.max(0, Math.min(100, backendPercent));
    }

    return this._jobProgress.percent ?? 0;
  }

  /**
   * Return per-room fill percentage, delegating to getRoomProgressSnapshot for single-source math.
   * @param {number|string} roomId
   * @returns {number} 0–100
   */
  getRoomProgressPercent(roomId) {
    return this.getRoomProgressSnapshot(roomId)?.percent ?? 0;
  }
  
  /**
   * Fetch queue-independent per-room learning estimates and store them in state.
   * PURPOSE: supplies estimate chips for room cards without requiring an active job.
   * RULES:
   * - monotonic request sequence prevents stale responses from overwriting newer state
   * - request-context validation discards responses from a previous vacuum/map
   * - estimates are cleared immediately when the vacuum or map changes
   */
  async loadRoomEstimates() {
    const state = this.card?._state;
    const actions = this.card?._actions;
    const config = this.card?._config;

    if (!state || !actions || !config) return;

    const requestVacuumEntityId = String(config.vacuum_entity_id ?? "");
    const requestMapId = String(state.activeMapId?.() ?? "");

    if (!requestVacuumEntityId || !requestMapId) return;

    const contextChanged =
      this._lastRoomEstimateVacuumEntityId !== requestVacuumEntityId ||
      this._lastRoomEstimateMapId !== requestMapId;

    if (contextChanged) {
      state.clearRoomEstimates();
      this.card._scheduleRender();
    }

    this._lastRoomEstimateVacuumEntityId = requestVacuumEntityId;
    this._lastRoomEstimateMapId = requestMapId;

    const requestSeq = ++this._roomEstimateRequestSeq;

    let result = null;

    try {
      result = await actions.getRoomLearningEstimates({
        vacuum_entity_id: requestVacuumEntityId,
        map_id: requestMapId,
        current_battery: state.batteryLevel?.(),
      });
    } catch (error) {
      if (requestSeq !== this._roomEstimateRequestSeq) return;

      console.warn(
        "[eufy-vacuum-command-center] Failed to load room learning estimates.",
        error
      );
      return;
    }

    if (requestSeq !== this._roomEstimateRequestSeq) return;
    if (!result) return;

    const currentVacuumEntityId = String(this.card?._config?.vacuum_entity_id ?? "");
    const currentMapId = String(this.card?._state?.activeMapId?.() ?? "");

    const responseVacuumEntityId = String(result.vacuum_entity_id ?? "");
    const responseMapId = String(result.map_id ?? "");

    if (currentVacuumEntityId !== requestVacuumEntityId) return;
    if (currentMapId !== requestMapId) return;

    if (responseVacuumEntityId && responseVacuumEntityId !== requestVacuumEntityId) return;
    if (responseMapId && responseMapId !== requestMapId) return;

    state.setRoomEstimates(result);
    this.card._scheduleRender();
  }
}
