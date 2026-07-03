/**
 * ============================================================
 * RENDERERS: SAVED ZONES
 * ============================================================
 *
 * The saved-zones side panel — named reusable clean regions ("the couch",
 * "the stove"), grouped by the room they're filed under. Collapsible; each row
 * is a multi-select checkbox, and the shared clean-setting selects (Suction /
 * Mode / Intensity / Water) sit up top so "Clean N selected" runs off them —
 * the same device settings the ad-hoc zone clean uses. (Wave 3b — Cut 2.)
 *
 * ============================================================
 */

export function applySavedZonesRenderers(proto) {
  /**
   * Render the saved-zones companion panel.
   *
   * @param {object} state - Card state accessor.
   * @returns {string} HTML string.
   */
  proto.renderSavedZonesPanel = function (state) {
    const groups = state.savedZonesGrouped?.() ?? [];
    const total = groups.reduce((n, g) => n + g.zones.length, 0);
    const collapsed = state.savedZonesCollapsed?.() ?? false;
    const selCount = state.selectedSavedZoneCount?.() ?? 0;
    const zoneMax = state.zoneMax?.() ?? 10;
    const overCap = selCount > zoneMax;

    const header = `
      <div class="evcc-saved-zones-header" data-action="toggle-saved-zones-collapse"
           role="button" tabindex="0" aria-expanded="${!collapsed}">
        <div class="evcc-saved-zones-header-text">
          <div class="evcc-saved-zones-title">${this.t("saved_zones.title")}</div>
          <div class="evcc-saved-zones-subtitle">${this.t("saved_zones.subtitle")}</div>
        </div>
        ${selCount
          ? `<span class="evcc-saved-zones-selbadge">${this.t("saved_zones.selected_badge", { count: selCount })}</span>`
          : ""}
        <span class="evcc-saved-zones-chevron ${collapsed ? "is-collapsed" : ""}" aria-hidden="true">▾</span>
      </div>`;

    if (collapsed) {
      return `<aside class="evcc-saved-zones-panel is-collapsed">${header}</aside>`;
    }

    // Draw-to-save (Cut 3): while a save-draw is active, a banner drives the map drag ->
    // "Save zone"; otherwise a "+ Draw a zone" button (only over a live map — you draw on it).
    const drawing = (state.zoneDrawMode?.() ?? false) && (state.zoneDrawPurpose?.() === "save");
    const canDraw = state.canDrawZone?.() ?? false;
    const drawCount = state.zoneCount?.() ?? 0;
    const drawUi = drawing
      ? `
        <div class="evcc-saved-zones-draw">
          <div class="evcc-saved-zones-draw-hint">${this.t("saved_zones.draw_hint")}</div>
          <div class="evcc-saved-zones-draw-actions">
            <button type="button" class="evcc-chip evcc-chip--save"
                    data-action="save-drawn-zone"${drawCount === 0 ? " disabled" : ""}>${this.t("saved_zones.save_drawn")}</button>
            <button type="button" class="evcc-chip" data-action="cancel-draw-saved-zone">${this.t("saved_zones.cancel_draw")}</button>
          </div>
        </div>`
      : (canDraw
          ? `<button type="button" class="evcc-chip evcc-saved-zones-drawbtn" data-action="draw-saved-zone">${this.t("saved_zones.draw")}</button>`
          : "");

    // Re-file picker (Cut 4): the rooms on the active map + an Unassigned option; changing it
    // moves the zone to another room's group. room_number is matched against room_id (same
    // space savedZonesGrouped uses).
    const rooms = state.getRoomsForActiveMap?.() ?? [];
    const roomOptions = (roomNumber) => {
      const cur = roomNumber == null ? "" : String(roomNumber);
      return `<option value=""${cur === "" ? " selected" : ""}>${this.t("saved_zones.unassigned")}</option>`
        + rooms.map((r) => {
          const val = this.escapeHtml(String(r.room_id));
          return `<option value="${val}"${String(r.room_id) === cur ? " selected" : ""}>${this.escapeHtml(r.name)}</option>`;
        }).join("");
    };

    const listInner = groups.map((group) => `
      <div class="evcc-saved-zones-room-group">
        <div class="evcc-saved-zones-room-header">
          ${group.room_id == null
            ? this.t("saved_zones.unassigned")
            : this.escapeHtml(group.name)}
        </div>
        ${group.zones.map((zone) => {
          const sel = state.isSavedZoneSelected?.(zone.id) ?? false;
          const zid = this.escapeHtml(zone.id);
          return `
          <div class="evcc-saved-zones-item ${sel ? "is-selected" : ""}">
            <label class="evcc-saved-zones-item-main">
              <input type="checkbox" class="evcc-saved-zones-check"
                     data-action="toggle-saved-zone" data-zone-id="${zid}"${sel ? " checked" : ""}
                     aria-label="${this.t("saved_zones.select_zone", { name: this.escapeHtml(zone.name) })}" />
              <span class="evcc-saved-zones-item-name">${this.escapeHtml(zone.name)}</span>
              ${zone.area_m2 != null
                ? `<span class="evcc-saved-zones-area">${this.t("saved_zones.area_m2", { area: this.escapeHtml((Number(zone.area_m2) || 0).toFixed(1)) })}</span>`
                : ""}
            </label>
            <div class="evcc-saved-zones-item-actions">
              <select class="evcc-saved-zones-roomsel" data-action="set-saved-zone-room"
                      data-zone-id="${zid}" aria-label="${this.t("saved_zones.room_select_aria")}">
                ${roomOptions(zone.room_number)}
              </select>
              <button type="button" class="evcc-chip evcc-saved-zones-rename"
                      data-action="rename-saved-zone" data-zone-id="${zid}"
              >${this.t("saved_zones.rename")}</button>
              <button type="button" class="evcc-chip evcc-saved-zones-del"
                      data-action="delete-saved-zone" data-zone-id="${zid}"
              >${this.t("common.delete")}</button>
            </div>
          </div>`;
        }).join("")}
      </div>`).join("");
    const listBlock = total ? `<div class="evcc-saved-zones-list">${listInner}</div>` : "";

    // While drawing-to-save, keep it focused: banner + the existing list (to spot dupes),
    // but drop the clean settings + "Clean N selected" actions (they're for cleaning, not saving).
    if (drawing) {
      return `
        <aside class="evcc-saved-zones-panel">
          ${header}
          ${drawUi}
          ${listBlock}
        </aside>`;
    }

    if (!total) {
      return `
        <aside class="evcc-saved-zones-panel">
          ${header}
          ${drawUi}
          <div class="evcc-saved-zones-empty">${this.t("saved_zones.empty")}</div>
        </aside>`;
    }

    // Shared clean-setting selects (device-level) — a saved-zone clean runs off these,
    // scoped to the "sz-setting" change binding so it doesn't collide with the map panel.
    const settingRows = this._renderZoneSettingRows?.(state, "sz-setting") ?? "";
    const settings = settingRows
      ? `
        <div class="evcc-saved-zones-settings">
          <div class="evcc-saved-zones-section-title">${this.t("map.zone_settings")}
            <span class="evcc-saved-zones-note">${this.t("map.zone_settings_note")}</span></div>
          ${settingRows}
        </div>`
      : "";

    const actions = `
      <div class="evcc-saved-zones-actions">
        <button type="button" class="evcc-chip evcc-chip--save evcc-saved-zones-clean"
                data-action="clean-selected-saved-zones"${selCount === 0 || overCap ? " disabled" : ""}>
          ${selCount
            ? this.t("saved_zones.clean_selected", { count: selCount })
            : this.t("saved_zones.clean_selected_empty")}
        </button>
        ${selCount
          ? `<button type="button" class="evcc-chip" data-action="clear-saved-zone-selection">${this.t("saved_zones.clear")}</button>`
          : ""}
        ${overCap
          ? `<span class="evcc-saved-zones-cap-warn">${this.t("saved_zones.over_cap", { max: zoneMax })}</span>`
          : ""}
      </div>`;

    return `
      <aside class="evcc-saved-zones-panel">
        ${header}
        ${drawUi}
        ${settings}
        ${listBlock}
        ${actions}
      </aside>`;
  };
}
