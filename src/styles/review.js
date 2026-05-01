// CSS styles for the Review tab panels, job cards, matcher, stat rows, and badges.

export const reviewStyles = `
  .evcc-review-view {
    display: flex;
    flex-direction: column;
    gap: var(--evcc-grid-gap, 12px);
  }

  .evcc-review-grid {
    display: grid;
    gap: var(--evcc-grid-gap, 12px);
    grid-template-columns: 1fr;
  }

  .evcc-review-panel {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 16px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-default);
    background: var(--evcc-surface-panel);
  }

  .evcc-review-panel--wide {
    grid-column: 1 / -1;
  }

  .evcc-review-panel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  .evcc-review-panel-title {
    font-size: 0.98rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-review-panel-subtitle {
    margin-top: 4px;
    font-size: 0.82rem;
    color: var(--evcc-text-secondary);
    line-height: 1.45;
  }

  .evcc-review-stats,
  .evcc-review-filters {
    display: grid;
    gap: 12px;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  }

  .evcc-review-matcher {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .evcc-review-chip-filter {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .evcc-review-reason-chips {
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-width: min(100%, 460px);
  }

  .evcc-review-filter-chips {
    gap: 8px;
  }

  .evcc-review-matcher-grid {
    display: grid;
    gap: 14px;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  }

  .evcc-review-matcher-field {
    padding: 14px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-subtle);
    background: var(--evcc-surface-raised);
  }

  .evcc-review-matcher-actions {
    display: flex;
    justify-content: flex-end;
  }

  .evcc-review-matcher-results {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 14px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-subtle);
    background: color-mix(in srgb, var(--evcc-surface-panel) 88%, white 12%);
  }

  .evcc-review-matcher-results-header {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .evcc-review-matcher-match-chips {
    gap: 8px;
  }

  .evcc-review-stat,
  .evcc-review-job-card {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 14px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-subtle);
    background: var(--evcc-surface-raised);
  }

  .evcc-review-stat-value,
  .evcc-review-job-title {
    font-size: 0.96rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-review-stat-label,
  .evcc-review-job-subtitle,
  .evcc-review-kv-label,
  .evcc-review-kv-subtitle {
    font-size: 0.78rem;
    color: var(--evcc-text-secondary);
  }

  .evcc-review-job-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .evcc-review-job-card--excluded {
    border-color: color-mix(in srgb, var(--evcc-sem-error) 28%, transparent);
  }

  .evcc-review-job-card--suggested {
    border-color: color-mix(in srgb, var(--evcc-sem-warning) 28%, transparent);
  }

  .evcc-review-job-header,
  .evcc-review-job-badges,
  .evcc-review-job-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    justify-content: space-between;
  }

  .evcc-review-job-badges {
    justify-content: flex-end;
  }

  .evcc-review-badge--excluded {
    border-color: color-mix(in srgb, var(--evcc-sem-error) 40%, transparent);
    background: color-mix(in srgb, var(--evcc-sem-error) 14%, transparent);
    color: var(--evcc-sem-error);
  }

  .evcc-review-badge--suggested,
  .evcc-review-badge--warning {
    border-color: color-mix(in srgb, var(--evcc-sem-warning) 40%, transparent);
    background: color-mix(in srgb, var(--evcc-sem-warning) 14%, transparent);
    color: var(--evcc-sem-warning);
  }

  .evcc-review-badge--neutral {
    border-color: var(--evcc-border-default);
    background: var(--evcc-surface-input);
    color: var(--evcc-text-secondary);
  }

  .evcc-review-job-grid {
    display: grid;
    gap: 10px;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  }

  .evcc-review-kv {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .evcc-review-kv-value,
  .evcc-review-job-note {
    font-size: 0.84rem;
    color: var(--evcc-text-primary);
    line-height: 1.5;
  }

  .evcc-review-job-note {
    padding: 10px 12px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-subtle);
    background: color-mix(in srgb, var(--evcc-surface-panel) 90%, white 10%);
  }

  .evcc-review-reason {
    min-width: 220px;
  }

  .evcc-review-empty {
    padding: 12px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px dashed var(--evcc-border-default);
    color: var(--evcc-text-muted);
    font-size: 0.84rem;
    line-height: 1.5;
  }

  @media (max-width: 720px) {
    .evcc-review-grid,
    .evcc-review-stats,
    .evcc-review-filters,
    .evcc-review-job-grid,
    .evcc-review-matcher-grid {
      grid-template-columns: 1fr;
    }
  }
`;
