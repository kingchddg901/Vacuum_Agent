/**
 * ============================================================
 * RENDERERS: ROOMS
 * ============================================================
 *
 * Renders the Rooms view — action bar, learning overlays, active
 * job strip, room grid, and individual room tiles.
 *
 * ============================================================
 */

/**
 * Mix rooms renderer methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applyRoomsRenderers(proto) {

  /* =========================================================
     RENDER ROOMS VIEW
     ========================================================= */

  proto.renderRoomsView = function (ctx) {
    const { state } = ctx;

    const rooms = state.getRoomsForActiveMap();
    const orderedRooms = this._withCurrentRoomPinned(rooms, state);
    const canStart = state.canStartCleaning();
    const blockedReason = state.startBlockedReason();
    const hasWarning = state.hasStartWarning();
    const enabledCount = state.enabledRoomCount();
    const activeJob = state.activeJobRooms();

    if (rooms.length === 0) {
      return `
        <div class="evcc-rooms-view">
          <div class="evcc-empty">
            No rooms found. Run the discover rooms service to get started.
          </div>
        </div>
      `;
    }

    return `
      <div class="evcc-rooms-view">

        ${this.renderRoomsActionBar(
          canStart,
          blockedReason,
          enabledCount,
          rooms,
          hasWarning
        )}

        ${typeof this.renderLearningSummary === "function" ? this.renderLearningSummary(state) : ""}

        ${typeof this.renderIncompleteRunBanner === "function" ? this.renderIncompleteRunBanner(state) : ""}

        ${typeof this.renderLearningPreJobPanel === "function" ? this.renderLearningPreJobPanel(state) : ""}

        ${typeof this.renderLearningLiveBanner === "function" ? this.renderLearningLiveBanner(state) : ""}

        ${activeJob ? this.renderActiveJobSection(activeJob) : ""}

        ${typeof this.renderLearningProgressList === "function" ? this.renderLearningProgressList(state) : ""}

        ${this._renderOrphanedRoomsPanel(state)}

        <div class="evcc-rooms-workspace">
          <div class="evcc-rooms-main">

            ${this._renderRoomsViewToggle(state)}

            ${state.isMapViewActive?.()
              ? (typeof this.renderMapRoomView === "function"
                  ? this.renderMapRoomView(ctx)
                  : "")
              : `<div class="evcc-room-grid">
                   ${orderedRooms.map((room) => this.renderRoomCard(room, state)).join("")}
                 </div>`}
          </div>

          ${typeof this.renderRunProfilesPanel === "function"
            ? this.renderRunProfilesPanel(state)
            : ""}
        </div>

      </div>
    `;
  };

  /* =========================================================
     VIEW TOGGLE (list / map)
     ========================================================= */

  proto._renderRoomsViewToggle = function (state, ctx) {
    const mapActive = state.isMapViewActive?.() ?? false;

    return `
      <div class="evcc-rooms-view-toggle">
        <button
          class="evcc-rooms-view-toggle-btn${!mapActive ? " active" : ""}"
          data-action="set-map-view"
          data-map-view="false"
          title="List view"
          aria-label="List view"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
            <line x1="5" y1="4" x2="13" y2="4"/>
            <line x1="5" y1="8" x2="13" y2="8"/>
            <line x1="5" y1="12" x2="13" y2="12"/>
            <circle cx="2.5" cy="4" r="1" fill="currentColor" stroke="none"/>
            <circle cx="2.5" cy="8" r="1" fill="currentColor" stroke="none"/>
            <circle cx="2.5" cy="12" r="1" fill="currentColor" stroke="none"/>
          </svg>
        </button>
        <button
          class="evcc-rooms-view-toggle-btn${mapActive ? " active" : ""}"
          data-action="set-map-view"
          data-map-view="true"
          title="Map view"
          aria-label="Map view"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <rect x="2" y="2" width="5" height="5" rx="1"/>
            <rect x="9" y="2" width="5" height="5" rx="1"/>
            <rect x="2" y="9" width="5" height="5" rx="1"/>
            <rect x="9" y="9" width="5" height="5" rx="1"/>
          </svg>
        </button>
        <button
          class="evcc-rooms-view-toggle-btn${(state.roomFloorTextureEnabled?.() ?? true) ? " active" : ""}"
          data-action="room-texture-toggle"
          title="${(state.roomFloorTextureEnabled?.() ?? true) ? "Hide room-card textures" : "Show room-card textures"}"
          aria-label="${(state.roomFloorTextureEnabled?.() ?? true) ? "Hide room-card textures" : "Show room-card textures"}"
          aria-pressed="${(state.roomFloorTextureEnabled?.() ?? true) ? "true" : "false"}"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round">
            <rect x="2.5" y="3.5" width="11" height="9" rx="2"/>
            <path d="M4.5 9.5 L7.5 6.5 M7 11 L11 7 M9.5 11 L12 8.5"/>
          </svg>
        </button>
        ${mapActive ? `
        <button
          class="evcc-rooms-view-toggle-btn evcc-rooms-view-toggle-btn--configure"
          data-action="open-map-config"
          title="Configure map"
          aria-label="Configure map"
        >
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="8" cy="8" r="2.5"/>
            <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41"/>
          </svg>
          Configure
        </button>
        <select
          class="evcc-rooms-animal-select"
          data-action="map-animal-select"
          title="Companion animal"
          aria-label="Companion animal"
        >
          ${(window.AnimalSVG?.list?.() ?? ["cat","dog","raccoon","parrot","snake"]).map((a) => {
            const def     = window.AnimalSVG?.get?.(a);
            const label   = def?.label ?? (a.charAt(0).toUpperCase() + a.slice(1).replace(/_/g, " "));
            const current = state.mapAnimalSelection?.() ?? "cat";
            return `<option value="${a}"${current === a ? " selected" : ""}>${label}</option>`;
          }).join("")}
        </select>
        <input
          type="range"
          class="evcc-rooms-animal-scale"
          data-action="map-animal-scale"
          min="0.5" max="3" step="0.25"
          value="${state.mapAnimalScale?.() ?? 1.0}"
          title="Icon size"
          aria-label="Icon size"
        >
        <button
          class="evcc-rooms-view-toggle-btn${(state.mapAnimalEnabled?.() ?? true) ? " active" : ""}"
          data-action="map-animal-toggle"
          title="${(state.mapAnimalEnabled?.() ?? true) ? "Hide companion" : "Show companion"}"
          aria-label="${(state.mapAnimalEnabled?.() ?? true) ? "Hide companion" : "Show companion"}"
          aria-pressed="${(state.mapAnimalEnabled?.() ?? true) ? "true" : "false"}"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" stroke="none">
            <ellipse cx="8" cy="10.5" rx="3" ry="2.3"/>
            <circle cx="3.8" cy="7" r="1.3"/>
            <circle cx="6.5" cy="4.8" r="1.3"/>
            <circle cx="9.5" cy="4.8" r="1.3"/>
            <circle cx="12.2" cy="7" r="1.3"/>
          </svg>
        </button>
        <button
          class="evcc-rooms-view-toggle-btn${(state.mapFloorTextureEnabled?.() ?? true) ? " active" : ""}"
          data-action="map-texture-toggle"
          title="${(state.mapFloorTextureEnabled?.() ?? true) ? "Hide map textures" : "Show map textures"}"
          aria-label="${(state.mapFloorTextureEnabled?.() ?? true) ? "Hide map textures" : "Show map textures"}"
          aria-pressed="${(state.mapFloorTextureEnabled?.() ?? true) ? "true" : "false"}"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round">
            <rect x="2" y="2" width="12" height="12" rx="1.5"/>
            <path d="M2 6 L6 2 M2 10 L10 2 M2 14 L14 2 M6 14 L14 6 M10 14 L14 10"/>
          </svg>
        </button>` : ""}
      </div>
    `;
  };

  /* =========================================================
     ORPHANED ROOMS PANEL
     =========================================================
     Small inline panel shown when rooms have not been placed
     in the access tree yet (no inbound link, not dock room).
     ========================================================= */

  /**
   * Pin the currently-cleaning room to the top of the list during an
   * active job. Returns the original list untouched when no job is
   * running or no room is currently flagged. Stable for everything
   * else — original order preserved.
   *
   * Bigger win on mobile (small viewport, lots of scroll) but also
   * useful on desktop when the room grid wraps.
   */
  proto._withCurrentRoomPinned = function (rooms, state) {
    if (!Array.isArray(rooms) || rooms.length < 2) return rooms;
    const controller = this.card?._learningController;
    if (!controller?.getRoomProgressSnapshot) return rooms;
    if (!state?.hasActiveRun?.()) return rooms;

    const currentIndex = rooms.findIndex((r) => {
      const snap = controller.getRoomProgressSnapshot(r.id);
      return Boolean(snap?.isCurrent);
    });
    if (currentIndex < 1) return rooms;   // 0 = already first, -1 = none
    const reordered = rooms.slice();
    const [pinned] = reordered.splice(currentIndex, 1);
    reordered.unshift(pinned);
    return reordered;
  };

  proto._renderOrphanedRoomsPanel = function (state) {
    const orphaned = state.orphanedRooms?.() ?? [];
    if (!orphaned.length) return "";

    return `
      <div class="evcc-orphaned-rooms-panel">
        <span class="evcc-orphaned-rooms-label">Access not set</span>
        <div class="evcc-chips evcc-orphaned-rooms-chips">
          ${orphaned.map((room) => `
            <span class="evcc-chip evcc-orphaned-rooms-chip">
              ${this.escapeHtml(room.name)}
            </span>
          `).join("")}
        </div>
      </div>
    `;
  };

  /* =========================================================
     RENDER ACTIVE JOB SECTION
     ========================================================= */

  proto.renderActiveJobSection = function (activeJob) {
    const safeJob = Array.isArray(activeJob) ? activeJob : [];
    if (!safeJob.length) return "";

    return `
      <div class="evcc-active-job">
        <div class="evcc-active-job-header">
          <span class="evcc-active-job-label">Running</span>
          <span class="evcc-active-job-pulse"></span>
        </div>

        <div class="evcc-queue-chips">
          ${safeJob.map((room) => `
            <div class="evcc-queue-chip evcc-queue-chip--active">
              <span class="evcc-queue-chip-order">${this.escapeHtml(room.jobOrder ?? "")}</span>
              <span class="evcc-queue-chip-label">${this.escapeHtml(room.name ?? "")}</span>
            </div>
          `).join("")}
        </div>
      </div>
    `;
  };

  /* =========================================================
     RENDER ROOMS ACTION BAR
     ========================================================= */

  /**
   * Render the primary action bar (start/cancel/pause, select-all, clear queue).
   *
   * @param {boolean} canStart - Whether a clean can be started now.
   * @param {string|null} blockedReason - Human-readable reason why start is blocked.
   * @param {number} enabledCount - Number of rooms currently in the queue.
   * @param {Array<object>} rooms - Full room list for the active map.
   * @param {boolean} hasWarning - Whether a non-blocking start warning is active.
   * @returns {string} HTML string.
   */
