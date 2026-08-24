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

  /* Optional leading glyph on a chip (see BADGE_ICONS in renderers/review.js).
     Sized in em units so it tracks --evcc-chip-font-size and any user font
     scaling, instead of pinning to a px size the surrounding text has outgrown.

     margin-inline-end, not margin-right: the icon leads the text, so under
     ar/he the whole chip mirrors and the gap has to follow it to the other
     side. flex 0 0 auto keeps it from being squeezed when a translated label
     is long — the TEXT may wrap in filter rows, the glyph never shrinks.

     No colour declared on purpose: the SVG paints with currentColor, so it
     inherits whichever semantic token the chip's modifier class set.

     (No backticks in this comment — one would close the enclosing template
     literal and silently truncate every rule after it. That is the exact bug
     scripts/check-styles.mjs exists to catch, and it caught this one.) */
  .evcc-chip-icon {
    inline-size: 1em;
    block-size:  1em;
    flex:        0 0 auto;
    margin-inline-end: 0.4em;
  }

  /* Filter-chip rows carry long, must-stay-READABLE labels (you pick a filter by
     its text), so under translation they WRAP within the chip rather than
     truncate or push the row into horizontal overflow. Targeted at the filter
     rows only — the base .evcc-chip stays nowrap (per the layout decision);
     mirrors the searchable-filter rule in metrics.js. No-op for English (short
     filter labels fit one line), so the byte-pinned baselines are unchanged. */
  .evcc-metrics-filter-chips .evcc-chip,
  .evcc-review-filter-chips .evcc-chip {
    white-space:   normal;
    overflow-wrap: anywhere;
    max-width:     100%;
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

  /* Native <select> option popup: Windows Chrome ignores the select's var-based bg and paints
     the OS-default (often white) popup, so light option text goes invisible (bad contrast).
     Pin a THEMED bg + text on the OPTION itself (which the popup DOES respect) — a card-wide
     floor for EVERY dropdown, adapting to light/dark via the tokens. A specific select can
     still override. This rule lands in both the card foundation and the modal host, since both
     interpolate sharedChipStyles; it supersedes the per-select copies (rooms-animal / ext-allrooms). */
  select option {
    background: var(--evcc-surface-panel, #1c2127);
    color: var(--evcc-text-primary, #f0f2f5);
  }
`;

export const foundationStyles = `

  :host {
    display: block;
    position: relative;
    height: 100%;
    min-height: 0;
  }

  /* PANEL MODE. height:100% needs a parent with a definite height, and
     ha-panel-custom does not give its child one — a panel is expected to size
     itself. Without this the shell collapses to content height (measured: 209px in
     a 780px viewport), which unpins the mobile nav and leaves the sticky header
     with no scroll container. As a dashboard CARD the host does supply a height, so
     this is scoped to the panel attribute rather than applied globally.

     --evcc-panel-offset is MEASURED (main.js:_syncPanelOffset) — where the host
     actually starts in the viewport. It replaces a guess: this integration
     registers through panel_custom with embed_iframe=False, so HA renders it in
     ha-panel-custom, which gives the panel the whole area and NO toolbar. The
     old header-height subtraction therefore removed ~56px for chrome that
     is not on screen, leaving that much dead space below the bottom nav.

     The --header-height chain stays as the fallback for the frame before the
     first measurement, and for any context where the toolbar IS drawn, so this
     degrades to the previous behaviour rather than to an overflow. */
  :host([data-evcc-panel]) {
    height: calc(100dvh - var(--evcc-panel-offset, var(--header-height, 56px)));
  }

  /* anchor: CNVJMQTE */
  :host {

    /* =======================================================
       CANONICAL FOUNDATION TOKENS
       ======================================================= */

    /* Surfaces */
    /* anchor: CNRE7F7B */
    --evcc-surface-base:   var(--card-background-color, #1c2127);
    --evcc-surface-card:   var(--evcc-surface-base);
    --evcc-surface-panel:  color-mix(in srgb, var(--evcc-surface-base) 85%, white 15%);
    --evcc-surface-raised: color-mix(in srgb, var(--evcc-surface-base) 92%, white 8%);
    --evcc-surface-input:  rgba(255,255,255,0.06);
    --evcc-surface-overlay: rgba(0,0,0,0.4);
    --evcc-surface-subtle: rgba(255,255,255,0.04);
    --evcc-surface-hover:  rgba(255,255,255,0.08);
    --evcc-surface-chip:   rgba(255,255,255,0.09);
    --evcc-surface-action: rgba(255,255,255,0.10);
    --evcc-surface-action-hover: rgba(255,255,255,0.18);
    --evcc-surface-sunken: rgba(0,0,0,0.18);
    --evcc-surface-warning: rgba(255,180,0,0.12);
    /* The success half of the same pair, added when the sequence-override row
       needed a confirmed-state box and found only the warning one. Same alphas
       as its sibling above and its partner below, so a success box and a
       warning box weigh the same on the card. Literal, like the warning pair --
       NOT derived from --evcc-sem-success: the warning surface is its own hue
       (255,180,0) rather than sem-warning's (245,166,35), and a set where one
       half tracks the semantic colour and the other does not is worse than
       either rule applied consistently. */
    --evcc-surface-success: rgba(76,175,110,0.12);

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
    --evcc-border-success: rgba(76,175,110,0.35);

    /* Accent */
    /* anchor: CNQ4HPFN */
    --evcc-accent: var(--accent-color, #3b82f6);
    --evcc-accent-soft: rgba(0,229,255,0.16);

    /* Generic semantics */
    /* anchor: RNCCB8J2  the SEMANTIC DEFAULT palette -- the replica set. harness/cvd/
       report.mjs hard-copies these four hexes as RGB triples to run the colour-vision
       contrast floor against them. Change a default here and the report keeps PASSING,
       about colours the product no longer ships -- a green accessibility result for a
       palette that does not exist. */
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
    /* xs was referenced before it existed; 4px is the value that was already
       falling back, so the scale gains its missing member and nothing moves. */
    --evcc-space-xs: 4px;
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
     CARD SHELL — deliberately absent. Do not re-add .evcc-card.
     =========================================================
     R2-DEAD-4. There was a .evcc-card block here and NO element ever carried the
     class — the shell frame emits .evcc-shell (main.js). Every declaration in it
     was silently inert for the life of the block, so deleting it changes nothing
     that renders.

     It cost two fix rounds during live:FONT-1: the typeface read sat here, on a
     selector that matches nothing, which is why the faces stayed "unloaded" — no
     rendered text ever asked for the family. The real read now lives on
     .evcc-shell in styles/shell.js, pinned by TF-1 (the chain, a11y-first) and
     TF-7 (the markup side: main.js must still emit the class).

     Five declarations died with it and were never in effect: color, font-size
     14px, line-height 1.5, position relative, isolation isolate. If the shell
     SHOULD carry any of them, that is a deliberate visual change to make on
     .evcc-shell and eyeball — not a silent restore of this block. */

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
