/**
 * Viewport state — drives mobile-vs-desktop shell selection.
 *
 * The card mounts once and runs in whichever viewport HA shows it.
 * This module owns the "which shell are we rendering today" decision
 * and the `compact` hint that individual renderers can read when they
 * want to tighten themselves up.
 *
 * Why a single boolean instead of a CSS breakpoint:
 *   - Layouts diverge structurally (bottom-tab vs top-tab nav, drawer
 *     vs side panel, etc.) — too much for CSS hiding to handle cleanly.
 *   - Picking ONE shell at render time keeps the DOM small.
 *   - The detection runs on resize too, so rotating from portrait to
 *     landscape (which on a phone usually means re-evaluating) just
 *     works.
 *
 * Threshold rationale (<600px = mobile):
 *   - iPhone portrait widths range 360-430px. All firmly mobile.
 *   - iPad portrait is 768px. Gets desktop layout, which fits fine.
 *   - Phone landscape lands ~720-900px depending on device. Desktop
 *     layout there is also fine — landscape proportions are desktop-
 *     like even on a phone.
 *   - 600 is the conventional Material breakpoint between phone and
 *     tablet, and matches Lovelace's existing card-vs-grid behavior.
 */

const MOBILE_MAX_WIDTH = 600;

export function applyViewportState(proto) {

  // Defaults to "desktop" so any code that reads viewport before the
  // first measurement runs (e.g. tests, server-rendered hydration)
  // doesn't accidentally get a half-built mobile layout. The card's
  // connectedCallback measures and corrects immediately on mount.
  proto._viewport = "desktop";

  proto.viewport = function () {
    return this._viewport;
  };

  proto.isMobileViewport = function () {
    return this._viewport === "mobile";
  };

  /**
   * Compact rendering hint. Currently coincides with mobile-viewport
   * but is intentionally a separate getter so renderers that want
   * "narrow-card" semantics (e.g. embedded in a 300px-wide grid cell)
   * can opt in independently of true mobile detection.
   */
  proto.isCompactRender = function () {
    return this._viewport === "mobile";
  };

  /**
   * Set the viewport based on a measured width. Returns true if the
   * viewport label changed (caller should re-render), false otherwise.
   */
  proto.setViewportFromWidth = function (widthPx) {
    const next = (widthPx < MOBILE_MAX_WIDTH) ? "mobile" : "desktop";
    if (next === this._viewport) return false;
    this._viewport = next;
    return true;
  };

  /**
   * Manual override — used by tests or by a future "force mobile/desktop"
   * power-user toggle. Returns true if changed.
   */
  proto.setViewport = function (label) {
    if (label !== "mobile" && label !== "desktop") return false;
    if (label === this._viewport) return false;
    this._viewport = label;
    return true;
  };
}

export const VIEWPORT_MOBILE_MAX_WIDTH = MOBILE_MAX_WIDTH;
