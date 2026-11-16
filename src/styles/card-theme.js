/**
 * THE VA THEME, ON A DASHBOARD CARD.
 *
 * The panel wears the VA theme; dashboard cards wear the HA theme. That split is not an
 * oversight — a card is a guest in somebody's dashboard and matching its host is usually
 * the right default — but it leaves no way to carry a VA palette onto a dashboard. This is
 * the opt-in half, and it is opt-in on purpose: switching it on by default would change the
 * appearance of every existing dashboard on upgrade.
 *
 * WHAT MAKES IT CHEAP. Nothing about rendering changes. Both render paths already read
 * every value as a token reference with the shipped value as its CSS fallback — the card
 * CSS layer at renderers/floor-texture-surface.js, the map canvas via `_resolveFloorColor` — so a card
 * with no tokens resolves to the shipped defaults and a card WITH tokens resolves to the
 * theme. The entire job is getting the tokens onto the host element.
 *
 * WHERE THE VALUES COME FROM. `sensor.<robot>_theme_state` carries `card_theme`: the active
 * theme's RAW tokens/colours/alpha. Raw, not resolved, because resolution is a four-layer
 * merge that lives in `state/theme.js` and the card already carries the two default layers
 * (the room-fill palette and FLOOR_TEXTURE_REGISTRY) — it renders materials from them
 * already. Resolving here means ONE implementation shared with the panel instead of a Python
 * port of the same merge.
 *
 * THE SENSOR IS FOUND BY ATTRIBUTE, NEVER BY SLUGGING AN ENTITY ID. `sensor.${slug}_theme_state`
 * is exactly the construction that produced issue #81: Home Assistant slugs an entity id from
 * the TRANSLATED name at creation time, so a derived id is wrong on every localized install
 * and wrong again for anyone who renamed the entity. The sensor publishes
 * `vacuum_entity_id`; match on that.
 *
 * COST, measured 2026-11-16 against the standalone cards bundle: the writer is +1,828 B from
 * `./apply-tokens.js` (it was +443,485 B through `styles/index.js`, which imports every
 * stylesheet in the project) and the resolver is +18,483 B.
 */

import { applyThemeState } from "../state/theme.js";
import { applyDynamicTheme } from "./apply-tokens.js";

/* One prototype for every card on the page. `resolvedTheme()` is a pure function of the
   state object hung off it, so the per-card instance below is the only thing that has to
   be separate — two robots on one dashboard legitimately resolve to different palettes. */
let _themeProto = null;
function themeProto() {
  if (!_themeProto) {
    _themeProto = {};
    applyThemeState(_themeProto);
  }
  return _themeProto;
}

/**
 * The theme sensor's state object for this vacuum, or null.
 *
 * Matches on the published `vacuum_entity_id` attribute rather than reconstructing the
 * entity id — see the note above; a derived id is the #81 bug in a different costume.
 */
export function findThemeSensor(hass, vacuumEntityId) {
  if (!hass?.states || !vacuumEntityId) return null;
  for (const [entityId, st] of Object.entries(hass.states)) {
    if (!entityId.startsWith("sensor.")) continue;
    const a = st?.attributes;
    if (a && a.vacuum_entity_id === vacuumEntityId && a.card_theme !== undefined) return st;
  }
  return null;
}

/**
 * The resolved token map this card should paint, or null when there is nothing to paint.
 *
 * Returns null — rather than an empty map — only when the data is ABSENT or unusable. An
 * active theme that happens to set nothing still returns a (possibly default-only) map,
 * because "follow the VA theme, which currently overrides nothing" and "there is no VA
 * theme here" are different answers and the caller treats them differently.
 */
export function resolveVaTokens(hass, vacuumEntityId) {
  const sensor = findThemeSensor(hass, vacuumEntityId);
  const ct = sensor?.attributes?.card_theme;
  if (!ct || !ct.theme_id) return null;

  const state = Object.create(themeProto());
  state.setThemeLibrary({
    library: {
      [ct.theme_id]: {
        id: ct.theme_id,
        tokens: ct.tokens || {},
        colors: ct.colors || {},
        alpha: ct.alpha || {},
      },
    },
    themes: [],
    default_theme_id: null,
  });
  state.setBackendThemeState({
    active_theme_id: ct.theme_id,
    // The live draft rides along, so a card follows the theme editor as it is being used.
    working_draft: sensor.attributes.working_draft,
    editor_mode: "live",
  });

  const resolved = state.resolvedTheme();
  return resolved && resolved.tokens ? resolved.tokens : null;
}

/**
 * Paint the VA theme onto `host`, or strip it back off.
 *
 * `enabled` false — or data that cannot be resolved — calls the writer with an EMPTY token
 * map rather than returning early, and that is the load-bearing part. `applyDynamicTheme`
 * removes every registry token the map does not carry, so the empty call is what UNDOES a
 * previous paint and hands the card back to the HA theme. An early return would leave the
 * last palette stuck on the host with no way to clear it short of a reload.
 *
 * @returns {boolean} true when a VA theme is now painted on this host.
 */
export function applyVaThemeToCard(host, hass, vacuumEntityId, enabled) {
  if (!host) return false;
  const tokens = enabled ? resolveVaTokens(hass, vacuumEntityId) : null;
  applyDynamicTheme(host, { tokens: tokens || {} });
  return Boolean(tokens);
}
