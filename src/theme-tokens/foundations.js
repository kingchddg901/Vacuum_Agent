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
  foundationToken.motion("--evcc-transition-normal", "Transition Normal"),
];
