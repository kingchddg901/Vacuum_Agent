// Pause-timeout control bindings.
//
// Lives beside its renderer (renderers/pause-timeout.js) rather than in
// bindings/base-station.js where it started. The control moved out of the Base
// Station tab because that tab is capability-gated on `supports_base_station`, so a
// vacuum without a settable dock had no reachable UI for a job-lifecycle setting.
//
// The handler would have kept working from its old home — bindEvents() runs every
// binder on every render and `_onAll` delegates across the whole shadow root — which
// is exactly why it needed moving rather than leaving. A binding that still works
// from the wrong file is worse than one that breaks: nothing fails, and the next
// person greps base-station.js for a control that is not there.

export function applyPauseTimeoutBindings(proto) {
  /** Wire the pause-timeout chips in the rooms sidebar. */
  proto._bindPauseTimeout = function () {
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
          // 0 is a real choice, not a failure to choose — say so explicitly rather
          // than reporting "set to 0 min", which reads like a bug.
          const label = minutes === 0
            ? this.t("bind_pause_timeout.auto_cancel_disabled")
            : this.t("bind_pause_timeout.set", { minutes });
          this.card.showToast?.(label, { kind: "success" });
        } else {
          this.card.showToast?.(this.t("bind_pause_timeout.could_not_save"), { kind: "error" });
        }

        this.card._scheduleRender();
      } catch (err) {
        console.error("[eufy-vacuum-command-center] Failed to set pause timeout:", err);
        this.card.showToast?.(this.t("bind_pause_timeout.could_not_save"), { kind: "error" });
      }
    });
  };
}
