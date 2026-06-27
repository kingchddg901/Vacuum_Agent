/**
 * ============================================================
 * BINDINGS: LANGUAGE CONTROL
 * ============================================================
 *
 * Wires the header globe control:
 *   - toggle-language-menu  → open/close the dropdown
 *   - close-language-menu   → the backdrop (outside click)
 *   - set-language          → pick a locale (or "auto")
 *
 * All idempotent via card._onAll, re-attached after every render like the rest
 * of the bindings. The control lives in BOTH the desktop and mobile headers; a
 * single selector set covers both.
 *
 * ============================================================
 */

/**
 * Mix language-control binding methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardBindings prototype to extend.
 */
export function applyLanguageBindings(proto) {

  proto._bindLanguage = function () {
    // Globe button: toggle the dropdown. stopPropagation so the click doesn't
    // immediately bubble to any outside-close handler.
    this.card._onAll("[data-action='toggle-language-menu']", "click", (e) => {
      e.stopPropagation();
      this.card.toggleLanguageMenu();
    });

    // Backdrop: any click outside the menu closes it.
    this.card._onAll("[data-action='close-language-menu']", "click", () => {
      this.card.closeLanguageMenu();
    });

    // Option pick: apply the chosen language (or "auto").
    this.card._onAll("[data-action='set-language']", "click", (e) => {
      const lang = e.currentTarget?.dataset?.lang;
      if (lang) this.card.setLanguageOverride(lang);
    });
  };
}
