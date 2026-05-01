/**
 * ============================================================
 * BINDINGS: BASE STATION
 * ============================================================
 *
 * Wires DOM interactions in the Base Station view — dock action
 * buttons and pause timeout selector.
 *
 * ============================================================
 */

/**
 * Mix base station binding methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardBindings prototype to extend.
 */
export function applyBaseStationBindings(proto) {

  /**
   * Attach all Base Station view event handlers — pause timeout selector and dock action buttons.
   */
  proto._bindBaseStation = function () {
    this.card._onAll("[data-pause-timeout-minutes]", "click", async (e) => {
      const rawMinutes = e.currentTarget?.dataset?.pauseTimeoutMinutes;
      const minutes = Number(rawMinutes);
      if (!Number.isFinite(minutes) || !this.card._actions) return;

      try {
        const payload = await this.card._actions.setPauseTimeoutSettings?.({
          vacuum_entity_id: this.card._state.vacuumEntityId?.(),
          pause_timeout_minutes_default: minutes,
        });

        if (payload) {
          this.card._state.setPauseTimeoutSettings?.(payload);
        }

        this.card._scheduleRender();
      } catch (err) {
        console.error("[eufy-vacuum-command-center] Failed to set pause timeout:", err);
      }
    });

    this.card._onAll("[data-dock-action]", "click", async (e) => {
      const action = e.currentTarget?.dataset?.dockAction;
      if (!action || !this.card._actions) return;

      const actionMap = {
        wash_mop: "washMop",
        dry_mop: "dryMop",
        stop_dry_mop: "stopDryMop",
        empty_dust: "emptyDust",
      };

      const method = actionMap[action];
      if (!method || typeof this.card._actions[method] !== "function") return;

      this.card._state.beginDockAction?.(action);
      this.card._scheduleRender();

      try {
        await this.card._actions[method]();
      } finally {
        this.card._state.endDockAction?.();
        await this.card.refreshDashboardSnapshot?.();
        await this.card.refreshDockActionStatus?.();
        this.card._scheduleRender();
      }
    });
  };
}
