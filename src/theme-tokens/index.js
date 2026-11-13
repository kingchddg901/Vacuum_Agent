/**
 * ============================================================
 * THEME TOKENS: INDEX / COMBINER
 * ============================================================
 *
 * PURPOSE
 * -------
 * Central assembly point for the helper-driven EVCC control-
 * surface theme token registry.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * Static group files remain the authoring surface for shell,
 * surfaces, chips, etc. The Animal Companion section is built
 * dynamically from the live AnimalSVG registry — adding a new
 * animal via animals/<name>.js + manifest.js requires no edits
 * here.
 *
 * Exports are live `let` bindings. When a new animal registers
 * (the 'animal-svg-registered' document event fires), this module
 * rebuilds the four registry exports in place. Consumers reading
 * the exports as ESM imports see the new values via live bindings
 * without any explicit subscription.
 *
 * Exports:
 * - THEME_TOKEN_REGISTRY
 * - THEME_TOKEN_MAP
 * - THEME_GROUP_MAP
 * - THEME_GROUPS
 *
 * Backend persistence remains flat. Group metadata exists only
 * for editor organization.
 *
 * ============================================================
 */

import {
  STATIC_GROUPS_BEFORE_ANIMALS,
  STATIC_GROUPS_AFTER_ANIMALS,
  buildThemeGroups,
} from "./groups.js";

import { SHELL_TOKENS          } from "./shell.js";
import { SURFACE_TOKENS        } from "./surfaces.js";
import { BORDER_TOKENS         } from "./borders.js";
import { CHIP_TOKENS           } from "./chips.js";
import { ROOM_CARD_TOKENS      } from "./room-cards.js";
import { MAP_TOKENS            } from "./map.js";
import { FLOOR_TEXTURE_TOKENS  } from "./floor-textures.js";
import {
  buildUserFloorTokenRegistry,
  buildUserFloorGroupOrder,
} from "./user-floors.js";
import {
  currentUserMaterials,
  USER_MATERIAL_EVENT,
} from "../textures/user-materials.js";
import { QUEUE_ORDERING_TOKENS } from "./queue-ordering.js";
import { STATUS_TOKENS         } from "./status.js";
import { LEARNING_TOKENS       } from "./learning.js";
import { MODAL_TOKENS          } from "./modals.js";
import { FOUNDATION_TOKENS     } from "./foundations.js";

import {
  ANIMAL_PARENT_GROUP,
  animalSubGroupLabel,
  animalEditorGroupLabel,
  buildAnimalTokenSets,
  buildAnimalGroupOrder,
} from "./animals.js";

/* =========================================================
   STATIC TOKEN SETS (group order matches groups.js)
   ========================================================= */

const STATIC_BEFORE_ANIMALS = [
  SHELL_TOKENS,
  SURFACE_TOKENS,
  BORDER_TOKENS,
  CHIP_TOKENS,
  ROOM_CARD_TOKENS,
  MAP_TOKENS,
  FLOOR_TEXTURE_TOKENS,
  QUEUE_ORDERING_TOKENS,
  STATUS_TOKENS,
  LEARNING_TOKENS,
  MODAL_TOKENS,
];

const STATIC_AFTER_ANIMALS = [
  FOUNDATION_TOKENS,
];

/* =========================================================
   FALLBACK ANIMAL LIST
   =========================================================
   Used before animal-svg has loaded (the module bundle is parsed
   before the dynamic import in src/main.js completes). The same
   five animals ship in the integration's frontend folder, so this
   fallback gives the editor a usable shape on first paint. The
   real list takes over on the next rebuild triggered by
   'animal-svg-registered'.
   ========================================================= */

// anchor: RNR60SN8  the bundled animal roster — the replica set, FOUR copies
//
// ⚠ THIS ANCHOR SAID TWO COPIES AND THERE ARE FOUR. It was minted repairing this file and
// theme-preview-registry.js, and a pre-release audit then found the same stale roster in
// src/renderers/map.js (the companion picker — so the fox was still unselectable on the
// cold path) and src/renderers/theme-preview.js (inert; it reads only "cat"). An anchor is
// a claim about completeness and this one was wrong the day it was minted. Grep the
// LITERAL before trusting the anchor. See docs/dev/00c-replicas.md.
//
// Used only when window.AnimalSVG has not loaded yet: the generated-docs build (node,
// no window) and the first render before the bundle lands. The LIVE list wins whenever
// it exists, so a stale entry here is invisible in a warm browser and loud everywhere
// else — which is exactly how it went unnoticed.
//
// It was ["cat","dog","raccoon","parrot","snake"] after fox and mittens shipped. The
// per-animal tokens are DERIVED from this roster, so both animals got none at all:
// src/i18n/en.js:2596 defines 14 fox token LABELS, translated into all 18 packs, naming
// tokens that were never generated — ~252 strings pointing at nothing. check:i18n cannot
// see it (it verifies used->defined, not defined->used).
//
// ⚠ MITTENS IS DELIBERATELY ABSENT, and adding her here is the trap. She is
// `memorial: true` and declares one colour, so in a BROWSER (live roster) she correctly
// gets her protected eye-only set. But this fallback runs where AnimalSVG is NOT loaded,
// declaredColorSuffixes() then returns null, and the documented default is "show the full
// catalog" — so listing her here publishes 14 tokens INCLUDING FUR for a memorial animal,
// in exactly the generated docs a theme author reads. Her absence is the protection.
// Measured 2026-10-03: adding her yielded 14, not her 6.
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

