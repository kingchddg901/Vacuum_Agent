// CSS for the Saved Zones sidebar panel (Wave 3b) — mirrors the run-profiles
// panel tokens so the two sidecol panels read as a set. Cut 2 adds the collapse
// header, per-row multi-select, the shared setting selects and the actions bar.

export const savedZonesStyles = `
  .evcc-saved-zones-panel {
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

  .evcc-saved-zones-header {
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    user-select: none;
  }
  .evcc-saved-zones-header:focus-visible {
    outline: 2px solid var(--evcc-accent, #4c9be8);
    outline-offset: 2px;
    border-radius: 6px;
  }

  .evcc-saved-zones-header-text {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
    flex: 1 1 auto;
  }

  .evcc-saved-zones-title {
    font-size: 0.96rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-saved-zones-subtitle,
  .evcc-saved-zones-empty {
    font-size: 0.78rem;
    line-height: 1.45;
    color: var(--evcc-text-secondary);
  }

  .evcc-saved-zones-selbadge {
    flex: 0 0 auto;
    font-size: 0.72rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 999px;
    color: var(--evcc-on-accent, #fff);
    background: var(--evcc-accent, #4c9be8);
  }

  .evcc-saved-zones-chevron {
    flex: 0 0 auto;
    color: var(--evcc-text-muted);
    transition: transform 0.15s ease;
  }
  .evcc-saved-zones-chevron.is-collapsed {
    transform: rotate(-90deg);
  }

  .evcc-saved-zones-settings {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 12px;
    border-radius: var(--evcc-radius-inner, 12px);
    border: 1px solid var(--evcc-border-default);
    background: color-mix(in srgb, var(--evcc-surface-input) 60%, transparent);
  }

  .evcc-saved-zones-section-title {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--evcc-text-muted);
  }

  .evcc-saved-zones-note {
    display: block;
    margin-top: 3px;
    font-size: 0.72rem;
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
    color: var(--evcc-text-secondary);
  }

  .evcc-saved-zones-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .evcc-saved-zones-room-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .evcc-saved-zones-room-header {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--evcc-text-muted);
  }

  .evcc-saved-zones-item {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 10px 12px;
    border-radius: var(--evcc-radius-inner, 12px);
    border: 1px solid var(--evcc-border-default);
    background: color-mix(in srgb, var(--evcc-surface-input) 72%, transparent);
  }

  .evcc-saved-zones-item.is-selected {
    border-color: var(--evcc-accent, #4c9be8);
    background: color-mix(in srgb, var(--evcc-accent, #4c9be8) 16%, var(--evcc-surface-input));
  }

  .evcc-saved-zones-item--disabled {
    opacity: 0.5;
  }

  .evcc-saved-zones-item-main {
    display: flex;
    align-items: baseline;
    gap: 8px;
    min-width: 0;
    flex: 1 1 auto;
    cursor: pointer;
  }

  .evcc-saved-zones-check {
    flex: 0 0 auto;
    align-self: center;
    width: 16px;
    height: 16px;
    accent-color: var(--evcc-accent, #4c9be8);
    cursor: pointer;
  }

  .evcc-saved-zones-item-name {
    font-size: 0.84rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .evcc-saved-zones-area {
    font-size: 0.74rem;
    color: var(--evcc-text-muted);
    white-space: nowrap;
  }

  .evcc-saved-zones-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  .evcc-saved-zones-cap-warn {
    font-size: 0.74rem;
    font-weight: 600;
    color: var(--evcc-danger, #e5534b);
  }

  .evcc-saved-zones-drawbtn {
    align-self: flex-start;
    font-weight: 700;
  }

  .evcc-saved-zones-draw {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 12px;
    border-radius: var(--evcc-radius-inner, 12px);
    border: 1px dashed var(--evcc-accent, #4c9be8);
    background: color-mix(in srgb, var(--evcc-accent, #4c9be8) 10%, transparent);
  }
  .evcc-saved-zones-draw-hint {
    font-size: 0.78rem;
    line-height: 1.4;
    color: var(--evcc-text-secondary);
  }
  .evcc-saved-zones-draw-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
`;
