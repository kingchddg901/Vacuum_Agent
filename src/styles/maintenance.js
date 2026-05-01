/**
 * ============================================================
 * STYLES: MAINTENANCE
 * ============================================================
 *
 * PURPOSE
 * -------
 * Visual styling for the Maintenance tab.
 *
 * ============================================================
 */

export const maintenanceModalHostStyles = `
  .evcc-maintenance-modal {
    max-width: 560px;
  }

  .evcc-maintenance-modal-hero {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 14px;
    border-radius: var(--evcc-radius-inner, 10px);
    border: 1px solid var(--evcc-border-default);
    background: color-mix(in srgb, var(--evcc-surface-raised) 92%, white 8%);
  }

  .evcc-maintenance-modal-hero--status-good {
    background: color-mix(in srgb, var(--evcc-sem-success) 12%, var(--evcc-surface-raised));
  }

  .evcc-maintenance-modal-hero--status-warning,
  .evcc-maintenance-modal-hero--status-replace_soon {
    background: color-mix(in srgb, var(--evcc-sem-warning) 12%, var(--evcc-surface-raised));
  }

  .evcc-maintenance-modal-hero--status-replace_now {
    background: color-mix(in srgb, var(--evcc-sem-error) 12%, var(--evcc-surface-raised));
  }

  .evcc-maintenance-modal-hero-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .evcc-maintenance-modal-hero-label,
  .evcc-maintenance-modal-hero-status {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--evcc-text-secondary);
  }

  .evcc-maintenance-modal-hero-value {
    font-size: 1.18rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-maintenance-modal-hero-detail {
    font-size: 0.85rem;
    color: var(--evcc-text-secondary);
    line-height: 1.45;
  }

  .evcc-maintenance-modal-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .evcc-maintenance-guide-list,
  .evcc-maintenance-guide-notes {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .evcc-maintenance-guide-list {
    margin: 0;
    padding-left: 18px;
  }

  .evcc-maintenance-guide-item,
  .evcc-maintenance-guide-note,
  .evcc-maintenance-reset-hint {
    font-size: 0.86rem;
    line-height: 1.55;
    color: var(--evcc-text-secondary);
  }

  .evcc-maintenance-guide-note,
  .evcc-maintenance-reset-hint {
    padding: 12px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-subtle);
    background: var(--evcc-surface-raised);
  }

  .evcc-maintenance-reset-hint--success {
    border-color: color-mix(in srgb, var(--evcc-sem-success) 40%, transparent);
    background: color-mix(in srgb, var(--evcc-sem-success) 10%, var(--evcc-surface-raised));
    color: var(--evcc-text-primary);
  }

  .evcc-maintenance-reset-hint--error {
    border-color: color-mix(in srgb, var(--evcc-sem-error) 40%, transparent);
    background: color-mix(in srgb, var(--evcc-sem-error) 10%, var(--evcc-surface-raised));
    color: var(--evcc-text-primary);
  }

  .evcc-maintenance-reset-meta,
  .evcc-maintenance-reset-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
`;

