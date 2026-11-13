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
import { userFloorGroupLabel } from "../theme-tokens/user-floors.js";
import { currentUserMaterials, USER_MATERIAL_EVENT } from "../textures/user-materials.js";

/* =========================================================
   STATIC PREVIEW ENTRIES (non-animal groups)
   ========================================================= */

/*
 * Each entry's user-facing pane title/description is i18n'd: it carries a
 * stable `titleKey`/`descKey` (namespace "theme_preview.*") that the renderer
 * (`_renderThemePreviewPane` in theme-preview.js) resolves via `this.t` at the
 * render site, keeping this module a pure data/routing layer. The OBJECT KEYS
 * (group ids like "App Shell & Typography") are data/identity, NOT translated.
 */
const STATIC_PREVIEW_ENTRIES = {
  "App Shell & Typography": {
    method: "_renderThemePreviewShellTypography",
    titleKey: "theme_preview.group.shell.title",
    descKey: "theme_preview.group.shell.desc",
  },
  "Cards & Surfaces": {
    method: "_renderThemePreviewCardsSurfaces",
    titleKey: "theme_preview.group.surfaces.title",
    descKey: "theme_preview.group.surfaces.desc",
  },
  "Borders & Shadows": {
    method: "_renderThemePreviewBordersShadows",
    titleKey: "theme_preview.group.borders.title",
    descKey: "theme_preview.group.borders.desc",
  },
  "Chips": {
    method: "_renderThemePreviewChips",
    titleKey: "theme_preview.group.chips.title",
    descKey: "theme_preview.group.chips.desc",
  },
  "Room Cards": {
    method: "_renderThemePreviewRoomCards",
    titleKey: "theme_preview.group.rooms.title",
    descKey: "theme_preview.group.rooms.desc",
  },
  "Floor Textures": {
    method: "_renderThemePreviewFloorTextures",
    titleKey: "theme_preview.group.floor.title",
    descKey: "theme_preview.group.floor.desc",
  },
  "Floor Textures — Tile": {
    method: "_renderThemePreviewFloorTextureTile",
    titleKey: "theme_preview.group.floor_tile.title",
    descKey: "theme_preview.group.floor_tile.desc",
  },
  "Floor Textures — Wood": {
    method: "_renderThemePreviewFloorTextureWood",
    titleKey: "theme_preview.group.floor_wood.title",
    descKey: "theme_preview.group.floor_wood.desc",
  },
  "Floor Textures — Marble": {
    method: "_renderThemePreviewFloorTextureMarble",
    titleKey: "theme_preview.group.floor_marble.title",
    descKey: "theme_preview.group.floor_marble.desc",
  },
  "Floor Textures — Concrete": {
    method: "_renderThemePreviewFloorTextureConcrete",
    titleKey: "theme_preview.group.floor_concrete.title",
    descKey: "theme_preview.group.floor_concrete.desc",
  },
  "Floor Textures — Carpet Low": {
    method: "_renderThemePreviewFloorTextureCarpetLow",
    titleKey: "theme_preview.group.floor_carpet_low.title",
    descKey: "theme_preview.group.floor_carpet_low.desc",
  },
  "Floor Textures — Carpet High": {
    method: "_renderThemePreviewFloorTextureCarpetHigh",
    titleKey: "theme_preview.group.floor_carpet_high.title",
    descKey: "theme_preview.group.floor_carpet_high.desc",
  },
  "Floor Textures — Granite": {
    method: "_renderThemePreviewFloorTextureGranite",
    titleKey: "theme_preview.group.floor_granite.title",
    descKey: "theme_preview.group.floor_granite.desc",
  },
  "Queue & Ordering": {
    method: "_renderThemePreviewQueueOrdering",
    titleKey: "theme_preview.group.queue.title",
    descKey: "theme_preview.group.queue.desc",
  },
  "Status, Confidence & Alerts": {
    method: "_renderThemePreviewStatusAlerts",
    titleKey: "theme_preview.group.status.title",
    descKey: "theme_preview.group.status.desc",
  },
  "Learning & Metrics": {
    method: "_renderThemePreviewLearningMetrics",
    titleKey: "theme_preview.group.learning.title",
    descKey: "theme_preview.group.learning.desc",
  },
  [ANIMAL_PARENT_GROUP]: {
    method: "_renderThemePreviewAnimalCompanion",
    titleKey: "theme_preview.group.animal.title",
    descKey: "theme_preview.group.animal.desc",
  },
  "Modals & Overlays": {
    method: "_renderThemePreviewModalsOverlays",
    titleKey: "theme_preview.group.modal.title",
    descKey: "theme_preview.group.modal.desc",
  },
  "Shared Foundations": {
    method: "_renderThemePreviewSharedFoundations",
    titleKey: "theme_preview.group.foundations.title",
    descKey: "theme_preview.group.foundations.desc",
  },
};

