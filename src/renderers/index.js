/**
 * ============================================================
 * RENDERERS: COMBINER
 * ============================================================
 *
 * Defines VacuumCardRenderers and mixes all renderer modules
 * onto its prototype via prototype composition.
 *
 * ============================================================
 */

import { applySharedRenderers     } from "./shared.js";
import { applyBaseStationRenderers } from "./base-station.js";
import { applyMetricsRenderers    } from "./metrics.js";
import { applyReviewRenderers     } from "./review.js";
import { applyRoomsRenderers      } from "./rooms.js";
import { applyRunProfilesRenderers } from "./run-profiles.js";
import { applyMaintenanceRenderers } from "./maintenance.js";
import { applyRoomAccessRenderers  } from "./room-access.js";
import { applyRoomEstimateRenderers } from "./room-estimate.js";
import { applyRoomEditorRenderer  } from "./room-editor.js";
import { applyRoomRulesRenderers  } from "./room-rules.js";
import { applyOrderModalRenderer  } from "./order-modal.js";
import { applyThemeRenderers      } from "./theme.js";
import { applyThemePreviewRenderers } from "./theme-preview.js";
import { applyMapRenderers          } from "./map.js";
import { applyFloorTextureSurface   } from "./floor-texture-surface.js";
import { applySetupRenderers           } from "./setup.js";
import { applyMappingReviewRenderers   } from "./mapping-review.js";
import { applyMobileShellRenderer      } from "./mobile-shell.js";

/* =========================================================
   LEARNING RENDERERS
   =========================================================
   Learning UI is:
   - read-only (state driven)
   - layered on top of rooms
   - safe to inject without breaking existing layouts
   ========================================================= */
import { applyLearningRenderers   } from "./learning.js";

/* =========================================================
   CLASS
   ========================================================= */

export class VacuumCardRenderers {
  /**
   * @param {object} card - The host `VacuumCard` custom element instance.
   */
  constructor(card) {
    this.card = card;
  }

  /**
   * Update the card reference after a hot-reload or config change.
   *
   * @param {object} card - New card instance.
   * @returns {VacuumCardRenderers} `this` for chaining.
   */
  sync(card) {
    this.card = card;
    return this;
  }
}

/* =========================================================
   PROTOTYPE COMPOSITION
   =========================================================
   Order matters:

   - shared first (base utilities)
   - rooms next (primary UI)
   - modals after rooms
   - learning LAST (overlays / augmentations)
   ========================================================= */

applySharedRenderers(VacuumCardRenderers.prototype);
applyBaseStationRenderers(VacuumCardRenderers.prototype);
applyMetricsRenderers(VacuumCardRenderers.prototype);
applyReviewRenderers(VacuumCardRenderers.prototype);
applyRoomsRenderers(VacuumCardRenderers.prototype);
applyRunProfilesRenderers(VacuumCardRenderers.prototype);
applyMaintenanceRenderers(VacuumCardRenderers.prototype);
applyRoomAccessRenderers(VacuumCardRenderers.prototype);
applyRoomEstimateRenderers(VacuumCardRenderers.prototype);
applyRoomEditorRenderer(VacuumCardRenderers.prototype);
applyRoomRulesRenderers(VacuumCardRenderers.prototype);
applyOrderModalRenderer(VacuumCardRenderers.prototype);
applyThemeRenderers(VacuumCardRenderers.prototype);
applyThemePreviewRenderers(VacuumCardRenderers.prototype);
applyMapRenderers(VacuumCardRenderers.prototype);
applyFloorTextureSurface(VacuumCardRenderers.prototype);

/* =========================================================
   LEARNING
   ========================================================= */

applyLearningRenderers(VacuumCardRenderers.prototype);
applySetupRenderers(VacuumCardRenderers.prototype);
applyMappingReviewRenderers(VacuumCardRenderers.prototype);
applyMobileShellRenderer(VacuumCardRenderers.prototype);
