/**
 * ============================================================
 * THEME TOKEN HELPERS
 * ============================================================
 *
 * PURPOSE
 * -------
 * Central helper layer for helper-driven theme token registry
 * authoring.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * Group files are the maintainable authoring surface for the
 * registry. These helpers keep grouped token entries consistent
 * while preserving the flat backend persistence contract.
 *
 * Backend persistence remains:
 * - flat tokens dictionary (only token VALUES persist, flat)
 *
 * Editor-only metadata remains:
 * - group     organization
 * - min/max/step  slider + import-clamp bounds
 *
 * Stable registry entry shape remains:
 * - key
 * - label
 * - group
 * - type
 * - min   (optional) bounded-scalar floor   — editor-only
 * - max   (optional) bounded-scalar ceiling — editor-only
 * - step  (optional) slider granularity     — editor-only
 *
 * RANGE IS A PROPERTY OF THE TOKEN KIND
 * -------------------------------------
 * A bounded scalar's range is declared ONCE, by a semantic
 * type-method (.unit / .blur / .angle / .signed) — not hand-
 * authored as min/max on every token (277 tokens = 277 chances
 * to fumble a bound). One definition per kind feeds BOTH
 * consumers: the editor slider (min/max/step) and the import
 * clamp. Single source ⇒ they cannot drift — the editor can't
 * emit a value its own importer would reject.
 *
 * Bare .number stays RANGELESS on purpose, so nothing inherits a
 * wrong bound by accident; ranges come only from a semantic method
 * or an explicit per-token override (the rare deviating token).
 *
 * min/max/step are editor-only metadata — the same category as
 * label/group/type. They are NOT persisted (only flat token
 * values are), so THEME_TOKEN_TYPES is unchanged: the semantic
 * methods are sugar over type:"number" + a range.
 *
 * ============================================================
 */

/* =========================================================
   TYPE VOCABULARY
   ========================================================= */

export const THEME_TOKEN_TYPES = Object.freeze([
  "color",
  "text",
  // A 1-4 part CSS LENGTH LIST (padding, margin, a gap pair). A refinement of
  // "text", not a sibling of "size": `size` is ONE scalar and renders a slider,
  // which cannot express `14px 16px 10px`. Splitting it out of `text` is what
  // lets the editor say what the box wants -- a bare `text` box is also used for
  // gradients and an easing (--evcc-learning-*-gradient, --evcc-learning-anim-ease),
  // so a "e.g. 12px 16px" hint on the shared type would be wrong for those.
  // Issue #83: the reporter's complaint was a text box whose only content was the
  // word "Default".
  "lengths",
  "shadow",
  "size",
  "number",
  "duration",
  "motion",
  "typography",
  "easing",
]);

const VALID_TOKEN_TYPES = new Set(THEME_TOKEN_TYPES);

/**
 * A bare number in a CSS length list means px — issue #83, "or at least default to px".
 *
 * `padding: 8` is not valid CSS and silently does nothing, so a user who types the
 * number they mean gets no padding and no error. This coerces each bare number to px
 * and leaves everything else exactly as typed.
 *
 * IT FAILS OPEN, DELIBERATELY. A normaliser that mangles a valid `calc(100% - 2px)` into
 * nonsense is worse than one that does nothing, because the user cannot see why their
 * value stopped working. Two things provide that, and only one of them is a guard:
 *
 *   1. THE PART REGEX. A part is only rewritten if it is a bare number END TO END, so
 *      every part of `calc(100% - 2px)`, `min(4px, 1%)` and `1px, 2px` is left alone
 *      without anything having to recognise the function. THIS is what protects them.
 *   2. THE >4 GUARD. More than four whitespace-separated parts is not a length list at
 *      all, so it is returned whole — [LEN-9].
 *
 * THERE WAS A THIRD, `if (/[(),]/.test(raw)) return raw`, AND IT WAS REMOVED. An ablation
 * proved it DEAD: deleting it reddened no test, because (1) already covered every input
 * it was written for. Measured across eleven inputs it changed the answer for four, and
 * in three of those it was the WRONG answer — `var(--evcc-space-md) 8` is a valid two-part
 * list and the guard blocked exactly the coercion this function exists to perform, so a
 * user mixing a token with a number silently got no padding. Dominated where it was meant
 * to help, harmful where it acted. See [LEN-4], which now tests the mechanism that holds.
 *
 * The one deliberate non-coercion inside a list it CAN read is a zero: unitless `0` is
 * valid CSS and is what people write, so `0 8` becomes `0 8px`, not `0px 8px`.
 *
 * Lives here rather than in bindings/theme.js because bindings cannot be imported
 * outside a browser, and this is the half worth testing — see [LEN-*].
 *
 * @param {string} value raw input text
 * @returns {string} the same list with bare numbers given px, or the input untouched
 */
