/**
 * ============================================================
 * STYLES: SHELL
 * ============================================================
 *
 * PURPOSE
 * -------
 * Styles for the outer card shell, header, navigation tabs,
 * and the view stage that all feature views live inside.
 *
 * This file owns:
 * - .evcc-shell      — outermost card container
 * - .evcc-header     — vacuum name, status, battery
 * - .evcc-nav        — view tab strip
 * - .evcc-view-stage — content area below header
 *
 *
 * WHAT THIS FILE SHOULD NOT CONTAIN
 * ----------------------------------
 * - room card styles
 * - maintenance styles
 * - modal styles
 * - theme editor styles
 *
 *
 * IMPORTANT
 * ---------
 * This file is fully aligned with the normalized EVCC token
 * system.
 *
 * That means:
 * - no direct Home Assistant semantic colors here
 * - no legacy shell-only tokens
 * - all surfaces, borders, status colors, and motion resolve
 *   through canonical EVCC tokens first
 *
 * ============================================================
 */

export const shellStyles = `

  /* =========================================================
     OUTER SHELL
     ========================================================= */

  .evcc-shell {
    background:    var(--evcc-surface-card);
    border-radius: var(--evcc-radius-card);
    box-shadow:    var(--evcc-shadow-card, 0 6px 14px rgba(0, 0, 0, 0.14));
    overflow:      hidden;
    display:       flex;
    flex-direction: column;
    height:        100%;
    min-height:    0;
  }

  /* =========================================================
     HEADER
     ========================================================= */

  .evcc-header {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    padding:         14px 16px 12px;
    border-bottom:   1px solid var(--evcc-border-subtle);
    gap:             var(--evcc-gap);
  }

  .evcc-header-left {
    display:       flex;
    flex-direction: column;
    gap:           2px;
    min-width:     0;
  }

  .evcc-vacuum-name {
    font-size:      1.05rem;
    font-weight:    600;
    color:          var(--evcc-text-primary);
    white-space:    nowrap;
    overflow:       hidden;
    text-overflow:  ellipsis;
  }

  .evcc-vacuum-status {
    display:     flex;
    align-items: center;
    gap:         6px;
    font-size:   0.8rem;
    color:       var(--evcc-text-secondary);
  }

  .evcc-dock-status {
    margin-top: 2px;
  }

  .evcc-status-prefix {
    color:        var(--evcc-text-muted);
    margin-right: 4px;
  }

  /* =========================================================
     STATUS DOT
     ========================================================= */

  .evcc-status-dot {
    width:         7px;
    height:        7px;
    border-radius: 50%;
    flex-shrink:   0;
    background:    var(--evcc-status-dot-idle, var(--evcc-text-muted));
    box-shadow:    var(--evcc-status-dot-shadow, none);
  }

  .evcc-status-dot.cleaning  { background: var(--evcc-status-dot-cleaning,   var(--evcc-sem-success)); }
  .evcc-status-dot.docked    { background: var(--evcc-status-dot-docked,     var(--evcc-accent)); }
  .evcc-status-dot.returning { background: var(--evcc-status-dot-returning,  var(--evcc-sem-warning)); }
  .evcc-status-dot.error     { background: var(--evcc-status-dot-error,      var(--evcc-sem-error)); }
  .evcc-status-dot.paused    { background: var(--evcc-status-dot-paused,     var(--evcc-accent)); }
  .evcc-status-dot.charging  { background: var(--evcc-status-dot-charging,   var(--evcc-sem-success)); }
  .evcc-status-dot.offline   { background: var(--evcc-status-dot-offline,    var(--evcc-text-muted)); }
  .evcc-status-dot.unavailable { background: var(--evcc-status-dot-unavailable, var(--evcc-text-muted)); }

  .evcc-battery {
    font-size:   0.78rem;
    color:       var(--evcc-text-muted);
    white-space: nowrap;
  }

  .evcc-battery.low {
    color: var(--evcc-sem-warning);
  }

  .evcc-battery.critical {
    color: var(--evcc-sem-error);
  }

  /* =========================================================
     HEADER LANGUAGE CONTROL
     =========================================================
     A globe button (top-right of the header) that opens a dropdown of the
     bundled locales. The open menu must out-stack the view content (which
     paints AFTER the header in DOM), so `.is-open` lifts the whole control
     into a high stacking context; a transparent fixed backdrop catches the
     outside click. Shared desktop + mobile (mobile positions the wrapper —
     see styles/mobile.js). */

  .evcc-header-right {
    display:     flex;
    align-items: center;
    flex-shrink: 0;
  }

  .evcc-lang {
    position: relative;
    display:  inline-flex;
  }

  /* When open, lift above the view-stage and map layers (which top out near
     z-index 10). The backdrop/menu stack within this context. */
  .evcc-lang.is-open {
    z-index: 100;
  }

  .evcc-lang-button {
    position:       relative;
    z-index:        2;            /* stay clickable above the backdrop */
    display:        inline-flex;
    align-items:    center;
    gap:            4px;
    padding:        4px 8px;
    border-radius:  var(--evcc-radius-chip);
    background:     transparent;
    color:          var(--evcc-text-secondary);
    cursor:         pointer;
    font-size:      0.78rem;
    line-height:    1;
    transition:     background var(--evcc-transition-normal, 150ms ease),
                    color      var(--evcc-transition-normal, 150ms ease);
  }

  .evcc-lang-button:hover {
    background: var(--evcc-surface-raised);
    color:      var(--evcc-text-primary);
  }

  .evcc-lang.is-open .evcc-lang-button {
    background: var(--evcc-surface-raised);
    color:      var(--evcc-text-primary);
  }

  .evcc-lang-globe {
    font-size: 1rem;
  }

  .evcc-lang-code {
    font-weight:          600;
    letter-spacing:       0.03em;
    font-variant-numeric: tabular-nums;
  }

  .evcc-lang-backdrop {
    /* fixed = clipped to the VIEWPORT, not the overflow:hidden card box, so the
       outside-click target covers the whole screen. Assumes no ancestor sets
       transform / filter / contain (which would make this its containing block
       and re-clip it) — true today (.evcc-card uses only isolation:isolate). */
    position:   fixed;
    inset:      0;
    z-index:    1;            /* below the button + menu, above everything else */
    background: transparent;
  }

  .evcc-lang-menu {
    position:      absolute;
    top:           calc(100% + 6px);
    right:         0;
    z-index:       3;
    min-width:     190px;
    max-width:     calc(100vw - 20px);   /* never overflow a narrow card's right edge */
    max-height:    62vh;
    overflow-y:    auto;
    padding:       4px;
    background:    var(--evcc-surface-raised);
    border:        1px solid var(--evcc-border-subtle);
    border-radius: var(--evcc-radius-card, 10px);
    box-shadow:    var(--evcc-shadow-overlay, 0 8px 24px rgba(0, 0, 0, 0.28));
  }

  .evcc-lang-menu-heading {
    padding:        6px 8px 4px;
    font-size:      0.7rem;
    font-weight:    600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color:          var(--evcc-text-muted);
  }

  .evcc-lang-option {
    display:       flex;
    align-items:   center;
    gap:           6px;
    width:         100%;
    padding:       7px 8px;
    border:        none;
    border-radius: var(--evcc-radius-chip);
    background:    transparent;
    color:         var(--evcc-text-secondary);
    font-size:     0.82rem;
    text-align:    left;
    cursor:        pointer;
    transition:    background var(--evcc-transition-normal, 150ms ease),
                   color      var(--evcc-transition-normal, 150ms ease);
  }

  .evcc-lang-option:hover {
    background: color-mix(in srgb, var(--evcc-accent) 12%, transparent);
    color:      var(--evcc-text-primary);
  }

  .evcc-lang-option.is-active {
    color:       var(--evcc-accent);
    font-weight: 600;
  }

  .evcc-lang-check {
    flex:       0 0 auto;
    width:      1em;
    text-align: center;
    color:      var(--evcc-accent);
  }

  .evcc-lang-label {
    flex:          1 1 auto;
    overflow:      hidden;
    text-overflow: ellipsis;
    white-space:   nowrap;
  }

  /* =========================================================
     NAV TABS
     ========================================================= */

  .evcc-nav {
    display:       flex;
    /* Wrap the TAB STRIP to a second row when long (translated) labels push the
       tabs past the width, instead of overflowing the card into a horizontal
       scroll — a growth-zone strip, taller is acceptable. No-op for English,
       whose tabs fit one row (labels keep wrapping inside their own tab as
       before), so the byte-pinned baselines are unchanged. */
    flex-wrap:     wrap;
    gap:           2px;
    padding:       8px 12px;
    border-bottom: 1px solid var(--evcc-border-subtle);
    background:    var(--evcc-surface-panel);
  }

  .evcc-nav-tab {
    flex:          1;
    padding:       6px 4px;
    border-radius: var(--evcc-radius-chip);
    font-size:     0.78rem;
    font-weight:   500;
    color:         var(--evcc-text-secondary);
    text-align:    center;
    transition:
      background var(--evcc-transition-normal, 150ms ease),
      color      var(--evcc-transition-normal, 150ms ease);
  }

  .evcc-nav-tab:hover {
    background: var(--evcc-surface-raised);
    color:      var(--evcc-text-primary);
  }

  .evcc-nav-tab.active {
    background:  color-mix(in srgb, var(--evcc-accent) 18%, transparent);
    color:       var(--evcc-accent);
    font-weight: 600;
  }

  /* =========================================================
     VIEW STAGE
     =========================================================
     The scrollable content area that each view renders into.
     ========================================================= */

  .evcc-view-stage {
    flex:       1;
    overflow-y: auto;
    padding:    var(--evcc-space-lg);
    min-height: 0;
    min-width:  0;
  }

  .evcc-view-stage[data-view="theme"] {
    display:    flex;
    overflow:   hidden;
    min-height: 0;
    height:     auto;
    max-height: none;
  }

  /* =========================================================
     EMPTY / PLACEHOLDER STATE
     ========================================================= */

  .evcc-empty {
    display:         flex;
    align-items:     center;
    justify-content: center;
    padding:         32px 16px;
    color:           var(--evcc-text-muted);
    font-size:       0.88rem;
    text-align:      center;
  }

  /* =========================================================
     TOASTS
     =========================================================
     Floating stack of transient feedback pills. Pinned to the
     bottom of the card so it sits above the mobile bottom nav
     and the view content. Pointer-events: none on the root so
     the toasts don't intercept clicks behind them; the
     individual toast re-enables them for the dismiss button.
     ========================================================= */

  .evcc-toast-root {
    position:       absolute;
    left:           0;
    right:          0;
    bottom:         16px;
    display:        flex;
    justify-content: center;
    pointer-events: none;
    z-index:        50;
  }

  .evcc-toast-stack {
    display:        flex;
    flex-direction: column-reverse;
    gap:            8px;
    align-items:    center;
    max-width:      90%;
    pointer-events: none;
  }

  .evcc-toast {
    pointer-events: auto;
    display:        flex;
    align-items:    center;
    gap:            10px;
    padding:        8px 12px;
    border-radius:  10px;
    font-size:      0.85rem;
    background:     var(--evcc-surface-raised, rgba(30, 30, 30, 0.94));
    color:          var(--evcc-text-primary);
    box-shadow:     0 4px 14px rgba(0, 0, 0, 0.28);
    border:         1px solid var(--evcc-border-subtle, rgba(255,255,255,0.08));
    min-width:      200px;
    max-width:      420px;
    animation:      evcc-toast-in 160ms ease-out;
  }

  .evcc-toast--success {
    border-left: 3px solid var(--evcc-sem-success);
  }

  .evcc-toast--error {
    border-left: 3px solid var(--evcc-sem-error);
  }

  .evcc-toast--info {
    border-left: 3px solid var(--evcc-accent);
  }

  .evcc-toast-message {
    flex: 1;
    line-height: 1.3;
  }

  .evcc-toast-dismiss {
    background:   transparent;
    border:       none;
    color:        var(--evcc-text-muted);
    cursor:       pointer;
    font-size:    0.95rem;
    padding:      0 4px;
    line-height:  1;
  }

  .evcc-toast-dismiss:hover {
    color: var(--evcc-text-primary);
  }

  @keyframes evcc-toast-in {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  .evcc-shell {
    position: relative;
  }
`;
