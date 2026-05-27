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
 * Fallback idempotency tracking for hosts that don't carry a `dataset`
 * (ShadowRoot, Document, Window). Keyed by host element; the inner Set
 * holds the event names already bound on that host. WeakMap allows the
 * host element to be GC'd without leaking.
 */
const _boundEventsMap = new WeakMap();

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
   * Add an event listener to a single element. **Idempotent** — if this
   * element + event pair has already been bound by a previous `_on` call,
   * the new call is a no-op.
   *
   * WHY idempotent: bindEvents() re-runs after every render. When a render
   * doesn't actually replace the element (viewHtml unchanged), calling
   * addEventListener again stacks another listener — every click then
   * fires the handler N times where N is the number of renders since the
   * element was last replaced. For toggle handlers this looks like
   * "clicking sometimes doesn't take"; for handlers that open a file
   * picker, clicking once opens N pickers in sequence.
   *
   * Tracking strategy:
   * - Standard DOM elements use a per-event `dataset` attribute. Replaced
   *   DOM (innerHTML wipe) gets a fresh element with no marker, so the
   *   next bind attaches a new listener correctly.
   * - Hosts without `dataset` (ShadowRoot, Document, Window) fall back
   *   to a module-level WeakMap. These hosts don't get destroyed by
   *   render cycles, so the WeakMap entry persists for the host's
   *   lifetime — which is exactly what we want.
   *
   * @param {EventTarget|null} el
   * @param {string} event - DOM event name (e.g. "click")
   * @param {EventListener} handler
   * @param {AddEventListenerOptions} [options] - passed through to
   *   `addEventListener`. Required for `{passive: false}` listeners on
   *   wheel/touchstart/touchmove (the only way to keep them preventable).
   *
   * No-ops if el is null.
   */
  card._on = function (el, event, handler, options) {
    if (!el) return;
    if (el.dataset !== undefined) {
      // Standard DOM elements: per-event dataset marker.
      const key = `evccBound${event.charAt(0).toUpperCase()}${event.slice(1)}`;
      if (el.dataset[key] === "1") return;
      el.dataset[key] = "1";
    } else {
      // ShadowRoot / Document / Window: dataset doesn't exist, use a WeakMap.
      let bound = _boundEventsMap.get(el);
      if (!bound) {
        bound = new Set();
        _boundEventsMap.set(el, bound);
      }
      if (bound.has(event)) return;
      bound.add(event);
    }
    el.addEventListener(event, handler, options);
  };

  /**
   * Add an event listener to all elements matching selector. Each element
   * is bound through `_on`, so every site is idempotent automatically.
   */
  card._onAll = function (selector, event, handler, options) {
    this.$all(selector).forEach((el) => this._on(el, event, handler, options));
  };
}