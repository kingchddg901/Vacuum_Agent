// What does Home Assistant call this entity? One question, one answer, every surface.
//
// WHY THIS EXISTS. From HA 2026.11 an entity's displayed name is COMPOSED from its context
// rather than read from one attribute: the entity's own name, prefixed by its device, and
// its parent device when it has one. A card that reads `friendly_name` now disagrees with
// every built-in card on the same dashboard — the release notes are explicit that a custom
// card showing an unexpected name is the card's to fix, and that `friendly_name` is kept
// only for backward compatibility and is headed for deprecation.
//
// WE WERE NOT IN THE COHORT. HA sent patches to the authors of dozens of popular custom
// cards ahead of 2026.11. No PR or issue of ours carries one (26 PRs, 41 issues, measured
// 2026-11-04), so this is ours to write.
//
// THE NAME ARGUMENT IS OMITTED ON PURPOSE. `formatEntityName(stateObj, name?, options?)`
// treats a missing `name` as HA's own DEFAULT_ENTITY_NAME, which is
// `[parent_device, device, entity]` (frontend `src/common/entity/entity_name_config.ts`).
// Passing an explicit `[{type:"device"},{type:"entity"}]` would pin us to today's built-in
// composition, drop the parent-device segment that child devices depend on, and stop
// tracking HA when the default moves. Omitting it is what keeps us identical to the
// built-in cards by construction rather than by coincidence.
//
// THE FALLBACK IS LOAD-BEARING, NOT DEFENSIVE. `hass.formatEntityName` arrived in 2026.4
// and `hacs.json` declares a 2025.6.0 floor, so for every install from the floor through
// 2026.3 the helper is simply absent and `friendly_name` is the only answer there is. That
// is the same shape as `entity_helpers.py::device_config_entry_ids` on the Python side —
// read the new name first, fall back, and test that the fallback still bites. See
// docs/dev/37-the-entity-surface.md § 1a.
//
// NOT GUARDED WITH try/catch, deliberately. Every built-in card calls this function
// unguarded; swallowing an exception here would make the old-core fallback permanent and
// silent on a modern core, which is exactly the failure this module exists to prevent.

/**
 * The name HA itself would show for an entity, or "" when there is nothing to show.
 *
 * Returns "" rather than the entity id so each caller keeps its OWN last resort — the card
 * header formats the object id, a picker row shows the raw id, a rule label says "Entity".
 * Centralising the question does not mean centralising everyone's fallback.
 *
 * Callers must therefore use `||`, not `??`: "" is a real answer meaning "unknown".
 *
 * @param {object|null|undefined} hass      the HA connection object
 * @param {string|null|undefined} entityId  entity id, used for the state lookup
 * @param {object|null} [stateObj]          the state object when the caller already holds
 *                                          it, which avoids a second lookup inside a loop
 *                                          over every entity in the house
 * @returns {string}
 */
export function entityDisplayName(hass, entityId, stateObj = undefined) {
  const state = stateObj ?? (entityId ? hass?.states?.[entityId] : null) ?? null;
  if (!state) return "";

  if (typeof hass?.formatEntityName === "function") {
    const composed = String(hass.formatEntityName(state) ?? "").trim();
    // An empty compose must not blank a name we could still read the old way.
    if (composed) return composed;
  }

  return String(state.attributes?.friendly_name ?? "").trim();
}
