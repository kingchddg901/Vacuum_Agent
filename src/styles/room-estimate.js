// CSS styles for the Room Estimate modal: section layout, estimate rows, and notes.

export const roomEstimateStyles = `
  .evcc-room-estimate-modal {
    max-width: 560px;
  }

  .evcc-room-estimate-header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }

  .evcc-room-estimate-subtitle {
    margin-top: 4px;
    color: var(--evcc-modal-text-secondary, var(--evcc-text-secondary));
    font-size: 0.88rem;
  }

  .evcc-room-estimate-section {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .evcc-room-estimate-grid {
    display: grid;
    gap: 8px;
  }

  .evcc-room-estimate-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 10px 12px;
    border: 1px solid var(--evcc-modal-border-subtle, var(--evcc-border-subtle));
    border-radius: 12px;
    background: color-mix(in srgb, var(--evcc-modal-surface-panel, var(--evcc-surface-panel)) 82%, transparent);
    color: var(--evcc-modal-text-secondary, var(--evcc-text-secondary));
  }

  .evcc-room-estimate-row span:last-child {
    color: var(--evcc-modal-text-primary, var(--evcc-text-primary));
    font-weight: 600;
    text-align: right;
  }

  .evcc-room-estimate-notes {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .evcc-room-estimate-note,
  .evcc-room-estimate-empty {
    padding: 12px 14px;
    border-radius: 12px;
    border: 1px dashed var(--evcc-modal-border-subtle, var(--evcc-border-subtle));
    color: var(--evcc-modal-text-secondary, var(--evcc-text-secondary));
    background: color-mix(in srgb, var(--evcc-modal-surface-panel, var(--evcc-surface-panel)) 70%, transparent);
  }
`;
