/**
 * ============================================================
 * THEME TOKENS: SHARED FOUNDATIONS
 * ============================================================
 *
 * PURPOSE
 * -------
 * Defines shared spacing, radius, typography, motion, and
 * geometry primitives reused across multiple EVCC systems.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * These tokens form the editor-facing foundation layer while
 * backend persistence continues to store the same tokens as a
 * flat dictionary.
 *
 * ============================================================
 */

import { foundationToken } from "./helpers.js";

export const FOUNDATION_TOKENS = [
  foundationToken.typography("--evcc-font-family", "Font Family"),
  foundationToken.size("--evcc-gap", "Gap"),
  foundationToken.size("--evcc-grid-gap", "Grid Gap"),
  foundationToken.motion("--evcc-hover-lift", "Hover Lift"),
  foundationToken.size("--evcc-pad", "Pad"),
  foundationToken.number("--evcc-press-scale", "Press Scale"),
  foundationToken.size("--evcc-radius-card", "Radius Card"),
  foundationToken.size("--evcc-radius-chip", "Radius Chip"),
  foundationToken.size("--evcc-radius-inner", "Radius Inner"),
  foundationToken.size("--evcc-radius-panel", "Radius Panel"),
  foundationToken.size("--evcc-section-gap", "Section Gap"),
  foundationToken.text("--evcc-space-lg", "Space Lg"),
  foundationToken.text("--evcc-space-md", "Space Md"),
  foundationToken.text("--evcc-space-sm", "Space Sm"),
  // Registered 2026-11-16, and the ONLY one of the four that was not. It has been
  // declared in CSS since the family was completed (styles/foundation.js:297 = 4px,
  // and scripts/check-styles.mjs:278-279 records it being taken OUT of
  // KNOWN_DANGLING) -- so it painted correctly everywhere and offered no control,
  // which is indistinguishable from a token that does not exist. `.text` matches its
  // three siblings above rather than `.size`, which is what they all are.
  foundationToken.text("--evcc-space-xs", "Space Xs"),
  foundationToken.motion("--evcc-transition-normal", "Transition Normal"),
];
