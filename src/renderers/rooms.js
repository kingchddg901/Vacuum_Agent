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

import { renderStepsManifest } from "../state/steps-manifest.js";

/**
 * Local-block reason CODES that state/rooms.js returns (as opposed to raw backend
 * messages). The renderer localizes these via tRaw("rooms.block_reason.<code>");
 * any value NOT in this set is a backend-provided message and passes through raw.
 */
const BLOCK_REASON_CODES = new Set([
  "no_rooms_included", "already_cleaning", "returning_to_dock", "vacuum_error", "start_blocked",
]);

/**
 * Mix rooms renderer methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applyRoomsRenderers(proto) {

  /* =========================================================
     RENDER ROOMS VIEW
     ========================================================= */

  /**
   * Pre-run "This run" preview: when a stepped (charge) profile is applied but not yet
   * running, show its true Clean → ⚡ Charge → Clean sequence up top, so the flat "N room"
   * queue below doesn't misrepresent a multi-phase run. Reuses the profile-card sequence
   * render; charge time is ADMITTED, not modelled (it varies with the dock battery).
   *
   * @param {object} state - Card state accessor.
   * @returns {string} HTML ("" with no applied stepped profile, or mid-run).
   */
  proto.renderSteppedRunPreview = function (state) {
    if (state.hasActiveRun?.()) return "";
    const collapsed = Boolean(state.isSteppedPreviewCollapsed?.());

    // Source A — an explicitly applied stepped run profile (takes precedence).
    const profileId = state.pendingStepRunProfileId?.();
    const profile = profileId
      ? (state.savedRunProfiles?.() ?? []).find((p) => p.id === profileId)
      : null;

    // Source B — the live queue's OWN ad-hoc breaks (charge/wait added straight to
    // the queue, no saved profile). Surfaced via the dashboard snapshot's queue_steps.
    const queueSteps = state.dashboardSnapshot?.()?.queue_steps ?? null;
    const queueHasBreaks = Boolean(queueSteps?.has_breaks);

    let body = "";
    if (profile && typeof this._renderRunProfileStepsSummary === "function") {
      body = this._renderRunProfileStepsSummary(state, profile);
    } else if (queueHasBreaks) {
      const nameById = {};
      (state.getRoomsForActiveMap?.() ?? []).forEach((room) => {
        nameById[String(room.id)] = room.name;
      });
      const zoneNameById = {};
      (state.savedZones?.() ?? []).forEach((z) => {
        if (z && z.id != null) zoneNameById[String(z.id)] = z.name;
      });
      body = renderStepsManifest({
        steps: queueSteps.steps,
        nameById,
        zoneNameById,
        t: (key, vars) => this.t(key, vars),
        escapeHtml: (s) => this.escapeHtml(s),
      });
    }
    if (!body) return "";

    // The "charge time varies" note is about a CHARGE step's dock time — only relevant when
    // the plan actually has one. A rooms+zone or rooms+wait plan must not show it.
    const noteSteps = profile ? (profile.steps ?? []) : (queueSteps?.steps ?? []);
    const hasChargeStep = Array.isArray(noteSteps)
      && noteSteps.some((s) => s && s.type === "charge_wait");

    return `
      <div class="evcc-stepped-run-preview ${collapsed ? "evcc-stepped-run-preview--collapsed" : ""}">
        <button
          type="button"
          class="evcc-stepped-run-preview-header"
          data-action="toggle-stepped-preview"
          aria-expanded="${collapsed ? "false" : "true"}"
        >
          <span class="evcc-stepped-run-preview-title">${this.t("rooms.run_plan_title")}</span>
          <span class="evcc-stepped-run-preview-caret" aria-hidden="true">${collapsed ? "▸" : "▾"}</span>
        </button>
        ${collapsed ? "" : `
          ${body}
          ${hasChargeStep ? `<div class="evcc-stepped-run-preview-note">${this.t("rooms.charge_time_varies")}</div>` : ""}
        `}
      </div>
    `;
  };

  proto.renderRoomsView = function (ctx) {
    const { state } = ctx;

    const rooms = state.getRoomsForActiveMap();
    const orderedRooms = this._withCurrentRoomPinned(rooms, state);
    const canStart = state.canStartCleaning();
    const rawBlockReason = state.startBlockedReason();
    const blockedReason = rawBlockReason && BLOCK_REASON_CODES.has(rawBlockReason)
      ? this.tRaw(`rooms.block_reason.${rawBlockReason}`)
      : rawBlockReason;
    const hasWarning = state.hasStartWarning();
    const enabledCount = state.enabledRoomCount();
    const activeJob = state.activeJobRooms();

    if (rooms.length === 0) {
      return `
        <div class="evcc-rooms-view">
          <div class="evcc-empty">${this.t("rooms.empty")}</div>
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

        ${typeof this.renderSteppedRunPreview === "function" ? this.renderSteppedRunPreview(state) : ""}

        ${typeof this.renderLiveQueue === "function" ? this.renderLiveQueue(state) : ""}

        ${typeof this.renderLearningSummary === "function" ? this.renderLearningSummary(state) : ""}

        ${typeof this.renderIncompleteRunBanner === "function" ? this.renderIncompleteRunBanner(state) : ""}

        ${typeof this.renderLearningPreJobPanel === "function" ? this.renderLearningPreJobPanel(state) : ""}

        ${typeof this.renderLearningProcessingControl === "function" ? this.renderLearningProcessingControl(state) : ""}

        ${typeof this.renderLearningLiveBanner === "function" ? this.renderLearningLiveBanner(state) : ""}

        ${typeof this.renderLearningChargeStatus === "function" ? this.renderLearningChargeStatus(state) : ""}

        ${typeof this.renderLearningWaitStatus === "function" ? this.renderLearningWaitStatus(state) : ""}

        ${typeof this.renderLearningZoneStatus === "function" ? this.renderLearningZoneStatus(state) : ""}

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

          <div class="evcc-rooms-sidecol">
            ${typeof this.renderRunProfilesPanel === "function"
              ? this.renderRunProfilesPanel(state)
              : ""}
            ${typeof this.renderSavedZonesPanel === "function"
              ? this.renderSavedZonesPanel(state)
              : ""}
            ${(state.isMapViewActive?.() && (state.canDrawZone?.() ?? false) && (state.zoneDrawMode?.() ?? false)
               && (state.zoneDrawPurpose?.() !== "save"))
              ? this._renderZonePanel(
                  state,
                  state.zoneDrafts?.() ?? [],
                  state.zoneCount?.() ?? 0,
                  state.zoneMax?.() ?? 10,
                )
              : ""}
            ${(state.isMapViewActive?.() && (state.overlaysAligned?.() ?? false)
               && typeof this._renderMapLayersPanel === "function")
              ? this._renderMapLayersPanel(state)
              : ""}
          </div>
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
          title="${this.t("rooms.list_view")}"
          aria-label="${this.t("rooms.list_view")}"
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
          title="${this.t("rooms.map_view")}"
          aria-label="${this.t("rooms.map_view")}"
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
          title="${(state.roomFloorTextureEnabled?.() ?? true) ? this.t("rooms.hide_room_card_textures") : this.t("rooms.show_room_card_textures")}"
          aria-label="${(state.roomFloorTextureEnabled?.() ?? true) ? this.t("rooms.hide_room_card_textures") : this.t("rooms.show_room_card_textures")}"
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
          title="${this.t("rooms.configure_map")}"
          aria-label="${this.t("rooms.configure_map")}"
        >
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="8" cy="8" r="2.5"/>
            <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41"/>
          </svg>
          ${this.t("rooms.configure")}
        </button>
        ${this._renderMapAnimalControls(state)}
        <button
          class="evcc-rooms-view-toggle-btn${(state.mapFloorTextureEnabled?.() ?? true) ? " active" : ""}"
          data-action="map-texture-toggle"
          title="${(state.mapFloorTextureEnabled?.() ?? true) ? this.t("rooms.hide_map_textures") : this.t("rooms.show_map_textures")}"
          aria-label="${(state.mapFloorTextureEnabled?.() ?? true) ? this.t("rooms.hide_map_textures") : this.t("rooms.show_map_textures")}"
          aria-pressed="${(state.mapFloorTextureEnabled?.() ?? true) ? "true" : "false"}"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round">
            <rect x="2" y="2" width="12" height="12" rx="1.5"/>
            <path d="M2 6 L6 2 M2 10 L10 2 M2 14 L14 2 M6 14 L14 6 M10 14 L14 10"/>
          </svg>
        </button>
        <button
          class="evcc-rooms-view-toggle-btn${(state.mapRoomLabelsEnabled?.() ?? true) ? " active" : ""}"
          data-action="map-labels-toggle"
          title="${(state.mapRoomLabelsEnabled?.() ?? true) ? this.t("rooms.hide_room_labels") : this.t("rooms.show_room_labels")}"
          aria-label="${(state.mapRoomLabelsEnabled?.() ?? true) ? this.t("rooms.hide_room_labels") : this.t("rooms.show_room_labels")}"
          aria-pressed="${(state.mapRoomLabelsEnabled?.() ?? true) ? "true" : "false"}"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round">
            <path d="M2.5 4 L8.5 4 L13 8 L8.5 12 L2.5 12 Z"/>
            <circle cx="5" cy="8" r="0.9" fill="currentColor" stroke="none"/>
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
        <span class="evcc-orphaned-rooms-label">${this.t("rooms.access_not_set")}</span>
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
          <span class="evcc-active-job-label">${this.t("rooms.running")}</span>
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
  // A zone is a queued clean unit too — count the zone steps alongside the rooms so the header
  // reads "2 rooms · 1 zone", not just the room count (the zone is otherwise invisible up here).
  const _queueSteps = this.card?._state?.dashboardSnapshot?.()?.queue_steps?.steps;
  const _zoneCount = (Array.isArray(_queueSteps) ? _queueSteps : []).filter(
    (s) => s && s.type === "zone"
  ).length;
  const _roomsLabel = this.t("rooms.count_rooms", { count: enabledCount });
  const countLabel = _zoneCount > 0
    ? `${_roomsLabel} · ${this.t("rooms.count_zones", { count: _zoneCount })}`
    : _roomsLabel;
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
    ? this.t("rooms.confirm_cancel")
    : hasActiveRun
      ? this.t("rooms.cancel_run")
      : startRequiresConfirmation
        ? this.t("rooms.confirm_start")
        : this.t("rooms.start_cleaning");

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

  // Stepped-run preview: when a charge profile is applied (pre-run), render the queue chips
  // from its ordered steps, treating each charge point as a "fake room" chip in the row.
  const steppedProfileId = !hasActiveRun ? cardState?.pendingStepRunProfileId?.() : null;
  const steppedProfile = steppedProfileId
    ? (cardState?.savedRunProfiles?.() ?? []).find((p) => p.id === steppedProfileId)
    : null;
  // Ad-hoc queue breaks (no saved profile applied): the live queue itself carries the
  // charge/wait steps. Render the SAME interleaved chip row so the break shows in place
  // between its rooms — display-only for now (values aren't inline-editable for the ad-hoc
  // queue yet, unlike the profile chips whose inputs are wired via run-profiles bindings;
  // param-edit is the follow-up).
  const queueStepsSnap = !hasActiveRun && !steppedProfile
    ? (cardState?.dashboardSnapshot?.()?.queue_steps ?? null)
    : null;
  const queueHasBreaks = Boolean(queueStepsSnap?.has_breaks) && Array.isArray(queueStepsSnap?.steps);
  const chipRoomById = {};
  const chipMinutesById = {};
  const chipZoneEstById = {};
  if (steppedProfile || queueHasBreaks) {
    (Array.isArray(rooms) ? rooms : []).forEach((r) => { chipRoomById[String(r.id)] = r; });
    timeline.forEach((t) => { if (t && t.room_id != null) chipMinutesById[String(t.room_id)] = t.minutes; });
    // Per-zone estimate (learned avg or area fallback) -> the zone chip's time + source marker.
    const zoneEst = cardState?.dashboardPlannedJobEstimateZones?.();
    (Array.isArray(zoneEst) ? zoneEst : []).forEach((z) => {
      if (z && z.zone_id != null) chipZoneEstById[String(z.zone_id)] = z;
    });
  }

  return `
    <div class="evcc-rooms-action-bar">

      <div class="evcc-rooms-bar-top">
        <div class="evcc-rooms-queue-summary">
          <span class="evcc-rooms-queue-count">${this.escapeHtml(countLabel)}</span>
          <span class="evcc-rooms-queue-label">${this.t("rooms.included")}</span>
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
            >${canResumeRun ? this.t("rooms.resume") : this.t("rooms.pause")}</button>
          ` : ""}

          <button type="button" class="evcc-chip" data-action="locate-vacuum">
            ${this.t("rooms.locate")}
          </button>

          ${!hasActiveRun ? `
            <button type="button" class="evcc-chip" data-action="select-all">
              ${this.t("rooms.select_all")}
            </button>

            <button
              type="button"
              class="evcc-chip ${clearQueueRequiresConfirmation ? "evcc-chip--start-warn evcc-chip--confirm-flash" : ""}"
              data-action="clear-queue"
            >${clearQueueRequiresConfirmation ? this.t("rooms.confirm_clear") : this.t("rooms.clear_queue")}</button>
          ` : ""}

          ${!cardState?.hasActiveRun?.() && enabledCount >= 2 ? `
            <button type="button" class="evcc-chip" data-action="add-charge-break">
              ${this.t("rooms.add_charge_break")}
            </button>
            <button type="button" class="evcc-chip" data-action="add-wait-break">
              ${this.t("rooms.add_wait_break")}
            </button>
            ${(cardState?.savedZones?.() ?? []).length ? `
              <button type="button" class="evcc-chip" data-action="open-zone-picker">
                ${this.t("rooms.add_zone")}
              </button>
            ` : ""}
          ` : ""}
          ${!cardState?.hasActiveRun?.() && Boolean(cardState?.dashboardSnapshot?.()?.queue_steps?.has_breaks) ? `
            <button type="button" class="evcc-chip" data-action="clear-queue-breaks">
              ${this.t("rooms.clear_breaks")}
            </button>
          ` : ""}
        </div>
      </div>

      ${blockedReason && !canStart ? `
        <div class="evcc-rooms-block-reason">${this.escapeHtml(blockedReason)}</div>
      ` : ""}

      ${cancelRequiresConfirmation ? `
        <div class="evcc-rooms-cancel-warning" role="alert">
          ${this.tRaw("rooms.cancel_warning")}
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
              ? this.t("rooms.strict_order_on_text")
              : this.escapeHtml(orderAdvisory)}
          </div>
          <button
            type="button"
            class="evcc-chip ${strictOrder ? "active" : ""}"
            data-action="toggle-strict-order"
            aria-pressed="${strictOrder ? "true" : "false"}"
          >${strictOrder ? this.t("rooms.strict_order_on_label") : this.t("rooms.force_exact_order")}</button>
        </div>
      ` : ""}

      ${showPrimaryConfirmCancel ? `
        <div class="evcc-rooms-inline-actions">
          <button
            type="button"
            class="evcc-chip"
            data-action="cancel-primary-confirmation"
          >${this.t("common.cancel")}</button>
        </div>
      ` : ""}

      ${startRequiresConfirmation ? `
        <div class="evcc-start-preflight-panel">
          <div class="evcc-start-preflight-header">${this.t("rooms.reduced_run_detected")}</div>

          <div class="evcc-start-preflight-summary">
            <span>${this.t("rooms.n_blocked", { count: this.escapeHtml(String(startPreflight?.blocked_room_count ?? 0)) })}</span>
            <span>·</span>
            <span>${this.t("rooms.n_included", { count: this.escapeHtml(String(startPreflight?.included_room_count ?? enabledCount)) })}</span>
            ${Number.isFinite(Number(startPreflight?.blocked_expected_minutes)) && Number(startPreflight?.blocked_expected_minutes) > 0 ? `
              <span>·</span>
              <span>${this.t("rooms.duration_skipped", { duration: this.escapeHtml(this._formatLearningDuration(Number(startPreflight.blocked_expected_minutes))) })}</span>
            ` : ""}
          </div>

          ${blockedRooms.length ? `
            <div class="evcc-start-preflight-section">
              <div class="evcc-start-preflight-title">${this.t("rooms.blocked_rooms")}</div>
              <div class="evcc-start-preflight-list">
                ${blockedRooms.map((room) => `
                  <div class="evcc-start-preflight-item">
                    <span class="evcc-start-preflight-room">${this.escapeHtml(room.name ?? room.room_id ?? this.t("rooms.room_fallback"))}</span>
                    <span class="evcc-start-preflight-reason">${this.escapeHtml(room.reason ?? this.t("rooms.blocked_fallback"))}</span>
                  </div>
                `).join("")}
              </div>
            </div>
          ` : ""}

          ${modifiedRooms.length ? `
            <div class="evcc-start-preflight-section">
              <div class="evcc-start-preflight-title">${this.t("rooms.modified_rooms")}</div>
              <div class="evcc-start-preflight-list">
                ${modifiedRooms.map((room) => {
                  const changeLabel = Object.keys(room.changes ?? {}).join(", ") || this.t("rooms.settings_adjusted");
                  // Fan-out attribution: when this entry was created
                  // purely by a rule fan-out (no direct rule on this
                  // room contributed), the backend flags it with
                  // derived: true and source_* fields. Surface the
                  // source rule name so users see why a room they
                  // didn't author a rule for is being modified.
                  const derivedNote = room.derived && room.source_rule_name
                    ? ` ${this.t("rooms.derived_via", { room: room.source_room_name ?? this.t("rooms.another_room"), rule: room.source_rule_name })}`
                    : "";
                  return `
                    <div class="evcc-start-preflight-item">
                      <span class="evcc-start-preflight-room">${this.escapeHtml(room.name ?? room.room_id ?? this.t("rooms.room_fallback"))}</span>
                      <span class="evcc-start-preflight-reason">${this.escapeHtml(changeLabel + derivedNote)}</span>
                    </div>
                  `;
                }).join("")}
              </div>
            </div>
          ` : ""}

          ${warnings.length ? `
            <div class="evcc-start-preflight-section">
              <div class="evcc-start-preflight-title">${this.t("rooms.warnings")}</div>
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

      ${steppedProfile ? `
        <div class="evcc-queue-chips evcc-queue-chips--preview">
          ${this._renderSteppedRunChips(steppedProfile, chipRoomById, chipMinutesById, "profile", chipZoneEstById)}
        </div>
      ` : queueHasBreaks ? `
        <div class="evcc-queue-chips evcc-queue-chips--preview">
          ${this._renderSteppedRunChips({ steps: queueStepsSnap.steps }, chipRoomById, chipMinutesById, "queue", chipZoneEstById)}
        </div>
      ` : queueRooms.length > 0 ? `
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
                title="${this.t("rooms.queue_chip_title")}"
                aria-label="${this.t("rooms.queue_room_aria", { name: this.escapeHtml(room.name) })}"
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
          ${this.t("rooms.no_rooms_queued")}
        </div>
      `}

      ${this.renderZonePickerModal(cardState)}
    </div>
  `;
};

  /**
   * Multi-select saved-zone picker for inserting a zone STEP. A fixed-position modal
   * (renders correctly wherever it sits in the DOM); tapping a zone toggles it, Add inserts
   * one zone step cleaning the whole selection.
   *
   * @param {object} cardState - The card state accessor.
   * @returns {string} HTML string (empty when the picker is closed).
   */
  proto.renderZonePickerModal = function (cardState) {
    if (!cardState?.queueZonePickerOpen?.()) return "";
    const zones = cardState.savedZones?.() ?? [];
    const selectedCount = (cardState.queueZonePickerSelected?.() ?? []).length;
    return `
      <div class="evcc-modal-backdrop" data-action="close-zone-picker">
        <div class="evcc-modal" data-stop-propagation>
          <div class="evcc-modal-header">
            <div class="evcc-modal-title">${this.t("rooms.zone_picker_title")}</div>
            <button type="button" class="evcc-chip evcc-chip--icon" data-action="close-zone-picker"
              title="${this.t("common.close")}">✕</button>
          </div>
          <div class="evcc-modal-body">
            ${zones.length ? `
              <div class="evcc-zone-picker-list">
                ${zones.map((z) => `
                  <button type="button"
                    class="evcc-zone-picker-item ${cardState.isQueueZonePicked?.(z.id) ? "is-picked" : ""}"
                    data-action="toggle-zone-pick" data-zone-id="${this.escapeHtml(String(z.id))}">
                    <span class="evcc-zone-picker-check" aria-hidden="true">${cardState.isQueueZonePicked?.(z.id) ? "☑" : "☐"}</span>
                    <span class="evcc-zone-picker-name">🎯 ${this.escapeHtml(z.name ?? this.t("rooms.zone_fallback"))}</span>
                  </button>
                `).join("")}
              </div>
            ` : `<div class="evcc-queue-empty">${this.t("rooms.zone_picker_empty")}</div>`}
          </div>
          <div class="evcc-modal-footer">
            <button type="button" class="evcc-chip" data-action="close-zone-picker">${this.t("common.cancel")}</button>
            <button type="button" class="evcc-chip evcc-chip--save" data-action="confirm-zone-picker"
              ${selectedCount ? "" : "disabled"}>${this.t("rooms.zone_picker_add")}</button>
          </div>
        </div>
      </div>
    `;
  };

  /**
   * Render the pre-run queue chips from a stepped profile's ordered steps: each room_group's
   * rooms as room chips, each charge point as a "fake room" charge chip — so the flat chip row
   * shows the true Kitchen · ⚡ Charge · Kitchen sequence. Display-only (no room interaction).
   *
   * @param {object} profile - The applied run profile (carries .steps).
   * @param {object} roomById - room_id -> the full room object (name, mapId, ...).
   * @param {object} minutesById - room_id -> estimated minutes.
   * @returns {string} HTML string.
   */
  proto._renderSteppedRunChips = function (profile, roomById, minutesById, mode = "profile", zoneEstById = {}) {
    const steps = Array.isArray(profile?.steps) ? profile.steps : [];
    // "profile"  — editable inputs wired to the applied profile (data-chip-*-index).
    // "queue"    — editable inputs wired to the live queue (data-queue-break-*-index),
    //              plus a per-chip move handle (opens the steps reorder modal) and a remove.
    // "readonly" — static value pills, no controls.
    const queueMode = mode === "queue";
    const displayOnly = mode === "readonly";
    const chips = [];
    let pos = 0;
    let breakIdx = 0;

    // Zone chips show saved-zone NAMES (the step carries ids).
    const savedZones = this.card?._state?.savedZones?.() ?? [];
    const zoneNameById = {};
    (Array.isArray(savedZones) ? savedZones : []).forEach((z) => {
      if (z && z.id != null) zoneNameById[String(z.id)] = z.name;
    });

    // Move handle: opens the shared move-to-position modal on the "steps" scope, seeded on
    // this item. The generic open-order-selector binding reads data-scope + data-item-id.
    const moveHandle = (itemId) => queueMode
      ? `<button type="button" class="evcc-queue-chip-move"
          data-action="open-order-selector" data-scope="steps" data-item-id="${this.escapeHtml(itemId)}"
          title="${this.t("rooms.move_step")}" aria-label="${this.t("rooms.move_step")}">⋮⋮</button>`
      : "";
    const removeBtn = (bi) => `<button type="button" class="evcc-queue-chip-remove"
        data-action="remove-queue-break" data-break-index="${bi}"
        title="${this.t("rooms.remove_break")}" aria-label="${this.t("rooms.remove_break")}">✕</button>`;

    steps.forEach((step, si) => {
      if (step && step.type === "charge_wait") {
        pos += 1;
        const bi = breakIdx; breakIdx += 1;
        const target = Number(step.target_battery_percent ?? 100);
        const valuePart = displayOnly
          ? `<span class="evcc-queue-chip-time">${this.escapeHtml(String(target))}%</span>`
          : `<input type="number" min="1" max="100" step="1"
              value="${this.escapeHtml(String(target))}"
              class="evcc-queue-chip-input" ${queueMode ? `data-queue-break-charge-index="${bi}"` : `data-chip-charge-index="${si}"`}
              aria-label="${this.t("rooms.chip_charge_to", { target: this.escapeHtml(String(target)) })}" /><span class="evcc-queue-chip-unit">%</span>`;
        chips.push(`
          <div class="evcc-queue-chip evcc-queue-chip--charge">
            ${moveHandle(`break:${bi}`)}
            <span class="evcc-queue-chip-order">${pos}</span>
            <span class="evcc-queue-chip-charge-icon" aria-hidden="true">⚡</span>
            <span class="evcc-queue-chip-label">${this.t("rooms.chip_charge_label")}</span>
            ${valuePart}
            ${queueMode ? removeBtn(bi) : ""}
          </div>`);
        return;
      }
      if (step && step.type === "wait") {
        pos += 1;
        const bi = breakIdx; breakIdx += 1;
        const mins = Number(step.wait_minutes ?? 30);
        const valuePart = displayOnly
          ? `<span class="evcc-queue-chip-time">${this.escapeHtml(String(mins))} ${this.t("run_profiles.minutes_unit")}</span>`
          : `<input type="number" min="1" max="1440" step="1"
              value="${this.escapeHtml(String(mins))}"
              class="evcc-queue-chip-input" ${queueMode ? `data-queue-break-wait-index="${bi}"` : `data-chip-wait-index="${si}"`}
              aria-label="${this.t("rooms.chip_wait", { minutes: this.escapeHtml(String(mins)) })}" /><span class="evcc-queue-chip-unit">${this.t("run_profiles.minutes_unit")}</span>`;
        chips.push(`
          <div class="evcc-queue-chip evcc-queue-chip--wait">
            ${moveHandle(`break:${bi}`)}
            <span class="evcc-queue-chip-order">${pos}</span>
            <span class="evcc-queue-chip-charge-icon" aria-hidden="true">⏱</span>
            <span class="evcc-queue-chip-label">${this.t("rooms.chip_wait_label")}</span>
            ${valuePart}
            ${queueMode ? removeBtn(bi) : ""}
          </div>`);
        return;
      }
      if (step && step.type === "zone") {
        pos += 1;
        const bi = breakIdx; breakIdx += 1;
        const ids = Array.isArray(step.zone_ids) ? step.zone_ids : [];
        const names = ids
          .map((id) => zoneNameById[String(id)] || this.t("rooms.zone_fallback"))
          .join(", ");
        // Sum this chip's zones (a chip can carry several) and mark the time LEARNED only when
        // every one is learned — one un-sampled zone makes the whole chip an estimate (~).
        let zoneSeconds = 0;
        let anyKnown = false;
        let allLearned = ids.length > 0;
        let samples = 0;
        ids.forEach((id) => {
          const e = zoneEstById[String(id)];
          const secs = Number(e?.seconds);
          if (e && Number.isFinite(secs) && secs > 0) {
            zoneSeconds += secs;
            anyKnown = true;
            if (e.source === "learned") samples += Number(e.sample_count) || 0;
            else allLearned = false;
          } else {
            allLearned = false;
          }
        });
        const learned = anyKnown && allLearned;
        const timePart = anyKnown
          ? `<span class="evcc-queue-chip-time${learned ? " evcc-queue-chip-time--learned" : ""}"
              title="${learned
                ? this.t("rooms.zone_time_learned", { count: samples })
                : this.t("rooms.zone_time_estimated")}">${learned ? "" : "~"}${this.escapeHtml(this._formatLearningMinutes(zoneSeconds / 60))}</span>`
          : "";
        chips.push(`
          <div class="evcc-queue-chip evcc-queue-chip--zone">
            ${moveHandle(`break:${bi}`)}
            <span class="evcc-queue-chip-order">${pos}</span>
            <span class="evcc-queue-chip-charge-icon" aria-hidden="true">🎯</span>
            <span class="evcc-queue-chip-label">${this.escapeHtml(names)}</span>
            ${timePart}
            ${queueMode ? removeBtn(bi) : ""}
          </div>`);
        return;
      }
      const groupRooms = (step && Array.isArray(step.rooms)) ? step.rooms : [];
      for (const r of groupRooms) {
        pos += 1;
        const rid = String(r.room_id);
        const room = roomById[rid];
        const name = room?.name ?? this.t("run_profiles.room_fallback", { id: this.escapeHtml(rid) });
        const mins = minutesById[rid];
        // Queue mode renders room chips as a div (not a button) so the move handle nests
        // legally — but keeps data-queue-chip + the room data attrs so the SAME chip binding
        // still gives click=settings and long-press=remove. Only the grip/remove/input
        // sub-controls are excluded from those (see _bindQueueChipActions guard).
        if (queueMode) {
          chips.push(`
            <div class="evcc-queue-chip evcc-queue-chip--queued"
              data-queue-chip="true"
              data-room-id="${this.escapeHtml(rid)}"
              data-map-id="${this.escapeHtml(String(room?.mapId ?? ""))}"
              data-enabled="true"
            >
              ${moveHandle(`room:${rid}`)}
              <span class="evcc-queue-chip-order">${pos}</span>
              <span class="evcc-queue-chip-label">${this.escapeHtml(name)}</span>
              ${mins != null ? `<span class="evcc-queue-chip-time">${this.escapeHtml(this._formatLearningMinutes(mins))}</span>` : ""}
            </div>`);
          continue;
        }
        // A real room chip stays interactive (click to edit, long-press to toggle) via the
        // shared queue-chip binding — only the charge/wait "fake room" chips are display-only.
        chips.push(`
          <button type="button"
            class="evcc-queue-chip evcc-queue-chip--queued"
            data-queue-chip="true"
            data-room-id="${this.escapeHtml(rid)}"
            data-map-id="${this.escapeHtml(String(room?.mapId ?? ""))}"
            data-enabled="true"
          >
            <span class="evcc-queue-chip-order">${pos}</span>
            <span class="evcc-queue-chip-label">${this.escapeHtml(name)}</span>
            ${mins != null ? `<span class="evcc-queue-chip-time">${this.escapeHtml(this._formatLearningMinutes(mins))}</span>` : ""}
          </button>`);
      }
    });
    return chips.join("");
  };

  /* =========================================================
     TOTAL LIVE QUEUE — the running job's whole phase sequence as an ordered chip row
     (the monitor twin of the composer). Read-only; driven by the active_job clone via
     state.dashboardLiveQueue(). Each chip is done / current (live %/ETA) / upcoming.
     ========================================================= */

  proto.renderLiveQueue = function (state) {
    const lq = state.dashboardLiveQueue?.();
    // Guard on a real, non-empty steps array (not just truthiness) so the harness null-object
    // can't paint an empty labelled box over a baseline.
    const steps = Array.isArray(lq?.steps) ? lq.steps : [];
    if (!steps.length) return "";
    const collapsed = Boolean(state.isLiveQueueCollapsed?.());
    const chips = steps.map((step) => this._renderLiveQueueChip(step)).join("");
    return `
      <div class="evcc-live-queue ${collapsed ? "evcc-live-queue--collapsed" : ""}">
        <button
          type="button"
          class="evcc-live-queue-header"
          data-action="toggle-live-queue"
          aria-expanded="${collapsed ? "false" : "true"}"
        >
          <span class="evcc-live-queue-label">${this.t("rooms.live_queue_label")}</span>
          <span class="evcc-live-queue-caret" aria-hidden="true">${collapsed ? "▸" : "▾"}</span>
        </button>
        ${collapsed ? "" : `<div class="evcc-queue-chips evcc-live-queue-chips">${chips}</div>`}
      </div>`;
  };

  proto._renderLiveQueueChip = function (step) {
    const st = String(step?.state || "upcoming");
    const stateCls = `evcc-live-chip--${st}`;
    const order = `<span class="evcc-queue-chip-order">${Number(step?.seq) || ""}</span>`;
    const doneMark = st === "done"
      ? `<span class="evcc-live-chip-done" aria-hidden="true">✓</span>` : "";
    const etaPart = (mins) => (st === "current" && mins != null)
      ? `<span class="evcc-queue-chip-time">~${this.escapeHtml(this._formatLearningMinutes(mins))}</span>`
      : "";

    if (step?.kind === "charge") {
      const target = Number(step.target_battery_percent ?? 100);
      return `<div class="evcc-queue-chip evcc-queue-chip--charge ${stateCls}">
        ${order}<span class="evcc-queue-chip-charge-icon" aria-hidden="true">⚡</span>
        <span class="evcc-queue-chip-label">${this.t("rooms.chip_charge_label")} ${this.escapeHtml(String(target))}%</span>${etaPart(step.eta_minutes)}${doneMark}</div>`;
    }
    if (step?.kind === "wait") {
      const mins = Number(step.wait_minutes ?? 30);
      return `<div class="evcc-queue-chip evcc-queue-chip--wait ${stateCls}">
        ${order}<span class="evcc-queue-chip-charge-icon" aria-hidden="true">⏱</span>
        <span class="evcc-queue-chip-label">${this.t("rooms.chip_wait_label")} ${this.escapeHtml(String(mins))} ${this.t("run_profiles.minutes_unit")}</span>${doneMark}</div>`;
    }
    if (step?.kind === "zone") {
      const names = (Array.isArray(step.zone_names) ? step.zone_names : [])
        .filter(Boolean).join(", ") || this.t("rooms.zone_fallback");
      return `<div class="evcc-queue-chip evcc-queue-chip--zone ${stateCls}">
        ${order}<span class="evcc-queue-chip-charge-icon" aria-hidden="true">🎯</span>
        <span class="evcc-queue-chip-label">${this.escapeHtml(names)}</span>${etaPart(step.eta_minutes)}${doneMark}</div>`;
    }
    // room
    const name = step?.name
      || this.t("run_profiles.room_fallback", { id: this.escapeHtml(String(step?.room_id ?? "")) });
    const pct = (st === "current" && step?.progress_percent != null)
      ? `<span class="evcc-queue-chip-time">${Math.max(0, Math.min(99, Math.floor(Number(step.progress_percent))))}%</span>`
      : "";
    return `<div class="evcc-queue-chip evcc-queue-chip--queued ${stateCls}">
      ${order}<span class="evcc-queue-chip-label">${this.escapeHtml(name)}</span>${pct}${doneMark}</div>`;
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

  // Localize each per-room setting chip by its stable VALUE, falling back to the
  // backend label (then a title-cased format). tVocabRaw — the chips are
  // escapeHtml'd at render below; this mirrors the room editor + standalone card,
  // which already localized while these compact cards showed the English label.
  const modeChip = normalizedRoom.cleanMode
    ? this.tVocabRaw("clean_mode", normalizedRoom.cleanMode, normalizedRoom.cleanModeLabel || this._formatCleanMode(normalizedRoom.cleanMode))
    : null;

  const isDefaultPower = !normalizedRoom.fanSpeed ||
    ["off", "normal"].includes(String(normalizedRoom.fanSpeed).toLowerCase());
  const powerChip = !isDefaultPower
    ? this.tVocabRaw("fan_speed", normalizedRoom.fanSpeed, normalizedRoom.fanSpeedLabel || this._formatFanSpeed(normalizedRoom.fanSpeed))
    : null;

  const isDefaultPath = !normalizedRoom.cleanIntensity ||
    String(normalizedRoom.cleanIntensity).toLowerCase() === "standard";
  const pathChip = !isDefaultPath
    ? this.tVocabRaw("clean_intensity", normalizedRoom.cleanIntensity, normalizedRoom.cleanIntensityLabel || this._formatCleanIntensity(normalizedRoom.cleanIntensity))
    : null;

  const waterChip = this._isMopMode(normalizedRoom.cleanMode) &&
    normalizedRoom.waterLevel &&
    String(normalizedRoom.waterLevel).toLowerCase() !== "off"
    ? this.tVocabRaw("water_level", normalizedRoom.waterLevel, normalizedRoom.waterLevelLabel || this._formatWaterLevel(normalizedRoom.waterLevel))
    : null;

  const edgeMopChip = this._isMopMode(normalizedRoom.cleanMode) && normalizedRoom.edgeMopping
    ? this.t("rooms.edge_mop_on")
    : null;

  const passesChip = Number(normalizedRoom.cleanPasses) > 1
    ? this.t("rooms.n_passes", { count: Number(normalizedRoom.cleanPasses) })
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
      this.t("rooms.estimate_label", { value: this._formatLearningMinutes(roomEstimate.minutes) }),
    ];

    if (roomEstimate.source) {
      estimateParts.push(this.t("rooms.source_label", { value: String(roomEstimate.source) }));
    }

    const estimateBattery = Number(roomEstimate.battery);
    if (Number.isFinite(estimateBattery)) {
      estimateParts.push(this.t("rooms.battery_label", { value: estimateBattery }));
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
      const trustLabel = variant === "success" ? this.t("rooms.trust_reliable")
        : variant === "warning" ? this.t("rooms.trust_learning")
        : variant === "error" ? this.t("rooms.trust_uncertain")
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
      confidenceChip = this.renderConfidenceChip({ ui_variant: "neutral" }, this.t("rooms.trust_unlearned"), this.t("rooms.trust_unlearned"));
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
              this.t("rooms.projected_water_use", { ml: Math.round(projectedWaterMl) }),
              plannedWaterRoom?.clean_mode_label ? this.t("rooms.mode_label", { value: String(plannedWaterRoom.clean_mode_label) }) : plannedWaterRoom?.effective_clean_mode ? this.t("rooms.mode_label", { value: String(plannedWaterRoom.effective_clean_mode) }) : null,
              plannedWaterRoom?.water_level_label ? this.t("rooms.water_label", { value: String(plannedWaterRoom.water_level_label) }) : plannedWaterRoom?.effective_water_level ? this.t("rooms.water_label", { value: String(plannedWaterRoom.effective_water_level) }) : null,
            ].filter(Boolean).join(" · ")
          )}"
        >
          ${this.t("rooms.water_ml", { ml: Math.round(projectedWaterMl) })}
        </div>
      `;
    }
  }

  const notes = [];

  if (roomEstimate?.intensity_mismatch) {
    notes.push({ type: "intensity_mismatch", text: `⚠ ${this.t("rooms.intensity_mismatch")}`, variant: "warning" });
  }

  const troubleEntry = state?.troubleRoomForRoom?.(normalizedRoom.id) ?? null;
  if (troubleEntry?.is_trouble) {
    const missCount = Number(troubleEntry.miss_count ?? 0);
    const runCount  = Number(troubleEntry.run_count ?? 0);
    const missRate  = Number(troubleEntry.miss_rate ?? 0);
    const pct       = Number.isFinite(missRate) ? Math.round(missRate * 100) : null;
    notes.push({
      type: "trouble",
      text: `⚠ ${this.t("rooms.trouble_missed", { miss: missCount, count: runCount })}${pct !== null ? ` (${pct}%)` : ""}`,
      variant: "warning",
      title: this.t("rooms.trouble_note_title", { pct: pct ?? "?" }),
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
    const titleParts = [this.t("rooms.last_cleaned_label", { value: normalizedRoom.lastCleanedAt })];
    if (normalizedRoom.lastJobMode) {
      titleParts.push(this.t("rooms.mode_label", { value: String(normalizedRoom.lastJobMode) }));
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
                this.t("rooms.progress_label", { pct: progressSnapshot.percent }),
                Number.isFinite(progressSnapshot.elapsedMinutes)
                  ? this.t("rooms.elapsed_label", { value: this._formatLearningMinutes(progressSnapshot.elapsedMinutes) })
                  : "",
                Number.isFinite(progressSnapshot.remainingMinutes)
                  ? this.t("rooms.remaining_label", { value: this._formatLearningMinutes(progressSnapshot.remainingMinutes) })
                  : "",
              ].filter(Boolean).join(" · ")
            )}"
          >
            ${this.t("rooms.percent_complete", { pct: progressSnapshot.percent })}
          </div>

          ${Number.isFinite(progressSnapshot.remainingMinutes) ? `
            <div
              class="evcc-room-status evcc-room-progress-chip evcc-room-progress-chip--remaining"
              title="${this.escapeHtml(
                [
                  this.t("rooms.progress_label", { pct: progressSnapshot.percent }),
                  Number.isFinite(progressSnapshot.elapsedMinutes)
                    ? this.t("rooms.elapsed_label", { value: this._formatLearningMinutes(progressSnapshot.elapsedMinutes) })
                    : "",
                  this.t("rooms.remaining_label", { value: this._formatLearningMinutes(progressSnapshot.remainingMinutes) }),
                ].filter(Boolean).join(" · ")
              )}"
            >
              ${this.t("rooms.remaining_left", { value: this._formatLearningMinutes(progressSnapshot.remainingMinutes) })}
            </div>
          ` : ""}
        </div>
      `
      : "";

  // Composer lock: while a job runs, room toggling is frozen (toggleRoomEnabled no-ops); mark the
  // card so the click reads as inert rather than silently doing nothing.
  const runLocked = Boolean(state?.hasActiveRun?.());
  return `
    <div
      class="evcc-room-card ${normalizedRoom.enabled ? "is-enabled" : "is-disabled"} ${runLocked ? "evcc-room-card--run-locked" : ""} ${dragSourceClass} ${dragTargetClass} ${roomFillClass} ${roomConfidenceClass}"
      data-room-card-toggle="true"
      data-room-id="${normalizedRoom.id}"
      data-map-id="${this.escapeHtml(normalizedRoom.mapId)}"
      data-enabled="${normalizedRoom.enabled ? "true" : "false"}"
      data-order-drop-target
      data-scope="rooms"
      data-item-id="${normalizedRoom.id}"
      role="button"
      tabindex="0"
      aria-disabled="${runLocked ? "true" : "false"}"
      aria-pressed="${normalizedRoom.enabled ? "true" : "false"}"
      aria-label="${this.escapeHtml(normalizedRoom.enabled ? this.t("rooms.exclude_room_aria", { name: normalizedRoom.name }) : this.t("rooms.include_room_aria", { name: normalizedRoom.name }))}"
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
              title="${this.t("rooms.move_room")}"
            >${this.t("rooms.move")}</button>

            <button
              type="button"
              class="evcc-chip evcc-chip--icon evcc-order-drag-handle"
              data-order-drag-item
              data-scope="rooms"
              data-item-id="${normalizedRoom.id}"
              draggable="true"
              title="${this.t("rooms.drag_to_reorder")}"
            >⋮⋮</button>
          </div>

          <button
            type="button"
            class="evcc-room-settings-hit-target"
            data-action="open-room-settings"
            data-room-id="${normalizedRoom.id}"
            data-map-id="${this.escapeHtml(normalizedRoom.mapId)}"
            title="${this.t("rooms.room_settings")}"
            aria-label="${this.t("rooms.open_room_settings_aria", { name: this.escapeHtml(normalizedRoom.name) })}"
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
                  // Title resolved by note TYPE — NOT by matching the English
                  // text (which breaks the moment the text is translated).
                  const fallbackTitle =
                    note.type === "no_learned_data"
                      ? this.t("rooms.note_no_learned_data_title")
                      : note.type === "runs_to_reliable"
                        ? this.t("rooms.note_runs_to_reliable_title", { count: note.count ?? "?" })
                        : note.type === "intensity_mismatch"
                          ? this.t("rooms.note_intensity_mismatch_title")
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
      // Theme-preview swatches set this so their floor texture renders even when room-card
      // textures are toggled off (a preview should preview regardless of that display toggle).
      forceFloorTexture: Boolean(room?.force_floor_texture ?? room?.forceFloorTexture),
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

  /**
   * Map a BUILT-IN profile name to its i18n key, or null for user-created
   * profiles (no key — the user's own label is shown verbatim). Single source of
   * truth for the name→key mapping, shared by _roomProfileLabel and the
   * room-editor preset chips so the two can't drift.
   */
  proto._builtInProfileI18nKey = function (profile) {
    const value = String(profile ?? "").trim();
    if (!value) return "rooms.profile_standard";
    if (value.toLowerCase() === "custom") return "rooms.profile_custom";
    if (value === "vacuum_quick") return "rooms.profile_vacuum_only_quick";
    if (value === "vacuum_deep") return "rooms.profile_vacuum_only_deep";
    if (value === "vacuum_mop_quick") return "rooms.profile_quick";
    if (value === "vacuum_mop_deep") return "rooms.profile_deep";
    if (value === "user_1") return "rooms.profile_user_1";
    return null;
  };

  proto._roomProfileLabel = function (profile) {
    const key = this._builtInProfileI18nKey(profile);
    if (key) return this.t(key);

    return String(profile ?? "").trim()
      .replace(/[_-]+/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  };

  proto._formatCleanMode = function (value) {
    const raw = String(value ?? "").trim().toLowerCase();

    if (raw === "vacuum_mop") return this.t("rooms.mode_vacuum_mop");
    if (raw === "vacuum and mop") return this.t("rooms.mode_vacuum_mop");
    if (raw === "vacuum") return this.t("rooms.mode_vacuum");
    if (raw === "mop") return this.t("rooms.mode_mop");

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
