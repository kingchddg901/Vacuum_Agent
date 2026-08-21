/**
 * ============================================================
 * RENDERERS: LEARNING REVIEW
 * ============================================================
 *
 * Renders the Learning Review view — filterable job history with
 * profile matcher and per-job room cards for excluding bad runs.
 *
 * ============================================================
 */

/**
 * Optional badge glyphs, keyed by a badge's `icon` field. A badge without one
 * renders exactly as before, so this is opt-in per badge rather than per class.
 *
 * INLINE SVG, NOT A UNICODE GLYPH. U+26A0 WARNING SIGN was the obvious choice and
 * fails three ways here: it is absent from BOTH shipped OpenDyslexic faces (1586
 * codepoints, measured — so the font we serve for dyslexic users would fall back
 * mid-row), it has dual text/emoji presentation so bare it renders monochrome on
 * some platforms and as the colour emoji on others, and the emoji presentation
 * IGNORES CSS color — it would sit in a `--evcc-sem-warning` row refusing the
 * theme, invisibly to check-styles, which lints CSS declarations and cannot see a
 * glyph that bypasses CSS entirely.
 *
 * `currentColor` inherits the chip's semantic colour, so the icon is themed by the
 * same token as its text and needs no colour of its own.
 *
 * aria-hidden: the badge TEXT is the accessible name and is already translated in
 * every shipped locale. The triangle is scannability — it lets a faulted run be
 * spotted down a long list without reading — and the shape is ISO 7010 W001, about
 * as close to language-independent as iconography gets. It is deliberately NOT
 * carrying meaning alone: a bare glyph has no accessible name, and colour-blind
 * users lose the amber cue.
 */
const BADGE_ICONS = Object.freeze({
  warning:
    '<svg class="evcc-chip-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
    '<path fill="currentColor" fill-rule="evenodd" ' +
    'd="M12.86 3.48a1 1 0 0 0-1.72 0L1.4 20.5A1 1 0 0 0 2.26 22h19.48a1 1 0 0 0 .86-1.5L12.86 3.48Z' +
    'M11 9.25a1 1 0 0 1 2 0v5.5a1 1 0 0 1-2 0v-5.5Z' +
    'M12 16.9a1.25 1.25 0 1 0 0 2.5 1.25 1.25 0 0 0 0-2.5Z"/></svg>',
});

