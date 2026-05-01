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
    const snapshot = state.learningHistorySnapshot?.();
    if (!snapshot) {
      return `<div class="evcc-empty">Loading learning history...</div>`;
    }

    if (snapshot.available === false) {
      return `
        <div class="evcc-review-view">
          <div class="evcc-empty">
            ${this.escapeHtml(snapshot.message || snapshot.reason || "Learning history unavailable.")}
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
                <div class="evcc-review-panel-title">Learning Review</div>
                <div class="evcc-review-panel-subtitle">
                  ${this.escapeHtml(snapshot.message || "Review runs used for learning and exclude bad history when needed.")}
                </div>
              </div>
            </div>

            <div class="evcc-review-stats">
              ${this._renderReviewStat("Jobs", summary?.filtered_job_count ?? summary?.job_count ?? 0)}
              ${this._renderReviewStat("Rooms", summary?.filtered_room_count ?? 0)}
              ${this._renderReviewStat("Profiles", summary?.filtered_room_profile_count ?? 0)}
              ${this._renderReviewStat("Updated", this._formatReviewTimestamp(snapshot.updated_at) || "Unknown")}
            </div>
          </section>

          <section class="evcc-review-panel evcc-review-panel--wide">
            <div class="evcc-review-panel-header">
              <div>
                <div class="evcc-review-panel-title">Filters</div>
                <div class="evcc-review-panel-subtitle">Narrow to room, profile, status, or learning use.</div>
              </div>
            </div>

            <div class="evcc-review-filters">
              ${this._renderReviewChipFilter("Room", "room_slug", state.learningHistoryRooms?.().map((room) => ({
                value: room?.room_slug ?? room?.slug ?? "",
                label: room?.room_name ?? room?.label ?? room?.slug ?? "Room",
              })), state.learningHistoryFilters?.().room_slug, "All Rooms")}

              ${this._renderReviewChipFilter("Profile", "profile_key", state.learningHistoryProfiles?.().map((profile) => ({
                value: profile?.profile_key ?? "",
                label: profile?.label ?? profile?.profile_key ?? "Profile",
                title: profile?.subtitle
                  ? `${profile?.label ?? profile?.profile_key ?? "Profile"} | ${profile.subtitle}`
                  : (profile?.label ?? profile?.profile_key ?? "Profile"),
              })), state.learningHistoryFilters?.().profile_key, "All Profiles")}

              ${this._renderReviewChipFilter("Status", "status", state.learningHistoryStatusOptions?.(), state.learningHistoryFilters?.().status, "All Statuses")}

              ${this._renderReviewChipFilter("Learning Use", "used_for_learning", state.learningHistoryUsedOptions?.(), state.learningHistoryFilters?.().used_for_learning, "All Learning Use")}

              ${this._renderReviewChipFilter("Sort", "sort", state.learningHistorySortOptions?.(), state.learningHistorySort?.(), "Newest", "", true)}
            </div>
          </section>

          <section class="evcc-review-panel evcc-review-panel--wide">
            <div class="evcc-review-panel-header">
              <div>
                <div class="evcc-review-panel-title">Profile Matcher</div>
                <div class="evcc-review-panel-subtitle">Try room-editor settings locally to find exact learned profile matches without editing a live room.</div>
              </div>
            </div>

            ${this._renderReviewProfileMatcher(state)}
          </section>

          <section class="evcc-review-panel evcc-review-panel--wide">
            <div class="evcc-review-panel-header">
              <div>
                <div class="evcc-review-panel-title">Runs</div>
                <div class="evcc-review-panel-subtitle">Newest first unless another sort is selected.</div>
              </div>
            </div>

            ${jobs.length ? `
              <div class="evcc-review-job-list">
                ${jobs.map((job) => this._renderLearningReviewJobCard(job, state)).join("")}
              </div>
            ` : `
              <div class="evcc-review-empty">No learning history jobs matched the current filters.</div>
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
        <div class="evcc-review-stat-label">${this.escapeHtml(label)}</div>
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
        <span class="evcc-field-label">${this.escapeHtml(label)}</span>
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

    return `
      <div class="evcc-review-chip-filter">
        <div class="evcc-field-label">${this.escapeHtml(label)}</div>
        <div class="evcc-chips evcc-review-filter-chips">
          ${finalOptions.map((opt) => `
            <button
              type="button"
              class="evcc-chip ${String(opt.value) === String(selected ?? "") ? "active" : ""}"
              data-review-filter-chip="${this.escapeHtml(key)}"
              data-value="${this.escapeHtml(opt.value)}"
              title="${this.escapeHtml(opt.title)}"
            >${this.escapeHtml(opt.label)}</button>
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
          ${this._renderReviewMatcherField("Cleaning Mode", "clean_mode", fields.clean_mode, state.cleanModeOptions?.() ?? [])}
          ${this._renderReviewMatcherField("Suction Level", "fan_speed", fields.fan_speed, state.suctionLevelOptions?.() ?? [])}
          ${state.showReviewProfileMatcherWaterLevel?.()
            ? this._renderReviewMatcherField("Water Level", "water_level", fields.water_level, state.waterLevelOptions?.() ?? [])
            : ""}
          ${this._renderReviewMatcherField("Cleaning Path", "clean_intensity", fields.clean_intensity, state.cleanIntensityOptions?.() ?? [])}
          ${this._renderReviewMatcherField("Cleaning Passes", "clean_passes", fields.clean_passes, [
            { value: 1, label: "1 Pass" },
            { value: 2, label: "2 Passes" },
          ])}
          ${state.showReviewProfileMatcherEdgeMopping?.()
            ? this._renderReviewMatcherField("Edge Mopping", "edge_mopping", fields.edge_mopping, [
              { value: true, label: "On" },
              { value: false, label: "Off" },
            ])
            : ""}
        </div>

        <div class="evcc-review-matcher-actions">
          <button
            type="button"
            class="evcc-chip"
            data-review-matcher-action="reset"
          >Reset Matcher</button>
        </div>

        <div class="evcc-review-matcher-results">
          <div class="evcc-review-matcher-results-header">
            <div class="evcc-review-panel-title">Matched Profiles</div>
            <div class="evcc-review-panel-subtitle">
              ${matches.length
                ? this.escapeHtml(`${matches.length} exact match${matches.length === 1 ? "" : "es"} found.`)
                : "No exact profile matches for the current settings."}
            </div>
          </div>

          ${matches.length ? `
            <div class="evcc-chips evcc-review-matcher-match-chips">
              ${matches.map((match) => `
                <button
                  type="button"
                  class="evcc-chip ${String(profileFilter) === String(match.profile_key) ? "active" : ""}"
                  data-review-matcher-profile="${this.escapeHtml(match.profile_key)}"
                  title="Filter learning jobs to this profile"
                >${this.escapeHtml(match.label ?? match.profile_key)}</button>
              `).join("")}
            </div>
          ` : `
            <div class="evcc-review-empty">Adjust the matcher fields until they line up with a saved profile exactly.</div>
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

    return `
      <div class="evcc-editor-field-group evcc-review-matcher-field">
        <div class="evcc-field-label">${this.escapeHtml(label)}</div>
        <div class="evcc-chips">
          ${normalized.map((option) => `
            <button
              type="button"
              class="evcc-chip ${String(option.value) === String(selected) ? "active" : ""}"
              data-review-matcher-field="${this.escapeHtml(key)}"
              data-value="${this.escapeHtml(String(option.value))}"
            >${this.escapeHtml(String(option.label))}</button>
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
        <div class="evcc-field-label">Exclude Reason</div>
        <div class="evcc-chips evcc-review-filter-chips">
          ${options.map((opt) => `
            <button
              type="button"
              class="evcc-chip ${String(opt?.value ?? "") === String(selectedReason ?? "") ? "active" : ""}"
              data-review-reason-chip="${this.escapeHtml(jobId)}"
              data-value="${this.escapeHtml(String(opt?.value ?? ""))}"
              ${pending ? "disabled" : ""}
            >${this.escapeHtml(String(opt?.label ?? opt?.value ?? ""))}</button>
          `).join("")}
        </div>
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

    if (excluded) badges.push({ text: "Excluded", cls: "evcc-review-badge--excluded" });
    if (job?.exclude_suggested === true) badges.push({ text: job?.exclude_suggested_reason_label || "Suggested Exclude", cls: "evcc-review-badge--suggested" });
    if (String(job?.status ?? "").trim().toLowerCase() !== "completed") badges.push({ text: job?.status_label || this._formatReviewLabel(job?.status || "Unknown"), cls: "evcc-review-badge--warning" });
    if (job?.sanity_passed === false) badges.push({ text: "Sanity Failed", cls: "evcc-review-badge--warning" });
    if (job?.mid_job_recharge_observed === true) badges.push({ text: "Recharge", cls: "evcc-review-badge--neutral" });
    if (job?.is_single_room === true) badges.push({ text: "Single Room", cls: "evcc-review-badge--neutral" });
    if (job?.is_multi_room === true) badges.push({ text: "Multi Room", cls: "evcc-review-badge--neutral" });

    const detailParts = [
      this._formatReviewTimestamp(job?.started_at),
      Number.isFinite(Number(job?.duration_minutes)) ? `${Number(job.duration_minutes).toFixed(1).replace(/\.0$/, "")} min` : "",
      Number.isFinite(Number(job?.outlier_score)) ? `Outlier ${Number(job.outlier_score).toFixed(2)}` : "",
      Number.isFinite(Number(job?.battery_used)) ? `Battery ${Number(job.battery_used)}` : "",
      Number.isFinite(Number(job?.total_water_used_ml)) && Number(job.total_water_used_ml) > 0
        ? `Water ${Math.round(Number(job.total_water_used_ml))} ml`
        : "",
    ].filter(Boolean);

    const reasonText =
      job?.exclude_suggested_reason_text ||
      job?.exclude_reason_text ||
      job?.restore_reason_text ||
      job?.status_text ||
      (Array.isArray(job?.learning_blocker_texts) && job.learning_blocker_texts.length ? job.learning_blocker_texts.join(", ") : "") ||
      (Array.isArray(job?.sanity_flag_texts) && job.sanity_flag_texts.length ? job.sanity_flag_texts.join(", ") : "") ||
      job?.cancel_detection?.reason_text ||
      job?.exclude_suggested_reason_label ||
      job?.exclude_reason_label ||
      job?.restore_reason_label ||
      (Array.isArray(job?.learning_blockers) && job.learning_blockers.length ? job.learning_blockers.join(", ") : "") ||
      (Array.isArray(job?.sanity_flags) && job.sanity_flags.length ? job.sanity_flags.join(", ") : "");

    const profileDisplay = job?.profile_label || job?.selected_profile_label || job?.resolved_profile_label || job?.profile_key || "Unknown";
    const profileSubtitle = job?.profile_subtitle || null;
    const roomDisplay = Array.isArray(job?.room_slugs) && job.room_slugs.length
        ? job.room_slugs.join(", ")
      : "Unknown";
    const primaryRoomDisplay = job?.primary_room_label || job?.primary_room_slug || "Unknown";
    const scopeDisplay =
      job?.job_scope_label ||
      (job?.job_scope ? this._formatReviewLabel(job.job_scope) : "Unknown");

    return `
      <article class="evcc-review-job-card ${excluded ? "evcc-review-job-card--excluded" : ""} ${job?.exclude_suggested ? "evcc-review-job-card--suggested" : ""}">
        <div class="evcc-review-job-header">
          <div>
            <div class="evcc-review-job-title">${this.escapeHtml(jobId)}</div>
            <div class="evcc-review-job-subtitle">${this.escapeHtml(detailParts.join(" | "))}</div>
          </div>
          <div class="evcc-review-job-badges">
            ${badges.map((badge) => `
              <span class="evcc-chip ${badge.cls}">${this.escapeHtml(badge.text)}</span>
            `).join("")}
          </div>
        </div>

        <div class="evcc-review-job-grid">
          ${this._renderReviewKeyValue("Rooms", roomDisplay)}
          ${this._renderReviewKeyValue("Scope", scopeDisplay)}
          ${this._renderReviewKeyValue("Profile", profileDisplay, profileSubtitle)}
          ${this._renderReviewKeyValue("Used For Learning", job?.used_for_learning === true ? "Yes" : "No")}
          ${this._renderReviewKeyValue("Primary Room", primaryRoomDisplay)}
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
            >${pending ? "Working..." : "Exclude"}</button>
          ` : ""}

          ${restoreAllowed ? `
            <button
              type="button"
              class="evcc-chip"
              data-review-action="restore"
              data-job-id="${this.escapeHtml(jobId)}"
              ${pending ? "disabled" : ""}
            >${pending ? "Working..." : "Restore"}</button>
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
        <div class="evcc-review-kv-label">${this.escapeHtml(label)}</div>
        <div class="evcc-review-kv-value">${this.escapeHtml(value)}</div>
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
