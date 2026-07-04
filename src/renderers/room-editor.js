/**
 * ============================================================
 * RENDERERS: ROOM EDITOR MODAL
 * ============================================================
 *
 * Renders the room editor modal — profile selector, clean mode,
 * suction, water level, intensity, passes, edge mop, and per-room
 * map-color fields. Carpet-locked rooms suppress mop fields and show
 * a notice.
 *
 * ============================================================
 */

import { normalizeHex, roomFillDefault } from "../cards/map-room-color.js";

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
              title="${this.t("common.close")}"
            >✕</button>
          </div>

          ${isCarpet ? `
            <div class="evcc-room-editor-carpet-notice">
              🪵 ${this.t("room_editor.carpet_notice")}
            </div>
          ` : ""}

          <div class="evcc-room-editor-include-row">
            <span class="evcc-room-editor-include-label">${this.t("room_editor.queue_status_label")}</span>
            <button
              type="button"
              class="evcc-chip evcc-chip--toggle-include ${room.enabled ? "active" : ""}"
              data-action="toggle-room"
              data-room-id="${room.id}"
              data-map-id="${this.escapeHtml(room.mapId)}"
              data-enabled="${room.enabled ? "true" : "false"}"
            >${room.enabled ? this.t("room_editor.included") : this.t("room_editor.excluded")}</button>
          </div>

          <div class="evcc-editor-field-groups">

            ${state.supportsRoomProfiles() ? this._renderProfileSelector(state, room, fields) : ""}
            ${this._renderCleanModeField(state, fields)}
            ${this._renderMopStateIndicator(state)}
            ${this._renderSuctionField(state, fields)}
            ${state.showWaterLevel()  ? this._renderWaterLevelField(state, fields)  : ""}
            ${this._renderIntensityField(state, fields)}
            ${this._renderPassesField(fields, state.maxCleanPasses(), state.passesIsGlobal())}
            ${state.showEdgeMopping() ? this._renderEdgeMoppingField(fields) : ""}
            ${this._renderTransitionField(room)}
            ${this._renderRoomColorField(room, fields)}

          </div>

          <div class="evcc-modal-footer">
            <button
              type="button"
              class="evcc-chip"
              data-action="open-room-access"
              data-room-id="${room.id}"
              data-map-id="${this.escapeHtml(room.mapId)}"
            >${this.t("room_editor.access")}</button>

            <button
              type="button"
              class="evcc-chip"
              data-action="close-room-editor"
            >${this.t("common.cancel")}</button>

            <button
              type="button"
              class="evcc-chip evcc-chip--save"
              data-action="save-room-editor"
            >${this.t("common.save")}</button>
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
        <div class="evcc-field-label">${this.t("room_editor.cleaning_profile")}</div>
        <div class="evcc-chips">

          <button
            type="button"
            class="evcc-chip evcc-chip--custom ${isCustom ? "active" : ""}"
            data-field="profile_name"
            data-value="custom"
            ${isCustom ? "disabled" : ""}
          >${this.t("room_editor.custom")}</button>

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
          >${this.t("room_editor.save_as_new")}</button>

          <button
            type="button"
            class="evcc-chip"
            data-action="overwrite-room-profile"
            ${hasCustomProfiles ? "" : "disabled"}
          >${this.t("room_editor.save_over")}</button>

          <button
            type="button"
            class="evcc-chip"
            data-action="rename-room-profile"
            ${currentProfileName && currentProfile && !currentProfileProtected ? "" : "disabled"}
          >${this.t("common.rename")}</button>

          <button
            type="button"
            class="evcc-chip evcc-chip--danger"
            data-action="delete-room-profile"
            ${currentProfileName && currentProfile && !currentProfileProtected ? "" : "disabled"}
          >${this.t("common.delete")}</button>
        </div>

        <div class="evcc-room-profile-meta">
          ${isCustom
            ? this.t("room_editor.meta_custom")
            : currentProfile
              ? (currentProfileProtected
                  ? this.t("room_editor.meta_profile_builtin", { label: this.escapeHtml(currentProfile.label) })
                  : this.t("room_editor.meta_profile_custom", { label: this.escapeHtml(currentProfile.label) }))
              : this.t("room_editor.meta_select")}
        </div>
      </div>
    `;
  };

  /**
   * Clean mode chip row — options declared by the adapter's
   * vocabulary.clean_mode_options. Carpet rooms see only vacuum-only
   * modes (filtered by state layer).
   */
  proto._renderCleanModeField = function (state, fields) {
    const options = state.cleanModeOptions();
    if (options.length === 0) return "";

    return `
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">${this.t("room_editor.cleaning_mode")}</div>
        <div class="evcc-chips">
          ${options.map((opt) => `
            <button
              type="button"
              class="evcc-chip ${fields.clean_mode === opt.value ? "active" : ""}"
              data-field="clean_mode"
              data-value="${this.escapeHtml(opt.value)}"
            >${this.tVocab("clean_mode", opt.value, opt.label)}</button>
          `).join("")}
        </div>
      </div>
    `;
  };

  /**
   * Suction level chip row — options from adapter vocabulary.fan_speed_options.
   */
  proto._renderSuctionField = function (state, fields) {
    const options = state.suctionLevelOptions();
    if (options.length === 0) return "";

    return `
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">${this.t("room_editor.suction_level")}</div>
        <div class="evcc-chips">
          ${options.map((opt) => `
            <button
              type="button"
              class="evcc-chip ${fields.fan_speed === opt.value ? "active" : ""}"
              data-field="fan_speed"
              data-value="${this.escapeHtml(opt.value)}"
            >${this.tVocab("fan_speed", opt.value, opt.label)}</button>
          `).join("")}
        </div>
      </div>
    `;
  };

  /**
   * Water level chip row — only rendered when mop mode is active and
   * room is not carpet. Options from adapter vocabulary.water_level_options.
   * Visibility controlled by state.showWaterLevel().
   */
  proto._renderWaterLevelField = function (state, fields) {
    const options = state.waterLevelOptions();
    if (options.length === 0) return "";

    return `
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">${this.t("room_editor.water_level")}</div>
        <div class="evcc-chips">
          ${options.map((opt) => `
            <button
              type="button"
              class="evcc-chip ${fields.water_level === opt.value ? "active" : ""}"
              data-field="water_level"
              data-value="${this.escapeHtml(opt.value)}"
            >${this.tVocab("water_level", opt.value, opt.label)}</button>
          `).join("")}
        </div>
      </div>
    `;
  };

  /**
   * Cleaning path chip row — options from adapter
   * vocabulary.clean_intensity_options. Brands that don't expose
   * a path/intensity concept declare an empty list and this row hides.
   */
  proto._renderIntensityField = function (state, fields) {
    const options = state.cleanIntensityOptions();
    if (options.length === 0) return "";

    return `
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">${this.t("room_editor.cleaning_path")}</div>
        <div class="evcc-chips">
          ${options.map((opt) => `
            <button
              type="button"
              class="evcc-chip ${fields.clean_intensity === opt.value ? "active" : ""}"
              data-field="clean_intensity"
              data-value="${this.escapeHtml(opt.value)}"
            >${this.tVocab("clean_intensity", opt.value, opt.label)}</button>
          `).join("")}
        </div>
      </div>
    `;
  };

  /**
   * Clean passes — 1..maxPasses chips (adapter dispatch.passes_max; Eufy 2,
   * Roborock 3). Defaults to 2 when the bound is missing. When passes is global
   * (Roborock S6: the robot uses its OWN app-set whole-run pass count and ignores
   * a per-segment repeat — confirmed live), a note warns that the per-room value
   * here may be overridden by the robot. The chips stay interactive (harmless; the
   * batch max-wins path still reads them).
   */
  proto._renderPassesField = function (fields, maxPasses, passesIsGlobal) {
    const max = Math.max(1, Math.trunc(Number(maxPasses)) || 2);
    const chips = [];
    for (let n = 1; n <= max; n += 1) {
      chips.push(`
          <button
            type="button"
            class="evcc-chip ${fields.clean_passes === n ? "active" : ""}"
            data-field="clean_passes"
            data-value="${n}"
          >${this.t("room_editor.pass", { count: n })}</button>`);
    }
    const note = passesIsGlobal
      ? `<div class="evcc-room-editor-field-note">
           ${this.t("room_editor.passes_global_note")}
         </div>`
      : "";
    return `
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">${this.t("room_editor.cleaning_passes")}</div>
        <div class="evcc-chips">${chips.join("")}</div>
        ${note}
      </div>
    `;
  };

  /**
   * Read-only mop-state indicator for tank-driven brands (Roborock: no per-room
   * clean_mode — mopping is whether the water tank is attached). Renders nothing
   * for brands that expose a per-room clean_mode (Eufy: snapshot.mop_active null).
   */
  proto._renderMopStateIndicator = function (state) {
    const mopActive = state.mopActive();
    if (mopActive === null) return "";
    return `
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">${this.t("room_editor.cleaning_mode")}</div>
        <div class="evcc-room-editor-mopstate ${mopActive ? "mopping" : "vacuum"}">
          ${mopActive
            ? this.t("room_editor.mopstate_mopping")
            : this.t("room_editor.mopstate_vacuum")}
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
           ${this.t("room_editor.transition_callout")}
         </div>`
      : "";

    return `
      <div class="evcc-editor-field-group evcc-editor-field-group--transition">
        <div class="evcc-field-label">${this.t("room_editor.transition_space_label")}</div>
        ${callout}
        <div class="evcc-chips">
          <button
            type="button"
            class="evcc-chip ${isTransition ? "active" : ""}"
            data-action="toggle-room-transition"
            data-room-id="${this.escapeHtml(String(room.id))}"
            data-map-id="${this.escapeHtml(String(room.mapId))}"
            data-value="${isTransition ? "false" : "true"}"
          >${isTransition ? this.t("room_editor.transition_is") : this.t("room_editor.transition_mark")}</button>
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
        <div class="evcc-field-label">${this.t("room_editor.edge_mopping")}</div>
        <div class="evcc-chips">
          <button
            type="button"
            class="evcc-chip ${fields.edge_mopping ? "active" : ""}"
            data-field="edge_mopping"
            data-value="true"
          >${this.t("common.on")}</button>
          <button
            type="button"
            class="evcc-chip ${!fields.edge_mopping ? "active" : ""}"
            data-field="edge_mopping"
            data-value="false"
          >${this.t("common.off")}</button>
        </div>
      </div>
    `;
  };

  /**
   * Per-room map fill color override. A native <input type="color"> is the swatch (it opens the
   * OS picker at the input, no positioning hack needed). Buffered in editorFields like the other
   * settings and persisted on Save. With no override the swatch previews the room's default palette
   * slot (by room id, the raster convention) and the picker opens there; a "reset" clears back to
   * the palette. See docs/dev/themeable-map-palette.md.
   */
  proto._renderRoomColorField = function (room, fields) {
    const override = normalizeHex(fields.color);
    const fallback = roomFillDefault(Number(room.id) - 1);   // this room's default palette color
    const inputValue = override || fallback;
    const hasOverride = !!override;
    // When unset, the swatch still previews the room's CURRENT (palette) color so the picker opens
    // there — the --unset class dashes the swatch + mutes the label so it reads as "not a custom
    // pick" rather than an already-set override.
    return `
      <div class="evcc-editor-field-group evcc-editor-field-group--color">
        <div class="evcc-field-label">${this.t("room_editor.color_label")}</div>
        <div class="evcc-room-color-row${hasOverride ? "" : " evcc-room-color-row--unset"}">
          <input
            type="color"
            class="evcc-room-color-input"
            data-room-color-input
            value="${this.escapeHtml(inputValue)}"
            title="${this.t("room_editor.color_pick_title")}"
            aria-label="${this.t("room_editor.color_label")}"
          />
          <span class="evcc-room-color-value">
            ${hasOverride ? this.escapeHtml(override) : this.t("room_editor.color_default")}
          </span>
          ${hasOverride ? `
            <button
              type="button"
              class="evcc-chip evcc-room-color-reset"
              data-action="reset-room-color"
            >${this.t("room_editor.color_reset")}</button>
          ` : ""}
        </div>
      </div>
    `;
  };
}
