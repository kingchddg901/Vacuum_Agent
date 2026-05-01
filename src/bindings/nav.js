/**
 * ============================================================
 * BINDINGS: NAVIGATION
 * ============================================================
 *
 * Wires the view tab strip — clicking a [data-view] button calls
 * card.setView() and schedules a re-render.
 *
 * ============================================================
 */

/**
 * Mix navigation binding methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardBindings prototype to extend.
 */
export function applyNavBindings(proto) {

  /**
   * Attach click handlers to all [data-view] tab buttons.
   * Handlers are re-attached after every render because the DOM is replaced.
   */
  proto._bindNav = function () {
    this.card._onAll("[data-view]", "click", (e) => {
      const view = e.currentTarget.dataset.view;
      if (view) this.card.setView(view);
    });
  };
}