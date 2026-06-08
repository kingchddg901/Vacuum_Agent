/**
 * ============================================================
 * STYLES: EXTERNAL JOBS
 * ============================================================
 *
 * Two exports because the feature spans two style targets:
 *   - externalJobsStyles        -> the card shadow root (subtab strip + list)
 *   - externalWizardModalStyles -> the body-level modal host (the wizard)
 *
 * Uses ONLY canonical foundation tokens (no new tokens): --evcc-accent,
 * --evcc-surface-{input,raised,panel}, --evcc-text-{primary,secondary},
 * --evcc-border-{default,strong}, --evcc-sem-{warning,error}, --evcc-radius-*.
 * The wizard reuses the shared .evcc-chip + .evcc-editor-field-group classes
 * already present in the modal host; chip active state is the foundation's
 * `.evcc-chip.active`, so it is not re-styled here.
 * ============================================================
 */

const SHARED_BTN = `
  .evcc-btn {
    border: 1px solid var(--evcc-border-default);
    background: var(--evcc-surface-input);
    color: var(--evcc-text-primary);
    border-radius: var(--evcc-radius-inner, 8px);
    padding: 8px 14px;
    font-size: 0.86rem;
    cursor: pointer;
  }
  .evcc-btn:hover { background: var(--evcc-surface-panel); }
  .evcc-btn[disabled] { opacity: 0.5; cursor: default; }
  .evcc-btn-primary {
    background: color-mix(in srgb, var(--evcc-accent) 18%, transparent);
    border-color: color-mix(in srgb, var(--evcc-accent) 40%, transparent);
    color: var(--evcc-accent);
    font-weight: 600;
  }
  .evcc-btn-warn {
    background: color-mix(in srgb, var(--evcc-sem-warning) 18%, transparent);
    border-color: color-mix(in srgb, var(--evcc-sem-warning) 40%, transparent);
    color: var(--evcc-sem-warning);
  }
  .evcc-btn-ghost { background: transparent; }
`;

export const externalJobsStyles = `
  .evcc-review-subtabs { display: flex; gap: 8px; margin-bottom: 14px; }
  .evcc-review-subtab {
    border: 1px solid var(--evcc-border-default);
    background: transparent;
    color: var(--evcc-text-secondary);
    border-radius: var(--evcc-radius-chip, 999px);
    padding: 6px 16px;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .evcc-review-subtab.is-active {
    background: color-mix(in srgb, var(--evcc-accent) 18%, transparent);
    border-color: color-mix(in srgb, var(--evcc-accent) 40%, transparent);
    color: var(--evcc-accent);
    font-weight: 600;
  }
  .evcc-external-empty { padding: 24px; text-align: center; color: var(--evcc-text-secondary); }
  .evcc-external-list { display: flex; flex-direction: column; gap: 10px; }
  .evcc-external-card {
    display: flex; justify-content: space-between; align-items: center; gap: 12px;
    padding: 14px 16px;
    background: var(--evcc-surface-raised);
    border: 1px solid var(--evcc-border-default);
    border-radius: var(--evcc-radius-card, 12px);
  }
  .evcc-external-card-title { font-weight: 600; color: var(--evcc-text-primary); }
  .evcc-external-card-meta { font-size: 0.82rem; color: var(--evcc-text-secondary); margin-top: 2px; }
  .evcc-external-card-actions { display: flex; gap: 8px; flex-shrink: 0; }
  ${SHARED_BTN}
`;

