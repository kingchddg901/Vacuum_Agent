/**
 * ============================================================
 * STYLES: APPLY RESOLVED THEME
 * ============================================================
 *
 * PURPOSE
 * -------
 * Apply the current resolved theme layer to all live card-owned
 * DOM surfaces that consume EVCC CSS variables.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * This file is a small runtime bridge:
 * - state resolves the effective theme
 * - styles/applyDynamicTheme writes CSS variables to a target
 * - this helper decides which live targets receive that layer
 *
 * This is not theme-definition authoring, so it lives with the
 * style runtime rather than in a standalone theme folder.
 *
 * ============================================================
 */

import { applyDynamicTheme } from "./index.js";

/**
 * Applies the card's current resolved theme to all live DOM targets that consume
 * EVCC CSS variables — the card host and, when present, the external modal host.
 *
 * @param {HTMLElement} card - The custom-element card instance with a ._state reference.
 */
export function applyThemeToCard(card) {
  const state = card._state;
  if (!state || typeof state.resolvedTheme !== "function") return;

  const resolved = state.resolvedTheme();

  /* ---------------------------------------------------------
     1. APPLY TO CARD HOST
     --------------------------------------------------------- */
  applyDynamicTheme(card, resolved);

  /* ---------------------------------------------------------
     2. APPLY TO MODAL HOST
     ---------------------------------------------------------
     Modals render outside shadowRoot, so they need the same
     resolved token layer bridged onto their external host node.
     --------------------------------------------------------- */
  if (card._modalHost && document.body.contains(card._modalHost)) {
    applyDynamicTheme(card._modalHost, resolved);
  }
}
