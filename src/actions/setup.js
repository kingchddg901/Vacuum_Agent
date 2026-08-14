// Service wrappers for Setup tab: status, add vacuum, import map, room config, and map delete.

import {
  DOMAIN,
  SERVICE_SETUP_GET_STATUS,
  SERVICE_SETUP_ADD_VACUUM,
  SERVICE_SET_ENTITY_OVERRIDE,
  SERVICE_SETUP_IMPORT_MAP,
  SERVICE_SETUP_GET_MAP_ROOMS,
  SERVICE_SETUP_SAVE_ROOMS,
  SERVICE_SETUP_DELETE_MAP,
  SERVICE_SETUP_REJECT_ROOMS,
  SERVICE_SETUP_FORCE_REMOVE_ROOM,
  SERVICE_SETUP_SET_PANEL_TITLE,
  SERVICE_SETUP_SET_MAP_CAMERA,
  SERVICE_DISCOVER_ROOMS,
  SERVICE_RECONCILE_ROOM,
} from "../constants.js";

export function applySetupActions(proto) {

  /**
   * Fetch the current setup status from the backend.
   * Returns a SetupStatus dict or null.
   */
  proto.getSetupStatus = async function () {
    const result = await this.callService(DOMAIN, SERVICE_SETUP_GET_STATUS, {}, true);
    return result?.response ?? result ?? null;
  };

  /**
   * Register the given vacuum entity with the integration.
   * Returns an ActionResult dict or null.
   */
  /**
   * Pin one role to an entity the user picked, or clear it (live:ENT-13).
   *
   * All THREE params are named explicitly. This wrapper layer destructures a
   * fixed list and silently drops anything unlisted, so an omitted param here
   * fails as "the service ignored me" rather than as an error.
   *
   * @param {string} vacuumEntityId
   * @param {string} role
   * @param {string} entityId  blank clears the override
   */
  proto.setEntityOverride = async function (vacuumEntityId, role, entityId) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_SET_ENTITY_OVERRIDE,
      {
        vacuum_entity_id: vacuumEntityId,
        role,
        entity_id: entityId ?? "",
      },
      true,
    );
    return result?.response ?? result ?? null;
  };

  proto.addVacuum = async function (vacuumEntityId) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_SETUP_ADD_VACUUM,
      { vacuum_entity_id: vacuumEntityId },
      true,
    );
    return result?.response ?? result ?? null;
  };

  /**
   * Set (or clear, with an empty title) the vacuum's sidebar panel title.
   * The backend re-registers the panel live; the sidebar repaints on refresh.
   * Returns an ActionResult dict or null.
   */
  proto.renamePanel = async function (vacuumEntityId, title) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_SETUP_SET_PANEL_TITLE,
      { vacuum_entity_id: vacuumEntityId, title: String(title ?? "") },
      true,
    );
    return result?.response ?? result ?? null;
  };

  /**
   * Set (or clear, with an empty entity_id) this vacuum's live-map image/camera
   * entity override — the entity used as the Map view's live backdrop. Blank clears
   * the override (falls back to the adapter pattern). Returns an ActionResult or null.
   */
  proto.setMapCamera = async function (vacuumEntityId, entityId) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_SETUP_SET_MAP_CAMERA,
      { vacuum_entity_id: vacuumEntityId, entity_id: String(entityId ?? "") },
      true,
    );
    return result?.response ?? result ?? null;
  };

  /**
   * Import the currently active map for the given vacuum.
   * Returns an ActionResult dict or null.
   */
  proto.importActiveMap = async function (vacuumEntityId) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_SETUP_IMPORT_MAP,
      { vacuum_entity_id: vacuumEntityId },
      true,
    );
    return result?.response ?? result ?? null;
  };

  /**
   * Fetch room list for a specific map (for the room config step).
   * Returns { rooms: [...], vacuum_entity_id, map_id } or null.
   */
  proto.getSetupMapRooms = async function (vacuumEntityId, mapId) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_SETUP_GET_MAP_ROOMS,
      { vacuum_entity_id: vacuumEntityId, map_id: String(mapId) },
      true,
    );
    return result?.response ?? result ?? null;
  };

  /**
   * Delete one imported map.
   * @param {string} confirmationToken - required by backend; high-protection maps need exact map display name
   */
  proto.deleteSetupMap = async function (vacuumEntityId, mapId, confirmationToken) {
    const data = {
      vacuum_entity_id: vacuumEntityId,
      map_id:           String(mapId),
    };
    if (confirmationToken) data.confirmation_token = confirmationToken;
    const result = await this.callService(DOMAIN, SERVICE_SETUP_DELETE_MAP, data, true);
    return result?.response ?? result ?? null;
  };

  /**
   * Save room configuration for a map.
   * @param {number[]} enabledRoomIds - rooms to keep; omitted rooms are excluded
   * @param {Object<string,string>} floorTypes - String(room_id) → floor_type
   */
  proto.saveSetupRooms = async function (vacuumEntityId, mapId, enabledRoomIds, floorTypes) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_SETUP_SAVE_ROOMS,
      {
        vacuum_entity_id:  vacuumEntityId,
        map_id:            String(mapId),
        enabled_room_ids:  enabledRoomIds,
        floor_types:       floorTypes,
      },
      true,
    );
    return result?.response ?? result ?? null;
  };

  /**
   * Mark one or more discovered rooms as phantoms — they never surface in
   * room_drift.new_rooms again, even if discovery re-reports them.
   *
   * @param {number[]} roomIds - integer room IDs to reject
   */
  proto.rejectSetupRooms = async function (vacuumEntityId, roomIds) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_SETUP_REJECT_ROOMS,
      {
        vacuum_entity_id: vacuumEntityId,
        room_ids:         roomIds,
      },
      true,
    );
    return result?.response ?? result ?? null;
  };

  /**
   * Bypass the missing-pass counter and immediately flag one room as removed.
   * The room stays in managed_rooms (history preserved); only the drift
   * signal flips so the setup tab moves it from transiently_missing →
   * removed_rooms on the next status read.
   */
  proto.forceRemoveSetupRoom = async function (vacuumEntityId, roomId) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_SETUP_FORCE_REMOVE_ROOM,
      {
        vacuum_entity_id: vacuumEntityId,
        room_id:          Number(roomId),
      },
      true,
    );
    return result?.response ?? result ?? null;
  };

  /**
   * Apply (migrate) or dismiss (ignore) the identity-shift reconciliation
   * reviews for one map (CARD-7/RP-019, Gap 3).
   *
   * DIRECT hass.callService — deliberately bypasses this file's usual
   * `this.callService` wrapper. The backend refuses a stale/missing
   * plan_token by RAISING a ServiceValidationError (plan_changed /
   * plan_token_required) rather than returning a {success:false} shape, so
   * the shared wrapper's generic catch-and-toast (core.js) would swallow the
   * one detail the caller needs to distinguish. Same reasoning as
   * analyzeMapImage/uploadMapImage's own direct-call pattern (actions/map.js).
   * Throws on failure — bindings/setup.js owns the try/catch + the
   * plan_changed/plan_token_required message inspection (mirroring
   * bindings/map.js's _uploadErrorMessage pattern).
   *
   * @param {string} action - "migrate" | "ignore"
   * @param {string|null} planToken - opaque; round-tripped from the reviews
   *   payload, never parsed. Design doc sends it on BOTH migrate and ignore.
   */
  proto.reconcileRoom = async function (vacuumEntityId, mapId, action, planToken) {
    const result = await this.hass.callService(
      DOMAIN,
      SERVICE_RECONCILE_ROOM,
      {
        vacuum_entity_id: vacuumEntityId,
        map_id:           String(mapId),
        action,
        plan_token:       planToken,
      },
      undefined, // target
      false,     // notifyOnError — the binding owns user-facing messaging
      true,      // returnResponse — service is registered supports_response=True
    );
    return result?.response ?? result ?? null;
  };

  /**
   * Fire a discover_rooms pass for one vacuum/map. NOT response-capable on
   * the backend by design (Gap 2/CARD-7 — see setup/status.py's passive
   * reconciliation read, which deliberately does not make discover_rooms
   * response-capable). This only needs the call to COMPLETE so the backend's
   * discovery cache (and its reconciliation block + plan_token) is fresh
   * before the caller re-polls getSetupStatus. Used by the reconcile-room
   * stale-plan_token silent recovery and its manual "re-discover" fallback —
   * never called from a render/poll path.
   */
  proto.discoverRooms = async function (vacuumEntityId, mapId) {
    await this.callService(
      DOMAIN,
      SERVICE_DISCOVER_ROOMS,
      { vacuum_entity_id: vacuumEntityId, map_id: String(mapId) },
      false,
    );
  };
}
