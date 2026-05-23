/**
 * ============================================================
 * THEME TOKENS: ANIMAL COMPANION
 * ============================================================
 *
 * PURPOSE
 * -------
 * Theme overrides for the map view's animal companion (<animal-svg>).
 *
 * Structure follows the floor-textures pattern:
 *   - Parent "Animal Companion" group holds global tokens (the five
 *     battery-state eye colors + an optional cross-animal palette
 *     override layer).
 *   - Per-animal subgroups ("Animal Companion — Cat" etc.) hold that
 *     specific animal's palette overrides plus optional per-animal
 *     eye-state overrides.
 *
 * OVERRIDE PRIORITY (high → low)
 * ------------------------------
 *   1. Per-animal theme token   (--evcc-animal-cat-fur)
 *   2. Global animal token      (--evcc-animal-fur)
 *   3. Animal's own default     (value baked into the animal's colors block)
 *
 * The animal-svg shadow root wraps each color it consumes with this
 * two-level fallback, so themes can either reskin everything in one
 * place (set the globals) or fine-tune per animal (set the per-animal
 * tokens). Both can coexist.
 *
 * HSL TRIPLET FORMAT
 * ------------------
 * Animal SVGs reference colors via `hsl(var(--animal-X))`, so the
 * VALUE assigned to these tokens must be HSL components only — NOT a
 * full `hsl(...)` expression. Example: "142 71% 45%".
 *
 * ============================================================
 */

import { makeTypedGroupToken } from "./helpers.js";

// Helpers — one per sub-group. Matches the floor-textures.js convention
// of defining per-sub-group token factories inline.
const a   = makeTypedGroupToken("Animal Companion",             "color");
const aCat     = makeTypedGroupToken("Animal Companion — Cat",     "color");
const aDog     = makeTypedGroupToken("Animal Companion — Dog",     "color");
const aRaccoon = makeTypedGroupToken("Animal Companion — Raccoon", "color");
const aParrot  = makeTypedGroupToken("Animal Companion — Parrot",  "color");
const aSnake   = makeTypedGroupToken("Animal Companion — Snake",   "color");

// ---- Parent group: global tokens applied across every animal ----
//
// Set these once to bulk-override all animals. Per-animal sub-groups can
// further override on top.
export const ANIMAL_TOKENS = [
  // Battery-state eye colors (semantic, not animal-specific).
  a.color("--evcc-animal-eye-good",     "Eye — Good (>50% battery)"),
  a.color("--evcc-animal-eye-mid",      "Eye — Mid (25–50%)"),
  a.color("--evcc-animal-eye-warn",     "Eye — Warn (15–25%)"),
  a.color("--evcc-animal-eye-low",      "Eye — Low (≤15%)"),
  a.color("--evcc-animal-eye-charging", "Eye — Charging (pulses)"),

  // Global palette fallbacks. Set these to apply across all animals at once.
  a.color("--evcc-animal-fur",            "Fur (all animals)"),
  a.color("--evcc-animal-fur-shadow",     "Fur Shadow (all)"),
  a.color("--evcc-animal-fur-highlight",  "Fur Highlight (all)"),
  a.color("--evcc-animal-eye",            "Eye Base (all)"),
  a.color("--evcc-animal-pupil",          "Pupil (all)"),
  a.color("--evcc-animal-nose",           "Nose (all)"),
  a.color("--evcc-animal-whisker",        "Whisker (all)"),
  a.color("--evcc-animal-ear-inner",      "Ear Inner (all)"),
  a.color("--evcc-animal-white-tip",      "White Tip / Accent (all)"),
];

// ---- Per-animal sub-groups ----
//
// Each animal exposes the same shape: 5 battery-state eye colors + 9 palette
// tokens. Setting any token here overrides the corresponding global token for
// just that animal.

function perAnimalTokens(g) {
  return [
    // Per-animal battery-state overrides.
    g.color(`${g.PREFIX_STUB}-eye-good`,     "Eye — Good"),
    g.color(`${g.PREFIX_STUB}-eye-mid`,      "Eye — Mid"),
    g.color(`${g.PREFIX_STUB}-eye-warn`,     "Eye — Warn"),
    g.color(`${g.PREFIX_STUB}-eye-low`,      "Eye — Low"),
    g.color(`${g.PREFIX_STUB}-eye-charging`, "Eye — Charging"),
    // Per-animal palette.
    g.color(`${g.PREFIX_STUB}-fur`,            "Fur"),
    g.color(`${g.PREFIX_STUB}-fur-shadow`,     "Fur Shadow"),
    g.color(`${g.PREFIX_STUB}-fur-highlight`,  "Fur Highlight"),
    g.color(`${g.PREFIX_STUB}-eye`,            "Eye Base"),
    g.color(`${g.PREFIX_STUB}-pupil`,          "Pupil"),
    g.color(`${g.PREFIX_STUB}-nose`,           "Nose"),
    g.color(`${g.PREFIX_STUB}-whisker`,        "Whisker"),
    g.color(`${g.PREFIX_STUB}-ear-inner`,      "Ear Inner"),
    g.color(`${g.PREFIX_STUB}-white-tip`,      "White Tip / Accent"),
  ];
}

// Stamp each per-animal helper with its token prefix stub so perAnimalTokens
// can build the keys generically. Keeps the 5 arrays from being duplicated.
aCat.PREFIX_STUB     = "--evcc-animal-cat";
aDog.PREFIX_STUB     = "--evcc-animal-dog";
aRaccoon.PREFIX_STUB = "--evcc-animal-raccoon";
aParrot.PREFIX_STUB  = "--evcc-animal-parrot";
aSnake.PREFIX_STUB   = "--evcc-animal-snake";

export const ANIMAL_CAT_TOKENS     = perAnimalTokens(aCat);
export const ANIMAL_DOG_TOKENS     = perAnimalTokens(aDog);
export const ANIMAL_RACCOON_TOKENS = perAnimalTokens(aRaccoon);
export const ANIMAL_PARROT_TOKENS  = perAnimalTokens(aParrot);
export const ANIMAL_SNAKE_TOKENS   = perAnimalTokens(aSnake);
