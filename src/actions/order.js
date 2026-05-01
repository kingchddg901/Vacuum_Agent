// Shared action layer for persisting reordered items via the order adapter pattern.
// RULES: persistence + state cleanup only; FLIP animation and visual feedback live in bindings.

export function applyOrderActions(proto) {

  /**
   * Persist a selector-based move-to-position reorder.
   * @returns {object|null} reorder metadata for binding-side animation, or null if aborted
   */
  proto.confirmOrderedPositionChange = async function () {
    const scope = this.state.orderSelectorScope();
    const itemId = this.state.orderSelectorItemId();
    const targetPosition = this.state.orderSelectorTargetPosition();
    const adapter = this.state.getOrderAdapter(scope);

    if (!adapter || itemId == null || targetPosition == null) return null;

    const nextItems = this.state.previewMovedItemsForScope(
      scope,
      itemId,
      targetPosition
    );

    const meta = {
      scope,
      mode: "selector",
      itemId,
      targetPosition,
      patch: this.state._buildOrderPatch(nextItems, adapter),
    };

    await adapter.persist.call(
      {
        _actions: this,
        state: this.state,
        hass: this.hass,
      },
      nextItems,
      meta
    );

    this.state.closeOrderSelector();

    return {
      scope,
      movedItemId: itemId,
      mode: "selector",
    };
  };

  /**
   * Persist a drag-drop reorder.
   * @param {string} scope - order adapter scope (e.g. "rooms")
   * @param {*} targetId - item ID of the drop target
   * @returns {object|null} reorder metadata for binding-side animation, or null if aborted
   */
  proto.confirmDraggedOrderChange = async function (scope, targetId) {
    const adapter = this.state.getOrderAdapter(scope);
    const sourceId = this.state.orderDragItemId();

    if (!adapter || sourceId == null || targetId == null) {
      this.state.clearOrderDrag();
      return null;
    }

    const nextItems = this.state.previewDraggedItemsForScope(
      scope,
      sourceId,
      targetId
    );

    const meta = {
      scope,
      mode: "drag",
      sourceId,
      targetId,
      patch: this.state._buildOrderPatch(nextItems, adapter),
    };

    await adapter.persist.call(
      {
        _actions: this,
        state: this.state,
        hass: this.hass,
      },
      nextItems,
      meta
    );

    this.state.clearOrderDrag();

    return {
      scope,
      movedItemId: sourceId,
      mode: "drag",
    };
  };
}