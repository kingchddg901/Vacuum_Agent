/**
 * ============================================================
 * STYLES: DIALOG MODAL  (confirm / alert / prompt)
 * ============================================================
 *
 * Interpolated into MODAL_HOST_STYLES (styles/index.js) — the dialog renders
 * in the body-level modal host. Only the dialog-specific bits live here; the
 * shell, footer, and buttons reuse the shared .evcc-modal* / .evcc-btn*
 * classes already present in the modal host (from externalWizardModalStyles).
 * ============================================================
 */

export const dialogModalStyles = `
  .evcc-dialog-modal {
    max-width: 420px;
    width: calc(100vw - 32px);
  }

  .evcc-dialog-title {
    margin-bottom: 8px;
  }

  .evcc-dialog-message {
    color: var(--evcc-modal-text-primary, #f0f2f5);
    font-size: 0.95rem;
    line-height: 1.45;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .evcc-dialog-input {
    width: 100%;
    margin-top: 12px;
    padding: 9px 11px;
    border-radius: 8px;
    background: var(--evcc-modal-input-bg, rgba(255, 255, 255, 0.06));
    border: 1px solid var(--evcc-modal-border-strong, rgba(255, 255, 255, 0.18));
    color: var(--evcc-modal-text-primary, #f0f2f5);
    font: inherit;
  }

  .evcc-dialog-input:focus {
    outline: none;
    border-color: var(--evcc-modal-accent, #3b82f6);
  }

  /* One or two buttons, always trailing-aligned (alert has only confirm). */
  .evcc-dialog-actions {
    justify-content: flex-end;
    gap: 8px;
  }
`;
