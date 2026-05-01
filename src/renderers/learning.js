/**
 * ============================================================
 * RENDERERS: LEARNING
 * ============================================================
 *
 * Read-only UI rendering for the learning system — pre-job
 * estimate panel, live run banner, progress list, and the
 * reusable confidence chip. Augments the Rooms view.
 *
 * ============================================================
 */

/**
 * Mix learning renderer methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applyLearningRenderers(proto) {

  /* =========================================================
     PUBLIC ENTRY HELPERS
     ========================================================= */

  /**
   * Render a dismissible banner when the last job ended without cleaning all
   * queued rooms. Offers a one-click re-queue for missed rooms.
   * Hidden while a job is actively running.
   *
   * @param {object} state - Card state accessor.
   * @returns {string} HTML string, or empty string when not applicable.
   */
  proto.renderIncompleteRunBanner = function (state) {
    if (!state.hasIncompleteRunLog?.()) return "";

    // Hide during an active job — no point surfacing a retry while cleaning.
    if (state.learningJobActive?.()) return "";

    const log = state.incompleteRunLog();
    const missedRooms = state.incompleteRunMissedRooms();
    const missedCount = missedRooms.length;

    const outcomeStatus = String(log?.outcome_status ?? "cancelled").toLowerCase();
    const outcomeLabel = { cancelled: "cancelled", failed: "failed", interrupted: "interrupted" }[outcomeStatus] ?? outcomeStatus;

    const roomChips = missedRooms
      .map((r) => `<span class="evcc-incomplete-run-room">${this.escapeHtml(r.name)}</span>`)
      .join("");

    return `
      <div class="evcc-incomplete-run-banner" role="alert">
        <div class="evcc-incomplete-run-body">
          <div class="evcc-incomplete-run-title">
            Last run ${this.escapeHtml(outcomeLabel)} —
            ${missedCount} room${missedCount === 1 ? "" : "s"} missed
          </div>
          <div class="evcc-incomplete-run-rooms">${roomChips}</div>
        </div>
        <div class="evcc-incomplete-run-actions">
          <button
            class="evcc-incomplete-run-retry"
            data-action="queue-missed-rooms"
          >Queue missed rooms</button>
          <button
            class="evcc-incomplete-run-dismiss"
            data-action="dismiss-incomplete-run-log"
            aria-label="Dismiss"
          >✕</button>
        </div>
      </div>
    `;
  };

  /**
   * Render the pre-job estimate panel showing planned duration and water use.
   * Returns empty string when no estimate is available or a job is already active.
   *
   * @param {object} state - Card state accessor.
   * @returns {string} HTML string.
   */
  proto.renderLearningPreJobPanel = function (state) {
    const estimate = state.dashboardPlannedJobEstimate?.() ?? state.learningEstimate();
    if (!estimate) return "";

    if (estimate.error || estimate.available === false) {
      return `
        <div class="evcc-learning-panel evcc-learning-panel--empty">
          <div class="evcc-learning-panel-header">
            <div class="evcc-learning-panel-title">Estimate unavailable</div>
          </div>
          <div class="evcc-learning-empty-message">
            ${this.escapeHtml(
              estimate.error === "no_payload"
                ? "Queue rooms first to see an estimate"
                : estimate.message || estimate.error_detail || "Estimate unavailable."
            )}
          </div>
        </div>
      `;
    }

    const totalMinutes = this._formatLearningDuration(estimate.total_minutes);
    const jobEtaAt     = this._formatLearningWallClock(estimate.job_eta_at);
    const breakpoint   = estimate.confidence_breakpoint ?? null;
    const staleAt      = this._formatLearningWallClock(estimate.stats_rebuilt_at);
    const waterEstimate = state.dashboardPlannedWaterEstimate?.();
    const startStatus = state.dashboardStartStatus?.() ?? {};

    const overhead = estimate.overhead ?? {};
    const mopWash = overhead.mop_wash ?? {};
    const mopWashLabel =
      String(mopWash.mode ?? "") === "by_time" && Number(mopWash.cycle_count ?? 0) > 0
        ? `${this._formatLearningMinutes(overhead.mop_wash_minutes)} (${mopWash.cycle_count} cycle${Number(mopWash.cycle_count) === 1 ? "" : "s"} × ${this._formatLearningMinutes(mopWash.minutes_per_cycle)} every ${this._formatLearningMinutes(mopWash.interval_minutes)})`
        : `0 min (no cycles scheduled)`;

    return `
      <div class="evcc-learning-panel evcc-learning-panel--prejob">
        <div class="evcc-learning-panel-header">
          <div class="evcc-learning-panel-title-group">
            <div class="evcc-learning-panel-title">Estimated Job Time</div>
            <div class="evcc-learning-panel-subtitle">
              ${this.escapeHtml(totalMinutes)}
              ${jobEtaAt ? ` · done by ${this.escapeHtml(jobEtaAt)}` : ""}
            </div>
          </div>

          ${this.renderConfidenceChip(
            breakpoint,
            this._learningConfidenceLabel(
              estimate.confidence_label,
              "job"
            )
          )}
        </div>

        ${estimate.stats_stale ? `
          <div class="evcc-learning-notice evcc-learning-notice--stale">
            ⚠ Estimates may be outdated${staleAt ? ` (last rebuilt ${this.escapeHtml(staleAt)})` : ""}
          </div>
        ` : ""}

        ${estimate.battery_warning ? `
          <div class="evcc-learning-notice evcc-learning-notice--battery">
            ⚡ May need to recharge mid-job
          </div>
        ` : ""}

        ${startStatus?.water_warning_message && Number(waterEstimate?.mopping_room_count ?? 0) > 0 ? `
          <div class="evcc-learning-notice ${startStatus?.water_warning_reason === "not_enough_clean_water" ? "evcc-learning-notice--battery" : "evcc-learning-notice--stale"}">
            ${this.escapeHtml(startStatus.water_warning_message)}
          </div>
        ` : ""}

        ${this._renderLearningWaterEstimateChips(waterEstimate)}

        ${waterEstimate?.available && Number(waterEstimate.mopping_room_count ?? 0) > 0 ? `
          <div class="evcc-learning-water-summary">
            <div class="evcc-learning-panel-subtitle">Water estimate</div>

            <div class="evcc-learning-overhead-rows">
              <div class="evcc-learning-overhead-row">
                <span>Tank now</span>
                <span>
                  ${this.escapeHtml(this._formatLearningMilliliters(waterEstimate.available_clean_tank_ml))}
                  ${Number.isFinite(Number(waterEstimate.station_clean_water_percent))
                    ? ` (${this.escapeHtml(`${Math.round(Number(waterEstimate.station_clean_water_percent))}%`)})`
                    : ""}
                </span>
              </div>

              <div class="evcc-learning-overhead-row">
                <span>Job will use</span>
                <span>${this.escapeHtml(this._formatLearningMilliliters(waterEstimate.estimated_total_dock_clean_water_used_ml))}</span>
              </div>

              <div class="evcc-learning-overhead-row">
                <span>Tank after run</span>
                <span>
                  ${this.escapeHtml(this._formatLearningMilliliters(waterEstimate.estimated_clean_tank_remaining_ml))}
                  ${Number.isFinite(Number(waterEstimate.estimated_clean_tank_remaining_percent))
                    ? ` (${this.escapeHtml(`${Math.round(Number(waterEstimate.estimated_clean_tank_remaining_percent))}%`)})`
                    : ""}
                </span>
              </div>
            </div>
          </div>
        ` : ""}

        <details class="evcc-learning-overhead">
          <summary class="evcc-learning-overhead-summary">Overhead breakdown</summary>

          <div class="evcc-learning-overhead-rows">
            <div class="evcc-learning-overhead-row">
              <span>Startup</span>
              <span>${this.escapeHtml(this._formatLearningMinutes(overhead.startup_minutes))}</span>
            </div>

            <div class="evcc-learning-overhead-row">
              <span>Transitions</span>
              <span>${this.escapeHtml(this._formatLearningMinutes(overhead.transition_minutes))}</span>
            </div>

            <div class="evcc-learning-overhead-row">
              <span>Recharge</span>
              <span>${this.escapeHtml(this._formatLearningMinutes(overhead.recharge_minutes))}</span>
            </div>

            ${Number(mopWash.cycle_count ?? 0) > 0 ? `
              <div class="evcc-learning-overhead-row">
                <span>Mop wash</span>
                <span>${this.escapeHtml(mopWashLabel)}</span>
              </div>
            ` : ""}

            <div class="evcc-learning-overhead-row">
              <span>Dust empty</span>
              <span>${this.escapeHtml(this._formatLearningMinutes(overhead.dust_empty_minutes))}</span>
            </div>

            <div class="evcc-learning-overhead-row">
              <span>Return to dock</span>
              <span>${this.escapeHtml(this._formatLearningMinutes(overhead.return_minutes))}</span>
            </div>
          </div>
        </details>

      </div>
    `;
  };

  /**
   * Render the live run banner showing current/next room during an active job.
   * Returns empty string when no live queue is active.
   *
   * @param {object} state - Card state accessor.
   * @returns {string} HTML string.
   */
  proto.renderLearningLiveBanner = function (state) {
    if (!state.shouldShowLiveQueue()) return "";

    const nextRoom = state.learningLiveBannerRoom();
    const isAllComplete = state.learningAllCompleted?.() ?? false;
    const batteryWarning = Boolean(state.learningBatteryWarning?.());
    const bannerKey = isAllComplete
      ? "all-complete"
      : String(nextRoom?.room_id ?? "pending");

    return `
      <div
        class="evcc-learning-live-banner evcc-learning-live-banner--animated"
        data-learning-key="${this.escapeHtml(bannerKey)}"
      >
        ${isAllComplete ? `
          <div class="evcc-learning-live-banner-main">
            <div class="evcc-learning-live-title">All rooms complete</div>
            <div class="evcc-learning-live-subtitle">Returning to dock</div>
          </div>
        ` : nextRoom ? `
          <div class="evcc-learning-live-banner-main">
            <div class="evcc-learning-live-title">
              ▶ Cleaning ${this.escapeHtml(nextRoom.room_name ?? "Next room")}
            </div>

            <div class="evcc-learning-live-subtitle">
              ${nextRoom.eta_at ? `Done at ${this.escapeHtml(this._formatLearningWallClock(nextRoom.eta_at))}` : ""}
            </div>
          </div>

          ${this.renderConfidenceChip(
            nextRoom.confidence_breakpoint ?? null,
            this._learningConfidenceLabel(nextRoom.confidence_label, "room")
          )}
        ` : `
          <div class="evcc-learning-live-banner-main">
            <div class="evcc-learning-live-title">Learning active</div>
            <div class="evcc-learning-live-subtitle">Waiting for next room update</div>
          </div>
        `}
      </div>

      ${batteryWarning ? `
        <div class="evcc-learning-notice evcc-learning-notice--battery">
          ⚡ May need to recharge to finish remaining rooms
        </div>
      ` : ""}

      ${(() => {
        const progress = state.dashboardJobProgress?.();
        if (!progress?.stall_detected) return "";
        const elapsed  = Number(progress.stall_elapsed_minutes);
        const expected = Number(progress.stall_expected_minutes);
        const elapsedStr  = Number.isFinite(elapsed)  ? this._formatLearningMinutes(elapsed)  : null;
        const expectedStr = Number.isFinite(expected) ? this._formatLearningMinutes(expected) : null;
        const detail = elapsedStr && expectedStr
          ? ` (${elapsedStr} elapsed, expected ${expectedStr})`
          : elapsedStr ? ` (${elapsedStr} elapsed)` : "";
        return `
          <div class="evcc-learning-notice evcc-learning-notice--stall">
            ⏳ Robot may be stuck in current room${this.escapeHtml(detail)}
          </div>
        `;
      })()}
    `;
  };

  /**
   * Render the room-by-room progress list during an active job
   * (completed, in-progress, and remaining rooms with ETAs).
   *
   * @param {object} state - Card state accessor.
   * @returns {string} HTML string.
   */
  proto.renderLearningProgressList = function (state) {
    if (!state.shouldShowLiveQueue()) return "";

    const timeline = state.learningRoomTimeline();
    if (!timeline.length) return "";

    return `
      <div class="evcc-learning-progress">
        <div class="evcc-learning-progress-title">Live Progress</div>

        <div class="evcc-learning-progress-list">
          ${timeline.map((entry) => {
            if (entry.completed) {
              return this._renderLearningCompletedRow(entry);
            }

            if (entry.current) {
              return this._renderLearningCurrentRow(entry);
            }

            if (!entry.current && !entry.remaining && !entry.completed) {
              return this._renderLearningCurrentRow(entry);
            }

            return this._renderLearningRemainingRow(entry);
          }).join("")}
        </div>
      </div>
    `;
  };

  /**
   * Render a confidence-level chip for a room estimate breakpoint.
   *
   * @param {string} breakpoint - Confidence level key (e.g. "high", "medium", "low").
   * @param {string} label - Display text for the chip.
   * @param {string} [title=""] - Tooltip text.
   * @returns {string} HTML string, or empty string when inputs are absent.
   */
  proto.renderConfidenceChip = function (breakpoint, label, title = "") {
    if (!breakpoint || !label) return "";

    const variant = String(breakpoint.ui_variant ?? "").toLowerCase();
    const cls = {
      success: "evcc-learning-chip--success",
      warning: "evcc-learning-chip--warning",
      error:   "evcc-learning-chip--error",
    }[variant] ?? "evcc-learning-chip--neutral";

    return `
      <span class="evcc-learning-chip ${cls}" ${title ? `title="${this.escapeHtml(title)}"` : ""}>
        ${this.escapeHtml(label)}
      </span>
    `;
  };

  /* =========================================================
     INTERNAL ROW RENDERERS
     ========================================================= */

  proto._renderLearningWaterEstimateChips = function (waterEstimate) {
    if (!waterEstimate || waterEstimate.available === false) return "";

    const rooms = Array.isArray(waterEstimate.rooms) ? waterEstimate.rooms : [];
    const totalWaterUse = Number(waterEstimate.estimated_total_dock_clean_water_used_ml);
    const washCycleCount = Number(waterEstimate.wash_cycle_count ?? 0);

    let vacuumOnly = 0;
    let mopOnly = 0;
    let both = 0;

    for (const room of rooms) {
      const hasVacuum = String(room.clean_mode ?? "").includes("vacuum");
      const hasMop = Boolean(room.mop_active);
      if (hasVacuum && hasMop) both++;
      else if (hasVacuum) vacuumOnly++;
      else if (hasMop) mopOnly++;
    }

    if (vacuumOnly + mopOnly + both === 0) return "";

    const chips = [];

    if (Number.isFinite(totalWaterUse) && totalWaterUse > 0) {
      chips.push(`~${this._formatLearningMilliliters(totalWaterUse)} water`);
    }

    if (vacuumOnly > 0) chips.push(`${vacuumOnly} vacuum-only room${vacuumOnly === 1 ? "" : "s"}`);
    if (mopOnly   > 0) chips.push(`${mopOnly} mop-only room${mopOnly === 1 ? "" : "s"}`);
    if (both      > 0) chips.push(`${both} vacuum + mop room${both === 1 ? "" : "s"}`);

    if (washCycleCount > 0) {
      chips.push(`${washCycleCount} wash cycle${washCycleCount === 1 ? "" : "s"}`);
    }

    return chips.length ? `
      <div class="evcc-learning-chip-row">
        ${chips.map((label) => `
          <span class="evcc-learning-chip evcc-learning-chip--neutral">
            ${this.escapeHtml(label)}
          </span>
        `).join("")}
      </div>
    ` : "";
  };

  proto._renderLearningPreJobRow = function (entry) {
    const notes = [];

    if (entry.intensity_mismatch) {
      notes.push("⚠ estimated from different intensity");
    }

    if (entry.source === "default") {
      notes.push("No data yet");
    }

    if (Number(entry?.learning_velocity?.runs_to_high ?? 0) > 0) {
      notes.push(`${entry.learning_velocity.runs_to_high} runs to reliable`);
    }

    return `
      <div
        class="evcc-learning-room-row evcc-learning-room-row--prejob"
        data-learning-key="${this.escapeHtml(String(entry.room_id ?? entry.position ?? ""))}"
      >
        <div class="evcc-learning-room-main">
          <div class="evcc-learning-room-name">
            ${this.escapeHtml(entry.room_name ?? `Room ${entry.room_id ?? ""}`)}
          </div>

          <div class="evcc-learning-room-meta">
            ${this.escapeHtml(this._formatLearningMinutes(entry.minutes))}
            ${entry.eta_at ? ` · ${this.escapeHtml(this._formatLearningWallClock(entry.eta_at))}` : ""}
          </div>

          ${notes.length ? `
            <div class="evcc-learning-room-notes">
              ${notes.map((note) => `<div class="evcc-learning-room-note">${this.escapeHtml(note)}</div>`).join("")}
            </div>
          ` : ""}
        </div>

        ${this.renderConfidenceChip(
          entry.confidence_breakpoint ?? null,
          this._learningConfidenceLabel(entry.confidence_label, "room")
        )}
      </div>
    `;
  };

  proto._renderLearningCompletedRow = function (entry) {
    return `
      <div
        class="evcc-learning-progress-row evcc-learning-progress-row--completed evcc-learning-progress-row--animated"
        data-learning-key="${this.escapeHtml(String(entry.room_id ?? entry.position ?? ""))}"
      >
        <div class="evcc-learning-progress-main">
          <div class="evcc-learning-progress-name">
            ✓ ${this.escapeHtml(entry.room_name ?? `Room ${entry.room_id ?? ""}`)}
          </div>
          <div class="evcc-learning-progress-meta">
            ${this.escapeHtml(this._formatLearningMinutes(entry.actual_duration_minutes))}
          </div>
        </div>
      </div>
    `;
  };

