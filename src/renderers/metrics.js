/**
 * ============================================================
 * RENDERERS: METRICS
 * ============================================================
 *
 * Renders the Metrics view — tabbed panels for learning quality,
 * room stats, profiles, water usage, and dock events.
 *
 * ============================================================
 */

/**
 * Mix metrics renderer methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applyMetricsRenderers(proto) {

  /* =========================================================
     MAIN VIEW
     ========================================================= */

  /**
   * Render the full Metrics view with overview stats, filters, tabs, and tab content.
   *
   * @param {object} ctx - Render context containing `state`.
   * @returns {string} HTML string.
   */
  proto.renderMetricsView = function (ctx) {
    const { state } = ctx;
    const snapshot = state.metricsSnapshot?.();
    if (!snapshot) {
      return `<div class="evcc-empty">Loading metrics...</div>`;
    }

    if (snapshot.available === false) {
      return `
        <div class="evcc-metrics-view">
          <div class="evcc-empty">
            ${this.escapeHtml(snapshot.message || snapshot.reason || "Metrics unavailable.")}
          </div>
        </div>
      `;
    }

    const overview = state.metricsOverview?.() ?? {};
    const metrics = overview.metrics ?? {};
    const windows = overview.metric_windows ?? {};
    const activeTab = state.metricsActiveTab?.() ?? "learning";

    return `
      <div class="evcc-metrics-view">
        <div class="evcc-metrics-grid">
          <section class="evcc-metrics-panel">
            <div class="evcc-metrics-panel-header">
              <div>
                <div class="evcc-metrics-panel-title">Metrics</div>
                <div class="evcc-metrics-panel-subtitle">
                  ${this.escapeHtml(snapshot.message || "Usage, learning quality, water, and dock metrics across the learning dataset.")}
                </div>
              </div>
            </div>

            <div class="evcc-metrics-stats">
              ${this._renderMetricsStat("Jobs", metrics.job_count ?? 0)}
              ${this._renderMetricsStat("Used", metrics.learning_used_count ?? 0)}
              ${this._renderMetricsStat("Excluded", metrics.excluded_count ?? 0)}
              ${this._renderMetricsStat("Updated", this._formatMetricsTimestamp(snapshot.updated_at) || "Unknown")}
            </div>
          </section>

          <section class="evcc-metrics-panel evcc-metrics-panel--wide">
            <div class="evcc-metrics-panel-header">
              <div>
                <div class="evcc-metrics-panel-title">Filters</div>
                <div class="evcc-metrics-panel-subtitle">Focus the metrics by room, profile, status, or learning use.</div>
              </div>
            </div>

            <div class="evcc-metrics-filters">
              ${this._renderMetricsChipFilter("Room", "room_slug", state.metricsFilterRoomOptions?.(), state.metricsFilters?.().room_slug, "All Rooms")}
              ${this._renderMetricsChipFilter("Profile", "profile_key", state.metricsFilterProfileOptions?.().map((option) => ({
                value: option?.value,
                label: option?.label ?? option?.value ?? "Profile",
                title: option?.subtitle
                  ? `${option?.label ?? option?.value ?? "Profile"} | ${option.subtitle}`
                  : (option?.label ?? option?.value ?? "Profile"),
              })), state.metricsFilters?.().profile_key, "All Profiles")}
              ${this._renderMetricsChipFilter("Status", "status", state.metricsFilterStatusOptions?.(), state.metricsFilters?.().status, "All Statuses")}
              ${this._renderMetricsChipFilter("Learning Use", "used_for_learning", state.metricsFilterUsedOptions?.().map((option) => ({
                value: option?.value_key ?? option?.value,
                label: option?.label ?? option?.value_key ?? option?.value,
              })), state.metricsFilters?.().used_for_learning, "All Learning Use")}
            </div>
          </section>

          <section class="evcc-metrics-panel evcc-metrics-panel--wide">
            <div class="evcc-metrics-tabs" role="tablist" aria-label="Metrics groups">
              ${state.metricsTabOptions?.().map((option) => `
                <button
                  type="button"
                  class="evcc-chip evcc-metrics-tab ${activeTab === option.value ? "active" : ""}"
                  data-metrics-tab="${this.escapeHtml(option.value)}"
                  role="tab"
                  aria-selected="${activeTab === option.value ? "true" : "false"}"
                >${this.escapeHtml(option.label)}</button>
              `).join("")}
            </div>

            <div class="evcc-metrics-tab-panel">
              ${this._renderMetricsTabContent(activeTab, state, metrics, windows)}
            </div>
          </section>
        </div>
      </div>
    `;
  };

  /* =========================================================
     TAB CONTENT
     ========================================================= */

  /**
   * Dispatch to the correct tab renderer based on the active tab key.
   *
   * @param {string} activeTab - Active tab value (e.g. "learning", "rooms").
   * @param {object} state - Card state.
   * @param {object} metrics - Metrics overview metrics object.
   * @param {object} windows - Metric time-window summaries.
   * @returns {string} HTML string.
   */
  proto._renderMetricsTabContent = function (activeTab, state, metrics, windows) {
    switch (activeTab) {
      case "rooms":
        return this._renderMetricsRoomsTab(state);
      case "profiles":
        return this._renderMetricsProfilesTab(state);
      case "water":
        return this._renderMetricsWaterTab(state, metrics);
      case "dock":
        return this._renderMetricsDockTab(metrics, state);
      case "battery":
        return this._renderMetricsBatteryTab(state);
      case "learning":
      default:
        return this._renderMetricsLearningTab(state, metrics, windows);
    }
  };

  /**
   * Render the Learning tab — time-window cards, mini-stat grid, and found-profile cards.
   *
   * @param {object} state - Card state.
   * @param {object} metrics - Overview metrics object.
   * @param {object} windows - Time-window summaries (today, last_7_days, last_30_days).
   * @returns {string} HTML string.
   */
  proto._renderMetricsLearningTab = function (state, metrics, windows) {
    const foundProfiles = state.metricsFoundProfiles?.() ?? [];
    const learningStats = state.metricsLearningStats?.() ?? {};
    const exactCount = Array.isArray(learningStats.exact) ? learningStats.exact.length : 0;
    const baselineCount = Array.isArray(learningStats.baselines) ? learningStats.baselines.length : 0;
    const accuracyCount = Array.isArray(learningStats.accuracy) ? learningStats.accuracy.length : 0;

    return `
      <div class="evcc-metrics-section-stack">
        <div class="evcc-metrics-window-grid">
          ${this._renderMetricsWindowCard("Today", windows.today)}
          ${this._renderMetricsWindowCard("Last 7 Days", windows.last_7_days)}
          ${this._renderMetricsWindowCard("Last 30 Days", windows.last_30_days)}
        </div>

        <div class="evcc-metrics-card-grid">
          ${this._renderMetricsMiniCard("Found Profiles", foundProfiles.length, "Profiles with learning history attached")}
          ${this._renderMetricsMiniCard("Exact Stats", exactCount, "Exact room-learning stat groups")}
          ${this._renderMetricsMiniCard("Baselines", baselineCount, "Room baseline groups")}
          ${this._renderMetricsMiniCard("Accuracy Rows", accuracyCount, "Accuracy stat rows")}
          ${this._renderMetricsMiniCard("Recharge Count", metrics.mid_job_recharge_count ?? 0, "Observed mid-job recharges")}
          ${this._renderMetricsMiniCard("Wash Cycles", metrics.wash_cycle_count ?? 0, "Wash cycles recorded from jobs")}
        </div>

        ${foundProfiles.length ? `
          <div class="evcc-metrics-card-grid">
            ${this._withDisambiguatedTitles(foundProfiles).slice(0, 8).map((profile) => this._renderMetricsFoundProfileCard(profile)).join("")}
          </div>
        ` : `
          <div class="evcc-metrics-empty">No found profiles were returned for the current filters.</div>
        `}
      </div>
    `;
  };

  /**
   * Render the Rooms tab — grid of per-room metric cards.
   *
   * @param {object} state - Card state.
   * @returns {string} HTML string.
   */
  proto._renderMetricsRoomsTab = function (state) {
    const rooms = state.metricsRooms?.() ?? [];
    if (!rooms.length) {
      return `<div class="evcc-metrics-empty">No room metrics matched the current filters.</div>`;
    }

    return `
      <div class="evcc-metrics-card-grid">
        ${rooms.map((room) => this._renderMetricsRoomCard(room)).join("")}
      </div>
    `;
  };

  /**
   * Render the Profiles tab — room-profile cards and found-profile cards.
   *
   * @param {object} state - Card state.
   * @returns {string} HTML string.
   */
  proto._renderMetricsProfilesTab = function (state) {
    const profiles = state.metricsRoomProfiles?.() ?? [];
    const foundProfiles = state.metricsFoundProfiles?.() ?? [];

    return `
      <div class="evcc-metrics-section-stack">
        ${profiles.length ? `
          <div class="evcc-metrics-card-grid">
            ${this._withDisambiguatedTitles(profiles).map((profile) => this._renderMetricsRoomProfileCard(profile)).join("")}
          </div>
        ` : `
          <div class="evcc-metrics-empty">No room-profile metrics matched the current filters.</div>
        `}

        ${foundProfiles.length ? `
          <div class="evcc-metrics-panel-header">
            <div>
              <div class="evcc-metrics-panel-title">Found Profiles</div>
              <div class="evcc-metrics-panel-subtitle">Detected profile families and trust state.</div>
            </div>
          </div>
          <div class="evcc-metrics-card-grid">
            ${this._withDisambiguatedTitles(foundProfiles).slice(0, 12).map((profile) => this._renderMetricsFoundProfileCard(profile)).join("")}
          </div>
        ` : ""}
      </div>
    `;
  };

  /**
   * Render the Water tab — summary totals and top water-usage rooms and profiles.
   *
   * @param {object} state - Card state.
   * @param {object} metrics - Overview metrics object.
   * @returns {string} HTML string.
   */
  proto._renderMetricsWaterTab = function (state, metrics) {
    const rooms = [...(state.metricsRooms?.() ?? [])]
      .sort((a, b) => Number(b?.avg_total_water_used_ml ?? 0) - Number(a?.avg_total_water_used_ml ?? 0))
      .slice(0, 8);
    const profiles = [...(state.metricsRoomProfiles?.() ?? [])]
      .sort((a, b) => Number(b?.avg_total_water_used_ml ?? 0) - Number(a?.avg_total_water_used_ml ?? 0))
      .slice(0, 8);

    return `
      <div class="evcc-metrics-section-stack">
        <div class="evcc-metrics-card-grid">
          ${this._renderMetricsMiniCard("Robot Water", this._formatMetricsMilliliters(metrics.total_robot_water_used_ml), "Robot-applied cleaning water")}
          ${this._renderMetricsMiniCard("Water Overhead", this._formatMetricsMilliliters(metrics.total_water_overhead_ml), "Dock or wash overhead water")}
          ${this._renderMetricsMiniCard("Total Water", this._formatMetricsMilliliters(metrics.total_water_used_ml), "Total water used across matching jobs")}
        </div>

        ${rooms.length ? `
          <div class="evcc-metrics-panel-header">
            <div>
              <div class="evcc-metrics-panel-title">Highest Water Rooms</div>
              <div class="evcc-metrics-panel-subtitle">Average total water use per room.</div>
            </div>
          </div>
          <div class="evcc-metrics-card-grid">
            ${rooms.map((room) => this._renderMetricsWaterRoomCard(room)).join("")}
          </div>
        ` : ""}

        ${profiles.length ? `
          <div class="evcc-metrics-panel-header">
            <div>
              <div class="evcc-metrics-panel-title">Highest Water Profiles</div>
              <div class="evcc-metrics-panel-subtitle">Average total water use per profile.</div>
            </div>
          </div>
          <div class="evcc-metrics-card-grid">
            ${profiles.map((profile) => this._renderMetricsWaterProfileCard(profile)).join("")}
          </div>
        ` : ""}
      </div>
    `;
  };

  /**
   * Render the Dock tab — dock event counts, water overhead, and source timestamps.
   *
   * @param {object} metrics - Overview metrics object.
   * @param {object} state - Card state.
   * @returns {string} HTML string.
   */
  proto._renderMetricsDockTab = function (metrics, state) {
    const dock = metrics?.dock ?? {};
    const sources = state.metricsSources?.() ?? {};

    return `
      <div class="evcc-metrics-section-stack">
        <div class="evcc-metrics-card-grid">
          ${this._renderMetricsMiniCard("Mop Wash", dock.mop_wash_count ?? 0, "Dock mop wash count")}
          ${this._renderMetricsMiniCard("Dust Empty", dock.dust_empty_count ?? 0, "Dock dust-empty count")}
          ${this._renderMetricsMiniCard("Dry Starts", dock.dry_start_count ?? 0, "Dock dry-start count")}
          ${this._renderMetricsMiniCard("Wash Cycles", dock.wash_cycle_count_from_jobs ?? 0, "Wash cycles inferred from jobs")}
          ${this._renderMetricsMiniCard("Water Overhead", this._formatMetricsMilliliters(dock.total_water_overhead_ml), "Total dock water overhead")}
          ${this._renderMetricsMiniCard("Avg Overhead / Job", this._formatMetricsMilliliters(dock.avg_water_overhead_ml_per_job), "Average water overhead per job")}
        </div>

        <div class="evcc-metrics-card-grid">
          ${this._renderMetricsMiniCard("Last Mop Wash", this._formatMetricsTimestamp(dock.last_mop_wash) || "Unknown", "Latest dock mop wash")}
          ${this._renderMetricsMiniCard("Last Dust Empty", this._formatMetricsTimestamp(dock.last_dust_empty) || "Unknown", "Latest dock dust empty")}
          ${this._renderMetricsMiniCard("Last Dry Start", this._formatMetricsTimestamp(dock.last_dry_start) || "Unknown", "Latest dock dry start")}
          ${this._renderMetricsMiniCard("Last Dry Duration", this._formatMetricsDurationValue(dock.last_dry_duration), "Latest dock dry duration")}
          ${this._renderMetricsMiniCard("Room Stats Rebuilt", this._formatMetricsTimestamp(sources.room_stats_rebuilt_at) || "Unknown", "Latest room stat rebuild")}
          ${this._renderMetricsMiniCard("Accuracy Updated", this._formatMetricsTimestamp(sources.accuracy_stats_updated_at) || "Unknown", "Latest accuracy update")}
        </div>
      </div>
    `;
  };

  /* =========================================================
     FILTER CONTROLS
     ========================================================= */

  /**
   * Render a `<select>` filter for a single metrics dimension.
   *
   * @param {string} label - Visible field label.
   * @param {string} key - data-metrics-filter key.
   * @param {Array<{value:string,label:string}>} options - Filter options.
   * @param {string} selected - Currently selected value.
   * @param {string} fallbackLabel - Label for the "all" / empty option.
   * @returns {string} HTML string.
   */
  proto._renderMetricsSelect = function (label, key, options, selected, fallbackLabel) {
    const safeOptions = Array.isArray(options) ? options : [];
    const finalOptions = [{ value: "", label: fallbackLabel }, ...safeOptions.filter((opt) => String(opt?.value ?? "") !== "")];

    return `
      <label class="evcc-field evcc-metrics-filter">
        <span class="evcc-field-label">${this.escapeHtml(label)}</span>
        <select data-metrics-filter="${this.escapeHtml(key)}">
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
   * Render a chip-button filter row for a single metrics dimension.
   *
   * @param {string} label - Visible field label.
   * @param {string} key - data-metrics-filter-chip key.
   * @param {Array<{value:string,label:string,title?:string}>} options - Filter options.
   * @param {string} selected - Currently selected value.
   * @param {string} fallbackLabel - Label for the "all" / empty chip.
   * @returns {string} HTML string.
   */
  proto._renderMetricsChipFilter = function (label, key, options, selected, fallbackLabel) {
    const safeOptions = Array.isArray(options) ? options : [];
    const normalized = safeOptions
      .filter((opt) => opt && typeof opt === "object")
      .map((opt) => ({
        value: String(opt?.value ?? ""),
        label: String(opt?.label ?? opt?.value ?? ""),
        title: String(opt?.title ?? opt?.label ?? opt?.value ?? ""),
      }));

    const finalOptions = [{ value: "", label: fallbackLabel }, ...normalized.filter((opt) => opt.value !== "")];

    const searchable = key === "profile_key";
    const head = searchable
      ? `<div class="evcc-chip-filter-head">
           <div class="evcc-field-label">${this.escapeHtml(label)}</div>
           <input type="text" class="evcc-chip-search" data-chip-search placeholder="Search…" aria-label="Search ${this.escapeHtml(label)}">
         </div>`
      : `<div class="evcc-field-label">${this.escapeHtml(label)}</div>`;
    return `
      <div class="evcc-metrics-chip-filter${searchable ? " evcc-chip-filter--searchable" : ""}" data-chip-filter-group>
        ${head}
        <div class="evcc-chips evcc-metrics-filter-chips">
          ${finalOptions.map((opt, i) => `
            <button
              type="button"
              class="evcc-chip ${String(opt.value) === String(selected ?? "") ? "active" : ""}"
              data-metrics-filter-chip="${this.escapeHtml(key)}"
              data-value="${this.escapeHtml(opt.value)}"
              ${i === 0 ? `data-all-chip="true"` : ""}
              title="${this.escapeHtml(opt.title)}"
            >${this.escapeHtml(opt.label)}</button>
          `).join("")}
        </div>
      </div>
    `;
  };

  /* =========================================================
     CARD PRIMITIVES
     ========================================================= */

  /**
   * Render a single stat cell (value + label).
   *
   * @param {string} label - Stat label.
   * @param {string|number} value - Stat value.
   * @returns {string} HTML string.
   */
  proto._renderMetricsStat = function (label, value) {
    return `
      <div class="evcc-metrics-stat">
        <div class="evcc-metrics-stat-value">${this.escapeHtml(value)}</div>
        <div class="evcc-metrics-stat-label">${this.escapeHtml(label)}</div>
      </div>
    `;
  };

  /**
   * Render a time-window summary card (duration, job count, water, recharge).
   *
   * @param {string} title - Window label (e.g. "Today").
   * @param {object} window - Window summary object from the metrics snapshot.
   * @returns {string} HTML string.
   */
  proto._renderMetricsWindowCard = function (title, window) {
    const item = window ?? {};
    return `
      <div class="evcc-metrics-card">
        <div class="evcc-metrics-card-title">${this.escapeHtml(title)}</div>
        <div class="evcc-metrics-card-value">${this.escapeHtml(this._formatMetricsDuration(item.total_duration_minutes))}</div>
        <div class="evcc-metrics-card-detail">${this.escapeHtml(`${Number(item.job_count ?? 0)} jobs | ${Number(item.learning_used_count ?? 0)} used`)}</div>
        <div class="evcc-metrics-card-secondary">${this.escapeHtml(`Water ${this._formatMetricsMilliliters(item.total_water_used_ml)} | Recharge ${Number(item.mid_job_recharge_count ?? 0)}`)}</div>
      </div>
    `;
  };

  /**
   * Render a compact stat card with title, primary value, and optional detail line.
   *
   * @param {string} title - Card heading.
   * @param {string|number} value - Primary display value.
   * @param {string} [detail] - Optional secondary detail line.
   * @returns {string} HTML string.
   */
  proto._renderMetricsMiniCard = function (title, value, detail = "") {
    return `
      <div class="evcc-metrics-card">
        <div class="evcc-metrics-card-title">${this.escapeHtml(title)}</div>
        <div class="evcc-metrics-card-value">${this.escapeHtml(value)}</div>
        ${detail ? `<div class="evcc-metrics-card-detail">${this.escapeHtml(detail)}</div>` : ""}
      </div>
    `;
  };

  /**
   * Render a per-room metrics card showing average duration, run count, and trust level.
   *
   * @param {object} room - Room metrics object.
   * @returns {string} HTML string.
   */
  proto._renderMetricsRoomCard = function (room) {
    const title = room?.room_label || room?.room_slug || "Room";
    return `
      <div class="evcc-metrics-card">
        <div class="evcc-metrics-card-title">${this.escapeHtml(title)}</div>
        <div class="evcc-metrics-card-value">${this.escapeHtml(this._formatMetricsDuration(room?.avg_duration_minutes))}</div>
        <div class="evcc-metrics-card-detail">${this.escapeHtml(`${Number(room?.run_count ?? 0)} runs | ${Number(room?.learning_run_count ?? 0)} used`)}</div>
        <div class="evcc-metrics-card-secondary">${this.escapeHtml(`Trust ${this._formatMetricsTrustLevel(room?.trust_level)} | ${Number(room?.runs_to_trusted ?? 0)} runs to trusted`)}</div>
      </div>
    `;
  };

  /**
   * Render a per-room-profile metrics card with optional save-candidate badge and save button.
   *
   * @param {object} profile - Room-profile metrics object.
   * @returns {string} HTML string.
   */
  // Disambiguate result-card titles the same way — and STABLY — as the filter
  // chips: fold the settings into the title for any profile whose label has a
  // known namesake, and drop the now-duplicate subtitle. Reuses the card-state
  // accumulator so a filtered-down card keeps its full title instead of
  // collapsing. Unique cards are untouched.
  proto._withDisambiguatedTitles = function (profiles) {
    if (!Array.isArray(profiles) || !profiles.length) return Array.isArray(profiles) ? profiles : [];
    const st = this.card?._state;
    const titleOf = (p) =>
      String(p?.profile_label || p?.selected_profile_label || p?.resolved_profile_label || p?.profile_key || "Profile");
    st?._noteAmbiguousProfiles?.(profiles.map(titleOf));
    return profiles.map((p) => {
      const t = titleOf(p);
      const settings = String(p?.profile_subtitle ?? "").trim();
      return st?._isAmbiguousProfileLabel?.(t) && settings
        ? { ...p, display_title: `${t} · ${settings}`, _settings_in_title: true }
        : p;
    });
  };

  proto._renderMetricsRoomProfileCard = function (profile) {
    const title = profile?.display_title || profile?.profile_label || profile?.selected_profile_label || profile?.resolved_profile_label || profile?.profile_key || "Profile";
    const subtitle = profile?._settings_in_title ? "" : (profile?.profile_subtitle || profile?.room_label || profile?.room_slug || "");
    const saveKey = this.card?._state?.metricsProfileSaveKey?.("profile", profile) ?? "";
    const pending = this.card?._state?.isMetricsProfileSavePending?.(saveKey) ?? false;
    const canSave = profile?.save_candidate === true && profile?.save_supported === true && String(profile?.save_service ?? "").trim() !== "";
    return `
      <div class="evcc-metrics-card">
        <div class="evcc-metrics-card-header">
          <div class="evcc-metrics-card-title">${this.escapeHtml(title)}</div>
          ${profile?.save_candidate === true ? `
            <span class="evcc-chip evcc-metrics-card-badge" title="${this.escapeHtml(profile?.save_suggested_label || "Suggested save candidate")}">
              ${this.escapeHtml(profile?.save_suggested_label || "Save Candidate")}
            </span>
          ` : ""}
        </div>
        ${subtitle ? `<div class="evcc-metrics-card-subtitle">${this.escapeHtml(subtitle)}</div>` : ""}
        <div class="evcc-metrics-card-value">${this.escapeHtml(this._formatMetricsDuration(profile?.avg_duration_minutes))}</div>
        <div class="evcc-metrics-card-detail">${this.escapeHtml(`${Number(profile?.run_count ?? 0)} runs | ${Number(profile?.learning_run_count ?? 0)} used`)}</div>
        <div class="evcc-metrics-card-secondary">${this.escapeHtml(`Water ${this._formatMetricsMilliliters(profile?.avg_total_water_used_ml)} | Trust ${this._formatMetricsTrustLevel(profile?.trust_level)}`)}</div>
        ${canSave ? `
          <div class="evcc-metrics-card-actions">
            <button
              type="button"
              class="evcc-chip"
              data-metrics-save-profile="profile"
              data-profile-key="${this.escapeHtml(String(profile?.profile_key ?? ""))}"
              data-room-slug="${this.escapeHtml(String(profile?.room_slug ?? ""))}"
              ${pending ? "disabled" : ""}
              title="${this.escapeHtml(profile?.save_suggested_label || "Save this learned profile")}"
            >${pending ? "Saving..." : "Save Profile"}</button>
          </div>
        ` : ""}
      </div>
    `;
  };

  /**
   * Render a found-profile metrics card showing trust level, run counts, and optional save button.
   *
   * @param {object} profile - Found-profile metrics object.
   * @returns {string} HTML string.
   */
  proto._renderMetricsFoundProfileCard = function (profile) {
    const title = profile?.display_title || profile?.profile_label || profile?.selected_profile_label || profile?.resolved_profile_label || profile?.profile_key || "Profile";
    const subtitle = profile?._settings_in_title ? "" : (profile?.profile_subtitle || profile?.room_label || profile?.room_slug || "");
    const trustReason = profile?.trust_reason_text || profile?.trust_reason || "";
    const saveKey = this.card?._state?.metricsProfileSaveKey?.("found", profile) ?? "";
    const pending = this.card?._state?.isMetricsProfileSavePending?.(saveKey) ?? false;
    const canSave = profile?.save_candidate === true && String(profile?.save_service ?? "").trim() !== "";
    return `
      <div class="evcc-metrics-card">
        <div class="evcc-metrics-card-header">
          <div class="evcc-metrics-card-title">${this.escapeHtml(title)}</div>
          ${profile?.save_candidate === true ? `
            <span class="evcc-chip evcc-metrics-card-badge" title="${this.escapeHtml(profile?.save_suggested_label || "Suggested save candidate")}">
              ${this.escapeHtml(profile?.save_suggested_label || "Save Candidate")}
            </span>
          ` : ""}
        </div>
        ${subtitle ? `<div class="evcc-metrics-card-subtitle">${this.escapeHtml(subtitle)}</div>` : ""}
        <div class="evcc-metrics-card-value">${this.escapeHtml(this._formatMetricsTrustLevel(profile?.trust_level))}</div>
        <div class="evcc-metrics-card-detail">${this.escapeHtml(`${Number(profile?.run_count ?? 0)} runs | ${Number(profile?.learning_run_count ?? 0)} used`)}</div>
        ${trustReason ? `<div class="evcc-metrics-card-secondary">${this.escapeHtml(trustReason)}</div>` : ""}
        ${canSave ? `
          <div class="evcc-metrics-card-actions">
            <button
              type="button"
              class="evcc-chip"
              data-metrics-save-profile="found"
              data-profile-key="${this.escapeHtml(String(profile?.profile_key ?? ""))}"
              data-room-slug="${this.escapeHtml(String(profile?.room_slug ?? ""))}"
              ${pending ? "disabled" : ""}
              title="${this.escapeHtml(profile?.save_suggested_label || "Save this learned profile")}"
            >${pending ? "Saving..." : "Save Profile"}</button>
          </div>
        ` : ""}
      </div>
    `;
  };

  /**
   * Render a water-usage room card showing average total, robot, and overhead water.
   *
   * @param {object} room - Room metrics object.
   * @returns {string} HTML string.
   */
  proto._renderMetricsWaterRoomCard = function (room) {
    return `
      <div class="evcc-metrics-card">
        <div class="evcc-metrics-card-title">${this.escapeHtml(room?.room_label || room?.room_slug || "Room")}</div>
        <div class="evcc-metrics-card-value">${this.escapeHtml(this._formatMetricsMilliliters(room?.avg_total_water_used_ml))}</div>
        <div class="evcc-metrics-card-detail">${this.escapeHtml(`Robot ${this._formatMetricsMilliliters(room?.avg_robot_water_used_ml)} | Overhead ${this._formatMetricsMilliliters(room?.avg_water_overhead_ml)}`)}</div>
      </div>
    `;
  };

  /**
   * Render a water-usage profile card showing average total, robot, and overhead water.
   *
   * @param {object} profile - Profile metrics object.
   * @returns {string} HTML string.
   */
  proto._renderMetricsWaterProfileCard = function (profile) {
    return `
      <div class="evcc-metrics-card">
        <div class="evcc-metrics-card-title">${this.escapeHtml(profile?.profile_label || profile?.profile_key || "Profile")}</div>
        <div class="evcc-metrics-card-value">${this.escapeHtml(this._formatMetricsMilliliters(profile?.avg_total_water_used_ml))}</div>
        <div class="evcc-metrics-card-detail">${this.escapeHtml(`Robot ${this._formatMetricsMilliliters(profile?.avg_robot_water_used_ml)} | Overhead ${this._formatMetricsMilliliters(profile?.avg_water_overhead_ml)}`)}</div>
      </div>
    `;
  };

  /* =========================================================
     FORMATTERS
     ========================================================= */

  /**
   * Format a numeric minute value as a human-readable duration string.
   *
   * @param {*} value - Raw minute count.
   * @returns {string} Formatted duration.
   */
  proto._formatMetricsDuration = function (value) {
    const minutes = Number(value);
    if (!Number.isFinite(minutes)) return "0 min";
    return this._formatLearningDuration(minutes);
  };

  /**
   * Format a numeric milliliter value as a rounded "N ml" string.
   *
   * @param {*} value - Raw milliliter amount.
   * @returns {string} Formatted milliliter string.
   */
  proto._formatMetricsMilliliters = function (value) {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return "0 ml";
    return `${Math.round(amount)} ml`;
  };

  /**
   * Format an ISO timestamp for metrics display (short month, day, hour, minute).
   *
   * @param {string|null} value - ISO timestamp string or null.
   * @returns {string} Formatted timestamp, or empty string.
   */
  proto._formatMetricsTimestamp = function (value) {
    return this.formatTimestamp(value, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }, "");
  };

  /**
   * Format a snake_case trust-level key as a title-cased display string.
   *
   * @param {string|null} value - Raw trust level key.
   * @returns {string} Title-cased label, or "Unknown".
   */
  proto._formatMetricsTrustLevel = function (value) {
    return String(value ?? "")
      .replace(/[_-]+/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase()) || "Unknown";
  };

  /**
   * Format a raw duration value: numeric → "N min", non-numeric → string passthrough.
   *
   * @param {*} value - Raw duration value.
   * @returns {string} Formatted duration.
   */
  proto._formatMetricsDurationValue = function (value) {
    const numeric = Number(value);
    if (Number.isFinite(numeric)) {
      return `${numeric.toFixed(1).replace(/\.0$/, "")} min`;
    }
    return String(value ?? "Unknown");
  };

  /* =========================================================
     BATTERY TAB
     =========================================================
     Surface the 10 battery sensors registered by the integration's
     BatteryHealthManager:
     - Top row: 4 headline chips (cycles, health, current charge rate,
       last-job drain/m²).
     - Charge rates table: per-zone instantaneous + mid-job mean.
     - Last-job table: drain rates plus the per-clean-mode / per-fan-speed /
       per-water-level aggregates pulled from the sensor's attributes.
     - Footer: paths to the raw CSV/JSONL the integration writes.

     No charts here — HA's history-graph / apexcharts cards do that better
     against the live sensors. The integration's sessions.csv and
     samples.jsonl give the long-term raw view.
  ========================================================= */

  proto._renderMetricsBatteryTab = function (state) {
    const m = state.batteryMetrics?.() ?? {};

    const numFmt = (raw, digits = 2) => {
      const n = Number(raw);
      return Number.isFinite(n) ? n.toFixed(digits).replace(/\.?0+$/, "") : "—";
    };

    // HA reports "unknown" / "unavailable" as literal strings for sensors
    // that haven't published yet — treat those as missing too.
    const isMissing = (raw) => {
      if (raw == null) return true;
      const s = String(raw).trim().toLowerCase();
      return s === "" || s === "unknown" || s === "unavailable" || s === "none";
    };

    const sensorVal = (entry, digits = 2, suffix = "") => {
      if (!entry || isMissing(entry.state)) return "—";
      const n = Number(entry.state);
      if (!Number.isFinite(n)) return String(entry.state);
      return `${numFmt(n, digits)}${suffix}`;
    };

    // Top chips — pull the four most-glanceable values.
    const chips = `
      <div class="evcc-metrics-card-grid">
        ${this._renderMetricsMiniCard(
          "Charge cycles",
          sensorVal(m.cycles, 1),
          "Cumulative drain ÷ 100"
        )}
        ${this._renderMetricsMiniCard(
          "Health %",
          sensorVal(m.health, 0, "%"),
          m.health?.attrs?.baseline_session_count
            ? `vs first ${m.health.attrs.baseline_session_count} full charges`
            : "Building baseline"
        )}
        ${this._renderMetricsMiniCard(
          "Charge rate",
          sensorVal(m.rate_overall, 2, " %/min"),
          m.rate_overall?.attrs?.charging ? "Charging now" : "Last sample"
        )}
        ${this._renderMetricsMiniCard(
          "Last job %/m²",
          sensorVal(m.last_job_per_m2, 3),
          m.last_job_per_m2?.attrs?.area_m2
            ? `${numFmt(m.last_job_per_m2.attrs.area_m2, 1)} m² | ${numFmt(m.last_job_per_m2.attrs.battery_used_pct, 0)} % used`
            : "Awaiting first job"
        )}
      </div>
    `;

    // Charge rates table — one row per tracked zone.
    const ratesTable = `
      <div class="evcc-metrics-section-title">Charge rates by zone</div>
      <table class="evcc-metrics-table">
        <thead>
          <tr>
            <th>Zone</th>
            <th>Last rate</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Overall</td>
            <td>${this.escapeHtml(sensorVal(m.rate_overall, 2, " %/min"))}</td>
            <td>Any active charge interval</td>
          </tr>
          <tr>
            <td>Low (≤ 29 %)</td>
            <td>${this.escapeHtml(sensorVal(m.rate_low, 2, " %/min"))}</td>
            <td>Slow precharge / soft-cell signal</td>
          </tr>
          <tr>
            <td>High (≥ 80 %)</td>
            <td>${this.escapeHtml(sensorVal(m.rate_high, 2, " %/min"))}</td>
            <td>CV taper — earliest health drop indicator</td>
          </tr>
          <tr>
            <td>Mid-job (15→75)</td>
            <td>${this.escapeHtml(sensorVal(m.rate_mid_job, 2, " %/min"))}</td>
            <td>${this.escapeHtml(
              `Rolling mean | ${m.rate_mid_job?.attrs?.sample_count ?? 0} samples`
            )}</td>
          </tr>
          <tr>
            <td>Last full session</td>
            <td>${this.escapeHtml(sensorVal(m.last_charge_duration, 0, " min"))}</td>
            <td>${this.escapeHtml(
              m.last_charge_duration?.attrs?.last_charge_delta_pct != null
                ? `Charged ${m.last_charge_duration.attrs.last_charge_delta_pct} %`
                : ""
            )}</td>
          </tr>
        </tbody>
      </table>
    `;

    // Per-mode aggregate table — pulls from any of the last-job sensors;
    // they all expose the same attribute shape, so use last_job_per_m2.
    const buckets = m.last_job_per_m2?.attrs?.by_clean_mode_mean ?? {};
    const fanBuckets = m.last_job_per_m2?.attrs?.by_fan_speed_mean ?? {};
    const waterBuckets = m.last_job_per_m2?.attrs?.by_water_level_mean ?? {};

    const renderBucketRows = (obj, label) => {
      const keys = Object.keys(obj || {});
      if (!keys.length) {
        return `<tr><td colspan="3"><em>${this.escapeHtml(label)} — no single-bucket jobs yet</em></td></tr>`;
      }
      return keys.map((k) => `
        <tr>
          <td>${this.escapeHtml(k)}</td>
          <td>${this.escapeHtml(numFmt(obj[k]?.mean, 3))}</td>
          <td>${this.escapeHtml(String(obj[k]?.count ?? 0))}</td>
        </tr>
      `).join("");
    };

    const allCount = m.last_job_per_m2?.attrs?.all_jobs_count ?? 0;
    const allMean = m.last_job_per_m2?.attrs?.all_jobs_mean;

    const aggregateTable = `
      <div class="evcc-metrics-section-title">Drain per m² by single-bucket job</div>
      <div class="evcc-metrics-section-subtitle">
        Only jobs where every room used the same setting feed these means.
        Mixed-mode runs still update the all-jobs row but skip per-bucket buckets.
      </div>
      <table class="evcc-metrics-table">
        <thead>
          <tr>
            <th>Bucket</th>
            <th>Mean %/m²</th>
            <th>Jobs</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>All jobs (mixed + single)</strong></td>
            <td>${this.escapeHtml(numFmt(allMean, 3))}</td>
            <td>${this.escapeHtml(String(allCount))}</td>
          </tr>
          <tr><td colspan="3"><em>By clean mode</em></td></tr>
          ${renderBucketRows(buckets, "Clean mode")}
          <tr><td colspan="3"><em>By fan speed</em></td></tr>
          ${renderBucketRows(fanBuckets, "Fan speed")}
          <tr><td colspan="3"><em>By water level</em></td></tr>
          ${renderBucketRows(waterBuckets, "Water level")}
        </tbody>
      </table>
    `;

    // Last job summary — also expose post-job recharge linkage when present.
    const lastJob = m.last_job_per_m2?.attrs ?? {};
    const postJob = lastJob.post_job_charge ?? null;
    const lastJobBlock = lastJob.recorded_at ? `
      <div class="evcc-metrics-section-title">Most recent completed job</div>
      <table class="evcc-metrics-table">
        <tbody>
          <tr><td>Job ID</td><td>${this.escapeHtml(String(lastJob.job_id ?? "—"))}</td></tr>
          <tr><td>Recorded</td><td>${this.escapeHtml(this._formatMetricsTimestamp(lastJob.recorded_at) || "—")}</td></tr>
          <tr><td>Duration</td><td>${this.escapeHtml(numFmt(lastJob.duration_min, 1) + " min")}</td></tr>
          <tr><td>Area</td><td>${this.escapeHtml(numFmt(lastJob.area_m2, 1) + " m²")}</td></tr>
          <tr><td>Battery used</td><td>${this.escapeHtml(numFmt(lastJob.battery_used_pct, 0) + " %")}</td></tr>
          <tr><td>Drain rate</td><td>${this.escapeHtml(sensorVal(m.last_job_per_min, 2, " %/min"))}</td></tr>
          <tr><td>Drain per hour</td><td>${this.escapeHtml(sensorVal(m.last_job_per_hour, 1, " %/h"))}</td></tr>
          <tr><td>Drain per m²</td><td>${this.escapeHtml(sensorVal(m.last_job_per_m2, 3, " %/m²"))}</td></tr>
          <tr><td>Single clean mode</td><td>${this.escapeHtml(lastJob.single_clean_mode ?? "(mixed)")}</td></tr>
          <tr><td>Single fan speed</td><td>${this.escapeHtml(lastJob.single_fan_speed ?? "(mixed)")}</td></tr>
          <tr><td>Single water level</td><td>${this.escapeHtml(lastJob.single_water_level ?? "(mixed)")}</td></tr>
          <tr><td>Weighted by</td><td>${this.escapeHtml(lastJob.weighted_by ?? "—")}</td></tr>
          ${postJob ? `
            <tr><td colspan="2"><em>Post-job recharge</em></td></tr>
            <tr><td>Recharge duration</td><td>${this.escapeHtml(numFmt(postJob.duration_min, 1) + " min")}</td></tr>
            <tr><td>Recharge delta</td><td>${this.escapeHtml(`${postJob.start_battery ?? "?"} → ${postJob.end_battery ?? "?"} %`)}</td></tr>
            <tr><td>Avg rate</td><td>${this.escapeHtml(numFmt(postJob.avg_rate_per_min, 2) + " %/min")}</td></tr>
            <tr><td>Ended</td><td>${this.escapeHtml(postJob.ended_reason ?? "—")}</td></tr>
          ` : `
            <tr><td>Post-job recharge</td><td><em>Awaiting next charge session</em></td></tr>
          `}
        </tbody>
      </table>
    ` : `
      <div class="evcc-metrics-section-title">Most recent completed job</div>
      <div class="evcc-empty">No completed job yet — sensors populate after the first finalized run.</div>
    `;

    const objectId = state.vacuumObjectId?.() ?? "";
    const rawDataNote = `
      <div class="evcc-metrics-section-title">Raw data files</div>
      <div class="evcc-metrics-section-subtitle">
        Long-term review is best done from the raw files written by the integration.
        Chart any of the sensors above with HA's history-graph or apexcharts-card; for
        deeper analysis open the CSV in a spreadsheet.
      </div>
      <pre class="evcc-metrics-codeblock">config/eufy_vacuum/battery/${this.escapeHtml(objectId)}/sessions.csv
config/eufy_vacuum/battery/${this.escapeHtml(objectId)}/samples.jsonl</pre>
    `;

    return `
      <div class="evcc-metrics-section-stack">
        ${chips}
        ${ratesTable}
        ${aggregateTable}
        ${lastJobBlock}
        ${rawDataNote}
      </div>
    `;
  };
}
