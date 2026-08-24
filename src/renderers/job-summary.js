/**
 * ============================================================
 * RENDERERS: JOB SUMMARY MODAL
 * ============================================================
 *
 * What a run was asked to do, what happened in each room, and what went wrong.
 *
 * THE GAP THIS CLOSES. The job-history row said "3 errors" and everything else
 * lived in a JSON file. Chris can read a row, notice something is off, and go open
 * the record; the person this card is built for will not. So whatever is not on
 * this surface effectively does not exist for them.
 *
 * It is a JOB view that happens to include errors, not an error view — the warning
 * badge and the row itself open the SAME modal, so there is one surface to learn
 * rather than two.
 *
 * THE HONESTY RULES IT INHERITS, each from a measurement rather than a preference:
 *
 *   Omit, never zero. A field absent from the record is omitted. Rendering 0 for an
 *   unmeasured value asserts something stronger than "we did not measure it" — the
 *   REV-6 bug, where an absent battery block rendered as a confident "Battery 0".
 *
 *   Two cleaning times, not one. cleaning_seconds and cleaning_wall_seconds differ
 *   on 110 of 113 real timing entries; collapsing them silently picks a side.
 *
 *   No per-room battery. It exists in the record and does not reconcile with the
 *   job total (measured: 7 of 28 jobs agree), so showing it would make the modal
 *   contradict its own header.
 *
 *   "Not recovered", never "job stopped". recovered_at tells us whether a fault
 *   cleared. NOTHING in the record establishes that a fault ENDED a run, so the
 *   card must not imply causation it cannot support.
 *
 *   A room with settings and no result is normal — a queued room the run never
 *   reached leaves nothing to measure (26 of 139 alfred rooms, 24 of 31 ivy).
 *
 * ============================================================
 */

