// Item-agnostic ordering engine: sort, move, drag, and position-selector state.
// Feature adapters supply getItems/getId/getOrder/setOrder/persist — this module owns none of that.

export function applyOrderState(proto) {

  /* =========================================================
     SHARED MODAL / DRAG STATE
     ========================================================= */

  proto._ensureOrderState = function () {
    if (!this._orderState) {
      this._orderState = {
        scope: null,
        activeItemId: null,
        targetPosition: null,
        dragItemId: null,
        dragOverItemId: null,
      };
    }

    return this._orderState;
  };

  proto.resetOrderState = function () {
    this._orderState = {
      scope: null,
      activeItemId: null,
      targetPosition: null,
      dragItemId: null,
      dragOverItemId: null,
    };
  };

  /* =========================================================
     GENERIC ORDER HELPERS
     ========================================================= */

  proto._normalizeNumericOrder = function (value, fallback = 999999) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  };

  proto._sortOrderedItems = function (items, adapter) {
    const safeItems = Array.isArray(items) ? [...items] : [];
    const getOrder = adapter.getOrder;
    const getId = adapter.getId;

    return safeItems.sort((a, b) => {
      const orderA = this._normalizeNumericOrder(getOrder(a));
      const orderB = this._normalizeNumericOrder(getOrder(b));

      if (orderA !== orderB) return orderA - orderB;

      const idA = String(getId(a));
      const idB = String(getId(b));
      return idA.localeCompare(idB);
    });
  };

  proto._reindexOrderedItems = function (items, adapter) {
    const setOrder = adapter.setOrder;
    return items.map((item, index) => setOrder(item, index + 1));
  };

  proto._moveOrderedItemToPosition = function (items, adapter, itemId, targetPosition) {
    const ordered = this._reindexOrderedItems(
      this._sortOrderedItems(items, adapter),
      adapter
    );

    const getId = adapter.getId;
    const numericTarget = Math.max(
      1,
      Math.min(Number(targetPosition) || 1, ordered.length)
    );

    const sourceIndex = ordered.findIndex(
      (item) => String(getId(item)) === String(itemId)
    );

    if (sourceIndex === -1) return ordered;

    const next = [...ordered];
    const [moved] = next.splice(sourceIndex, 1);
    next.splice(numericTarget - 1, 0, moved);

    return this._reindexOrderedItems(next, adapter);
  };

  proto._swapOrderedItemsById = function (items, adapter, sourceId, targetId) {
    const ordered = this._reindexOrderedItems(
      this._sortOrderedItems(items, adapter),
      adapter
    );

    const getId = adapter.getId;

    const sourceIndex = ordered.findIndex(
      (item) => String(getId(item)) === String(sourceId)
    );
    const targetIndex = ordered.findIndex(
      (item) => String(getId(item)) === String(targetId)
    );

    if (sourceIndex === -1 || targetIndex === -1 || sourceIndex === targetIndex) {
      return ordered;
    }

    const next = [...ordered];
    const [moved] = next.splice(sourceIndex, 1);
    next.splice(targetIndex, 0, moved);

    return this._reindexOrderedItems(next, adapter);
  };

  proto._buildOrderPatch = function (items, adapter) {
    const getId = adapter.getId;
    const getOrder = adapter.getOrder;

    return items.map((item) => ({
      id: getId(item),
      order: this._normalizeNumericOrder(getOrder(item), 1),
    }));
  };

  /* =========================================================
     SHARED ADAPTER RESOLUTION
     ========================================================= */

  proto.getOrderAdapter = function (_scope) {
    return null;
  };

  proto.getOrderedItemsForScope = function (scope) {
    const adapter = this.getOrderAdapter(scope);
    if (!adapter?.getItems) return [];

    const items = adapter.getItems.call(this);
    return this._reindexOrderedItems(
      this._sortOrderedItems(items, adapter),
      adapter
    );
  };

  proto.getOrderedItemById = function (scope, itemId) {
    const items = this.getOrderedItemsForScope(scope);
    const adapter = this.getOrderAdapter(scope);
    if (!adapter) return null;

    return items.find(
      (item) => String(adapter.getId(item)) === String(itemId)
    ) ?? null;
  };

  proto.getOrderedItemPosition = function (scope, itemId) {
    const items = this.getOrderedItemsForScope(scope);
    const adapter = this.getOrderAdapter(scope);
    if (!adapter) return null;

    const index = items.findIndex(
      (item) => String(adapter.getId(item)) === String(itemId)
    );

    return index === -1 ? null : index + 1;
  };

  /* =========================================================
     REORDER MODAL STATE
     ========================================================= */

  proto.openOrderSelector = function (scope, itemId) {
    const state = this._ensureOrderState();
    const position = this.getOrderedItemPosition(scope, itemId);

    state.scope = scope;
    state.activeItemId = itemId;
    state.targetPosition = position;
  };

  proto.closeOrderSelector = function () {
    const state = this._ensureOrderState();
    state.scope = null;
    state.activeItemId = null;
    state.targetPosition = null;
  };

  proto.isOrderSelectorOpen = function () {
    const state = this._ensureOrderState();
    return !!(state.scope && state.activeItemId != null);
  };

  proto.orderSelectorScope = function () {
    return this._ensureOrderState().scope;
  };

  proto.orderSelectorItemId = function () {
    return this._ensureOrderState().activeItemId;
  };

  proto.orderSelectorItem = function () {
    const state = this._ensureOrderState();
    if (!state.scope || state.activeItemId == null) return null;

    return this.getOrderedItemById(state.scope, state.activeItemId);
  };

  proto.orderSelectorTargetPosition = function () {
    return this._ensureOrderState().targetPosition;
  };

  proto.setOrderSelectorTargetPosition = function (position) {
    const state = this._ensureOrderState();
    state.targetPosition = Number(position) || 1;
  };

  proto.orderSelectorPositions = function () {
    const state = this._ensureOrderState();
    if (!state.scope) return [];

    const items = this.getOrderedItemsForScope(state.scope);
    return Array.from({ length: items.length }, (_, index) => index + 1);
  };

  /* =========================================================
     DRAG STATE
     ========================================================= */

  proto.beginOrderDrag = function (scope, itemId) {
    const state = this._ensureOrderState();
    state.scope = scope;
    state.dragItemId = itemId;
    state.dragOverItemId = itemId;
  };

  proto.setOrderDragOverItem = function (itemId) {
    const state = this._ensureOrderState();
    state.dragOverItemId = itemId;
  };

  proto.orderDragItemId = function () {
    return this._ensureOrderState().dragItemId;
  };

  proto.orderDragOverItemId = function () {
    return this._ensureOrderState().dragOverItemId;
  };

  proto.clearOrderDrag = function () {
    const state = this._ensureOrderState();
    state.dragItemId = null;
    state.dragOverItemId = null;
  };

  /* =========================================================
     ORDER COMPUTATION
     ========================================================= */

  proto.previewMovedItemsForScope = function (scope, itemId, targetPosition) {
    const adapter = this.getOrderAdapter(scope);
    if (!adapter) return [];

    const items = adapter.getItems.call(this);
    return this._moveOrderedItemToPosition(items, adapter, itemId, targetPosition);
  };

  proto.previewDraggedItemsForScope = function (scope, sourceId, targetId) {
    const adapter = this.getOrderAdapter(scope);
    if (!adapter) return [];

    const items = adapter.getItems.call(this);
    return this._swapOrderedItemsById(items, adapter, sourceId, targetId);
  };
}