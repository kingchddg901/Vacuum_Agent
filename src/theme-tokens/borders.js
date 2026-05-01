/**
 * ============================================================
 * THEME TOKENS: BORDERS & SHADOWS
 * ============================================================
 *
 * PURPOSE
 * -------
 * Defines shared border-strength and shadow-depth tokens used by
 * cards, chips, overlays, and feedback surfaces.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * Border and shadow metadata belongs together in editor grouping
 * because both shape control-surface elevation and separation,
 * while backend persistence remains flat.
 *
 * ============================================================
 */

import { borderToken } from "./helpers.js";

export const BORDER_TOKENS = [
  borderToken.color("--evcc-border-default", "Border Default"),
  borderToken.color("--evcc-border-strong", "Border Strong"),
  borderToken.color("--evcc-border-subtle", "Border Subtle"),
  borderToken.shadow("--evcc-shadow-card", "Shadow Card"),
  borderToken.shadow("--evcc-shadow-hover", "Shadow Hover"),
];
