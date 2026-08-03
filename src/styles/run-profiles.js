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

  /* ---- Ordered-steps editor (room groups + charge steps) ---- */

  .evcc-run-profiles-steps {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .evcc-run-profiles-steps-hint {
    font-size: 0.72rem;
    line-height: 1.4;
    color: var(--evcc-text-muted);
  }

  .evcc-run-profiles-steps-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .evcc-run-profiles-step {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 9px;
    border-radius: var(--evcc-radius-inner, 12px);
    border: 1px solid var(--evcc-border-default);
    background: color-mix(in srgb, var(--evcc-surface-input) 60%, transparent);
  }

  .evcc-run-profiles-step--charge {
    border-color: color-mix(in srgb, var(--evcc-accent, #4c9aff) 55%, var(--evcc-border-default));
    background: color-mix(in srgb, var(--evcc-accent, #4c9aff) 12%, transparent);
  }

  .evcc-run-profiles-step--wait {
    border-color: color-mix(in srgb, var(--evcc-sem-warning, #d99a2b) 45%, var(--evcc-border-default));
    background: color-mix(in srgb, var(--evcc-sem-warning, #d99a2b) 10%, transparent);
  }

  .evcc-run-profiles-step--zone {
    border-color: color-mix(in srgb, var(--evcc-sem-success, #3ba55d) 45%, var(--evcc-border-default));
    background: color-mix(in srgb, var(--evcc-sem-success, #3ba55d) 10%, transparent);
  }

  /* A legacy leading/trailing charge_wait/wait has nothing to bracket and will never
     actually run (CARD-6 clause (1)) -- struck-through + dashed, mirrors the queue's
     own --skipped chip treatment elsewhere in this card. */
  .evcc-run-profiles-step--unsupported {
    border-style: dashed;
    opacity: 0.7;
  }
  .evcc-run-profiles-step--unsupported .evcc-run-profiles-step-kind {
    text-decoration: line-through;
  }
  .evcc-run-profiles-step-warning {
    flex-basis: 100%;
    font-size: 0.7rem;
    color: var(--evcc-sem-warning, #d99a2b);
  }

  .evcc-run-profiles-step-num {
    flex: 0 0 auto;
    width: 20px;
    height: 20px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    font-size: 0.7rem;
    font-weight: 700;
    color: var(--evcc-text-secondary);
    background: color-mix(in srgb, var(--evcc-surface-input) 90%, transparent);
  }

  .evcc-run-profiles-step-body {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    font-size: 0.78rem;
    color: var(--evcc-text-secondary);
  }

  .evcc-run-profiles-step-kind {
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-run-profiles-step-rooms {
    min-width: 0;
    overflow-wrap: anywhere;
  }

  .evcc-run-profiles-step-mode {
    font-size: 0.66rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 1px 6px;
    border-radius: 999px;
    color: var(--evcc-text-muted);
    background: color-mix(in srgb, var(--evcc-surface-input) 92%, transparent);
  }

  .evcc-run-profiles-charge-input {
    width: 58px;
    min-height: 30px;
    padding: 0 8px;
    border-radius: var(--evcc-radius-inner, 10px);
    border: 1px solid var(--evcc-border-default);
    background: var(--evcc-surface-input, rgba(255, 255, 255, 0.05));
    color: var(--evcc-text-primary);
    font: inherit;
    text-align: end;
  }

  .evcc-run-profiles-step-controls {
    flex: 0 0 auto;
    display: flex;
    gap: 4px;
  }

  .evcc-run-profiles-step-btn {
    width: 26px;
    height: 26px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    border: 1px solid var(--evcc-border-default);
    background: var(--evcc-surface-input, rgba(255, 255, 255, 0.05));
    color: var(--evcc-text-secondary);
    font: inherit;
    cursor: pointer;
  }

  .evcc-run-profiles-step-btn:disabled {
    opacity: 0.35;
    cursor: default;
  }

  .evcc-run-profiles-step-btn--remove {
    color: var(--evcc-danger, #ff6b6b);
  }

  .evcc-run-profiles-steps-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  /* ---- Read-only run sequence (admits the charge step in the selected-profile card) ---- */

  .evcc-run-profiles-sequence {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .evcc-run-profiles-seq-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
    counter-reset: evcc-seq;
  }

  .evcc-run-profiles-seq-step {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.78rem;
    color: var(--evcc-text-secondary);
  }

  .evcc-run-profiles-seq-step::before {
    counter-increment: evcc-seq;
    content: counter(evcc-seq);
    flex: 0 0 auto;
    width: 16px;
    height: 16px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    font-size: 0.62rem;
    font-weight: 700;
    color: var(--evcc-text-muted);
    background: color-mix(in srgb, var(--evcc-surface-input) 90%, transparent);
  }

  .evcc-run-profiles-seq-step--charge,
  .evcc-run-profiles-seq-step--wait,
  .evcc-run-profiles-seq-step--zone {
    color: var(--evcc-text-primary);
    font-weight: 600;
  }

  .evcc-run-profiles-seq-kind {
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-run-profiles-seq-mode {
    font-size: 0.64rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 1px 5px;
    border-radius: 999px;
    color: var(--evcc-text-muted);
    background: color-mix(in srgb, var(--evcc-surface-input) 92%, transparent);
  }

  /* ---- Pre-run "This run" stepped preview (Rooms view, above the flat queue) ---- */

  .evcc-stepped-run-preview {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px 14px;
    border-radius: var(--evcc-radius-panel, 16px);
    border: 1px solid color-mix(in srgb, var(--evcc-accent, #4c9aff) 40%, var(--evcc-border-default));
    background: color-mix(in srgb, var(--evcc-accent, #4c9aff) 8%, transparent);
  }

  .evcc-stepped-run-preview-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    width: 100%;
    padding: 0;
    background: none;
    border: none;
    cursor: pointer;
    font: inherit;
    text-align: start;
  }

  .evcc-stepped-run-preview-title {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--evcc-text-muted);
  }

  .evcc-stepped-run-preview-caret {
    font-size: 0.7rem;
    color: var(--evcc-text-muted);
  }

  /* RTL: the COLLAPSED caret glyph (▸) points along the reading direction, so
     mirror it to point ◂ toward the now-right-aligned label. The EXPANDED ▾ is
     vertical — the horizontal flip is a visual no-op there. dir lives on the
     shadow host (applyDir), hence :host(); span needs inline-block for transform. */
  :host([dir="rtl"]) .evcc-stepped-run-preview-caret {
    display: inline-block;
    transform: scaleX(-1);
  }

  .evcc-stepped-run-preview--collapsed {
    gap: 0;
  }

  .evcc-stepped-run-preview-note {
    font-size: 0.72rem;
    line-height: 1.4;
    color: var(--evcc-text-muted);
  }

  /* Responsive collapse is handled by flex-wrap above (container-relative) —
     NOT a viewport @media query. The card can be narrower than the screen
     (HA panel, dashboard column, render harness), so a viewport breakpoint
     would leave the 320px panel overlapping the rooms on a wide screen. */
`;
