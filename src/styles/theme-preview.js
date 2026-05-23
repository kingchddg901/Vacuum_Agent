// CSS styles for the live theme preview pane: all preview sample elements and their token-driven appearances.

export const themePreviewStyles = `
  /* =========================================================
     THEME PREVIEW PANE
     ========================================================= */

  .evcc-theme-editor-pane {
    display: flex;
    gap: 16px;
    flex: 1;
    min-height: 0;
    min-width: 0;
    overflow: hidden;
  }

  .evcc-theme-preview-column {
    display: flex;
    flex: 0 0 320px;
    width: 320px;
    min-height: 0;
    padding-right: 4px;
    overflow: hidden;
  }

  .evcc-theme-preview-pane {
    display: flex;
    flex-direction: column;
    gap: 12px;
    width: 100%;
    min-height: 0;
    overflow: hidden;
    padding: 14px;
    background: var(--evcc-surface-card, var(--evcc-card-bg, #242b33));
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.08));
    border-radius: var(--evcc-radius-card, 16px);
    box-shadow: var(--evcc-shadow-card, 0 12px 32px rgba(0, 0, 0, 0.25));
  }

  .evcc-theme-preview-header {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .evcc-theme-preview-eyebrow {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.55));
  }

  .evcc-theme-preview-title {
    font-size: 1rem;
    font-weight: 700;
    color: var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-theme-preview-description {
    font-size: 0.8rem;
    line-height: 1.45;
    color: var(--evcc-text-secondary, rgba(255, 255, 255, 0.72));
  }

  .evcc-theme-preview-body,
  .evcc-theme-preview-grid,
  .evcc-theme-preview-text-stack,
  .evcc-theme-preview-border-stack,
  .evcc-theme-preview-shadow-stack,
  .evcc-theme-preview-chip-grid,
  .evcc-theme-preview-status-dots,
  .evcc-theme-preview-queue-strip,
  .evcc-theme-preview-reorder-row,
  .evcc-theme-preview-inline-actions,
  .evcc-theme-preview-modal-body {
    display: flex;
    flex-wrap: wrap;
    gap: var(--evcc-gap, 10px);
  }

  .evcc-theme-preview-body,
  .evcc-theme-preview-grid {
    flex-direction: column;
  }

  .evcc-theme-preview-card,
  .evcc-theme-preview-learning-panel,
  .evcc-theme-preview-room-card {
    display: flex;
    flex-direction: column;
    gap: var(--evcc-gap, 10px);
    padding: var(--evcc-card-padding, 14px);
    min-height: var(--evcc-card-min-height, 0);
    background: var(--evcc-surface-panel, var(--evcc-panel-bg, #1c2127));
    border: 1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
    border-radius: var(--evcc-radius-card, 16px);
    box-shadow: var(--evcc-shadow-card, none);
  }

  .evcc-theme-preview-card--hero {
    background:
      linear-gradient(
        135deg,
        color-mix(in srgb, var(--evcc-accent, #3b82f6) 14%, transparent),
        transparent 58%
      ),
      var(--evcc-surface-panel, var(--evcc-panel-bg, #1c2127));
  }

  .evcc-theme-preview-section-title,
  .evcc-theme-preview-shell-kicker {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.58));
  }

  .evcc-theme-preview-heading {
    font-family: var(--evcc-font-family, inherit);
    font-size: 1.2rem;
    line-height: 1.15;
    color: var(--evcc-text-primary, #f0f2f5);
    margin: 0;
  }

  .evcc-theme-preview-copy,
  .evcc-theme-preview-text-primary,
  .evcc-theme-preview-modal-title {
    color: var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-theme-preview-copy,
  .evcc-theme-preview-text-secondary,
  .evcc-theme-preview-text-muted,
  .evcc-theme-preview-note {
    font-size: 0.84rem;
    line-height: 1.45;
  }

  .evcc-theme-preview-text-secondary,
  .evcc-theme-preview-detail-label {
    color: var(--evcc-text-secondary, rgba(255, 255, 255, 0.72));
  }

  .evcc-theme-preview-text-muted,
  .evcc-theme-preview-note {
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.56));
  }

  .evcc-theme-preview-linkish,
  .evcc-theme-preview-accent-pill {
    color: var(--evcc-accent, #3b82f6);
    font-weight: 600;
  }

  .evcc-theme-preview-accent-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 4px 10px;
    border-radius: var(--evcc-radius-chip, 999px);
    background: color-mix(in srgb, var(--evcc-accent, #3b82f6) 18%, transparent);
    border: 1px solid color-mix(in srgb, var(--evcc-accent, #3b82f6) 40%, transparent);
  }

  .evcc-theme-preview-surface-card {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: var(--evcc-card-padding, 14px);
    background: var(--evcc-surface-card, var(--evcc-card-bg, #242b33));
    border-radius: var(--evcc-radius-card, 16px);
    box-shadow: var(--evcc-shadow-card, none);
  }

  .evcc-theme-preview-surface-panel {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: var(--evcc-pad, 12px);
    background: var(--evcc-surface-panel, var(--evcc-panel-bg, #1c2127));
    border-radius: var(--evcc-radius-panel, 14px);
    border: 1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
  }

  .evcc-theme-preview-input {
    display: flex;
    align-items: center;
    min-height: 38px;
    padding: 0 12px;
    border-radius: var(--evcc-radius-inner, 12px);
    background: var(--evcc-surface-input, var(--evcc-bg-input, rgba(255, 255, 255, 0.05)));
    border: 1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.56));
    font-size: 0.82rem;
  }

  .evcc-theme-preview-border-sample,
  .evcc-theme-preview-shadow-sample,
  .evcc-theme-preview-drag-card,
  .evcc-theme-preview-order-target {
    padding: 12px;
    border-radius: var(--evcc-radius-inner, 12px);
    background: var(--evcc-surface-card, var(--evcc-card-bg, #242b33));
    color: var(--evcc-text-primary, #f0f2f5);
    font-size: 0.82rem;
  }

  .evcc-theme-preview-border-sample--subtle {
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.08));
  }

  .evcc-theme-preview-border-sample--default {
    border: 1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
  }

  .evcc-theme-preview-border-sample--strong {
    border: 1px solid var(--evcc-border-strong, rgba(255, 255, 255, 0.18));
  }

  .evcc-theme-preview-shadow-sample--card {
    box-shadow: var(--evcc-shadow-card, 0 8px 20px rgba(0, 0, 0, 0.2));
  }

  .evcc-theme-preview-shadow-sample--hover {
    box-shadow: var(--evcc-shadow-hover, 0 12px 30px rgba(0, 0, 0, 0.28));
    transform: translateY(calc(var(--evcc-hover-lift, 0px) * -1));
  }

  .evcc-theme-preview-chip-grid .evcc-chip {
    cursor: default;
  }

  .evcc-theme-preview-chip--hover {
    background: var(--evcc-chip-hover-bg, var(--evcc-chip-bg, rgba(255, 255, 255, 0.05)));
    border-color: var(--evcc-chip-hover-border, var(--evcc-chip-border, rgba(255, 255, 255, 0.12)));
    color: var(--evcc-chip-hover-text, var(--evcc-chip-text, #f0f2f5));
  }

  .evcc-theme-preview-chip--included {
    background: var(--evcc-chip-included-bg, rgba(34, 197, 94, 0.15));
    border-color: var(--evcc-chip-included-border, rgba(34, 197, 94, 0.3));
    color: var(--evcc-chip-included-text, #22c55e);
  }

  .evcc-theme-preview-chip--excluded {
    background: var(--evcc-chip-excluded-bg, rgba(239, 68, 68, 0.12));
    border-color: var(--evcc-chip-excluded-border, rgba(239, 68, 68, 0.3));
    color: var(--evcc-chip-excluded-text, #f87171);
  }

  .evcc-theme-preview-chip--success {
    background: var(--evcc-chip-success-bg, rgba(34, 197, 94, 0.15));
    border-color: var(--evcc-chip-success-border, rgba(34, 197, 94, 0.3));
    color: var(--evcc-chip-success-text, #22c55e);
  }

  .evcc-theme-preview-chip--warning {
    background: var(--evcc-chip-warning-bg, rgba(245, 158, 11, 0.15));
    border-color: var(--evcc-chip-warning-border, rgba(245, 158, 11, 0.35));
    color: var(--evcc-chip-warning-text, #f59e0b);
  }

  .evcc-theme-preview-room-card {
    position: relative;
    overflow: hidden;
    background:
      linear-gradient(
        90deg,
        color-mix(in srgb, var(--evcc-accent, #3b82f6) var(--evcc-room-fill-opacity, 10%), transparent),
        transparent 70%
      ),
      var(--evcc-surface-card, var(--evcc-card-bg, #242b33));
  }

  .evcc-theme-preview-room-card--filled::before {
    content: "";
    position: absolute;
    inset: 0;
    background: color-mix(in srgb, var(--evcc-accent, #3b82f6) var(--evcc-room-fill-opacity, 18%), transparent);
    pointer-events: none;
  }

  .evcc-theme-preview-room-header,
  .evcc-theme-preview-room-detail-row,
  .evcc-theme-preview-modal-header,
  .evcc-theme-preview-modal-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  .evcc-theme-preview-room-name,
  .evcc-theme-preview-surface-title {
    font-weight: 700;
    color: var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-theme-preview-profile-chip {
    background: var(--evcc-profile-chip-bg, rgba(255, 255, 255, 0.06));
    border-color: var(--evcc-profile-chip-border, rgba(255, 255, 255, 0.14));
    color: var(--evcc-profile-chip-text, var(--evcc-text-primary, #f0f2f5));
  }

  .evcc-theme-preview-profile-chip--custom {
    background: var(--evcc-profile-chip-custom-bg, rgba(245, 158, 11, 0.14));
    border-color: var(--evcc-profile-chip-custom-border, rgba(245, 158, 11, 0.3));
    color: var(--evcc-profile-chip-custom-text, #f59e0b);
  }

  .evcc-theme-preview-room-chip {
    background: var(--evcc-room-chip-bg, rgba(255, 255, 255, 0.06));
    border-color: var(--evcc-room-chip-border, rgba(255, 255, 255, 0.14));
    color: var(--evcc-room-chip-text, var(--evcc-text-secondary, rgba(255, 255, 255, 0.72)));
  }

  /* =========================================================
     FLOOR TEXTURE PREVIEW — real room-card grid
     ========================================================= */

  .evcc-theme-preview-ftx-card-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--evcc-gap, 10px);
    pointer-events: none;
  }

  .evcc-theme-preview-order-chip,
  .evcc-theme-preview-room-order {
    background: var(--evcc-order-chip-bg, var(--evcc-queue-order-bg, rgba(255, 255, 255, 0.06)));
    border-color: var(--evcc-order-chip-border, var(--evcc-queue-order-border, rgba(255, 255, 255, 0.14)));
    color: var(--evcc-order-chip-text, var(--evcc-queue-order-text, var(--evcc-text-primary, #f0f2f5)));
  }

  .evcc-theme-preview-queue-chip {
    display: inline-flex;
    align-items: center;
    gap: var(--evcc-queue-chip-gap, 8px);
    padding: 8px 10px;
    border-radius: var(--evcc-radius-chip, 999px);
    border: 1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
    font-size: 0.82rem;
    white-space: nowrap;
  }

  .evcc-theme-preview-queue-chip--current {
    background: var(--evcc-queue-current-bg, rgba(59, 130, 246, 0.12));
    border-color: var(--evcc-queue-current-border, rgba(59, 130, 246, 0.28));
    color: var(--evcc-queue-current-text, var(--evcc-text-primary, #f0f2f5));
    box-shadow: var(--evcc-queue-current-glow, none);
  }

  .evcc-theme-preview-queue-chip--pending {
    background: var(--evcc-queue-pending-bg, rgba(255, 255, 255, 0.05));
    border-color: var(--evcc-queue-pending-border, rgba(255, 255, 255, 0.12));
    color: var(--evcc-queue-pending-text, var(--evcc-text-secondary, rgba(255, 255, 255, 0.72)));
    opacity: var(--evcc-queue-pending-opacity, 1);
  }

  .evcc-theme-preview-queue-chip--completed {
    background: var(--evcc-queue-completed-bg, rgba(34, 197, 94, 0.12));
    border-color: var(--evcc-queue-completed-border, rgba(34, 197, 94, 0.28));
    color: var(--evcc-queue-completed-text, #22c55e);
    opacity: var(--evcc-queue-completed-opacity, 1);
  }

  .evcc-theme-preview-queue-chip--inferred {
    background: var(--evcc-queue-inferred-bg, rgba(245, 158, 11, 0.12));
    border-color: var(--evcc-queue-inferred-border, rgba(245, 158, 11, 0.28));
    color: var(--evcc-queue-inferred-text, #f59e0b);
    box-shadow: var(--evcc-queue-inferred-glow, none);
  }

  .evcc-theme-preview-drag-card {
    opacity: var(--evcc-drag-opacity, 0.88);
    transform: scale(var(--evcc-drag-scale, 1.02));
    box-shadow: var(--evcc-drag-shadow, var(--evcc-shadow-hover, 0 12px 30px rgba(0, 0, 0, 0.28)));
  }

  .evcc-theme-preview-order-target {
    border: 1px dashed var(--evcc-order-target-outline, var(--evcc-order-feedback-border, rgba(59, 130, 246, 0.35)));
    background: transparent;
  }

  .evcc-theme-preview-status-dot {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: var(--evcc-text-secondary, rgba(255, 255, 255, 0.72));
    font-size: 0.82rem;
  }

  .evcc-theme-preview-status-dot::before {
    content: "";
    width: 10px;
    height: 10px;
    border-radius: 50%;
    box-shadow: var(--evcc-status-dot-shadow, none);
    animation: evcc-theme-preview-pulse var(--evcc-status-pulse-duration, 1600ms) ease-in-out infinite;
  }

  .evcc-theme-preview-status-dot--idle::before {
    background: var(--evcc-status-dot-idle, var(--evcc-color-idle, #94a3b8));
  }

  .evcc-theme-preview-status-dot--cleaning::before {
    background: var(--evcc-status-dot-cleaning, var(--evcc-color-cleaning, #3b82f6));
  }

  .evcc-theme-preview-status-dot--docked::before {
    background: var(--evcc-status-dot-docked, var(--evcc-color-docked, #22c55e));
  }

  .evcc-theme-preview-status-dot--error::before {
    background: var(--evcc-status-dot-error, var(--evcc-color-error, #ef4444));
  }

  .evcc-theme-preview-confidence-high,
  .evcc-theme-preview-learning-confidence-high {
    background: var(--evcc-confidence-high-bg, var(--evcc-learning-confidence-high-bg, rgba(34, 197, 94, 0.12)));
    border-color: var(--evcc-confidence-high-border, var(--evcc-learning-confidence-high-border, rgba(34, 197, 94, 0.28)));
    color: var(--evcc-confidence-high-text, var(--evcc-learning-confidence-high-text, #22c55e));
  }

  .evcc-theme-preview-confidence-medium,
  .evcc-theme-preview-learning-confidence-medium {
    background: var(--evcc-confidence-medium-bg, var(--evcc-learning-confidence-medium-bg, rgba(245, 158, 11, 0.12)));
    border-color: var(--evcc-confidence-medium-border, var(--evcc-learning-confidence-medium-border, rgba(245, 158, 11, 0.28)));
    color: var(--evcc-confidence-medium-text, var(--evcc-learning-confidence-medium-text, #f59e0b));
  }

  .evcc-theme-preview-confidence-low {
    background: var(--evcc-confidence-low-bg, rgba(239, 68, 68, 0.12));
    border-color: var(--evcc-confidence-low-border, rgba(239, 68, 68, 0.28));
    color: var(--evcc-confidence-low-text, #f87171);
  }

  .evcc-theme-preview-alert {
    padding: 10px 12px;
    border-radius: var(--evcc-radius-inner, 12px);
    border: 1px solid transparent;
    font-size: 0.8rem;
  }

  .evcc-theme-preview-alert--info {
    background: color-mix(in srgb, var(--evcc-sem-info, #3b82f6) 12%, transparent);
    border-color: color-mix(in srgb, var(--evcc-sem-info, #3b82f6) 28%, transparent);
    color: var(--evcc-sem-info, #3b82f6);
  }

  .evcc-theme-preview-alert--warning {
    background: var(--evcc-modal-warning-bg, color-mix(in srgb, var(--evcc-sem-warning, #f59e0b) 12%, transparent));
    border-color: var(--evcc-modal-warning-border, color-mix(in srgb, var(--evcc-sem-warning, #f59e0b) 28%, transparent));
    color: var(--evcc-modal-warning-text, var(--evcc-sem-warning, #f59e0b));
  }

  .evcc-theme-preview-alert--error {
    background: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 12%, transparent);
    border-color: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 28%, transparent);
    color: var(--evcc-sem-error, #ef4444);
  }

  .evcc-theme-preview-estimate-default {
    background: var(--evcc-estimate-default-bg, rgba(148, 163, 184, 0.12));
    border-color: var(--evcc-estimate-default-border, rgba(148, 163, 184, 0.28));
    color: var(--evcc-estimate-default-text, #cbd5e1);
  }

  .evcc-theme-preview-estimate-learned {
    background: var(--evcc-estimate-learned-bg, rgba(59, 130, 246, 0.12));
    border-color: var(--evcc-estimate-learned-border, rgba(59, 130, 246, 0.28));
    color: var(--evcc-estimate-learned-text, #60a5fa);
  }

  .evcc-theme-preview-learning-panel {
    background:
      linear-gradient(
        145deg,
        color-mix(in srgb, var(--evcc-learning-reanchor-highlight, var(--evcc-accent, #3b82f6)) 12%, transparent),
        transparent 62%
      ),
      var(--evcc-learning-panel-bg, var(--evcc-surface-panel, #1c2127));
    border-color: var(--evcc-learning-panel-border, var(--evcc-border-default, rgba(255, 255, 255, 0.12)));
    box-shadow: var(--evcc-learning-panel-shadow, none);
  }

  .evcc-theme-preview-note {
    color: var(--evcc-learning-note-text, var(--evcc-learning-text-secondary, rgba(255, 255, 255, 0.72)));
  }

  .evcc-theme-preview-modal-stage {
    position: relative;
    min-height: 260px;
    overflow: hidden;
    border-radius: var(--evcc-radius-card, 16px);
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.08));
  }

  .evcc-theme-preview-modal-backdrop {
    position: absolute;
    inset: 0;
    background: var(--evcc-modal-backdrop-bg, rgba(0, 0, 0, 0.7));
    backdrop-filter: blur(calc(var(--evcc-modal-backdrop-blur, 8) * 1px));
  }

  .evcc-theme-preview-modal {
    position: relative;
    z-index: 1;
    width: min(92%, 320px);
    margin: 18px auto;
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: var(--evcc-modal-padding, 16px);
    background: var(--evcc-modal-bg, #1c2127);
    border: 1px solid var(--evcc-modal-border, rgba(255, 255, 255, 0.14));
    border-radius: var(--evcc-modal-radius, 18px);
    box-shadow: var(--evcc-modal-shadow, 0 20px 60px rgba(0, 0, 0, 0.6));
  }

  .evcc-theme-preview-modal-title {
    font-size: 0.96rem;
    font-weight: 700;
  }

  .evcc-theme-preview-modal-accent-chip {
    background: var(--evcc-modal-accent-bg, color-mix(in srgb, var(--evcc-modal-accent, var(--evcc-accent, #3b82f6)) 18%, transparent));
    border-color: var(--evcc-modal-accent-border, color-mix(in srgb, var(--evcc-modal-accent, var(--evcc-accent, #3b82f6)) 36%, transparent));
    color: var(--evcc-modal-accent-text, var(--evcc-modal-accent, var(--evcc-accent, #3b82f6)));
  }

  .evcc-theme-preview-foundation-card {
    gap: var(--evcc-section-gap, 16px);
  }

  @keyframes evcc-theme-preview-pulse {
    0%, 100% {
      opacity: 0.85;
    }

    50% {
      opacity: 1;
    }
  }

  /* ------------------------------------------------------------------
     Animal Companion preview grid
     ------------------------------------------------------------------
     5 battery-state rows × N animal columns. Each cell is a thumbnail
     <animal-svg>. The grid inherits the card's draft theme tokens via
     CSS custom-property cascade — no JS wiring needed to make the
     previews react to token edits.
  ----------------------------------------------------------------- */
  .evcc-theme-preview-animal-grid {
    display: flex;
    flex-direction: column;
    gap: 8px;
    background: var(--evcc-surface-panel, var(--evcc-panel-bg, #1c2127));
    border: 1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
    border-radius: var(--evcc-radius-card, 16px);
    padding: 14px;
  }

  .evcc-theme-preview-animal-row {
    display: grid;
    grid-template-columns: 90px repeat(auto-fit, minmax(80px, 1fr));
    align-items: center;
    gap: 8px;
  }

  /* Single-animal (sub-group) preview: one larger cell, centred. */
  .evcc-theme-preview-animal-grid--single .evcc-theme-preview-animal-row {
    grid-template-columns: 90px 1fr;
  }

  .evcc-theme-preview-animal-grid--single .evcc-theme-preview-animal-cell {
    min-height: 110px;
    padding: 8px;
  }

  .evcc-theme-preview-animal-grid--single .evcc-theme-preview-animal-collabel {
    text-align: left;
    padding-left: 8px;
  }

  .evcc-theme-preview-animal-row--header {
    border-bottom: 1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
    padding-bottom: 6px;
    margin-bottom: 2px;
  }

  .evcc-theme-preview-animal-rowlabel {
    display: flex;
    flex-direction: column;
    gap: 1px;
    font-size: 12px;
    color: var(--evcc-text-primary, #e6e6e6);
  }

  .evcc-theme-preview-animal-rowlabel-title {
    font-weight: 600;
  }

  .evcc-theme-preview-animal-rowlabel-hint {
    font-size: 10px;
    color: var(--evcc-text-muted, #9ca3af);
  }

  .evcc-theme-preview-animal-collabel {
    font-size: 11px;
    text-align: center;
    text-transform: capitalize;
    color: var(--evcc-text-secondary, #c7c9d1);
  }

  .evcc-theme-preview-animal-cell {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 4px;
    background: var(--evcc-surface-elevated, rgba(255, 255, 255, 0.03));
    border-radius: 8px;
    min-height: 60px;
  }

  .evcc-theme-preview-animal-note {
    font-size: 11px;
    line-height: 1.45;
    color: var(--evcc-text-muted, #9ca3af);
    margin-top: 8px;
  }

  .evcc-theme-preview-animal-note code {
    background: var(--evcc-surface-elevated, rgba(255, 255, 255, 0.06));
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 10.5px;
  }

  @media (max-width: 1100px) {
    .evcc-theme-editor-pane {
      flex-direction: column;
    }

    .evcc-theme-preview-column {
      flex: 0 0 auto;
      width: 100%;
      overflow: visible;
      order: -1;
      padding-right: 0;
    }

    .evcc-theme-preview-pane {
      max-height: none;
      overflow: visible;
    }
  }
`;
