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
 * Group files remain the authoring surface. This combiner turns
 * them into:
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

import { THEME_GROUPS } from "./groups.js";

import { SHELL_TOKENS          } from "./shell.js";
import { SURFACE_TOKENS        } from "./surfaces.js";
import { BORDER_TOKENS         } from "./borders.js";
import { CHIP_TOKENS           } from "./chips.js";
import { ROOM_CARD_TOKENS      } from "./room-cards.js";
import { FLOOR_TEXTURE_TOKENS  } from "./floor-textures.js";
import { QUEUE_ORDERING_TOKENS } from "./queue-ordering.js";
import { STATUS_TOKENS         } from "./status.js";
import { LEARNING_TOKENS       } from "./learning.js";
import { MODAL_TOKENS          } from "./modals.js";
import { FOUNDATION_TOKENS     } from "./foundations.js";

const GROUPED_TOKEN_SETS = [
  SHELL_TOKENS,
  SURFACE_TOKENS,
  BORDER_TOKENS,
  CHIP_TOKENS,
  ROOM_CARD_TOKENS,
  FLOOR_TEXTURE_TOKENS,
  QUEUE_ORDERING_TOKENS,
  STATUS_TOKENS,
  LEARNING_TOKENS,
  MODAL_TOKENS,
  FOUNDATION_TOKENS,
];

/**
 * Throws at module-load time if any two registry entries share the same key.
 * Catches authoring mistakes in group files before they silently corrupt the editor.
 *
 * @param {Array<{key: string}>} tokens - Flat token array to validate.
 */
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

export const THEME_TOKEN_REGISTRY = GROUPED_TOKEN_SETS.flat();

assertUniqueTokenKeys(THEME_TOKEN_REGISTRY);

export const THEME_TOKEN_MAP = Object.freeze(
  Object.fromEntries(THEME_TOKEN_REGISTRY.map((token) => [token.key, token]))
);

export const THEME_GROUP_MAP = Object.freeze(
  THEME_GROUPS.reduce((acc, group) => {
    acc[group] = THEME_TOKEN_REGISTRY.filter((token) => token.group === group);
    return acc;
  }, {})
);

export { THEME_GROUPS };
