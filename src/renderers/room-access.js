/**
 * ============================================================
 * RENDERERS: ROOM ACCESS MODAL
 * ============================================================
 *
 * Renders the room access graph editor modal — outbound links
 * are editable, inbound links are read-only, validation surfaces
 * inline before save.
 *
 * ============================================================
 */

/**
 * Mix room access renderer methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applyRoomAccessRenderers(proto) {
  /**
   * Render the room access editor modal. Returns empty string when closed.
   *
   * @param {{ state: object }} ctx - Render context.
   * @returns {string} HTML string.
   */
  proto.renderRoomAccessModal = function (ctx) {
    const { state } = ctx;

    if (!state.isRoomAccessOpen?.()) return "";

    const room = state.activeAccessRoom?.();
    if (!room) return "";

    const editableRooms = state.accessEditableRooms?.() ?? [];
    const inboundRooms = state.accessInboundRooms?.() ?? [];
    const selectedIds = new Set(state.roomAccessFields?.().grants_access_to ?? []);
    const validation = state.roomAccessValidation?.() ?? { valid: true, issues: [] };
    const saveError = state.roomAccessSaveError?.();

    const isDockRoom = state.roomAccessFields?.().is_dock_room ?? false;

    return `
      <div class="evcc-modal-backdrop" data-action="close-room-access">
        <div class="evcc-modal evcc-room-access-modal" data-stop-propagation>

          <div class="evcc-modal-header">
            <div class="evcc-modal-title">${this.t("room_access.title", { name: this.escapeHtml(room.name) })}</div>
            <button
              type="button"
              class="evcc-chip evcc-chip--icon"
              data-action="close-room-access"
              title="${this.t("common.close")}"
            >✕</button>
          </div>

          <div class="evcc-modal-body">

            <div class="evcc-room-access-section">
              <div class="evcc-field-label">${this.t("room_access.dock_room_label")}</div>
              <div class="evcc-room-access-help">
                ${this.t("room_access.dock_room_help")}
              </div>
              <div class="evcc-chips">
                <button
                  type="button"
                  class="evcc-chip ${isDockRoom ? "active" : ""}"
                  data-action="toggle-is-dock-room"
                >${isDockRoom ? this.t("room_access.is_dock_room") : this.t("room_access.set_dock_room")}</button>
              </div>
            </div>

            <div class="evcc-room-access-section">
              <div class="evcc-field-label">${this.t("room_access.accessed_from_here_label")}</div>
              <div class="evcc-room-access-help">
                ${this.t("room_access.accessed_from_here_help")}
              </div>

              <div class="evcc-chips evcc-room-access-chip-grid">
                ${editableRooms.length
                  ? editableRooms.map((entry) => {
                      const isSelected = selectedIds.has(entry.id);
                      const isAvailable = entry.available !== false;
                      const claimedBy = entry.claimedBy ?? null;
                      const title = claimedBy
                        ? this.t("room_access.claimed_by", { room: claimedBy })
                        : "";
                      return `
                        <button
                          type="button"
                          class="evcc-chip evcc-room-access-chip
                            ${isSelected ? "active" : ""}
                            ${entry.missing ? "evcc-room-access-chip--missing" : ""}
                            ${!isAvailable ? "evcc-room-access-chip--claimed" : ""}"
                          data-action="toggle-room-access-target"
                          data-room-id="${this.escapeHtml(entry.id)}"
                          ${!isAvailable ? "disabled" : ""}
                          ${title ? `title="${this.escapeHtml(title)}"` : ""}
                        >${this.escapeHtml(entry.name)}</button>
                      `;
                    }).join("")
                  : `<span class="evcc-room-access-empty">${this.t("room_access.no_other_rooms")}</span>`}
              </div>
            </div>

            ${!isDockRoom ? `
            <div class="evcc-room-access-section">
              <div class="evcc-field-label">${this.t("room_access.accessed_from_label")}</div>
              <div class="evcc-room-access-help">
                ${this.t("room_access.accessed_from_help")}
              </div>

              <div class="evcc-chips evcc-room-access-chip-grid">
                ${inboundRooms.length
                  ? inboundRooms.map((entry) => `
                      <span
                        class="evcc-chip evcc-room-access-chip evcc-room-access-chip--readonly ${entry.missing ? "evcc-room-access-chip--missing" : ""}"
                      >${this.escapeHtml(entry.name)}</span>
                    `).join("")
                  : `<span class="evcc-room-access-empty">${this.t("room_access.no_inbound")}</span>`}
              </div>
            </div>
            ` : ""}

            ${validation.issues?.length ? `
              <div class="evcc-room-access-issues">
                <div class="evcc-field-label">${this.t("room_access.graph_issues_label")}</div>
                <div class="evcc-room-access-issue-list">
                  ${validation.issues.map((issue) => `
                    <div class="evcc-room-access-issue">${this.escapeHtml(issue.message ?? this.t("room_access.invalid_graph"))}</div>
                  `).join("")}
                </div>
              </div>
            ` : ""}

            ${saveError ? `
              <div class="evcc-room-access-save-error">
                ${this.escapeHtml(saveError)}
              </div>
            ` : ""}

          </div>

          <div class="evcc-modal-footer">
            <button
              type="button"
              class="evcc-chip"
              data-action="close-room-access"
            >${this.t("common.cancel")}</button>

            <button
              type="button"
              class="evcc-chip evcc-chip--save"
              data-action="save-room-access"
              ${validation.valid ? "" : "disabled"}
            >${this.t("room_access.save")}</button>
          </div>

        </div>
      </div>
    `;
  };
}
