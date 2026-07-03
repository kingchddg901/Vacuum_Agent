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
import { applyMappingReviewActions } from "./mapping-review.js";
import { applyExternalJobsActions } from "./external-jobs.js";

/* =========================================================
   CLASS
   ========================================================= */

export class VacuumCardActions {
  /**
   * @param {object} hass - Home Assistant hass object
   * @param {VacuumCardState} state
   */
  constructor(hass, state) {
    this.hass = hass;
    this.state = state;
  }

  /**
   * Refresh hass and state references on every HA update.
   * @returns {this}
   */
  sync(hass, state) {
    this.hass = hass;
    this.state = state;
    return this;
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
applyMappingReviewActions(VacuumCardActions.prototype);
applyExternalJobsActions(VacuumCardActions.prototype);
