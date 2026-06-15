// Service wrappers for Setup tab: status, add vacuum, import map, room config, and map delete.

import {
  DOMAIN,
  SERVICE_SETUP_GET_STATUS,
  SERVICE_SETUP_ADD_VACUUM,
  SERVICE_SETUP_IMPORT_MAP,
  SERVICE_SETUP_GET_MAP_ROOMS,
  SERVICE_SETUP_SAVE_ROOMS,
  SERVICE_SETUP_DELETE_MAP,
  SERVICE_SETUP_REJECT_ROOMS,
  SERVICE_SETUP_FORCE_REMOVE_ROOM,
  SERVICE_SETUP_SET_PANEL_TITLE,
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
}
