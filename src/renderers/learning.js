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
    const outcomeLabel = {
      cancelled: this.t("learning.outcome_cancelled"),
      failed: this.t("learning.outcome_failed"),
      interrupted: this.t("learning.outcome_interrupted"),
    }[outcomeStatus] ?? this.escapeHtml(outcomeStatus);

    const roomChips = missedRooms
      .map((r) => `<span class="evcc-incomplete-run-room">${this.escapeHtml(r.name)}</span>`)
      .join("");

    return `
      <div class="evcc-incomplete-run-banner" role="alert">
        <div class="evcc-incomplete-run-body">
          <div class="evcc-incomplete-run-title">
            ${this.t("learning.incomplete_title", { outcome: outcomeLabel, count: missedCount })}
          </div>
          <div class="evcc-incomplete-run-rooms">${roomChips}</div>
        </div>
        <div class="evcc-incomplete-run-actions">
          <button
            class="evcc-incomplete-run-retry"
            data-action="queue-missed-rooms"
          >${this.t("learning.queue_missed_rooms")}</button>
          <button
            class="evcc-incomplete-run-dismiss"
            data-action="dismiss-incomplete-run-log"
            aria-label="${this.t("learning.dismiss_aria")}"
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
            <div class="evcc-learning-panel-title">${this.t("learning.estimate_unavailable_title")}</div>
          </div>
          <div class="evcc-learning-empty-message">
            ${estimate.error === "no_payload"
              ? this.t("learning.estimate_queue_first")
              : this.escapeHtml(estimate.message || estimate.error_detail) || this.t("learning.estimate_unavailable_message")}
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
        ? this.t("learning.mop_wash_label", {
            total: this._formatLearningMinutes(overhead.mop_wash_minutes),
            count: mopWash.cycle_count,
            per: this._formatLearningMinutes(mopWash.minutes_per_cycle),
            interval: this._formatLearningMinutes(mopWash.interval_minutes),
          })
        : this.t("learning.mop_wash_label_none");

    return `
      <div class="evcc-learning-panel evcc-learning-panel--prejob">
        <div class="evcc-learning-panel-header">
          <div class="evcc-learning-panel-title-group">
            <div class="evcc-learning-panel-title">${this.t("learning.estimated_job_time")}</div>
            <div class="evcc-learning-panel-subtitle">
              ${this.escapeHtml(totalMinutes)}
              ${jobEtaAt ? ` · ${this.t("learning.done_by", { time: this.escapeHtml(jobEtaAt) })}` : ""}
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
            ⚠ ${staleAt ? this.t("learning.stats_stale_with_time", { time: this.escapeHtml(staleAt) }) : this.t("learning.stats_stale")}
          </div>
        ` : ""}

        ${estimate.battery_warning ? `
          <div class="evcc-learning-notice evcc-learning-notice--battery">
            ⚡ ${this.t("learning.battery_mid_job")}
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
            <div class="evcc-learning-panel-subtitle">${this.t("learning.water_estimate")}</div>

            <div class="evcc-learning-overhead-rows">
              <div class="evcc-learning-overhead-row">
                <span>${this.t("learning.tank_now")}</span>
                <span>
                  ${this.escapeHtml(this._formatLearningMilliliters(waterEstimate.available_clean_tank_ml))}
                  ${Number.isFinite(Number(waterEstimate.station_clean_water_percent))
                    ? ` (${this.escapeHtml(`${Math.round(Number(waterEstimate.station_clean_water_percent))}%`)})`
                    : ""}
                </span>
              </div>

              <div class="evcc-learning-overhead-row">
                <span>${this.t("learning.job_will_use")}</span>
                <span>${this.escapeHtml(this._formatLearningMilliliters(waterEstimate.estimated_total_dock_clean_water_used_ml))}</span>
              </div>

              <div class="evcc-learning-overhead-row">
                <span>${this.t("learning.tank_after_run")}</span>
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
          <summary class="evcc-learning-overhead-summary">${this.t("learning.overhead_breakdown")}</summary>

          <div class="evcc-learning-overhead-rows">
            <div class="evcc-learning-overhead-row">
              <span>${this.t("learning.overhead_startup")}</span>
              <span>${this.escapeHtml(this._formatLearningMinutes(overhead.startup_minutes))}</span>
            </div>

            <div class="evcc-learning-overhead-row">
              <span>${this.t("learning.overhead_transitions")}</span>
              <span>${this.escapeHtml(this._formatLearningMinutes(overhead.transition_minutes))}</span>
            </div>

            <div class="evcc-learning-overhead-row">
              <span>${this.t("learning.overhead_recharge")}</span>
              <span>${this.escapeHtml(this._formatLearningMinutes(overhead.recharge_minutes))}</span>
            </div>

            ${Number(mopWash.cycle_count ?? 0) > 0 ? `
              <div class="evcc-learning-overhead-row">
                <span>${this.t("learning.overhead_mop_wash")}</span>
                <span>${mopWashLabel}</span>
              </div>
            ` : ""}

            <div class="evcc-learning-overhead-row">
              <span>${this.t("learning.overhead_dust_empty")}</span>
              <span>${this.escapeHtml(this._formatLearningMinutes(overhead.dust_empty_minutes))}</span>
            </div>

            <div class="evcc-learning-overhead-row">
              <span>${this.t("learning.overhead_return")}</span>
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
            <div class="evcc-learning-live-title">${this.t("learning.all_rooms_complete")}</div>
            <div class="evcc-learning-live-subtitle">${this.t("learning.returning_to_dock")}</div>
          </div>
        ` : nextRoom ? `
          <div class="evcc-learning-live-banner-main">
            <div class="evcc-learning-live-title">
              ▶ ${this.t("learning.cleaning_room", { room: this.escapeHtml(nextRoom.room_name ?? this.t("learning.next_room")) })}
            </div>

            <div class="evcc-learning-live-subtitle">
              ${nextRoom.eta_at ? this.t("learning.done_at", { time: this.escapeHtml(this._formatLearningWallClock(nextRoom.eta_at)) }) : ""}
            </div>
          </div>

          ${this.renderConfidenceChip(
            nextRoom.confidence_breakpoint ?? null,
            this._learningConfidenceLabel(nextRoom.confidence_label, "room")
          )}
        ` : `
          <div class="evcc-learning-live-banner-main">
            <div class="evcc-learning-live-title">${this.t("learning.learning_active")}</div>
            <div class="evcc-learning-live-subtitle">${this.t("learning.waiting_next_room")}</div>
          </div>
        `}
      </div>

      ${batteryWarning ? `
        <div class="evcc-learning-notice evcc-learning-notice--battery">
          ⚡ ${this.t("learning.battery_finish_rooms")}
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
          ? ` ${this.t("learning.stall_detail_expected", { elapsed: this.escapeHtml(elapsedStr), expected: this.escapeHtml(expectedStr) })}`
          : elapsedStr ? ` ${this.t("learning.stall_detail", { elapsed: this.escapeHtml(elapsedStr) })}` : "";
        return `
          <div class="evcc-learning-notice evcc-learning-notice--stall">
            ⏳ ${this.t("learning.robot_stuck")}${detail}
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
        <div class="evcc-learning-progress-title">${this.t("learning.live_progress")}</div>

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
      chips.push(this.t("learning.chip_water", { ml: this.escapeHtml(this._formatLearningMilliliters(totalWaterUse)) }));
    }

    if (vacuumOnly > 0) {
      chips.push(this.t("learning.chip_vacuum_only", { count: vacuumOnly }));
    }
    if (mopOnly > 0) {
      chips.push(this.t("learning.chip_mop_only", { count: mopOnly }));
    }
    if (both > 0) {
      chips.push(this.t("learning.chip_vacuum_mop", { count: both }));
    }

    if (washCycleCount > 0) {
      chips.push(this.t("learning.chip_wash_cycle", { count: washCycleCount }));
    }

    return chips.length ? `
      <div class="evcc-learning-chip-row">
        ${chips.map((label) => `
          <span class="evcc-learning-chip evcc-learning-chip--neutral">
            ${label}
          </span>
        `).join("")}
      </div>
    ` : "";
  };

  proto._renderLearningPreJobRow = function (entry) {
    const notes = [];

    if (entry.intensity_mismatch) {
      notes.push(`⚠ ${this.t("learning.note_intensity_mismatch")}`);
    }

    if (entry.source === "default") {
      notes.push(this.t("learning.note_no_data"));
    }

    if (Number(entry?.learning_velocity?.runs_to_high ?? 0) > 0) {
      const runs = entry.learning_velocity.runs_to_high;
      notes.push(this.t("learning.note_runs_to_reliable", { count: runs }));
    }

    return `
      <div
        class="evcc-learning-room-row evcc-learning-room-row--prejob"
        data-learning-key="${this.escapeHtml(String(entry.room_id ?? entry.position ?? ""))}"
      >
        <div class="evcc-learning-room-main">
          <div class="evcc-learning-room-name">
            ${entry.room_name != null ? this.escapeHtml(entry.room_name) : this.t("learning.room_fallback", { id: this.escapeHtml(String(entry.room_id ?? "")) })}
          </div>

          <div class="evcc-learning-room-meta">
            ${this.escapeHtml(this._formatLearningMinutes(entry.minutes))}
            ${entry.eta_at ? ` · ${this.escapeHtml(this._formatLearningWallClock(entry.eta_at))}` : ""}
          </div>

          ${notes.length ? `
            <div class="evcc-learning-room-notes">
              ${notes.map((note) => `<div class="evcc-learning-room-note">${note}</div>`).join("")}
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
            ✓ ${entry.room_name != null ? this.escapeHtml(entry.room_name) : this.t("learning.room_fallback", { id: this.escapeHtml(String(entry.room_id ?? "")) })}
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
    ? `${snapshot.percent}%${Number.isFinite(snapshot.remainingMinutes) ? ` · ${this.t("learning.minutes_left", { minutes: this.escapeHtml(this._formatLearningMinutes(snapshot.remainingMinutes)) })}` : ""}`
    : (entry.eta_at ? this.t("learning.done_at", { time: this.escapeHtml(this._formatLearningWallClock(entry.eta_at)) }) : "");

  return `
    <div
      class="evcc-learning-progress-row evcc-learning-progress-row--current evcc-learning-progress-row--animated"
      data-learning-key="${this.escapeHtml(String(entry.room_id ?? entry.position ?? ""))}"
    >
      <div class="evcc-learning-progress-main">
        <div class="evcc-learning-progress-name">
          ▶ ${entry.room_name != null ? this.escapeHtml(entry.room_name) : this.t("learning.room_fallback", { id: this.escapeHtml(String(entry.room_id ?? "")) })}
        </div>
        <div class="evcc-learning-progress-meta">
          ${progressMeta}
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
            ○ ${entry.room_name != null ? this.escapeHtml(entry.room_name) : this.t("learning.room_fallback", { id: this.escapeHtml(String(entry.room_id ?? "")) })}
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
    if (!Number.isFinite(n)) return this.t("learning.minutes_short", { value: "0" });

    return this.t("learning.minutes_short", { value: n.toFixed(1).replace(/\.0$/, "") });
  };

  proto._formatLearningDuration = function (value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return this.t("learning.minutes_only", { minutes: 0 });

    const rounded = Math.round(n);
    const hours = Math.floor(rounded / 60);
    const minutes = rounded % 60;

    if (hours <= 0) {
      return this.t("learning.minutes_only", { minutes });
    }

    if (minutes <= 0) {
      return this.t("learning.hours_only", { hours });
    }

    return this.t("learning.hours_minutes", { hours, minutes });
  };

  proto._formatLearningMilliliters = function (value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return this.t("learning.unknown");

    return this.t("learning.milliliters", { ml: Math.round(n) });
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

    // Known confidence tiers (estimator breakpoint keys: high/medium/low) get a
    // translated label; an unknown value falls back to a title-cased raw string.
    const known = normalized === "high" || normalized === "medium" || normalized === "low";
    const title = known
      ? this.t(`learning.confidence_${normalized}`)
      : normalized.charAt(0).toUpperCase() + normalized.slice(1);

    if (scope === "job") {
      if (known) return this.t(`learning.confidence_${normalized}_job`);
      return this.t("learning.confidence_job_suffix", { label: title });
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
          <div class="evcc-learning-panel-title">${this.t("learning.cleaning_complete")}</div>
          <div class="evcc-learning-panel-subtitle">
            ${finishedAt ? this.t("learning.finished_at", { time: this.escapeHtml(finishedAt) }) : ""}
          </div>
        </div>

        <button
          class="evcc-chip evcc-learning-chip--neutral"
          data-action="dismiss-learning-summary"
        >
          ${this.t("learning.dismiss")}
        </button>
      </div>

      <div class="evcc-learning-summary-stats">

        <div class="evcc-learning-summary-stat">
          <div class="evcc-learning-summary-value">${this.escapeHtml(total)}</div>
          <div class="evcc-learning-summary-label">${this.t("learning.stat_actual")}</div>
        </div>

        <div class="evcc-learning-summary-stat">
          <div class="evcc-learning-summary-value">${this.escapeHtml(summary.rooms_completed)}</div>
          <div class="evcc-learning-summary-label">${this.t("learning.stat_rooms")}</div>
        </div>

        ${hasPredicted ? `
          <div class="evcc-learning-summary-stat">
            <div class="evcc-learning-summary-value">${this.escapeHtml(this._formatLearningDuration(predictedMinutes))}</div>
            <div class="evcc-learning-summary-label">${this.t("learning.stat_predicted")}</div>
          </div>

          <div class="evcc-learning-summary-stat">
            <div class="evcc-learning-summary-value">${this.escapeHtml(deltaLabel)}</div>
            <div class="evcc-learning-summary-label">${this.t("learning.stat_delta")}</div>
          </div>
        ` : ""}

      </div>

      ${summary.battery_warning ? `
        <div class="evcc-learning-notice evcc-learning-notice--battery">
          ⚡ ${this.t("learning.battery_recharged")}
        </div>
      ` : ""}

    </div>
  `;
};
  
}
