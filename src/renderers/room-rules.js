/**
 * ============================================================
 * RENDERERS: ROOM RULES
 * ============================================================
 *
 * Renders the Room Rules view — a per-room entity rule editor
 * for configuring blockers and modifiers.
 * Layout: sub-tab strip → rule list ↔ inline rule editor form.
 *
 * ============================================================
 */

const NO_VALUE_OPERATORS = new Set(["is_on", "is_off", "exists", "missing"]);

// Option lists for modifier setting-overrides are read from the
// adapter's vocabulary at render time (state.adapterOptionsFor).
// Each adapter declares what its hardware supports — Eufy declares
// 4 fan speeds, Roborock with Max+ would declare 5, etc. The card
// renders whatever the adapter says is valid for this brand.

/**
 * Mix room rules renderer methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applyRoomRulesRenderers(proto) {

  /* =========================================================
     MAIN VIEW
     ========================================================= */

  proto.renderRoomRulesView = function (ctx) {
    const { state } = ctx;
    const rooms = state.getRoomsForActiveMap?.() ?? [];

    if (!rooms.length) {
      return `
        <div class="evcc-room-rules-view">
          <div class="evcc-empty">${this.t("room_rules.empty")}</div>
        </div>
      `;
    }

    const activeRoom = state.resolvedRoomRulesRoom?.();
    const draft = state.roomRulesDraft?.();
    const draftMode = state.roomRulesDraftMode?.();
    const saveError = state.roomRulesSaveError?.();

    return `
      <div class="evcc-room-rules-view">
        ${this._renderRoomRulesSubtabs(rooms, activeRoom)}
        <div class="evcc-room-rules-content">
          ${activeRoom
            ? (draft
                ? this._renderRuleEditor(state, activeRoom, draft, draftMode, saveError)
                : this._renderRuleList(state, activeRoom))
            : `<div class="evcc-empty">${this.t("room_rules.select_room_above")}</div>`}
        </div>
      </div>
    `;
  };

  /* =========================================================
     SUB-TABS
     ========================================================= */

  proto._renderRoomRulesSubtabs = function (rooms, activeRoom) {
    const sorted = [...rooms].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

    return `
      <div class="evcc-room-rules-subtabs">
        ${sorted.map((room) => {
          const isActive = activeRoom && String(room.id) === String(activeRoom.id);
          const ruleCount = Array.isArray(room.rules) ? room.rules.length : 0;
          return `
            <button
              type="button"
              class="evcc-room-rules-subtab ${isActive ? "active" : ""}"
              data-action="set-room-rules-tab"
              data-room-id="${this.escapeHtml(String(room.id))}"
            >
              ${this.escapeHtml(room.name)}
              ${ruleCount ? `<span class="evcc-room-rules-subtab-count">${ruleCount}</span>` : ""}
            </button>
          `;
        }).join("")}
      </div>
    `;
  };

  /* =========================================================
     RULE LIST
     ========================================================= */

  proto._renderRuleList = function (state, room) {
    const rules = state.roomRulesForRoom?.(room.id) ?? [];

    return `
      <div class="evcc-rule-list">
        ${rules.length
          ? rules.map((rule) => this._renderRuleCard(state, rule)).join("")
          : `<div class="evcc-rule-list-empty">${this.t("room_rules.no_rules_for_room", { name: this.escapeHtml(room.name) })}</div>`}

        <div class="evcc-rule-list-actions">
          <button
            type="button"
            class="evcc-chip evcc-chip--save"
            data-action="open-new-rule"
          >+ ${this.t("room_rules.add_rule")}</button>
        </div>
      </div>
    `;
  };

  proto._renderRuleCard = function (state, rule) {
    const condition = state.ruleConditionSummary?.(rule) ?? "";
    const effect = state.ruleEffectSummary?.(rule) ?? "";
    const label = rule.label || rule.entity_id || this.t("room_rules.unnamed_rule");
    const isBlocker = rule.kind === "blocker";

    return `
      <div class="evcc-rule-card ${!rule.enabled ? "evcc-rule-card--disabled" : ""}">
        <div class="evcc-rule-card-body">
          <span class="evcc-rule-kind-badge evcc-rule-kind-badge--${isBlocker ? "blocker" : "modifier"}">
            ${isBlocker ? this.t("room_rules.kind_blocker") : this.t("room_rules.kind_modifier")}
          </span>

          <div class="evcc-rule-info">
            <div class="evcc-rule-label">${this.escapeHtml(label)}</div>
            ${rule.label ? `<div class="evcc-rule-entity">${this.escapeHtml(rule.entity_id)}</div>` : ""}
            <div class="evcc-rule-condition">${this.escapeHtml(condition)}</div>
            <div class="evcc-rule-effect">${this.escapeHtml(effect)}</div>
            ${(() => {
              const fanOutCount = Array.isArray(rule.fan_out_room_ids)
                ? rule.fan_out_room_ids.length
                : 0;
              if (fanOutCount <= 0) return "";
              const fanOutText = fanOutCount === 1
                ? this.t("room_rules.also_affects_one", { count: fanOutCount })
                : this.t("room_rules.also_affects_many", { count: fanOutCount });
              return `<div class="evcc-rule-fan-out">${fanOutText}</div>`;
            })()}
          </div>

          ${!rule.enabled ? `<span class="evcc-rule-disabled-tag">${this.t("room_rules.disabled")}</span>` : ""}
        </div>

        <div class="evcc-rule-card-actions">
          <button
            type="button"
            class="evcc-chip"
            data-action="edit-rule"
            data-rule-id="${this.escapeHtml(String(rule.id ?? ""))}"
          >${this.t("common.edit")}</button>
          <button
            type="button"
            class="evcc-chip evcc-chip--danger"
            data-action="delete-rule"
            data-rule-id="${this.escapeHtml(String(rule.id ?? ""))}"
          >${this.t("common.delete")}</button>
        </div>
      </div>
    `;
  };

  /* =========================================================
     RULE EDITOR FORM
     ========================================================= */

  proto._renderRuleEditor = function (state, room, draft, draftMode, saveError) {
    const isNew = draftMode === "new";
    const isModifier = draft.kind === "modifier";
    const descriptor = state.ruleEntityDescriptor?.(draft) ?? null;
    const operatorGroups = state.ruleOperatorGroups?.(draft) ?? [];
    const entitySearchResults = state.ruleEntitySearchResults?.(draft.entity_id, 10) ?? [];
    const hideValue = NO_VALUE_OPERATORS.has(draft.operator ?? "");
    const isValid = state.roomRulesDraftIsValid?.() ?? false;

    return `
      <div class="evcc-rule-editor">
        <div class="evcc-rule-editor-header">
          <div class="evcc-rule-editor-title">
            ${isNew
              ? this.t("room_rules.editor_title_new", { name: this.escapeHtml(room.name) })
              : this.t("room_rules.editor_title_edit", { name: this.escapeHtml(room.name) })}
          </div>
        </div>

        <div class="evcc-rule-editor-body">
          <div class="evcc-rule-editor-section">
            <div class="evcc-field-label">${this.t("room_rules.rule_type")}</div>
            <div class="evcc-chips">
              <button
                type="button"
                class="evcc-chip ${draft.kind === "blocker" ? "active" : ""}"
                data-rule-field="kind"
                data-rule-value="blocker"
              >${this.t("room_rules.kind_blocker")}</button>
              <button
                type="button"
                class="evcc-chip ${draft.kind === "modifier" ? "active" : ""}"
                data-rule-field="kind"
                data-rule-value="modifier"
              >${this.t("room_rules.kind_modifier")}</button>
            </div>
            <div class="evcc-rule-editor-help">
              ${draft.kind === "blocker"
                ? this.t("room_rules.help_blocker")
                : this.t("room_rules.help_modifier")}
            </div>
          </div>

          <div class="evcc-rule-editor-section">
            <label class="evcc-field-label" for="rule-label">${this.t("room_rules.label_field")} <span class="evcc-rule-editor-optional">${this.t("room_rules.optional")}</span></label>
            <input
              id="rule-label"
              type="text"
              class="evcc-rule-editor-input"
              placeholder="${this.t("room_rules.label_placeholder")}"
              value="${this.escapeHtml(draft.label ?? "")}"
              data-rule-input="label"
            />
          </div>

          <div class="evcc-rule-editor-section">
            <label class="evcc-field-label" for="rule-entity">${this.t("room_rules.entity_id")}</label>
            <input
              id="rule-entity"
              type="text"
              class="evcc-rule-editor-input ${descriptor?.entityExists ? "" : "evcc-rule-editor-input--error"}"
              placeholder="binary_sensor.front_door"
              value="${this.escapeHtml(draft.entity_id ?? "")}"
              data-rule-input="entity_id"
            />
            ${this._renderRuleEntitySearchResults(draft, entitySearchResults)}
            ${this._renderRuleEntityHelp(descriptor)}
          </div>

          <div class="evcc-rule-editor-section">
            <div class="evcc-field-label">${this.t("room_rules.condition")}</div>
            ${operatorGroups.map((group) => `
              <div class="evcc-rule-operator-group">
                <div class="evcc-rule-operator-group-label">${this.escapeHtml(group.label)}</div>
                <div class="evcc-chips">
                  ${group.operators.map((operator) => `
                    <button
                      type="button"
                      class="evcc-chip ${draft.operator === operator.value ? "active" : ""}"
                      data-rule-field="operator"
                      data-rule-value="${this.escapeHtml(operator.value)}"
                    >${this.escapeHtml(operator.label)}</button>
                  `).join("")}
                </div>
              </div>
            `).join("")}
          </div>

          ${!hideValue ? this._renderRuleValueField(state, draft, descriptor) : ""}

          <div class="evcc-rule-editor-section">
            <div class="evcc-field-label">${this.t("room_rules.enabled")}</div>
            <div class="evcc-chips">
              <button
                type="button"
                class="evcc-chip ${draft.enabled ? "active" : ""}"
                data-rule-field="enabled"
                data-rule-value="true"
              >${this.t("common.yes")}</button>
              <button
                type="button"
                class="evcc-chip ${!draft.enabled ? "active" : ""}"
                data-rule-field="enabled"
                data-rule-value="false"
              >${this.t("common.no")}</button>
            </div>
          </div>

          <div class="evcc-rule-editor-section">
            <label class="evcc-field-label" for="rule-reason">
              ${this.t("room_rules.reason")} <span class="evcc-rule-editor-optional">${this.t("room_rules.optional")}</span>
            </label>
            <input
              id="rule-reason"
              type="text"
              class="evcc-rule-editor-input"
              placeholder="${isModifier ? this.t("room_rules.reason_placeholder_modifier") : this.t("room_rules.reason_placeholder_blocker")}"
              value="${this.escapeHtml(draft.effect?.reason ?? "")}"
              data-rule-input="effect.reason"
            />
          </div>

          ${isModifier ? this._renderModifierChanges(draft, state) : ""}

          ${isModifier ? this._renderRuleFanOutSection(draft, state) : ""}
        </div>

        ${saveError ? `<div class="evcc-rule-editor-save-error">${this.escapeHtml(saveError)}</div>` : ""}

        <div class="evcc-rule-editor-footer">
          <button
            type="button"
            class="evcc-chip"
            data-action="cancel-rule-editor"
          >${this.t("common.cancel")}</button>
          <button
            type="button"
            class="evcc-chip evcc-chip--save"
            data-action="save-rule"
            ${isValid ? "" : "disabled"}
          >${isNew ? this.t("room_rules.add_rule") : this.t("room_rules.save_rule")}</button>
        </div>
      </div>
    `;
  };

  proto._renderRuleEntityHelp = function (descriptor) {
    if (!descriptor?.entityId) {
      return `<div class="evcc-rule-editor-help">${this.t("room_rules.entity_help_choose")}</div>`;
    }

    if (!descriptor.entityExists) {
      return `<div class="evcc-rule-editor-help">${this.t("room_rules.entity_help_unavailable")}</div>`;
    }

    const bits = [
      `${this.escapeHtml(descriptor.entityLabel)}`,
      this.t("room_rules.entity_help_type", { category: this.escapeHtml(descriptor.category) }),
    ];

    if (descriptor.currentState != null) {
      bits.push(this.t("room_rules.entity_help_current", { state: this.escapeHtml(String(descriptor.currentState)) }));
    }

    if (descriptor.unit) {
      bits.push(this.t("room_rules.entity_help_unit", { unit: this.escapeHtml(String(descriptor.unit)) }));
    }

    if (descriptor.category === "enum" && descriptor.options?.length) {
      const optCount = descriptor.options.length;
      bits.push(optCount === 1
        ? this.t("room_rules.entity_help_options_one", { count: optCount })
        : this.t("room_rules.entity_help_options_many", { count: optCount }));
    }

    return `<div class="evcc-rule-editor-help">${bits.join(" • ")}</div>`;
  };

  proto._renderRuleEntitySearchResults = function (draft, results) {
    const query = String(draft?.entity_id ?? "").trim();
    if (query.length < 2) return "";

    if (!results.length) {
      return `<div class="evcc-rule-entity-search-empty">${this.t("room_rules.entity_search_empty")}</div>`;
    }

    return `
      <div class="evcc-rule-entity-search">
        ${results.map((result) => `
          <button
            type="button"
            class="evcc-rule-entity-search-result ${String(draft?.entity_id ?? "") === String(result.entity_id) ? "active" : ""}"
            data-rule-entity-select="${this.escapeHtml(String(result.entity_id))}"
          >
            <span class="evcc-rule-entity-search-title">${this.escapeHtml(result.friendly_name || result.entity_id)}</span>
            <span class="evcc-rule-entity-search-meta">
              ${this.escapeHtml(result.entity_id)}
              ${result.state != null ? ` • ${this.escapeHtml(String(result.state))}` : ""}
            </span>
          </button>
        `).join("")}
      </div>
    `;
  };

  proto._renderRuleValueField = function (state, draft, descriptor) {
    const valueMode = descriptor?.valueModeForOperator?.(draft.operator) ?? "text";
    const value = draft.value;

    if (valueMode === "single-select" && descriptor?.options?.length) {
      return `
        <div class="evcc-rule-editor-section">
          <label class="evcc-field-label" for="rule-value-select">${this.t("room_rules.value")}</label>
          <select
            id="rule-value-select"
            class="evcc-rule-editor-input"
            data-rule-select="value"
          >
            <option value="">${this.t("room_rules.select_a_value")}</option>
            ${descriptor.options.map((option) => `
              <option
                value="${this.escapeHtml(String(option.value))}"
                ${String(value ?? "") === String(option.value) ? "selected" : ""}
              >${this.escapeHtml(option.label)}</option>
            `).join("")}
          </select>
        </div>
      `;
    }

    if (valueMode === "multi-select" && descriptor?.options?.length) {
      const selectedValues = Array.isArray(value) ? value.map(String) : [];
      return `
        <div class="evcc-rule-editor-section">
          <div class="evcc-field-label">${this.t("room_rules.value")}</div>
          <div class="evcc-chips">
            ${descriptor.options.map((option) => `
              <button
                type="button"
                class="evcc-chip ${selectedValues.includes(String(option.value)) ? "active" : ""}"
                data-rule-multivalue="${this.escapeHtml(String(option.value))}"
              >${this.escapeHtml(option.label)}</button>
            `).join("")}
          </div>
          <div class="evcc-rule-editor-help">${this.t("room_rules.value_multi_help")}</div>
        </div>
      `;
    }

    if (valueMode === "number") {
      return `
        <div class="evcc-rule-editor-section">
          <label class="evcc-field-label" for="rule-value-number">${this.t("room_rules.value")}</label>
          <input
            id="rule-value-number"
            type="number"
            class="evcc-rule-editor-input"
            value="${this.escapeHtml(value == null ? "" : String(value))}"
            ${descriptor?.min != null ? `min="${descriptor.min}"` : ""}
            ${descriptor?.max != null ? `max="${descriptor.max}"` : ""}
            ${descriptor?.step != null ? `step="${descriptor.step}"` : ""}
            data-rule-number-input="value"
          />
          ${(descriptor?.unit || descriptor?.min != null || descriptor?.max != null)
            ? `<div class="evcc-rule-editor-help">${[
                descriptor?.unit ? this.t("room_rules.entity_help_unit", { unit: this.escapeHtml(String(descriptor.unit)) }) : null,
                descriptor?.min != null ? this.t("room_rules.help_min", { min: descriptor.min }) : null,
                descriptor?.max != null ? this.t("room_rules.help_max", { max: descriptor.max }) : null,
              ].filter(Boolean).join(" • ")}</div>`
            : ""}
        </div>
      `;
    }

    return `
      <div class="evcc-rule-editor-section">
        <label class="evcc-field-label" for="rule-value">${this.t("room_rules.value")}</label>
        <input
          id="rule-value"
          type="text"
          class="evcc-rule-editor-input"
          placeholder="${draft.operator === "in" || draft.operator === "not_in" ? this.t("room_rules.value_placeholder_list") : this.t("room_rules.value_placeholder_text")}"
          value="${this.escapeHtml(Array.isArray(value) ? value.join(", ") : String(value ?? ""))}"
          data-rule-input="value"
        />
        ${draft.operator === "in" || draft.operator === "not_in"
          ? `<div class="evcc-rule-editor-help">${this.t("room_rules.value_list_help")}</div>`
          : ""}
      </div>
    `;
  };

  /**
   * Render the "Also apply to" multi-select picker for a modifier rule.
   *
   * Each candidate room is rendered as a toggle chip. The chip's active
   * state mirrors membership in draft.fan_out_room_ids; tapping it
   * dispatches data-rule-field="fan_out_room_ids" with the room id as
   * the value. updateRuleDraftField handles the toggle semantics.
   *
   * Hidden when only the rule's own room exists on the map — fan-out
   * needs at least one other room to be meaningful.
   *
   * @param {object} draft - Current rule draft.
   * @param {object} state - Card state accessor.
   * @returns {string} HTML string, or empty when there are no candidates.
   */
  proto._renderRuleFanOutSection = function (draft, state) {
    const candidates = state.availableFanOutTargets?.() ?? [];
    if (!candidates.length) return "";

    const selected = new Set(
      (Array.isArray(draft.fan_out_room_ids) ? draft.fan_out_room_ids : [])
        .map((id) => String(id))
    );

    return `
      <div class="evcc-rule-editor-section">
        <div class="evcc-field-label">${this.t("room_rules.fan_out_label")}</div>
        <div class="evcc-rule-editor-help">
          ${this.t("room_rules.fan_out_help")}
        </div>
        <div class="evcc-chips">
          ${candidates.map((room) => `
            <button
              type="button"
              class="evcc-chip ${selected.has(String(room.id)) ? "active" : ""}"
              data-rule-field="fan_out_room_ids"
              data-rule-value="${this.escapeHtml(String(room.id))}"
            >${this.escapeHtml(room.name)}</button>
          `).join("")}
        </div>
      </div>
    `;
  };

  proto._renderModifierChanges = function (draft, state) {
    const changes = draft.effect?.changes ?? {};

    // chipRow returns "" when the adapter declared no options for this
    // role — keeps brands without a given concept (e.g. Roborock has no
    // clean_intensity) from rendering an empty "Clean Intensity: -" row.
    const chipRow = (label, field, options) => {
      if (!Array.isArray(options) || options.length === 0) return "";
      return `
        <div class="evcc-rule-change-row">
          <div class="evcc-rule-change-label">${this.escapeHtml(label)}</div>
          <div class="evcc-chips">
            <button
              type="button"
              class="evcc-chip evcc-chip--muted ${changes[field] == null ? "active" : ""}"
              data-rule-field="effect.changes.${this.escapeHtml(field)}"
              data-rule-value=""
            >-</button>
            ${options.map((option) => `
              <button
                type="button"
                class="evcc-chip ${changes[field] === option.value ? "active" : ""}"
                data-rule-field="effect.changes.${this.escapeHtml(field)}"
                data-rule-value="${this.escapeHtml(String(option.value))}"
              >${this.escapeHtml(option.label)}</button>
            `).join("")}
          </div>
        </div>
      `;
    };

    // Read each option list from the adapter at render time. The state
    // accessor returns [] when the adapter omits a role, and chipRow
    // hides the row in that case.
    const cleanModeOptions      = state?.adapterOptionsFor?.("clean_mode") ?? [];
    const fanSpeedOptions       = state?.adapterOptionsFor?.("fan_speed") ?? [];
    const waterLevelOptions     = state?.adapterOptionsFor?.("water_level") ?? [];
    const cleanIntensityOptions = state?.adapterOptionsFor?.("clean_intensity") ?? [];

    return `
      <div class="evcc-rule-editor-section">
        <div class="evcc-field-label">${this.t("room_rules.setting_overrides")}</div>
        <div class="evcc-rule-editor-help">
          ${this.t("room_rules.setting_overrides_help")}
        </div>

        ${chipRow(this.t("room_rules.change_clean_mode"), "clean_mode", cleanModeOptions)}
        ${chipRow(this.t("room_rules.change_fan_speed"), "fan_speed", fanSpeedOptions)}
        ${chipRow(this.t("room_rules.change_water_level"), "water_level", waterLevelOptions)}
        ${chipRow(this.t("room_rules.change_clean_intensity"), "clean_intensity", cleanIntensityOptions)}

        <div class="evcc-rule-change-row">
          <div class="evcc-rule-change-label">${this.t("room_rules.change_clean_passes")}</div>
          <div class="evcc-chips">
            <button
              type="button"
              class="evcc-chip evcc-chip--muted ${changes.clean_passes == null ? "active" : ""}"
              data-rule-field="effect.changes.clean_passes"
              data-rule-value=""
            >-</button>
            ${[1, 2].map((count) => `
              <button
                type="button"
                class="evcc-chip ${changes.clean_passes === count ? "active" : ""}"
                data-rule-field="effect.changes.clean_passes"
                data-rule-value="${count}"
              >${count}</button>
            `).join("")}
          </div>
        </div>

        <div class="evcc-rule-change-row">
          <div class="evcc-rule-change-label">${this.t("room_rules.change_edge_mopping")}</div>
          <div class="evcc-chips">
            <button
              type="button"
              class="evcc-chip evcc-chip--muted ${changes.edge_mopping == null ? "active" : ""}"
              data-rule-field="effect.changes.edge_mopping"
              data-rule-value=""
            >-</button>
            <button
              type="button"
              class="evcc-chip ${changes.edge_mopping === true ? "active" : ""}"
              data-rule-field="effect.changes.edge_mopping"
              data-rule-value="true"
            >${this.t("common.on")}</button>
            <button
              type="button"
              class="evcc-chip ${changes.edge_mopping === false ? "active" : ""}"
              data-rule-field="effect.changes.edge_mopping"
              data-rule-value="false"
            >${this.t("common.off")}</button>
          </div>
        </div>
      </div>
    `;
  };
}