export function normaliseLengthList(value) {
  const raw = String(value ?? "").trim();
  if (!raw) return "";                 // empty means UNSET: it must stay empty so the
                                       // var() fallback chain still inherits.
  const parts = raw.split(/\s+/);
  if (parts.length > 4) return raw;    // not a length list we recognise [LEN-9]

  return parts
    .map((p) => (/^-?\d*\.?\d+$/.test(p) && Number(p) !== 0 ? `${p}px` : p))
    .join(" ");
}

/* =========================================================
   SEMANTIC SCALAR RANGES
   =========================================================
   Default min/max/step per bounded-scalar KIND. Override per
   token only for exceptions (e.g. a 0-2 chroma multiplier via
   .unit(key, label, { max: 2 })).
   ========================================================= */

export const SCALAR_RANGES = Object.freeze({
  // 0-1 ratio: the bulk — alpha, opacity, any unit interval. STAYS 0-1: a layer
  // opacity above 1 is inert. It is one factor of
  // `opacity: calc(enabled * floor-opacity-card * layer-opacity)` and the product
  // is CSS-clamped, so with the card factor at its usual 1 a layer value of 2.5
  // renders identically to 1. Measured on a live editor. This bound is a SANITY
  // bound, not a range anyone can spend — do not "widen" it for headroom.
  unit:   { min: 0, max: 1, step: 0.01 },
  // Blur radius in px. NOT routed through `unit` — that would cap blur at 1px.
  // 8 was still too tight: 24px is a visibly different vein and the slider could
  // not reach it, so the only way to get there was typing into the number box.
  // A value you can only reach by typing is a range that is set wrong.
  blur:   { min: 0, max: 32, step: 0.5 },
  // Hue shift in degrees. Wraps, so this is already the whole space.
  angle:  { min: -180, max: 180, step: 1 },
  // Signed delta (e.g. minor-lighten, offset-from-master) — not 0-1. Same
  // reasoning as `unit`: these ride an opacity/lightness that saturates.
  signed: { min: -1, max: 1, step: 0.01 },
});




/**
 * The bounds the IMPORTER will hold a token to — and therefore the bounds the
 * editor's number field must hold it to as well.
 *
 * ONE question, asked in two places (clampThemeScalars on the way in,
 * _formatScalarThemeValue on the way out). They were briefly about to be two
 * copies of the same three lines, which is the shape where one gets fixed and the
 * other does not.
 *
 * Returns the spec's min/max. There is ONE range per token and all three readers
 * share it — the slider, the number field beside it, and the importer's clamp — so
 * they cannot drift. (A `clampMin`/`clampMax` second range was described here and
 * at `ranged` below, and was never implemented: nothing mints those fields and
 * nothing reads them. The description is removed rather than the split built,
 * because a single shared bound is what actually ships and what ISSUE #60's audit
 * confirmed by measurement.)
 *
 * @param {object|null} spec - a THEME_TOKEN_MAP entry.
 * @returns {{min: number|null, max: number|null}} nulls where unbounded.
 */
export function scalarClampBounds(spec) {
  const pick = (v) => (Number.isFinite(v) ? v : null);
  return { min: spec ? pick(spec.min) : null, max: spec ? pick(spec.max) : null };
}

/* =========================================================
   LABEL GENERATION
   ========================================================= */

/**
 * Derives a human-readable label from a CSS custom property key.
 * Strips the "--evcc-" prefix, converts hyphens to spaces, and title-cases each word.
 *
 * @param {string} key - CSS custom property name (e.g. "--evcc-chip-bg").
 * @returns {string} Human-readable label (e.g. "Chip Bg").
 */
