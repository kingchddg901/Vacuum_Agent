/**
 * ============================================================
 * BINDINGS: CORE
 * ============================================================
 *
 * PURPOSE
 * -------
 * Low-level DOM event wiring helpers used by every bindings
 * module.
 *
 * This file owns:
 * - $()       — querySelector shorthand
 * - $all()    — querySelectorAll shorthand
 * - _on()     — add listener to one element
 * - _onAll()  — add listener to all matching elements
 *
 *
 * WHAT THIS FILE SHOULD NOT CONTAIN
 * ----------------------------------
 * - feature-specific binding logic
 * - state reads
 * - rendering
 * - service calls
 *
 *
 * HOW THIS FILE FITS INTO THE SYSTEM
 * -----------------------------------
 * These methods are added directly onto the card element
 * in main.js so they are available everywhere via `this`.
 *
 * ============================================================
 */

/**
 * Install low-level shadowRoot querySelector helpers and event binding utilities
 * directly onto the card element instance.
 * Called once in the card constructor; every bindings module depends on these.
 *
 * @param {HTMLElement} card - The card custom element instance.
 */
export function applyCardDomHelpers(card) {

  /**
   * Return the first element matching selector within shadowRoot.
   */
  card.$ = function (selector) {
    return this.shadowRoot?.querySelector(selector) ?? null;
  };

  /**
   * Return all elements matching selector within shadowRoot.
   */
  card.$all = function (selector) {
    return [...(this.shadowRoot?.querySelectorAll(selector) ?? [])];
  };

  /**
   * Add an event listener to a single element.
   * No-ops if el is null.
   */
  card._on = function (el, event, handler) {
    el?.addEventListener(event, handler);
  };

  /**
   * Add an event listener to all elements matching selector.
   */
  card._onAll = function (selector, event, handler) {
    this.$all(selector).forEach((el) => el.addEventListener(event, handler));
  };
}