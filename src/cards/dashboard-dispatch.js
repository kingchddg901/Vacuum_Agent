// Pure run-launcher logic for the Vacuum Agent dashboard card.
//
// This module is intentionally DOM-free and side-effect-free so it can be unit
// tested with `node --test` (see dashboard-dispatch.test.mjs). The card element
// (dashboard-card.js) holds the armed state here and only EXECUTES the plan this
// module produces — it never builds service calls itself.
//
// Two responsibilities:
//   1. nextArmed()  — the mutual-exclusivity state machine. Arming a profile or a
//      scene clears any room selection (and vice-versa): exactly one run SOURCE is
//      ever live. This function returns NEW armed state only — never a service
//      call — which is what structurally guarantees "selecting is inert".
//   2. planStart()  — given the armed state + context, return the ORDERED list of
//      {domain, service, data} calls Start should dispatch. The empty/no-source
//      case returns [] (Start no-ops), so nothing can fire until a source is armed.

/**
 * @typedef {Object} Armed
 * @property {null|"rooms"|"profile"|"scene"} source
 * @property {number[]} selectedRoomIds   room_ids toggled on (source === "rooms")
 * @property {string|null} profileId       saved run-profile id (source === "profile")
 * @property {string|null} sceneOption      vendor-app scene name (source === "scene")
 */

/** The neutral armed state — nothing selected, Start is a no-op. */
export function emptyArmed() {
  return { source: null, selectedRoomIds: [], profileId: null, sceneOption: null };
}

function toggleId(ids, id) {
  const has = ids.some((x) => String(x) === String(id));
  return has ? ids.filter((x) => String(x) !== String(id)) : [...ids, id];
}

/**
 * Mutual-exclusivity reducer. Returns a brand-new Armed state; the inputs are
 * never mutated. NEVER returns or triggers a service call — arming is inert.
 *
 * Actions:
 *   { type: "toggleRoom", roomId }   toggle a room into/out of the selection
 *   { type: "pickProfile", profileId } arm a saved profile ("" clears)
 *   { type: "pickScene", option }      arm a vendor-app scene ("" clears)
 *   { type: "clear" }                  reset to emptyArmed()
 *
 * @param {Armed} state
 * @param {{type: string, roomId?: number, profileId?: string, option?: string}} action
 * @returns {Armed}
 */
export function nextArmed(state, action) {
  const cur = state ?? emptyArmed();
  switch (action?.type) {
    case "toggleRoom": {
      const selectedRoomIds = toggleId(cur.selectedRoomIds ?? [], action.roomId);
      return selectedRoomIds.length
        ? { source: "rooms", selectedRoomIds, profileId: null, sceneOption: null }
        : emptyArmed();
    }
    case "pickProfile":
      return action.profileId
        ? { source: "profile", selectedRoomIds: [], profileId: action.profileId, sceneOption: null }
        : emptyArmed();
    case "pickScene":
      return action.option
        ? { source: "scene", selectedRoomIds: [], profileId: null, sceneOption: action.option }
        : emptyArmed();
    case "clear":
      return emptyArmed();
    default:
      return cur;
  }
}

/** True when arming `source` should grey-out the room pickers (and vice-versa). */
export function roomsDisabled(armed) {
  return armed?.source === "profile" || armed?.source === "scene";
}

/**
 * Is the armed source still runnable against LIVE data? A scene option or a saved
 * profile can vanish (vendor-app edit / library delete) between arming and Start.
 * Firing a removed scene is the dangerous case (select_option = the run), so Start
 * must re-validate. Rooms are always "valid" here — planStart filters them to the
 * live switch set, and an empty result already no-ops.
 *
 * @param {Armed} armed
 * @param {{sceneOptions?: string[], profileIds?: string[]}} live
 */
export function armedIsValid(armed, live = {}) {
  const a = armed ?? emptyArmed();
  if (a.source === "scene") {
    return (live.sceneOptions ?? []).map(String).includes(String(a.sceneOption));
  }
  if (a.source === "profile") {
    return (live.profileIds ?? []).map(String).includes(String(a.profileId));
  }
  return true;
}

/**
 * Build the ordered service-call plan for Start. Pure: returns an array of
 * { domain, service, data } descriptors; the caller executes them in order.
 *
 * @param {Armed} armed
 * @param {Object} ctx
 * @param {string} ctx.vacuumEntityId
 * @param {string} [ctx.mapId]                active map id (for rooms / profile)
 * @param {string} [ctx.sceneEntityId]        resolved select.<obj>_scene id
 * @param {Array<{entityId: string, roomId: (number|string), currentlyOn: boolean,
 *                dirty?: boolean, fields?: object}>} [ctx.rooms]
 *        every managed room switch for this vacuum, with current on/off + any
 *        unsaved per-row field edits.
 * @returns {Array<{domain: string, service: string, data: object}>}
 */
export function planStart(armed, ctx) {
  const a = armed ?? emptyArmed();
  const vacuum_entity_id = ctx?.vacuumEntityId;
  if (!vacuum_entity_id) return [];

  if (a.source === "scene") {
    if (!ctx?.sceneEntityId || !a.sceneOption) return [];
    // Selecting the option IS the run — this is the only call (no VA dispatch).
    return [
      { domain: "select", service: "select_option",
        data: { entity_id: ctx.sceneEntityId, option: a.sceneOption } },
    ];
  }

  if (a.source === "profile") {
    if (!a.profileId) return [];
    const data = { vacuum_entity_id, profile_id: a.profileId };
    if (ctx?.mapId != null) data.map_id = String(ctx.mapId);
    return [{ domain: "eufy_vacuum", service: "start_run_profile", data }];
  }

  if (a.source === "rooms") {
    const selected = new Set((a.selectedRoomIds ?? []).map(String));
    const rooms = ctx?.rooms ?? [];
    const chosen = rooms.filter((r) => selected.has(String(r.roomId)));
    if (!chosen.length) return [];

    const calls = [];
    // 1. Persist any unsaved per-row field edits for the rooms being run.
    for (const r of chosen) {
      if (r.dirty && r.fields) {
        calls.push({
          domain: "eufy_vacuum", service: "update_room_fields",
          data: {
            vacuum_entity_id,
            map_id: String(r.mapId ?? ctx?.mapId ?? ""),
            room_id: r.roomId,
            ...r.fields,
          },
        });
      }
    }
    // 2. Reconcile the room switches so EXACTLY the chosen set is on.
    for (const r of rooms) {
      const want = selected.has(String(r.roomId));
      if (want && !r.currentlyOn) {
        calls.push({ domain: "switch", service: "turn_on", data: { entity_id: r.entityId } });
      } else if (!want && r.currentlyOn) {
        calls.push({ domain: "switch", service: "turn_off", data: { entity_id: r.entityId } });
      }
    }
    // 3. Start the run off the now-armed selection.
    const startData = { vacuum_entity_id };
    if (ctx?.mapId != null) startData.map_id = String(ctx.mapId);
    calls.push({ domain: "eufy_vacuum", service: "start_selected_rooms", data: startData });
    return calls;
  }

  // No source armed → Start is a no-op (nothing fires before a selection).
  return [];
}
