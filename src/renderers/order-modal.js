/**
 * ============================================================
 * RENDERERS: SHARED ORDER MODAL
 * ============================================================
 *
 * Position-selector modal for any ordered list. Used as the
 * canonical reorder UX on mobile and the fallback where drag
 * is awkward or disabled.
 *
 * ============================================================
 */

/**
 * Mix order modal renderer methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applyOrderModalRenderer(proto) {

  /**
   * Render the position-selector modal for an in-flight reorder operation.
   * Returns an empty string when no reorder is active.
   *
   * @param {{ state: object }} ctx - Render context.
   * @returns {string} HTML string.
   */
  proto.renderOrderSelectorModal = function (ctx) {
    const { state } = ctx;

    if (!state.isOrderSelectorOpen()) return "";

    const scope = state.orderSelectorScope();
    const item = state.orderSelectorItem();
    const position = state.orderSelectorTargetPosition();
    const positions = state.orderSelectorPositions();
    const adapter = state.getOrderAdapter(scope);

    if (!item || !adapter) return "";

    const label = adapter.getLabel(item);

    return `
      <div class="evcc-modal-backdrop" data-action="close-order-selector">
        <div class="evcc-modal" data-stop-propagation>

          <div class="evcc-modal-header">
            <div class="evcc-modal-title">Move ${this.escapeHtml(label)}</div>
            <button
              type="button"
              class="evcc-chip evcc-chip--icon"
              data-action="close-order-selector"
              title="Close"
            >✕</button>
          </div>

          <div class="evcc-modal-body">
            <div class="evcc-editor-field-group">
              <div class="evcc-field-label">Position</div>
              <div class="evcc-chips">
                ${positions.map((value) => `
                  <button
                    type="button"
                    class="evcc-chip ${Number(position) === Number(value) ? "active" : ""}"
                    data-action="set-order-position"
                    data-position="${value}"
                  >${value}</button>
                `).join("")}
              </div>
            </div>
          </div>

          <div class="evcc-modal-footer">
            <button
              type="button"
              class="evcc-chip"
              data-action="close-order-selector"
            >Cancel</button>

            <button
              type="button"
              class="evcc-chip evcc-chip--save"
              data-action="confirm-order-selector"
            >Save</button>
          </div>

        </div>
      </div>
    `;
  };
}