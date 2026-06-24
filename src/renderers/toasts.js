/**
 * ============================================================
 * RENDERERS: TOASTS
 * ============================================================
 *
 * Tiny stack of transient feedback pills surfaced on the card
 * — "Maintenance reset saved", "Interval saved", etc.
 *
 * The active list comes from state.activeToasts(); expired
 * entries are filtered out by the state module on read, so the
 * renderer never has to think about TTL.
 *
 * ============================================================
 */

export function applyToastsRenderer(proto) {

  /**
   * Render the toast stack. Returns empty string when no toasts
   * are active so the DOM stays empty.
   *
   * @param {object} ctx - Render context containing `state`.
   * @returns {string} HTML string.
   */
  proto.renderToasts = function (ctx) {
    const toasts = ctx?.state?.activeToasts?.() ?? [];
    if (!toasts.length) return "";

    return `
      <div class="evcc-toast-stack">
        ${toasts.map((t) => `
          <div
            class="evcc-toast evcc-toast--${this.escapeHtml(t.kind)}"
            data-toast-id="${this.escapeHtml(t.id)}"
            role="status"
          >
            <span class="evcc-toast-message">${this.escapeHtml(t.message)}</span>
            <button
              type="button"
              class="evcc-toast-dismiss"
              data-action="dismiss-toast"
              data-toast-id="${this.escapeHtml(t.id)}"
              aria-label="${this.t("toast.dismiss")}"
            >x</button>
          </div>
        `).join("")}
      </div>
    `;
  };
}
