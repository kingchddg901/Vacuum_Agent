/**
 * ============================================================
 * BINDINGS: ROOMS
 * ============================================================
 *
 * PURPOSE
 * -------
 * Wires all DOM interactions in the Rooms view.
 *
 * This file owns:
 * - room toggle (include/exclude)
 * - start cleaning button
 * - clear queue button
 * - queue chip tap-to-open settings
 * - queue chip long-press include/exclude toggle
 *
 * WHAT THIS FILE SHOULD NOT CONTAIN
 * ----------------------------------
 * - rendering (lives in renderers/rooms.js)
 * - state logic (lives in state/rooms.js)
 * - service calls (lives in actions/rooms.js)
 *
 * HOW THIS FILE FITS INTO THE SYSTEM
 * -----------------------------------
 * Mixed onto VacuumCardBindings via applyRoomsBindings(proto).
 * _bindRooms() is called from bindEvents() after every render.
 *
 * ============================================================
 */

/**
 * Mix rooms binding methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardBindings prototype to extend.
 */
export function applyRoomsBindings(proto) {

  /**
   * Attach all Rooms view event handlers — room toggles, start/clear actions,
   * and queue chip interactions.
   */
  proto._bindRooms = function () {
    this._bindRoomToggles();
    this._bindRoomActions();
    this._bindQueueChipActions();
  };

  /** Wire room-card toggle clicks to include/exclude rooms from the active queue. */
  proto._bindRoomToggles = function () {
    this.card._onAll("[data-room-card-toggle='true']", "click", async (e) => {
      if (
        e.target.closest(
          "[data-action='open-room-settings'], .evcc-room-settings-hit-target, [data-action='open-order-selector'], [data-order-drag-item]"
        )
      ) {
        return;
      }

      const card = e.currentTarget;
      const roomId = Number(card.dataset.roomId);
      const mapId = String(card.dataset.mapId);
      const enabled = card.dataset.enabled === "true";

      if (!roomId || !mapId) return;

      await this.card._actions.toggleRoomEnabled(mapId, roomId, enabled);
      if (enabled) {
        this.card._state.disableSegmentForRoom?.(roomId);
      } else {
        this.card._state.enableSegmentForRoom?.(roomId);
      }
      this.card._state.clearStartConfirmation?.();
      this.card._state.clearCancelRunConfirmation?.();
      await this.card.refreshDashboardSnapshot?.();
    });

    this.card._onAll("[data-room-card-toggle='true']", "keydown", async (e) => {
      if (e.key !== "Enter" && e.key !== " ") {
        return;
      }

      if (
        e.target.closest(
          "[data-action='open-room-settings'], .evcc-room-settings-hit-target, [data-action='open-order-selector'], [data-order-drag-item]"
        )
      ) {
        return;
      }

      e.preventDefault();

      const card = e.currentTarget;
      const roomId = Number(card.dataset.roomId);
      const mapId = String(card.dataset.mapId);
      const enabled = card.dataset.enabled === "true";

      if (!roomId || !mapId) return;

      await this.card._actions.toggleRoomEnabled(mapId, roomId, enabled);
      if (enabled) {
        this.card._state.disableSegmentForRoom?.(roomId);
      } else {
        this.card._state.enableSegmentForRoom?.(roomId);
      }
      this.card._state.clearStartConfirmation?.();
      this.card._state.clearCancelRunConfirmation?.();
      await this.card.refreshDashboardSnapshot?.();
    });
  };

  /** Wire Start Cleaning and Clear Queue action buttons. */
  proto._bindRoomActions = function () {
  this.card._on(
    this.card.$("[data-action='primary-room-action']:not([disabled])"),
    "click",
    async () => {
      if (this.card._state.cancelRunRequiresConfirmation?.()) {
        await this.card._actions.cancelActiveRun();
        await this.card.refreshDashboardSnapshot?.();
        this.card._scheduleRender();
        return;
      }

      if (this.card._state.hasActiveRun?.()) {
        this.card._state.requestCancelRunConfirmation?.();
        this.card._scheduleRender();
        return;
      }

      if (this.card._state.startRequiresConfirmation?.()) {
        await this.card._actions.startCleaning({
          confirmReducedRun: true,
          confirmToken: this.card._state.startConfirmationToken?.(),
        });
        await this.card.refreshDashboardSnapshot?.();
        this.card._scheduleRender();
        return;
      }

      await this.card._actions.startCleaning();
      await this.card.refreshDashboardSnapshot?.();
      this.card._scheduleRender();
    }
  );

  this.card._on(
    this.card.$("[data-action='cancel-primary-confirmation']"),
    "click",
    () => {
      this.card._state.clearStartConfirmation?.();
      this.card._state.clearCancelRunConfirmation?.();
      this.card._scheduleRender();
    }
  );

  this.card._on(
    this.card.$("[data-action='pause-run']"),
    "click",
    async () => {
      await this.card._actions.pauseActiveRun();
      await this.card.refreshDashboardSnapshot?.();
      this.card._scheduleRender();
    }
  );

  this.card._on(
    this.card.$("[data-action='resume-run']"),
    "click",
    async () => {
      await this.card._actions.resumeActiveRun();
      await this.card.refreshDashboardSnapshot?.();
      this.card._scheduleRender();
    }
  );

  this.card._on(
    this.card.$("[data-action='locate-vacuum']"),
    "click",
    async () => {
      await this.card._actions.locateVacuum();
      this.card._scheduleRender();
    }
  );

  this.card._on(
    this.card.$("[data-action='select-all']"),
    "click",
    async () => {
      this.card._state.clearStartConfirmation?.();
      this.card._state.clearCancelRunConfirmation?.();
      await this.card._actions.selectAllRooms();
      await this.card.refreshDashboardSnapshot?.();
    }
  );

  this.card._on(
    this.card.$("[data-action='clear-queue']"),
    "click",
    async () => {
      this.card._state.clearStartConfirmation?.();
      this.card._state.clearCancelRunConfirmation?.();
      await this.card._actions.clearQueue();
      await this.card.refreshDashboardSnapshot?.();
    }
  );

  /* ======================================================
     LEARNING: DISMISS SUMMARY
     ====================================================== */

  this.card._on(
    this.card.$("[data-action='dismiss-learning-summary']"),
    "click",
    () => {
      this.card._learningController.dismissLearningSummary();
    }
  );

  /* ======================================================
     INCOMPLETE RUN BANNER: DISMISS
     ====================================================== */

  this.card._on(
    this.card.$("[data-action='dismiss-incomplete-run-log']"),
    "click",
    () => {
      this.card._state.clearIncompleteRunLog?.();
      this.card._scheduleRender();
    }
  );

  /* ======================================================
     INCOMPLETE RUN BANNER: QUEUE MISSED ROOMS
     ====================================================== */

  this.card._on(
    this.card.$("[data-action='queue-missed-rooms']"),
    "click",
    async () => {
      const missedRoomIds = this.card._state.incompleteRunMissedRoomIds?.() ?? [];

      // Always clear the banner first so it doesn't re-show on re-render.
      this.card._state.clearIncompleteRunLog?.();
      this.card._state.clearStartConfirmation?.();
      this.card._state.clearCancelRunConfirmation?.();

      if (missedRoomIds.length > 0) {
        await this.card._actions.retryMissedRooms(missedRoomIds);
        await this.card.refreshDashboardSnapshot?.();
      }

      this.card._scheduleRender();
    }
  );
};

  /**
   * Wire queue chip tap (open settings) and long-press (toggle include/exclude).
   *
   * Long-press duration is configurable via `queue_chip_long_press_ms`
   * (config.theme.queue_chip_long_press_ms or config.queue_chip_long_press_ms).
   * Default: 450 ms, clamped 250–1000.
   */
  proto._bindQueueChipActions = function () {
    const chips = Array.from(
      this.card.shadowRoot?.querySelectorAll("[data-queue-chip='true']") ?? []
    );

    const LONG_PRESS_MS = this.card._state.queueChipLongPressMs();
    const DOUBLE_CLICK_DELAY_MS = 280;

    chips.forEach((chip) => {
      let longPressTimer = null;
      let longPressTriggered = false;
      let pointerActive = false;
      let clickTimer = null;

      chip.title = "Click for settings - Double-click for estimate - Hold to remove from queue";

      const clearClickTimer = () => {
        if (clickTimer) {
          window.clearTimeout(clickTimer);
          clickTimer = null;
        }
      };

      const clearPressState = () => {
        if (longPressTimer) {
          window.clearTimeout(longPressTimer);
          longPressTimer = null;
        }
        pointerActive = false;
      };

      const startPress = (event) => {
        if (event.button != null && event.button !== 0) return;

        longPressTriggered = false;
        pointerActive = true;

        chip.classList.add("is-pressing");

        longPressTimer = window.setTimeout(async () => {
          if (!pointerActive) return;

          longPressTriggered = true;
          clearClickTimer();
          chip.classList.remove("is-pressing");
          chip.classList.add("is-long-pressing");

          const roomId = Number(chip.dataset.roomId);
          const mapId = String(chip.dataset.mapId);
          const enabled = chip.dataset.enabled === "true";

          try {
            await this.card._actions.toggleRoomEnabled(mapId, roomId, enabled);
            await this.card.refreshDashboardSnapshot?.();
          } finally {
            chip.classList.remove("is-long-pressing");
          }
        }, LONG_PRESS_MS);
      };

      const cancelPress = () => {
        chip.classList.remove("is-pressing");
        clearPressState();
      };

      chip.addEventListener("pointerdown", startPress);
      chip.addEventListener("pointerup", () => {
        chip.classList.remove("is-pressing");
        clearPressState();
      });
      chip.addEventListener("pointerleave", cancelPress);
      chip.addEventListener("pointercancel", cancelPress);

      chip.addEventListener("click", (event) => {
        if (longPressTriggered) {
          event.preventDefault();
          event.stopPropagation();
          longPressTriggered = false;
          clearClickTimer();
          return;
        }

        const roomId = Number(chip.dataset.roomId);
        const mapId = String(chip.dataset.mapId);
        if (!roomId || !mapId) return;

        clearClickTimer();
        clickTimer = window.setTimeout(() => {
          this.card._state.openRoomEditor(roomId, mapId);
          this.card._scheduleRender();
          clickTimer = null;
        }, DOUBLE_CLICK_DELAY_MS);
      });

      chip.addEventListener("dblclick", (event) => {
        event.preventDefault();
        event.stopPropagation();

        if (longPressTriggered) {
          longPressTriggered = false;
          clearClickTimer();
          return;
        }

        clearClickTimer();

        const roomId = Number(chip.dataset.roomId);
        const mapId = String(chip.dataset.mapId);
        if (!roomId || !mapId) return;

        this.card._state.openRoomEstimateModal?.(roomId, mapId);
        this.card._scheduleRender();
      });

      chip.addEventListener("contextmenu", (event) => {
        event.preventDefault();
      });
    });
  };
}
