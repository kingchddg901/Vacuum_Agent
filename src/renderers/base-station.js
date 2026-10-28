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
    // CENSUS-6: code first. dockStatusLabel() is the backend's English
    // *_status_label, and preferring it meant the header's "Dock status:" stayed
    // English in all 18 locales while vocab.device_status.* — documented for
    // exactly this row — sat unused. tVocab falls back to the backend label for
    // any state not keyed, so an unknown status still reads.
    //
    // All three rows use tVocab**Raw**: the sink below is _renderBaseStationStat,
    // which escapeHtml()s what it is handed. tVocab escapes too, so the escaping
    // twin double-escapes — latent while no catalogue value carries & < > " ',
    // measured true for all 18 device_status catalogues, and no longer true the
    // moment a locale renders one of these with an apostrophe.
    const _dockStatusCode = state.dockStatus?.() ?? upkeep.dock_status ?? null;
    const _dockStatusLabel = state.dockStatusLabel?.() ?? upkeep.dock_status_label ?? null;
    const dockStatus = _dockStatusCode
      ? this.tVocabRaw("device_status", _dockStatusCode, _dockStatusLabel ?? _dockStatusCode)
      : (_dockStatusLabel ?? null);
    // The two rows CENSUS-6 stopped short of. Same shape, different vocabularies:
    // lifecycle_state is the start-readiness verdict (vocab.lifecycle_state.*, six
    // values, RN1SW6P4), while the Task row carries active_job_status — our own job
    // slot, not the device. get_dock_action_status (dock/manager.py:489) emits
    // active_job_status and NEVER task_status, so dockTaskStatus()'s first branch is
    // unreachable from this payload; vocab.status.* is the right field for what does
    // arrive, and a restored task_status would fall back to the backend label.
    const _lifecycleCode = state.dockLifecycleState?.() ?? null;
    const _lifecycleLabel = state.dockLifecycleStateLabel?.() ?? null;
    const lifecycleState = _lifecycleCode
      ? this.tVocabRaw("lifecycle_state", _lifecycleCode, _lifecycleLabel ?? _lifecycleCode)
      : (_lifecycleLabel ?? null);
    const _taskCode = state.dockTaskStatus?.() ?? null;
    const _taskLabel = state.dockTaskStatusLabel?.() ?? null;
    const taskStatus = _taskCode
      ? this.tVocabRaw("status", _taskCode, _taskLabel ?? _taskCode)
      : (_taskLabel ?? null);
    const docked = state.isDocked?.() ?? false;
    const actionStatus = state.dockActionStatus?.() ?? null;
    const plannedWater = state.dashboardPlannedWaterEstimate?.() ?? null;
    const events = upkeep.dock_events ?? {};

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
                  ${this._baseStationAttentionSubtitle(upkeep)}
                </div>
              </div>
            </div>

            <div class="evcc-base-station-stats">
              ${this._renderBaseStationStat(this.t("base_station.stat_dock_status"), dockStatus || this.t("base_station.unknown"))}
              ${this._renderBaseStationStat(this.t("base_station.stat_lifecycle"), lifecycleState || this.t("base_station.unknown"))}
              ${this._renderBaseStationStat(this.t("base_station.stat_task"), taskStatus || this.t("base_station.unknown"))}
              ${this._renderBaseStationStat(this.t("base_station.stat_docked"), docked ? this.t("common.yes") : this.t("common.no"))}
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
                ${this._renderBaseStationStat(this.t("base_station.stat_station_water"), this._formatBaseStationWaterLevel(upkeep.station_water, state.stationWaterLabel?.()))}
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
        <div class="evcc-base-station-stat-label">${label}</div>
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
        <div class="evcc-base-station-activity-title">${label}</div>
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
    // Localize the gate via its stable reason CODE (ready / already_drying /
    // job_active / …); the backend's English message is the fallback. tVocabRaw:
    // the sinks escapeHtml it (single escape).
    const reasonText = this.tVocabRaw("dock_reason", gate?.reason, message || reasonLabel);

    return `
      <button
        type="button"
        class="evcc-base-station-action-card ${allowed ? "evcc-base-station-action-card--allowed" : "evcc-base-station-action-card--blocked"}"
        data-dock-action="${this.escapeHtml(action)}"
        ${allowed && !pending ? "" : "disabled"}
        title="${this.escapeHtml(reasonText) || (allowed ? label : this.t("base_station.action_unavailable"))}"
      >
        <div class="evcc-base-station-action-title">${label}</div>
        <div class="evcc-base-station-action-state">
          ${pending ? this.t("base_station.state_running") : allowed ? this.t("base_station.state_ready") : this.t("base_station.state_unavailable")}
        </div>
        <div class="evcc-base-station-action-detail">
          ${this.escapeHtml(reasonText) || this.t("base_station.action_available")}
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
    return `${Math.round(amount)} ${this.t("metrics.unit_ml")}`;
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
    const unitMl = this.t("metrics.unit_ml");
    const unitPct = this.t("metrics.unit_percent");
    if (Number.isFinite(percent)) {
      return `${Math.round(ml)} ${unitMl} (${Math.round(percent)}${unitPct})`;
    }
    return `${Math.round(ml)} ${unitMl}`;
  };

  /**
   * Format a water level value: numeric → "N%", non-numeric → title-cased label.
   *
   * @param {*} value - Raw water level (numeric percent or string key).
   * @returns {string} Formatted water level string.
   */
  /**
   * The Station Status panel's subtitle: how many upkeep items need attention.
   *
   * Composed from `attention_count`, which is the same thing the Upkeep tab's own header
   * already does with the same two keys — this panel printed `upkeep.attention_summary`,
   * the backend's English sentence, in all 17 languages. The keys live in the
   * `maintenance.*` namespace and are reused rather than duplicated: the concept belongs
   * to upkeep whichever view shows it, and a second copy would be two more keys to keep in
   * step for no gain.
   *
   * ABSENT IS NOT ZERO, and that rule is inherited rather than rediscovered: `Number(null)`
   * is 0 and 0 IS finite, so a `?? 0` here would render a confident "No upkeep items need
   * attention" on a payload that never said so. [C6-6] caught exactly that in the Upkeep
   * tab's copy.
   *
   * THE TWO BRANCHES ARE ESCAPED SEPARATELY, and that is the second defect this replaces.
   * The expression was `escapeHtml(attention_summary || t("…subtitle"))` — one escape over
   * both arms — so the localized fallback was escaped twice. Live, not theoretical:
   * measured across all 17 packs, `it` is the one whose subtitle carries an apostrophe
   * ("dell'attività"), and it rendered as `dell&#39;attività` on screen.
   *
   * @param {object} upkeep - the maintenance snapshot.
   * @returns {string} HTML-safe subtitle, for RAW interpolation.
   */
  proto._baseStationAttentionSubtitle = function (upkeep) {
    const countRaw = upkeep?.attention_count != null ? Number(upkeep.attention_count) : NaN;
    if (Number.isFinite(countRaw)) {
      // t() output is already escaped — interpolated raw by the caller.
      return countRaw > 0
        ? this.t("maintenance.attention_summary", { count: countRaw })
        : this.t("maintenance.attention_summary_none");
    }
    // Backend-sourced, so escaped HERE, at the untrusted source.
    const fromBackend = this.escapeHtml(upkeep?.attention_summary ?? "");
    return fromBackend || this.t("base_station.station_status_subtitle");
  };

  proto._formatBaseStationWaterLevel = function (value, backendLabel = null) {
    // `hasValue` is LOAD-BEARING, and this is the SHORTER COPY of a guard the maintenance
    // renderer already carries with its own note: Number(null) is 0 and Number.isFinite(0)
    // is true, so without it a dock that reports no water level at all renders a confident
    // "0%". It was reachable before (no code AND no label) and demoting the label below the
    // code widened it to every no-code payload — caught by [SSV-1] on exactly that input.
    const hasValue = value != null && value !== "";
    const numeric = Number(value);
    if (hasValue && Number.isFinite(numeric)) return `${Math.round(numeric)}${this.t("metrics.unit_percent")}`;
    // String keys ("low", "medium", "unknown", …) are backend vocabulary — localize via
    // the existing vocab.water_level family. Raw: the stat sink escapes.
    //
    // `backendLabel` is the payload's own station_water_label, and it is the FALLBACK, not
    // the preference. It used to win outright at the call site (`stationWaterLabel() || …`),
    // which short-circuited this whole function and printed the backend's English word in
    // every locale while the Dock status row beside it was translated. The label still
    // carries the only answer when no code arrives (tVocabRaw returns the fallback for a
    // null value), so nothing is lost by demoting it.
    return this.tVocabRaw("water_level", value, backendLabel || this._formatBaseStationLabel(value));
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
      return `${numeric.toFixed(1).replace(/\.0$/, "")} ${this.t("run_profiles.minutes_unit")}`;
    }
    return String(value ?? "");
  };
}