export const maintenanceStyles = `
  .evcc-maintenance-view {
    display: flex;
    flex-direction: column;
    gap: var(--evcc-grid-gap, 12px);
  }

  .evcc-maintenance-grid {
    display: grid;
    gap: var(--evcc-grid-gap, 12px);
    grid-template-columns: 1fr;
  }

  .evcc-maintenance-panel {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 16px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-default);
    background: var(--evcc-surface-panel);
  }

  .evcc-maintenance-panel--wide {
    grid-column: 1 / -1;
  }

  .evcc-maintenance-panel--placeholder {
    border-style: dashed;
    opacity: 0.9;
  }

  .evcc-maintenance-panel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  .evcc-maintenance-meta-badge {
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    min-height: var(--evcc-chip-height, 24px);
    padding: var(--evcc-chip-padding, 5px 14px);
    border-radius: var(--evcc-chip-radius, 999px);
    border: 1px solid var(--evcc-chip-border, var(--evcc-border-default));
    background: var(--evcc-chip-bg, var(--evcc-surface-input));
    color: var(--evcc-chip-text, var(--evcc-text-secondary));
    font-size: 0.8rem;
    font-weight: 600;
    line-height: 1;
  }

  .evcc-maintenance-model-line {
    font-size: 0.82rem;
    color: var(--evcc-text-secondary);
  }

  .evcc-maintenance-panel-title {
    font-size: 0.98rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-maintenance-panel-subtitle {
    margin-top: 4px;
    font-size: 0.82rem;
    color: var(--evcc-text-secondary);
    line-height: 1.45;
  }

  .evcc-maintenance-stats {
    display: grid;
    gap: 10px;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .evcc-maintenance-stat {
    padding: 12px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-subtle);
    background: var(--evcc-surface-raised);
  }

  .evcc-maintenance-stat-value {
    font-size: 0.96rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-maintenance-stat-label {
    margin-top: 4px;
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--evcc-text-muted);
  }

  .evcc-maintenance-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .evcc-maintenance-grid > .evcc-maintenance-panel:nth-child(1),
  .evcc-maintenance-grid > .evcc-maintenance-panel:nth-child(2) {
    min-height: 100%;
  }

  .evcc-maintenance-tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .evcc-maintenance-tab-panel {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .evcc-maintenance-tab-header {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .evcc-maintenance-card-grid {
    display: grid;
    gap: 12px;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  }

  .evcc-maintenance-card {
    position: relative;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-height: 120px;
    padding: 14px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-default);
    background: color-mix(in srgb, var(--evcc-surface-raised) 92%, white 8%);
    width: 100%;
    text-align: left;
    cursor: pointer;
  }

  .evcc-maintenance-card::before {
    content: "";
    position: absolute;
    inset: 0;
    width: var(--maintenance-remaining, 0%);
    background: color-mix(in srgb, var(--evcc-accent) 18%, transparent);
    z-index: 0;
    transition:
      width var(--evcc-transition-normal, 150ms ease),
      background var(--evcc-transition-normal, 150ms ease);
  }

  .evcc-maintenance-card > * {
    position: relative;
    z-index: 1;
  }

  .evcc-maintenance-card--status-good::before {
    background: color-mix(in srgb, var(--evcc-sem-success) 16%, transparent);
  }

  .evcc-maintenance-card--status-warning::before,
  .evcc-maintenance-card--status-replace_soon::before {
    background: color-mix(in srgb, var(--evcc-sem-warning) 20%, transparent);
  }

  .evcc-maintenance-card--status-replace_now::before {
    background: color-mix(in srgb, var(--evcc-sem-error) 22%, transparent);
  }

  .evcc-maintenance-card--unavailable {
    opacity: 0.7;
  }

  .evcc-maintenance-card:hover,
  .evcc-maintenance-item:hover {
    border-color: var(--evcc-border-strong);
  }

  .evcc-maintenance-card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  .evcc-maintenance-card-title {
    font-size: 0.92rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-maintenance-card-status {
    flex-shrink: 0;
    font-size: 0.76rem;
    font-weight: 600;
    color: var(--evcc-text-secondary);
  }

  .evcc-maintenance-card-value {
    font-size: 1.08rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-maintenance-card-detail {
    font-size: 0.82rem;
    line-height: 1.45;
    color: var(--evcc-text-secondary);
  }

  .evcc-maintenance-card-secondary {
    margin-top: auto;
    font-size: 0.78rem;
    color: var(--evcc-text-muted);
  }

  .evcc-maintenance-item {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    padding: 12px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-subtle);
    background: var(--evcc-surface-raised);
    width: 100%;
    text-align: left;
    cursor: pointer;
  }

  .evcc-maintenance-item-main {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .evcc-maintenance-item-name {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--evcc-text-primary);
  }

  .evcc-maintenance-item-detail {
    font-size: 0.8rem;
    color: var(--evcc-text-secondary);
    line-height: 1.45;
  }

  .evcc-maintenance-item-side {
    flex-shrink: 0;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--evcc-text-secondary);
    text-align: right;
  }

  .evcc-maintenance-item-detail {
    font-size: 0.8rem;
    color: var(--evcc-text-secondary);
    line-height: 1.45;
  }

  .evcc-maintenance-empty {
    padding: 12px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px dashed var(--evcc-border-default);
    color: var(--evcc-text-muted);
    font-size: 0.84rem;
    line-height: 1.5;
  }

  ${maintenanceModalHostStyles}

  @media (max-width: 720px) {
    .evcc-maintenance-grid {
      grid-template-columns: 1fr;
    }

    .evcc-maintenance-stats {
      grid-template-columns: 1fr;
    }
  }
`;
