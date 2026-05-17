/**
 * Mobile shell bindings.
 *
 * Wires the open/close behavior of the overflow ("More") sheet on
 * the mobile bottom nav. View switching itself is handled by the
 * standard [data-view] nav binding, so this module only has to
 * worry about the sheet's visibility.
 *
 * State: card._mobileMoreOpen (boolean). Toggled by the More button
 * in the bottom nav; cleared by backdrop tap, sheet-item tap, and
 * any view change. Initialised in main.js constructor.
 */

export function applyMobileShellBindings(proto) {

  proto._bindMobileShell = function () {
    const card = this.card;

    // More-button → toggle open/closed.
    card._onAll("[data-action='mobile-more-toggle']", "click", () => {
      card._mobileMoreOpen = !card._mobileMoreOpen;
      card._scheduleRender();
    });

    // Backdrop → close without selecting.
    card._onAll("[data-action='mobile-more-close']", "click", () => {
      if (!card._mobileMoreOpen) return;
      card._mobileMoreOpen = false;
      card._scheduleRender();
    });

    // Sheet item → the [data-view] handler in nav.js fires first and
    // switches the view. We follow up to close the sheet so the user
    // lands on the new view with a clean bottom-nav state.
    card._onAll("[data-action='mobile-more-select']", "click", () => {
      if (!card._mobileMoreOpen) return;
      card._mobileMoreOpen = false;
      // _scheduleRender is already queued by setView; calling it
      // again is a no-op thanks to the microtask coalescing.
      card._scheduleRender();
    });
  };
}
