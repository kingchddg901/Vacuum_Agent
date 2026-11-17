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
  foundationToken.lengths("--evcc-space-lg", "Space Lg"),
  foundationToken.lengths("--evcc-space-md", "Space Md"),
  foundationToken.lengths("--evcc-space-sm", "Space Sm"),
  // Registered 2026-11-16, and the ONLY one of the four that was not. It has been
  // declared in CSS since the family was completed (styles/foundation.js:297 = 4px,
  // and scripts/check-styles.mjs:278-279 records it being taken OUT of
  // KNOWN_DANGLING) -- so it painted correctly everywhere and offered no control,
  // which is indistinguishable from a token that does not exist.
  //
  // `.lengths` matches its three siblings above, and the choice against `.size` is
  // deliberate rather than inherited. Each of the four IS a single length, so `.size`
  // and its slider would fit -- but `.size` requires a declared range, and these four
  // ARE the scale every other spacing value in the system is measured against, so
  // picking bounds for them would be a decision about the scale itself rather than about
  // a control. `.lengths` takes any length in any unit, needs no range, says in its
  // placeholder what it wants, and coerces a bare number to px (issue #83).
  foundationToken.lengths("--evcc-space-xs", "Space Xs"),
  foundationToken.motion("--evcc-transition-normal", "Transition Normal"),
];
