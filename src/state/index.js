// Defines VacuumCardState and mixes all state domain modules onto its prototype.

import { applyCoreState       } from "./core.js";
import { applyDockState       } from "./dock.js";
import { applyMetricsState    } from "./metrics.js";
import { applyOrderState      } from "./order.js";
import { applyRoomProfilesState } from "./room-profiles.js";
import { applyRunProfilesState } from "./run-profiles.js";
import { applyReviewState     } from "./review.js";
import { applyRoomsState      } from "./rooms.js";
import { applyRoomsOrderState } from "./rooms-order.js";
import { applyRoomAccessState } from "./room-access.js";
import { applyRoomEstimateState } from "./room-estimate.js";
import { applyRoomEditorState } from "./room-editor.js";
import { applyRoomRulesState  } from "./room-rules.js";
import { applyMaintenanceState } from "./maintenance.js";
import { applyThemeState } from "./theme.js";
import { applyMapState   } from "./map.js";
import { applyViewportState } from "./viewport.js";

// Learning is predictive, temporal, and controller-managed — applied after all structural modules.
import { applyLearningState      } from "./learning.js";
import { applySetupState         } from "./setup.js";
import { applyMappingReviewState } from "./mapping-review.js";

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
  }

  /**
   * Refresh hass and config references on every HA update.
   * @returns {this}
   */
  sync(hass, config) {
    this.hass = hass;
    this.config = config;
    return this;
  }
}

/* === PROTOTYPE COMPOSITION ===
   core first, order before adapters, rooms before room-editor, learning last. */

applyCoreState(VacuumCardState.prototype);
applyDockState(VacuumCardState.prototype);
applyMetricsState(VacuumCardState.prototype);
applyOrderState(VacuumCardState.prototype);
applyRoomProfilesState(VacuumCardState.prototype);
applyRunProfilesState(VacuumCardState.prototype);
applyReviewState(VacuumCardState.prototype);
applyRoomsState(VacuumCardState.prototype);
applyRoomsOrderState(VacuumCardState.prototype);
applyRoomAccessState(VacuumCardState.prototype);
applyRoomEstimateState(VacuumCardState.prototype);
applyRoomEditorState(VacuumCardState.prototype);
applyRoomRulesState(VacuumCardState.prototype);
applyMaintenanceState(VacuumCardState.prototype);
applyThemeState(VacuumCardState.prototype);
applyMapState(VacuumCardState.prototype);
applyViewportState(VacuumCardState.prototype);

/* === LEARNING / SETUP / MAPPING (FINAL LAYERS) === */

applyLearningState(VacuumCardState.prototype);
applySetupState(VacuumCardState.prototype);
applyMappingReviewState(VacuumCardState.prototype);
