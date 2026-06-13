/**
 * ============================================================
 * STYLES: FOUNDATION
 * ============================================================
 *
 * PURPOSE
 * -------
 * Core visual layer for the card shell.
 *
 * This file owns:
 * - Canonical design tokens (EVCC system)
 * - HA fallback mapping (ONLY here)
 * - Backward compatibility aliases
 * - card shell layout
 * - header layout and typography
 * - navigation tabs
 * - shared chip system
 * - status badges
 * - view area wrapper
 * - stub/placeholder styles
 *
 * ============================================================
 */

export const sharedChipStyles = `

  .evcc-chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--evcc-chip-gap, 6px);
  }

  .evcc-chip,
  .evcc-room-setting-chip,
  .evcc-room-status {
    display: inline-flex;
    align-items: center;
    justify-content: center;

    min-height: var(--evcc-chip-height, 24px);
    padding: var(--evcc-chip-padding, 5px 14px);

    border-radius: var(--evcc-chip-radius, 999px);
    border: 1px solid var(--evcc-chip-border, var(--evcc-border-default));

    background: var(--evcc-chip-bg, var(--evcc-surface-input));
    color: var(--evcc-chip-text, var(--evcc-text-secondary));

    font-size: var(--evcc-chip-font-size, 0.82rem);
    font-weight: var(--evcc-chip-font-weight, 500);

    line-height: 1;
    white-space: nowrap;
    font-family: inherit;

    transition:
      background var(--evcc-transition-normal, 150ms ease),
      color var(--evcc-transition-normal, 150ms ease),
      border-color var(--evcc-transition-normal, 150ms ease),
      opacity var(--evcc-transition-normal, 150ms ease);
  }

  .evcc-chip {
    cursor: pointer;
  }

  .evcc-chip:hover:not(:disabled):not(.active) {
    background: var(--evcc-chip-hover-bg, var(--evcc-surface-panel));
    color: var(--evcc-chip-hover-text, var(--evcc-text-primary));
    border-color: var(--evcc-chip-hover-border, var(--evcc-border-strong));
  }

  .evcc-chip.active {
    background: var(--evcc-chip-active-bg,
      color-mix(in srgb, var(--evcc-accent) 18%, transparent));
    color: var(--evcc-chip-active-text, var(--evcc-accent));
    border-color: var(--evcc-chip-active-border,
      color-mix(in srgb, var(--evcc-accent) 40%, transparent));
    font-weight: 600;
  }

  .evcc-chip:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .evcc-chip--icon {
    min-height: var(--evcc-chip-icon-height, 24px);
    padding: var(--evcc-chip-icon-padding, 4px 8px);
    font-size: var(--evcc-chip-icon-size, 0.8rem);
  }
`;

