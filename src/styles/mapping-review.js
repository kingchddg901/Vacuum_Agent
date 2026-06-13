// CSS styles for the Mapping Review tab: room cards, bounds grid, job history entries.

export const mappingReviewStyles = `
  .evcc-mrev-view {
    display: flex;
    flex-direction: column;
    gap: var(--evcc-grid-gap, 12px);
  }

  .evcc-mrev-filter-label {
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--evcc-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .evcc-mrev-grid {
    display: grid;
    gap: var(--evcc-grid-gap, 12px);
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  }

  .evcc-mrev-card {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 14px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-default);
    background: var(--evcc-surface-panel);
  }

  .evcc-mrev-card-header {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .evcc-mrev-room-name {
    font-size: 0.96rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-mrev-room-meta {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
  }

  .evcc-mrev-room-id {
    font-size: 0.75rem;
    color: var(--evcc-text-secondary);
  }

  .evcc-mrev-badge {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    padding: 2px 8px;
    border-radius: 99px;
    font-size: 0.72rem;
    font-weight: 600;
  }

  /* Redundant non-color cue: a per-state shape mark (src/renderers/
     badge-marks.js) so badges read without relying on hue — covers
     CVD + monochromacy, and disambiguates likely from warn (shared color). */
  .evcc-mrev-badge-mark {
    width: 0.95em;
    height: 0.95em;
    flex: none;
  }

  .evcc-mrev-badge--ok {
    background: color-mix(in srgb, var(--evcc-sem-success) 15%, transparent);
    color: var(--evcc-sem-success);
  }

  .evcc-mrev-badge--likely {
    background: color-mix(in srgb, var(--evcc-sem-warning) 12%, transparent);
    color: var(--evcc-sem-warning);
    font-style: italic;
  }

  .evcc-mrev-badge--warn {
    background: color-mix(in srgb, var(--evcc-sem-warning) 15%, transparent);
    color: var(--evcc-sem-warning);
  }

  .evcc-mrev-badge--outlier {
    background: color-mix(in srgb, var(--evcc-sem-error) 15%, transparent);
    color: var(--evcc-sem-error);
  }

  .evcc-mrev-badge--baseline {
    background: color-mix(in srgb, var(--evcc-sem-info) 15%, transparent);
    color: var(--evcc-sem-info);
  }

  .evcc-mrev-badge--excluded {
    background: color-mix(in srgb, var(--evcc-text-muted, rgba(240,242,245,0.48)) 18%, transparent);
    color: var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    font-style: italic;
  }

  .evcc-mrev-no-bounds {
    font-size: 0.82rem;
    color: var(--evcc-text-secondary);
    font-style: italic;
  }

  .evcc-mrev-bounds-block {
    background: color-mix(in srgb, var(--evcc-surface-raised, #fff) 6%, transparent);
    border-radius: var(--evcc-radius-inner, 8px);
    padding: 10px 12px;
  }

  .evcc-mrev-bounds-grid {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .evcc-mrev-bounds-grid--compact {
    gap: 3px;
  }

  .evcc-mrev-bounds-row {
    display: grid;
    grid-template-columns: 56px 1fr auto;
    align-items: baseline;
    gap: 6px;
    font-size: 0.82rem;
  }

  .evcc-mrev-bounds-row--sub {
    opacity: 0.7;
  }

  .evcc-mrev-bounds-key {
    font-weight: 600;
    color: var(--evcc-text-secondary);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .evcc-mrev-bounds-val {
    color: var(--evcc-text-primary);
    font-variant-numeric: tabular-nums;
  }

  .evcc-mrev-bounds-dim {
    color: var(--evcc-text-secondary);
    font-size: 0.75rem;
    text-align: right;
    white-space: nowrap;
  }

  .evcc-mrev-history {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .evcc-mrev-history-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--evcc-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .evcc-mrev-job-entry {
    padding: 8px 10px;
    border-radius: 6px;
    border: 1px solid var(--evcc-border-default);
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .evcc-mrev-job-entry--outlier {
    border-color: color-mix(in srgb, var(--evcc-sem-error) 40%, transparent);
    background: color-mix(in srgb, var(--evcc-sem-error) 5%, transparent);
  }

  .evcc-mrev-job-entry--excluded {
    opacity: 0.55;
    border-color: var(--evcc-border-subtle, rgba(255,255,255,0.06));
  }

  .evcc-mrev-job-header {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
  }

  .evcc-mrev-job-id {
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--evcc-text-primary);
    font-variant-numeric: tabular-nums;
  }

  .evcc-mrev-job-id--excluded {
    text-decoration: line-through;
    color: var(--evcc-text-muted);
  }

  .evcc-mrev-job-date {
    font-size: 0.75rem;
    color: var(--evcc-text-secondary);
  }

  .evcc-mrev-job-actions {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .evcc-mrev-job-action-btn {
    font-size: 0.70rem;
    padding: 2px 8px;
    height: 20px;
    opacity: 0.85;
  }

  .evcc-mrev-job-action-btn:hover {
    opacity: 1;
  }

  .evcc-mrev-job-pending {
    font-size: 0.75rem;
    color: var(--evcc-text-muted);
    padding: 2px 4px;
  }

  .evcc-mrev-bounds-grid--muted {
    opacity: 0.6;
  }

  .evcc-chip--sm {
    height: 20px;
    padding: 0 8px;
    font-size: 0.70rem;
  }

  .evcc-mrev-card-footer {
    display: flex;
    justify-content: flex-end;
    gap: 6px;
    padding-top: 2px;
  }

  .evcc-mrev-clear-btn--disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .evcc-mrev-rebuild-btn {
    background: color-mix(in srgb, var(--evcc-accent, #6366f1) 15%, transparent);
    color: var(--evcc-accent, #6366f1);
    border-color: color-mix(in srgb, var(--evcc-accent, #6366f1) 30%, transparent);
  }

  .evcc-mrev-rebuild-btn:hover {
    background: color-mix(in srgb, var(--evcc-accent, #6366f1) 25%, transparent);
  }

  @media (max-width: 480px) {
    .evcc-mrev-grid {
      grid-template-columns: 1fr;
    }
  }
`;
