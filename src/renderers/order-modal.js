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
    const activeId = String(adapter.getId(item));

    // Layer 1: current order. Shows the room list as it is right now,
    // so the user sees the lay of the land before picking a target
    // position. The active room is highlighted.
    const currentItems = state.getOrderedItemsForScope?.(scope) ?? [];

    // Layer 2: preview after move. Pulled via the existing preview
    // helper so we don't duplicate ordering logic. Same item count,
    // just the active item relocated to the selected position. Only
    // rendered when the user has selected a position different from
    // the room's current one — otherwise it's redundant noise.
    const currentPosition = state.getOrderedItemPosition?.(scope, activeId);
    const showPreview = position != null
      && Number(position) !== Number(currentPosition);
    const previewItems = showPreview
      ? (state.previewMovedItemsForScope?.(scope, activeId, position) ?? [])
      : [];

    const renderChipRow = (items) => items.map((it, idx) => {
      const id = String(adapter.getId(it));
      const isActive = id === activeId;
      const itemLabel = adapter.getLabel(it);
      return `
        <span class="evcc-order-preview-chip ${isActive ? "evcc-order-preview-chip--active" : ""}">
          <span class="evcc-order-preview-chip-pos">${idx + 1}</span>
          ${this.escapeHtml(itemLabel)}
        </span>
      `;
    }).join("");

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
              <div class="evcc-field-label">Currently</div>
              <div class="evcc-order-preview-row">
                ${renderChipRow(currentItems)}
              </div>
            </div>

            ${showPreview ? `
              <div class="evcc-editor-field-group">
                <div class="evcc-field-label">After move</div>
                <div class="evcc-order-preview-row">
                  ${renderChipRow(previewItems)}
                </div>
              </div>
            ` : ""}

            <div class="evcc-editor-field-group">
              <div class="evcc-field-label">Move to position</div>
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
              ${showPreview ? "" : "disabled"}
            >Save</button>
          </div>

        </div>
      </div>
    `;
  };
}