export function applyJobSummaryRenderers(proto) {
  /**
   * Render the job summary modal. Returns "" when closed, and also when the open
   * job has left the snapshot — a vanished job closes rather than freezing.
   *
   * @param {{ state: object }} ctx - Render context.
   * @returns {string} HTML string.
   */
  proto.renderJobSummaryModal = function (ctx) {
    const { state } = ctx;
    if (!state.isJobSummaryOpen?.()) return "";
    const job = state.activeJobSummary?.();
    if (!job) return "";

    const jobId = String(job.job_id ?? "");
    const isExternal = state.jobSummaryIsExternal?.() === true;

    return `
      <div class="evcc-modal-backdrop" data-action="close-job-summary">
        <div class="evcc-modal evcc-job-summary-modal" data-stop-propagation>

          <div class="evcc-modal-header">
            <div class="evcc-modal-title-group">
              <div class="evcc-modal-title">${this.t("job_summary.title")}</div>
              <div class="evcc-job-summary-subtitle">${this.escapeHtml(jobId)}</div>
            </div>
            <button
              type="button"
              class="evcc-chip evcc-chip--icon"
              data-action="close-job-summary"
              title="${this.t("common.close")}"
            >X</button>
          </div>

          <div class="evcc-modal-body">
            ${isExternal ? `
              <div class="evcc-job-summary-note">${this.t("job_summary.captured_from_app")}</div>
            ` : ""}
            ${this._renderJobSummaryOverall(state, job)}
            ${this._renderJobSummaryRooms(state)}
            ${this._renderJobSummaryFaults(state)}
          </div>

          <div class="evcc-modal-footer">
            <div class="evcc-modal-footer-row">
              <button type="button" class="evcc-btn evcc-btn-ghost" data-action="close-job-summary">
                ${this.t("common.close")}
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  };

  /* =========================================================
     1. OVERALL
     ========================================================= */
  proto._renderJobSummaryOverall = function (state, job) {
    const rows = [];
    const push = (label, value) => {
      if (value !== null && value !== undefined && value !== "") {
        rows.push(this._renderReviewKeyValue(label, String(value)));
      }
    };

    const started = this._formatReviewTimestamp?.(job.started_at);
    if (started) push(this.t("job_summary.started"), started);

    // Elapsed wall-clock and time actually spent cleaning are DIFFERENT numbers and
    // are labelled as such; the difference is the run's overhead.
    const mins = Number(job.duration_minutes);
    if (Number.isFinite(mins)) {
      push(this.t("job_summary.elapsed"), this._formatLearningMinutes(mins));
    }

    const cleaningS = Number(job.cleaning_time_seconds);
    if (Number.isFinite(cleaningS) && cleaningS > 0) {
      push(this.t("job_summary.cleaning_time"), this._formatJobSummaryDuration(cleaningS));
    }

    const area = Number(job.total_area_m2 ?? job.area_m2);
    if (Number.isFinite(area) && area > 0) {
      push(this.t("job_summary.area"), this.t("review.detail_area_m2", { value: area.toFixed(1) }));
    }

    // REV-6: `!= null` BEFORE the finite check. Number(null) is 0 and finite, so
    // isFinite alone let an ABSENT battery render as a confident "0".
    if (job.battery_used != null && Number.isFinite(Number(job.battery_used))) {
      push(this.t("job_summary.battery"),
           this.t("common.percent_value", { percent: Number(job.battery_used) }));
    }

    const roomCount = Number(job.room_count);
    if (Number.isFinite(roomCount) && roomCount > 0) {
      push(this.t("learning.stat_rooms"), String(roomCount));
    }

    // The recharge line. Without it a run that drew 55% reports "11% used", because
    // battery.used is start-minus-end and cannot see the pack going back up.
    const recharge = state.jobSummaryRecharge?.();
    const rechargeHtml = recharge
      ? `<div class="evcc-job-summary-recharge">${
          Number(recharge.seconds) > 0
            ? this.t("job_summary.recharged_for", {
                count: Number(recharge.count) || 1,
                duration: this._formatJobSummaryDuration(Number(recharge.seconds)),
              })
            : this.t("job_summary.recharged", { count: Number(recharge.count) || 1 })
        }</div>`
      : "";

    if (!rows.length && !rechargeHtml) return "";

    return `
      <section class="evcc-job-summary-section">
        <div class="evcc-job-summary-grid">${rows.join("")}</div>
        ${rechargeHtml}
      </section>
    `;
  };

  /* =========================================================
     2. PER ROOM
     ========================================================= */
  proto._renderJobSummaryRooms = function (state) {
    const rooms = state.jobSummaryRooms?.() ?? [];
    if (!rooms.length) return "";

    const body = rooms.map((room) => {
      const name = room.name || room.slug || this.t("review.unknown");

      // Settings are localized from the CODE, so the user's own language wins over
      // whatever English the backend spoke when the run finalized.
      const settings = room.settings && typeof room.settings === "object" ? room.settings : {};
      const chips = [
        ["clean_mode", settings.clean_mode],
        ["fan_speed", settings.fan_speed],
        // clean_intensity and path_type are ONE user-facing concept ("Cleaning
        // Path"); the card has unified them everywhere else and this follows suit.
        ["clean_intensity", settings.clean_intensity ?? settings.path_type],
        ["water_level", settings.water_level],
      ]
        .filter(([, v]) => v !== null && v !== undefined && v !== "")
        .map(([field, v]) => `<span class="evcc-chip evcc-chip--sm">${
          this.escapeHtml(this.tVocabRaw(field, String(v), this._formatReviewLabel(String(v))))
        }</span>`);

      const passes = Number(settings.clean_passes);
      if (Number.isFinite(passes) && passes > 1) {
        chips.push(`<span class="evcc-chip evcc-chip--sm">${
          this.t("review.passes", { count: passes })
        }</span>`);
      }
      if (settings.edge_mopping === true) {
        chips.push(`<span class="evcc-chip evcc-chip--sm">${
          this.t("room_editor.edge_mopping")
        }</span>`);
      }

      // Results. A queued room the run never reached has none — that is normal, and
      // the row still earns its place by showing what WOULD have been used.
      const results = [];
      const cs = Number(room.cleaning_seconds);
      const ws = Number(room.cleaning_wall_seconds);
      if (Number.isFinite(cs) && cs > 0) {
        results.push(this.t("job_summary.room_cleaning", { duration: this._formatJobSummaryDuration(cs) }));
      }
      // Only worth a second number when it actually differs from the first.
      if (Number.isFinite(ws) && ws > 0 && ws !== cs) {
        results.push(this.t("job_summary.room_elapsed", { duration: this._formatJobSummaryDuration(ws) }));
      }
      const ra = Number(room.area_m2);
      if (Number.isFinite(ra) && ra > 0) {
        results.push(this.t("review.detail_area_m2", { value: ra.toFixed(1) }));
      }

      return `
        <div class="evcc-job-summary-room">
          <div class="evcc-job-summary-room-name">${this.escapeHtml(String(name))}</div>
          ${chips.length ? `<div class="evcc-chips evcc-job-summary-room-chips">${chips.join("")}</div>` : ""}
          <div class="evcc-job-summary-room-result">${
            results.length
              ? this.escapeHtml(results.join(" · "))
              : `<span class="evcc-job-summary-muted">${this.t("job_summary.room_no_result")}</span>`
          }</div>
        </div>
      `;
    }).join("");

    return `
      <section class="evcc-job-summary-section">
        <div class="evcc-job-summary-section-title">${this.t("review.kv_rooms")}</div>
        ${body}
      </section>
    `;
  };

  /* =========================================================
     3. ERRORS  (omitted entirely when the run was clean)
     ========================================================= */
  proto._renderJobSummaryFaults = function (state) {
    const faults = state.jobSummaryFaults?.() ?? [];
    if (!faults.length) return "";

    const body = faults.map((f) => {
      // faultLabel lives on VacuumCardState (applyFaultState on state proto),
      // NOT on the renderer proto — so it MUST be called via the `state`
      // parameter, never via `this` on the renderer. A prior call to
      // this.faultLabel(...) shipped a runtime crash on every job that carried
      // a run_error (the exact scenario the fault section exists for).
      const label = state.faultLabel(f.label_key, f.code);

      const meta = [];
      const src = String(f.source ?? "").trim().toLowerCase();
      if (src === "dock") meta.push(this.t("job_summary.source_dock"));
      else if (src === "robot") meta.push(this.t("job_summary.source_robot"));
      else meta.push(this.t("job_summary.source_unknown"));

      // Recovery ONLY. "Job stopped" would assert a cause the record cannot support.
      meta.push(f.recovered === true
        ? this.t("job_summary.recovered")
        : this.t("job_summary.not_recovered"));

      return `
        <div class="evcc-job-summary-fault">
          <div class="evcc-job-summary-fault-name">${this.escapeHtml(String(label))}</div>
          <div class="evcc-job-summary-fault-meta">${this.escapeHtml(meta.join(" · "))}</div>
        </div>
      `;
    }).join("");

    return `
      <section class="evcc-job-summary-section evcc-job-summary-section--faults">
        <div class="evcc-job-summary-section-title">${
          this.t("job_summary.errors_count", { count: faults.length })
        }</div>
        ${body}
      </section>
    `;
  };

  /**
   * Seconds -> a HUMAN duration, using the card's existing hours+minutes format.
   *
   * A run is not a stopwatch reading. _formatLearningDuration renders "1h 41m" and
   * "17 min" through learning.hours_minutes / hours_only / minutes_only, which are
   * already translated in all 18 packs -- so this reuses that rather than inventing
   * a second duration convention for one modal.
   *
   * Below half a minute that formatter rounds to "0 min", which reads as "no time
   * at all" for something that demonstrably happened -- the same confident-zero
   * trap as REV-6's "Battery 0". Those keep their seconds. In the real corpus the
   * shortest room is 120 s, so this band is defensive rather than routine.
   */
  proto._formatJobSummaryDuration = function (seconds) {
    const s = Math.max(0, Math.round(Number(seconds) || 0));
    if (s < 30) return this.t("common.seconds_short", { seconds: s });
    return this._formatLearningDuration(s / 60);
  };
}
