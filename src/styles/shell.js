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
     NAV TABS
     ========================================================= */

  .evcc-nav {
    display:       flex;
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
