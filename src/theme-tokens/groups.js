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
 * ============================================================
 */

export const THEME_GROUPS = [
  "App Shell & Typography",
  "Cards & Surfaces",
  "Borders & Shadows",
  "Chips",
  "Room Cards",
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
  "Animal Companion",
  "Animal Companion — Cat",
  "Animal Companion — Dog",
  "Animal Companion — Raccoon",
  "Animal Companion — Parrot",
  "Animal Companion — Snake",
  "Shared Foundations",
];