/* =========================================================
   REBUILD
   ========================================================= */

function assertUniqueTokenKeys(tokens) {
  const seen = new Set();
  for (const token of tokens) {
    const key = String(token?.key ?? "");
    if (!key) {
      throw new Error("[theme-tokens] Registry entry is missing key.");
    }
    if (seen.has(key)) {
      throw new Error(`[theme-tokens] Duplicate token key detected: ${key}`);
    }
    seen.add(key);
  }
}

export let THEME_TOKEN_REGISTRY = [];
export let THEME_TOKEN_MAP      = {};
export let THEME_GROUP_MAP      = {};
export let THEME_GROUPS         = [];

function rebuild() {
  const animals = currentAnimalList();
  const { parent: animalParent, perAnimal } = buildAnimalTokenSets(animals);
  const animalSubgroupTokens = perAnimal.flatMap((g) => g.tokens);

  // Drop-in floor materials mint their editor controls the same way the animal section
  // does. Floors were the hand-authored half (53 literals in floor-textures.js), which
  // is why a dropped-in material could not have controls without someone editing source.
  const userFloorTokens = buildUserFloorTokenRegistry(currentUserMaterials());

  const groupedTokenSets = [
    ...STATIC_BEFORE_ANIMALS,
    animalParent,
    animalSubgroupTokens,
    ...STATIC_AFTER_ANIMALS,
    userFloorTokens,
  ];

  const flat = groupedTokenSets.flat();
  assertUniqueTokenKeys(flat);

  const animalGroupOrder = buildAnimalGroupOrder(animals);
  const groupList = buildThemeGroups(animalGroupOrder)
    .concat(buildUserFloorGroupOrder(currentUserMaterials()));

  THEME_TOKEN_REGISTRY = flat;
  THEME_TOKEN_MAP      = Object.freeze(
    Object.fromEntries(flat.map((token) => [token.key, token]))
  );
  THEME_GROUP_MAP      = Object.freeze(
    groupList.reduce((acc, group) => {
      acc[group] = flat.filter((t) => t.group === group);
      return acc;
    }, {})
  );
  THEME_GROUPS         = groupList;
}

/**
 * Rebuild the four exports now.
 *
 * Exported because the drop-in material catalogue is fetched ASYNCHRONOUSLY and the
 * document event is only a convenience: correctness must not depend on a DOM event
 * existing. The caller sets the material list and calls this, which also makes the whole
 * path exercisable outside a browser — the first attempt here verified in node, where
 * `document` is undefined, so the listener never ran and the check read as "no tokens
 * minted" when the minting was fine.
 *
 * Deliberately NOT called from user-materials.js: that would make the import cycle
 * real. Orchestration belongs at the call site.
 */
export function rebuildThemeTokens() {
  rebuild();
}

// Initial build with the fallback list. The dynamic rebuild on
// 'animal-svg-registered' will overwrite this once animals actually
// register — typically before the editor is opened, since main.js
// dynamically imports animal-svg during the card's first render.
rebuild();

if (typeof document !== "undefined" && document.addEventListener) {
  document.addEventListener("animal-svg-registered", () => {
    try {
      rebuild();
    } catch (err) {
      console.warn("[theme-tokens] rebuild on animal-svg-registered failed:", err);
    }
  });
  // Same shape for drop-in floor materials: the catalogue is fetched asynchronously, so
  // the first build runs without it and this rebuilds once it lands.
  document.addEventListener(USER_MATERIAL_EVENT, () => {
    try {
      rebuild();
    } catch (err) {
      console.warn(`[theme-tokens] rebuild on ${USER_MATERIAL_EVENT} failed:`, err);
    }
  });
}

// Re-export helpers so consumers can resolve animal group labels
// without importing animals.js directly.
export { ANIMAL_PARENT_GROUP, animalSubGroupLabel, animalEditorGroupLabel };
