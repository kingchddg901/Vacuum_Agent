/**
 * ============================================================
 * BINDINGS: SHARED ORDER SYSTEM
 * ============================================================
 *
 * Shared event delegation for generic ordering interactions —
 * mobile position selector, desktop drag-and-drop, FLIP
 * animation, and moved-item highlight feedback.
 *
 * Drag interactions must NOT trigger a full card re-render
 * during dragstart/dragover — replacing the DOM mid-drag
 * collapses the browser drag session.
 *
 * ============================================================
 */

/**
 * Mix shared order system binding methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardBindings prototype to extend.
 */
export function applyOrderBindings(proto) {

  /* =========================================================
     INTERNAL HELPERS
     ========================================================= */

  proto._orderRoot = function () {
    return this.card?.shadowRoot ?? null;
  };

  /**
   * Snapshot current `getBoundingClientRect` positions for all drop targets in a scope.
   * Used as the FLIP "before" state immediately before a mutation.
   *
   * @param {string} scope - Order scope identifier (e.g. "rooms", "queue").
   * @returns {Map<string, {left:number, top:number}>} Map of item ID → position.
   */
  proto._captureOrderedRects = function (scope) {
    const root = this._orderRoot();
    if (!root) return new Map();

    const elements = root.querySelectorAll(
      `[data-order-drop-target][data-scope="${scope}"]`
    );

    const rects = new Map();

    elements.forEach((el) => {
      const itemId = el.dataset.itemId;
      if (!itemId) return;

      rects.set(String(itemId), {
        left: el.getBoundingClientRect().left,
        top: el.getBoundingClientRect().top,
      });
    });

    return rects;
  };

  /**
   * Briefly add `.evcc-order-feedback` to the moved item for a CSS highlight pulse.
   *
   * @param {string} scope - Order scope identifier.
   * @param {string|number} movedItemId - ID of the item that was moved.
   */
  proto._applyOrderFeedback = function (scope, movedItemId) {
    const root = this._orderRoot();
    if (!root || movedItemId == null) return;

    const selector =
      `[data-order-drop-target][data-scope="${scope}"][data-item-id="${String(movedItemId)}"]`;

    const movedEl = root.querySelector(selector);
    if (!movedEl) return;

    movedEl.classList.remove("evcc-order-feedback");
    void movedEl.offsetWidth;
    movedEl.classList.add("evcc-order-feedback");

    window.setTimeout(() => {
      movedEl.classList.remove("evcc-order-feedback");
    }, 900);
  };

  /**
   * Animate all reordered items from their pre-mutation positions back to their
   * current positions (FLIP technique — "First Last Invert Play").
   *
   * @param {string} scope - Order scope identifier.
   * @param {Map<string, {left:number, top:number}>} beforeRects - Pre-mutation positions.
   */
  proto._playOrderFlip = function (scope, beforeRects) {
    const root = this._orderRoot();
    if (!root || !beforeRects?.size) return;

    const elements = root.querySelectorAll(
      `[data-order-drop-target][data-scope="${scope}"]`
    );

    elements.forEach((el) => {
      const itemId = String(el.dataset.itemId ?? "");
      if (!itemId || !beforeRects.has(itemId)) return;

      const first = beforeRects.get(itemId);
      const lastRect = el.getBoundingClientRect();

      const deltaX = first.left - lastRect.left;
      const deltaY = first.top - lastRect.top;

      if (Math.abs(deltaX) < 1 && Math.abs(deltaY) < 1) return;

      el.animate(
        [
          { transform: `translate(${deltaX}px, ${deltaY}px)` },
          { transform: "translate(0px, 0px)" },
        ],
        {
          duration: 240,
          easing: "cubic-bezier(0.22, 1, 0.36, 1)",
        }
      );
    });
  };

  /**
   * Run an order mutation, then schedule a re-render and play the FLIP animation.
   *
   * @param {string} scope - Order scope identifier.
   * @param {string|number} movedItemId - ID of the item being moved (for highlight feedback).
   * @param {() => Promise<*>} mutate - Async mutation callback; skip animation if falsy result.
   */
  proto._runOrderMutationWithFlip = async function (scope, movedItemId, mutate) {
    const beforeRects = this._captureOrderedRects(scope);

    const result = await mutate();
    if (!result) return;

    this.card._scheduleRender();

    await new Promise((resolve) => requestAnimationFrame(resolve));
    await new Promise((resolve) => requestAnimationFrame(resolve));

    this._playOrderFlip(scope, beforeRects);
    this._applyOrderFeedback(scope, movedItemId);
  };

  /**
   * Confirm the mobile position selector choice and animate the reorder.
   */
  proto.confirmOrderSelectorWithFlip = async function () {
    const scope = this.card._state.orderSelectorScope();
    const movedItemId = this.card._state.orderSelectorItemId();

    await this._runOrderMutationWithFlip(scope, movedItemId, async () => {
      return await this.card._actions.confirmOrderedPositionChange();
    });
  };

  /**
   * Confirm a drag-and-drop reorder and animate the result.
   *
   * @param {string} scope - Order scope identifier.
   * @param {string|number} targetId - Drop target item ID.
   */
  proto.confirmDraggedOrderWithFlip = async function (scope, targetId) {
    const movedItemId = this.card._state.orderDragItemId();

    await this._runOrderMutationWithFlip(scope, movedItemId, async () => {
      return await this.card._actions.confirmDraggedOrderChange(scope, targetId);
    });
  };

  /** Remove drag source/target CSS classes from all order elements. */
  proto._clearDragVisualState = function () {
    const root = this._orderRoot();
    if (!root) return;

    root.querySelectorAll(".evcc-order-drag-source").forEach((el) => {
      el.classList.remove("evcc-order-drag-source");
    });

    root.querySelectorAll(".evcc-order-drag-target").forEach((el) => {
      el.classList.remove("evcc-order-drag-target");
    });
  };

  /**
   * Highlight the drag source and drop target items during a drag session.
   *
   * @param {string} scope - Order scope identifier.
   * @param {string|number} sourceId - Item being dragged.
   * @param {string|number} targetId - Current drop target item.
   */
  proto._applyDragVisualState = function (scope, sourceId, targetId) {
    const root = this._orderRoot();
    if (!root) return;

    this._clearDragVisualState();

    if (sourceId != null) {
      const sourceEl = root.querySelector(
        `[data-order-drop-target][data-scope="${scope}"][data-item-id="${String(sourceId)}"]`
      );
      if (sourceEl) sourceEl.classList.add("evcc-order-drag-source");
    }

    if (targetId != null) {
      const targetEl = root.querySelector(
        `[data-order-drop-target][data-scope="${scope}"][data-item-id="${String(targetId)}"]`
      );
      if (targetEl) targetEl.classList.add("evcc-order-drag-target");
    }
  };

  /* =========================================================
     ROOT EVENT BINDING
     ========================================================= */

  proto.bindOrderEvents = function (root) {
    if (!root) return;

    root.addEventListener("click", (event) => {
      const target = event.target.closest("[data-action]");
      if (!target) return;

      const action = target.dataset.action;

      if (action === "open-order-selector") {
        event.preventDefault();
        event.stopPropagation();
        this.card._state.openOrderSelector(
          target.dataset.scope,
          target.dataset.itemId
        );
        this.card._scheduleRender();
      }

      if (action === "close-order-selector") {
        event.preventDefault();
        this.card._state.closeOrderSelector();
        this.card._scheduleRender();
      }

      if (action === "set-order-position") {
        event.preventDefault();
        this.card._state.setOrderSelectorTargetPosition(
          target.dataset.position
        );
        this.card._scheduleRender();
      }

      if (action === "confirm-order-selector") {
        event.preventDefault();
        this.confirmOrderSelectorWithFlip();
      }
    });

    root.addEventListener("dragstart", (event) => {
      const target = event.target.closest("[data-order-drag-item]");
      if (!target) return;

      const scope = target.dataset.scope;
      const itemId = target.dataset.itemId;
      if (!scope || itemId == null) return;

      this.card._state.beginOrderDrag(scope, itemId);

      try {
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", String(itemId));
      } catch (_error) {
        // Browser differences are tolerated.
      }

      this._applyDragVisualState(scope, itemId, itemId);
    });

    root.addEventListener("dragover", (event) => {
      const target = event.target.closest("[data-order-drop-target]");
      if (!target) return;

      event.preventDefault();

      const scope = target.dataset.scope;
      const itemId = target.dataset.itemId;
      if (!scope || itemId == null) return;

      this.card._state.setOrderDragOverItem(itemId);
      this._applyDragVisualState(
        scope,
        this.card._state.orderDragItemId(),
        itemId
      );
    });

    root.addEventListener("drop", (event) => {
      const target = event.target.closest("[data-order-drop-target]");
      if (!target) return;

      event.preventDefault();

      const scope = target.dataset.scope;
      const targetId = target.dataset.itemId;

      this._clearDragVisualState();
      this.confirmDraggedOrderWithFlip(scope, targetId);
    });

    root.addEventListener("dragend", () => {
      this.card._state.clearOrderDrag();
      this._clearDragVisualState();
    });
  };
}
