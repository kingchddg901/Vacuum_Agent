/**
 * ============================================================
 * BADGE STATE MARKS — redundant non-color cue
 * ============================================================
 *
 * Six per-state SVG marks so a mapping-bounds badge is identifiable
 * WITHOUT color — colour resolves only five groups (likely & warn
 * share the warning hue by design), so the shape channel is what
 * disambiguates the sixth, and it covers monochromacy + every CVD
 * type at once.
 *
 * All six are authored from ONE source: same 16×16 viewBox, same
 * stroke weight, `currentColor` (each inherits its badge's state
 * color). No ASCII/symbol-font mixing — fonts land glyphs at
 * inconsistent weights/baselines at dot size, which breaks both
 * legibility and the grayscale-distinguishability check.
 *
 * The shapes are chosen to stay distinct in FLAT GRAYSCALE at dot
 * size (verified by harness/tests/shape-marks.spec.mjs):
 *   ok        ✓  open check     (success — safety-critical pair)
 *   outlier   ✕  closed cross   (error   — safety-critical pair)
 *   warn      !  bar + dot
 *   likely    ◐  half-filled disc (partial confidence)
 *   excluded  –  heavy dash     (struck out)
 *   baseline  ◆  filled diamond (anchor / reference)
 *
 * ok (✓) and outlier (✕) carry the good-vs-bad load and differ in
 * stroke topology (open path vs closed crossing); they're weighted to
 * survive the small render.
 * ============================================================
 */

export const MARK_VIEWBOX = "0 0 16 16";

/** Inner SVG markup per state (currentColor; consistent stroke weight). */
export const BADGE_MARK_PATHS = Object.freeze({
  ok: `<path d="M3.4 8.6l3 3 6.2-7" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>`,
  outlier: `<path d="M4.4 4.4l7.2 7.2M11.6 4.4l-7.2 7.2" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>`,
  warn: `<path d="M8 3.2v5.6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><circle cx="8" cy="12.3" r="1.25" fill="currentColor"/>`,
  likely: `<circle cx="8" cy="8" r="5.3" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M8 2.7a5.3 5.3 0 0 1 0 10.6z" fill="currentColor"/>`,
  excluded: `<path d="M3.4 8h9.2" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>`,
  baseline: `<path d="M8 2.4l5.6 5.6-5.6 5.6L2.4 8z" fill="currentColor"/>`,
});

/** Full inline SVG for a badge mark, sized via CSS (.evcc-mrev-badge-mark). */
export function badgeMark(state) {
  const inner = BADGE_MARK_PATHS[state];
  if (!inner) return "";
  return `<svg class="evcc-mrev-badge-mark" viewBox="${MARK_VIEWBOX}" aria-hidden="true" focusable="false">${inner}</svg>`;
}
