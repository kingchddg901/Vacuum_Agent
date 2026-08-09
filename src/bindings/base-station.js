/**
 * ============================================================
 * BINDINGS: BASE STATION
 * ============================================================
 *
 * Wires DOM interactions in the Base Station view — the dock action
 * buttons. The pause-timeout selector moved to bindings/pause-timeout.js
 * when its control left this capability-gated tab for the rooms sidebar.
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
   * Attach all Base Station view event handlers — the dock action buttons.
   *
   * The pause-timeout selector used to live here and now has its own module
   * (bindings/pause-timeout.js), because its control moved out of this
   * capability-gated tab and into the rooms sidebar.
   */
  proto._bindBaseStation = function () {

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

      const labels = {
        wash_mop: this.t("bind_base_station.mop_wash_sent"),
        dry_mop: this.t("bind_base_station.mop_dry_sent"),
        stop_dry_mop: this.t("bind_base_station.stop_drying_sent"),
        empty_dust: this.t("bind_base_station.dust_empty_sent"),
      };

      let ok = false;
      try {
        const result = await this.card._actions[method]();
        ok = result !== null;
      } finally {
        this.card._state.endDockAction?.();
        await this.card.refreshDashboardSnapshot?.();
        await this.card.refreshDockActionStatus?.();
        this.card._scheduleRender();
      }

      this.card.showToast?.(
        ok ? (labels[action] ?? this.t("bind_base_station.dock_action_sent"))
           : this.t("bind_base_station.dock_action_failed", { action: action.replace(/_/g, " ") }),
        { kind: ok ? "success" : "error" }
      );
    });
  };
}
