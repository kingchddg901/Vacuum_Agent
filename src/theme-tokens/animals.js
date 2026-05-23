/**
 * ============================================================
 * THEME TOKENS: ANIMAL COMPANION
 * ============================================================
 *
 * PURPOSE
 * -------
 * Theme overrides for the map view's animal companion (<animal-svg>).
 * The animal-svg custom element wraps every color it consumes as
 *   --animal-X: var(--evcc-animal-X, <animal default>);
 * so any token set here on the card host overrides the per-animal
 * default value baked into the animal's definition. Themes can fully
 * reskin every animal by setting all five+ palette tokens; or partial
 * overrides for just the battery-state eye colors.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * Animal companion tokens live in their own group so they can be
 * authored as a coherent palette (light / dark / character / whimsy)
 * rather than mixed into shell or surface tokens. Backend persistence
 * remains the flat token dictionary.
 *
 * HSL TRIPLET FORMAT
 * ------------------
 * Animal SVGs reference colors via `hsl(var(--animal-X))`, so the
 * VALUE assigned to these tokens must be HSL components only — NOT a
 * full `hsl(...)` expression. Example: "142 71% 45%" (good — green).
 *
 * ============================================================
 */

import { animalToken } from "./helpers.js";

export const ANIMAL_TOKENS = [
  // ---- Battery-state eye colors (overrides for the five framework defaults) ----
  animalToken.color("--evcc-animal-eye-good",     "Eye — Good (>50% battery)"),
  animalToken.color("--evcc-animal-eye-mid",      "Eye — Mid (25–50%)"),
  animalToken.color("--evcc-animal-eye-warn",     "Eye — Warn (15–25%)"),
  animalToken.color("--evcc-animal-eye-low",      "Eye — Low (≤15%)"),
  animalToken.color("--evcc-animal-eye-charging", "Eye — Charging (pulses)"),

  // ---- Palette overrides (apply to every animal that consumes the matching --animal-X) ----
  animalToken.color("--evcc-animal-fur",           "Fur"),
  animalToken.color("--evcc-animal-fur-shadow",    "Fur Shadow"),
  animalToken.color("--evcc-animal-fur-highlight", "Fur Highlight"),
  animalToken.color("--evcc-animal-pupil",         "Pupil"),
  animalToken.color("--evcc-animal-nose",          "Nose"),
  animalToken.color("--evcc-animal-whisker",       "Whisker"),
  animalToken.color("--evcc-animal-ear-inner",     "Ear Inner"),
  animalToken.color("--evcc-animal-white-tip",     "White Tip / Accent"),
];
