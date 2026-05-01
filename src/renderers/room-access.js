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
            <div class="evcc-modal-title">${this.escapeHtml(room.name)} Access</div>
            <button
              type="button"
              class="evcc-chip evcc-chip--icon"
              data-action="close-room-access"
              title="Close"
            >✕</button>
          </div>

          <div class="evcc-modal-body">

            <div class="evcc-room-access-section">
              <div class="evcc-field-label">Dock Room</div>
              <div class="evcc-room-access-help">
                The dock room is the origin of the access tree. It has no inbound dependencies.
                Only one room can be the dock room.
              </div>
              <div class="evcc-chips">
                <button
                  type="button"
                  class="evcc-chip ${isDockRoom ? "active" : ""}"
                  data-action="toggle-is-dock-room"
                >${isDockRoom ? "This is the Dock Room" : "Set as Dock Room"}</button>
              </div>
            </div>

            <div class="evcc-room-access-section">
              <div class="evcc-field-label">Rooms Accessed From Here</div>
              <div class="evcc-room-access-help">
                Select the rooms this room unlocks. A room already claimed by another room
                cannot be selected here.
              </div>

              <div class="evcc-chips evcc-room-access-chip-grid">
                ${editableRooms.length
                  ? editableRooms.map((entry) => {
                      const isSelected = selectedIds.has(entry.id);
                      const isAvailable = entry.available !== false;
                      const claimedBy = entry.claimedBy ?? null;
                      const title = claimedBy
                        ? `Already claimed by Room ${claimedBy}`
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
                  : `<span class="evcc-room-access-empty">No other rooms are available on this map.</span>`}
              </div>
            </div>

            ${!isDockRoom ? `
            <div class="evcc-room-access-section">
              <div class="evcc-field-label">Accessed From</div>
              <div class="evcc-room-access-help">
                The room that grants access to this room. Read-only — set from the other room's editor.
              </div>

              <div class="evcc-chips evcc-room-access-chip-grid">
                ${inboundRooms.length
                  ? inboundRooms.map((entry) => `
                      <span
                        class="evcc-chip evcc-room-access-chip evcc-room-access-chip--readonly ${entry.missing ? "evcc-room-access-chip--missing" : ""}"
                      >${this.escapeHtml(entry.name)}</span>
                    `).join("")
                  : `<span class="evcc-room-access-empty">No room grants access here yet.</span>`}
              </div>
            </div>
            ` : ""}

            ${validation.issues?.length ? `
              <div class="evcc-room-access-issues">
                <div class="evcc-field-label">Graph Issues</div>
                <div class="evcc-room-access-issue-list">
                  ${validation.issues.map((issue) => `
                    <div class="evcc-room-access-issue">${this.escapeHtml(issue.message ?? "Invalid room access graph.")}</div>
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
            >Cancel</button>

            <button
              type="button"
              class="evcc-chip evcc-chip--save"
              data-action="save-room-access"
              ${validation.valid ? "" : "disabled"}
            >Save Access</button>
          </div>

        </div>
      </div>
    `;
  };
}
