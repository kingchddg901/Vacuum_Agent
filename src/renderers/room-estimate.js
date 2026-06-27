/**
 * ============================================================
 * RENDERERS: ROOM ESTIMATE MODAL
 * ============================================================
 *
 * Renders the room estimate detail modal — keeps the main
 * estimate panel compact by moving full breakdown here.
 *
 * ============================================================
 */

/**
 * Mix room estimate renderer methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applyRoomEstimateRenderers(proto) {
  /**
   * Render the room estimate detail modal. Returns empty string when closed.
   *
   * @param {{ state: object }} ctx - Render context.
   * @returns {string} HTML string.
   */
  proto.renderRoomEstimateModal = function (ctx) {
    const { state } = ctx;
    if (!state.isRoomEstimateModalOpen?.()) return "";

    const details = state.activeRoomEstimateDetails?.();
    const room = details?.room ?? null;
    if (!room) return "";

    const entry = details.entry ?? null;
    const roomEstimate = details.roomEstimate ?? null;
    const plannedWaterRoom = details.plannedWaterRoom ?? null;
    const progressSnapshot =
      this.card?._learningController?.getRoomProgressSnapshot?.(room.id) ?? null;

    const minutes = Number(entry?.minutes ?? roomEstimate?.minutes);
    const etaAt = entry?.eta_at ?? roomEstimate?.eta_at ?? null;
    const sampleCount = Number(roomEstimate?.sample_count);
    const battery = Number(roomEstimate?.battery);
    const estimatedWaterMl = Number(plannedWaterRoom?.estimated_robot_water_used_ml);
    const hasEstimatedWater = Number.isFinite(estimatedWaterMl);

    const notes = [];
    if (roomEstimate?.intensity_mismatch) notes.push(this.t("room_estimate.note_intensity_mismatch"));
    if (roomEstimate?.source === "default") notes.push(this.t("room_estimate.note_no_learned_data"));
    if (Number(roomEstimate?.learning_velocity?.runs_to_high ?? 0) > 0) {
      notes.push(this.t("room_estimate.note_runs_to_reliable", { count: roomEstimate.learning_velocity.runs_to_high }));
    }

    const summaryRows = [
      Number.isFinite(minutes)
        ? { label: this.t("room_estimate.label_estimated_time"), value: this._formatLearningMinutes(minutes) }
        : null,
      etaAt
        ? { label: this.t("room_estimate.label_done_by"), value: this._formatLearningWallClock(etaAt) }
        : null,
      roomEstimate?.source
        ? { label: this.t("room_estimate.label_source"), value: String(roomEstimate.source) }
        : null,
      Number.isFinite(sampleCount)
        ? { label: this.t("room_estimate.label_samples"), value: String(sampleCount) }
        : null,
      Number.isFinite(battery)
        ? { label: this.t("room_estimate.label_battery"), value: String(battery) }
        : null,
    ].filter(Boolean);

    const waterRows = [
      hasEstimatedWater
        ? { label: this.t("room_estimate.label_projected_water"), value: this.t("room_estimate.water_ml", { ml: Math.round(estimatedWaterMl) }) }
        : null,
      plannedWaterRoom?.clean_mode_label
        ? { label: this.t("room_estimate.label_mode"), value: String(plannedWaterRoom.clean_mode_label) }
        : plannedWaterRoom?.effective_clean_mode
          ? { label: this.t("room_estimate.label_mode"), value: this.tVocabRaw("clean_mode", plannedWaterRoom.effective_clean_mode, plannedWaterRoom.effective_clean_mode) }
          : null,
      plannedWaterRoom?.water_level_label
        ? { label: this.t("room_estimate.label_water_level"), value: String(plannedWaterRoom.water_level_label) }
        : plannedWaterRoom?.effective_water_level
          ? { label: this.t("room_estimate.label_water_level"), value: this.tVocabRaw("water_level", plannedWaterRoom.effective_water_level, plannedWaterRoom.effective_water_level) }
          : null,
    ].filter(Boolean);

    const liveRows = progressSnapshot
      ? [
          { label: this.t("room_estimate.label_progress"), value: `${Math.max(0, Math.min(100, Number(progressSnapshot.percent ?? 0)))}%` },
          Number.isFinite(progressSnapshot.elapsedMinutes)
            ? { label: this.t("room_estimate.label_elapsed"), value: this._formatLearningMinutes(progressSnapshot.elapsedMinutes) }
            : null,
          Number.isFinite(progressSnapshot.remainingMinutes)
            ? { label: this.t("room_estimate.label_remaining"), value: this._formatLearningMinutes(progressSnapshot.remainingMinutes) }
            : null,
        ].filter(Boolean)
      : [];

    const subtitleParts = [];
    if (Number.isFinite(minutes)) subtitleParts.push(this._formatLearningMinutes(minutes));
    if (etaAt) subtitleParts.push(this.t("room_estimate.subtitle_done_by", { time: this._formatLearningWallClock(etaAt) }));

    return `
      <div class="evcc-modal-backdrop" data-action="close-room-estimate">
        <div class="evcc-modal evcc-room-estimate-modal" data-stop-propagation>

          <div class="evcc-modal-header">
            <div class="evcc-modal-title-group">
              <div class="evcc-modal-title">${this.t("room_estimate.modal_title", { name: this.escapeHtml(room.name) })}</div>
              ${subtitleParts.length ? `
                <div class="evcc-room-estimate-subtitle">${this.escapeHtml(subtitleParts.join(" - "))}</div>
              ` : ""}
            </div>

            <div class="evcc-room-estimate-header-actions">
              ${typeof this.renderConfidenceChip === "function" && details.confidenceBreakpoint
                ? this.renderConfidenceChip(
                    details.confidenceBreakpoint,
                    this._learningConfidenceLabel(details.confidenceLabel, "room")
                  )
                : ""}
              <button
                type="button"
                class="evcc-chip evcc-chip--icon"
                data-action="close-room-estimate"
                title="${this.t("common.close")}"
              >X</button>
            </div>
          </div>

          <div class="evcc-modal-body">
            ${summaryRows.length ? `
              <div class="evcc-room-estimate-section">
                <div class="evcc-field-label">${this.t("room_estimate.section_summary")}</div>
                <div class="evcc-room-estimate-grid">
                  ${summaryRows.map((row) => `
                    <div class="evcc-room-estimate-row">
                      <span>${this.escapeHtml(row.label)}</span>
                      <span>${this.escapeHtml(row.value)}</span>
                    </div>
                  `).join("")}
                </div>
              </div>
            ` : ""}

            ${waterRows.length ? `
              <div class="evcc-room-estimate-section">
                <div class="evcc-field-label">${this.t("room_estimate.section_water")}</div>
                <div class="evcc-room-estimate-grid">
                  ${waterRows.map((row) => `
                    <div class="evcc-room-estimate-row">
                      <span>${this.escapeHtml(row.label)}</span>
                      <span>${this.escapeHtml(row.value)}</span>
                    </div>
                  `).join("")}
                </div>
              </div>
            ` : ""}

            ${liveRows.length ? `
              <div class="evcc-room-estimate-section">
                <div class="evcc-field-label">${this.t("room_estimate.section_live")}</div>
                <div class="evcc-room-estimate-grid">
                  ${liveRows.map((row) => `
                    <div class="evcc-room-estimate-row">
                      <span>${this.escapeHtml(row.label)}</span>
                      <span>${this.escapeHtml(row.value)}</span>
                    </div>
                  `).join("")}
                </div>
              </div>
            ` : ""}

            ${notes.length ? `
              <div class="evcc-room-estimate-section">
                <div class="evcc-field-label">${this.t("room_estimate.section_notes")}</div>
                <div class="evcc-room-estimate-notes">
                  ${notes.map((note) => `
                    <div class="evcc-room-estimate-note">${this.escapeHtml(note)}</div>
                  `).join("")}
                </div>
              </div>
            ` : `
              <div class="evcc-room-estimate-empty">
                ${this.t("room_estimate.empty_notes")}
              </div>
            `}
          </div>

          <div class="evcc-modal-footer">
            <button
              type="button"
              class="evcc-chip"
              data-action="close-room-estimate"
            >${this.t("common.close")}</button>
          </div>

        </div>
      </div>
    `;
  };
}