export const foundationStyles = `

  :host {
    display: block;
    position: relative;
    height: 100%;
    min-height: 0;

    /* =======================================================
       CANONICAL FOUNDATION TOKENS
       ======================================================= */

    /* Surfaces */
    --evcc-surface-base:   var(--card-background-color, #1c2127);
    --evcc-surface-card:   var(--evcc-surface-base);
    --evcc-surface-panel:  color-mix(in srgb, var(--evcc-surface-base) 85%, white 15%);
    --evcc-surface-raised: color-mix(in srgb, var(--evcc-surface-base) 92%, white 8%);
    --evcc-surface-input:  rgba(255,255,255,0.06);
    --evcc-surface-overlay: rgba(0,0,0,0.4);
    --evcc-surface-subtle: rgba(255,255,255,0.04);
    --evcc-surface-chip:   rgba(255,255,255,0.09);
    --evcc-surface-action: rgba(255,255,255,0.10);
    --evcc-surface-action-hover: rgba(255,255,255,0.18);
    --evcc-surface-sunken: rgba(0,0,0,0.18);
    --evcc-surface-warning: rgba(255,180,0,0.12);

    /* Text */
    --evcc-text-primary:   var(--primary-text-color, #f0f2f5);
    --evcc-text-secondary: var(--secondary-text-color, rgba(240,242,245,0.72));
    --evcc-text-muted:     rgba(240,242,245,0.48);
    --evcc-text-strong:    var(--primary-text-color, #f0f2f5);
    --evcc-text-on-accent: #ffffff;

    /* Borders */
    --evcc-border-subtle:  rgba(255,255,255,0.06);
    --evcc-border-default: rgba(255,255,255,0.10);
    --evcc-border-strong:  rgba(255,255,255,0.18);
    --evcc-border-warning: rgba(255,180,0,0.35);

    /* Accent */
    --evcc-accent: var(--accent-color, #3b82f6);
    --evcc-accent-soft: rgba(0,229,255,0.16);

    /* Generic semantics */
    --evcc-sem-success: var(--success-color, #4caf6e);
    --evcc-sem-warning: var(--warning-color, #f5a623);
    --evcc-sem-error:   var(--error-color,   #e05252);
    /* Info: a stable literal blue, NOT var(--info-color, …) — HA's
       --info-color is theme-inconsistent (amber in some themes) and could
       collide with the warning hue. Used for reference/baseline states. */
    --evcc-sem-info:    #4a9fe0;

    /* Radius */
    --evcc-radius-card:  var(--ha-card-border-radius, 12px);
    --evcc-radius-inner: 8px;
    --evcc-radius-chip:  999px;

    /* Spacing */
    --evcc-space-sm: 8px;
    --evcc-space-md: 12px;
    --evcc-space-lg: 16px;

    --evcc-gap: var(--evcc-space-md);
    --evcc-pad: var(--evcc-space-lg);

    /* =======================================================
       BACKWARD COMPATIBILITY (DO NOT REMOVE YET)
       ======================================================= */

    --evcc-card-bg:       var(--evcc-surface-card);
    --evcc-panel-bg:      var(--evcc-surface-panel);
    --evcc-bg-input:      var(--evcc-surface-input);

    /* Old status colors → mapped to semantics */
    --evcc-color-cleaning:  var(--evcc-sem-success);
    --evcc-color-docked:    var(--evcc-accent);
    --evcc-color-error:     var(--evcc-sem-error);
    --evcc-color-idle:      var(--evcc-text-secondary);

    /* =======================================================
       CHIP BASE TOKENS
       ======================================================= */

    --evcc-chip-height: 24px;
    --evcc-chip-padding: 5px 14px;
    --evcc-chip-radius: 999px;

    --evcc-chip-bg: var(--evcc-surface-input);
    --evcc-chip-border: var(--evcc-border-default);
    --evcc-chip-text: var(--evcc-text-secondary);

    --evcc-chip-hover-bg: var(--evcc-surface-panel);
    --evcc-chip-hover-text: var(--evcc-text-primary);
    --evcc-chip-hover-border: var(--evcc-border-strong);

    --evcc-chip-icon-height: 24px;
    --evcc-chip-icon-padding: 4px 8px;
    --evcc-chip-icon-size: 0.8rem;

    /* Motion */
    --evcc-transition-normal: 150ms ease;
  }

  /* =========================================================
     RESET
     ========================================================= */

  *, *::before, *::after {
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

  ha-card {
    contain: none !important;
    overflow: hidden !important;
    height: 100%;
    min-height: 0;
  }

  /* =========================================================
     CARD SHELL
     ========================================================= */

  .evcc-card {
    background: var(--evcc-surface-card);
    border-radius: var(--evcc-radius-card);
    color: var(--evcc-text-primary);
    font-family: var(--paper-font-body1_-_font-family, sans-serif);
    font-size: 14px;
    line-height: 1.5;
    position: relative;
    isolation: isolate;
  }

  /* =========================================================
     HEADER
     ========================================================= */

  .evcc-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--evcc-gap);
    padding: var(--evcc-pad) var(--evcc-pad) 0;
    flex-wrap: wrap;
  }

  .evcc-vacuum-name {
    font-size: 1.1rem;
    font-weight: 600;
    line-height: 1.2;
  }

  .evcc-battery {
    font-size: 0.8rem;
    color: var(--evcc-text-secondary);
  }

  /* =========================================================
     STATUS BADGE
     ========================================================= */

  .evcc-status-badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 99px;
    font-size: 0.75rem;
    font-weight: 500;

    background: var(--evcc-surface-raised);
    color: var(--evcc-text-secondary);
    border: 1px solid var(--evcc-border-default);
  }

  /* =========================================================
     NAVIGATION
     ========================================================= */

  .evcc-tab {
    padding: 6px 14px;
    border-radius: var(--evcc-radius-chip);
    font-size: 0.85rem;
    color: var(--evcc-text-secondary);
    transition: background 0.15s, color 0.15s;
  }

  .evcc-tab:hover {
    background: var(--evcc-surface-raised);
    color: var(--evcc-text-primary);
  }

  .evcc-tab.active {
    background: color-mix(in srgb, var(--evcc-accent) 18%, transparent);
    color: var(--evcc-accent);
    font-weight: 500;
  }

  .evcc-view {
    padding: var(--evcc-pad);
  }

  ${sharedChipStyles}
`;