/**
 * Mix learning review renderer methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applyReviewRenderers(proto) {

  /* =========================================================
     MAIN VIEW
     ========================================================= */

  /**
   * Render the full Learning Review view with stats, filters, profile matcher, and job list.
   *
   * @param {object} ctx - Render context containing `state`.
   * @returns {string} HTML string.
   */
  proto.renderLearningReviewView = function (ctx) {
    const { state } = ctx;
    const strip = this._renderReviewSubtabStrip(state);
    const inner = state.reviewSubtab() === "external"
      ? this.renderExternalJobsSubtab(ctx)
      : this._renderLearningHistoryView(ctx);
    return `<div class="evcc-review-shell">${strip}${inner}</div>`;
  };

  proto._renderLearningHistoryView = function (ctx) {
    const { state } = ctx;
    const snapshot = state.learningHistorySnapshot?.();
    if (!snapshot) {
      return `<div class="evcc-empty">${this.t("review.loading")}</div>`;
    }

    if (snapshot.available === false) {
      return `
        <div class="evcc-review-view">
          <div class="evcc-empty">
            ${this.escapeHtml(
              // Same code->vocab routing as the metrics view: reason is a
              // backend CODE, message the English fallback. Escaped once here.
              this.tVocabRaw("snapshot_reason", snapshot.reason,
                snapshot.message || snapshot.reason || this.tRaw("review.unavailable"))
            )}
          </div>
        </div>
      `;
    }

    const summary = snapshot.summary ?? {};
    const jobs = this._getSortedLearningReviewJobs(state, snapshot.jobs ?? []);

    return `
      <div class="evcc-review-view">
        <div class="evcc-review-grid">

          <section class="evcc-review-panel">
            <div class="evcc-review-panel-header">
              <div>
                <div class="evcc-review-panel-title">${this.t("review.panel_title")}</div>
                <div class="evcc-review-panel-subtitle">
                  ${this.t("review.panel_subtitle")}
                </div>
              </div>
            </div>

            <div class="evcc-review-stats">
              ${this._renderReviewStat(this.t("review.stat_jobs"), summary?.filtered_job_count ?? summary?.job_count ?? 0)}
              ${this._renderReviewStat(this.t("review.stat_rooms"), summary?.filtered_room_count ?? 0)}
              ${this._renderReviewStat(this.t("review.stat_profiles"), summary?.filtered_room_profile_count ?? 0)}
              ${this._renderReviewStat(this.t("review.stat_updated"), this._formatReviewTimestamp(snapshot.updated_at) || this.t("review.unknown"))}
            </div>
          </section>

          <section class="evcc-review-panel evcc-review-panel--wide">
            <div class="evcc-review-panel-header">
              <div>
                <div class="evcc-review-panel-title">${this.t("review.filters_title")}</div>
                <div class="evcc-review-panel-subtitle">${this.t("review.filters_subtitle")}</div>
              </div>
            </div>

            <div class="evcc-review-filters">
              ${this._renderReviewChipFilter(this.t("review.filter_room"), "room_slug", state.learningHistoryRooms?.().map((room) => ({
                value: room?.room_slug ?? room?.slug ?? "",
                label: room?.room_name ?? room?.label ?? room?.slug ?? this.t("review.room_fallback"),
              })), state.learningHistoryFilters?.().room_slug, this.t("review.filter_all_rooms"))}

              ${/* R2-BUG-2. Keyed on the SAVED PROFILE, not the per-room settings signature.
                    The old row mapped profile_key, whose label reads "Dining Room Vacuum
                    Quick · Quick · Quiet" — the room name inside the profile chip. That
                    made the ROOM row above redundant (picking a signature already pins the
                    room), grew the column as rooms × profiles × settings so it needed
                    scroll arrows, and could not filter jobs at all: a job spans rooms, so
                    _job_matches ignored it while the chip still rendered active. */ ""}
              ${this._renderReviewChipFilter(this.t("review.filter_profile"), "profile_name", state.learningHistoryProfileNames?.() ?? [], state.learningHistoryFilters?.().profile_name, this.t("review.filter_all_profiles"))}

              ${this._renderReviewChipFilter(this.t("review.filter_status"), "status", state.learningHistoryStatusOptions?.(), state.learningHistoryFilters?.().status, this.t("review.filter_all_statuses"))}

              ${this._renderReviewChipFilter(this.t("review.filter_learning_use"), "used_for_learning", state.learningHistoryUsedOptions?.(), state.learningHistoryFilters?.().used_for_learning, this.t("review.filter_all_learning_use"))}

              ${this._renderReviewChipFilter(this.t("review.filter_origin"), "origin", state.learningHistoryOriginOptions?.(), state.learningHistoryFilters?.().origin, this.t("review.filter_all_origins"))}

              ${/* NO fallback chip here, unlike every other filter in this row. Sort is not
                    a filter: learningHistorySort() defaults to NEWEST and never returns "",
                    and setLearningHistorySort("") is rejected by the REVIEW_SORTS membership
                    check — so an empty-valued "all" chip could never be active and clicking
                    it did nothing. It also rendered the SAME label as the real Newest option
                    (both resolve through tVocab), so the row showed "Newest" twice with the
                    second one selected. The options list is already complete and exactly one
                    is always selected. */ ""}
              ${this._renderReviewChipFilter(this.t("review.filter_sort"), "sort", state.learningHistorySortOptions?.(), state.learningHistorySort?.(), "", "", false)}
            </div>
          </section>

          <section class="evcc-review-panel evcc-review-panel--wide">
            <div class="evcc-review-panel-header">
              <div>
                <div class="evcc-review-panel-title">${this.t("review.matcher_title")}</div>
                <div class="evcc-review-panel-subtitle">${this.t("review.matcher_subtitle")}</div>
              </div>
            </div>

            ${this._renderReviewProfileMatcher(state)}
          </section>

          <section class="evcc-review-panel evcc-review-panel--wide">
            <div class="evcc-review-panel-header">
              <div>
                <div class="evcc-review-panel-title">${this.t("review.runs_title")}</div>
                <div class="evcc-review-panel-subtitle">${this.t("review.runs_subtitle")}</div>
                ${summary?.jobs_truncated === true ? `
                  <div class="evcc-review-panel-subtitle evcc-review-truncation-note">${this.t("review.runs_truncated", {
                    shown: Number(summary?.returned_job_count ?? jobs.length),
                    total: Number(summary?.filtered_job_count ?? 0),
                  })}</div>
                ` : ""}
              </div>
            </div>

            ${jobs.length ? `
              <div class="evcc-review-job-list">
                ${jobs.map((job) => this._renderLearningReviewJobCard(job, state)).join("")}
              </div>
            ` : `
              <div class="evcc-review-empty">${this.t("review.runs_empty")}</div>
            `}
          </section>

        </div>
      </div>
    `;
  };

  /* =========================================================
     FILTER CONTROLS
     ========================================================= */

  /**
   * Render a single stat cell (value + label) in the overview header.
   *
   * @param {string} label - Stat label.
   * @param {string|number} value - Stat value.
   * @returns {string} HTML string.
   */
  proto._renderReviewStat = function (label, value) {
    return `
      <div class="evcc-review-stat">
        <div class="evcc-review-stat-value">${this.escapeHtml(value)}</div>
        <div class="evcc-review-stat-label">${label}</div>
      </div>
    `;
  };

  /**
   * Render a `<select>` filter for a single review dimension.
   *
   * @param {string} label - Visible field label.
   * @param {string} key - data-review-filter key.
   * @param {Array<{value:string,label:string}>} options - Filter options.
   * @param {string} selected - Currently selected value.
   * @param {string} fallbackLabel - Label for the empty / "all" option.
   * @param {boolean} [isSort] - When true, omits the fallback "all" option.
   * @returns {string} HTML string.
   */
  proto._renderReviewSelect = function (label, key, options, selected, fallbackLabel, isSort = false) {
    const safeOptions = Array.isArray(options) ? options : [];
    const normalized = safeOptions.length
      ? safeOptions
      : [{ value: "", label: fallbackLabel }];

    const finalOptions = isSort
      ? normalized
      : [{ value: "", label: fallbackLabel }, ...normalized.filter((opt) => String(opt?.value ?? "") !== "")];

    return `
      <label class="evcc-field evcc-review-filter">
        <span class="evcc-field-label">${label}</span>
        <select data-review-filter="${this.escapeHtml(key)}">
          ${finalOptions.map((opt) => `
            <option
              value="${this.escapeHtml(String(opt?.value ?? ""))}"
              ${String(opt?.value ?? "") === String(selected ?? "") ? "selected" : ""}
            >${this.escapeHtml(String(opt?.label ?? opt?.value ?? ""))}</option>
          `).join("")}
        </select>
      </label>
    `;
  };

  /**
   * Render a chip-button filter row for a single review dimension.
   *
   * @param {string} label - Visible field label.
   * @param {string} key - data-review-filter-chip key.
   * @param {Array<{value:string,label:string,title?:string}>} options - Filter options.
   * @param {string} selected - Currently selected value.
   * @param {string} fallbackLabel - Label for the "all" fallback chip.
   * @param {string} [emptyValue] - Value used for the fallback chip (default "").
   * @param {boolean} [includeFallback] - Whether to prepend the fallback chip.
   * @returns {string} HTML string.
   */
  proto._renderReviewChipFilter = function (label, key, options, selected, fallbackLabel, emptyValue = "", includeFallback = true) {
    const safeOptions = Array.isArray(options) ? options : [];
    const normalized = safeOptions
      .filter((opt) => opt && typeof opt === "object")
      .map((opt) => ({
        value: String(opt?.value ?? ""),
        label: String(opt?.label ?? opt?.value ?? ""),
        title: String(opt?.title ?? opt?.label ?? opt?.value ?? ""),
      }));

    const finalOptions = includeFallback
      ? [{ value: String(emptyValue), label: fallbackLabel }, ...normalized.filter((opt) => opt.value !== String(emptyValue))]
      : normalized;

    const searchable = key === "profile_key";
    const head = searchable
      ? `<div class="evcc-chip-filter-head">
           <div class="evcc-field-label">${label}</div>
           <input type="text" class="evcc-chip-search" data-chip-search placeholder="${this.t("review.search_placeholder")}" aria-label="${this.t("review.search_aria", { label: this.escapeHtml(label) })}">
         </div>`
      : `<div class="evcc-field-label">${label}</div>`;
    return `
      <div class="evcc-review-chip-filter${searchable ? " evcc-chip-filter--searchable" : ""}" data-chip-filter-group>
        ${head}
        <div class="evcc-chips evcc-review-filter-chips">
          ${finalOptions.map((opt, i) => `
            <button
              type="button"
              class="evcc-chip ${String(opt.value) === String(selected ?? "") ? "active" : ""}"
              data-review-filter-chip="${this.escapeHtml(key)}"
              data-value="${this.escapeHtml(opt.value)}"
              ${i === 0 && includeFallback ? `data-all-chip="true"` : ""}
              title="${this.escapeHtml(this.tVocabRaw(key, opt.value, opt.title))}"
            >${i === 0 && includeFallback ? opt.label : this.tVocab(key, opt.value, opt.label)}</button>
          `).join("")}
        </div>
      </div>
    `;
  };

  /* =========================================================
     PROFILE MATCHER
     ========================================================= */

  /**
   * Render the profile matcher panel — field chips, reset button, and match chips.
   *
   * @param {object} state - Card state.
   * @returns {string} HTML string, or empty string if no matcher fields exist.
   */
  proto._renderReviewProfileMatcher = function (state) {
    const fields = state.reviewProfileMatcherFields?.();
    if (!fields) return "";

    const matches = state.reviewProfileMatcherMatches?.() ?? [];
    const profileFilter = state.learningHistoryFilters?.().profile_key ?? "";

    return `
      <div class="evcc-review-matcher">
        <div class="evcc-review-matcher-grid">
          ${this._renderReviewMatcherField(this.t("review.matcher_clean_mode"), "clean_mode", fields.clean_mode, state.cleanModeOptions?.() ?? [])}
          ${this._renderReviewMatcherField(this.t("review.matcher_suction_level"), "fan_speed", fields.fan_speed, state.suctionLevelOptions?.() ?? [])}
          ${state.showReviewProfileMatcherWaterLevel?.()
            ? this._renderReviewMatcherField(this.t("review.matcher_water_level"), "water_level", fields.water_level, state.waterLevelOptions?.() ?? [])
            : ""}
          ${this._renderReviewMatcherField(this.t("review.matcher_clean_path"), "clean_intensity", fields.clean_intensity, state.cleanIntensityOptions?.() ?? [])}
          ${this._renderReviewMatcherField(this.t("review.matcher_clean_passes"), "clean_passes", fields.clean_passes, [
            { value: 1, label: this.t("review.passes", { count: 1 }) },
            { value: 2, label: this.t("review.passes", { count: 2 }) },
          ])}
          ${state.showReviewProfileMatcherEdgeMopping?.()
            ? this._renderReviewMatcherField(this.t("review.matcher_edge_mopping"), "edge_mopping", fields.edge_mopping, [
              { value: true, label: this.t("common.on") },
              { value: false, label: this.t("common.off") },
            ])
            : ""}
        </div>

        <div class="evcc-review-matcher-actions">
          <button
            type="button"
            class="evcc-chip"
            data-review-matcher-action="reset"
          >${this.t("review.matcher_reset")}</button>
        </div>

        <div class="evcc-review-matcher-results">
          <div class="evcc-review-matcher-results-header">
            <div class="evcc-review-panel-title">${this.t("review.matched_profiles_title")}</div>
            <div class="evcc-review-panel-subtitle">
              ${matches.length
                ? this.t("review.matcher_count", { count: matches.length })
                : this.t("review.matcher_no_matches")}
            </div>
          </div>

          ${matches.length ? `
            <div class="evcc-chips evcc-review-matcher-match-chips">
              ${matches.map((match) => `
                <button
                  type="button"
                  class="evcc-chip ${String(profileFilter) === String(match.profile_key) ? "active" : ""}"
                  data-review-matcher-profile="${this.escapeHtml(match.profile_key)}"
                  title="${this.t("review.matcher_chip_title")}"
                >${this.escapeHtml(this._localizedProfile(match).label || match.label || match.profile_key)}</button>
              `).join("")}
            </div>
          ` : `
            <div class="evcc-review-empty">${this.t("review.matcher_empty")}</div>
          `}
        </div>
      </div>
    `;
  };

  /**
   * Render a single matcher field chip row.
   *
   * @param {string} label - Field label.
   * @param {string} key - data-review-matcher-field key.
   * @param {*} selected - Currently selected value.
   * @param {Array} options - Options array (objects with value/label, or primitives).
   * @returns {string} HTML string, or empty string if no valid options.
   */
  proto._renderReviewMatcherField = function (label, key, selected, options) {
    const normalized = (Array.isArray(options) ? options : [])
      .map((option) => {
        if (option && typeof option === "object" && "value" in option) {
          return {
            value: option.value,
            label: option.label ?? option.value,
          };
        }

        return {
          value: option,
          label: option,
        };
      })
      .filter((option) => option.value != null && String(option.value).trim() !== "");

    if (!normalized.length) return "";

    // CC-5: this compared `String(option.value) === String(selected)` while
    // setReviewProfileMatcherField stores the DISPLAY-canonicalised clean mode.
    // The option carries the ADAPTER's declared token ("vacuum_mop"); the field
    // holds "Vacuum and mop". Those are never equal, so the chip the user had
    // just clicked did not render active — the row looked like nothing was
    // selected while the matcher was in fact filtering on it.
    //
    // Same display-label-vs-canonical-token split as issue #48, and answered the
    // same way: canonicalise BOTH sides at comparison time rather than changing
    // what is stored. The store side is deliberate — the matcher compares against
    // profile templates that hold display labels — and canonicalising here also
    // absorbs any legacy spelling already sitting in a saved matcher.
    //
    // Reuses the room editor's comparator instead of adding a second one; that
    // function IS the answer to "are these two clean modes the same".
    const canonical = key === "clean_mode"
      ? (value) =>
          this.card?._state?._canonicalCleanModeCompare?.(value) ??
          String(value ?? "").trim().toLowerCase().replace(/[\s+_-]+/g, "")
      : (value) => String(value ?? "");
    const matches = (a, b) => canonical(a) === canonical(b);

    return `
      <div class="evcc-editor-field-group evcc-review-matcher-field">
        <div class="evcc-field-label">${label}</div>
        <div class="evcc-chips">
          ${normalized.map((option) => `
            <button
              type="button"
              class="evcc-chip ${matches(option.value, selected) ? "active" : ""}"
              data-review-matcher-field="${this.escapeHtml(key)}"
              data-value="${this.escapeHtml(String(option.value))}"
            >${this.tVocab(key, option.value, String(option.label))}</button>
          `).join("")}
        </div>
      </div>
    `;
  };

  /* =========================================================
     JOB CARDS
     ========================================================= */

  /**
   * Render the exclude-reason chip selector for a job card.
   *
   * @param {string} jobId - Job ID the reason chips belong to.
   * @param {object} state - Card state.
   * @param {boolean} pending - Whether a job action is pending (disables chips).
   * @returns {string} HTML string.
   */
  proto._renderReviewReasonChips = function (jobId, state, pending) {
    const selectedReason = state.learningHistoryExcludeReason?.(jobId);
    const options = state.learningHistoryExcludeReasonOptions?.() ?? [];

    return `
      <div class="evcc-review-reason-chips">
        <div class="evcc-field-label">${this.t("review.exclude_reason")}</div>
        <div class="evcc-chips evcc-review-filter-chips">
          ${options.map((opt) => `
            <button
              type="button"
              class="evcc-chip ${String(opt?.value ?? "") === String(selectedReason ?? "") ? "active" : ""}"
              data-review-reason-chip="${this.escapeHtml(jobId)}"
              data-value="${this.escapeHtml(String(opt?.value ?? ""))}"
              ${pending ? "disabled" : ""}
            >${this.tVocab("exclude_reason", String(opt?.value ?? ""), String(opt?.label ?? opt?.value ?? ""))}</button>
          `).join("")}
        </div>
        ${String(selectedReason ?? "") === "custom" ? `
          <input
            type="text"
            class="evcc-chip-search evcc-review-custom-reason"
            data-review-custom-reason="${this.escapeHtml(jobId)}"
            value="${this.escapeHtml(String(state.learningHistoryCustomReason?.(jobId) ?? ""))}"
            placeholder="${this.t("review.custom_reason_placeholder")}"
            aria-label="${this.t("review.custom_reason_placeholder")}"
            ${pending ? "disabled" : ""}
          >
        ` : ""}
      </div>
    `;
  };

  /**
   * Render a single learning-review job card with badges, key-value grid, and action buttons.
   *
   * @param {object} job - Job summary object from the learning history snapshot.
   * @param {object} state - Card state.
   * @returns {string} HTML string.
   */
  proto._renderLearningReviewJobCard = function (job, state) {
    const jobId = String(job?.job_id ?? "");
    const pending = state.isLearningHistoryJobActionPending?.(jobId) ?? false;
    const excludeAllowed = job?.exclude_allowed === true;
    const restoreAllowed = job?.restore_allowed === true;
    const excluded = job?.excluded_from_learning === true;
    const badges = [];

    const isExternal = String(job?.origin ?? "").trim().toLowerCase() === "external";
    if (excluded) badges.push({ text: this.t("review.badge_excluded"), cls: "evcc-review-badge--excluded" });
    // External runs get their OWN flag — being externally captured is not a sanity
    // or learning verdict, so it never reads as "Sanity Failed" (backend also forces
    // sanity_passed True for these; the origin guard below is belt-and-suspenders).
    if (isExternal) badges.push({ text: this.t("review.badge_external"), cls: "evcc-review-badge--neutral" });
    if (job?.exclude_suggested === true) badges.push({ text: this.tVocabRaw("exclude_suggested_reason", job?.exclude_suggested_reason, job?.exclude_suggested_reason_label || this.t("review.badge_suggested_exclude")), cls: "evcc-review-badge--suggested" });
    if (String(job?.status ?? "").trim().toLowerCase() !== "completed") badges.push({ text: this.tVocabRaw("status", job?.status, job?.status_label || this._formatReviewLabel(job?.status || this.t("review.unknown"))), cls: "evcc-review-badge--warning" });
    if (job?.sanity_passed === false && !isExternal) badges.push({ text: this.t("review.badge_sanity_failed"), cls: "evcc-review-badge--warning" });
    if (job?.mid_job_recharge_observed === true) badges.push({ text: this.t("review.badge_recharge"), cls: "evcc-review-badge--neutral" });
    // Error evidence captured DURING the run. The backend has carried this end to
    // end for both origins (finalizer and app-started ingest write the same keys)
    // and NOTHING displayed it — a run that hit a fault looked identical here to
    // one that did not, which is the whole point of having captured it.
    //
    // The count rides the badge when known. total_error_seconds is deliberately
    // absent on the app-started path (no per-phase timings to derive it from), so
    // it goes in the TOOLTIP only when finite — printing an unmeasured duration
    // as "0s" would assert the run spent no time in error, a stronger claim than
    // "we did not measure it".
    if (job?.had_errors === true) {
      const errorCount = Number(job?.error_count);
      const errorSeconds = Number(job?.total_error_seconds);
      // RF-DOCK clause 4 / live:RB-ERR-1. error_seconds_by_source has been written
      // by the finalizer all along and nothing ever read it, so the user was told a
      // fault happened and never which hardware raised it. That is the DOCK-1 case
      // exactly: five STATION CLEAN WATER PUMP SHORT faults, correctly NOT deducted,
      // and the run reported as merely "errors" — the station's pump was failing and
      // the card had the evidence to say so.
      //
      // Only sources with seconds are named, so a purely robot-side run never
      // mentions a dock; unattributed is named EXPLICITLY rather than omitted,
      // because saying nothing would imply an attribution we do not have. A brand
      // that classifies nothing (or a code added after the table was written) lands
      // there honestly instead of being silently blamed on the robot.
      const bySource = job?.error_seconds_by_source;
      const sourceParts = [];
      if (bySource && typeof bySource === "object") {
        const dock = Math.round(Number(bySource.dock));
        const robot = Math.round(Number(bySource.robot));
        const unknown = Math.round(Number(bySource.unknown));
        if (Number.isFinite(dock) && dock > 0) sourceParts.push(this.t("review.badge_errors_from_dock", { seconds: dock }));
        if (Number.isFinite(robot) && robot > 0) sourceParts.push(this.t("review.badge_errors_from_robot", { seconds: robot }));
        if (Number.isFinite(unknown) && unknown > 0) sourceParts.push(this.t("review.badge_errors_unattributed", { seconds: unknown }));
      }
      const titleParts = [];
      if (Number.isFinite(errorSeconds) && errorSeconds > 0) {
        titleParts.push(this.t("review.badge_errors_seconds",
          // count drives CLDR form selection; seconds is what the string
          // interpolates. Same number, two roles — without count the
          // selector sees undefined and every language gets "other".
          { seconds: Math.round(errorSeconds), count: Math.round(errorSeconds) }));
      }
      titleParts.push(...sourceParts);
      // anchor: CN147YHC
      badges.push({
        text: Number.isFinite(errorCount) && errorCount > 0
          ? this.t("review.badge_errors_count", { count: errorCount })
          : this.t("review.badge_errors"),
        cls: "evcc-review-badge--warning",
        // Only THIS badge takes the triangle, not every --warning chip. The icon
        // means "this run hit a fault", not "this chip is warning-coloured" — a
        // sanity-failed or non-completed run share the class and are a different
        // claim. An icon on all of them would say a fault occurred when none did.
        icon: "warning",
        title: titleParts.length ? titleParts.join(" · ") : null,
      });
    }
    if (job?.is_single_room === true) badges.push({ text: this.t("review.badge_single_room"), cls: "evcc-review-badge--neutral" });
    if (job?.is_multi_room === true) badges.push({ text: this.t("review.badge_multi_room"), cls: "evcc-review-badge--neutral" });
    // Atomic-dispatched reconcile: the live room signal disagreed with the assigned (positional)
    // room for a segment — flagged for review, never auto-overridden (see reconcile_dispatched_identity).
    if (job?.has_attribution_disagreement === true) badges.push({ text: this.t("review.badge_attribution_disagreement"), cls: "evcc-review-badge--warning", title: this.t("review.badge_attribution_disagreement_title") });

    const detailParts = [
      this._formatReviewTimestamp(job?.started_at),
      Number.isFinite(Number(job?.duration_minutes)) ? this.t("review.detail_minutes", { value: Number(job.duration_minutes).toFixed(1).replace(/\.0$/, "") }) : "",
      Number.isFinite(Number(job?.outlier_score)) ? this.t("review.detail_outlier", { value: Number(job.outlier_score).toFixed(2) }) : "",
      // REV-6: `!= null` FIRST, before the finite check. Number(null) and
      // Number(undefined) are 0 and NaN respectively — the null case is finite,
      // so isFinite alone let an ABSENT battery render as a confident
      // "Battery 0". Externally-captured runs have no battery block at all, so
      // that was every app-started run in the list. Omitting the stat is the
      // honest render; claiming zero consumption is not.
      job?.battery_used != null && Number.isFinite(Number(job.battery_used))
        ? this.t("review.detail_battery", { value: Number(job.battery_used) })
        : "",
      Number.isFinite(Number(job?.total_water_used_ml)) && Number(job.total_water_used_ml) > 0
        ? this.t("review.detail_water", { value: Math.round(Number(job.total_water_used_ml)) })
        : "",
    ].filter(Boolean);

    // Per-job explanatory note, built CODE-FIRST: localize the stable reason CODE
    // via vocab.reason_code.*, falling back PER-CODE to the backend English
    // sentence/label (then a client title-case) so an unkeyed code still reads in
    // English — never a raw key. tVocabRaw (not tVocab) because the note is sunk
    // through escapeHtml at render below. Arrays map EACH code independently and
    // join — never zip codes[] with the index-filtered *_texts[] arrays, which can
    // desync (codes are unfiltered, *_texts drop entries with no _reason_text).
    const reasonChunk = (code, fallback) =>
      code ? this.tVocabRaw("reason_code", String(code), fallback || this._formatReviewLabel(String(code))) : "";
    const reasonFromList = (codes) =>
      (Array.isArray(codes) ? codes : [])
        .map((code) => reasonChunk(code))
        .filter(Boolean)
        .join(", ");

    const reasonText =
      reasonChunk(job?.exclude_suggested_reason, job?.exclude_suggested_reason_text || job?.exclude_suggested_reason_label) ||
      reasonChunk(job?.exclude_reason, job?.exclude_reason_text || job?.exclude_reason_label) ||
      reasonChunk(job?.restore_reason, job?.restore_reason_text || job?.restore_reason_label) ||
      reasonChunk(job?.status, job?.status_text) ||
      reasonFromList(job?.learning_blockers) ||
      reasonFromList(job?.sanity_flags) ||
      reasonChunk(job?.cancel_detection?.reason, job?.cancel_detection?.reason_text);

    // Fold the settings into the profile value (and drop the duplicate subtitle)
    // for profiles with a known namesake — same stable disambiguation as the
    // Metrics cards and the filter chips.
    // Localize the job's profile in the user's card (globe) language by recomposing
    // from the flat setting codes the backend attaches to single-room jobs — same as
    // the filter chips and metrics cards. _localizedProfile falls back to the
    // backend's composed label/subtitle when a job carries no settings (multi-room).
    const lp = this._localizedProfile(job);
    const profileBase = lp.label || job?.profile_key || this.t("review.unknown");
    const profileSettings = String(lp.subtitle ?? "").trim();
    const profileAmbiguous = !!(this.card?._state?._isAmbiguousProfileLabel?.(profileBase) && profileSettings);
    const profileDisplay = profileAmbiguous ? `${profileBase} · ${profileSettings}` : profileBase;
    // anchor: CNP8K5RW  the review job-card badge row
    const profileSubtitle = profileAmbiguous ? null : (profileSettings || null);
    const roomDisplay = Array.isArray(job?.room_slugs) && job.room_slugs.length
        ? job.room_slugs.join(", ")
      : this.t("review.unknown");
    // Zones cleaned in this run (snapshotted names) — shown only when the run had a zone.
    const zoneNames = Array.isArray(job?.zone_names) ? job.zone_names.filter(Boolean) : [];
    const zonesDisplay = zoneNames.length ? zoneNames.join(", ") : "";
    const primaryRoomDisplay = job?.primary_room_label || job?.primary_room_slug || this.t("review.unknown");
    const scopeDisplay = job?.job_scope
      ? this.tVocabRaw("job_scope", job.job_scope, job?.job_scope_label || this._formatReviewLabel(job.job_scope))
      : (job?.job_scope_label || this.t("review.unknown"));

    // The whole card opens the Job Summary. data-job-summary-open also sits on the
    // error badge below, so the badge and the row lead to the SAME surface rather
    // than a separate error dialog. role/tabindex because a div that behaves like a
    // button must be reachable and announced as one.
    return `
      <article class="evcc-review-job-card ${excluded ? "evcc-review-job-card--excluded" : ""} ${job?.exclude_suggested ? "evcc-review-job-card--suggested" : ""}"
               data-job-summary-open="${this.escapeHtml(jobId)}"
               role="button"
               tabindex="0"
               aria-label="${this.t("job_summary.open_aria")}">
        <div class="evcc-review-job-header">
          <div>
            <div class="evcc-review-job-title">${this.escapeHtml(jobId)}</div>
            <div class="evcc-review-job-subtitle">${this.escapeHtml(detailParts.join(" | "))}</div>
          </div>
          <div class="evcc-review-job-badges">
            ${badges.map((badge) => {
              // Object.hasOwn, not a bare lookup: `badge.icon` is ours today, but a
              // plain index would resolve "constructor"/"toString" to prototype junk
              // and splice it into the DOM the day this field takes an outside value.
              const icon = badge.icon && Object.hasOwn(BADGE_ICONS, badge.icon) ? BADGE_ICONS[badge.icon] : "";
              return `
              <span class="evcc-chip ${badge.cls}"${badge.title ? ` title="${this.escapeHtml(badge.title)}"` : ""}>${icon}${this.escapeHtml(badge.text)}</span>
            `;
            }).join("")}
          </div>
        </div>

        <div class="evcc-review-job-grid">
          ${this._renderReviewKeyValue(this.t("review.kv_rooms"), roomDisplay)}
          ${zonesDisplay ? this._renderReviewKeyValue(this.t("review.kv_zones"), zonesDisplay) : ""}
          ${Number.isFinite(Number(job?.cleaning_area_m2)) && Number(job.cleaning_area_m2) > 0
            ? this._renderReviewKeyValue(this.t("review.kv_area"), this.t("review.detail_area_m2", { value: Number(job.cleaning_area_m2).toFixed(1).replace(/\.0$/, "") }))
            : ""}
          ${this._renderReviewKeyValue(this.t("review.kv_scope"), scopeDisplay)}
          ${this._renderReviewKeyValue(this.t("review.kv_profile"), profileDisplay, profileSubtitle)}
          ${this._renderReviewKeyValue(this.t("review.kv_used_for_learning"), job?.used_for_learning === true ? this.t("common.yes") : this.t("common.no"))}
          ${this._renderReviewKeyValue(this.t("review.kv_primary_room"), primaryRoomDisplay)}
        </div>

        ${reasonText ? `
          <div class="evcc-review-job-note">${this.escapeHtml(reasonText)}</div>
        ` : ""}

        <div class="evcc-review-job-actions">
          ${excludeAllowed ? `
            ${this._renderReviewReasonChips(jobId, state, pending)}
            <button
              type="button"
              class="evcc-chip"
              data-review-action="exclude"
              data-job-id="${this.escapeHtml(jobId)}"
              ${pending ? "disabled" : ""}
            >${pending ? this.t("review.working") : this.t("review.exclude")}</button>
          ` : ""}

          ${restoreAllowed ? `
            <button
              type="button"
              class="evcc-chip"
              data-review-action="restore"
              data-job-id="${this.escapeHtml(jobId)}"
              ${pending ? "disabled" : ""}
            >${pending ? this.t("review.working") : this.t("review.restore")}</button>
          ` : ""}
        </div>
      </article>
    `;
  };

  /**
   * Render a key-value pair cell within a job card grid.
   *
   * @param {string} label - Field label.
   * @param {string} value - Field value.
   * @param {string} [subtitle] - Optional subtitle line below the value.
   * @returns {string} HTML string.
   */
  proto._renderReviewKeyValue = function (label, value, subtitle = "") {
    return `
      <div class="evcc-review-kv">
        <div class="evcc-review-kv-label">${label}</div>
        <div class="evcc-review-kv-value">${value}</div>
        ${subtitle ? `<div class="evcc-review-kv-subtitle">${this.escapeHtml(subtitle)}</div>` : ""}
      </div>
    `;
  };

  /* =========================================================
     SORTING / FORMATTERS
     ========================================================= */

  /**
   * Sort and optionally filter the job list according to the active sort mode.
   *
   * @param {object} state - Card state (provides active sort).
   * @param {Array} jobs - Raw job array from the snapshot.
   * @returns {Array} Sorted (and possibly filtered) job array.
   */
  proto._getSortedLearningReviewJobs = function (state, jobs) {
    const safeJobs = Array.isArray(jobs) ? [...jobs] : [];
    const sort = state.learningHistorySort?.() ?? "newest";

    if (sort === "outlier") {
      return safeJobs.sort((a, b) => Number(b?.outlier_score ?? 0) - Number(a?.outlier_score ?? 0));
    }

    if (sort === "suggested") {
      return safeJobs
        .filter((job) => job?.exclude_suggested === true)
        .sort((a, b) => Number(b?.outlier_score ?? 0) - Number(a?.outlier_score ?? 0));
    }

    if (sort === "excluded") {
      return safeJobs
        .filter((job) => job?.excluded_from_learning === true)
        .sort((a, b) => new Date(b?.started_at ?? 0).getTime() - new Date(a?.started_at ?? 0).getTime());
    }

    return safeJobs.sort((a, b) => new Date(b?.started_at ?? 0).getTime() - new Date(a?.started_at ?? 0).getTime());
  };

  /**
   * Format an ISO timestamp for review display (short month, day, hour, minute).
   *
   * @param {string|null} value - ISO timestamp string or null.
   * @returns {string} Formatted timestamp, or empty string.
   */
  proto._formatReviewTimestamp = function (value) {
    return this.formatTimestamp(value, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }, "");
  };

  /**
   * Convert a snake_case or kebab-case string to a title-cased display label.
   *
   * @param {string|null} value - Raw key string.
   * @returns {string} Title-cased label.
   */
  proto._formatReviewLabel = function (value) {
    return String(value ?? "")
      .replace(/[_-]+/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  };
}