export const externalWizardModalStyles = `
  .evcc-external-wizard-modal { max-width: 560px; width: 92vw; }
  .evcc-external-error {
    background: color-mix(in srgb, var(--evcc-sem-error) 16%, transparent);
    border: 1px solid color-mix(in srgb, var(--evcc-sem-error) 40%, transparent);
    color: var(--evcc-sem-error);
    border-radius: var(--evcc-radius-inner, 8px); padding: 8px 12px; margin-bottom: 12px; font-size: 0.85rem;
  }
  .evcc-ext-count {
    display: flex; align-items: center; flex-wrap: wrap; gap: 10px;
    margin-bottom: 12px; color: var(--evcc-text-primary);
  }
  .evcc-ext-count-label { font-weight: 600; }
  .evcc-ext-stepper { display: inline-flex; align-items: center; gap: 8px; }
  .evcc-ext-step {
    width: 30px; height: 30px; padding: 0; font-size: 1.05rem; line-height: 1;
    display: inline-flex; align-items: center; justify-content: center;
  }
  .evcc-ext-count-n { min-width: 1.4em; text-align: center; font-size: 1.05rem; }
  .evcc-ext-seglist { display: flex; flex-direction: column; gap: 6px; }
  .evcc-ext-seg {
    display: flex; align-items: center; gap: 12px;
    padding: 8px 10px; border-radius: var(--evcc-radius-inner, 8px);
    background: var(--evcc-surface-input);
  }
  .evcc-ext-seg.is-v2 { flex-direction: column; align-items: stretch; gap: 8px; }
  .evcc-ext-seg-row { display: flex; align-items: center; gap: 12px; }
  .evcc-ext-seg-start { font-size: 0.8rem; color: var(--evcc-text-secondary); min-width: 110px; }
  .evcc-ext-seg-facts { font-size: 0.82rem; color: var(--evcc-text-secondary); }
  .evcc-ext-split {
    min-width: 110px; text-align: left;
    border: 1px solid var(--evcc-border-default);
    background: transparent; color: var(--evcc-text-secondary);
    border-radius: var(--evcc-radius-inner, 8px); padding: 5px 9px; font-size: 0.78rem; cursor: pointer;
  }
  .evcc-ext-split.is-split {
    color: var(--evcc-accent);
    border-color: color-mix(in srgb, var(--evcc-accent) 40%, transparent);
  }
  /* v2 action-first controls — the label says what the button DOES. */
  .evcc-ext-merge {
    align-self: flex-start; min-width: 110px; text-align: left;
    border: 1px solid var(--evcc-border-default);
    background: transparent; color: var(--evcc-text-secondary);
    border-radius: var(--evcc-radius-inner, 8px); padding: 5px 9px; font-size: 0.78rem; cursor: pointer;
  }
  .evcc-ext-merge:hover:not([disabled]) {
    color: var(--evcc-accent);
    border-color: color-mix(in srgb, var(--evcc-accent) 40%, transparent);
  }
  .evcc-ext-splits { display: flex; flex-wrap: wrap; gap: 6px; padding-left: 12px; }
  .evcc-ext-split-here {
    border: 1px dashed var(--evcc-border-default);
    background: transparent; color: var(--evcc-text-secondary);
    border-radius: var(--evcc-radius-inner, 8px); padding: 4px 8px; font-size: 0.74rem; cursor: pointer;
  }
  .evcc-ext-split-here:hover:not([disabled]) {
    color: var(--evcc-accent);
    border-color: color-mix(in srgb, var(--evcc-accent) 50%, transparent);
  }
  .evcc-ext-step[disabled], .evcc-ext-merge[disabled], .evcc-ext-split-here[disabled] {
    opacity: 0.5; cursor: default;
  }
  .evcc-ext-room {
    border: 1px solid var(--evcc-border-default);
    border-radius: var(--evcc-radius-card, 12px); padding: 12px 14px; margin-bottom: 12px;
  }
  .evcc-ext-room-head { font-weight: 600; margin-bottom: 8px; color: var(--evcc-text-primary); }
  .evcc-ext-edge .evcc-field-label { color: var(--evcc-accent); }
  .evcc-ext-hint { font-size: 0.72rem; color: var(--evcc-text-secondary); font-weight: 400; }
  .evcc-ext-detected { font-size: 0.78rem; color: var(--evcc-text-secondary); margin-top: 6px; }
  .evcc-ext-allrooms {
    background: var(--evcc-surface-input);
    color: var(--evcc-text-primary);
    border: 1px solid var(--evcc-border-default);
    border-radius: var(--evcc-radius-inner, 8px); padding: 6px 8px; font-size: 0.82rem;
  }
  /* Native option popup ignores the var-based select bg on Windows Chrome and
     renders light text on a white system popup. Pin a solid dark bg + light text
     (concrete fallbacks) so the room list stays readable — mirrors
     .evcc-rooms-animal-select option. */
  .evcc-ext-allrooms option {
    background: var(--evcc-surface-panel, #1c2127);
    color:      var(--evcc-text-primary, #f0f2f5);
  }
  .evcc-ext-blocked { color: var(--evcc-sem-warning); font-size: 0.82rem; margin-bottom: 8px; }
  .evcc-modal-footer-row { display: flex; justify-content: space-between; gap: 8px; }
  ${SHARED_BTN}
`;
