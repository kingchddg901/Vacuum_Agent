// CSS styles for the Metrics tab panels, stats, filter chips, and card grids.

export const metricsStyles = `
  .evcc-metrics-view {
    display: flex;
    flex-direction: column;
    gap: var(--evcc-grid-gap, 12px);
  }

  .evcc-metrics-grid {
    display: grid;
    gap: var(--evcc-grid-gap, 12px);
    grid-template-columns: 1fr;
  }

  .evcc-metrics-panel {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 16px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-default);
    background: var(--evcc-surface-panel);
  }

  .evcc-metrics-panel--wide {
    grid-column: 1 / -1;
  }

  .evcc-metrics-panel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  .evcc-metrics-panel-title {
    font-size: 0.98rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-metrics-panel-subtitle,
  .evcc-metrics-card-subtitle,
  .evcc-metrics-stat-label {
    font-size: 0.82rem;
    color: var(--evcc-text-secondary);
    line-height: 1.45;
  }

  .evcc-metrics-stats,
  .evcc-metrics-filters,
  .evcc-metrics-window-grid,
  .evcc-metrics-card-grid {
    display: grid;
    gap: 12px;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  }

  .evcc-metrics-stat,
  .evcc-metrics-card {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 14px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-subtle);
    background: var(--evcc-surface-raised);
  }

  .evcc-metrics-stat-value,
  .evcc-metrics-card-value {
    font-size: 0.96rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-metrics-card-title {
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-metrics-card-header,
  .evcc-metrics-card-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    flex-wrap: wrap;
  }

  .evcc-metrics-card-badge {
    border-color: color-mix(in srgb, var(--evcc-sem-warning) 40%, transparent);
    background: color-mix(in srgb, var(--evcc-sem-warning) 14%, transparent);
    color: var(--evcc-sem-warning);
  }

  .evcc-metrics-card-detail,
  .evcc-metrics-card-secondary {
    font-size: 0.84rem;
    color: var(--evcc-text-secondary);
    line-height: 1.45;
  }

  .evcc-metrics-tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .evcc-metrics-chip-filter {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .evcc-metrics-filter-chips {
    gap: 8px;
  }

  .evcc-metrics-tab-panel,
  .evcc-metrics-section-stack {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .evcc-metrics-empty {
    padding: 12px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px dashed var(--evcc-border-default);
    color: var(--evcc-text-muted);
    font-size: 0.84rem;
    line-height: 1.5;
  }

  @media (max-width: 720px) {
    .evcc-metrics-grid,
    .evcc-metrics-stats,
    .evcc-metrics-filters,
    .evcc-metrics-window-grid,
    .evcc-metrics-card-grid {
      grid-template-columns: 1fr;
    }
  }
`;
