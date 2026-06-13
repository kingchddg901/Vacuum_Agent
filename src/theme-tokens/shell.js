/**
 * ============================================================
 * THEME TOKENS: APP SHELL & TYPOGRAPHY
 * ============================================================
 *
 * PURPOSE
 * -------
 * Defines the top-level shell and primary text tokens that set
 * the overall visual direction for the card.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * These tokens are authored in their group file for editor
 * organization, while backend persistence remains the flat
 * token dictionary.
 *
 * ============================================================
 */

import { shellToken } from "./helpers.js";

export const SHELL_TOKENS = [
  shellToken.color("--evcc-accent", "Accent"),
  shellToken.color("--evcc-accent-soft", "Accent Soft"),
  shellToken.color("--evcc-text-muted", "Text Muted"),
  shellToken.color("--evcc-text-on-accent", "Text On Accent"),
  shellToken.color("--evcc-text-primary", "Text Primary"),
  shellToken.color("--evcc-text-secondary", "Text Secondary"),
  shellToken.color("--evcc-text-strong", "Text Strong"),
];
