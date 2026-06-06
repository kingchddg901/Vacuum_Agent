/**
 * ============================================================
 * HARNESS: SEMANTIC-COLOR TOKEN SET
 * ============================================================
 *
 * The ONE enumeration the colorblind gallery and the CVD ΔE
 * measurement both derive from — so coverage and concern share a
 * single source: you cannot have a colored state the gallery omits
 * or the CVD check misses.
 *
 * Derived from the registry, never hand-listed: the color-typed
 * tokens in the Status/Confidence/Alerts and Learning & Metrics
 * groups. Add a colored state-token to those groups (src/theme-
 * tokens/status.js, learning.js) and it auto-appears here — which
 * forces a new gallery entry (completeness test) and a new CVD
 * measurement region.
 *
 * ============================================================
 */

import { THEME_TOKEN_REGISTRY } from "../src/theme-tokens/index.js";

/** Editor groups whose color tokens are state/semantic colors. */
export const SEMANTIC_GROUPS = Object.freeze([
  "Status, Confidence & Alerts",
  "Learning & Metrics",
]);

/** Every semantic-color token key, sorted. */
export const SEMANTIC_COLOR_TOKENS = Object.freeze(
  THEME_TOKEN_REGISTRY
    .filter((t) => t.type === "color" && SEMANTIC_GROUPS.includes(t.group))
    .map((t) => t.key)
    .sort(),
);
