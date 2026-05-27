/**
 * ============================================================
 * RENDERERS: MAINTENANCE
 * ============================================================
 *
 * Renders the Maintenance tab — upkeep/replacement summary cards,
 * attention list, water card, and maintenance item modal.
 *
 * ============================================================
 */

/**
 * Mix maintenance renderer methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applyMaintenanceRenderers(proto) {

  /* =========================================================
     MAIN VIEW
     ========================================================= */

  /**
   * Render the full Maintenance view with overview stats, attention list, tab switcher, and item cards.
   *
   * @param {object} ctx - Render context containing `state`.
   * @returns {string} HTML string.
   */
  proto.renderMaintenanceView = function (ctx) {
    const { state } = ctx;

    const upkeep = state.dashboardUpkeep?.() ?? {};
    const attentionSummary = upkeep.attention_summary ?? state.dashboardAttentionSummary?.();
    const statusSummary = state.dashboardStatusSummary?.();
    const modelMeta = upkeep.model_meta ?? {};

    const replacementItems = Array.isArray(upkeep.replacement_items)
      ? upkeep.replacement_items
      : [];

    const maintenanceItems = Array.isArray(upkeep.maintenance_items)
      ? upkeep.maintenance_items
      : [];

    const attentionCount = Number(upkeep.attention_count ?? 0);
    const highestPriorityStatus = upkeep.highest_priority_status_label ?? upkeep.highest_priority_status ?? null;
    const updatedAt = upkeep.updated_at ?? null;
    const activeTab = state.maintenanceActiveTab?.() ?? "maintenance_items";
    const tabItems = activeTab === "replacements"
      ? replacementItems
      : maintenanceItems;
    const tabTitle = activeTab === "replacements"
      ? "Replacement Items"
      : "Maintenance Items";
    const tabSubtitle = activeTab === "replacements"
      ? "Upstream replacement-style items"
      : "Integration-managed maintenance intervals";
    const attentionItems = [
      ...maintenanceItems.map((item) => ({ ...item, _category: "Maintenance" })),
      ...replacementItems.map((item) => ({ ...item, _category: "Replacement" })),
    ].filter((item) => this._maintenanceItemNeedsAttention(item));
    const stationWater = upkeep.station_water ?? null;
    const plannedWaterEstimate = state.dashboardPlannedWaterEstimate?.() ?? null;
    const availableCleanTankMl = plannedWaterEstimate?.available_clean_tank_ml ?? null;

    const modelName = modelMeta.name ?? null;
    const guideFamilyName = modelMeta.guide_family_name ?? null;
    const replacementAttentionCount = replacementItems.filter((item) =>
      this._maintenanceItemNeedsAttention(item)
    ).length;
    const maintenanceAttentionCount = maintenanceItems.filter((item) =>
      this._maintenanceItemNeedsAttention(item)
    ).length;

    return `
      <div class="evcc-maintenance-view">
        <div class="evcc-maintenance-grid">

          <section class="evcc-maintenance-panel">
            <div class="evcc-maintenance-panel-header">
              <div>
                <div class="evcc-maintenance-panel-title">Maintenance Overview</div>
                <div class="evcc-maintenance-panel-subtitle">
                  ${this.escapeHtml(attentionSummary || statusSummary || "Backend maintenance snapshot")}
                </div>
              </div>
              ${guideFamilyName ? `
                <div class="evcc-maintenance-meta-badge">
                  ${this.escapeHtml(guideFamilyName)}
                </div>
              ` : ""}
            </div>

            ${modelName || updatedAt ? `
              <div class="evcc-maintenance-model-line">
                ${this.escapeHtml(modelName ?? "")}
                ${modelName && updatedAt ? " · " : ""}
                ${updatedAt ? `Updated ${this.escapeHtml(this._formatMaintenanceTimestamp(updatedAt))}` : ""}
              </div>
            ` : ""}

            <div class="evcc-maintenance-stats">
              ${this._renderMaintenanceStat("Attention", attentionCount)}
              ${this._renderMaintenanceStat("Priority", highestPriorityStatus || "Normal")}
              ${this._renderMaintenanceStat("Items", maintenanceItems.length)}
              ${this._renderMaintenanceStat("Water", upkeep.station_water_label ?? stationWater ?? "Unknown")}
            </div>
          </section>

          <section class="evcc-maintenance-panel">
            <div class="evcc-maintenance-panel-header">
              <div>
                <div class="evcc-maintenance-panel-title">Replacement Overview</div>
                <div class="evcc-maintenance-panel-subtitle">
                  Replacement inventory and lifecycle snapshot
                </div>
              </div>
            </div>

            <div class="evcc-maintenance-stats">
              ${this._renderMaintenanceStat("Items", replacementItems.length)}
              ${this._renderMaintenanceStat("Attention", replacementAttentionCount)}
              ${this._renderMaintenanceStat("Healthy", Math.max(replacementItems.length - replacementAttentionCount, 0))}
              ${this._renderMaintenanceStat("Status", replacementItems.length ? "Tracked" : "Empty")}
            </div>
          </section>

          <section class="evcc-maintenance-panel evcc-maintenance-panel--wide">
            <div class="evcc-maintenance-panel-header">
              <div>
                <div class="evcc-maintenance-panel-title">Needs Attention</div>
                <div class="evcc-maintenance-panel-subtitle">
                  ${this.escapeHtml(attentionItems.length
                    ? "Items currently flagged for service or replacement attention"
                    : "No maintenance or replacement items currently need attention")}
                </div>
              </div>
            </div>

            ${attentionItems.length
              ? `<div class="evcc-maintenance-list">
                  ${attentionItems.map((item) => this._renderMaintenanceAttentionItem(item)).join("")}
                 </div>`
              : `<div class="evcc-maintenance-empty">Everything currently looks healthy.</div>`
            }
          </section>

          <section class="evcc-maintenance-panel evcc-maintenance-panel--wide">
            <div class="evcc-maintenance-panel-header">
              <div>
                <div class="evcc-maintenance-panel-title">Items</div>
                <div class="evcc-maintenance-panel-subtitle">
                  Switch between maintenance intervals and replacement items
                </div>
              </div>
            </div>

            <div class="evcc-maintenance-tabs" role="tablist" aria-label="Maintenance item groups">
              <button
                type="button"
                class="evcc-chip evcc-maintenance-tab ${activeTab === "maintenance_items" ? "active" : ""}"
                data-maintenance-tab="maintenance_items"
                role="tab"
                aria-selected="${activeTab === "maintenance_items" ? "true" : "false"}"
              >
                Maintenance Items
              </button>

              <button
                type="button"
                class="evcc-chip evcc-maintenance-tab ${activeTab === "replacements" ? "active" : ""}"
                data-maintenance-tab="replacements"
                role="tab"
                aria-selected="${activeTab === "replacements" ? "true" : "false"}"
              >
                Replacements
              </button>
            </div>

            <div class="evcc-maintenance-tab-panel">
              <div class="evcc-maintenance-tab-header">
                <div class="evcc-maintenance-panel-title">${this.escapeHtml(tabTitle)}</div>
                <div class="evcc-maintenance-panel-subtitle">${this.escapeHtml(tabSubtitle)}</div>
              </div>

              ${tabItems.length
                ? `<div class="evcc-maintenance-card-grid">
                    ${tabItems.map((item) => this._renderMaintenanceCard(item)).join("")}
                    ${activeTab === "maintenance_items"
                      ? this._renderStationWaterCard(stationWater, availableCleanTankMl, upkeep.station_water_label)
                      : ""}
                   </div>`
                : `<div class="evcc-maintenance-empty">No ${activeTab === "replacements" ? "replacement" : "maintenance"} items reported.</div>`
              }
            </div>
          </section>

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
  proto._renderMaintenanceStat = function (label, value) {
    return `
      <div class="evcc-maintenance-stat">
        <div class="evcc-maintenance-stat-value">${this.escapeHtml(value)}</div>
        <div class="evcc-maintenance-stat-label">${this.escapeHtml(label)}</div>
      </div>
    `;
  };

  /**
   * Render a clickable attention-list item that opens the maintenance modal.
   *
   * @param {object} item - Maintenance or replacement item with injected `_category` key.
   * @returns {string} HTML string.
   */
  proto._renderMaintenanceAttentionItem = function (item) {
    const name = item?.label ?? item?.component_label ?? item?.name ?? item?.title ?? "Unnamed item";
    const status = item?.status_label ?? this._formatMaintenanceStatus(item?.status ?? "warning");
    const detail =
      item?.remaining_summary ??
      item?.usage_summary ??
      item?.summary ??
      item?.message ??
      item?.description ??
      item?.detail ??
      "";

    return `
      <button
        type="button"
        class="evcc-maintenance-item"
        data-action="open-maintenance-modal"
        data-item-kind="${this.escapeHtml(String(item?.kind ?? ""))}"
        data-item-component="${this.escapeHtml(String(item?.component ?? ""))}"
        data-item-entity-id="${this.escapeHtml(String(item?.entity_id ?? ""))}"
      >
        <div class="evcc-maintenance-item-main">
          <div class="evcc-maintenance-item-name">${this.escapeHtml(name)}</div>
          <div class="evcc-maintenance-item-detail">
            ${this.escapeHtml(
              [item?._category, detail].filter(Boolean).join(" · ")
            )}
          </div>
        </div>
        <div class="evcc-maintenance-item-side">${this.escapeHtml(status)}</div>
      </button>
    `;
  };

  /**
   * Render a maintenance or replacement item card with progress fill and guide summary.
   *
   * @param {object} item - Maintenance or replacement item.
   * @returns {string} HTML string.
   */
  proto._renderMaintenanceCard = function (item) {
    const name = item?.label ?? item?.component_label ?? item?.name ?? item?.title ?? "Unnamed item";
    const kind = String(item?.kind ?? "maintenance");
    const statusKey = String(item?.status ?? "unknown");
    const status = item?.status_label ?? this._formatMaintenanceStatus(statusKey);
    const available = item?.available !== false;
    const remainingPercent = this._maintenanceRemainingPercent(item);
    const fillPercent = Number.isFinite(remainingPercent)
      ? Math.max(0, Math.min(100, remainingPercent))
      : 0;
    const primaryValue = this._maintenancePrimaryValue(item);
    const secondaryValue = this._maintenanceSecondaryValue(item);
    const guide = item?.guide?.display ?? null;
    const guideSummary = guide?.frequency || this._formatMaintenanceFrequency(guide?.frequency);

    return `
      <button
        type="button"
        class="evcc-maintenance-card evcc-maintenance-card--status-${this.escapeHtml(statusKey)} ${available ? "" : "evcc-maintenance-card--unavailable"}"
        data-action="open-maintenance-modal"
        data-item-kind="${this.escapeHtml(kind)}"
        data-item-component="${this.escapeHtml(String(item?.component ?? ""))}"
        data-item-entity-id="${this.escapeHtml(String(item?.entity_id ?? ""))}"
        style="--maintenance-remaining:${fillPercent}%;"
      >
        <div class="evcc-maintenance-card-header">
          <div class="evcc-maintenance-card-title">${this.escapeHtml(name)}</div>
          <div class="evcc-maintenance-card-status">${this.escapeHtml(status)}</div>
        </div>

        <div class="evcc-maintenance-card-value">
          ${this.escapeHtml(primaryValue)}
        </div>

        <div class="evcc-maintenance-card-detail">
          ${this.escapeHtml(
            [item?.kind_label ?? this._formatMaintenanceKind(kind), secondaryValue].filter(Boolean).join(" | ")
          )}
        </div>

        ${guideSummary ? `
          <div class="evcc-maintenance-card-secondary">
            ${this.escapeHtml(guideSummary)}
          </div>
        ` : ""}
      </button>
    `;
  };

  /**
   * Render the station water reservoir card with derived status and fill percentage.
   *
   * PURPOSE: The backend may return a numeric percent or a string level key ("low", "full", etc.).
   * RULES: Numeric thresholds: ≥70 → good, ≥35 → warning, >0 → replace_soon, 0 → replace_now.
   *        String normalization maps common labels to the same four status keys.
   *
   * @param {*} stationWater - Raw water level value (number or string).
   * @param {number|null} [availableCleanTankMl] - Available clean tank volume in ml.
   * @param {string|null} [stationWaterLabel] - Override display label from state.
   * @returns {string} HTML string.
   */
  proto._renderStationWaterCard = function (stationWater, availableCleanTankMl = null, stationWaterLabel = null) {
    const hasValue = stationWater != null && stationWater !== "";
    const numericValue = Number(stationWater);
    const isNumeric = Number.isFinite(numericValue);
    const rawValue = String(stationWaterLabel ?? "").trim() || (hasValue
      ? (isNumeric ? `${Math.round(numericValue)}%` : String(stationWater))
      : "Unknown");

    const normalized = String(rawValue).trim().toLowerCase();
    let statusKey = "unknown";

    if (isNumeric) {
      if (numericValue >= 70) {
        statusKey = "good";
      } else if (numericValue >= 35) {
        statusKey = "warning";
      } else if (numericValue > 0) {
        statusKey = "replace_soon";
      } else {
        statusKey = "replace_now";
      }
    } else if (["full", "high", "good", "ok", "normal"].includes(normalized)) {
      statusKey = "good";
    } else if (["medium", "mid"].includes(normalized)) {
      statusKey = "warning";
    } else if (["low", "empty", "none"].includes(normalized)) {
      statusKey = "replace_soon";
    }

    const statusLabel = isNumeric
      ? (numericValue >= 70
          ? "High"
          : numericValue >= 35
            ? "Medium"
            : numericValue > 0
              ? "Low"
              : "Empty")
      : (String(stationWaterLabel ?? "").trim() || this._formatMaintenanceStatus(statusKey));
    const fillPercent = isNumeric
      ? Math.max(0, Math.min(100, numericValue))
      : (
          statusKey === "good" ? 100 :
          statusKey === "warning" ? 55 :
          statusKey === "replace_soon" ? 20 : 0
        );

    return `
      <article
        class="evcc-maintenance-card evcc-maintenance-card--status-${this.escapeHtml(statusKey)}"
        style="--maintenance-remaining:${fillPercent}%;"
      >
        <div class="evcc-maintenance-card-header">
          <div class="evcc-maintenance-card-title">Station Water</div>
          <div class="evcc-maintenance-card-status">${this.escapeHtml(statusLabel)}</div>
        </div>

        <div class="evcc-maintenance-card-value">
          ${this.escapeHtml(rawValue)}
        </div>

        <div class="evcc-maintenance-card-detail">
          Base station water reservoir status
        </div>

        ${Number.isFinite(Number(availableCleanTankMl)) ? `
          <div class="evcc-maintenance-card-secondary">
            ~${this.escapeHtml(String(Math.round(Number(availableCleanTankMl))))} ml remaining
          </div>
        ` : ""}
      </article>
    `;
  };

  /* =========================================================
     ITEM MODAL
     ========================================================= */

  /**
   * Render the maintenance item detail modal with guide steps, notes,
   * the user-adjustable interval editor (maintenance items only), and
   * reset flow.
   *
   * The interval editor surfaces the adapter-declared default/max bounds
   * (default_interval_hours / max_interval_hours on the item) so the
   * input can validate before submitting through
   * eufy_vacuum.set_maintenance_interval.
   *
   * @param {object} ctx - Render context containing `state`.
   * @returns {string} HTML string, or empty string if no modal item is active.
   */
  proto.renderMaintenanceItemModal = function (ctx) {
    const state = ctx?.state;
    const item = state?.activeMaintenanceModalItem?.();
    if (!item) return "";

    const name = item?.label ?? item?.component_label ?? item?.name ?? item?.title ?? "Item details";
    const kind = String(item?.kind ?? "maintenance");
    const statusKey = String(item?.status ?? "unknown");
    const status = item?.status_label ?? this._formatMaintenanceStatus(statusKey);
    const primaryValue = this._maintenancePrimaryValue(item);
    const secondaryValue = this._maintenanceSecondaryValue(item);
    const guide = item?.guide?.display ?? null;
    const guideSteps = Array.isArray(guide?.steps) ? guide.steps.filter(Boolean) : [];
    const guideNotes = Array.isArray(guide?.notes) ? guide.notes.filter(Boolean) : [];
    const resetUi = state?.maintenanceResetUi?.() ?? {};
    const canInvokeReset = state?.canInvokeMaintenanceReset?.(item) ?? false;
    const resetKind = String(item?.reset_kind ?? "").trim().toLowerCase();
    const resetPending = Boolean(resetUi?.pending);
    const resetConfirming = Boolean(resetUi?.confirming);
    const resetSuccess = String(resetUi?.success ?? "");
    const resetError = String(resetUi?.error ?? "");
    return `
      <div class="evcc-modal-backdrop" data-action="close-maintenance-modal">
        <div class="evcc-modal evcc-maintenance-modal" data-stop-propagation>
          <div class="evcc-modal-header">
            <div class="evcc-modal-title">${this.escapeHtml(name)}</div>
            <button
              type="button"
              class="evcc-chip evcc-chip--icon"
              data-action="close-maintenance-modal"
              title="Close"
            >X</button>
          </div>

          <div class="evcc-modal-body">
            <div class="evcc-maintenance-modal-hero evcc-maintenance-modal-hero--status-${this.escapeHtml(statusKey)}">
              <div class="evcc-maintenance-modal-hero-top">
                <div class="evcc-maintenance-modal-hero-label">${this.escapeHtml(item?.kind_label ?? this._formatMaintenanceKind(kind))}</div>
                <div class="evcc-maintenance-modal-hero-status">${this.escapeHtml(status)}</div>
              </div>

              <div class="evcc-maintenance-modal-hero-value">${this.escapeHtml(primaryValue)}</div>

              ${secondaryValue ? `
                <div class="evcc-maintenance-modal-hero-detail">${this.escapeHtml(secondaryValue)}</div>
              ` : ""}
            </div>

            ${guideSteps.length ? `
              <div class="evcc-editor-field-group">
                <div class="evcc-field-label">Steps</div>
                <ol class="evcc-maintenance-guide-list">
                  ${guideSteps.map((step) => `
                    <li class="evcc-maintenance-guide-item">${this.escapeHtml(step)}</li>
                  `).join("")}
                </ol>
              </div>
            ` : `
              <div class="evcc-maintenance-empty">No model-aware steps were provided for this item.</div>
            `}

            ${guideNotes.length ? `
              <div class="evcc-editor-field-group">
                <div class="evcc-field-label">Notes</div>
                <div class="evcc-maintenance-guide-notes">
                  ${guideNotes.map((note) => `
                    <div class="evcc-maintenance-guide-note">${this.escapeHtml(note)}</div>
                  `).join("")}
                </div>
              </div>
            ` : ""}

            ${kind === "maintenance" ? (() => {
              const currentInterval = Number(item?.interval_hours);
              const defaultInterval = Number(item?.default_interval_hours);
              const maxInterval = Number(item?.max_interval_hours);
              const vacuumEntityId = item?.reset_service_data?.vacuum_entity_id ?? "";
              const compKey = item?.component ?? "";
              const inputValue = Number.isFinite(currentInterval) && currentInterval > 0
                ? currentInterval
                : (Number.isFinite(defaultInterval) ? defaultInterval : "");
              const hintParts = [];
              if (Number.isFinite(defaultInterval) && defaultInterval > 0) hintParts.push(`Default ${defaultInterval}h`);
              if (Number.isFinite(maxInterval) && maxInterval > 0) hintParts.push(`Max ${maxInterval}h`);
              return `
                <div class="evcc-editor-field-group">
                  <div class="evcc-field-label">Interval</div>
                  <div class="evcc-maintenance-interval-row">
                    <input
                      type="number"
                      class="evcc-maintenance-interval-input"
                      data-role="maintenance-interval-input"
                      min="1"
                      ${Number.isFinite(maxInterval) && maxInterval > 0 ? `max="${maxInterval}"` : ""}
                      step="0.5"
                      value="${this.escapeHtml(String(inputValue))}"
                      data-default="${this.escapeHtml(String(defaultInterval || 0))}"
                      data-vacuum-entity-id="${this.escapeHtml(String(vacuumEntityId))}"
                      data-component="${this.escapeHtml(String(compKey))}"
                    />
                    <span class="evcc-maintenance-interval-unit">hours</span>
                    <button
                      type="button"
                      class="evcc-chip evcc-chip--save"
                      data-action="save-maintenance-interval"
                    >Save</button>
                    ${Number.isFinite(defaultInterval) && defaultInterval > 0 ? `
                      <button
                        type="button"
                        class="evcc-chip"
                        data-action="reset-maintenance-interval-default"
                        title="Restore manufacturer default (${defaultInterval}h)"
                      >Default</button>
                    ` : ""}
                  </div>
                  ${hintParts.length ? `
                    <div class="evcc-maintenance-interval-hint">${this.escapeHtml(hintParts.join(" · "))}</div>
                  ` : ""}
                </div>
              `;
            })() : ""}

            ${canInvokeReset ? `
              <div class="evcc-editor-field-group">
                <div class="evcc-field-label">Reset</div>

                ${resetSuccess ? `
                  <div class="evcc-maintenance-reset-hint evcc-maintenance-reset-hint--success">
                    ${this.escapeHtml(resetSuccess)}
                  </div>
                ` : ""}

                ${resetError ? `
                  <div class="evcc-maintenance-reset-hint evcc-maintenance-reset-hint--error">
                    ${this.escapeHtml(resetError)}
                  </div>
                ` : ""}

                ${resetConfirming ? `
                  <div class="evcc-maintenance-reset-hint">
                    ${this.escapeHtml(
                      resetKind === "integration"
                        ? `This will reset the tracked maintenance interval for ${name}.`
                        : `This will send the reset command to the device for ${name}.`
                    )}
                  </div>

                  <div class="evcc-maintenance-reset-actions">
                    <button
                      type="button"
                      class="evcc-chip"
                      data-action="cancel-maintenance-reset"
                      ${resetPending ? "disabled" : ""}
                    >Cancel</button>

                    <button
                      type="button"
                      class="evcc-chip evcc-chip--save"
                      data-action="confirm-maintenance-reset"
                      ${resetPending ? "disabled" : ""}
                    >${resetPending ? "Resetting..." : "Confirm Reset"}</button>
                  </div>
                ` : `
                  <div class="evcc-maintenance-reset-actions">
                    <button
                      type="button"
                      class="evcc-chip"
                      data-action="begin-maintenance-reset"
                      title="${this.escapeHtml(
                        resetKind === "integration"
                          ? "Reset this tracked maintenance interval and refresh the dashboard snapshot."
                          : "Send the reset command to the device for this replacement item."
                      )}"
                      ${resetPending ? "disabled" : ""}
                    >Reset</button>
                  </div>
                `}
              </div>
            ` : ""}
          </div>

          <div class="evcc-modal-footer">
            <button
              type="button"
              class="evcc-chip"
              data-action="close-maintenance-modal"
            >Close</button>
          </div>
        </div>
      </div>
    `;
  };

  /* =========================================================
     PREDICATES / VALUE HELPERS
     ========================================================= */

  /**
   * Return true if the item should appear in the Needs Attention list.
   *
   * PURPOSE: Consolidates multiple backend flag conventions into a single boolean.
   * RULES: Explicit flags (needs_attention, overdue, due, warning) take precedence;
   *        remaining_percent ≤ 20 also qualifies as needing attention.
   *
   * @param {object} item - Maintenance or replacement item.
   * @returns {boolean}
   */
  proto._maintenanceItemNeedsAttention = function (item) {
    if (!item || typeof item !== "object") return false;

    if (item.needs_attention === true) return true;
    if (item.attention_required === true) return true;
    if (item.warning === true) return true;
    if (item.overdue === true) return true;
    if (item.due === true) return true;

    const status = String(item?.status ?? "").trim().toLowerCase();

    if ([
      "warning",
      "replace_soon",
      "replace_now",
    ].includes(status)) {
      return true;
    }

    const remainingPercent = Number(item.remaining_percent);
    if (Number.isFinite(remainingPercent) && remainingPercent <= 20) {
      return true;
    }

    return false;
  };

  /**
   * Derive a remaining-life percentage from item fields.
   * Falls back to calculating from remaining/interval or max-life hours.
   *
   * @param {object} item - Maintenance or replacement item.
   * @returns {number|null} Percentage 0–100, or null if indeterminate.
   */
  proto._maintenanceRemainingPercent = function (item) {
    const explicitPercent = Number(item?.remaining_percent);
    if (Number.isFinite(explicitPercent)) return explicitPercent;

    const remainingHours = Number(item?.remaining_hours);
    const maxHours = Number(
      item?.kind === "replacement"
        ? (item?.max_life_hours ?? item?.total_life_hours)
        : item?.interval_hours
    );

    if (Number.isFinite(remainingHours) && Number.isFinite(maxHours) && maxHours > 0) {
      return (remainingHours / maxHours) * 100;
    }

    return null;
  };

  /**
   * Derive the primary display value for an item card (percent, hours, or raw remaining).
   *
   * @param {object} item - Maintenance or replacement item.
   * @returns {string} Human-readable primary value string.
   */
  proto._maintenancePrimaryValue = function (item) {
    const explicitSummary = String(item?.remaining_summary ?? "").trim();
    if (explicitSummary) {
      return explicitSummary;
    }

    const percent = this._maintenanceRemainingPercent(item);
    if (Number.isFinite(percent)) {
      return `${Math.round(percent)}% remaining`;
    }

    const remainingHours = Number(item?.remaining_hours);
    if (Number.isFinite(remainingHours)) {
      return `${this._formatMaintenanceHours(remainingHours)} remaining`;
    }

    const rawValue = item?.remaining_value;
    const rawUnit = item?.remaining_unit;
    if (rawValue != null) {
      return [rawValue, rawUnit].filter(Boolean).join(" ");
    }

    return "Unknown remaining life";
  };

  /**
   * Derive the secondary display value for an item card (usage or remaining detail).
   *
   * @param {object} item - Maintenance or replacement item.
   * @returns {string} Human-readable secondary string, or empty string if unavailable.
   */
  proto._maintenanceSecondaryValue = function (item) {
    const explicitSummary = String(item?.usage_summary ?? "").trim();
    if (explicitSummary) {
      return explicitSummary;
    }

    if (item?.kind === "replacement") {
      const usageHours = Number(item?.usage_hours);
      const maxHours = Number(item?.max_life_hours ?? item?.total_life_hours);

      if (Number.isFinite(usageHours) && Number.isFinite(maxHours)) {
        return `${this._formatMaintenanceHours(usageHours)} used of ${this._formatMaintenanceHours(maxHours)}`;
      }
    }

    const remainingHours = Number(item?.remaining_hours);
    const intervalHours = Number(item?.interval_hours);

    if (Number.isFinite(remainingHours) && Number.isFinite(intervalHours)) {
      return `${this._formatMaintenanceHours(remainingHours)} left of ${this._formatMaintenanceHours(intervalHours)}`;
    }

    const usedSinceResetHours = Number(item?.used_since_reset_hours ?? item?.current_usage_hours);
    if (Number.isFinite(usedSinceResetHours)) {
      return `${this._formatMaintenanceHours(usedSinceResetHours)} used since reset`;
    }

    return "";
  };

  /* =========================================================
     FORMATTERS
     ========================================================= */

  /**
   * Format a numeric hour value as "N hour(s)" with singular/plural agreement.
   *
   * @param {*} value - Raw hour count.
   * @returns {string} Formatted hours string.
   */
  proto._formatMaintenanceHours = function (value) {
    const hours = Number(value);
    if (!Number.isFinite(hours)) return "0 hours";
    const normalized = hours.toFixed(1).replace(/\.0$/, "");
    const numeric = Number(normalized);
    const unit = numeric === 1 ? "hour" : "hours";
    return `${normalized} ${unit}`;
  };

  /**
   * Format a frequency key as a title-cased display string.
   *
   * @param {string|null} value - Raw frequency key.
   * @returns {string} Formatted string, or empty string for blank input.
   */
  proto._formatMaintenanceFrequency = function (value) {
    const raw = String(value ?? "").trim();
    if (!raw) return "";

    return raw
      .replace(/[_-]+/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  };

  /**
   * Convert a snake_case kind key to a title-cased display label.
   *
   * @param {string|null} kind - Raw kind key (e.g. "replace_soon").
   * @returns {string} Title-cased label.
   */
  proto._formatMaintenanceKind = function (kind) {
    return String(kind ?? "")
      .replace(/[_-]+/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  };

  /**
   * Convert a status key to a human-readable label, handling known special cases.
   *
   * @param {string|null} status - Raw status key.
   * @returns {string} Display label.
   */
  proto._formatMaintenanceStatus = function (status) {
    const normalized = String(status ?? "").trim().toLowerCase();

    if (normalized === "replace_now") return "Replace Now";
    if (normalized === "replace_soon") return "Replace Soon";
    if (normalized === "warning") return "Warning";
    if (normalized === "good") return "Good";
    if (normalized === "unknown") return "Unknown";

    return this._formatMaintenanceKind(normalized || "unknown");
  };

  /**
   * Format an ISO timestamp for maintenance display (short month, day, hour, minute).
   *
   * @param {string|null} value - ISO timestamp string or null.
   * @returns {string} Formatted timestamp, or empty string.
   */
  proto._formatMaintenanceTimestamp = function (value) {
    return this.formatTimestamp(value, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }, "");
  };
}
