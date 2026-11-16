/**
 * ============================================================
 * STYLES: COMBINER
 * ============================================================
 *
 * PURPOSE
 * -------
 * Combines all style modules into one string injected into
 * shadowRoot on each render.
 *
 *
 * HOW THIS FILE FITS INTO THE SYSTEM
 * -----------------------------------
 * Imported by main.js. The STYLES export is passed into
 * runRenderCycle() and injected via <style> in the shell.
 *
 * Add new style modules here as features are built.
 *
 * ============================================================
 */

import { foundationStyles, sharedChipStyles } from "./foundation.js";
import { fontStyles, fontTokenRules          } from "./fonts.js";
import { baseStationStyles                   } from "./base-station.js";
import { metricsStyles                       } from "./metrics.js";
import { reviewStyles                        } from "./review.js";
import { shellStyles                         } from "./shell.js";
import { layoutStyles                        } from "./layout.js";
import { orderStyles                         } from "./order.js";
import { roomStyles                          } from "./rooms.js";
import { roomAccessStyles                    } from "./room-access.js";
import { roomEstimateStyles                  } from "./room-estimate.js";
import { roomRulesStyles                     } from "./room-rules.js";
import { runProfileStyles                    } from "./run-profiles.js";
import { savedZonesStyles                    } from "./saved-zones.js";
import { maintenanceStyles, maintenanceModalHostStyles } from "./maintenance.js";
import { modalStyles                         } from "./modals.js";
import { learningStyles                      } from "./learning.js";
import { themeStyles                         } from "./theme.js";
import { themePreviewStyles                  } from "./theme-preview.js";
import { mapStyles                           } from "./map.js";
import { floorTextureStyles                  } from "./floor-texture-styles.js";
import { setupStyles                         } from "./setup.js";
import { MOBILE_STYLES                       } from "./mobile.js";
import { externalJobsStyles, externalWizardModalStyles } from "./external-jobs.js";
import { dialogModalStyles                   } from "./dialog.js";
import { jobSummaryStyles                    } from "./job-summary.js";
/* animalHslComponents, syncColourScheme and applyDynamicTheme now live in
   ./apply-tokens.js. MOVED, NOT COPIED, and for one measured reason: this module
   imports every stylesheet in the project, so anything that reached the token WRITER
   through here dragged 443 KB of CSS in with it -- fine for the panel, which needs the
   stylesheets anyway, ruinous for a dashboard card that only wants to paint tokens.
   Re-exported below so every existing import keeps working unchanged. */
export { animalHslComponents, applyDynamicTheme } from "./apply-tokens.js";

export const STYLES = [
  // FIRST: the @font-face declarations must be parsed before anything reads
  // --evcc-font-family, and the [data-evcc-font] override must lose to nothing
  // except specificity (it is on the root, so it beats a theme-set token).
  fontStyles,
  foundationStyles,
  baseStationStyles,
  metricsStyles,
  reviewStyles,
  shellStyles,
  layoutStyles,
  orderStyles,
  roomStyles,
  roomAccessStyles,
  roomEstimateStyles,
  roomRulesStyles,
  runProfileStyles,
  savedZonesStyles,
  maintenanceStyles,
  modalStyles,
  learningStyles,
  themeStyles,
  themePreviewStyles,
  mapStyles,
  floorTextureStyles,
  setupStyles,
  // Mobile shell styles last — they reach into shared elements via
  // .evcc-shell[data-viewport="mobile"] selectors and need to win
  // specificity over the desktop defaults declared in the modules
  // above.
  externalJobsStyles,
  MOBILE_STYLES,
].join("\n");



/**
 * Writes resolved theme tokens as inline CSS custom properties on a host element.
 * Tokens absent or empty in the resolved theme are removed so foundation defaults
 * take over rather than leaving stale values from a previous draft.
 *
 * @param {HTMLElement} card          - The target element (card host or modal host).
 * @param {{ tokens: object }} resolvedTheme - Resolved theme object from state.resolvedTheme().
 */




/* The two document.body portal-host stylesheets are NOT members of the STYLES cascade
   above; they are injected separately into body-level hosts. They now live in their own
   modules like every other stylesheet in this directory. Re-exported here so existing
   imports (main.js, harness/mount-entry.js, the typeface tests) keep resolving. */
export { MODAL_HOST_STYLES } from "./modal-host.js";
export { TOAST_HOST_STYLES } from "./toast-host.js";
