// Card-local toast queue. Lightweight feedback for service results
// (save / reset / dock action) so the user knows their click landed.
//
// State shape: { items: [{ id, message, kind, expiresAt }] }
//
// `kind` is one of: "success" (default), "error", "info"
// `expiresAt` is a Date.now() ms timestamp; toasts are filtered out
// once now > expiresAt at render time, and a scheduled re-render
// removes them from the DOM.

let _toastIdCounter = 0;

export function applyToastsState(proto) {
  proto._ensureToastsState = function () {
    if (!this._toastsState) {
      this._toastsState = { items: [] };
    }
    return this._toastsState;
  };

  /**
   * Push a toast onto the queue. Returns the toast id.
   *
   * @param {string} message - Display text.
   * @param {object} [opts]
   * @param {"success"|"error"|"info"} [opts.kind] - Default "success".
   * @param {number} [opts.ttl] - Lifetime in ms. Default 3500.
   */
  proto.pushToast = function (message, opts = {}) {
    const state = this._ensureToastsState();
    const id = `toast-${++_toastIdCounter}`;
    const kind = ["success", "error", "info"].includes(opts.kind) ? opts.kind : "success";
    const ttl = Number.isFinite(opts.ttl) ? Math.max(1000, opts.ttl) : 3500;
    state.items.push({
      id,
      message: String(message ?? ""),
      kind,
      expiresAt: Date.now() + ttl,
    });
    return id;
  };

  /**
   * Drop a toast by id (used by the dismiss button binding).
   */
  proto.dismissToast = function (id) {
    const state = this._ensureToastsState();
    state.items = state.items.filter((t) => t.id !== id);
  };

  /**
   * Active toasts whose expiresAt has not passed. Renderer reads
   * this each tick; expired entries get filtered out implicitly.
   */
  proto.activeToasts = function () {
    const state = this._ensureToastsState();
    const now = Date.now();
    const live = state.items.filter((t) => t.expiresAt > now);
    if (live.length !== state.items.length) {
      state.items = live;
    }
    return live;
  };
}
