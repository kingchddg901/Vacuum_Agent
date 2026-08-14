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
 * Threshold rationale — NARROW **or** SHORT is mobile:
 *   - iPhone portrait widths range 360-430px. All firmly mobile.
 *   - iPad portrait is 768px. Gets desktop layout, which fits fine.
 *   - 600 is the conventional Material breakpoint between phone and
 *     tablet, and matches Lovelace's existing card-vs-grid behavior.
 *
 * THE HEIGHT RULE EXISTS BECAUSE THE WIDTH RULE WAS WRONG ABOUT LANDSCAPE.
 * This comment used to read: "Phone landscape lands ~720-900px depending on
 * device. Desktop layout there is also fine — landscape proportions are
 * desktop-like even on a phone." It is not fine, and the reasoning inverted
 * the problem. Landscape is desktop-like in ASPECT and the opposite of
 * desktop in the dimension that actually matters: rotating a 390x844 phone
 * gives ~844x390, so the card cleared the 600px width gate and dropped its
 * entire compact chrome — mobile header, 44px tap floors, the 22vh preview
 * cap, the bounded chip band — at the exact moment it had 390px of height
 * instead of 844. Reported from a phone: "it reads the wider viewpoint and
 * tries to render in desktop mode. But it's not really that wide, and it has
 * no height at that point."
 *
 * 500px of height clears a landscape phone (~390-430) without catching a
 * normal desktop window. A desktop browser dragged shorter than that does get
 * the compact shell, and that is intended rather than a side effect: it has no
 * vertical room either, which is the whole thing the compact shell is for.
 */

const MOBILE_MAX_WIDTH = 600;
const COMPACT_MAX_HEIGHT = 500;

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
   * Set the viewport from measured size. Returns true if the label changed
   * (caller should re-render), false otherwise.
   *
   * WIDTH is the card's own measured width — a card in a narrow grid cell
   * should render compact even on a wide screen.
   *
   * HEIGHT is the WINDOW's, not the card's, and deliberately so: as a
   * dashboard card the host's height is content-driven, so measuring it would
   * feed the layout its own output. The window is the real constraint on
   * vertical room, and in panel mode the window IS the card.
   *
   * Height is optional so a caller with no window (tests, SSR) keeps the
   * width-only behaviour rather than being forced into a guess.
   */
  proto.setViewportFromSize = function (widthPx, heightPx) {
    const h = Number.isFinite(heightPx)
      ? heightPx
      : (typeof window !== "undefined" ? window.innerHeight : Infinity);
    const next =
      (widthPx < MOBILE_MAX_WIDTH || h < COMPACT_MAX_HEIGHT) ? "mobile" : "desktop";
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
