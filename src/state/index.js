// Defines VacuumCardState and mixes all state domain modules onto its prototype.

import { resolveLang          } from "../i18n/index.js";
import { applyCoreState       } from "./core.js";
import { applyDockState       } from "./dock.js";
import { applyMetricsState    } from "./metrics.js";
import { applyOrderState      } from "./order.js";
import { applyRoomProfilesState } from "./room-profiles.js";
import { applyRunProfilesState } from "./run-profiles.js";
import { applySavedZonesState } from "./saved-zones.js";
import { applyReviewState     } from "./review.js";
import { applyRoomsState      } from "./rooms.js";
import { applyRoomsOrderState } from "./rooms-order.js";
import { applyStepsQueueOrderState } from "./steps-queue-order.js";
import { applyRoomAccessState } from "./room-access.js";
import { applyRoomEstimateState } from "./room-estimate.js";
import { applyRoomEditorState } from "./room-editor.js";
import { applyRoomRulesState  } from "./room-rules.js";
import { applyMaintenanceState } from "./maintenance.js";
import { applyThemeState } from "./theme.js";
import { applyMapState   } from "./map.js";
import { applyViewportState } from "./viewport.js";
import { applyToastsState }   from "./toasts.js";
import { applyConfirmationsState } from "./confirmations.js";
import { applyDialogState }   from "./dialog.js";

// Learning is predictive, temporal, and controller-managed — applied after all structural modules.
import { applyLearningState      } from "./learning.js";
import { applyFaultState         } from "./faults.js";
import { applyJobSummaryState    } from "./job-summary.js";
import { applySetupState         } from "./setup.js";
import { applyExternalJobsState     } from "./external-jobs.js";

/* =========================================================
   CLASS
   ========================================================= */

export class VacuumCardState {

  /**
   * @param {object} hass - Home Assistant hass object
   * @param {object} config - Lovelace card config
   */
  constructor(hass, config) {
    this.hass = hass;
    this.config = config;
    this._migrateLegacyVacKeys?.();   // carry over pre-fix suffix-less localStorage prefs
  }

  /**
   * Refresh hass and config references on every HA update.
   * @returns {this}
   */
  sync(hass, config) {
    this.hass = hass;
    this.config = config;
    this._migrateLegacyVacKeys?.();   // retry the one-time prefs migration once the vacuum is known
    return this;
  }

  /**
   * Install the card's language resolver.
   *
   * State holds `hass` and `config` but NOT `_langOverride` — the per-user globe
   * lives on the card element, because it is a per-user choice persisted per
   * browser rather than card config. State-level modules that render localized
   * text (the steps-queue order adapter's break chips, and anything that follows)
   * therefore cannot reach the globe on their own: `resolveLang(hass, config)`
   * silently resolves to the HA/pin language, so a user who picks Arabic on the
   * globe sees an Arabic modal with English chips inside it.
   *
   * Same shape as `setConfirmationsRenderTrigger` (anchor CNMY8CY9) — a callback
   * from the card rather than a back-reference, so state never holds the element.
   *
   * @param {() => string} fn - returns the card's resolved BCP-47 language.
   * @returns {this}
   */
  setLangResolver(fn) {
    this._langResolver = typeof fn === "function" ? fn : null;
    return this;
  }

  /**
   * The language state-level renderers should translate into.
   *
   * Prefers the card's resolver (globe-aware). Falls back to hass+config so a
   * state constructed without a card — every unit test, and the window between
   * construction and the first hass sync — still resolves a real language rather
   * than throwing. The fallback is the OLD behaviour, so an uninstalled resolver
   * degrades to HA/pin rather than to English literals; [SI-lang-*] pins that the
   * card actually installs it, because a seam nobody wires is decorative.
   *
   * @returns {string} BCP-47 code.
   */
  i18nLanguage() {
    if (this._langResolver) {
      const code = this._langResolver();
      if (code) return String(code);
    }
    return resolveLang(this.hass, this.config);
  }
}

/* === PROTOTYPE COMPOSITION ===
   core first, order before adapters, rooms before room-editor, learning last. */

applyCoreState(VacuumCardState.prototype);
applyConfirmationsState(VacuumCardState.prototype);
applyDialogState(VacuumCardState.prototype);
applyDockState(VacuumCardState.prototype);
applyMetricsState(VacuumCardState.prototype);
applyOrderState(VacuumCardState.prototype);
applyRoomProfilesState(VacuumCardState.prototype);
applyRunProfilesState(VacuumCardState.prototype);
applySavedZonesState(VacuumCardState.prototype);
applyReviewState(VacuumCardState.prototype);
applyRoomsState(VacuumCardState.prototype);
applyRoomsOrderState(VacuumCardState.prototype);
applyStepsQueueOrderState(VacuumCardState.prototype);  // chains onto rooms-order for scope "steps"
applyRoomAccessState(VacuumCardState.prototype);
applyRoomEstimateState(VacuumCardState.prototype);
applyRoomEditorState(VacuumCardState.prototype);
applyRoomRulesState(VacuumCardState.prototype);
applyMaintenanceState(VacuumCardState.prototype);
applyThemeState(VacuumCardState.prototype);
applyMapState(VacuumCardState.prototype);
applyViewportState(VacuumCardState.prototype);
applyToastsState(VacuumCardState.prototype);

/* === LEARNING / SETUP / MAPPING (FINAL LAYERS) === */

applyLearningState(VacuumCardState.prototype);
applyFaultState(VacuumCardState.prototype);
applyJobSummaryState(VacuumCardState.prototype);
applySetupState(VacuumCardState.prototype);
applyExternalJobsState(VacuumCardState.prototype);
