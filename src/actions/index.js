// Defines VacuumCardActions and mixes all action domain modules onto its prototype.

import { applyCoreActions } from "./core.js";
import { applyDockActions } from "./dock.js";
import { applyLearningActions } from "./learning.js";
import { applyMetricsActions } from "./metrics.js";
import { applyOrderActions } from "./order.js";
import { applyRoomProfilesActions } from "./room-profiles.js";
import { applyRunProfilesActions } from "./run-profiles.js";
import { applySavedZonesActions } from "./saved-zones.js";
import { applyReviewActions } from "./review.js";
import { applyRoomsActions } from "./rooms.js";
import { applyThemeActions } from "./theme.js";
import { applyMapActions          } from "./map.js";
import { applySetupActions        } from "./setup.js";
import { applyExternalJobsActions } from "./external-jobs.js";

/* =========================================================
   CLASS
   ========================================================= */

export class VacuumCardActions {
  /**
   * @param {object} hass - Home Assistant hass object
   * @param {VacuumCardState} state
   * @param {object} [card] - the host element (the panel card, or the map-host shim).
   *   Actions are otherwise the only one of the four layers with no card reference,
   *   which is exactly how core.js's failure/refusal toasts shipped inert: they call
   *   `this.showToast?.(this.t?.(…))`, both of which were undefined here, so `?.`
   *   swallowed every one. Optional so a bare `new VacuumCardActions(hass, state)`
   *   still constructs — it just degrades to silence, as before.
   */
  constructor(hass, state, card) {
    this.hass = hass;
    this.state = state;
    this.card = card ?? null;
  }

  /**
   * Refresh hass and state references on every HA update. `card` is deliberately NOT
   * re-taken: it is fixed for the lifetime of this object, and leaving it out keeps
   * the existing two-arg call sites correct.
   * @returns {this}
   */
  sync(hass, state) {
    this.hass = hass;
    this.state = state;
    return this;
  }

  /**
   * Translate a UI string for an action (toast text). Mirrors the identical
   * delegation on VacuumCardBindings: the action prototype has no `t` of its own, so
   * it goes to the renderers' i18n (`card._renderers.t`, renderers/shared.js), which
   * HTML-escapes per trust model B — the toast sink interpolates `message` directly
   * and must receive display-ready text. Falls back to the key: a visible miss, never
   * a throw and never a silent drop.
   *
   * @param {string} key - dot-namespaced string key (e.g. "common.service_failed").
   * @param {Record<string, unknown>} [vars] - interpolation values (raw).
   * @returns {string}
   */
  t(key, vars) {
    return this.card?._renderers?.t?.(key, vars) ?? key;
  }

  /**
   * HTML-escape a RAW value (a backend `reason` / `message`) for the same sink. Use
   * ONLY on raw strings — never on `t()` output, which is already escaped.
   * @param {*} value
   * @returns {string}
   */
  esc(value) {
    return this.card?._renderers?.escapeHtml?.(value) ?? String(value ?? "");
  }

  /**
   * Surface a message to the user. Delegates to the host's toast stack; both hosts
   * (main.js and cards/vacuum-map-host.js) implement showToast.
   * @param {string} message - display-ready (escaped) text.
   * @param {object} [opts] - {kind, ttl}.
   */
  showToast(message, opts) {
    return this.card?.showToast?.(message, opts);
  }
}

/* === PROTOTYPE COMPOSITION ===
   core must be first — all feature modules depend on callService().
   Theme is included as a regular backend service domain. */

applyCoreActions(VacuumCardActions.prototype);
applyDockActions(VacuumCardActions.prototype);
applyLearningActions(VacuumCardActions.prototype);
applyMetricsActions(VacuumCardActions.prototype);
applyOrderActions(VacuumCardActions.prototype);
applyRoomProfilesActions(VacuumCardActions.prototype);
applyRunProfilesActions(VacuumCardActions.prototype);
applySavedZonesActions(VacuumCardActions.prototype);
applyReviewActions(VacuumCardActions.prototype);
applyRoomsActions(VacuumCardActions.prototype);
applyThemeActions(VacuumCardActions.prototype);
applyMapActions(VacuumCardActions.prototype);
applySetupActions(VacuumCardActions.prototype);
applyExternalJobsActions(VacuumCardActions.prototype);
