// CSS styles for the Base Station tab panels, stats, activity, and action cards.

export const baseStationStyles = `
  .evcc-base-station-view {
    display: flex;
    flex-direction: column;
    gap: var(--evcc-grid-gap, 12px);
  }

  .evcc-base-station-grid {
    display: grid;
    gap: var(--evcc-grid-gap, 12px);
    grid-template-columns: 1fr;
  }

  .evcc-base-station-panel {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 16px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-default);
    background: var(--evcc-surface-panel);
  }

  .evcc-base-station-panel--wide {
    grid-column: 1 / -1;
  }

  .evcc-base-station-panel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  .evcc-base-station-panel-title {
    font-size: 0.98rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-base-station-panel-subtitle,
  .evcc-base-station-updated {
    font-size: 0.82rem;
    color: var(--evcc-text-secondary);
    line-height: 1.45;
  }

  .evcc-base-station-stats,
  .evcc-base-station-activity-grid,
  .evcc-base-station-action-grid {
    display: grid;
    gap: 12px;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  }

  .evcc-base-station-stat,
  .evcc-base-station-activity-card,
  .evcc-base-station-action-card {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 14px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-subtle);
    background: var(--evcc-surface-raised);
  }

  .evcc-base-station-stat-value,
  .evcc-base-station-activity-time,
  .evcc-base-station-action-title {
    font-size: 0.96rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-base-station-stat-label,
  .evcc-base-station-activity-title,
  .evcc-base-station-action-state {
    font-size: 0.78rem;
    color: var(--evcc-text-secondary);
  }

  .evcc-base-station-activity-detail,
  .evcc-base-station-action-detail {
    font-size: 0.82rem;
    color: var(--evcc-text-muted);
    line-height: 1.45;
  }

  .evcc-base-station-action-card {
    width: 100%;
    text-align: left;
    cursor: pointer;
    transition:
      border-color var(--evcc-transition-normal, 150ms ease),
      transform var(--evcc-transition-normal, 150ms ease);
  }

  .evcc-base-station-action-card:hover:not(:disabled) {
    border-color: var(--evcc-border-strong);
    transform: translateY(-1px);
  }

  .evcc-base-station-action-card--allowed {
    background: color-mix(in srgb, var(--evcc-sem-success) 8%, var(--evcc-surface-raised));
  }

  .evcc-base-station-action-card--blocked {
    cursor: default;
    opacity: 0.78;
  }

  @media (max-width: 720px) {
    .evcc-base-station-grid {
      grid-template-columns: 1fr;
    }

    .evcc-base-station-stats,
    .evcc-base-station-activity-grid,
    .evcc-base-station-action-grid {
      grid-template-columns: 1fr;
    }
  }
`;
