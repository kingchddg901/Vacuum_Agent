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
    /* Long suggested-profile names must wrap inside the narrow card, not clip. */
    white-space: normal;
    height: auto;
    min-height: 0;
    line-height: 1.3;
    text-align: center;
    overflow-wrap: anywhere;
    max-width: 100%;
  }

  .evcc-metrics-card-title {
    min-width: 0;
    overflow-wrap: anywhere;
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

  /* Searchable profile filter: label + search input on one row, then a
     height-capped, scrollable chip area so a long profile list never walls the
     panel. Shared by the Metrics and Learning Review filters. */
  .evcc-chip-filter-head {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .evcc-chip-filter-head .evcc-field-label {
    margin: 0;
    flex: 0 0 auto;
  }

  .evcc-chip-search {
    flex: 1 1 auto;
    min-width: 0;
    height: 28px;
    padding: 0 10px;
    font-family: inherit;
    font-size: 0.8rem;
    color: var(--evcc-text-primary);
    background: var(--evcc-surface-input);
    border: 1px solid var(--evcc-border-default);
    border-radius: var(--evcc-radius-inner, 8px);
    outline: none;
  }

  .evcc-chip-search:focus {
    border-color: var(--evcc-accent, var(--evcc-border-strong));
  }

  .evcc-chip-filter--searchable .evcc-metrics-filter-chips,
  .evcc-chip-filter--searchable .evcc-review-filter-chips {
    max-height: 132px;
    overflow-y: auto;
    padding-right: 2px;
  }

  /* Long disambiguated labels wrap inside the chip (like the card badges) so the
     group only ever scrolls vertically, never overflows its column width. */
  .evcc-chip-filter--searchable .evcc-chip {
    white-space: normal;
    height: auto;
    line-height: 1.25;
    text-align: center;
    overflow-wrap: anywhere;
    max-width: 100%;
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

  /* Battery sub-tab */

  .evcc-metrics-section-title {
    font-size: 0.92rem;
    font-weight: 600;
    color: var(--evcc-text-strong, var(--primary-text-color));
    margin-top: 4px;
  }

  .evcc-metrics-section-subtitle {
    font-size: 0.78rem;
    color: var(--evcc-text-muted);
    line-height: 1.45;
    margin-top: -6px;
  }

  .evcc-metrics-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }

  .evcc-metrics-table th,
  .evcc-metrics-table td {
    text-align: left;
    padding: 6px 10px;
    border-bottom: 1px solid var(--evcc-border-default);
  }

  .evcc-metrics-table th {
    font-weight: 600;
    color: var(--evcc-text-muted);
    font-size: 0.76rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .evcc-metrics-table tr:last-child td {
    border-bottom: none;
  }

  .evcc-metrics-table em {
    color: var(--evcc-text-muted);
    font-style: normal;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .evcc-metrics-codeblock {
    background: var(--evcc-bg-elevated, rgba(0, 0, 0, 0.18));
    border: 1px solid var(--evcc-border-default);
    border-radius: var(--evcc-radius-inner, 8px);
    padding: 10px 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.78rem;
    color: var(--evcc-text-default);
    white-space: pre-wrap;
    word-break: break-all;
    margin: 0;
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
