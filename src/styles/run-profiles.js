// CSS styles for the Run Profiles sidebar panel, editor form, and field inputs.

export const runProfileStyles = `
  .evcc-rooms-workspace {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    align-items: start;
  }

  .evcc-rooms-main {
    flex: 2 1 380px;
    min-width: 0;
  }

  .evcc-run-profiles-panel {
    flex: 1 1 300px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 14px;
    border-radius: var(--evcc-radius-panel, 16px);
    border: 1px solid var(--evcc-border-default);
    background: var(--evcc-surface-panel, var(--evcc-panel-bg, #1c2127));
    box-shadow: var(--evcc-shadow-card, 0 6px 14px rgba(0, 0, 0, 0.14));
  }

  .evcc-run-profiles-panel-header {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .evcc-run-profiles-title {
    font-size: 0.96rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-run-profiles-subtitle {
    font-size: 0.78rem;
    line-height: 1.45;
    color: var(--evcc-text-secondary);
  }

  .evcc-run-profiles-editor,
  .evcc-run-profiles-selected {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 12px;
    border-radius: var(--evcc-radius-inner, 12px);
    border: 1px solid var(--evcc-border-default);
    background: color-mix(in srgb, var(--evcc-surface-input) 72%, transparent);
  }

  .evcc-run-profiles-editor-title,
  .evcc-run-profiles-selected-name {
    font-size: 0.84rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-run-profiles-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .evcc-run-profiles-label {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--evcc-text-muted);
  }

  .evcc-run-profiles-input {
    width: 100%;
    min-height: 38px;
    padding: 0 12px;
    border-radius: var(--evcc-radius-inner, 12px);
    border: 1px solid var(--evcc-border-default);
    background: var(--evcc-surface-input, rgba(255, 255, 255, 0.05));
    color: var(--evcc-text-primary);
    font: inherit;
  }

  .evcc-run-profiles-toggle {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 0.78rem;
    color: var(--evcc-text-secondary);
  }

  .evcc-run-profiles-editor-actions,
  .evcc-run-profiles-selected-actions,
  .evcc-run-profiles-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .evcc-run-profiles-selected-meta,
  .evcc-run-profiles-selected-summary,
  .evcc-run-profiles-empty {
    font-size: 0.78rem;
    line-height: 1.45;
    color: var(--evcc-text-secondary);
  }

  /* Responsive collapse is handled by flex-wrap above (container-relative) —
     NOT a viewport @media query. The card can be narrower than the screen
     (HA panel, dashboard column, render harness), so a viewport breakpoint
     would leave the 320px panel overlapping the rooms on a wide screen. */
`;
