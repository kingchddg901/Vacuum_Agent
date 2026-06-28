/**
 * ============================================================
 * RENDERERS: DIALOG  (confirm / alert / prompt modal)
 * ============================================================
 *
 * The card-native replacement for window.confirm/alert/prompt. Renders into
 * the body-level modal host (main.js _updateModalHost), composed LAST so it
 * stacks above any modal that triggered it (e.g. the run-profile editor).
 *
 * Reuses the shared .evcc-modal* + .evcc-btn* classes already present in the
 * modal host; the dialog-only bits (message, text input) live in
 * styles/dialog.js (dialogModalStyles). All chrome is localized via this.t().
 * Returns "" when no dialog is open.
 * ============================================================
 */

export function applyDialogRenderer(proto) {
  proto.renderDialogModal = function (ctx) {
    const d = ctx.state.pendingDialog?.();
    if (!d) return "";

    const kind = d.kind === "alert" || d.kind === "prompt" ? d.kind : "confirm";

    const titleHtml = d.title
      ? `<div class="evcc-modal-title evcc-dialog-title">${this.escapeHtml(String(d.title))}</div>`
      : "";

    // The message is an authored card string already localized at the call
    // site (this.t(...)); escape again here — the sink is innerHTML.
    const messageHtml = d.message
      ? `<div class="evcc-dialog-message">${this.escapeHtml(String(d.message))}</div>`
      : "";

    const inputHtml = kind === "prompt"
      ? `<input class="evcc-dialog-input" type="text" data-evcc-dialog-input
                value="${this.escapeHtml(String(d.defaultValue ?? ""))}"
                placeholder="${this.escapeHtml(String(d.placeholder ?? ""))}" />`
      : "";

    const confirmLabel = d.confirmLabel
      ? this.escapeHtml(String(d.confirmLabel))
      : kind === "alert"
        ? this.t("common.ok")
        : kind === "prompt"
          ? this.t("common.save")
          : this.t("common.confirm");

    const cancelLabel = d.cancelLabel
      ? this.escapeHtml(String(d.cancelLabel))
      : this.t("common.cancel");

    const confirmClass = d.danger ? "evcc-btn-warn" : "evcc-btn-primary";

    // An alert has only an acknowledge button; confirm/prompt also cancel.
    const cancelBtn = kind === "alert"
      ? ""
      : `<button type="button" class="evcc-btn evcc-btn-ghost" data-action="dialog-cancel">${cancelLabel}</button>`;

    return `
      <div class="evcc-modal-backdrop" data-action="dialog-backdrop">
        <div class="evcc-modal evcc-dialog-modal" data-stop-propagation data-evcc-dialog>
          <div class="evcc-modal-body">
            ${titleHtml}
            ${messageHtml}
            ${inputHtml}
          </div>
          <div class="evcc-modal-footer">
            <div class="evcc-modal-footer-row evcc-dialog-actions">
              ${cancelBtn}
              <button type="button" class="evcc-btn ${confirmClass}" data-action="dialog-confirm">${confirmLabel}</button>
            </div>
          </div>
        </div>
      </div>
    `;
  };
}