/* =========================================================
   DYNAMIC ENTRIES (per-animal sub-groups)
   ========================================================= */

// REPLICA RNR60SN8 — the twin lives at src/theme-tokens/index.js, which carries the
// reasoning. Both rosters must list every bundled animal: this copy decides which
// previews the theme editor offers, the other decides which tokens exist at all, so a
// drift between them shows as a preview with no tokens or tokens with no preview.
const BUNDLED_ANIMAL_FALLBACK = ["cat", "dog", "fox", "raccoon", "parrot", "snake"];

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
    // so the preview pane resolves for a tribute animal too. The pane title/
    // description are i18n'd via stable keys + per-animal vars, resolved by
    // `_renderThemePreviewPane` (this.t) at the render site. The animal name is
    // [a-z0-9-]-sanitized; escaping at the sink is therefore a no-op.
    out[animalEditorGroupLabel(name)] = {
      method:     "_renderThemePreviewAnimal",
      methodArgs: [safe],
      titleKey:   "theme_preview.group.animal_sub.title",
      titleVars:  { animal: display },
      descKey:    "theme_preview.group.animal_sub.desc",
      descVars:   { animal: safe },
    };
  }
  return out;
}

/* =========================================================
   DYNAMIC ENTRIES (per drop-in material)
   =========================================================

   Same problem the animals above already solve, and solved the same way: a
   dropped-in material's token group exists only at RUNTIME, so it cannot be
   enumerated in STATIC_PREVIEW_ENTRIES. Without an entry the editor shows the
   group's controls with NO contextual preview beside them -- the sliders move
   real tokens and nothing on screen answers, which reads as the render being
   broken rather than the preview simply being absent.

   The group label is IMPORTED from user-floors.js, never restated: it is the
   key both halves must agree on, and a mismatch is silent in exactly this way.
   ========================================================= */

function buildUserFloorPreviewEntries(materials) {
  const out = {};
  for (const material of Array.isArray(materials) ? materials : []) {
    if (!material || typeof material.id !== "string" || !material.id) continue;
    const display = material.name || material.id;
    out[userFloorGroupLabel(material)] = {
      method:     "_renderThemePreviewFloorTextureUser",
      methodArgs: [material.id],
      titleKey:   "theme_preview.group.floor_user.title",
      titleVars:  { material: display },
      descKey:    "theme_preview.group.floor_user.desc",
      descVars:   { material: display },
    };
  }
  return out;
}

/* =========================================================
   LIVE REGISTRY (rebuilds on animal-svg-registered + drop-in load)
   ========================================================= */

function buildRegistry() {
  const animals = currentAnimalList();
  return Object.freeze({
    ...STATIC_PREVIEW_ENTRIES,
    ...buildAnimalSubgroupEntries(animals),
    ...buildUserFloorPreviewEntries(currentUserMaterials()),
  });
}

export let THEME_PREVIEW_REGISTRY = buildRegistry();

if (typeof document !== "undefined" && document.addEventListener) {
  const rebuild = () => {
    try {
      THEME_PREVIEW_REGISTRY = buildRegistry();
    } catch (err) {
      console.warn("[theme-preview-registry] rebuild failed:", err);
    }
  };
  document.addEventListener("animal-svg-registered", rebuild);
  // The catalogue lands AFTER first paint, so the registry built at module
  // evaluation time cannot contain a drop-in. Same contract as the animals.
  document.addEventListener(USER_MATERIAL_EVENT, rebuild);
}
