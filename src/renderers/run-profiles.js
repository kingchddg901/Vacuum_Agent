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
            <div class="evcc-run-profiles-title">Run Profiles</div>
            <div class="evcc-run-profiles-subtitle">
              Save this room setup and reapply it later without rebuilding the queue by hand.
            </div>
          </div>

          <button
            type="button"
            class="evcc-chip evcc-chip--save"
            data-action="open-new-run-profile"
          >Save This Setup</button>
        </div>

        ${editorOpen ? `
          <div class="evcc-run-profiles-editor">
            <div class="evcc-run-profiles-editor-title">
              ${editorMode === "edit" ? "Edit Saved Profile" : "Create Run Profile"}
            </div>

            <label class="evcc-run-profiles-field">
              <span class="evcc-run-profiles-label">Name</span>
              <input
                type="text"
                class="evcc-run-profiles-input"
                value="${this.escapeHtml(draft.name ?? "")}"
                placeholder="Morning Clean"
                data-run-profile-field="name"
              />
            </label>

            <label class="evcc-run-profiles-toggle">
              <input
                type="checkbox"
                ${draft.expose_as_button ? "checked" : ""}
                data-run-profile-field="expose_as_button"
              />
              <span>Expose as Home Assistant Button</span>
            </label>

            <div class="evcc-run-profiles-editor-actions">
              <button
                type="button"
                class="evcc-chip evcc-chip--save"
                data-action="${editorMode === "edit" ? "overwrite-run-profile" : "save-new-run-profile"}"
              >${editorMode === "edit" ? "Save Over Profile" : "Create Profile"}</button>

              <button
                type="button"
                class="evcc-chip"
                data-action="cancel-run-profile-editor"
              >Cancel</button>
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
            No saved profiles yet.
          </div>
        `}

        ${selected ? `
          <div class="evcc-run-profiles-selected">
            <div class="evcc-run-profiles-selected-name">
              ${this.escapeHtml(selected.name)}
            </div>

            <div class="evcc-run-profiles-selected-meta">
              <span>${this.escapeHtml(String(selected.room_count || selected.room_ids?.length || 0))} rooms</span>
              ${selected.expose_as_button ? `<span>· Exposed as button</span>` : ""}
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

            <div class="evcc-run-profiles-selected-actions">
              <button
                type="button"
                class="evcc-chip"
                data-action="edit-run-profile"
                data-profile-id="${this.escapeHtml(selected.id)}"
              >Edit</button>

              <button
                type="button"
                class="evcc-chip"
                data-action="delete-run-profile"
                data-profile-id="${this.escapeHtml(selected.id)}"
              >Delete</button>
            </div>
          </div>
        ` : ""}
      </aside>
    `;
  };
}
