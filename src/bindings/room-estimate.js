/**
 * ============================================================
 * BINDINGS: ROOM ESTIMATE MODAL
 * ============================================================
 *
 * Wires the room estimate modal — close button in the modal host.
 *
 * ============================================================
 */

/**
 * Mix room estimate binding methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardBindings prototype to extend.
 */
export function applyRoomEstimateBindings(proto) {
  proto._bindRoomEstimate = function () {
    // Queue-chip launch is bound from rooms.js.
  };

  proto._bindRoomEstimateHost = function (host) {
    if (!host) return;

    host.querySelectorAll("[data-action='close-room-estimate']").forEach((btn) => {
      btn.addEventListener("click", () => {
        this.card._state.closeRoomEstimateModal?.();
        this.card._scheduleRender();
      });
    });
  };
}
