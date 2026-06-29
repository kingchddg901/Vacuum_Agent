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
      return `<div class="evcc-empty">${this.t("metrics.loading")}</div>`;
    }

    if (snapshot.available === false) {
      return `
        <div class="evcc-metrics-view">
          <div class="evcc-empty">
            ${this.escapeHtml(snapshot.message || snapshot.reason || this.t("metrics.unavailable"))}
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
                <div class="evcc-metrics-panel-title">${this.t("metrics.panel_title")}</div>
                <div class="evcc-metrics-panel-subtitle">
                  ${this.t("metrics.panel_subtitle")}
                </div>
              </div>
            </div>

            <div class="evcc-metrics-stats">
              ${this._renderMetricsStat(this.t("metrics.stat_jobs"), metrics.job_count ?? 0)}
              ${this._renderMetricsStat(this.t("metrics.stat_used"), metrics.learning_used_count ?? 0)}
              ${this._renderMetricsStat(this.t("metrics.stat_excluded"), metrics.excluded_count ?? 0)}
              ${this._renderMetricsStat(this.t("metrics.stat_updated"), this._formatMetricsTimestamp(snapshot.updated_at) || this.t("metrics.unknown"))}
            </div>
          </section>

          <section class="evcc-metrics-panel evcc-metrics-panel--wide">
            <div class="evcc-metrics-panel-header">
              <div>
                <div class="evcc-metrics-panel-title">${this.t("metrics.filters_title")}</div>
                <div class="evcc-metrics-panel-subtitle">${this.t("metrics.filters_subtitle")}</div>
              </div>
            </div>

            <div class="evcc-metrics-filters">
              ${this._renderMetricsChipFilter(this.t("metrics.filter_room"), "room_slug", state.metricsFilterRoomOptions?.(), state.metricsFilters?.().room_slug, this.t("metrics.filter_all_rooms"))}
              ${this._renderMetricsChipFilter(this.t("metrics.filter_profile"), "profile_key",
                this._localizedProfileOptions(state.metricsFilterProfileOptions?.() ?? []),
                state.metricsFilters?.().profile_key, this.t("metrics.filter_all_profiles"))}
              ${this._renderMetricsChipFilter(this.t("metrics.filter_status"), "status", state.metricsFilterStatusOptions?.(), state.metricsFilters?.().status, this.t("metrics.filter_all_statuses"))}
              ${this._renderMetricsChipFilter(this.t("metrics.filter_learning_use"), "used_for_learning", state.metricsFilterUsedOptions?.().map((option) => ({
                value: option?.value_key ?? option?.value,
                label: option?.label ?? option?.value_key ?? option?.value,
              })), state.metricsFilters?.().used_for_learning, this.t("metrics.filter_all_learning_use"))}
            </div>
          </section>

          <section class="evcc-metrics-panel evcc-metrics-panel--wide">
            <div class="evcc-metrics-tabs" role="tablist" aria-label="${this.t("metrics.tabs_aria")}">
              ${state.metricsTabOptions?.().map((option) => `
                <button
                  type="button"
                  class="evcc-chip evcc-metrics-tab ${activeTab === option.value ? "active" : ""}"
                  data-metrics-tab="${this.escapeHtml(option.value)}"
                  role="tab"
                  aria-selected="${activeTab === option.value ? "true" : "false"}"
                >${this.tVocab("metrics_tab", option.value, option.label)}</button>
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
          ${this._renderMetricsWindowCard(this.t("metrics.window_today"), windows.today)}
          ${this._renderMetricsWindowCard(this.t("metrics.window_last_7_days"), windows.last_7_days)}
          ${this._renderMetricsWindowCard(this.t("metrics.window_last_30_days"), windows.last_30_days)}
        </div>

        <div class="evcc-metrics-card-grid">
          ${this._renderMetricsMiniCard(this.t("metrics.mini_found_profiles"), foundProfiles.length, this.t("metrics.mini_found_profiles_detail"))}
          ${this._renderMetricsMiniCard(this.t("metrics.mini_exact_stats"), exactCount, this.t("metrics.mini_exact_stats_detail"))}
          ${this._renderMetricsMiniCard(this.t("metrics.mini_baselines"), baselineCount, this.t("metrics.mini_baselines_detail"))}
          ${this._renderMetricsMiniCard(this.t("metrics.mini_accuracy_rows"), accuracyCount, this.t("metrics.mini_accuracy_rows_detail"))}
          ${this._renderMetricsMiniCard(this.t("metrics.mini_recharge_count"), metrics.mid_job_recharge_count ?? 0, this.t("metrics.mini_recharge_count_detail"))}
          ${this._renderMetricsMiniCard(this.t("metrics.mini_wash_cycles"), metrics.wash_cycle_count ?? 0, this.t("metrics.mini_wash_cycles_detail"))}
        </div>

        ${foundProfiles.length ? `
          <div class="evcc-metrics-card-grid">
            ${this._withDisambiguatedTitles(foundProfiles).slice(0, 8).map((profile) => this._renderMetricsFoundProfileCard(profile)).join("")}
          </div>
        ` : `
          <div class="evcc-metrics-empty">${this.t("metrics.empty_found_profiles")}</div>
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
      return `<div class="evcc-metrics-empty">${this.t("metrics.empty_rooms")}</div>`;
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
          <div class="evcc-metrics-empty">${this.t("metrics.empty_room_profiles")}</div>
        `}

        ${foundProfiles.length ? `
          <div class="evcc-metrics-panel-header">
            <div>
              <div class="evcc-metrics-panel-title">${this.t("metrics.found_profiles_title")}</div>
              <div class="evcc-metrics-panel-subtitle">${this.t("metrics.found_profiles_subtitle")}</div>
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
          ${this._renderMetricsMiniCard(this.t("metrics.water_robot"), this._formatMetricsMilliliters(metrics.total_robot_water_used_ml), this.t("metrics.water_robot_detail"))}
          ${this._renderMetricsMiniCard(this.t("metrics.water_overhead"), this._formatMetricsMilliliters(metrics.total_water_overhead_ml), this.t("metrics.water_overhead_detail"))}
          ${this._renderMetricsMiniCard(this.t("metrics.water_total"), this._formatMetricsMilliliters(metrics.total_water_used_ml), this.t("metrics.water_total_detail"))}
        </div>

        ${rooms.length ? `
          <div class="evcc-metrics-panel-header">
            <div>
              <div class="evcc-metrics-panel-title">${this.t("metrics.water_rooms_title")}</div>
              <div class="evcc-metrics-panel-subtitle">${this.t("metrics.water_rooms_subtitle")}</div>
            </div>
          </div>
          <div class="evcc-metrics-card-grid">
            ${rooms.map((room) => this._renderMetricsWaterRoomCard(room)).join("")}
          </div>
        ` : ""}

        ${profiles.length ? `
          <div class="evcc-metrics-panel-header">
            <div>
              <div class="evcc-metrics-panel-title">${this.t("metrics.water_profiles_title")}</div>
              <div class="evcc-metrics-panel-subtitle">${this.t("metrics.water_profiles_subtitle")}</div>
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
          ${this._renderMetricsMiniCard(this.t("metrics.dock_mop_wash"), dock.mop_wash_count ?? 0, this.t("metrics.dock_mop_wash_detail"))}
          ${this._renderMetricsMiniCard(this.t("metrics.dock_dust_empty"), dock.dust_empty_count ?? 0, this.t("metrics.dock_dust_empty_detail"))}
          ${this._renderMetricsMiniCard(this.t("metrics.dock_dry_starts"), dock.dry_start_count ?? 0, this.t("metrics.dock_dry_starts_detail"))}
          ${this._renderMetricsMiniCard(this.t("metrics.dock_wash_cycles"), dock.wash_cycle_count_from_jobs ?? 0, this.t("metrics.dock_wash_cycles_detail"))}
          ${this._renderMetricsMiniCard(this.t("metrics.dock_water_overhead"), this._formatMetricsMilliliters(dock.total_water_overhead_ml), this.t("metrics.dock_water_overhead_detail"))}
          ${this._renderMetricsMiniCard(this.t("metrics.dock_avg_overhead_per_job"), this._formatMetricsMilliliters(dock.avg_water_overhead_ml_per_job), this.t("metrics.dock_avg_overhead_per_job_detail"))}
        </div>

        <div class="evcc-metrics-card-grid">
          ${this._renderMetricsMiniCard(this.t("metrics.dock_last_mop_wash"), this._formatMetricsTimestamp(dock.last_mop_wash) || this.t("metrics.unknown"), this.t("metrics.dock_last_mop_wash_detail"))}
          ${this._renderMetricsMiniCard(this.t("metrics.dock_last_dust_empty"), this._formatMetricsTimestamp(dock.last_dust_empty) || this.t("metrics.unknown"), this.t("metrics.dock_last_dust_empty_detail"))}
          ${this._renderMetricsMiniCard(this.t("metrics.dock_last_dry_start"), this._formatMetricsTimestamp(dock.last_dry_start) || this.t("metrics.unknown"), this.t("metrics.dock_last_dry_start_detail"))}
          ${this._renderMetricsMiniCard(this.t("metrics.dock_last_dry_duration"), this._formatMetricsDurationValue(dock.last_dry_duration), this.t("metrics.dock_last_dry_duration_detail"))}
          ${this._renderMetricsMiniCard(this.t("metrics.dock_room_stats_rebuilt"), this._formatMetricsTimestamp(sources.room_stats_rebuilt_at) || this.t("metrics.unknown"), this.t("metrics.dock_room_stats_rebuilt_detail"))}
          ${this._renderMetricsMiniCard(this.t("metrics.dock_accuracy_updated"), this._formatMetricsTimestamp(sources.accuracy_stats_updated_at) || this.t("metrics.unknown"), this.t("metrics.dock_accuracy_updated_detail"))}
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
           <input type="text" class="evcc-chip-search" data-chip-search placeholder="${this.t("metrics.chip_search_placeholder")}" aria-label="${this.t("metrics.chip_search_aria", { label })}">
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
            >${this.tVocab(key, opt.value, opt.label)}</button>
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
        <div class="evcc-metrics-card-detail">${this.t("metrics.detail_jobs_used", { jobs: Number(item.job_count ?? 0), used: Number(item.learning_used_count ?? 0) })}</div>
        <div class="evcc-metrics-card-secondary">${this.t("metrics.detail_water_recharge", { water: this._formatMetricsMilliliters(item.total_water_used_ml), recharge: Number(item.mid_job_recharge_count ?? 0) })}</div>
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
    const title = room?.room_label || room?.room_slug || this.t("metrics.room_fallback");
    return `
      <div class="evcc-metrics-card">
        <div class="evcc-metrics-card-title">${this.escapeHtml(title)}</div>
        <div class="evcc-metrics-card-value">${this.escapeHtml(this._formatMetricsDuration(room?.avg_duration_minutes))}</div>
        <div class="evcc-metrics-card-detail">${this.t("metrics.detail_runs_used", { runs: Number(room?.run_count ?? 0), used: Number(room?.learning_run_count ?? 0) })}</div>
        <div class="evcc-metrics-card-secondary">${this.t("metrics.detail_trust_runs_to_trusted", { trust: this._formatMetricsTrustLevel(room?.trust_level), runs: Number(room?.runs_to_trusted ?? 0) })}</div>
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
      String(p?.profile_label || p?.selected_profile_label || p?.resolved_profile_label || p?.profile_key || this.t("metrics.profile_fallback"));
    st?._noteAmbiguousProfiles?.(profiles.map(titleOf));
    return profiles.map((p) => {
      const t = titleOf(p);
      const settings = String(p?.profile_subtitle ?? "").trim();
      return st?._isAmbiguousProfileLabel?.(t) && settings
        ? { ...p, display_title: `${t} · ${settings}`, _settings_in_title: true }
        : p;
    });
  };

  /**
   * Recompose a profile's display name + settings subtitle in the CARD's
   * per-user language from the raw settings the snapshot carries (clean_mode,
   * clean_intensity, fan_speed, water_level, passes, edge). Mirrors the backend
   * _settings_profile_label so the result matches, but localized. Falls back to
   * the backend's (English) profile_label/subtitle when the raw settings are
   * absent. Returns RAW strings (tVocabRaw/tRaw) — the card sinks escapeHtml.
   *
   * @param {object} profile
   * @returns {{label: string, subtitle: string}}
   */
  proto._localizedProfile = function (profile) {
    const fallback = {
      label: String(profile?.profile_label || profile?.label || profile?.selected_profile_label || profile?.resolved_profile_label || profile?.profile_key || ""),
      subtitle: String(profile?.profile_subtitle || profile?.subtitle || ""),
    };
    const hasSettings = profile?.clean_mode != null || profile?.clean_intensity != null || profile?.fan_speed != null || profile?.water_level != null;
    if (!hasSettings) return fallback;

    const v = (field, val) => (val == null || val === "") ? "" : this.tVocabRaw(field, val, String(val));
    const room = String(profile?.room_label ?? "").trim();
    const sel = String(profile?.selected_profile_name ?? "").trim().toLowerCase();
    const res = String(profile?.resolved_profile_name ?? "").trim().toLowerCase();
    const mode = v("clean_mode", profile?.clean_mode);
    const intensity = v("clean_intensity", profile?.clean_intensity);
    const fan = v("fan_speed", profile?.fan_speed);
    const water = (profile?.water_level != null && String(profile.water_level).toLowerCase() !== "off") ? v("water_level", profile.water_level) : "";
    const passes = Math.max(parseInt(profile?.clean_passes, 10) || 1, 1);
    const edge = Boolean(profile?.edge_mopping);
    const presetCodes = ["vacuum_quick", "vacuum_deep", "vacuum_mop_quick", "vacuum_mop_deep"];
    const isCustom = ["", "custom", "user_1"].includes(sel) || (sel !== res && !presetCodes.includes(sel));

    let label;
    if (!isCustom && (mode || intensity)) {
      label = [room, mode, intensity].filter(Boolean).join(" ").trim();
    } else {
      const bits = [room, this.tRaw("room_editor.custom"), mode];
      if (passes > 1) bits.push(this.tRaw("room_profile.passes", { count: passes }));
      label = bits.filter(Boolean).join(" ").trim();
    }
    const sub = [intensity, fan, water].filter(Boolean);
    if (passes > 1) sub.push(this.tRaw("room_profile.passes", { count: passes }));
    if (edge) sub.push(this.tRaw("room_card.edge_mopping_label"));
    return { label: label || fallback.label, subtitle: sub.join(" • ") || fallback.subtitle };
  };

  /**
   * Localize + disambiguate a list of profile filter options for the CARD's
   * per-user language. Each option carries the raw settings codes the backend
   * now sends; _localizedProfile recomposes a localized label + subtitle, and we
   * append the localized subtitle for any label that collides with a namesake.
   *
   * The ambiguity is (re)computed on the LOCALIZED label — NOT the backend's
   * pre-folded English label/subtitle — so two variants that share a name still
   * read apart after translation (and two that only collide once translated are
   * caught). The stable `value`/`profile_key` is never touched, so filtering
   * still targets the exact variant. Falls back to the backend English label for
   * any option without raw settings (graceful, e.g. sensor-only catalog rows).
   *
   * @param {Array<object>} options - backend filter options (value/label/…+settings).
   * @returns {Array<object>} options with localized, disambiguated label/subtitle/title.
   */
  proto._localizedProfileOptions = function (options) {
    if (!Array.isArray(options) || !options.length) return [];
    const st = this.card?._state;
    const localized = options.map((o) => {
      const lp = this._localizedProfile(o);
      return { o, label: lp.label, subtitle: String(lp.subtitle ?? "").trim() };
    });
    st?._noteAmbiguousProfiles?.(localized.map((x) => x.label));
    return localized.map(({ o, label, subtitle }) => {
      const ambiguous = !!(st?._isAmbiguousProfileLabel?.(label) && subtitle);
      return {
        ...o,
        label: ambiguous ? `${label} · ${subtitle}` : label,
        subtitle: ambiguous ? "" : subtitle,
        title: subtitle ? `${label} | ${subtitle}` : label,
      };
    });
  };

  proto._renderMetricsRoomProfileCard = function (profile) {
    const lp = this._localizedProfile(profile);
    const title = profile?._settings_in_title ? `${lp.label} · ${lp.subtitle}` : (lp.label || this.t("metrics.profile_fallback"));
    const subtitle = profile?._settings_in_title ? "" : (lp.subtitle || profile?.room_label || profile?.room_slug || "");
    const saveKey = this.card?._state?.metricsProfileSaveKey?.("profile", profile) ?? "";
    const pending = this.card?._state?.isMetricsProfileSavePending?.(saveKey) ?? false;
    const canSave = profile?.save_candidate === true && profile?.save_supported === true && String(profile?.save_service ?? "").trim() !== "";
    return `
      <div class="evcc-metrics-card">
        <div class="evcc-metrics-card-header">
          <div class="evcc-metrics-card-title">${this.escapeHtml(title)}</div>
          ${profile?.save_candidate === true ? `
            <span class="evcc-chip evcc-metrics-card-badge" title="${this.t("metrics.save_candidate_title")}">
              ${this.t("metrics.save_candidate")}
            </span>
          ` : ""}
        </div>
        ${subtitle ? `<div class="evcc-metrics-card-subtitle">${this.escapeHtml(subtitle)}</div>` : ""}
        <div class="evcc-metrics-card-value">${this.escapeHtml(this._formatMetricsDuration(profile?.avg_duration_minutes))}</div>
        <div class="evcc-metrics-card-detail">${this.t("metrics.detail_runs_used", { runs: Number(profile?.run_count ?? 0), used: Number(profile?.learning_run_count ?? 0) })}</div>
        <div class="evcc-metrics-card-secondary">${this.t("metrics.detail_water_trust", { water: this._formatMetricsMilliliters(profile?.avg_total_water_used_ml), trust: this._formatMetricsTrustLevel(profile?.trust_level) })}</div>
        ${canSave ? `
          <div class="evcc-metrics-card-actions">
            <button
              type="button"
              class="evcc-chip"
              data-metrics-save-profile="profile"
              data-profile-key="${this.escapeHtml(String(profile?.profile_key ?? ""))}"
              data-room-slug="${this.escapeHtml(String(profile?.room_slug ?? ""))}"
              ${pending ? "disabled" : ""}
              title="${this.t("metrics.save_profile_title")}"
            >${pending ? this.t("metrics.saving") : this.t("metrics.save_profile")}</button>
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
    const lp = this._localizedProfile(profile);
    const title = profile?._settings_in_title ? `${lp.label} · ${lp.subtitle}` : (lp.label || this.t("metrics.profile_fallback"));
    const subtitle = profile?._settings_in_title ? "" : (lp.subtitle || profile?.room_label || profile?.room_slug || "");
    // Localize from the stable trust_reason CODE; the backend's English
    // trust_reason_text is the fallback for any code we haven't keyed. tVocabRaw:
    // the sink escapeHtmls it (single escape).
    const trustReason = profile?.trust_reason
      ? this.tVocabRaw("estimate_reason", profile.trust_reason, profile?.trust_reason_text || "")
      : (profile?.trust_reason_text || "");
    const saveKey = this.card?._state?.metricsProfileSaveKey?.("found", profile) ?? "";
    const pending = this.card?._state?.isMetricsProfileSavePending?.(saveKey) ?? false;
    const canSave = profile?.save_candidate === true && String(profile?.save_service ?? "").trim() !== "";
    return `
      <div class="evcc-metrics-card">
        <div class="evcc-metrics-card-header">
          <div class="evcc-metrics-card-title">${this.escapeHtml(title)}</div>
          ${profile?.save_candidate === true ? `
            <span class="evcc-chip evcc-metrics-card-badge" title="${this.t("metrics.save_candidate_title")}">
              ${this.t("metrics.save_candidate")}
            </span>
          ` : ""}
        </div>
        ${subtitle ? `<div class="evcc-metrics-card-subtitle">${this.escapeHtml(subtitle)}</div>` : ""}
        <div class="evcc-metrics-card-value">${this.escapeHtml(this._formatMetricsTrustLevel(profile?.trust_level))}</div>
        <div class="evcc-metrics-card-detail">${this.t("metrics.detail_runs_used", { runs: Number(profile?.run_count ?? 0), used: Number(profile?.learning_run_count ?? 0) })}</div>
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
              title="${this.t("metrics.save_profile_title")}"
            >${pending ? this.t("metrics.saving") : this.t("metrics.save_profile")}</button>
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
        <div class="evcc-metrics-card-title">${this.escapeHtml(room?.room_label || room?.room_slug || this.t("metrics.room_fallback"))}</div>
        <div class="evcc-metrics-card-value">${this.escapeHtml(this._formatMetricsMilliliters(room?.avg_total_water_used_ml))}</div>
        <div class="evcc-metrics-card-detail">${this.t("metrics.detail_robot_overhead", { robot: this._formatMetricsMilliliters(room?.avg_robot_water_used_ml), overhead: this._formatMetricsMilliliters(room?.avg_water_overhead_ml) })}</div>
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
        <div class="evcc-metrics-card-title">${this.escapeHtml(profile?.profile_label || profile?.profile_key || this.t("metrics.profile_fallback"))}</div>
        <div class="evcc-metrics-card-value">${this.escapeHtml(this._formatMetricsMilliliters(profile?.avg_total_water_used_ml))}</div>
        <div class="evcc-metrics-card-detail">${this.t("metrics.detail_robot_overhead", { robot: this._formatMetricsMilliliters(profile?.avg_robot_water_used_ml), overhead: this._formatMetricsMilliliters(profile?.avg_water_overhead_ml) })}</div>
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
    const formatted = String(value ?? "")
      .replace(/[_-]+/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
    if (!formatted) return this.t("metrics.unknown");
    // Localize the trust/confidence tier (building/low/medium/good/high/trusted).
    // RAW (not tVocab): callers either insert via this.t (raw) or escapeHtml the
    // result themselves — tVocab would double-escape at the escapeHtml site.
    return this.tVocabRaw("trust_level", value, formatted);
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
    return String(value ?? this.t("metrics.unknown"));
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
          this.t("metrics.battery_charge_cycles"),
          sensorVal(m.cycles, 1),
          this.t("metrics.battery_charge_cycles_detail")
        )}
        ${this._renderMetricsMiniCard(
          this.t("metrics.battery_health"),
          sensorVal(m.health, 0, "%"),
          m.health?.attrs?.baseline_session_count
            ? this.t("metrics.battery_health_vs_first", { count: m.health.attrs.baseline_session_count })
            : this.t("metrics.battery_health_building")
        )}
        ${this._renderMetricsMiniCard(
          this.t("metrics.battery_charge_rate"),
          sensorVal(m.rate_overall, 2, " %/min"),
          m.rate_overall?.attrs?.charging ? this.t("metrics.battery_charging_now") : this.t("metrics.battery_last_sample")
        )}
        ${this._renderMetricsMiniCard(
          this.t("metrics.battery_last_job_per_m2"),
          sensorVal(m.last_job_per_m2, 3),
          m.last_job_per_m2?.attrs?.area_m2
            ? this.t("metrics.battery_area_used", { area: numFmt(m.last_job_per_m2.attrs.area_m2, 1), pct: numFmt(m.last_job_per_m2.attrs.battery_used_pct, 0) })
            : this.t("metrics.battery_awaiting_first_job")
        )}
      </div>
    `;

    // Charge rates table — one row per tracked zone.
    const ratesTable = `
      <div class="evcc-metrics-section-title">${this.t("metrics.battery_rates_title")}</div>
      <table class="evcc-metrics-table">
        <thead>
          <tr>
            <th>${this.t("metrics.battery_col_zone")}</th>
            <th>${this.t("metrics.battery_col_last_rate")}</th>
            <th>${this.t("metrics.battery_col_notes")}</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>${this.t("metrics.battery_zone_overall")}</td>
            <td>${this.escapeHtml(sensorVal(m.rate_overall, 2, " %/min"))}</td>
            <td>${this.t("metrics.battery_zone_overall_note")}</td>
          </tr>
          <tr>
            <td>${this.t("metrics.battery_zone_low")}</td>
            <td>${this.escapeHtml(sensorVal(m.rate_low, 2, " %/min"))}</td>
            <td>${this.t("metrics.battery_zone_low_note")}</td>
          </tr>
          <tr>
            <td>${this.t("metrics.battery_zone_high")}</td>
            <td>${this.escapeHtml(sensorVal(m.rate_high, 2, " %/min"))}</td>
            <td>${this.t("metrics.battery_zone_high_note")}</td>
          </tr>
          <tr>
            <td>${this.t("metrics.battery_zone_mid_job")}</td>
            <td>${this.escapeHtml(sensorVal(m.rate_mid_job, 2, " %/min"))}</td>
            <td>${this.t("metrics.battery_zone_mid_job_note", { count: m.rate_mid_job?.attrs?.sample_count ?? 0 })}</td>
          </tr>
          <tr>
            <td>${this.t("metrics.battery_zone_last_session")}</td>
            <td>${this.escapeHtml(sensorVal(m.last_charge_duration, 0, " min"))}</td>
            <td>${
              m.last_charge_duration?.attrs?.last_charge_delta_pct != null
                ? this.t("metrics.battery_zone_last_session_note", { pct: m.last_charge_duration.attrs.last_charge_delta_pct })
                : ""
            }</td>
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
        return `<tr><td colspan="3"><em>${this.t("metrics.battery_bucket_empty", { label })}</em></td></tr>`;
      }
      return keys.map((k) => `
        <tr>
          <!-- battery buckets carry clean_mode as a DISPLAY label ("vacuum and
               mop"); collapse " and " so tVocab's slug matches the vocab code key. -->
          <td>${this.tVocab("battery_bucket_key", String(k).replace(/\s+and\s+/gi, " "), k)}</td>
          <td>${this.escapeHtml(numFmt(obj[k]?.mean, 3))}</td>
          <td>${this.escapeHtml(String(obj[k]?.count ?? 0))}</td>
        </tr>
      `).join("");
    };

    const allCount = m.last_job_per_m2?.attrs?.all_jobs_count ?? 0;
    const allMean = m.last_job_per_m2?.attrs?.all_jobs_mean;

    const aggregateTable = `
      <div class="evcc-metrics-section-title">${this.t("metrics.battery_drain_title")}</div>
      <div class="evcc-metrics-section-subtitle">
        ${this.t("metrics.battery_drain_subtitle")}
      </div>
      <table class="evcc-metrics-table">
        <thead>
          <tr>
            <th>${this.t("metrics.battery_col_bucket")}</th>
            <th>${this.t("metrics.battery_col_mean_per_m2")}</th>
            <th>${this.t("metrics.battery_col_jobs")}</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>${this.t("metrics.battery_all_jobs")}</strong></td>
            <td>${this.escapeHtml(numFmt(allMean, 3))}</td>
            <td>${this.escapeHtml(String(allCount))}</td>
          </tr>
          <tr><td colspan="3"><em>${this.t("metrics.battery_by_clean_mode")}</em></td></tr>
          ${renderBucketRows(buckets, this.t("metrics.battery_bucket_clean_mode"))}
          <tr><td colspan="3"><em>${this.t("metrics.battery_by_fan_speed")}</em></td></tr>
          ${renderBucketRows(fanBuckets, this.t("metrics.battery_bucket_fan_speed"))}
          <tr><td colspan="3"><em>${this.t("metrics.battery_by_water_level")}</em></td></tr>
          ${renderBucketRows(waterBuckets, this.t("metrics.battery_bucket_water_level"))}
        </tbody>
      </table>
    `;

    // Last job summary — also expose post-job recharge linkage when present.
    const lastJob = m.last_job_per_m2?.attrs ?? {};
    const postJob = lastJob.post_job_charge ?? null;
    const lastJobBlock = lastJob.recorded_at ? `
      <div class="evcc-metrics-section-title">${this.t("metrics.battery_last_job_title")}</div>
      <table class="evcc-metrics-table">
        <tbody>
          <tr><td>${this.t("metrics.battery_row_job_id")}</td><td>${this.escapeHtml(String(lastJob.job_id ?? "—"))}</td></tr>
          <tr><td>${this.t("metrics.battery_row_recorded")}</td><td>${this.escapeHtml(this._formatMetricsTimestamp(lastJob.recorded_at) || "—")}</td></tr>
          <tr><td>${this.t("metrics.battery_row_duration")}</td><td>${this.escapeHtml(numFmt(lastJob.duration_min, 1) + " min")}</td></tr>
          <tr><td>${this.t("metrics.battery_row_area")}</td><td>${this.escapeHtml(numFmt(lastJob.area_m2, 1) + " m²")}</td></tr>
          <tr><td>${this.t("metrics.battery_row_battery_used")}</td><td>${this.escapeHtml(numFmt(lastJob.battery_used_pct, 0) + " %")}</td></tr>
          <tr><td>${this.t("metrics.battery_row_drain_rate")}</td><td>${this.escapeHtml(sensorVal(m.last_job_per_min, 2, " %/min"))}</td></tr>
          <tr><td>${this.t("metrics.battery_row_drain_per_hour")}</td><td>${this.escapeHtml(sensorVal(m.last_job_per_hour, 1, " %/h"))}</td></tr>
          <tr><td>${this.t("metrics.battery_row_drain_per_m2")}</td><td>${this.escapeHtml(sensorVal(m.last_job_per_m2, 3, " %/m²"))}</td></tr>
          <tr><td>${this.t("metrics.battery_row_single_clean_mode")}</td><td>${lastJob.single_clean_mode ? this.tVocab("clean_mode", String(lastJob.single_clean_mode).replace(/\s+and\s+/gi, " "), lastJob.single_clean_mode) : this.t("metrics.battery_mixed")}</td></tr>
          <tr><td>${this.t("metrics.battery_row_single_fan_speed")}</td><td>${lastJob.single_fan_speed ? this.tVocab("fan_speed", lastJob.single_fan_speed, lastJob.single_fan_speed) : this.t("metrics.battery_mixed")}</td></tr>
          <tr><td>${this.t("metrics.battery_row_single_water_level")}</td><td>${lastJob.single_water_level ? this.tVocab("water_level", lastJob.single_water_level, lastJob.single_water_level) : this.t("metrics.battery_mixed")}</td></tr>
          <tr><td>${this.t("metrics.battery_row_weighted_by")}</td><td>${lastJob.weighted_by ? this.tVocab("battery_weighted_by", lastJob.weighted_by, lastJob.weighted_by) : "—"}</td></tr>
          ${postJob ? `
            <tr><td colspan="2"><em>${this.t("metrics.battery_post_job_recharge")}</em></td></tr>
            <tr><td>${this.t("metrics.battery_row_recharge_duration")}</td><td>${this.escapeHtml(numFmt(postJob.duration_min, 1) + " min")}</td></tr>
            <tr><td>${this.t("metrics.battery_row_recharge_delta")}</td><td>${this.escapeHtml(`${postJob.start_battery ?? "?"} → ${postJob.end_battery ?? "?"} %`)}</td></tr>
            <tr><td>${this.t("metrics.battery_row_avg_rate")}</td><td>${this.escapeHtml(numFmt(postJob.avg_rate_per_min, 2) + " %/min")}</td></tr>
            <tr><td>${this.t("metrics.battery_row_ended")}</td><td>${this.escapeHtml(postJob.ended_reason ?? "—")}</td></tr>
          ` : `
            <tr><td>${this.t("metrics.battery_post_job_recharge")}</td><td><em>${this.t("metrics.battery_awaiting_charge_session")}</em></td></tr>
          `}
        </tbody>
      </table>
    ` : `
      <div class="evcc-metrics-section-title">${this.t("metrics.battery_last_job_title")}</div>
      <div class="evcc-empty">${this.t("metrics.battery_no_completed_job")}</div>
    `;

    const objectId = state.vacuumObjectId?.() ?? "";
    const rawDataNote = `
      <div class="evcc-metrics-section-title">${this.t("metrics.battery_raw_files_title")}</div>
      <div class="evcc-metrics-section-subtitle">
        ${this.t("metrics.battery_raw_files_subtitle")}
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
