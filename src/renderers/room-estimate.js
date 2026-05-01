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
    if (roomEstimate?.intensity_mismatch) notes.push("Estimated from different intensity");
    if (roomEstimate?.source === "default") notes.push("No learned data yet");
    if (Number(roomEstimate?.learning_velocity?.runs_to_high ?? 0) > 0) {
      notes.push(`${roomEstimate.learning_velocity.runs_to_high} runs to reliable`);
    }

    const summaryRows = [
      Number.isFinite(minutes)
        ? { label: "Estimated time", value: this._formatLearningMinutes(minutes) }
        : null,
      etaAt
        ? { label: "Done by", value: this._formatLearningWallClock(etaAt) }
        : null,
      roomEstimate?.source
        ? { label: "Source", value: String(roomEstimate.source) }
        : null,
      Number.isFinite(sampleCount)
        ? { label: "Samples", value: String(sampleCount) }
        : null,
      Number.isFinite(battery)
        ? { label: "Battery", value: String(battery) }
        : null,
    ].filter(Boolean);

    const waterRows = [
      hasEstimatedWater
        ? { label: "Projected water", value: `~${Math.round(estimatedWaterMl)} ml` }
        : null,
      plannedWaterRoom?.clean_mode_label
        ? { label: "Mode", value: String(plannedWaterRoom.clean_mode_label) }
        : plannedWaterRoom?.effective_clean_mode
          ? { label: "Mode", value: String(plannedWaterRoom.effective_clean_mode) }
          : null,
      plannedWaterRoom?.water_level_label
        ? { label: "Water level", value: String(plannedWaterRoom.water_level_label) }
        : plannedWaterRoom?.effective_water_level
          ? { label: "Water level", value: String(plannedWaterRoom.effective_water_level) }
          : null,
    ].filter(Boolean);

    const liveRows = progressSnapshot
      ? [
          { label: "Progress", value: `${Math.max(0, Math.min(100, Number(progressSnapshot.percent ?? 0)))}%` },
          Number.isFinite(progressSnapshot.elapsedMinutes)
            ? { label: "Elapsed", value: this._formatLearningMinutes(progressSnapshot.elapsedMinutes) }
            : null,
          Number.isFinite(progressSnapshot.remainingMinutes)
            ? { label: "Remaining", value: this._formatLearningMinutes(progressSnapshot.remainingMinutes) }
            : null,
        ].filter(Boolean)
      : [];

    const subtitleParts = [];
    if (Number.isFinite(minutes)) subtitleParts.push(this._formatLearningMinutes(minutes));
    if (etaAt) subtitleParts.push(`done by ${this._formatLearningWallClock(etaAt)}`);

    return `
      <div class="evcc-modal-backdrop" data-action="close-room-estimate">
        <div class="evcc-modal evcc-room-estimate-modal" data-stop-propagation>

          <div class="evcc-modal-header">
            <div class="evcc-modal-title-group">
              <div class="evcc-modal-title">${this.escapeHtml(room.name)} Estimate</div>
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
                title="Close"
              >X</button>
            </div>
          </div>

          <div class="evcc-modal-body">
            ${summaryRows.length ? `
              <div class="evcc-room-estimate-section">
                <div class="evcc-field-label">Estimate Summary</div>
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
                <div class="evcc-field-label">Water Projection</div>
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
                <div class="evcc-field-label">Live Progress</div>
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
                <div class="evcc-field-label">Learning Notes</div>
                <div class="evcc-room-estimate-notes">
                  ${notes.map((note) => `
                    <div class="evcc-room-estimate-note">${this.escapeHtml(note)}</div>
                  `).join("")}
                </div>
              </div>
            ` : `
              <div class="evcc-room-estimate-empty">
                No extra estimate notes for this room right now.
              </div>
            `}
          </div>

          <div class="evcc-modal-footer">
            <button
              type="button"
              class="evcc-chip"
              data-action="close-room-estimate"
            >Close</button>
          </div>

        </div>
      </div>
    `;
  };
}
