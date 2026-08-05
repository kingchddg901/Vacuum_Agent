/**
 * ============================================================
 * BINDINGS: LANGUAGE CONTROL
 * ============================================================
 *
 * Wires the header globe control:
 *   - toggle-language-menu  → open/close the dropdown
 *   - close-language-menu   → the backdrop (outside click)
 *   - set-language          → pick a locale (or "auto")
 *   - set-font              → pick the accessibility typeface
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

    // Accessibility typeface. Deliberately does NOT close the menu: the option
    // renders in the font it offers, so staying open lets the user see the
    // whole card change and switch straight back if it is not for them.
    this.card._onAll("[data-action='set-font']", "click", (e) => {
      const font = e.currentTarget?.dataset?.font;
      if (font) this.card.setUiFont(font);
    });
  };
}
