/**
 * ============================================================
 * RENDERERS: RUN PROFILES
 * ============================================================
 *
 * Renders the saved run profile side panel — save, recall, and
 * manage named room-queue setups alongside the Rooms view.
 *
 * ============================================================
 */

/**
 * Mix run profiles renderer methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applyRunProfilesRenderers(proto) {
  /**
   * Render the run profiles companion panel.
   *
   * @param {object} state - Card state accessor.
   * @returns {string} HTML string.
   */
  proto.renderRunProfilesPanel = function (state) {
    const profiles = state.savedRunProfiles?.() ?? [];
    const selected = state.selectedRunProfile?.() ?? null;
    const draft = state.runProfileDraft?.() ?? { name: "", expose_as_button: false };
    const editorOpen = Boolean(state.isRunProfileEditorOpen?.());
    const editorMode = state.runProfileEditorMode?.() ?? "new";

    return `
      <aside class="evcc-run-profiles-panel">
        <div class="evcc-run-profiles-panel-header">
          <div>
            <div class="evcc-run-profiles-title">${this.t("run_profiles.title")}</div>
            <div class="evcc-run-profiles-subtitle">
              ${this.t("run_profiles.subtitle")}
            </div>
          </div>

          <button
            type="button"
            class="evcc-chip evcc-chip--save"
            data-action="open-new-run-profile"
          >${this.t("run_profiles.save_this_setup")}</button>
        </div>

        ${editorOpen ? `
          <div class="evcc-run-profiles-editor">
            <div class="evcc-run-profiles-editor-title">
              ${editorMode === "edit" ? this.t("run_profiles.editor_title_edit") : this.t("run_profiles.editor_title_new")}
            </div>

            <label class="evcc-run-profiles-field">
              <span class="evcc-run-profiles-label">${this.t("run_profiles.name_label")}</span>
              <input
                type="text"
                class="evcc-run-profiles-input"
                value="${this.escapeHtml(draft.name ?? "")}"
                placeholder="${this.t("run_profiles.name_placeholder")}"
                data-run-profile-field="name"
              />
            </label>

            <label class="evcc-run-profiles-toggle">
              <input
                type="checkbox"
                ${draft.expose_as_button ? "checked" : ""}
                data-run-profile-field="expose_as_button"
              />
              <span>${this.t("run_profiles.expose_as_button")}</span>
            </label>

            ${editorMode === "edit" ? this._renderRunProfileStepsEditor(state) : ""}

            <div class="evcc-run-profiles-editor-actions">
              <button
                type="button"
                class="evcc-chip evcc-chip--save"
                data-action="${editorMode === "edit" ? "overwrite-run-profile" : "save-new-run-profile"}"
              >${editorMode === "edit" ? this.t("run_profiles.save_over") : this.t("run_profiles.create_profile")}</button>

              <button
                type="button"
                class="evcc-chip"
                data-action="cancel-run-profile-editor"
              >${this.t("common.cancel")}</button>
            </div>
          </div>
        ` : ""}

        ${profiles.length ? `
          <div class="evcc-run-profiles-list">
            ${profiles.map((profile) => `
              <button
                type="button"
                class="evcc-chip ${selected?.id === profile.id ? "active" : ""}"
                data-action="apply-run-profile"
                data-profile-id="${this.escapeHtml(profile.id)}"
                title="${this.escapeHtml(profile.summary || profile.room_names_label || profile.name)}"
              >${this.escapeHtml(profile.name)}</button>
            `).join("")}
          </div>
        ` : `
          <div class="evcc-run-profiles-empty">
            ${this.t("run_profiles.empty")}
          </div>
        `}

        ${selected ? `
          <div class="evcc-run-profiles-selected">
            <div class="evcc-run-profiles-selected-name">
              ${this.escapeHtml(selected.name)}
            </div>

            <div class="evcc-run-profiles-selected-meta">
              <span>${this.t("run_profiles.room_count", { count: this.escapeHtml(String(selected.room_count || selected.room_ids?.length || 0)) })}</span>
              ${selected.expose_as_button ? `<span>${this.t("run_profiles.exposed_as_button")}</span>` : ""}
            </div>

            ${selected.summary ? `
              <div class="evcc-run-profiles-selected-summary">
                ${this.escapeHtml(selected.summary)}
              </div>
            ` : selected.room_names_label ? `
              <div class="evcc-run-profiles-selected-summary">
                ${this.escapeHtml(selected.room_names_label)}
              </div>
            ` : ""}

            ${selected.has_charge_steps ? this._renderRunProfileStepsSummary(state, selected) : ""}

            <div class="evcc-run-profiles-selected-actions">
              <button
                type="button"
                class="evcc-chip evcc-chip--save"
                data-action="run-run-profile"
                data-profile-id="${this.escapeHtml(selected.id)}"
              >${this.t("run_profiles.run")}</button>

              <button
                type="button"
                class="evcc-chip"
                data-action="edit-run-profile"
                data-profile-id="${this.escapeHtml(selected.id)}"
              >${this.t("common.edit")}</button>

              <button
                type="button"
                class="evcc-chip"
                data-action="delete-run-profile"
                data-profile-id="${this.escapeHtml(selected.id)}"
              >${this.t("common.delete")}</button>
            </div>
          </div>
        ` : ""}
      </aside>
    `;
  };

  /**
   * Render the ordered-steps editor inside the profile editor (edit mode only).
   * Progressive disclosure: a simple profile shows just an "add a charge step"
   * affordance; once engaged it shows the room-group + charge-step list.
   *
   * @param {object} state - Card state accessor.
   * @returns {string} HTML string.
   */
  proto._renderRunProfileStepsEditor = function (state) {
    const steps = state.runProfileDraftSteps?.() ?? [];
    const expanded = Boolean(state.isDraftStepsExpanded?.());
    const rooms = state.getRoomsForActiveMap?.() ?? [];
    const nameById = {};
    rooms.forEach((room) => { nameById[String(room.id)] = room.name; });

    if (!expanded) {
      return `
        <div class="evcc-run-profiles-steps">
          <span class="evcc-run-profiles-label">${this.t("run_profiles.steps_label")}</span>
          <button
            type="button"
            class="evcc-chip evcc-run-profiles-steps-add"
            data-action="add-run-profile-charge"
          >${this.t("run_profiles.add_charge_step")}</button>
          <div class="evcc-run-profiles-steps-hint">${this.t("run_profiles.steps_hint")}</div>
        </div>
      `;
    }

    const lastIndex = steps.length - 1;
    const controls = (i) => `
      <span class="evcc-run-profiles-step-controls">
        <button type="button" class="evcc-run-profiles-step-btn" data-action="move-run-profile-step"
          data-step-index="${i}" data-step-dir="-1" ${i === 0 ? "disabled" : ""}
          title="${this.t("run_profiles.step_move_up")}">↑</button>
        <button type="button" class="evcc-run-profiles-step-btn" data-action="move-run-profile-step"
          data-step-index="${i}" data-step-dir="1" ${i === lastIndex ? "disabled" : ""}
          title="${this.t("run_profiles.step_move_down")}">↓</button>
        <button type="button" class="evcc-run-profiles-step-btn evcc-run-profiles-step-btn--remove"
          data-action="remove-run-profile-step" data-step-index="${i}"
          title="${this.t("run_profiles.step_remove")}">✕</button>
      </span>`;

    const rowsHtml = steps.map((step, i) => {
      if (step.type === "charge_wait") {
        const target = Number(step.target_battery_percent ?? 95);
        return `
          <li class="evcc-run-profiles-step evcc-run-profiles-step--charge">
            <span class="evcc-run-profiles-step-num">${i + 1}</span>
            <span class="evcc-run-profiles-step-body">
              <span class="evcc-run-profiles-step-kind">${this.t("run_profiles.step_charge_to")}</span>
              <input type="number" min="1" max="100" step="1"
                value="${this.escapeHtml(String(target))}"
                class="evcc-run-profiles-charge-input"
                data-run-profile-charge-index="${i}" />
              <span class="evcc-run-profiles-step-pct">%</span>
            </span>
            ${controls(i)}
          </li>`;
      }

      const groupRooms = Array.isArray(step.rooms) ? step.rooms : [];
      const names = groupRooms
        .map((r) => this.escapeHtml(
          nameById[String(r.room_id)] ?? this.t("run_profiles.room_fallback", { id: this.escapeHtml(String(r.room_id)) })
        ))
        .join(", ");
      const modes = new Set(groupRooms.map((r) => r.clean_mode).filter(Boolean));
      const modeHint = modes.size === 1 ? [...modes][0] : null;
      return `
        <li class="evcc-run-profiles-step evcc-run-profiles-step--group">
          <span class="evcc-run-profiles-step-num">${i + 1}</span>
          <span class="evcc-run-profiles-step-body">
            <span class="evcc-run-profiles-step-kind">${this.t("run_profiles.step_clean")}</span>
            <span class="evcc-run-profiles-step-rooms">${names || this.t("run_profiles.step_group_empty")}</span>
            ${modeHint ? `<span class="evcc-run-profiles-step-mode">${this.escapeHtml(modeHint)}</span>` : ""}
          </span>
          ${controls(i)}
        </li>`;
    }).join("");

    return `
      <div class="evcc-run-profiles-steps">
        <span class="evcc-run-profiles-label">${this.t("run_profiles.steps_label")}</span>
        <ol class="evcc-run-profiles-steps-list">${rowsHtml}</ol>
        <div class="evcc-run-profiles-steps-actions">
          <button type="button" class="evcc-chip" data-action="add-run-profile-charge"
          >${this.t("run_profiles.add_charge_step")}</button>
          <button type="button" class="evcc-chip" data-action="capture-run-profile-group"
          >${this.t("run_profiles.capture_group")}</button>
        </div>
        <div class="evcc-run-profiles-steps-hint">${this.t("run_profiles.steps_capture_hint")}</div>
      </div>
    `;
  };

  /**
   * Render a READ-ONLY sequence summary of a stepped profile ("Runs as: Clean Kitchen →
   * Charge to 95% → Clean Kitchen"). Admits the charge step + the true run order so the flat
   * queue's rooms-union view isn't mistaken for the whole run — WITHOUT putting a
   * (battery-dependent, deliberately unmodelled) duration on the charge.
   *
   * @param {object} state - Card state accessor.
   * @param {object} profile - The selected run profile (carries .steps).
   * @returns {string} HTML string.
   */
  proto._renderRunProfileStepsSummary = function (state, profile) {
    const steps = Array.isArray(profile.steps) ? profile.steps : [];
    if (!steps.length) return "";
    const rooms = state.getRoomsForActiveMap?.() ?? [];
    const nameById = {};
    rooms.forEach((room) => { nameById[String(room.id)] = room.name; });

    const items = steps.map((step) => {
      if (step.type === "charge_wait") {
        const target = Number(step.target_battery_percent ?? 95);
        return `
          <li class="evcc-run-profiles-seq-step evcc-run-profiles-seq-step--charge">
            <span class="evcc-run-profiles-seq-icon" aria-hidden="true">⚡</span>${this.t("run_profiles.step_charge_to")} ${this.escapeHtml(String(target))}%
          </li>`;
      }
      const groupRooms = Array.isArray(step.rooms) ? step.rooms : [];
      const names = groupRooms
        .map((r) => this.escapeHtml(
          nameById[String(r.room_id)] ?? this.t("run_profiles.room_fallback", { id: this.escapeHtml(String(r.room_id)) })
        ))
        .join(", ");
      const modes = new Set(groupRooms.map((r) => r.clean_mode).filter(Boolean));
      const modeHint = modes.size === 1 ? [...modes][0] : null;
      return `
        <li class="evcc-run-profiles-seq-step">
          <span class="evcc-run-profiles-seq-kind">${this.t("run_profiles.step_clean")}</span> ${names || this.t("run_profiles.step_group_empty")}${modeHint ? ` <span class="evcc-run-profiles-seq-mode">${this.escapeHtml(modeHint)}</span>` : ""}
        </li>`;
    }).join("");

    return `
      <div class="evcc-run-profiles-sequence">
        <span class="evcc-run-profiles-label">${this.t("run_profiles.runs_as")}</span>
        <ol class="evcc-run-profiles-seq-list">${items}</ol>
      </div>
    `;
  };
}
