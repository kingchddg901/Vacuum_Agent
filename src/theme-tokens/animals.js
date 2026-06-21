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

/* Memorial animals (registered with `memorial: true`, e.g. Mittens) live under
   their own "Rainbow Bridge" tribute section — separate from the everyday
   companions in both the theme editor and the map-view picker. The flag is
   orthogonal to `type` (body plan), so a memorial can be any animal shape. */
export const MEMORIAL_PARENT_GROUP = "Rainbow Bridge";

export function memorialSubGroupLabel(animalName) {
  const safe = String(animalName || "").replace(/[^a-z0-9-]/gi, "");
  const display = safe.charAt(0).toUpperCase() + safe.slice(1);
  return `${MEMORIAL_PARENT_GROUP} — ${display}`;
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
   The full catalog is 14 suffixes — 5 battery-state eye overrides plus
   9 palette overrides — but each animal exposes only the subset it
   actually themes: a palette token appears iff the animal's `colors`
   block declares the matching `--animal-<suffix>` key, and the eye-state
   bands appear iff it declares a themeable `--animal-eye`. Derived from
   the LIVE registry (window.AnimalSVG.get(name).colors), so a memorial
   like Mittens — baked-literal fur, only `--animal-eye` left dynamic —
   shows just its 6 real tokens instead of 8 inert no-op palette entries.
   Falls back to the full catalog when the registry isn't loaded yet (the
   pre-load bundle build); the 'animal-svg-registered' rebuild then refines.
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

/** The colors-block key a per-animal suffix depends on. The battery-state eye
 *  bands (eye-good/mid/warn/low/charging) are live iff the animal has a
 *  themeable eye, so they all key off "eye"; every other suffix keys off itself. */
function colorKeyForSuffix(suffix) {
  return suffix.startsWith("eye-") ? "eye" : suffix;
}

/** The palette suffixes an animal actually themes, read from its LIVE `colors`
 *  block (keys are `--animal-<suffix>`). Returns null when the registry isn't
 *  available (e.g. the pre-load bundle build) → caller shows the full catalog as
 *  a safe default; the 'animal-svg-registered' rebuild then refines it. */
function declaredColorSuffixes(animalName) {
  try {
    const def = (typeof window !== "undefined" && window.AnimalSVG?.get)
      ? window.AnimalSVG.get(animalName)
      : null;
    const colors = def && def.colors;
    if (colors && typeof colors === "object") {
      return new Set(Object.keys(colors).map((k) => k.replace(/^--animal-/, "")));
    }
  } catch (_) { /* registry not ready — fall through to "show all" */ }
  return null;
}

/** Whether an animal is a memorial (def.memorial), read from the live registry. */
function isMemorial(animalName) {
  try {
    const def = (typeof window !== "undefined" && window.AnimalSVG?.get)
      ? window.AnimalSVG.get(animalName)
      : null;
    return Boolean(def && def.memorial);
  } catch (_) {
    return false;
  }
}

/** The editor sub-group label for an animal — the Rainbow Bridge tribute section
 *  for memorials, the normal Animal Companion section otherwise. The canonical
 *  memorial-aware label; all consumers (token build + preview registry) use it. */
export function animalEditorGroupLabel(animalName) {
  return isMemorial(animalName)
    ? memorialSubGroupLabel(animalName)
    : animalSubGroupLabel(animalName);
}

function buildPerAnimalTokens(animalName) {
  const safe = String(animalName || "").replace(/[^a-z0-9-]/gi, "");
  if (!safe) return [];
  const group = animalEditorGroupLabel(animalName);   // Rainbow Bridge for memorials
  const tk = makeTypedGroupToken(group, "color");
  const declared = declaredColorSuffixes(animalName);   // null => show the full catalog
  return PER_ANIMAL_SUFFIXES
    .filter(({ suffix }) => declared === null || declared.has(colorKeyForSuffix(suffix)))
    .map(({ suffix, label }) => tk.color(`--evcc-animal-${safe}-${suffix}`, label));
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
      group:  animalEditorGroupLabel(name),
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
  const regular  = names.filter((n) => !isMemorial(n));
  const memorial = names.filter((n) => isMemorial(n));
  const order = [ANIMAL_PARENT_GROUP, ...regular.map(animalSubGroupLabel)];
  if (memorial.length) {
    // Tribute section after the everyday companions. The parent is heading-only
    // (no tokens of its own); the editor renders it because it has children.
    order.push(MEMORIAL_PARENT_GROUP, ...memorial.map(memorialSubGroupLabel));
  }
  return order;
}
