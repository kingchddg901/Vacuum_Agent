// CSS styles for the Room Access modal: chip grid, issue list, and save error states.

export const roomAccessStyles = `
  .evcc-room-access-modal {
    max-width: 560px;
  }

  .evcc-room-access-section,
  .evcc-room-access-issues {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 12px;
    border-radius: var(--evcc-radius-panel, 14px);
    border: 1px solid var(--evcc-border-default);
    background: color-mix(in srgb, var(--evcc-surface-panel) 85%, transparent);
  }

  .evcc-room-access-help {
    font-size: 0.82rem;
    line-height: 1.45;
    color: var(--evcc-text-secondary);
  }

  .evcc-room-access-chip-grid {
    gap: 8px;
  }

  .evcc-room-access-chip {
    transition:
      background var(--evcc-transition-normal, 150ms ease),
      border-color var(--evcc-transition-normal, 150ms ease),
      color var(--evcc-transition-normal, 150ms ease),
      opacity var(--evcc-transition-normal, 150ms ease);
  }

  .evcc-room-access-chip:not(.active):not(.evcc-room-access-chip--readonly) {
    opacity: 0.72;
  }

  .evcc-room-access-chip--readonly {
    cursor: default;
    opacity: 0.92;
  }

  .evcc-room-access-chip--missing {
    border-color: color-mix(in srgb, var(--evcc-sem-warning) 45%, transparent);
    color: var(--evcc-sem-warning);
  }

  .evcc-room-access-chip--claimed {
    opacity: 0.35;
    cursor: not-allowed;
    pointer-events: none;
  }

  .evcc-room-access-issue-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .evcc-room-access-issue,
  .evcc-room-access-save-error,
  .evcc-room-access-empty {
    font-size: 0.82rem;
    line-height: 1.4;
  }

  .evcc-room-access-issue,
  .evcc-room-access-save-error {
    color: var(--evcc-sem-warning);
  }

  .evcc-room-access-save-error {
    padding: 10px 12px;
    border-radius: 10px;
    border: 1px solid color-mix(in srgb, var(--evcc-sem-warning) 32%, transparent);
    background: color-mix(in srgb, var(--evcc-sem-warning) 12%, transparent);
  }

  .evcc-room-access-empty {
    color: var(--evcc-text-muted);
  }
`;