proto._renderLearningCurrentRow = function (entry) {
  const snapshot =
    this.card?._learningController?.getRoomProgressSnapshot?.(entry.room_id) ?? null;

  const progressMeta = snapshot?.isCurrent
    ? `${snapshot.percent}%${Number.isFinite(snapshot.remainingMinutes) ? ` · ~${this._formatLearningMinutes(snapshot.remainingMinutes)} left` : ""}`
    : (entry.eta_at ? `Done at ${this.escapeHtml(this._formatLearningWallClock(entry.eta_at))}` : "");

  return `
    <div
      class="evcc-learning-progress-row evcc-learning-progress-row--current evcc-learning-progress-row--animated"
      data-learning-key="${this.escapeHtml(String(entry.room_id ?? entry.position ?? ""))}"
    >
      <div class="evcc-learning-progress-main">
        <div class="evcc-learning-progress-name">
          ▶ ${this.escapeHtml(entry.room_name ?? `Room ${entry.room_id ?? ""}`)}
        </div>
        <div class="evcc-learning-progress-meta">
          ${this.escapeHtml(progressMeta)}
        </div>
      </div>

      <div class="evcc-learning-progress-side">
        <div class="evcc-learning-progress-minutes">
          ${this.escapeHtml(this._formatLearningMinutes(entry.minutes))}
        </div>
        ${this.renderConfidenceChip(
          entry.confidence_breakpoint ?? null,
          this._learningConfidenceLabel(entry.confidence_label, "room")
        )}
      </div>
    </div>
  `;
};

  proto._renderLearningRemainingRow = function (entry) {
    return `
      <div
        class="evcc-learning-progress-row evcc-learning-progress-row--remaining evcc-learning-progress-row--animated"
        data-learning-key="${this.escapeHtml(String(entry.room_id ?? entry.position ?? ""))}"
      >
        <div class="evcc-learning-progress-main">
          <div class="evcc-learning-progress-name">
            ○ ${this.escapeHtml(entry.room_name ?? `Room ${entry.room_id ?? ""}`)}
          </div>
          <div class="evcc-learning-progress-meta">
            ${entry.eta_at ? this.escapeHtml(this._formatLearningWallClock(entry.eta_at)) : ""}
          </div>
        </div>
      </div>
    `;
  };

  /* =========================================================
     SHARED FORMATTERS
     ========================================================= */

  proto._formatLearningMinutes = function (value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "0 min";

    return `${n.toFixed(1).replace(/\.0$/, "")} min`;
  };

  proto._formatLearningDuration = function (value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "0 min";

    const rounded = Math.round(n);
    const hours = Math.floor(rounded / 60);
    const minutes = rounded % 60;

    if (hours <= 0) {
      return `${minutes} min`;
    }

    if (minutes <= 0) {
      return `${hours}h`;
    }

    return `${hours}h ${minutes}m`;
  };

  proto._formatLearningMilliliters = function (value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "Unknown";

    return `${Math.round(n)} ml`;
  };

  proto._formatLearningWallClock = function (value) {
    return this.formatTimestamp(value, {
      hour: "numeric",
      minute: "2-digit",
    }, "");
  };

  proto._learningConfidenceLabel = function (value, scope = "room") {
    const normalized = String(value ?? "").trim().toLowerCase();
    if (!normalized) return "";

    const title = normalized.charAt(0).toUpperCase() + normalized.slice(1);

    if (scope === "job") {
      return `${title} confidence`;
    }

    return title;
  };
  /* =========================================================
     POST-JOB SUMMARY
     ========================================================= */

  /**
   * Render the post-job learning summary panel shown after a run completes.
   *
   * @param {object} state - Card state.
   * @returns {string} HTML string.
   */
  proto.renderLearningSummary = function (state) {
  if (!state.hasLearningSummary()) return "";

  const summary = state.learningSummary();

  const total = this._formatLearningDuration(summary.total_minutes);
  const finishedAt = this._formatLearningWallClock(summary.finished_at);

  const predictedMinutes =
    Number(summary.predicted_total_minutes ?? summary.predicted_minutes);

  const hasPredicted = Number.isFinite(predictedMinutes);

  const deltaMinutes = hasPredicted
    ? Number(summary.total_minutes) - predictedMinutes
    : null;

  const deltaLabel = Number.isFinite(deltaMinutes)
    ? `${deltaMinutes > 0 ? "+" : ""}${this._formatLearningDuration(Math.abs(deltaMinutes))}`
    : "";

  return `
    <div class="evcc-learning-panel evcc-learning-panel--summary">

      <div class="evcc-learning-panel-header">
        <div class="evcc-learning-panel-title-group">
          <div class="evcc-learning-panel-title">Cleaning Complete</div>
          <div class="evcc-learning-panel-subtitle">
            ${finishedAt ? `Finished at ${this.escapeHtml(finishedAt)}` : ""}
          </div>
        </div>

        <button
          class="evcc-chip evcc-learning-chip--neutral"
          data-action="dismiss-learning-summary"
        >
          Dismiss
        </button>
      </div>

      <div class="evcc-learning-summary-stats">

        <div class="evcc-learning-summary-stat">
          <div class="evcc-learning-summary-value">${this.escapeHtml(total)}</div>
          <div class="evcc-learning-summary-label">Actual</div>
        </div>

        <div class="evcc-learning-summary-stat">
          <div class="evcc-learning-summary-value">${this.escapeHtml(summary.rooms_completed)}</div>
          <div class="evcc-learning-summary-label">Rooms</div>
        </div>

        ${hasPredicted ? `
          <div class="evcc-learning-summary-stat">
            <div class="evcc-learning-summary-value">${this.escapeHtml(this._formatLearningDuration(predictedMinutes))}</div>
            <div class="evcc-learning-summary-label">Predicted</div>
          </div>

          <div class="evcc-learning-summary-stat">
            <div class="evcc-learning-summary-value">${this.escapeHtml(deltaLabel)}</div>
            <div class="evcc-learning-summary-label">Delta</div>
          </div>
        ` : ""}

      </div>

      ${summary.battery_warning ? `
        <div class="evcc-learning-notice evcc-learning-notice--battery">
          ⚡ Recharge occurred during job
        </div>
      ` : ""}

    </div>
  `;
};
  
}
