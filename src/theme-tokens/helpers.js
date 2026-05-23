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
 * - flat tokens dictionary
 *
 * Group metadata remains:
 * - editor-only organization
 *
 * Stable registry entry shape remains:
 * - key
 * - label
 * - group
 * - type
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
 * Calling the returned function produces a registry entry: { key, label, group, type }.
 *
 * @param {string} group       - Editor group name (e.g. "Chips").
 * @param {string} defaultType - Default token type used when none is specified.
 * @returns {Function} Token factory: (key, label?, type?) => { key, label, group, type }
 */
export function makeGroupedToken(group, defaultType = "color") {
  return function groupedToken(key, label = null, type = defaultType) {
    const normalizedType = VALID_TOKEN_TYPES.has(type) ? type : defaultType;

    return {
      key,
      label: label || makeTokenLabel(key),
      group,
      type: normalizedType,
    };
  };
}

/* =========================================================
   GROUP AUTHORING HELPER
   =========================================================
   Group files stay concise by using one helper object per group.
   Each helper keeps the same grouped-token pattern while exposing
   explicit type methods for the full inventory vocabulary.
   ========================================================= */

/**
 * Extends makeGroupedToken with explicit named type methods (.color, .text, .shadow, etc.)
 * so group files can author tokens with clear intent instead of passing a type string.
 *
 * @param {string} group       - Editor group name.
 * @param {string} defaultType - Default type for bare calls without a type method.
 * @returns {Function} Token factory augmented with one method per THEME_TOKEN_TYPES entry.
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
export const floorTextureToken  = makeTypedGroupToken("Floor Textures",               "number");
export const queueToken         = makeTypedGroupToken("Queue & Ordering",             "color");
export const statusToken        = makeTypedGroupToken("Status, Confidence & Alerts",  "color");
export const learningToken      = makeTypedGroupToken("Learning & Metrics",           "color");
export const modalToken         = makeTypedGroupToken("Modals & Overlays",            "color");
export const foundationToken    = makeTypedGroupToken("Shared Foundations",           "size");
export const animalToken        = makeTypedGroupToken("Animal Companion",              "color");
