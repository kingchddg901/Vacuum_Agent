/**
 * ============================================================
 * STYLES: LEARNING
 * ============================================================
 *
 * PURPOSE
 * -------
 * Visual system for learning-driven UI surfaces.
 *
 * This file owns:
 * - pre-job estimate panel
 * - live learning banner
 * - live progress list
 * - confidence chips
 * - notices / warnings
 * - overhead breakdown rows
 * - reanchor motion / animation styling
 *
 *
 * DESIGN RULES
 * ------------
 * - Confidence styling is token-first
 * - Gradients are optional and themeable
 * - UI falls back through EVCC semantic tokens
 * - Battery warning is informational only
 * - Motion is subtle and should support frequent ETA updates
 *
 * ============================================================
 */

export const learningStyles = `

  /* =========================================================
     TOKEN BRIDGE
     ========================================================= */

  :host {
    --evcc-learning-panel-bg:
      var(--evcc-surface-panel);

    --evcc-learning-panel-border:
      var(--evcc-border-default);

    --evcc-learning-panel-shadow:
      var(--evcc-shadow-card, 0 6px 14px rgba(0, 0, 0, 0.14));

    --evcc-learning-text-primary:
      var(--evcc-text-primary);

    --evcc-learning-text-secondary:
      var(--evcc-text-secondary);

    --evcc-learning-text-muted:
      var(--evcc-text-muted);

    --evcc-learning-chip-radius:
      var(--evcc-radius-chip, 999px);

    --evcc-learning-chip-font-size: 0.74rem;
    --evcc-learning-chip-font-weight: 700;

    /* === CONFIDENCE: HIGH === */
    --evcc-learning-confidence-high-bg:
      color-mix(in srgb, var(--evcc-sem-success) 18%, transparent);

    --evcc-learning-confidence-high-border:
      color-mix(in srgb, var(--evcc-sem-success) 42%, transparent);

    --evcc-learning-confidence-high-text:
      var(--evcc-sem-success);

    --evcc-learning-confidence-high-gradient:
      linear-gradient(
        135deg,
        color-mix(in srgb, var(--evcc-sem-success) 26%, transparent),
        color-mix(in srgb, var(--evcc-sem-success) 10%, transparent)
      );

    /* === CONFIDENCE: MEDIUM === */
    --evcc-learning-confidence-medium-bg:
      color-mix(in srgb, var(--evcc-sem-warning) 18%, transparent);

    --evcc-learning-confidence-medium-border:
      color-mix(in srgb, var(--evcc-sem-warning) 42%, transparent);

    --evcc-learning-confidence-medium-text:
      var(--evcc-sem-warning);

    --evcc-learning-confidence-medium-gradient:
      linear-gradient(
        135deg,
        color-mix(in srgb, var(--evcc-sem-warning) 26%, transparent),
        color-mix(in srgb, var(--evcc-sem-warning) 10%, transparent)
      );

    /* === CONFIDENCE: LOW === */
    --evcc-learning-confidence-low-border:
      color-mix(in srgb, var(--evcc-sem-error) 42%, transparent);

    --evcc-learning-confidence-low-text:
      var(--evcc-sem-error);

    --evcc-learning-confidence-low-gradient:
      linear-gradient(
        135deg,
        color-mix(in srgb, var(--evcc-sem-error) 26%, transparent),
        color-mix(in srgb, var(--evcc-sem-error) 10%, transparent)
      );

    /* === CONFIDENCE: NEUTRAL / FALLBACK === */
    --evcc-learning-confidence-neutral-border:
      var(--evcc-border-default);

    --evcc-learning-confidence-neutral-text:
      var(--evcc-text-secondary);

    --evcc-learning-confidence-neutral-gradient:
      linear-gradient(
        135deg,
        color-mix(in srgb, var(--evcc-text-muted) 16%, transparent),
        color-mix(in srgb, var(--evcc-text-muted) 8%, transparent)
      );

    /* === SHARED CONFIDENCE TINT TOKENS === */
    --evcc-confidence-high-bg:
      color-mix(in srgb, var(--evcc-sem-success) 18%, transparent);
    --evcc-confidence-high-border:
      color-mix(in srgb, var(--evcc-sem-success) 40%, transparent);
    --evcc-confidence-high-text:
      var(--evcc-sem-success);

    --evcc-confidence-medium-bg:
      color-mix(in srgb, var(--evcc-sem-warning) 18%, transparent);
    --evcc-confidence-medium-border:
      color-mix(in srgb, var(--evcc-sem-warning) 40%, transparent);
    --evcc-confidence-medium-text:
      var(--evcc-sem-warning);

    --evcc-confidence-low-bg:
      color-mix(in srgb, var(--evcc-sem-error) 18%, transparent);
    --evcc-confidence-low-border:
      color-mix(in srgb, var(--evcc-sem-error) 40%, transparent);
    --evcc-confidence-low-text:
      var(--evcc-sem-error);

    /* === MOTION === */
    --evcc-learning-anim-duration-fast: 180ms;
    --evcc-learning-anim-duration-normal: 260ms;
    --evcc-learning-anim-duration-slow: 520ms;
    --evcc-learning-anim-ease:
      cubic-bezier(0.22, 1, 0.36, 1);

    --evcc-learning-reanchor-highlight:
      color-mix(in srgb, var(--evcc-accent) 16%, transparent);

    --evcc-learning-reanchor-border:
      color-mix(in srgb, var(--evcc-accent) 34%, transparent);
  }

  /* =========================================================
     KEYFRAMES
     ========================================================= */

  @keyframes evccLearningFadeSlideIn {
    0% {
      opacity: 0;
      transform: translateY(8px);
    }
    100% {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes evccLearningBannerPulse {
    0% {
      box-shadow:
        0 0 0 0 color-mix(in srgb, var(--evcc-accent) 0%, transparent),
        var(--evcc-learning-panel-shadow);
    }
    40% {
      box-shadow:
        0 0 0 4px color-mix(in srgb, var(--evcc-accent) 16%, transparent),
        var(--evcc-learning-panel-shadow);
    }
    100% {
      box-shadow:
        0 0 0 0 color-mix(in srgb, var(--evcc-accent) 0%, transparent),
        var(--evcc-learning-panel-shadow);
    }
  }

  @keyframes evccLearningRowFlash {
    0% {
      background: color-mix(in srgb, var(--evcc-accent) 0%, transparent);
    }
    35% {
      background: color-mix(in srgb, var(--evcc-accent) 10%, transparent);
    }
    100% {
      background: color-mix(in srgb, var(--evcc-accent) 0%, transparent);
    }
  }

  @keyframes evccLearningCurrentPulse {
    0% {
      box-shadow: 0 0 0 0 color-mix(in srgb, var(--evcc-accent) 12%, transparent);
    }
    70% {
      box-shadow: 0 0 0 6px transparent;
    }
    100% {
      box-shadow: 0 0 0 0 transparent;
    }
  }

  /* =========================================================
     PANEL
     ========================================================= */

  .evcc-learning-panel,
  .evcc-learning-live-banner,
  .evcc-learning-progress {
    display: flex;
    flex-direction: column;
    gap: 12px;

    margin-bottom: 12px;
    padding: 12px 14px;

    border-radius: var(--evcc-radius-panel, 16px);
    border: 1px solid var(--evcc-learning-panel-border);
    background: var(--evcc-learning-panel-bg);
    box-shadow: var(--evcc-learning-panel-shadow);

    color: var(--evcc-learning-text-primary);

    transition:
      border-color var(--evcc-learning-anim-duration-normal) var(--evcc-learning-anim-ease),
      background var(--evcc-learning-anim-duration-normal) var(--evcc-learning-anim-ease),
      box-shadow var(--evcc-learning-anim-duration-normal) var(--evcc-learning-anim-ease),
      transform var(--evcc-learning-anim-duration-normal) var(--evcc-learning-anim-ease);
  }

  .evcc-learning-panel--empty {
    opacity: 0.95;
  }

  .evcc-learning-panel-header,
  .evcc-learning-live-banner {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  .evcc-learning-panel-title-group,
  .evcc-learning-live-banner-main {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }

  .evcc-learning-panel-title,
  .evcc-learning-live-title,
  .evcc-learning-progress-title {
    font-size: 0.92rem;
    font-weight: 700;
    color: var(--evcc-learning-text-primary);
  }

  .evcc-learning-charge-banner {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    padding: 8px 12px;
    border-radius: 10px;
    background: color-mix(in srgb, var(--evcc-accent, #4c9aff) 15%, transparent);
    border: 1px solid color-mix(in srgb, var(--evcc-accent, #4c9aff) 45%, transparent);
    color: var(--evcc-learning-text-primary);
    font-size: 0.84rem;
    font-weight: 600;
  }

  .evcc-learning-charge-icon {
    font-size: 0.95rem;
    line-height: 1;
  }

  .evcc-learning-charge-from {
    color: var(--evcc-learning-text-secondary);
    font-weight: 500;
  }

  .evcc-learning-panel-subtitle,
  .evcc-learning-live-subtitle,
  .evcc-learning-progress-meta,
  .evcc-learning-room-meta,
  .evcc-learning-empty-message {
    font-size: 0.8rem;
    color: var(--evcc-learning-text-secondary);
  }

  /* =========================================================
     ANIMATED SURFACES
     ========================================================= */

  .evcc-learning-live-banner--animated {
    animation:
      evccLearningFadeSlideIn var(--evcc-learning-anim-duration-normal) var(--evcc-learning-anim-ease),
      evccLearningBannerPulse var(--evcc-learning-anim-duration-slow) var(--evcc-learning-anim-ease);
    border-color: var(--evcc-learning-reanchor-border);
    will-change: transform, opacity, box-shadow;
  }

  .evcc-learning-progress-row--animated {
    animation:
      evccLearningFadeSlideIn var(--evcc-learning-anim-duration-fast) var(--evcc-learning-anim-ease),
      evccLearningRowFlash var(--evcc-learning-anim-duration-slow) var(--evcc-learning-anim-ease);
    will-change: transform, opacity, background;
  }

  /* =========================================================
     NOTICES
     ========================================================= */

  .evcc-learning-notice {
    display: flex;
    align-items: center;
    gap: 8px;

    padding: 8px 10px;
    border-radius: 10px;
    font-size: 0.8rem;
    font-weight: 500;
  }

  .evcc-learning-notice--stale {
    background: color-mix(in srgb, var(--evcc-sem-warning) 14%, transparent);
    border: 1px solid color-mix(in srgb, var(--evcc-sem-warning) 28%, transparent);
    color: var(--evcc-sem-warning);
  }

  .evcc-learning-notice--battery {
    background: color-mix(in srgb, var(--evcc-accent) 14%, transparent);
    border: 1px solid color-mix(in srgb, var(--evcc-accent) 28%, transparent);
    color: var(--evcc-accent);
  }

  .evcc-learning-notice--stall {
    background: color-mix(in srgb, var(--evcc-sem-error, #e05) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--evcc-sem-error, #e05) 30%, transparent);
    color: var(--evcc-sem-error, #e05);
  }

  /* =========================================================
     OVERHEAD
     ========================================================= */

  .evcc-learning-overhead {
    border-top: 1px solid var(--evcc-border-subtle);
    padding-top: 8px;
  }

  .evcc-learning-overhead-summary {
    cursor: pointer;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--evcc-learning-text-secondary);
    list-style: none;
  }

  .evcc-learning-overhead-summary::-webkit-details-marker {
    display: none;
  }

  .evcc-learning-overhead-rows {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 10px;
  }

  .evcc-learning-overhead-row,
  .evcc-learning-progress-row,
  .evcc-learning-room-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  .evcc-learning-overhead-row {
    font-size: 0.8rem;
    color: var(--evcc-learning-text-secondary);
  }

  /* =========================================================
     ROOM LIST / PROGRESS LIST
     ========================================================= */

  .evcc-learning-room-list,
  .evcc-learning-progress-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .evcc-learning-room-row,
  .evcc-learning-progress-row {
    padding: 8px 0;
    border-top: 1px solid var(--evcc-border-subtle);

    transition:
      opacity var(--evcc-learning-anim-duration-fast) var(--evcc-learning-anim-ease),
      transform var(--evcc-learning-anim-duration-fast) var(--evcc-learning-anim-ease),
      background var(--evcc-learning-anim-duration-fast) var(--evcc-learning-anim-ease),
      box-shadow var(--evcc-learning-anim-duration-fast) var(--evcc-learning-anim-ease);
  }

  .evcc-learning-room-main,
  .evcc-learning-progress-main,
  .evcc-learning-progress-side {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }

  .evcc-learning-room-name,
  .evcc-learning-progress-name {
    font-size: 0.84rem;
    font-weight: 600;
    color: var(--evcc-learning-text-primary);
    line-height: 1.25;
  }

  .evcc-learning-progress-side {
    align-items: flex-end;
    flex-shrink: 0;
  }

  .evcc-learning-progress-minutes {
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--evcc-learning-text-secondary);
  }

  .evcc-learning-room-notes {
    display: flex;
    flex-direction: column;
    gap: 3px;
    margin-top: 2px;
  }

  .evcc-learning-room-note {
    font-size: 0.74rem;
    color: var(--evcc-learning-text-muted);
  }

  .evcc-learning-progress-row--completed {
    opacity: 0.62;
  }

  .evcc-learning-progress-row--completed .evcc-learning-progress-name {
    text-decoration: line-through;
  }

  .evcc-learning-progress-row--current {
    background:
      linear-gradient(
        90deg,
        color-mix(in srgb, var(--evcc-accent) 10%, transparent),
        transparent
      );
    border-radius: 10px;
    padding: 10px 10px;
    margin: 0 -4px;
    border: 1px solid color-mix(in srgb, var(--evcc-accent) 18%, transparent);
    animation:
      evccLearningCurrentPulse 2.4s ease-in-out infinite;
  }

  /* =========================================================
     CONFIDENCE CHIPS
     ========================================================= */

  .evcc-learning-chip {
    display: inline-flex;
    align-items: center;
    justify-content: center;

    min-height: 24px;
    padding: 4px 10px;

    border-radius: var(--evcc-learning-chip-radius);
    border: 1px solid var(--evcc-learning-confidence-neutral-border);

    background: var(--evcc-learning-confidence-neutral-gradient);
    color: var(--evcc-learning-confidence-neutral-text);

    font-size: var(--evcc-learning-chip-font-size);
    font-weight: var(--evcc-learning-chip-font-weight);
    line-height: 1;
    white-space: nowrap;

    transition:
      border-color var(--evcc-learning-anim-duration-fast) var(--evcc-learning-anim-ease),
      background var(--evcc-learning-anim-duration-fast) var(--evcc-learning-anim-ease),
      color var(--evcc-learning-anim-duration-fast) var(--evcc-learning-anim-ease),
      transform var(--evcc-learning-anim-duration-fast) var(--evcc-learning-anim-ease);
  }

  .evcc-learning-chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .evcc-learning-chip--success {
    border-color: var(--evcc-learning-confidence-high-border);
    background: var(--evcc-learning-confidence-high-gradient);
    color: var(--evcc-learning-confidence-high-text);
  }

  .evcc-learning-chip--warning {
    border-color: var(--evcc-learning-confidence-medium-border);
    background: var(--evcc-learning-confidence-medium-gradient);
    color: var(--evcc-learning-confidence-medium-text);
  }

  .evcc-learning-chip--error {
    border-color: var(--evcc-learning-confidence-low-border);
    background: var(--evcc-learning-confidence-low-gradient);
    color: var(--evcc-learning-confidence-low-text);
  }

  .evcc-learning-chip--neutral {
    border-color: var(--evcc-learning-confidence-neutral-border);
    background: var(--evcc-learning-confidence-neutral-gradient);
    color: var(--evcc-learning-confidence-neutral-text);
  }

  /* =========================================================
     MOBILE
     ========================================================= */

  @media (max-width: 480px) {
    .evcc-learning-panel,
    .evcc-learning-live-banner,
    .evcc-learning-progress {
      padding: 10px 12px;
      gap: 10px;
    }

    .evcc-learning-panel-header,
    .evcc-learning-live-banner,
    .evcc-learning-room-row,
    .evcc-learning-progress-row {
      flex-direction: column;
      align-items: stretch;
    }

    .evcc-learning-progress-side {
      align-items: flex-start;
    }
  }

  /* =========================================================
     REDUCED MOTION
     ========================================================= */

  @media (prefers-reduced-motion: reduce) {
    .evcc-learning-live-banner--animated,
    .evcc-learning-progress-row--animated,
    .evcc-learning-progress-row--current {
      animation: none !important;
    }

    .evcc-learning-panel,
    .evcc-learning-live-banner,
    .evcc-learning-progress,
    .evcc-learning-room-row,
    .evcc-learning-progress-row,
    .evcc-learning-chip {
      transition: none !important;
    }
  }

  /* =========================================================
     INCOMPLETE RUN BANNER
     =========================================================
     Shown on the Rooms view when the last job was cancelled,
     failed, or interrupted before all rooms were cleaned.
     ========================================================= */

  .evcc-incomplete-run-banner {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 8px 0 4px;
    padding: 10px 12px;
    border-radius: var(--evcc-radius-card, 12px);
    background: var(--evcc-surface-warning, rgba(255, 180, 0, 0.12));
    border: 1px solid var(--evcc-border-warning, rgba(255, 180, 0, 0.35));
    font-size: 0.82rem;
  }

  .evcc-incomplete-run-body {
    flex: 1;
    min-width: 0;
  }

  .evcc-incomplete-run-title {
    font-weight: 600;
    color: var(--evcc-text-primary);
    margin-bottom: 4px;
    line-height: 1.3;
  }

  .evcc-incomplete-run-rooms {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 4px;
  }

  .evcc-incomplete-run-room {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--evcc-surface-chip, rgba(255,255,255,0.08));
    border: 1px solid var(--evcc-border-default);
    font-size: 0.76rem;
    font-weight: 500;
    color: var(--evcc-text-secondary);
    white-space: nowrap;
  }

  .evcc-incomplete-run-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }

  .evcc-incomplete-run-retry {
    padding: 5px 12px;
    border-radius: 999px;
    border: 1px solid var(--evcc-border-default);
    background: var(--evcc-surface-action, rgba(255,255,255,0.1));
    color: var(--evcc-text-primary);
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.15s ease, opacity 0.15s ease;
  }

  .evcc-incomplete-run-retry:hover {
    background: var(--evcc-surface-action-hover, rgba(255,255,255,0.18));
  }

  .evcc-incomplete-run-retry:active {
    opacity: 0.75;
  }

  .evcc-incomplete-run-dismiss {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    border: 1px solid var(--evcc-border-default);
    background: transparent;
    color: var(--evcc-text-muted);
    font-size: 0.75rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.15s ease, color 0.15s ease;
    padding: 0;
    line-height: 1;
  }

  .evcc-incomplete-run-dismiss:hover {
    background: var(--evcc-surface-chip, rgba(255,255,255,0.1));
    color: var(--evcc-text-primary);
  }

  /* Cleaning Complete summary banner */

  .evcc-learning-summary-stats {
    display: flex;
    flex-wrap: wrap;
    gap: 24px;
    margin-top: 4px;
  }

  .evcc-learning-summary-stat {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 60px;
  }

  .evcc-learning-summary-value {
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--evcc-text-strong, var(--primary-text-color));
    line-height: 1.1;
  }

  .evcc-learning-summary-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--evcc-text-muted);
  }

  @media (max-width: 480px) {
    .evcc-learning-summary-stats { gap: 16px; }
    .evcc-learning-summary-stat { min-width: 50px; }
  }
`;
