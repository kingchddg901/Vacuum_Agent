// Pure logic for HA 2026.6+ "By entity" card-picker suggestions.
//
// HA 2026.6 added an opt-in `getEntitySuggestion(hass, entityId)` hook on a card's
// window.customCards entry: when a user picks an entity in the entity-first card
// picker, HA calls the hook per card and renders any returned config under a
// "Community" section (see home-assistant/frontend PR #52228). On older HA the
// field is simply ignored — the cards still work, they just aren't auto-suggested.
//
// This module holds the DECISION logic, kept DOM-free so it's unit-testable under
// `node --test` (the card element files import HTMLElement/customElements and can't
// be loaded there). The card entries wire these into their getEntitySuggestion.

/**
 * True when `vacuumEntityId` is a vacuum MANAGED by the integration. Our companion
 * entities (per-room switches, the map-overlays sensor, …) all carry a
 * `vacuum_entity_id` attribute pointing back at their vacuum, so the presence of
 * ANY such entity is the brand-agnostic "we manage this one" signal — true for Eufy
 * and Roborock alike, false for a stock/unmanaged vacuum. This is what keeps us from
 * suggesting our card on someone else's Roomba: the picker calls the hook for EVERY
 * vacuum entity in HA, ours or not.
 */
export function isManagedVacuum(hass, vacuumEntityId) {
  const states = hass?.states;
  if (!states || typeof vacuumEntityId !== "string") return false;
  if (!vacuumEntityId.startsWith("vacuum.")) return false;
  for (const s of Object.values(states)) {
    if (s?.attributes?.vacuum_entity_id === vacuumEntityId) return true;
  }
  return false;
}

/**
 * The first per-room switch's room_id for a vacuum, or null. Mirrors the filter in
 * _shared.roomSwitchesFor, kept local so this module stays dependency-free.
 */
function firstRoomId(hass, vacuumEntityId) {
  const states = hass?.states ?? {};
  for (const [id, s] of Object.entries(states)) {
    if (
      id.startsWith("switch.") &&
      s?.attributes?.vacuum_entity_id === vacuumEntityId &&
      s?.attributes?.room_id != null
    ) {
      return s.attributes.room_id;
    }
  }
  return null;
}

/**
 * getEntitySuggestion body for the multi-room dashboard card. Returns a suggestion
 * config (with the required `custom:` prefix) for OUR managed vacuums, else null.
 * `type` is the card's registered type WITHOUT the custom: prefix.
 */
export function dashboardSuggestion(hass, entityId, type) {
  if (!isManagedVacuum(hass, entityId)) return null;
  return { config: { type: `custom:${type}`, vacuum_entity_id: entityId } };
}

/**
 * getEntitySuggestion body for the single-room card. Pre-fills the vacuum's first
 * room (like getStubConfig) so the suggestion preview is meaningful rather than an
 * empty "pick a room" state.
 */
export function roomSuggestion(hass, entityId, type) {
  if (!isManagedVacuum(hass, entityId)) return null;
  return {
    config: {
      type: `custom:${type}`,
      vacuum_entity_id: entityId,
      room_id: firstRoomId(hass, entityId),
    },
  };
}
