/**
 * ============================================================
 * RENDERERS: BASE STATION
 * ============================================================
 *
 * Renders the Base Station view — dock status, water level,
 * dock action cards, and pause timeout controls.
 *
 * ============================================================
 */

/**
 * Mix base station renderer methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applyBaseStationRenderers(proto) {

  /* =========================================================
     MAIN VIEW
     ========================================================= */

  /**
   * Render the full Base Station view with status stats, water panel, activity, and dock actions.
   *
   * @param {object} ctx - Render context containing `state`.
   * @returns {string} HTML string.
   */
  proto.renderBaseStationView = function (ctx) {
    const { state } = ctx;
    const upkeep = state.dashboardUpkeep?.() ?? {};
    const dockStatus = state.dockStatusLabel?.() ?? state.dockStatus?.() ?? upkeep.dock_status_label ?? upkeep.dock_status ?? null;
    const lifecycleState = state.dockLifecycleStateLabel?.() ?? state.dockLifecycleState?.() ?? null;
    const taskStatus = state.dockTaskStatusLabel?.() ?? state.dockTaskStatus?.() ?? null;
    const docked = state.isDocked?.() ?? false;
    const actionStatus = state.dockActionStatus?.() ?? null;
    const plannedWater = state.dashboardPlannedWaterEstimate?.() ?? null;
    const events = upkeep.dock_events ?? {};
    const pauseTimeoutMinutes = state.pauseTimeoutMinutesDefault?.();

    /* Capability-gated dock action list. The backend's per-action
       gate exposes `supported: bool` reflecting the adapter's
       capability flags (supports_mop_wash / supports_mop_dry /
       supports_empty_dust). Actions not supported by this vacuum
       are omitted entirely rather than rendered as disabled clutter.
       `stop_dry_mop` rides on supports_mop_dry. */
    const _DOCK_ACTIONS = [
      { id: "wash_mop",     label: this.t("base_station.action_wash_mop")     },
      { id: "dry_mop",      label: this.t("base_station.action_dry_mop")      },
      { id: "stop_dry_mop", label: this.t("base_station.action_stop_drying")  },
      { id: "empty_dust",   label: this.t("base_station.action_empty_dust")   },
    ];
    const supportedActions = _DOCK_ACTIONS.filter(
      ({ id }) => state.dockActionGate?.(id)?.supported !== false,
    );
    const actionCards = supportedActions
      .map(({ id, label }) => this._renderDockActionCard(id, label, state))
      .join("");

    /* Derive panel-level capability flags from the per-action gates.
       The Water panel only makes sense for vacuums whose dock exposes
       a clean-water tank — which is the same surface that wash_mop
       depends on. The Recent Dock Activity panel only makes sense
       when at least one event-producing action is supported. */
    const hasWaterCapability =
      state.dockActionGate?.("wash_mop")?.supported !== false;
    const hasAnyDockActivity = supportedActions.length > 0;

    return `
      <div class="evcc-base-station-view">
        <div class="evcc-base-station-grid">

          <section class="evcc-base-station-panel">
            <div class="evcc-base-station-panel-header">
              <div>
                <div class="evcc-base-station-panel-title">${this.t("base_station.station_status_title")}</div>
                <div class="evcc-base-station-panel-subtitle">
                  ${this.escapeHtml(
                    upkeep.attention_summary ||
                    this.t("base_station.station_status_subtitle")
                  )}
                </div>
              </div>
            </div>

            <div class="evcc-base-station-stats">
              ${this._renderBaseStationStat(this.t("base_station.stat_dock_status"), dockStatus || this.t("base_station.unknown"))}
              ${this._renderBaseStationStat(this.t("base_station.stat_lifecycle"), lifecycleState || this.t("base_station.unknown"))}
              ${this._renderBaseStationStat(this.t("base_station.stat_task"), taskStatus || this.t("base_station.unknown"))}
              ${this._renderBaseStationStat(this.t("base_station.stat_docked"), docked ? this.t("base_station.yes") : this.t("base_station.no"))}
            </div>

            ${(upkeep.updated_at || actionStatus?.updated_at) ? `
              <div class="evcc-base-station-updated">
                ${this.t("base_station.updated_prefix", {
                  timestamp: this.escapeHtml(
                    this._formatBaseStationTimestamp(actionStatus?.updated_at ?? upkeep.updated_at)
                  ),
                })}
              </div>
            ` : ""}
          </section>

          ${hasWaterCapability ? `
            <section class="evcc-base-station-panel">
              <div class="evcc-base-station-panel-header">
                <div>
                  <div class="evcc-base-station-panel-title">${this.t("base_station.water_title")}</div>
                  <div class="evcc-base-station-panel-subtitle">
                    ${this.t("base_station.water_subtitle")}
                  </div>
                </div>
              </div>

              <div class="evcc-base-station-stats">
                ${this._renderBaseStationStat(this.t("base_station.stat_station_water"), state.stationWaterLabel?.() || this._formatBaseStationWaterLevel(upkeep.station_water))}
                ${this._renderBaseStationStat(this.t("base_station.stat_tank_now"), this._formatBaseStationMilliliters(plannedWater?.available_clean_tank_ml))}
                ${this._renderBaseStationStat(this.t("base_station.stat_after_job"), this._formatBaseStationProjectedTank(plannedWater))}
                ${this._renderBaseStationStat(this.t("base_station.stat_job_use"), this._formatBaseStationMilliliters(plannedWater?.estimated_total_dock_clean_water_used_ml))}
              </div>
            </section>
          ` : ""}

          ${hasAnyDockActivity ? `
            <section class="evcc-base-station-panel evcc-base-station-panel--wide">
              <div class="evcc-base-station-panel-header">
                <div>
                  <div class="evcc-base-station-panel-title">${this.t("base_station.activity_title")}</div>
                  <div class="evcc-base-station-panel-subtitle">
                    ${this.t("base_station.activity_subtitle")}
                  </div>
                </div>
              </div>

              <div class="evcc-base-station-activity-grid">
                ${state.dockActionGate?.("wash_mop")?.supported !== false
                  ? this._renderBaseStationActivityCard(this.t("base_station.activity_mop_wash"), events.last_mop_wash, events.mop_wash_count)
                  : ""}
                ${state.dockActionGate?.("empty_dust")?.supported !== false
                  ? this._renderBaseStationActivityCard(this.t("base_station.activity_dust_empty"), events.last_dust_empty, events.dust_empty_count)
                  : ""}
                ${state.dockActionGate?.("dry_mop")?.supported !== false
                  ? this._renderBaseStationActivityCard(this.t("base_station.activity_dry_start"), events.last_dry_start, events.dry_start_count, events.last_dry_duration)
                  : ""}
              </div>
            </section>
          ` : ""}

          <section class="evcc-base-station-panel evcc-base-station-panel--wide">
            <div class="evcc-base-station-panel-header">
              <div>
                <div class="evcc-base-station-panel-title">${this.t("base_station.pause_timeout_title")}</div>
                <div class="evcc-base-station-panel-subtitle">
                  ${this.t("base_station.pause_timeout_subtitle")}
                </div>
              </div>
            </div>

            <div class="evcc-chips">
              ${[15, 30, 45, 60].map((minutes) => `
                <button
                  type="button"
                  class="evcc-chip ${pauseTimeoutMinutes === minutes ? "active" : ""}"
                  data-pause-timeout-minutes="${minutes}"
                >${this.t("base_station.minutes_short", { minutes })}</button>
              `).join("")}
            </div>
          </section>

          ${supportedActions.length > 0 ? `
            <section class="evcc-base-station-panel evcc-base-station-panel--wide">
              <div class="evcc-base-station-panel-header">
                <div>
                  <div class="evcc-base-station-panel-title">${this.t("base_station.dock_actions_title")}</div>
                  <div class="evcc-base-station-panel-subtitle">
                    ${this.t("base_station.dock_actions_subtitle")}
                  </div>
                </div>
              </div>

              <div class="evcc-base-station-action-grid">
                ${actionCards}
              </div>
            </section>
          ` : ""}

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
   * @param {string} value - Stat value.
   * @returns {string} HTML string.
   */
  proto._renderBaseStationStat = function (label, value) {
    return `
      <div class="evcc-base-station-stat">
        <div class="evcc-base-station-stat-value">${this.escapeHtml(value)}</div>
        <div class="evcc-base-station-stat-label">${this.escapeHtml(label)}</div>
      </div>
    `;
  };

  /**
   * Render a dock-activity summary card (last time, event count, optional duration).
   *
   * @param {string} label - Activity label (e.g. "Mop Wash").
   * @param {string|null} lastAt - ISO timestamp of last event.
   * @param {number} count - Total recorded event count.
   * @param {*} [extra] - Optional extra value (e.g. last dry duration).
   * @returns {string} HTML string.
   */
  proto._renderBaseStationActivityCard = function (label, lastAt, count, extra = null) {
    return `
      <div class="evcc-base-station-activity-card">
        <div class="evcc-base-station-activity-title">${this.escapeHtml(label)}</div>
        <div class="evcc-base-station-activity-time">${this.escapeHtml(this._formatBaseStationTimestamp(lastAt)) || this.t("base_station.no_activity_yet")}</div>
        <div class="evcc-base-station-activity-detail">
          ${this.t("base_station.recorded_count", { count: Number(count ?? 0) })}
          ${extra != null && extra !== "" ? ` · ${this.escapeHtml(this._formatBaseStationDuration(extra))}` : ""}
        </div>
      </div>
    `;
  };

  /**
   * Render a dock action button card; shows gated availability and pending state.
   *
   * @param {string} action - Action key (e.g. "wash_mop").
   * @param {string} label - Display label.
   * @param {object} state - Card state.
   * @returns {string} HTML string.
   */
  proto._renderDockActionCard = function (action, label, state) {
    const gate = state.dockActionGate?.(action) ?? {};
    const allowed = gate?.allowed === true;
    const pending = state.isDockActionPending?.(action) ?? false;
    const reasonLabel = gate?.reason_label ?? "";
    const message = gate?.message ?? "";

    return `
      <button
        type="button"
        class="evcc-base-station-action-card ${allowed ? "evcc-base-station-action-card--allowed" : "evcc-base-station-action-card--blocked"}"
        data-dock-action="${this.escapeHtml(action)}"
        ${allowed && !pending ? "" : "disabled"}
        title="${this.escapeHtml(message || reasonLabel) || (allowed ? this.escapeHtml(label) : this.t("base_station.action_unavailable"))}"
      >
        <div class="evcc-base-station-action-title">${this.escapeHtml(label)}</div>
        <div class="evcc-base-station-action-state">
          ${pending ? this.t("base_station.state_running") : allowed ? this.t("base_station.state_ready") : this.t("base_station.state_unavailable")}
        </div>
        <div class="evcc-base-station-action-detail">
          ${this.escapeHtml(message || reasonLabel) || this.t("base_station.action_available")}
        </div>
      </button>
    `;
  };

  /* =========================================================
     FORMATTERS
     ========================================================= */

  /**
   * Convert a snake_case or kebab-case string to a title-cased display label.
   *
   * @param {*} value - Raw string value.
   * @returns {string} Title-cased label, or "Unknown" for blank input.
   */
  proto._formatBaseStationLabel = function (value) {
    const raw = String(value ?? "").trim();
    if (!raw) return this.t("base_station.unknown");
    return raw
      .replace(/[_-]+/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  };

  /**
   * Format an ISO timestamp for base station display (short month, day, hour, minute).
   *
   * @param {string|null} value - ISO timestamp string or null.
   * @returns {string} Formatted timestamp, or empty string.
   */
  proto._formatBaseStationTimestamp = function (value) {
    return this.formatTimestamp(value, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }, "");
  };

  /**
   * Format a numeric milliliter value as a rounded "N ml" string.
   *
   * @param {*} value - Raw milliliter amount.
   * @returns {string} Formatted string, or "Unknown" for non-finite input.
   */
  proto._formatBaseStationMilliliters = function (value) {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return this.t("base_station.unknown");
    return `${Math.round(amount)} ml`;
  };

  /**
   * Format the projected post-job tank level as "N ml (P%)" or "N ml".
   *
   * @param {object|null} plannedWater - Planned water estimate from state.
   * @returns {string} Formatted projection string, or "Unknown".
   */
  proto._formatBaseStationProjectedTank = function (plannedWater) {
    const ml = Number(plannedWater?.estimated_clean_tank_remaining_ml);
    const percent = Number(plannedWater?.estimated_clean_tank_remaining_percent);
    if (!Number.isFinite(ml)) return this.t("base_station.unknown");
    if (Number.isFinite(percent)) {
      return `${Math.round(ml)} ml (${Math.round(percent)}%)`;
    }
    return `${Math.round(ml)} ml`;
  };

  /**
   * Format a water level value: numeric → "N%", non-numeric → title-cased label.
   *
   * @param {*} value - Raw water level (numeric percent or string key).
   * @returns {string} Formatted water level string.
   */
  proto._formatBaseStationWaterLevel = function (value) {
    const numeric = Number(value);
    if (Number.isFinite(numeric)) return `${Math.round(numeric)}%`;
    return this._formatBaseStationLabel(value);
  };

  /**
   * Format a raw duration value: numeric → "N min", non-numeric → string passthrough.
   *
   * @param {*} value - Raw duration value.
   * @returns {string} Formatted duration string.
   */
  proto._formatBaseStationDuration = function (value) {
    const numeric = Number(value);
    if (Number.isFinite(numeric)) {
      return `${numeric.toFixed(1).replace(/\.0$/, "")} min`;
    }
    return String(value ?? "");
  };
}
