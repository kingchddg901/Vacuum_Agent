/**
 * ============================================================
 * THEME PREVIEW REGISTRY
 * ============================================================
 *
 * PURPOSE
 * -------
 * Maps theme-editor token groups to lightweight contextual
 * preview renderer methods.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * The theme preview system is intentionally group-aware. This
 * registry keeps preview routing declarative so the editor can
 * mount only the surfaces relevant to the currently focused
 * group instead of rendering a permanent full-card mirror.
 *
 * ============================================================
 */

export const THEME_PREVIEW_REGISTRY = Object.freeze({
  "App Shell & Typography": {
    method: "_renderThemePreviewShellTypography",
    title: "Shell & Typography Preview",
    description: "Accent, heading, and body text examples show the shell voice this group controls.",
  },
  "Cards & Surfaces": {
    method: "_renderThemePreviewCardsSurfaces",
    title: "Cards & Surfaces Preview",
    description: "Shared card, panel, and input surfaces show the base material language for the editor.",
  },
  "Borders & Shadows": {
    method: "_renderThemePreviewBordersShadows",
    title: "Borders & Shadows Preview",
    description: "Border strength and elevation samples reveal separation, depth, and hover lift.",
  },
  "Chips": {
    method: "_renderThemePreviewChips",
    title: "Chip Preview",
    description: "A compact chip matrix highlights default, active, hover, success, warning, and excluded states.",
  },
  "Room Cards": {
    method: "_renderThemePreviewRoomCards",
    title: "Room Card Preview",
    description: "Mini room cards expose profile chips, room chips, and room-surface treatment together.",
  },
  "Floor Textures": {
    method: "_renderThemePreviewFloorTextures",
    title: "Floor Texture Preview",
    description: "Live swatches show each material's overlay on the card surface. Opacity, scale, and tint tokens update in real time.",
  },
  "Floor Textures — Tile": {
    method: "_renderThemePreviewFloorTextureTile",
    title: "Tile Floor Preview",
    description: "Base and accent colors control the grout lines and tile face on card and map surfaces.",
  },
  "Floor Textures — Wood": {
    method: "_renderThemePreviewFloorTextureWood",
    title: "Wood Floor Preview",
    description: "Base and accent colors control the wood grain, seam lines, and directional depth layers.",
  },
  "Floor Textures — Marble": {
    method: "_renderThemePreviewFloorTextureMarble",
    title: "Marble Floor Preview",
    description: "Base and accent colors control the marble field and vein layers.",
  },
  "Floor Textures — Concrete": {
    method: "_renderThemePreviewFloorTextureConcrete",
    title: "Concrete Floor Preview",
    description: "Base and accent colors control the micro-texture and broad variation layers.",
  },
  "Floor Textures — Carpet Low": {
    method: "_renderThemePreviewFloorTextureCarpetLow",
    title: "Carpet Low Pile Preview",
    description: "Base color tints the low-pile carpet texture layer on the card surface.",
  },
  "Floor Textures — Carpet High": {
    method: "_renderThemePreviewFloorTextureCarpetHigh",
    title: "Carpet High Pile Preview",
    description: "Base color tints the high-pile carpet texture layer on the card surface.",
  },
  "Floor Textures — Granite": {
    method: "_renderThemePreviewFloorTextureGranite",
    title: "Granite Floor Preview",
    description: "Base color tints the granite texture layer on the card surface.",
  },
  "Queue & Ordering": {
    method: "_renderThemePreviewQueueOrdering",
    title: "Queue & Ordering Preview",
    description: "Queue strip, order chips, and drag feedback samples show sequencing and reorder states.",
  },
  "Status, Confidence & Alerts": {
    method: "_renderThemePreviewStatusAlerts",
    title: "Status & Alerts Preview",
    description: "Status dots, confidence badges, and alert surfaces show semantic state color relationships.",
  },
  "Learning & Metrics": {
    method: "_renderThemePreviewLearningMetrics",
    title: "Learning & Metrics Preview",
    description: "Estimate badges and learning panels preview predictive and analytical surfaces.",
  },
  "Animal Companion": {
    method: "_renderThemePreviewAnimalCompanion",
    title: "Animal Companion Preview",
    description: "Every registered animal in standing pose across all five battery-state bands. Eye-color tokens drive the columns; palette tokens drive the bodies.",
  },
  "Modals & Overlays": {
    method: "_renderThemePreviewModalsOverlays",
    title: "Modal & Overlay Preview",
    description: "A modal shell sample isolates overlay surfaces, chips, warning states, and backdrop treatment.",
  },
  "Shared Foundations": {
    method: "_renderThemePreviewSharedFoundations",
    title: "Shared Foundations Preview",
    description: "A mixed control-surface preview shows spacing, radius, motion, and typography primitives together.",
  },
});
