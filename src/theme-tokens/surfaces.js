/**
 * ============================================================
 * THEME TOKENS: CARDS & SURFACES
 * ============================================================
 *
 * PURPOSE
 * -------
 * Defines shared surface, card, and panel tokens used across the
 * app shell and reusable control surfaces.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * This group centralizes background, spacing, and raised-surface
 * metadata so the editor can expose surface controls together
 * without changing the flat backend token contract.
 *
 * ============================================================
 */

import { surfaceToken } from "./helpers.js";

export const SURFACE_TOKENS = [
  surfaceToken.color("--evcc-bg-input", "BG Input"),
  surfaceToken.color("--evcc-bg-panel", "BG Panel"),
  surfaceToken.color("--evcc-card-bg", "Card BG"),
  surfaceToken.size("--evcc-card-gap", "Card Gap"),
  surfaceToken.size("--evcc-card-min-height", "Card Min Height"),
  surfaceToken.size("--evcc-card-padding", "Card Padding"),
  surfaceToken.color("--evcc-panel-bg", "Panel BG"),
  surfaceToken.color("--evcc-surface-base", "Surface Base"),
  surfaceToken.color("--evcc-surface-card", "Surface Card"),
  surfaceToken.color("--evcc-surface-input", "Surface Input"),
  surfaceToken.color("--evcc-surface-overlay", "Surface Overlay"),
  surfaceToken.color("--evcc-surface-panel", "Surface Panel"),
  surfaceToken.color("--evcc-surface-raise", "Surface Raise"),
  surfaceToken.color("--evcc-surface-raised", "Surface Raised"),
];
