/**
 * ============================================================
 * STYLES: ORDER
 * ============================================================
 *
 * PURPOSE
 * -------
 * Shared visual language for ordered-list interactions.
 *
 * Fully aligned with EVCC token system:
 * - chip system
 * - motion system
 * - semantic tokens
 *
 * This file owns:
 * - order chip
 * - drag handle
 * - move button
 * - drag state
 * - reorder feedback
 *
 * ============================================================
 */

export const orderStyles = `

  /* =========================================================
     ORDER ROW / GROUPING
     ========================================================= */

  .evcc-order-controls {
    display: inline-flex;
    align-items: center;
    gap: var(--evcc-chip-gap, 6px);
    flex-wrap: wrap;
  }

  /* =========================================================
     ORDER CHIP
     ========================================================= */

  .evcc-order-chip {
    --evcc-chip-height:      22px;
    --evcc-chip-padding:     2px 8px;
    --evcc-chip-font-size:   0.72rem;
    --evcc-chip-font-weight: 700;

    --evcc-chip-bg:     var(--evcc-order-chip-bg,
                          var(--evcc-chip-neutral-bg,
                          var(--evcc-surface-input)));

    --evcc-chip-border: var(--evcc-order-chip-border,
                          var(--evcc-border-default));

    --evcc-chip-text:   var(--evcc-order-chip-text,
                          var(--evcc-text-secondary));

    min-width:       34px;
    border-radius:   var(--evcc-radius-chip, 999px);
    line-height:     1;
    white-space:     nowrap;
    font-variant-numeric: tabular-nums;
  }

  /* =========================================================
     MOVE BUTTON
     ========================================================= */

  .evcc-order-move-button {
    --evcc-chip-height:      22px;
    --evcc-chip-padding:     2px 8px;
    --evcc-chip-font-size:   0.72rem;
    --evcc-chip-font-weight: 600;
  }

  /* =========================================================
     DRAG HANDLE
     ========================================================= */

  .evcc-order-drag-handle {
    --evcc-chip-height:      22px;
    --evcc-chip-padding:     2px 8px;
    --evcc-chip-font-size:   0.78rem;
    --evcc-chip-font-weight: 700;

    cursor: grab;
    user-select: none;
    touch-action: none;
    letter-spacing: -0.08em;
    min-width: 30px;

    transition:
      background var(--evcc-transition-normal, 120ms ease),
      color var(--evcc-transition-normal, 120ms ease),
      border-color var(--evcc-transition-normal, 120ms ease);
  }

  .evcc-order-drag-handle:hover {
    background:   var(--evcc-chip-hover-bg, var(--evcc-surface-panel));
    color:        var(--evcc-chip-hover-text, var(--evcc-text-primary));
    border-color: var(--evcc-chip-hover-border, var(--evcc-border-strong));
  }

  .evcc-order-drag-handle:active {
    cursor: grabbing;
  }

  /* =========================================================
     SHARED CARD LIFT (MOTION ALIGNED)
     ========================================================= */

  .evcc-room-card {
    transition:
      transform    var(--evcc-transition-normal, 120ms ease),
      box-shadow   var(--evcc-transition-normal, 120ms ease),
      border-color var(--evcc-transition-normal, 120ms ease),
      background   var(--evcc-transition-normal, 120ms ease);
  }

  .evcc-room-card:hover {
    transform:  translateY(calc(-1 * var(--evcc-hover-lift, 1px)));
    box-shadow: var(--evcc-shadow-hover, 0 8px 18px rgba(0, 0, 0, 0.18));
  }

  /* =========================================================
     DRAG STATE
     ========================================================= */

  .evcc-order-drag-source {
    opacity:   var(--evcc-drag-opacity, 0.92);
    transform: scale(var(--evcc-drag-scale, 1.02));
    box-shadow: var(--evcc-drag-shadow, 0 14px 28px rgba(0, 0, 0, 0.25));
    z-index:   10;
  }

  .evcc-order-drag-target {
    outline:        1px dashed var(--evcc-order-target-outline,
                     color-mix(in srgb, var(--evcc-accent) 70%, transparent));
    outline-offset: 3px;
  }

  /* =========================================================
     REORDER FEEDBACK (FULL MOTION SYSTEM)
     ========================================================= */

  @keyframes evccOrderFeedbackPulse {
    0% {
      box-shadow:
        0 0 0 0 color-mix(in srgb, var(--evcc-accent) 0%, transparent),
        var(--evcc-shadow-card, 0 6px 14px rgba(0, 0, 0, 0.14));
    }

    35% {
      box-shadow:
        0 0 0 4px color-mix(in srgb, var(--evcc-accent) 20%, transparent),
        var(--evcc-shadow-hover, 0 10px 22px rgba(0, 0, 0, 0.20));
    }

    100% {
      box-shadow:
        0 0 0 0 color-mix(in srgb, var(--evcc-accent) 0%, transparent),
        var(--evcc-shadow-card, 0 6px 14px rgba(0, 0, 0, 0.14));
    }
  }

  .evcc-order-feedback {
    animation:
      evccOrderFeedbackPulse
      var(--evcc-reorder-feedback-duration, 700ms)
      var(--evcc-reorder-flip-easing, cubic-bezier(0.22, 1, 0.36, 1));

    border-color:
      var(--evcc-order-feedback-border,
      color-mix(in srgb, var(--evcc-accent) 55%, transparent)) !important;
  }

  /* =========================================================
     FEATURE-SAFE HELPERS
     ========================================================= */

  [data-order-drag-item] {
    -webkit-user-drag: element;
  }

  [data-order-drop-target] {
    position: relative;
    will-change: transform;
  }

  /* =========================================================
     MOBILE
     ========================================================= */

  @media (max-width: 720px) {
    .evcc-order-drag-handle {
      display: none;
    }
  }
`;