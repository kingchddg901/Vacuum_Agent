/**
 * ============================================================
 * RENDERERS: ROOM EDITOR MODAL
 * ============================================================
 *
 * Renders the room editor modal — profile selector, clean mode,
 * suction, water level, intensity, passes, and edge mop fields.
 * Carpet-locked rooms suppress mop fields and show a notice.
 *
 * ============================================================
 */

/**
 * Mix room editor renderer methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applyRoomEditorRenderer(proto) {

  /**
   * Render the full room editor modal (header, fields, footer).
   * Returns empty string when the editor is closed.
   *
   * @param {{ state: object }} ctx - Render context.
   * @returns {string} HTML string.
   */
  proto.renderRoomEditorModal = function (ctx) {
    const { state } = ctx;

    if (!state.isRoomEditorOpen()) return "";

    const room   = state.activeEditorRoom();
    const fields = state.editorFields();
    if (!room || !fields) return "";

    const isCarpet = state.isEditorRoomCarpet();

    return `
      <div class="evcc-modal-backdrop" data-action="close-room-editor">
        <div class="evcc-modal evcc-room-editor-modal" data-stop-propagation>

          <div class="evcc-modal-header">
            <div class="evcc-modal-title">${this.escapeHtml(room.name)}</div>
            <button
              type="button"
              class="evcc-chip evcc-chip--icon"
              data-action="close-room-editor"
              title="Close"
            >✕</button>
          </div>

          ${isCarpet ? `
            <div class="evcc-room-editor-carpet-notice">
              🪵 Carpet room — locked to vacuum-only modes
            </div>
          ` : ""}

          <div class="evcc-room-editor-include-row">
            <span class="evcc-room-editor-include-label">Current queue status:</span>
            <button
              type="button"
              class="evcc-chip evcc-chip--toggle-include ${room.enabled ? "active" : ""}"
              data-action="toggle-room"
              data-room-id="${room.id}"
              data-map-id="${this.escapeHtml(room.mapId)}"
              data-enabled="${room.enabled ? "true" : "false"}"
            >${room.enabled ? "Included" : "Excluded"}</button>
          </div>

          <div class="evcc-editor-field-groups">

            ${this._renderProfileSelector(state, room, fields)}
            ${this._renderCleanModeField(state, fields)}
            ${this._renderSuctionField(state, fields)}
            ${state.showWaterLevel()  ? this._renderWaterLevelField(state, fields)  : ""}
            ${this._renderIntensityField(state, fields)}
            ${this._renderPassesField(fields)}
            ${state.showEdgeMopping() ? this._renderEdgeMoppingField(fields) : ""}
            ${this._renderTransitionField(room)}

          </div>

          <div class="evcc-modal-footer">
            <button
              type="button"
              class="evcc-chip"
              data-action="open-room-access"
              data-room-id="${room.id}"
              data-map-id="${this.escapeHtml(room.mapId)}"
            >Access</button>

            <button
              type="button"
              class="evcc-chip"
              data-action="close-room-editor"
            >Cancel</button>

            <button
              type="button"
              class="evcc-chip evcc-chip--save"
              data-action="save-room-editor"
            >Save</button>
          </div>

        </div>
      </div>
    `;
  };

  /* =========================================================
     FIELD RENDERERS
     ========================================================= */

  /**
   * Profile preset selector.
   * Shows named profiles as chips + a "Custom" chip when diverged.
   */
  proto._renderProfileSelector = function (state, room, fields) {
    const isCustom = state.isCustomProfile();
    const options = state.roomProfilesList?.() ?? [];
    const currentProfileName = state.currentEditorManagedProfileName?.();
    const currentProfile = currentProfileName
      ? state.roomProfileDefinition?.(currentProfileName)
      : null;
    const currentProfileProtected = currentProfileName
      ? state.isProtectedRoomProfile?.(currentProfileName)
      : false;
    const hasCustomProfiles = (state.customRoomProfiles?.() ?? []).length > 0;

    if (options.length === 0) return "";

    return `
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">Cleaning Profile</div>
        <div class="evcc-chips">

          <button
            type="button"
            class="evcc-chip evcc-chip--custom ${isCustom ? "active" : ""}"
            data-field="profile_name"
            data-value="custom"
            ${isCustom ? "disabled" : ""}
          >Custom</button>

          ${options.map((opt) => `
            <button
              type="button"
              class="evcc-chip ${!isCustom && fields.profile_name === opt.name ? "active" : ""}"
              data-field="profile_name"
              data-value="${this.escapeHtml(opt.name)}"
              data-action="apply-profile"
            >${this.escapeHtml(opt.label)}</button>
          `).join("")}

        </div>

        <div class="evcc-room-profile-actions">
          <button
            type="button"
            class="evcc-chip"
            data-action="save-room-profile-as-new"
          >Save as New</button>

          <button
            type="button"
            class="evcc-chip"
            data-action="overwrite-room-profile"
            ${hasCustomProfiles ? "" : "disabled"}
          >Save Over</button>

          <button
            type="button"
            class="evcc-chip"
            data-action="rename-room-profile"
            ${currentProfileName && currentProfile && !currentProfileProtected ? "" : "disabled"}
          >Rename</button>

          <button
            type="button"
            class="evcc-chip evcc-chip--danger"
            data-action="delete-room-profile"
            ${currentProfileName && currentProfile && !currentProfileProtected ? "" : "disabled"}
          >Delete</button>
        </div>

        <div class="evcc-room-profile-meta">
          ${isCustom
            ? "Current room settings are custom and not linked to a saved profile."
            : currentProfile
              ? `${this.escapeHtml(currentProfile.label)} is ${currentProfileProtected ? "built in and read-only" : "a custom reusable profile"}.`
              : "Select a profile to apply reusable room settings."}
        </div>
      </div>
    `;
  };

  /**
   * Clean mode chip row — reads live options from vacuum entity.
   * Carpet rooms see only vacuum-only modes (filtered by state layer).
   */
  proto._renderCleanModeField = function (state, fields) {
    const options = state.cleanModeOptions();
    if (options.length === 0) return "";

    return `
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">Cleaning Mode</div>
        <div class="evcc-chips">
          ${options.map((opt) => `
            <button
              type="button"
              class="evcc-chip ${fields.clean_mode === opt ? "active" : ""}"
              data-field="clean_mode"
              data-value="${this.escapeHtml(opt)}"
            >${this.escapeHtml(opt)}</button>
          `).join("")}
        </div>
      </div>
    `;
  };

  /**
   * Suction level chip row.
   */
  proto._renderSuctionField = function (state, fields) {
    const options = state.suctionLevelOptions();
    if (options.length === 0) return "";

    return `
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">Suction Level</div>
        <div class="evcc-chips">
          ${options.map((opt) => `
            <button
              type="button"
              class="evcc-chip ${fields.fan_speed === opt ? "active" : ""}"
              data-field="fan_speed"
              data-value="${this.escapeHtml(opt)}"
            >${this.escapeHtml(opt)}</button>
          `).join("")}
        </div>
      </div>
    `;
  };

  /**
   * Water level chip row — only rendered when mop mode is active and
   * room is not carpet. Visibility controlled by state.showWaterLevel().
   */
  proto._renderWaterLevelField = function (state, fields) {
    const options = state.waterLevelOptions();
    if (options.length === 0) return "";

    return `
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">Water Level</div>
        <div class="evcc-chips">
          ${options.map((opt) => `
            <button
              type="button"
              class="evcc-chip ${fields.water_level === opt ? "active" : ""}"
              data-field="water_level"
              data-value="${this.escapeHtml(opt)}"
            >${this.escapeHtml(opt)}</button>
          `).join("")}
        </div>
      </div>
    `;
  };

  /**
   * Cleaning path chip row — reads from per-room entity/state layer.
   */
  proto._renderIntensityField = function (state, fields) {
    const options = state.cleanIntensityOptions();
    if (options.length === 0) return "";

    return `
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">Cleaning Path</div>
        <div class="evcc-chips">
          ${options.map((opt) => `
            <button
              type="button"
              class="evcc-chip ${fields.clean_intensity === opt ? "active" : ""}"
              data-field="clean_intensity"
              data-value="${this.escapeHtml(opt)}"
            >${this.escapeHtml(opt)}</button>
          `).join("")}
        </div>
      </div>
    `;
  };

  /**
   * Clean passes — 1 or 2, simple chip pair.
   */
  proto._renderPassesField = function (fields) {
    return `
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">Cleaning Passes</div>
        <div class="evcc-chips">
          <button
            type="button"
            class="evcc-chip ${fields.clean_passes === 1 ? "active" : ""}"
            data-field="clean_passes"
            data-value="1"
          >1 Pass</button>
          <button
            type="button"
            class="evcc-chip ${fields.clean_passes === 2 ? "active" : ""}"
            data-field="clean_passes"
            data-value="2"
          >2 Passes</button>
        </div>
      </div>
    `;
  };

  /**
   * Transition space toggle — immediate save, not buffered in editorFields.
   * Shows a soft callout when backend scoring flagged this room as a candidate.
   */
  proto._renderTransitionField = function (room) {
    const isTransition       = Boolean(room.isTransition       ?? room.is_transition);
    const transitionCandidate = Boolean(room.transitionCandidate ?? room.transition_candidate);

    const callout = transitionCandidate && !isTransition
      ? `<div class="evcc-room-editor-transition-callout">
           Shape analysis suggests this may be a hallway or connecting corridor.
         </div>`
      : "";

    return `
      <div class="evcc-editor-field-group evcc-editor-field-group--transition">
        <div class="evcc-field-label">Transition Space</div>
        ${callout}
        <div class="evcc-chips">
          <button
            type="button"
            class="evcc-chip ${isTransition ? "active" : ""}"
            data-action="toggle-room-transition"
            data-room-id="${this.escapeHtml(String(room.id))}"
            data-map-id="${this.escapeHtml(String(room.mapId))}"
            data-value="${isTransition ? "false" : "true"}"
          >${isTransition ? "Transition Space" : "Mark as Transition"}</button>
        </div>
      </div>
    `;
  };

  /**
   * Edge mopping toggle — only rendered when mop mode is active and
   * room is not carpet. Visibility controlled by state.showEdgeMopping().
   */
  proto._renderEdgeMoppingField = function (fields) {
    return `
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">Edge Mopping</div>
        <div class="evcc-chips">
          <button
            type="button"
            class="evcc-chip ${fields.edge_mopping ? "active" : ""}"
            data-field="edge_mopping"
            data-value="true"
          >On</button>
          <button
            type="button"
            class="evcc-chip ${!fields.edge_mopping ? "active" : ""}"
            data-field="edge_mopping"
            data-value="false"
          >Off</button>
        </div>
      </div>
    `;
  };
}
