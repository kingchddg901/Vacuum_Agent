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
  "shadow",
  "size",
  "number",
  "duration",
  "motion",
  "typography",
  "easing",
]);

const VALID_TOKEN_TYPES = new Set(THEME_TOKEN_TYPES);

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
 * clampMin/clampMax when present, else the slider's min/max so a spec minted
 * before the split still behaves.
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
  groupedToken.shadow = (key, label = null) => groupedToken(key, label, "shadow");
  groupedToken.size = (key, label = null) => groupedToken(key, label, "size");
  groupedToken.number = (key, label = null) => groupedToken(key, label, "number");
  groupedToken.duration = (key, label = null) => groupedToken(key, label, "duration");
  groupedToken.motion = (key, label = null) => groupedToken(key, label, "motion");
  groupedToken.typography = (key, label = null) => groupedToken(key, label, "typography");
  groupedToken.easing = (key, label = null) => groupedToken(key, label, "easing");

  // Range-carrying semantic methods. type:"number" + the kind's range, with an
  // optional per-token { min?, max?, step? } override merged on top.
  // Each bounded scalar carries TWO ranges: min/max drives the editor slider,
  // clampMin/clampMax is what the importer will accept. A per-token override that
  // widens min/max (e.g. the 0-2 chroma, the +/-8 signed blurs) must widen the
  // clamp with it, or the escape hatch would reintroduce the lossy round trip for
  // exactly the tokens someone bothered to give extra room.
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
