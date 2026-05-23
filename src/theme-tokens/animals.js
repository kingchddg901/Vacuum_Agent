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
 *     battery-state eye colors + a cross-animal palette override layer).
 *   - Per-animal subgroups ("Animal Companion — Cat" etc.) hold that
 *     specific animal's palette overrides plus per-animal eye-state
 *     overrides.
 *
 * SMART REGISTRY
 * --------------
 * This module exports BUILD FUNCTIONS, not static arrays. The combiner
 * in index.js calls buildAnimalTokenSets() with the live list of
 * registered animals (window.AnimalSVG.list()) and gets a fully
 * formed token registry. When a new animal registers itself, the
 * 'animal-svg-registered' document event fires, index.js rebuilds,
 * and the new animal's sub-group appears in the editor automatically
 * — no manual touch points in src/.
 *
 * OVERRIDE PRIORITY (high → low)
 * ------------------------------
 *   1. Per-animal theme token   (--evcc-animal-cat-fur)
 *   2. Global animal token      (--evcc-animal-fur)
 *   3. Animal's own default     (value baked into the animal's colors block)
 *
 * The animal-svg shadow root wraps each color it consumes with this
 * two-level fallback (see colorVarsStyle / batteryStateDefaultsCss in
 * animal-svg.js).
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

/* =========================================================
   GROUP NAMING
   ========================================================= */

export const ANIMAL_PARENT_GROUP = "Animal Companion";

/** Group label for a specific animal name. Stable across rebuilds so
 *  saved themes referencing a sub-group keep working. */
export function animalSubGroupLabel(animalName) {
  const safe = String(animalName || "").replace(/[^a-z0-9-]/gi, "");
  const display = safe.charAt(0).toUpperCase() + safe.slice(1);
  return `${ANIMAL_PARENT_GROUP} — ${display}`;
}

/* =========================================================
   PARENT GROUP — global tokens (shape never depends on animal list)
   ========================================================= */

const a = makeTypedGroupToken(ANIMAL_PARENT_GROUP, "color");

const PARENT_TOKENS = [
  // Battery-state eye colors (semantic, not animal-specific).
  a.color("--evcc-animal-eye-good",     "Eye — Good (>50% battery)"),
  a.color("--evcc-animal-eye-mid",      "Eye — Mid (25–50%)"),
  a.color("--evcc-animal-eye-warn",     "Eye — Warn (15–25%)"),
  a.color("--evcc-animal-eye-low",      "Eye — Low (≤15%)"),
  a.color("--evcc-animal-eye-charging", "Eye — Charging (pulses)"),

  // Global palette fallbacks. Set these to apply across every animal.
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

/* =========================================================
   PER-ANIMAL TOKEN SHAPE
   =========================================================
   Every animal exposes the same 14 tokens — 5 battery-state overrides
   plus 9 palette overrides. The names are derived from the animal name
   so the registry is mechanical.
   ========================================================= */

const PER_ANIMAL_SUFFIXES = [
  // Battery-state overrides — apply to just this animal.
  { suffix: "eye-good",       label: "Eye — Good" },
  { suffix: "eye-mid",        label: "Eye — Mid" },
  { suffix: "eye-warn",       label: "Eye — Warn" },
  { suffix: "eye-low",        label: "Eye — Low" },
  { suffix: "eye-charging",   label: "Eye — Charging" },
  // Palette overrides.
  { suffix: "fur",            label: "Fur" },
  { suffix: "fur-shadow",     label: "Fur Shadow" },
  { suffix: "fur-highlight",  label: "Fur Highlight" },
  { suffix: "eye",            label: "Eye Base" },
  { suffix: "pupil",          label: "Pupil" },
  { suffix: "nose",           label: "Nose" },
  { suffix: "whisker",        label: "Whisker" },
  { suffix: "ear-inner",      label: "Ear Inner" },
  { suffix: "white-tip",      label: "White Tip / Accent" },
];

function buildPerAnimalTokens(animalName) {
  const safe = String(animalName || "").replace(/[^a-z0-9-]/gi, "");
  if (!safe) return [];
  const group = animalSubGroupLabel(safe);
  const tk = makeTypedGroupToken(group, "color");
  return PER_ANIMAL_SUFFIXES.map(({ suffix, label }) =>
    tk.color(`--evcc-animal-${safe}-${suffix}`, label)
  );
}

/* =========================================================
   PUBLIC API
   ========================================================= */

/**
 * Build the full Animal Companion token set for the given list of
 * animal names. Returns `{ parent, perAnimal }`:
 *
 *   - `parent` — array of global tokens for the "Animal Companion" group.
 *   - `perAnimal` — array of `{ group, tokens }` entries, one per animal,
 *     each ready to be slotted into the combined registry.
 *
 * The animal-name list typically comes from `window.AnimalSVG.list()`
 * but accepts a manual fallback for the initial bundle build before
 * animal-svg has loaded.
 *
 * @param {string[]} animals
 * @returns {{ parent: Array, perAnimal: Array<{ group: string, tokens: Array }> }}
 */
export function buildAnimalTokenSets(animals) {
  const names = Array.isArray(animals) ? animals.filter(Boolean) : [];
  return {
    parent: PARENT_TOKENS,
    perAnimal: names.map((name) => ({
      group:  animalSubGroupLabel(name),
      tokens: buildPerAnimalTokens(name),
    })),
  };
}

/**
 * Convenience: full flat list of every animal token, in stable order.
 * Used by the registry combiner.
 *
 * @param {string[]} animals
 * @returns {Array}
 */
export function buildAnimalTokenRegistry(animals) {
  const { parent, perAnimal } = buildAnimalTokenSets(animals);
  return [
    ...parent,
    ...perAnimal.flatMap((g) => g.tokens),
  ];
}

/**
 * Group labels for the Animal Companion section in editor order:
 * parent first, then one per animal.
 *
 * @param {string[]} animals
 * @returns {string[]}
 */
export function buildAnimalGroupOrder(animals) {
  const names = Array.isArray(animals) ? animals.filter(Boolean) : [];
  return [ANIMAL_PARENT_GROUP, ...names.map(animalSubGroupLabel)];
}
