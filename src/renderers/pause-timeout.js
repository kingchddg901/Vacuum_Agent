// Pause-timeout control — how long a paused run may sit before it is cancelled
// and the robot sent home.
//
// WHY THIS IS ITS OWN MODULE, AND NOT IN base-station.js WHERE IT STARTED.
// The Base Station tab is capability-gated on `supports_base_station`, so a vacuum
// without a settable dock never rendered it — and a pause timeout is not a dock
// feature, it governs the job lifecycle. The result was a setting with no reachable
// UI on those vacuums, silently holding whatever default it was handed. Found on a
// live install where a Roborock sat at "no timeout" with nothing to reveal it.
//
// It renders in the rooms sidebar now, beside Run Profiles and Saved Zones, for
// EVERY vacuum. One home rather than two: rendering it here for dockless vacuums and
// there for the rest would leave a condition to get wrong and a user who learns one
// location and cannot find it on their other robot.

export function applyPauseTimeoutRenderer(proto) {
  /**
   * The sidebar panel. `0` is a real, selectable option.
   *
   * OFF USED TO BE UNREACHABLE. The chips were 15/30/45/60 while
   * `set_pause_timeout_settings` accepted 0 — so "no timeout" was a state the
   * interface could produce silently, via a service call, but never display or
   * offer. That gap is exactly how a vacuum ended up with the timeout disabled and
   * no way to see it. If a value is reachable by service it has to be visible here.
   */
  proto.renderPauseTimeoutPanel = function (state) {
    const current = state.pauseTimeoutMinutesDefault?.();
    const options = [0, 15, 30, 45, 60];

    return `
      <aside class="evcc-run-profiles-panel">
        <div class="evcc-run-profiles-panel-header">
          <div>
            <div class="evcc-run-profiles-title">${this.t("pause_timeout.title")}</div>
            <div class="evcc-run-profiles-subtitle">
              ${this.t("pause_timeout.subtitle")}
            </div>
          </div>
        </div>

        <div class="evcc-chips">
          ${options.map((minutes) => `
            <button
              type="button"
              class="evcc-chip ${current === minutes ? "active" : ""}"
              data-pause-timeout-minutes="${minutes}"
            >${minutes === 0
                ? this.t("common.off")
                : this.t("pause_timeout.minutes_short", { minutes })}</button>
          `).join("")}
        </div>
      </aside>
    `;
  };
}
