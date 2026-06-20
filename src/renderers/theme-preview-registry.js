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
 * The Animal Companion sub-groups are NOT enumerated here — they
 * are derived from the live AnimalSVG registry and rebuilt when
 * a new animal registers itself (via the 'animal-svg-registered'
 * document event). All animal previews route to the same
 * parameterized renderer; the animal name is passed through
 * `methodArgs` on the registry entry.
 *
 * Consumers read this module via `THEME_PREVIEW_REGISTRY` — a
 * live binding that the dispatch in theme-preview.js reads at
 * call time, so dynamic rebuilds are picked up automatically.
 *
 * ============================================================
 */

import { animalEditorGroupLabel, ANIMAL_PARENT_GROUP } from "../theme-tokens/index.js";

/* =========================================================
   STATIC PREVIEW ENTRIES (non-animal groups)
   ========================================================= */

const STATIC_PREVIEW_ENTRIES = {
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
    description: "Base color tints the marble texture layer on the card surface.",
  },
  "Floor Textures — Concrete": {
    method: "_renderThemePreviewFloorTextureConcrete",
    title: "Concrete Floor Preview",
    description: "Base color tints the concrete texture layer on the card surface.",
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
  [ANIMAL_PARENT_GROUP]: {
    method: "_renderThemePreviewAnimalCompanion",
    title: "Animal Companion Preview",
    description: "Every registered animal in standing pose across all five battery-state bands. Eye-color and global palette tokens in this group apply across every animal.",
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
};

/* =========================================================
   DYNAMIC ENTRIES (per-animal sub-groups)
   ========================================================= */

const BUNDLED_ANIMAL_FALLBACK = ["cat", "dog", "raccoon", "parrot", "snake"];

function currentAnimalList() {
  try {
    const live = (typeof window !== "undefined" && window.AnimalSVG?.list)
      ? window.AnimalSVG.list()
      : null;
    if (Array.isArray(live) && live.length > 0) return live;
  } catch (_) {}
  return BUNDLED_ANIMAL_FALLBACK;
}

function buildAnimalSubgroupEntries(animals) {
  const out = {};
  for (const name of animals) {
    const safe = String(name || "").replace(/[^a-z0-9-]/gi, "");
    if (!safe) continue;
    const display = safe.charAt(0).toUpperCase() + safe.slice(1);
    // Key by the memorial-aware editor group (Rainbow Bridge — X for memorials),
    // so the preview pane resolves for a tribute animal too.
    out[animalEditorGroupLabel(name)] = {
      method:     "_renderThemePreviewAnimal",
      methodArgs: [safe],
      title:      `${display} Preview`,
      description:
        `The ${safe} across all five battery-state bands. Tokens in this ` +
        `sub-group (prefixed --evcc-animal-${safe}-) override the global ` +
        `Animal Companion palette and eye-state colors for just the ${safe}.`,
    };
  }
  return out;
}

/* =========================================================
   LIVE REGISTRY (rebuilds on animal-svg-registered)
   ========================================================= */

function buildRegistry() {
  const animals = currentAnimalList();
  return Object.freeze({
    ...STATIC_PREVIEW_ENTRIES,
    ...buildAnimalSubgroupEntries(animals),
  });
}

export let THEME_PREVIEW_REGISTRY = buildRegistry();

if (typeof document !== "undefined" && document.addEventListener) {
  document.addEventListener("animal-svg-registered", () => {
    try {
      THEME_PREVIEW_REGISTRY = buildRegistry();
    } catch (err) {
      console.warn("[theme-preview-registry] rebuild failed:", err);
    }
  });
}
