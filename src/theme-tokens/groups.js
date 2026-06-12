/**
 * ============================================================
 * THEME TOKEN GROUPS
 * ============================================================
 *
 * PURPOSE
 * -------
 * Defines the stable editor group order for the EVCC control-
 * surface token registry.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * Group names are editor metadata only. Backend persistence
 * remains the flat token dictionary.
 *
 * The ordered list here drives:
 * - editor section ordering
 * - grouped registry assembly
 * - group map creation in the registry combiner
 *
 * The Animal Companion sub-groups are NOT listed here — they are
 * generated at runtime from the AnimalSVG registry so adding a new
 * mascot file doesn't require editing this list. See animals.js.
 * The combiner in index.js splices the dynamic animal groups into
 * the slot marked by ANIMAL_GROUPS_SLOT_BEFORE / AFTER.
 *
 * ============================================================
 */

/** Static groups that come before the Animal Companion section. */
export const STATIC_GROUPS_BEFORE_ANIMALS = [
  "App Shell & Typography",
  "Cards & Surfaces",
  "Borders & Shadows",
  "Chips",
  "Room Cards",
  "Map",
  "Floor Textures",
  "Floor Textures — Tile",
  "Floor Textures — Wood",
  "Floor Textures — Marble",
  "Floor Textures — Concrete",
  "Floor Textures — Carpet Low",
  "Floor Textures — Carpet High",
  "Floor Textures — Granite",
  "Queue & Ordering",
  "Status, Confidence & Alerts",
  "Learning & Metrics",
  "Modals & Overlays",
];

/** Static groups that come after the Animal Companion section. */
export const STATIC_GROUPS_AFTER_ANIMALS = [
  "Shared Foundations",
];

/**
 * Convenience full ordered list given a set of animal group labels
 * to splice into the animal slot.
 *
 * @param {string[]} animalGroupLabels — output of buildAnimalGroupOrder(...)
 * @returns {string[]}
 */
export function buildThemeGroups(animalGroupLabels) {
  return [
    ...STATIC_GROUPS_BEFORE_ANIMALS,
    ...(animalGroupLabels || []),
    ...STATIC_GROUPS_AFTER_ANIMALS,
  ];
}

// Backwards-compatibility shim. External callers (if any) that imported
// THEME_GROUPS directly used to get a static array. They now get a stale
// snapshot built with the bundled-animals fallback; the registry combiner
// is the canonical source of the live order. New code should import the
// live `THEME_GROUPS` from `./index.js`, which auto-rebuilds.
export const THEME_GROUPS = buildThemeGroups(
  ["Cat", "Dog", "Raccoon", "Parrot", "Snake"].map(
    (n) => `Animal Companion — ${n}`
  )
);
