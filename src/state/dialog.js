/**
 * ============================================================
 * STATE: DIALOG  (card-native confirm / alert / prompt)
 * ============================================================
 *
 * Backs the card's own confirm/alert/prompt dialogs — the replacement for
 * the browser-native window.confirm/alert/prompt. Those native dialogs use
 * the BROWSER's locale (so they can never follow the card's per-user
 * language) and are unreliable inside the Home Assistant app / webview,
 * where window.confirm() is commonly suppressed and returns false — which
 * silently swallowed confirmed actions like "delete profile" (the user saw
 * the prompt "stick" and the profile never deleted).
 *
 * One dialog is open at a time. The card-level _confirm/_alert/_prompt
 * helpers (main.js) store a spec carrying a `resolve` fn and schedule a
 * render; the modal-host binding calls resolveDialog(result), which both
 * clears the spec and fulfils that promise.
 *
 * Spec shape:
 *   { kind: "confirm" | "alert" | "prompt",
 *     message, title?, confirmLabel?, cancelLabel?, danger?,
 *     defaultValue?, placeholder?, resolve }
 * ============================================================
 */

// The "cancelled / dismissed" value each kind resolves to — mirrors the
// browser-native originals: confirm -> false, prompt -> null, alert -> resolve.
function dialogCancelValue(kind) {
  return kind === "prompt" ? null : kind === "alert" ? undefined : false;
}

export function applyDialogState(proto) {
  /**
   * Open a dialog. If one is already pending, its awaiting caller is settled
   * with the cancel value FIRST so its promise never hangs (a dialog can only
   * stack one deep — opening a new one dismisses the old).
   */
  proto.openDialog = function (spec) {
    const prev = this._pendingDialog;
    if (prev && typeof prev.resolve === "function") {
      prev.resolve(dialogCancelValue(prev.kind));
    }
    this._pendingDialog = spec || null;
  };

  /** The open dialog spec, or null. Read by renderDialogModal each tick. */
  proto.pendingDialog = function () {
    return this._pendingDialog || null;
  };

  /**
   * Clear the pending dialog and fulfil its promise with `result`. Safe to
   * call with nothing open (no-op) and idempotent — a duplicate resolve
   * (e.g. a re-bound listener firing twice) finds no spec and does nothing.
   */
  proto.resolveDialog = function (result) {
    const spec = this._pendingDialog;
    this._pendingDialog = null;
    if (spec && typeof spec.resolve === "function") {
      spec.resolve(result);
    }
  };

  /**
   * Dismiss the open dialog with its kind-appropriate cancel value (used by
   * Escape / backdrop). Returns true if a dialog was open, so the caller can
   * claim the keystroke and stop it reaching the modal underneath.
   */
  proto.cancelDialog = function () {
    if (!this._pendingDialog) return false;
    this.resolveDialog(dialogCancelValue(this._pendingDialog.kind));
    return true;
  };
}