export function makeTokenLabel(key) {
  return String(key || "")
    .replace(/^--evcc-/, "")
    .replace(/-/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
    .trim();
}

/* =========================================================
   ENTRY FACTORY
   ========================================================= */

/**
 * Returns a token factory bound to a specific editor group and default type.
 * Calling the returned function produces a registry entry:
 * { key, label, group, type } plus optional editor-only { min, max, step }
 * when a range is supplied (by a semantic method, never persisted).
 *
 * @param {string} group       - Editor group name (e.g. "Chips").
 * @param {string} defaultType - Default token type used when none is specified.
 * @returns {Function} Token factory: (key, label?, type?, range?) => entry
 */
export function makeGroupedToken(group, defaultType = "color") {
  return function groupedToken(key, label = null, type = defaultType, range = null) {
    const normalizedType = VALID_TOKEN_TYPES.has(type) ? type : defaultType;

    const entry = {
      key,
      label: label || makeTokenLabel(key),
      group,
      type: normalizedType,
    };

    // Editor-only range metadata — drives the slider AND the import clamp from
    // one definition. Not persisted (only flat token values are).
    if (range && typeof range === "object") {
      if (Number.isFinite(range.min)) entry.min = range.min;
      if (Number.isFinite(range.max)) entry.max = range.max;
      if (Number.isFinite(range.step)) entry.step = range.step;
    }

    return entry;
  };
}

/* =========================================================
   GROUP AUTHORING HELPER
   =========================================================
   Group files stay concise by using one helper object per group.
   Each helper keeps the same grouped-token pattern while exposing
   explicit type methods for the full inventory vocabulary, plus
   range-carrying semantic methods for bounded scalars.
   ========================================================= */

/**
 * Extends makeGroupedToken with:
 *   - explicit named TYPE methods (.color, .text, .shadow, ...) — sugar for a
 *     type string, no range.
 *   - range-carrying SEMANTIC methods (.unit, .blur, .angle, .signed) — sugar
 *     over type:"number" plus the kind's default min/max/step. Each accepts an
 *     optional override object for the rare deviating token, e.g.
 *     gm.unit(key, label, { max: 2 }) for a 0-2 multiplier.
 *
 * Bare .number is intentionally rangeless.
 *
 * @param {string} group       - Editor group name.
 * @param {string} defaultType - Default type for bare calls without a type method.
 * @returns {Function} Token factory augmented with type + semantic-range methods.
 */
export function makeTypedGroupToken(group, defaultType = "color") {
  const groupedToken = makeGroupedToken(group, defaultType);

  groupedToken.color = (key, label = null) => groupedToken(key, label, "color");
  groupedToken.text = (key, label = null) => groupedToken(key, label, "text");
  groupedToken.lengths = (key, label = null) => groupedToken(key, label, "lengths");
  groupedToken.shadow = (key, label = null) => groupedToken(key, label, "shadow");
  groupedToken.size = (key, label = null) => groupedToken(key, label, "size");
  groupedToken.number = (key, label = null) => groupedToken(key, label, "number");
  groupedToken.duration = (key, label = null) => groupedToken(key, label, "duration");
  groupedToken.motion = (key, label = null) => groupedToken(key, label, "motion");
  groupedToken.typography = (key, label = null) => groupedToken(key, label, "typography");
  groupedToken.easing = (key, label = null) => groupedToken(key, label, "easing");

  // Range-carrying semantic methods. type:"number" + the kind's range, with an
  // optional per-token { min?, max?, step? } override merged on top.
  // Each bounded scalar carries ONE range. min/max drives the editor slider, the
  // number field beside it (scalarClampBounds) and the importer's clamp alike, so
  // widening a per-token override widens all three together and they cannot drift.
  //
  // ⚠ This said a scalar carried TWO ranges — min/max for the slider, clampMin/
  // clampMax for the importer — and instructed anyone widening an override to widen
  // the clamp with it. That instruction could not be followed: no spec mints
  // clampMin/clampMax and no code reads them. Corrected rather than implemented,
  // because one shared bound is what ships and is what the ISSUE #60 release audit
  // verified against the v2.2.0 source.
  const ranged = (defaults) => (key, label = null, override = null) =>
    groupedToken(key, label, "number", { ...defaults, ...(override || {}) });

  groupedToken.unit = ranged(SCALAR_RANGES.unit);
  groupedToken.blur = ranged(SCALAR_RANGES.blur);
  groupedToken.angle = ranged(SCALAR_RANGES.angle);
  groupedToken.signed = ranged(SCALAR_RANGES.signed);

  return groupedToken;
}

/* =========================================================
   GROUP HELPERS
   ========================================================= */

export const shellToken         = makeTypedGroupToken("App Shell & Typography",      "color");
export const surfaceToken       = makeTypedGroupToken("Cards & Surfaces",             "color");
export const borderToken        = makeTypedGroupToken("Borders & Shadows",            "color");
export const chipToken          = makeTypedGroupToken("Chips",                        "color");
export const roomToken          = makeTypedGroupToken("Room Cards",                   "color");
export const mapToken           = makeTypedGroupToken("Map",                          "color");
export const floorTextureToken  = makeTypedGroupToken("Floor Textures",               "number");
export const queueToken         = makeTypedGroupToken("Queue & Ordering",             "color");
export const statusToken        = makeTypedGroupToken("Status, Confidence & Alerts",  "color");
export const learningToken      = makeTypedGroupToken("Learning & Metrics",           "color");
export const modalToken         = makeTypedGroupToken("Modals & Overlays",            "color");
export const foundationToken    = makeTypedGroupToken("Shared Foundations",           "size");
export const animalToken        = makeTypedGroupToken("Animal Companion",              "color");
// Per-animal helpers live in animals.js, following the floor-textures pattern.