proto.renderRoomsActionBar = function (
  canStart,
  blockedReason,
  enabledCount,
  rooms,
  hasWarning
) {
  const countLabel = enabledCount === 1 ? "1 room" : `${enabledCount} rooms`;
  const queueRooms = (Array.isArray(rooms) ? rooms : []).filter((room) => room.enabled);
  const startClass = canStart
    ? (hasWarning ? "evcc-chip--start-warn" : "evcc-chip--start")
    : "disabled";

  const cardState = this.card?._state;
  const learningJobActive = Boolean(cardState?.hasActiveRun?.());
  const progressPercent = Number(
    this.card?._learningController?.getJobProgressPercent?.() ?? 0
  );
  const timeline = Array.isArray(cardState?.learningRoomTimeline?.())
    ? cardState.learningRoomTimeline()
    : [];

  const completedRooms = cardState?.learningCompletedRooms?.() || [];

  const completedSet = new Set(
    completedRooms.map((r) => String(r.room_id))
  );

  const queueEstimatedMinutes = queueRooms.reduce((total, room) => {
    const roomId = String(room.id);
    const entry = timeline.find((t) => String(t.room_id) === roomId);
    const fallbackEstimate = this.card?._state?.roomEstimateForRoom?.(room.id) ?? null;

    const minutes = Number(
      entry?.minutes ??
      fallbackEstimate?.minutes
    );

    return Number.isFinite(minutes) ? total + minutes : total;
  }, 0);

  const plannedEstimateTotal = Number(cardState?.dashboardPlannedJobEstimateTotalMinutes?.());
  const queueEstimateMinutes = Number.isFinite(plannedEstimateTotal) && plannedEstimateTotal > 0
    ? plannedEstimateTotal
    : queueEstimatedMinutes;

  const queueEstimateLabel = queueEstimateMinutes > 0
    ? this._formatLearningDuration(queueEstimateMinutes)
    : null;

  const startConfirmation = cardState?.startConfirmation?.() ?? null;
  const startPreflight = cardState?.startPreflight?.() ?? startConfirmation?.preflight ?? null;
  const startRequiresConfirmation = Boolean(cardState?.startRequiresConfirmation?.());
  const cancelRequiresConfirmation = Boolean(cardState?.cancelRunRequiresConfirmation?.());
  const clearQueueRequiresConfirmation = Boolean(cardState?.clearQueueRequiresConfirmation?.());
  const hasActiveRun = Boolean(cardState?.hasActiveRun?.());
  const canPauseRun = Boolean(cardState?.canPauseRun?.());
  const canResumeRun = Boolean(cardState?.canResumeRun?.());

  const primaryActionLabel = cancelRequiresConfirmation
    ? "Confirm Cancel"
    : hasActiveRun
      ? "Cancel Run"
      : startRequiresConfirmation
        ? "Confirm Start"
        : "Start Cleaning";

  const primaryActionClass = cancelRequiresConfirmation
    ? "evcc-chip--start-warn evcc-chip--confirm-flash"
    : hasActiveRun
      ? "evcc-chip--cancel-run"
      : startRequiresConfirmation
        ? "evcc-chip--start-warn evcc-chip--confirm-flash"
        : startClass;

  const showPrimaryConfirmCancel = startRequiresConfirmation || cancelRequiresConfirmation;

  const blockedRooms = Array.isArray(startPreflight?.blocked_rooms)
    ? startPreflight.blocked_rooms
    : [];

  const modifiedRooms = Array.isArray(startPreflight?.modified_rooms)
    ? startPreflight.modified_rooms
    : [];

  const warnings = Array.isArray(startPreflight?.warnings)
    ? startPreflight.warnings
    : [];

  const mopCarpetWarning = cardState?.startMopCarpetWarning?.() ?? null;
  const orderAdvisory = cardState?.startOrderAdvisory?.() ?? null;
  const strictOrder = cardState?.strictOrder?.() ?? false;

  return `
    <div class="evcc-rooms-action-bar">

      <div class="evcc-rooms-bar-top">
        <div class="evcc-rooms-queue-summary">
          <span class="evcc-rooms-queue-count">${this.escapeHtml(countLabel)}</span>
          <span class="evcc-rooms-queue-label">included</span>
          ${queueEstimateLabel ? `
            <span class="evcc-rooms-queue-label">· ~${this.escapeHtml(queueEstimateLabel)}</span>
          ` : ""}
        </div>

        <div class="evcc-chips">
          <button
            type="button"
            class="evcc-chip ${primaryActionClass}"
            data-action="primary-room-action"
            ${!hasActiveRun && !startRequiresConfirmation && !canStart ? "disabled" : ""}
            title="${this.escapeHtml(blockedReason ?? "")}"
          >${this.escapeHtml(primaryActionLabel)}</button>

          ${hasActiveRun && (canPauseRun || canResumeRun) ? `
            <button
              type="button"
              class="evcc-chip"
              data-action="${canResumeRun ? "resume-run" : "pause-run"}"
            >${canResumeRun ? "Resume" : "Pause"}</button>
          ` : ""}

          <button type="button" class="evcc-chip" data-action="locate-vacuum">
            Locate
          </button>

          <button type="button" class="evcc-chip" data-action="select-all">
            Select All
          </button>

          <button
            type="button"
            class="evcc-chip ${clearQueueRequiresConfirmation ? "evcc-chip--start-warn evcc-chip--confirm-flash" : ""}"
            data-action="clear-queue"
          >${clearQueueRequiresConfirmation ? "Confirm Clear" : "Clear Queue"}</button>
        </div>
      </div>

      ${blockedReason && !canStart ? `
        <div class="evcc-rooms-block-reason">${this.escapeHtml(blockedReason)}</div>
      ` : ""}

      ${cancelRequiresConfirmation ? `
        <div class="evcc-rooms-cancel-warning" role="alert">
          Tap "Confirm Cancel" again to send the vacuum back to the dock,
          or press <strong>Cancel</strong> to keep the job running.
        </div>
      ` : ""}

      ${mopCarpetWarning ? `
        <div class="evcc-rooms-carpet-warning" role="alert">
          ⚠ ${this.escapeHtml(mopCarpetWarning)}
        </div>
      ` : ""}

      ${orderAdvisory ? `
        <div class="evcc-rooms-order-advisory">
          <div class="evcc-rooms-order-advisory-text">
            ${strictOrder
              ? "Strict order ON — rooms will clean one at a time in the order shown (slower: a dock trip between rooms)."
              : this.escapeHtml(orderAdvisory)}
          </div>
          <button
            type="button"
            class="evcc-chip ${strictOrder ? "active" : ""}"
            data-action="toggle-strict-order"
            aria-pressed="${strictOrder ? "true" : "false"}"
          >${strictOrder ? "Strict order: ON" : "Force this exact order"}</button>
        </div>
      ` : ""}

      ${showPrimaryConfirmCancel ? `
        <div class="evcc-rooms-inline-actions">
          <button
            type="button"
            class="evcc-chip"
            data-action="cancel-primary-confirmation"
          >Cancel</button>
        </div>
      ` : ""}

      ${startRequiresConfirmation ? `
        <div class="evcc-start-preflight-panel">
          <div class="evcc-start-preflight-header">Reduced Run Detected</div>

          <div class="evcc-start-preflight-summary">
            <span>${this.escapeHtml(String(startPreflight?.blocked_room_count ?? 0))} blocked</span>
            <span>·</span>
            <span>${this.escapeHtml(String(startPreflight?.included_room_count ?? enabledCount))} included</span>
            ${Number.isFinite(Number(startPreflight?.blocked_expected_minutes)) && Number(startPreflight?.blocked_expected_minutes) > 0 ? `
              <span>·</span>
              <span>~${this.escapeHtml(this._formatLearningDuration(Number(startPreflight.blocked_expected_minutes)))} skipped</span>
            ` : ""}
          </div>

          ${blockedRooms.length ? `
            <div class="evcc-start-preflight-section">
              <div class="evcc-start-preflight-title">Blocked Rooms</div>
              <div class="evcc-start-preflight-list">
                ${blockedRooms.map((room) => `
                  <div class="evcc-start-preflight-item">
                    <span class="evcc-start-preflight-room">${this.escapeHtml(room.name ?? room.room_id ?? "Room")}</span>
                    <span class="evcc-start-preflight-reason">${this.escapeHtml(room.reason ?? "Blocked")}</span>
                  </div>
                `).join("")}
              </div>
            </div>
          ` : ""}

          ${modifiedRooms.length ? `
            <div class="evcc-start-preflight-section">
              <div class="evcc-start-preflight-title">Modified Rooms</div>
              <div class="evcc-start-preflight-list">
                ${modifiedRooms.map((room) => {
                  const changeLabel = Object.keys(room.changes ?? {}).join(", ") || "Settings adjusted";
                  // Fan-out attribution: when this entry was created
                  // purely by a rule fan-out (no direct rule on this
                  // room contributed), the backend flags it with
                  // derived: true and source_* fields. Surface the
                  // source rule name so users see why a room they
                  // didn't author a rule for is being modified.
                  const derivedNote = room.derived && room.source_rule_name
                    ? ` (via ${room.source_room_name ?? "another room"}'s ${room.source_rule_name})`
                    : "";
                  return `
                    <div class="evcc-start-preflight-item">
                      <span class="evcc-start-preflight-room">${this.escapeHtml(room.name ?? room.room_id ?? "Room")}</span>
                      <span class="evcc-start-preflight-reason">${this.escapeHtml(changeLabel + derivedNote)}</span>
                    </div>
                  `;
                }).join("")}
              </div>
            </div>
          ` : ""}

          ${warnings.length ? `
            <div class="evcc-start-preflight-section">
              <div class="evcc-start-preflight-title">Warnings</div>
              <div class="evcc-start-preflight-list">
                ${warnings.map((warning) => `
                  <div class="evcc-start-preflight-item">
                    <span class="evcc-start-preflight-reason">${this.escapeHtml(warning)}</span>
                  </div>
                `).join("")}
              </div>
            </div>
          ` : ""}
        </div>
      ` : ""}

      ${queueRooms.length > 0 ? `
        <div class="evcc-queue-chips">

          ${queueRooms.map((room, index) => {
            const roomId = String(room.id);

            const entry = timeline.find(
              (t) => String(t.room_id) === roomId
            );

            const isCompleted = completedSet.has(roomId);
            const progressSnapshot =
              this.card?._learningController?.getRoomProgressSnapshot?.(room.id) ?? null;

            let stateClass = "evcc-queue-chip--queued";

            if (learningJobActive) {
              if (entry?.completed || isCompleted || progressSnapshot?.isCompleted) {
                stateClass = "evcc-queue-chip--completed";
              } else if (entry?.current || progressSnapshot?.isCurrent) {
                stateClass = "evcc-queue-chip--current";
              } else if (entry?.skipped || progressSnapshot?.isSkipped) {
                stateClass = "evcc-queue-chip--skipped";
              } else if (entry?.remaining || entry) {
                stateClass = "evcc-queue-chip--remaining";
              }
            }

            // running-long: an additive warning modifier on the current chip (the
            // room has run well past its estimate but isn't a 2x stall yet).
            const anomalyClass =
              (entry?.running_long || progressSnapshot?.isRunningLong)
                ? "evcc-queue-chip--running-long"
                : "";

            let confidenceClass = "";

            if (entry?.confidence_breakpoint?.ui_variant) {
              const variant = entry.confidence_breakpoint.ui_variant;
              if (variant === "success") confidenceClass = "evcc-queue-chip--confidence-high";
              else if (variant === "warning") confidenceClass = "evcc-queue-chip--confidence-medium";
              else if (variant === "error") confidenceClass = "evcc-queue-chip--confidence-low";
            }

            const minutes = entry?.minutes != null
              ? this._formatLearningMinutes(entry.minutes)
              : null;

            const chipProgress =
              stateClass === "evcc-queue-chip--completed"
                ? 100
                : stateClass === "evcc-queue-chip--current"
                  ? Number(progressSnapshot?.percent ?? progressPercent)
                  : 0;

            const liveLabel =
              stateClass === "evcc-queue-chip--current"
                ? `${Math.max(0, Math.min(99, Math.floor(chipProgress)))}%`
                : minutes;

            return `
              <button
                type="button"
                class="evcc-queue-chip ${stateClass} ${confidenceClass} ${anomalyClass}"
                data-queue-chip="true"
                data-room-id="${room.id}"
                data-map-id="${this.escapeHtml(room.mapId)}"
                data-enabled="${room.enabled ? "true" : "false"}"
                style="--job-progress:${chipProgress}%;"
                title="Click for settings · Double-click for estimate · Hold to remove from queue"
                aria-label="Queue room ${this.escapeHtml(room.name)}"
              >
                <span class="evcc-queue-chip-order">${index + 1}</span>

                <span class="evcc-queue-chip-label">
                  ${this.escapeHtml(room.name)}
                </span>

                ${liveLabel ? `
                  <span class="evcc-queue-chip-time">
                    ${this.escapeHtml(liveLabel)}
                  </span>
                ` : ""}

              </button>
            `;
          }).join("")}

        </div>
      ` : `
        <div class="evcc-queue-empty">
          No rooms queued — toggle rooms to include them
        </div>
      `}

    </div>
  `;
};

  /* =========================================================
     RENDER ROOM CARD
     ========================================================= */

  /**
   * Render a single room tile with toggle, floor texture, queue position,
   * and settings/order controls.
   *
   * @param {object} room - Room data object from state.
   * @param {object} state - Card state accessor.
   * @returns {string} HTML string.
   */
proto.renderRoomCard = function (room, state) {
  const normalizedRoom = this._normalizeRoomDisplayData(room);

  const modeChip = normalizedRoom.cleanMode
    ? (normalizedRoom.cleanModeLabel || this._formatCleanMode(normalizedRoom.cleanMode))
    : null;

  const isDefaultPower = !normalizedRoom.fanSpeed ||
    ["off", "normal"].includes(String(normalizedRoom.fanSpeed).toLowerCase());
  const powerChip = !isDefaultPower
    ? (normalizedRoom.fanSpeedLabel || this._formatFanSpeed(normalizedRoom.fanSpeed))
    : null;

  const isDefaultPath = !normalizedRoom.cleanIntensity ||
    String(normalizedRoom.cleanIntensity).toLowerCase() === "standard";
  const pathChip = !isDefaultPath
    ? (normalizedRoom.cleanIntensityLabel || this._formatCleanIntensity(normalizedRoom.cleanIntensity))
    : null;

  const waterChip = this._isMopMode(normalizedRoom.cleanMode) &&
    normalizedRoom.waterLevel &&
    String(normalizedRoom.waterLevel).toLowerCase() !== "off"
    ? (normalizedRoom.waterLevelLabel || this._formatWaterLevel(normalizedRoom.waterLevel))
    : null;

  const edgeMopChip = this._isMopMode(normalizedRoom.cleanMode) && normalizedRoom.edgeMopping
    ? "Edge Mop On"
    : null;

  const passesChip = Number(normalizedRoom.cleanPasses) > 1
    ? `${Number(normalizedRoom.cleanPasses)}× passes`
    : null;

  const dragItemId = this.card?._state?.orderDragItemId?.();
  const dragOverItemId = this.card?._state?.orderDragOverItemId?.();

  const dragSourceClass = String(dragItemId) === String(normalizedRoom.id)
    ? "evcc-order-drag-source"
    : "";

  const dragTargetClass = String(dragOverItemId) === String(normalizedRoom.id)
    ? "evcc-order-drag-target"
    : "";

  const roomEstimate = state?.roomEstimateForRoom?.(normalizedRoom.id) ?? null;
  const plannedWaterRoom = state?.dashboardPlannedWaterRoomForRoom?.(
    normalizedRoom.id,
    normalizedRoom.slug
  ) ?? null;

  let estimateChip = "";

  if (roomEstimate && roomEstimate.error == null) {
    const estimateClass = roomEstimate.source === "learned"
      ? "evcc-room-status--estimate-learned"
      : "evcc-room-status--estimate-default";

    const estimateLabel = roomEstimate.source === "learned"
      ? this._formatLearningMinutes(roomEstimate.minutes)
      : `~${this._formatLearningMinutes(roomEstimate.minutes)}`;

    const estimateParts = [
      `Estimate: ${this._formatLearningMinutes(roomEstimate.minutes)}`,
    ];

    if (roomEstimate.source) {
      estimateParts.push(`Source: ${String(roomEstimate.source)}`);
    }

    const estimateBattery = Number(roomEstimate.battery);
    if (Number.isFinite(estimateBattery)) {
      estimateParts.push(`Battery: ${estimateBattery}`);
    }

    const estimateTitle = estimateParts.join(" · ");

    estimateChip = `
      <div
        class="evcc-room-status evcc-room-status--estimate ${estimateClass}"
        title="${this.escapeHtml(estimateTitle)}"
      >
        ${this.escapeHtml(estimateLabel)}
      </div>
    `;
  }

  let confidenceChip = "";
  let roomConfidenceClass = "";
  let plannedWaterChip = "";

  if (roomEstimate && roomEstimate.error == null && typeof this.renderConfidenceChip === "function") {
    if (roomEstimate.source === "learned") {
      const variant = roomEstimate?.confidence_breakpoint?.ui_variant;
      const trustLabel = variant === "success" ? "Reliable"
        : variant === "warning" ? "Learning"
        : variant === "error" ? "Uncertain"
        : null;

      if (trustLabel) {
        confidenceChip = this.renderConfidenceChip(
          roomEstimate.confidence_breakpoint,
          trustLabel,
          trustLabel
        );

        if (variant === "success") roomConfidenceClass = "evcc-room-card--confidence-high";
        else if (variant === "warning") roomConfidenceClass = "evcc-room-card--confidence-medium";
        else roomConfidenceClass = "evcc-room-card--confidence-low";
      }
    } else if (roomEstimate.source === "default") {
      confidenceChip = this.renderConfidenceChip({ ui_variant: "neutral" }, "Unlearned", "Unlearned");
    }
  }

  const plannedWaterEffectiveMode = String(
    plannedWaterRoom?.effective_clean_mode ??
    plannedWaterRoom?.clean_mode ??
    ""
  ).toLowerCase();
  const plannedWaterEffectiveLevel = String(
    plannedWaterRoom?.effective_water_level ??
    plannedWaterRoom?.water_level ??
    ""
  ).toLowerCase();
  const plannedWaterMopActive = Boolean(
    plannedWaterRoom?.mop_active ||
    this._isMopMode(plannedWaterEffectiveMode)
  );

  if (plannedWaterMopActive && plannedWaterEffectiveLevel !== "off") {
    const projectedWaterMl = Number(plannedWaterRoom.estimated_robot_water_used_ml);
    if (Number.isFinite(projectedWaterMl)) {
      plannedWaterChip = `
        <div
          class="evcc-room-status"
          title="${this.escapeHtml(
            [
              `Projected water use: ~${Math.round(projectedWaterMl)} ml`,
              plannedWaterRoom?.clean_mode_label ? `Mode: ${String(plannedWaterRoom.clean_mode_label)}` : plannedWaterRoom?.effective_clean_mode ? `Mode: ${String(plannedWaterRoom.effective_clean_mode)}` : null,
              plannedWaterRoom?.water_level_label ? `Water: ${String(plannedWaterRoom.water_level_label)}` : plannedWaterRoom?.effective_water_level ? `Water: ${String(plannedWaterRoom.effective_water_level)}` : null,
            ].filter(Boolean).join(" · ")
          )}"
        >
          ${this.escapeHtml(`~${Math.round(projectedWaterMl)} ml water`)}
        </div>
      `;
    }
  }

  const notes = [];

  if (roomEstimate?.intensity_mismatch) {
    notes.push({ text: "⚠ intensity mismatch", variant: "warning" });
  }

  const troubleEntry = state?.troubleRoomForRoom?.(normalizedRoom.id) ?? null;
  if (troubleEntry?.is_trouble) {
    const missCount = Number(troubleEntry.miss_count ?? 0);
    const runCount  = Number(troubleEntry.run_count ?? 0);
    const missRate  = Number(troubleEntry.miss_rate ?? 0);
    const pct       = Number.isFinite(missRate) ? Math.round(missRate * 100) : null;
    notes.push({
      text: `⚠ Missed ${missCount}× of ${runCount} run${runCount === 1 ? "" : "s"}${pct !== null ? ` (${pct}%)` : ""}`,
      variant: "warning",
      title: `This room was missed in ${pct ?? "?"}% of recent runs. Consider checking for obstacles or map accuracy.`,
    });
  }

  const learningJobActive = Boolean(this.card?._state?.hasActiveRun?.());
  const progressSnapshot =
    this.card?._learningController?.getRoomProgressSnapshot?.(normalizedRoom.id) ?? null;

  const rawProgress =
    progressSnapshot?.percent ??
    this.card?._learningController?.getRoomProgressPercent?.(normalizedRoom.id);

  const roomProgress = Number.isFinite(rawProgress) ? rawProgress : 0;

  let roomFillClass = "evcc-room-card--queue-idle";

  if (normalizedRoom.enabled && learningJobActive) {
    if (progressSnapshot?.isCompleted || roomProgress >= 100) {
      roomFillClass = "evcc-room-card--queue-completed";
    } else if (progressSnapshot?.isCurrent || roomProgress > 0) {
      roomFillClass = "evcc-room-card--queue-current";
    } else {
      roomFillClass = "evcc-room-card--queue-remaining";
    }
  }

  // "Last cleaned ~Nd ago" pill — pulled from room_history on the
  // switch entity's attributes. Hide while a job is running on this
  // room (the progress chip already covers that case) and when no
  // timestamp is available (fresh install, or never cleaned).
  let lastCleanedChip = "";
  const lastCleanedAgoLabel = this.formatRelativeAgo?.(normalizedRoom.lastCleanedAt);
  if (lastCleanedAgoLabel && !(progressSnapshot?.isCurrent)) {
    const titleParts = [`Last cleaned: ${normalizedRoom.lastCleanedAt}`];
    if (normalizedRoom.lastJobMode) {
      titleParts.push(`Mode: ${String(normalizedRoom.lastJobMode)}`);
    }
    lastCleanedChip = `
      <div
        class="evcc-room-status evcc-room-status--last-cleaned"
        title="${this.escapeHtml(titleParts.join(" | "))}"
      >${this.escapeHtml(lastCleanedAgoLabel)}</div>
    `;
  }

  const progressMeta =
    learningJobActive &&
    progressSnapshot &&
    progressSnapshot.isCurrent
      ? `
        <div class="evcc-room-progress-meta">
          <div
            class="evcc-room-status evcc-room-progress-chip"
            title="${this.escapeHtml(
              [
                `Progress: ${progressSnapshot.percent}%`,
                Number.isFinite(progressSnapshot.elapsedMinutes)
                  ? `Elapsed: ${this._formatLearningMinutes(progressSnapshot.elapsedMinutes)}`
                  : "",
                Number.isFinite(progressSnapshot.remainingMinutes)
                  ? `Remaining: ${this._formatLearningMinutes(progressSnapshot.remainingMinutes)}`
                  : "",
              ].filter(Boolean).join(" · ")
            )}"
          >
            ${this.escapeHtml(`${progressSnapshot.percent}% complete`)}
          </div>

          ${Number.isFinite(progressSnapshot.remainingMinutes) ? `
            <div
              class="evcc-room-status evcc-room-progress-chip evcc-room-progress-chip--remaining"
              title="${this.escapeHtml(
                [
                  `Progress: ${progressSnapshot.percent}%`,
                  Number.isFinite(progressSnapshot.elapsedMinutes)
                    ? `Elapsed: ${this._formatLearningMinutes(progressSnapshot.elapsedMinutes)}`
                    : "",
                  `Remaining: ${this._formatLearningMinutes(progressSnapshot.remainingMinutes)}`,
                ].filter(Boolean).join(" · ")
              )}"
            >
              ${this.escapeHtml(`~${this._formatLearningMinutes(progressSnapshot.remainingMinutes)} left`)}
            </div>
          ` : ""}
        </div>
      `
      : "";

  return `
    <div
      class="evcc-room-card ${normalizedRoom.enabled ? "is-enabled" : "is-disabled"} ${dragSourceClass} ${dragTargetClass} ${roomFillClass} ${roomConfidenceClass}"
      data-room-card-toggle="true"
      data-room-id="${normalizedRoom.id}"
      data-map-id="${this.escapeHtml(normalizedRoom.mapId)}"
      data-enabled="${normalizedRoom.enabled ? "true" : "false"}"
      data-order-drop-target
      data-scope="rooms"
      data-item-id="${normalizedRoom.id}"
      role="button"
      tabindex="0"
      aria-pressed="${normalizedRoom.enabled ? "true" : "false"}"
      aria-label="${this.escapeHtml(`${normalizedRoom.enabled ? "Exclude" : "Include"} room ${normalizedRoom.name}`)}"
      style="--room-progress:${roomProgress}%;"
    >

      ${typeof this._renderFloorTextureLayer === "function"
        ? this._renderFloorTextureLayer(normalizedRoom)
        : ""}

      <div class="evcc-room-row evcc-room-row-1">
        <div class="evcc-room-controls">

          <div class="evcc-order-controls">
            <span class="evcc-order-chip">#${this.escapeHtml(normalizedRoom.order)}</span>

            <button
              type="button"
              class="evcc-chip evcc-order-move-button"
              data-action="open-order-selector"
              data-scope="rooms"
              data-item-id="${normalizedRoom.id}"
              title="Move room"
            >Move</button>

            <button
              type="button"
              class="evcc-chip evcc-chip--icon evcc-order-drag-handle"
              data-order-drag-item
              data-scope="rooms"
              data-item-id="${normalizedRoom.id}"
              draggable="true"
              title="Drag to reorder"
            >⋮⋮</button>
          </div>

          <button
            type="button"
            class="evcc-room-settings-hit-target"
            data-action="open-room-settings"
            data-room-id="${normalizedRoom.id}"
            data-map-id="${this.escapeHtml(normalizedRoom.mapId)}"
            title="Room settings"
            aria-label="Open room settings for ${this.escapeHtml(normalizedRoom.name)}"
          >
            <span class="evcc-chip evcc-chip--icon evcc-room-settings-button">⚙</span>
          </button>
        </div>
      </div>

      <div class="evcc-room-row evcc-room-row-2">
        <div class="evcc-room-name">${this.escapeHtml(normalizedRoom.name)}</div>
      </div>

      ${(modeChip || powerChip || pathChip || waterChip || edgeMopChip || passesChip) ? `
        <div class="evcc-room-setting-chips">
          ${modeChip    ? `<span class="evcc-room-setting-chip">${this.escapeHtml(modeChip)}</span>`    : ""}
          ${powerChip   ? `<span class="evcc-room-setting-chip">${this.escapeHtml(powerChip)}</span>`   : ""}
          ${pathChip    ? `<span class="evcc-room-setting-chip">${this.escapeHtml(pathChip)}</span>`    : ""}
          ${waterChip   ? `<span class="evcc-room-setting-chip">${this.escapeHtml(waterChip)}</span>`   : ""}
          ${edgeMopChip ? `<span class="evcc-room-setting-chip">${this.escapeHtml(edgeMopChip)}</span>` : ""}
          ${passesChip  ? `<span class="evcc-room-setting-chip">${this.escapeHtml(passesChip)}</span>`  : ""}
        </div>
      ` : ""}

      ${progressMeta}

      <div class="evcc-room-chip-row">

        ${estimateChip}

        ${confidenceChip}

        ${plannedWaterChip}

        ${lastCleanedChip}

      </div>

      ${notes.length ? `
        <div class="evcc-room-notes">
          ${notes.map((note) => `
            <div
              class="evcc-room-note evcc-room-note--${this.escapeHtml(note.variant)}"
              ${
                (() => {
                  const fallbackTitle =
                    String(note.text).includes("No learned data")
                      ? "This room is using a fallback estimate until enough learned samples are collected."
                      : String(note.text).includes("runs to reliable")
                        ? `Estimated ${String(note.text).split(" ")[0]} more runs to reach high confidence.`
                        : String(note.text).includes("intensity mismatch")
                          ? "Estimate was learned from a different cleaning intensity or profile."
                          : "";

                  const title = note.title || fallbackTitle;
                  return title ? `title="${this.escapeHtml(title)}"` : "";
                })()
              }
            >
              ${this.escapeHtml(note.text)}
            </div>
          `).join("")}
        </div>
      ` : ""}

    </div>
  `;
};

  /* =========================================================
     NORMALIZE ROOM DISPLAY DATA
     ========================================================= */

  proto._normalizeRoomDisplayData = function (room) {
    const details = room?.selected_profile_details ?? {};

    const profileName = String(
      room?.profile_name ??
      room?.profileName ??
      room?.profile ??
      "vacuum_quick"
    );

    const cleanMode = String(
      room?.clean_mode ??
      room?.cleanMode ??
      details?.clean_mode ??
      "vacuum"
    );

    const fanSpeed = String(
      room?.fan_speed ??
      room?.fanSpeed ??
      details?.fan_speed ??
      ""
    );

    const waterLevel = String(
      room?.water_level ??
      room?.waterLevel ??
      details?.water_level ??
      ""
    );

    const cleanIntensity = String(
      room?.clean_intensity ??
      room?.cleanIntensity ??
      details?.clean_intensity ??
      ""
    );

    const cleanPasses = Number(
      room?.clean_passes ??
      room?.cleanPasses ??
      room?.passes ??
      details?.default_clean_passes ??
      1
    );

    const edgeMopping = Boolean(
      room?.edge_mopping ??
      room?.edgeMopping ??
      details?.default_edge_mopping ??
      false
    );

    const floorType = String(
      room?.floor_type ??
      room?.floorType ??
      ""
    );

    const carpetType = String(
      room?.carpet_type ??
      room?.carpetType ??
      ""
    );

    const carpet = Boolean(
      room?.carpet ??
      (() => {
        const ft = String(floorType).toLowerCase();
        return ft === "carpet" || ft.startsWith("carpet_") || ft.startsWith("carpet-");
      })()
    );

    const order = Number(
      room?.order ??
      room?.displayOrder ??
      room?.position ??
      999999
    );

    return {
      id: room?.id,
      mapId: room?.mapId ?? room?.map_id ?? "",
      name: room?.name ?? room?.room_name ?? "",
      slug: room?.slug ?? room?.room_slug ?? null,
      enabled: Boolean(room?.enabled),
      order: Number.isFinite(order) ? order : 999999,
      profileName,
      profileLabel:
        room?.profile_label ??
        room?.profileLabel ??
        room?.selected_profile_label ??
        room?.resolved_profile_label ??
        null,
      profileSubtitle: room?.profile_subtitle ?? room?.profileSubtitle ?? null,
      lastCleanedAt: room?.lastCleanedAt ?? room?.last_cleaned_at ?? null,
      lastJobMode:   room?.lastJobMode   ?? room?.last_job_mode   ?? null,
      isCustomProfile: profileName.toLowerCase() === "custom",
      cleanMode,
      cleanModeLabel: room?.clean_mode_label ?? room?.cleanModeLabel ?? details?.clean_mode_label ?? null,
      fanSpeed,
      fanSpeedLabel: room?.fan_speed_label ?? room?.fanSpeedLabel ?? details?.fan_speed_label ?? null,
      waterLevel,
      waterLevelLabel: room?.water_level_label ?? room?.waterLevelLabel ?? details?.water_level_label ?? null,
      cleanIntensity,
      cleanIntensityLabel:
        room?.clean_intensity_label ??
        room?.cleanIntensityLabel ??
        details?.clean_intensity_label ??
        details?.path_type_label ??
        null,
      cleanPasses: Number.isFinite(cleanPasses) ? cleanPasses : 1,
      cleanPassesLabel: room?.clean_passes_label ?? room?.cleanPassesLabel ?? details?.clean_passes_label ?? null,
      edgeMopping,
      edgeMoppingLabel: room?.edge_mopping_label ?? room?.edgeMoppingLabel ?? details?.edge_mopping_label ?? null,
      floorType,
      floorTypeLabel: room?.floor_type_label ?? room?.floorTypeLabel ?? null,
      carpetType,
      carpetTypeLabel: room?.carpet_type_label ?? room?.carpetTypeLabel ?? null,
      carpet,
      selectedProfileDetails: details,
    };
  };

  /* =========================================================
     HELPERS
     ========================================================= */

  proto._isMopMode = function (cleanMode) {
    const mode = String(cleanMode ?? "").toLowerCase();
    return mode === "mop" || mode === "vacuum_mop" || mode.includes("mop") || mode.includes("wash");
  };

  proto._roomProfileLabel = function (profile) {
    const value = String(profile ?? "").trim();
    if (!value) return "Standard";
    if (value.toLowerCase() === "custom") return "Custom";
    if (value === "vacuum_quick") return "Vacuum Only Quick";
    if (value === "vacuum_deep") return "Vacuum Only Deep";
    if (value === "vacuum_mop_quick") return "Quick";
    if (value === "vacuum_mop_deep") return "Deep";
    if (value === "user_1") return "User Profile 1";

    return value
      .replace(/[_-]+/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  };

  proto._formatCleanMode = function (value) {
    const raw = String(value ?? "").trim().toLowerCase();

    if (raw === "vacuum_mop") return "Vacuum + Mop";
    if (raw === "vacuum and mop") return "Vacuum + Mop";
    if (raw === "vacuum") return "Vacuum";
    if (raw === "mop") return "Mop";

    return this._formatSettingValue(value);
  };

  proto._formatFanSpeed = function (value) {
    return this._formatSettingValue(value);
  };

  proto._formatWaterLevel = function (value) {
    return this._formatSettingValue(value);
  };

  proto._formatCleanIntensity = function (value) {
    return this._formatSettingValue(value);
  };

  proto._formatFloorType = function (value) {
    return this._formatSettingValue(value);
  };

  proto._formatSettingValue = function (value) {
    if (!value) return "";

    return String(value)
      .replace(/[_-]+/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  };
}
