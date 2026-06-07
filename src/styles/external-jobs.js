/**
 * ============================================================
 * STYLES: EXTERNAL JOBS
 * ============================================================
 *
 * Two exports because the feature spans two style targets:
 *   - externalJobsStyles      -> the card shadow root (subtab strip + list)
 *   - externalWizardModalStyles -> the body-level modal host (the wizard)
 *
 * The wizard reuses the shared modal + chip/field classes already present in
 * the modal host; these add only the External-specific pieces.
 * ============================================================
 */

const SHARED_BTN = `
  .evcc-btn {
    border: 1px solid var(--evcc-border, rgba(255, 255, 255, 0.14));
    background: var(--evcc-surface-2, rgba(255, 255, 255, 0.06));
    color: var(--evcc-text, #e8eef4);
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 0.86rem;
    cursor: pointer;
  }
  .evcc-btn:hover { background: var(--evcc-surface-3, rgba(255, 255, 255, 0.12)); }
  .evcc-btn[disabled] { opacity: 0.5; cursor: default; }
  .evcc-btn-primary {
    background: var(--evcc-accent, #3b82f6);
    border-color: var(--evcc-accent, #3b82f6);
    color: var(--evcc-on-accent, #fff);
  }
  .evcc-btn-warn {
    background: var(--evcc-warn, #b45309);
    border-color: var(--evcc-warn, #b45309);
    color: #fff;
  }
  .evcc-btn-ghost { background: transparent; }
`;

export const externalJobsStyles = `
  .evcc-review-subtabs { display: flex; gap: 8px; margin-bottom: 14px; }
  .evcc-review-subtab {
    border: 1px solid var(--evcc-border, rgba(255, 255, 255, 0.14));
    background: transparent;
    color: var(--evcc-text-dim, #9fb0c0);
    border-radius: 999px;
    padding: 6px 16px;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .evcc-review-subtab.is-active {
    background: var(--evcc-accent, #3b82f6);
    border-color: var(--evcc-accent, #3b82f6);
    color: var(--evcc-on-accent, #fff);
  }
  .evcc-external-empty { padding: 24px; text-align: center; color: var(--evcc-text-dim, #9fb0c0); }
  .evcc-external-list { display: flex; flex-direction: column; gap: 10px; }
  .evcc-external-card {
    display: flex; justify-content: space-between; align-items: center; gap: 12px;
    padding: 14px 16px;
    background: var(--evcc-surface-1, rgba(255, 255, 255, 0.04));
    border: 1px solid var(--evcc-border, rgba(255, 255, 255, 0.1));
    border-radius: 14px;
  }
  .evcc-external-card-title { font-weight: 600; color: var(--evcc-text, #e8eef4); }
  .evcc-external-card-meta { font-size: 0.82rem; color: var(--evcc-text-dim, #9fb0c0); margin-top: 2px; }
  .evcc-external-card-actions { display: flex; gap: 8px; flex-shrink: 0; }
  ${SHARED_BTN}
`;

export const externalWizardModalStyles = `
  .evcc-external-wizard-modal { max-width: 560px; width: 92vw; }
  .evcc-external-error {
    background: rgba(180, 60, 60, 0.16);
    border: 1px solid rgba(220, 90, 90, 0.4);
    color: #f3c0c0; border-radius: 10px; padding: 8px 12px; margin-bottom: 12px; font-size: 0.85rem;
  }
  .evcc-ext-count { margin-bottom: 12px; color: var(--evcc-text, #e8eef4); }
  .evcc-ext-seglist { display: flex; flex-direction: column; gap: 6px; }
  .evcc-ext-seg {
    display: flex; align-items: center; gap: 12px;
    padding: 8px 10px; border-radius: 10px;
    background: var(--evcc-surface-1, rgba(255, 255, 255, 0.04));
  }
  .evcc-ext-seg-start { font-size: 0.8rem; color: var(--evcc-text-dim, #9fb0c0); min-width: 110px; }
  .evcc-ext-seg-facts { font-size: 0.82rem; color: var(--evcc-text-dim, #9fb0c0); }
  .evcc-ext-split {
    min-width: 110px; text-align: left;
    border: 1px solid var(--evcc-border, rgba(255, 255, 255, 0.14));
    background: transparent; color: var(--evcc-text-dim, #9fb0c0);
    border-radius: 8px; padding: 5px 9px; font-size: 0.78rem; cursor: pointer;
  }
  .evcc-ext-split.is-split { color: var(--evcc-accent, #3b82f6); border-color: var(--evcc-accent, #3b82f6); }
  .evcc-ext-room {
    border: 1px solid var(--evcc-border, rgba(255, 255, 255, 0.1));
    border-radius: 14px; padding: 12px 14px; margin-bottom: 12px;
  }
  .evcc-ext-room-head { font-weight: 600; margin-bottom: 8px; color: var(--evcc-text, #e8eef4); }
  .evcc-ext-edge .evcc-field-label { color: var(--evcc-accent, #3b82f6); }
  .evcc-ext-hint { font-size: 0.72rem; color: var(--evcc-text-dim, #9fb0c0); font-weight: 400; }
  .evcc-ext-detected { font-size: 0.78rem; color: var(--evcc-text-dim, #9fb0c0); margin-top: 6px; }
  .evcc-ext-allrooms {
    background: var(--evcc-surface-2, rgba(255, 255, 255, 0.06));
    color: var(--evcc-text, #e8eef4);
    border: 1px solid var(--evcc-border, rgba(255, 255, 255, 0.14));
    border-radius: 8px; padding: 6px 8px; font-size: 0.82rem;
  }
  .evcc-ext-blocked { color: #f0b46a; font-size: 0.82rem; margin-bottom: 8px; }
  .evcc-modal-footer-row { display: flex; justify-content: space-between; gap: 8px; }
  ${SHARED_BTN}
`;
