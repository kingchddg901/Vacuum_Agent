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
import { THEME_TOKEN_REGISTRY                } from "../theme-tokens/index.js";

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
 * ANIMAL TOKENS ARE HSL COMPONENTS, NOT COLOURS.
 *
 * The animal SVGs consume every one of their variables inside hsl():
 *
 *   default:   "--animal-fur": "0 0% 7%"
 *   consumed:  fill="hsl(var(--animal-fur))"          332 uses, 332 wrapped
 *
 * But the theme system stores every colour token as 8-digit hex
 * (state/theme.js:_hexWithAlpha), so setting Fur to yellow at 88% produced
 * `fill="hsl(#e8e800e0)"` — invalid CSS. An invalid fill falls back to SVG's
 * initial value, which is BLACK. So ANY animal colour a user set turned that
 * part of the animal black, while untouched animals looked correct because
 * their built-in triplets were still in play. That reads as "I broke my
 * theme", which is how it was reported.
 *
 * Converted here, at the write to the DOM, rather than in resolvedTheme():
 * the editor's swatch reads the hex bucket, and the export envelope stores
 * hex, so both keep working unchanged. Nothing outside the animal-svg module
 * consumes --evcc-animal-*, so no other consumer can be surprised by the
 * different shape.
 *
 * Exported for the unit test — the conversion is pure and worth pinning.
 *
 * @param {string} hex "#rrggbb" or "#rrggbbaa"
 * @returns {string|null} "H S% L%" / "H S% L% / A", or null if not hex
 */
export function animalHslComponents(hex) {
  const m = /^#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?$/.exec(String(hex || "").trim());
  if (!m) return null;

  const int = parseInt(m[1], 16);
  const r = ((int >> 16) & 255) / 255;
  const g = ((int >> 8) & 255) / 255;
  const b = (int & 255) / 255;

  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  const d = max - min;

  let h = 0;
  let s = 0;
  if (d !== 0) {
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h *= 60;
  }

  const round = (n) => Math.round(n * 10) / 10;
  const base = `${round(h)} ${round(s * 100)}% ${round(l * 100)}%`;

  // Alpha rides along as hsl()'s slash syntax rather than being dropped —
  // the opacity slider is half of what this editor's colour row does.
  if (m[2] === undefined) return base;
  const a = parseInt(m[2], 16) / 255;
  // Two decimals so the emitted alpha reads as the percentage the slider
  // showed (0xe0 -> 0.88, not 0.878) — round() above is one decimal and is
  // for the H/S/L components.
  return a >= 1 ? base : `${base} / ${Math.round(a * 100) / 100}`;
}

/**
 * Writes resolved theme tokens as inline CSS custom properties on a host element.
 * Tokens absent or empty in the resolved theme are removed so foundation defaults
 * take over rather than leaving stale values from a previous draft.
 *
 * @param {HTMLElement} card          - The target element (card host or modal host).
 * @param {{ tokens: object }} resolvedTheme - Resolved theme object from state.resolvedTheme().
 */
export function applyDynamicTheme(card, resolvedTheme) {
  if (!card || !resolvedTheme) return;

  const { tokens } = resolvedTheme;
  const host = card;

  // anchor: CN344YSE
  THEME_TOKEN_REGISTRY.forEach((token) => {
    if (!Object.prototype.hasOwnProperty.call(tokens, token.key) || tokens[token.key] === null || tokens[token.key] === undefined || tokens[token.key] === "") {
      host.style.removeProperty(token.key);
    }
  });

  Object.entries(tokens).forEach(([property, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      // See animalHslComponents: these are consumed as bare hsl() components,
      // so a hex value here renders the animal black.
      const asComponents = property.startsWith("--evcc-animal-")
        ? animalHslComponents(value)
        : null;
      host.style.setProperty(property, asComponents ?? value);
    }
  });
}

/* The two document.body portal-host stylesheets are NOT members of the STYLES cascade
   above; they are injected separately into body-level hosts. They now live in their own
   modules like every other stylesheet in this directory. Re-exported here so existing
   imports (main.js, harness/mount-entry.js, the typeface tests) keep resolving. */
export { MODAL_HOST_STYLES } from "./modal-host.js";
export { TOAST_HOST_STYLES } from "./toast-host.js";
