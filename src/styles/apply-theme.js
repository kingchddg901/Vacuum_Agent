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

// From ./apply-tokens.js, NOT ./index.js. Same function -- index.js re-exports it -- but
// index.js imports every stylesheet in the project, so reaching the writer through it
// cost a measured +443,485 bytes to anything that did not already want the CSS.
import { applyDynamicTheme } from "./apply-tokens.js";

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

  /* ---------------------------------------------------------
     3. APPLY TO THE MOUNTED PREVIEW CARD
     ---------------------------------------------------------
     The theme editor's Dashboard Cards preview mounts a REAL eufy-room-card
     (main.js::_maybeMountThemePreviewCard). It is the same shape of problem as the
     modal host above, arrived at from the other direction: that one renders OUTSIDE
     the shadow root, this one renders INSIDE its own.

     Inheritance is not enough, and that was measured the hard way. The mounted card
     injects `foundationTokens` into its own shadow root, which DECLARES ~425
     --evcc-* tokens — and a declaration in the element's own tree beats a value
     inherited from this host. So the preview tracked the editor only for tokens
     foundation does NOT declare, which is exactly the two frame tokens and nothing
     else. Measured: setting --evcc-chip-padding to `20px 40px` on the panel moved
     the mounted card's chip not one pixel, while --evcc-card-frame-border-width
     came through, because that one is deliberately undeclared.

     An INLINE property on the card element outranks its own :host declaration, so
     bridging the layer here fixes every token at once. Doing it in THIS function
     rather than at the mount site is what makes it live: the 15 editor controls in
     bindings/theme.js call applyThemeToCard directly on each keystroke and never
     re-render, so a mount-site-only fix would update the preview a render late.
     Gated by [CPV-5]. */
  if (card._themePreviewCardEl && card.shadowRoot?.contains(card._themePreviewCardEl)) {
    applyDynamicTheme(card._themePreviewCardEl, resolved);
  }
}
