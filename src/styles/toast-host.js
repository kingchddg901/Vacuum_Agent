/**
 * TOAST HOST styles — the second document.body portal host.
 *
 * MOVED OUT OF `styles/index.js` 2026-08-21, same reason as the modal host: injected by
 * `main.js::_updateToastHost` into `document.body`, so it is not a member of the `STYLES`
 * shadow-root cascade and had no module of its own.
 *
 * `styles/index.js` re-exports this so every existing import keeps working.
 */

import { fontTokenRules } from "./fonts.js";

/* =========================================================
   TOAST HOST STYLES
   =========================================================
   Applied to the separate document.body toast host div. The
   host's z-index sits above the modal host (9999) so success /
   error feedback is visible while a modal is open. Pointer
   events are off on the wrapper so toasts don't block clicks
   inside the modal underneath; the per-toast dismiss button
   re-enables them.
   ========================================================= */
export const TOAST_HOST_STYLES = `

  /* TYPEFACE — this host cannot inherit --evcc-font-family, which is declared on
     :host([data-evcc-font]) inside the card's shadow tree. main.js stamps the same
     attribute here (_applyFontAttributeTo), so the token is re-declared for this
     branch of the document. The @font-face itself is registered document-wide, so
     only the token needs restating, not the face. Without this the card switches
     typeface and its toasts do not. */
  /* anchor: CNFC7N35 */
  ${fontTokenRules((id) => `.evcc-toast-host[data-evcc-font="${id}"]`)}
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  button {
    background: none;
    border: none;
    cursor: pointer;
    font: inherit;
    color: inherit;
  }

  .evcc-toast-stack {
    position:        fixed;
    inset-inline-start:            0;
    inset-inline-end:           0;
    bottom:          24px;
    display:         flex;
    flex-direction:  column-reverse;
    gap:             8px;
    align-items:     center;
    pointer-events:  none;
    /* anchor: CN3CGTPS */
    z-index:         10000;
    font-family:     var(--evcc-a11y-font-family, var(--evcc-font-family, var(--paper-font-body1_-_font-family, sans-serif)));
    font-size:       14px;
  }

  .evcc-toast {
    pointer-events: auto;
    display:        flex;
    align-items:    center;
    gap:            10px;
    padding:        10px 14px;
    border-radius:  10px;
    font-size:      0.9rem;
    background:     var(--evcc-surface-raised, rgba(28, 28, 30, 0.96));
    color:          var(--evcc-text-primary, #f0f2f5);
    box-shadow:     0 6px 18px rgba(0, 0, 0, 0.4);
    border:         1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.1));
    min-width:      220px;
    max-width:      90vw;
    animation:      evcc-toast-host-in 160ms ease-out;
  }

  .evcc-toast--success { border-inline-start: 3px solid var(--evcc-sem-success, #22c55e); }
  .evcc-toast--error   { border-inline-start: 3px solid var(--evcc-sem-error,   #ef4444); }
  .evcc-toast--info    { border-inline-start: 3px solid var(--evcc-accent,      #60a5fa); }

  .evcc-toast-message {
    flex: 1;
    line-height: 1.3;
  }

  .evcc-toast-dismiss {
    color:        var(--evcc-text-muted, rgba(255, 255, 255, 0.55));
    font-size:    0.95rem;
    padding:      0 6px;
    line-height:  1;
  }

  .evcc-toast-dismiss:hover {
    color: var(--evcc-text-primary, #f0f2f5);
  }

  @keyframes evcc-toast-host-in {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
  }
`;
