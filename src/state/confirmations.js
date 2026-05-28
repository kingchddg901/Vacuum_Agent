// Generic transient-confirmation registry.
//
// Owns the "did the user click once or twice?" state for destructive
// UI actions — Cancel Run, Clear Queue, per-variant image delete, etc.
// Built in:
//
//   - grace window — a rapid second click is swallowed for N ms after
//     the first, so a panicked double-tap doesn't fire the destructive
//     branch before the user sees the label flip.
//   - auto-clear   — a forgotten arm times out on its own. setView()
//     also bulk-clears every arm on nav so confirmations don't survive
//     view changes.
//   - bulk clear   — disarmAllConfirmations() drops every entry in one
//     call; main.js wires this into setView() so we no longer maintain
//     a manual list of clearX() calls that has to grow every time a
//     new confirmation is added.
//
// Keys are caller-defined strings. Convention: "<view>.<slot>" or
// "<view>.<slot>.<param>" for parameterised confirms (one per variant,
// one per item, etc.). Example keys:
//
//   "rooms.cancel-run"
//   "rooms.clear-queue"
//   "map-config.delete-variant.dark"
//
// Replaces the prior pattern of one flat boolean + one timer + four
// shim methods per confirmation scattered across state slices and
// card-instance fields. The shim accessors that used to back each
// confirmation still exist (state/rooms.js, state/map.js) and now
// delegate here; no renderer or binding callsite had to change.

const DEFAULT_TTL = 5000;
const DEFAULT_GRACE = 700;

export function applyConfirmationsState(proto) {

  proto._ensureConfirmationsState = function () {
    if (!this._confirmations) {
      this._confirmations = {
        entries: new Map(),    // key -> { armedAt, ttl, grace, timerId }
        renderTrigger: null,
      };
    }
    return this._confirmations;
  };

  /**
   * main.js wires this once so the registry can re-render the card
   * when an auto-clear timer fires. Without it, expired confirmations
   * stay visually pulsing until something else triggers a render.
   *
   * @param {() => void} fn
   */
  proto.setConfirmationsRenderTrigger = function (fn) {
    this._ensureConfirmationsState().renderTrigger =
      typeof fn === "function" ? fn : null;
  };

  /**
   * Arm a confirmation under `key`. Replaces any existing entry for
   * the same key (and cancels its auto-clear timer).
   *
   * @param {string} key
   * @param {object} [opts]
   * @param {number} [opts.ttl]   Auto-clear timeout in ms. 0 disables
   *                              auto-clear (caller is responsible for
   *                              eventually calling disarmConfirmation
   *                              or relying on the setView bulk clear).
   *                              Default 5000.
   * @param {number} [opts.grace] Double-tap guard window in ms.
   *                              Default 700.
   */
  proto.armConfirmation = function (key, opts = {}) {
    if (!key) return;
    const state = this._ensureConfirmationsState();
    const ttl = Number.isFinite(opts.ttl) ? Math.max(0, opts.ttl) : DEFAULT_TTL;
    const grace = Number.isFinite(opts.grace) ? Math.max(0, opts.grace) : DEFAULT_GRACE;

    const existing = state.entries.get(key);
    if (existing?.timerId) clearTimeout(existing.timerId);

    let timerId = null;
    if (ttl > 0) {
      timerId = setTimeout(() => {
        // Guard against the entry being replaced before the timer fired.
        const entry = state.entries.get(key);
        if (!entry || entry.timerId !== timerId) return;
        state.entries.delete(key);
        state.renderTrigger?.();
      }, ttl);
    }

    state.entries.set(key, { armedAt: Date.now(), ttl, grace, timerId });
  };

  proto.disarmConfirmation = function (key) {
    if (!key) return;
    const state = this._ensureConfirmationsState();
    const entry = state.entries.get(key);
    if (!entry) return;
    if (entry.timerId) clearTimeout(entry.timerId);
    state.entries.delete(key);
  };

  /**
   * Drop every armed confirmation. setView() calls this on every nav.
   */
  proto.disarmAllConfirmations = function () {
    const state = this._ensureConfirmationsState();
    for (const entry of state.entries.values()) {
      if (entry.timerId) clearTimeout(entry.timerId);
    }
    state.entries.clear();
  };

  /**
   * Drop every armed confirmation whose key starts with `prefix`.
   * Useful for parameterised slots (e.g. variant delete) where the
   * "only one armed at a time" invariant is enforced by clearing
   * sibling keys before arming a new one.
   *
   * @param {string} prefix
   */
  proto.disarmConfirmationsWithPrefix = function (prefix) {
    if (!prefix) return;
    const state = this._ensureConfirmationsState();
    for (const key of [...state.entries.keys()]) {
      if (key.startsWith(prefix)) {
        const entry = state.entries.get(key);
        if (entry?.timerId) clearTimeout(entry.timerId);
        state.entries.delete(key);
      }
    }
  };

  /**
   * Return the first armed key starting with `prefix`, or null. Used
   * by parameterised-slot shims to answer "which variant is armed?".
   *
   * @param {string} prefix
   * @returns {string|null}
   */
  proto.firstArmedConfirmationKey = function (prefix) {
    if (!prefix) return null;
    const state = this._ensureConfirmationsState();
    for (const key of state.entries.keys()) {
      if (key.startsWith(prefix)) return key;
    }
    return null;
  };

  proto.isConfirmationArmed = function (key) {
    if (!key) return false;
    return this._ensureConfirmationsState().entries.has(key);
  };

  /**
   * True while the grace window is still active for `key`. Bindings
   * check this to swallow a rapid second click that lands before the
   * user has had time to register the "Confirm" label flip.
   */
  proto.isConfirmationGuardActive = function (key) {
    if (!key) return false;
    const entry = this._ensureConfirmationsState().entries.get(key);
    if (!entry) return false;
    return (Date.now() - entry.armedAt) < entry.grace;
  };
}
