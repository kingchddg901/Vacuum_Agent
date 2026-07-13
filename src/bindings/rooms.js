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
        // Swallow a confirmation click that lands within the 700 ms
        // grace window — protects against a rapid double-tap of the
        // primary button accidentally killing a running job.
        if (this.card._state.cancelRunConfirmGuardActive?.()) {
          return;
        }
        await this.card._actions.cancelActiveRun();
        await this.card.refreshDashboardSnapshot?.();
        this.card.showToast?.(this.t("bind_rooms.cancel_sent"), { kind: "info", ttl: 4000 });
        this.card._scheduleRender();
        return;
      }

      if (this.card._state.hasActiveRun?.()) {
        this.card._state.requestCancelRunConfirmation?.();
        this.card._scheduleRender();
        return;
      }

      // A: an applied STEPPED profile runs its charge steps via start_run_profile — the flat
      // start_selected_rooms path would drop the charge + the extra passes.
      const stepProfileId = this.card._state.pendingStepRunProfileId?.();
      if (stepProfileId) {
        const result = await this.card._actions.startRunProfile({
          vacuum_entity_id: this.card._state.vacuumEntityId?.(),
          map_id: this.card._state.activeMapId?.(),
          profile_id: stepProfileId,
        });
        if (result?.ok === false) {
          this.card.showToast?.((result.reason ? this.esc(result.reason) : this.t("bind_run_profiles.unable_run")), { kind: "error" });
        } else {
          await this.card.refreshDashboardSnapshot?.();
        }
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

  // Strict-order opt-in toggle (per-run) in the order-advisory block.
  this.card._on(
    this.card.$("[data-action='toggle-strict-order']"),
    "click",
    () => {
      this.card._state.toggleStrictOrder?.();
      this.card._scheduleRender();
    }
  );

  // Collapse/expand the pre-run "This run" stepped preview.
  this.card._on(
    this.card.$("[data-action='toggle-stepped-preview']"),
    "click",
    () => {
      this.card._state.toggleSteppedPreviewCollapsed?.();
      this.card._scheduleRender();
    }
  );

  // Collapse/expand the live-queue monitor panel.
  this.card._on(
    this.card.$("[data-action='toggle-live-queue']"),
    "click",
    () => {
      this.card._state.toggleLiveQueueCollapsed?.();
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
      this.card.showToast?.(this.t("bind_rooms.locate_sent"), { kind: "info" });
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
      // Two-tap guard: same shape as cancel-run. First click arms,
      // second click within the auto-clear window fires the service.
      if (this.card._state.clearQueueRequiresConfirmation?.()) {
        // Swallow rapid double-tap inside the 700 ms grace window.
        if (this.card._state.clearQueueConfirmGuardActive?.()) {
          return;
        }
        this.card._state.clearClearQueueConfirmation?.();
        this.card._state.clearStartConfirmation?.();
        this.card._state.clearCancelRunConfirmation?.();
        await this.card._actions.clearQueue();
        await this.card.refreshDashboardSnapshot?.();
        this.card.showToast?.(this.t("bind_rooms.queue_cleared"), { kind: "success" });
        this.card._scheduleRender();
        return;
      }

      // 5s auto-clear is handled inside the confirmation registry;
      // no per-card timer bookkeeping here.
      this.card._state.requestClearQueueConfirmation?.();
      this.card._scheduleRender();
    }
  );

  /* ======================================================
     QUEUE BREAKS: add charge / add wait / clear
     ====================================================== */

  this.card._on(
    this.card.$("[data-action='add-charge-break']"),
    "click",
    async () => {
      await this.card._actions.addQueueBreak("charge_wait");
      await this.card.refreshDashboardSnapshot?.();
      this.card._scheduleRender();
    }
  );

  this.card._on(
    this.card.$("[data-action='add-wait-break']"),
    "click",
    async () => {
      await this.card._actions.addQueueBreak("wait");
      await this.card.refreshDashboardSnapshot?.();
      this.card._scheduleRender();
    }
  );

  this.card._on(
    this.card.$("[data-action='clear-queue-breaks']"),
    "click",
    async () => {
      await this.card._actions.clearQueueBreaks();
      await this.card.refreshDashboardSnapshot?.();
      this.card._scheduleRender();
    }
  );

  /* Live-queue step chips: edit a break's charge %/wait minutes, or remove it.
     (Reorder is the shared open-order-selector binding on the move handles.) */
  this.card._onAll("[data-queue-break-charge-index]", "change", async (e) => {
    const bi = Number(e.currentTarget.dataset.queueBreakChargeIndex);
    const val = Number(e.currentTarget.value);
    // Empty/junk input coerces to 0 (< the schema minimum); re-render to revert the display
    // to the stored value rather than firing a doomed service call.
    if (!Number.isFinite(bi) || !Number.isFinite(val) || val < 1) { this.card._scheduleRender(); return; }
    await this.card._actions.updateQueueBreakParam(bi, { targetBatteryPercent: val });
    await this.card.refreshDashboardSnapshot?.();
    this.card._scheduleRender();
  });

  this.card._onAll("[data-queue-break-wait-index]", "change", async (e) => {
    const bi = Number(e.currentTarget.dataset.queueBreakWaitIndex);
    const val = Number(e.currentTarget.value);
    if (!Number.isFinite(bi) || !Number.isFinite(val) || val < 1) { this.card._scheduleRender(); return; }
    await this.card._actions.updateQueueBreakParam(bi, { waitMinutes: val });
    await this.card.refreshDashboardSnapshot?.();
    this.card._scheduleRender();
  });

  this.card._onAll("[data-action='remove-queue-break']", "click", async (e) => {
    const bi = Number(e.currentTarget.dataset.breakIndex);
    if (!Number.isFinite(bi)) return;
    await this.card._actions.removeQueueBreak(bi);
    await this.card.refreshDashboardSnapshot?.();
    this.card._scheduleRender();
  });

  /* Zone picker: open, toggle a zone in the multi-select, confirm (add the whole
     selection as one zone step), cancel. */
  this.card._on(this.card.$("[data-action='open-zone-picker']"), "click", () => {
    this.card._state.openQueueZonePicker?.();
    this.card._scheduleRender();
  });

  this.card._onAll("[data-action='toggle-zone-pick']", "click", (e) => {
    const id = e.currentTarget.dataset.zoneId;
    if (id == null) return;
    this.card._state.toggleQueueZonePick?.(id);
    this.card._scheduleRender();
  });

  this.card._onAll("[data-action='close-zone-picker']", "click", () => {
    this.card._state.closeQueueZonePicker?.();
    this.card._scheduleRender();
  });

  this.card._on(this.card.$("[data-action='confirm-zone-picker']"), "click", async () => {
    const ids = this.card._state.queueZonePickerSelected?.() ?? [];
    this.card._state.closeQueueZonePicker?.();
    if (ids.length) {
      await this.card._actions.addQueueZone(ids);
      await this.card.refreshDashboardSnapshot?.();
    }
    this.card._scheduleRender();
  });

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
      const count = missedRoomIds.length;

      // Always clear the banner first so it doesn't re-show on re-render.
      this.card._state.clearIncompleteRunLog?.();
      this.card._state.clearStartConfirmation?.();
      this.card._state.clearCancelRunConfirmation?.();

      if (count === 0) {
        this.card._scheduleRender();
        return;
      }

      let result;
      try {
        result = await this.card._actions.retryMissedRooms(missedRoomIds);
        await this.card.refreshDashboardSnapshot?.();
      } catch (err) {
        console.error("[eufy-vacuum-command-center] retryMissedRooms failed", err);
      }

      const ok = result !== null && result !== undefined;
      this.card.showToast?.(
        ok ? this.t("bind_rooms.requeued_missed", { count })
           : this.t("bind_rooms.could_not_retry_missed"),
        { kind: ok ? "success" : "error" }
      );

      this.card._scheduleRender();
    }
  );

  /* ======================================================
     LEARNING-PROCESSING: BOX-LEVEL TOGGLE + PROCESS PENDING
     ====================================================== */

  this.card._on(
    this.card.$("[data-action='toggle-learning-processing']"),
    "change",
    async (e) => {
      const enabled = !!e?.target?.checked;
      try {
        await this.card._actions.setLearningProcessing?.(enabled);
        await this.card.refreshDashboardSnapshot?.();
      } catch (err) {
        console.error("[eufy-vacuum-command-center] setLearningProcessing failed", err);
      }
      this.card._scheduleRender();
    }
  );

  this.card._on(
    this.card.$("[data-action='process-pending-runs']"),
    "click",
    async () => {
      try {
        await this.card._actions.processPendingRuns?.();
        await this.card.refreshDashboardSnapshot?.();
      } catch (err) {
        console.error("[eufy-vacuum-command-center] processPendingRuns failed", err);
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

    // In queue mode a chip carries its own controls (reorder grip, break value input, remove).
    // Presses/clicks that originate on those must NOT trigger the chip's settings/long-press —
    // each sub-control has its own binding.
    const isChipSubControl = (event) =>
      !!event?.target?.closest?.(
        ".evcc-queue-chip-move, .evcc-queue-chip-remove, .evcc-queue-chip-input"
      );

    chips.forEach((chip) => {
      let longPressTimer = null;
      let longPressTriggered = false;
      let pointerActive = false;
      let clickTimer = null;

      chip.title = this.t("bind_rooms.chip_title");

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
        if (isChipSubControl(event)) return;

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

      this.card._on(chip, "pointerdown", startPress);
      this.card._on(chip, "pointerup", () => {
        chip.classList.remove("is-pressing");
        clearPressState();
      });
      this.card._on(chip, "pointerleave", cancelPress);
      this.card._on(chip, "pointercancel", cancelPress);

      this.card._on(chip, "click", (event) => {
        if (isChipSubControl(event)) return;

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

      this.card._on(chip, "dblclick", (event) => {
        if (isChipSubControl(event)) return;

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

      this.card._on(chip, "contextmenu", (event) => {
        event.preventDefault();
      });
    });
  };
}
