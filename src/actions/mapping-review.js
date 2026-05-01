// Service wrappers for the Map Bounds Review view: snapshot, clear, exclude/restore job bounds, rebuild.
import { DOMAIN } from "../constants.js";

const SERVICE_GET_ROOM_BOUNDS_SNAPSHOT  = "get_room_bounds_snapshot";
const SERVICE_CLEAR_ROOM_BOUNDS         = "clear_room_bounds";
const SERVICE_EXCLUDE_ROOM_JOB_BOUNDS   = "exclude_room_job_bounds";
const SERVICE_RESTORE_ROOM_JOB_BOUNDS   = "restore_room_job_bounds";
const SERVICE_REBUILD_ROOM_BOUNDS       = "rebuild_room_bounds_from_archive";

export function applyMappingReviewActions(proto) {
  /**
   * Fetch the room bounds snapshot for the Map Bounds Review view.
   * @param {object} [opts]
   * @param {string} [opts.vacuum_entity_id]
   * @param {string} [opts.map_id]
   * @returns {Promise<object|null>}
   */
  proto.getMappingBoundsSnapshot = async function ({ vacuum_entity_id, map_id } = {}) {
    const vacuumEntityId = vacuum_entity_id ?? this.state?.vacuumEntityId?.();
    const mapId          = map_id          ?? this.state?.activeMapId?.();
    if (!vacuumEntityId || !mapId) return null;

    const result = await this.callService(DOMAIN, SERVICE_GET_ROOM_BOUNDS_SNAPSHOT, {
      vacuum_entity_id: vacuumEntityId,
      map_id: String(mapId),
    }, true);
    return result?.response ?? result;
  };

  /**
   * Clear all accumulated bounds data for one room.
   * @param {object} opts
   * @param {string} [opts.vacuum_entity_id]
   * @param {string} [opts.map_id]
   * @param {string|number} opts.room_id
   * @returns {Promise<object|null>}
   */
  proto.clearRoomBounds = async function ({ vacuum_entity_id, map_id, room_id } = {}) {
    const vacuumEntityId = vacuum_entity_id ?? this.state?.vacuumEntityId?.();
    const mapId          = map_id          ?? this.state?.activeMapId?.();
    if (!vacuumEntityId || !mapId || !room_id) return null;

    const result = await this.callService(
      DOMAIN,
      SERVICE_CLEAR_ROOM_BOUNDS,
      { vacuum_entity_id: vacuumEntityId, map_id: String(mapId), room_id: String(room_id) },
      true,
    );
    return result?.response ?? result;
  };

  /**
   * Exclude a specific job's bounds contribution from the room's aggregate.
   * @param {object} opts
   * @param {string} [opts.vacuum_entity_id]
   * @param {string} [opts.map_id]
   * @param {string|number} opts.room_id
   * @param {number} opts.job_index
   * @returns {Promise<object|null>}
   */
  proto.excludeRoomJobBounds = async function ({ vacuum_entity_id, map_id, room_id, job_index } = {}) {
    const vacuumEntityId = vacuum_entity_id ?? this.state?.vacuumEntityId?.();
    const mapId          = map_id          ?? this.state?.activeMapId?.();
    if (!vacuumEntityId || !mapId || !room_id || job_index == null) return null;

    const result = await this.callService(
      DOMAIN,
      SERVICE_EXCLUDE_ROOM_JOB_BOUNDS,
      { vacuum_entity_id: vacuumEntityId, map_id: String(mapId), room_id: String(room_id), job_index: Number(job_index) },
      true,
    );
    return result?.response ?? result;
  };

  /**
   * Restore a previously excluded job's bounds contribution.
   * @param {object} opts
   * @param {string} [opts.vacuum_entity_id]
   * @param {string} [opts.map_id]
   * @param {string|number} opts.room_id
   * @param {number} opts.job_index
   * @returns {Promise<object|null>}
   */
  proto.restoreRoomJobBounds = async function ({ vacuum_entity_id, map_id, room_id, job_index } = {}) {
    const vacuumEntityId = vacuum_entity_id ?? this.state?.vacuumEntityId?.();
    const mapId          = map_id          ?? this.state?.activeMapId?.();
    if (!vacuumEntityId || !mapId || !room_id || job_index == null) return null;

    const result = await this.callService(
      DOMAIN,
      SERVICE_RESTORE_ROOM_JOB_BOUNDS,
      { vacuum_entity_id: vacuumEntityId, map_id: String(mapId), room_id: String(room_id), job_index: Number(job_index) },
      true,
    );
    return result?.response ?? result;
  };

  /**
   * Rebuild a room's bounds from its historical job archive.
   * @param {object} opts
   * @param {string} [opts.vacuum_entity_id]
   * @param {string} [opts.map_id]
   * @param {string|number} opts.room_id
   * @returns {Promise<object|null>}
   */
  proto.rebuildRoomBoundsFromArchive = async function ({ vacuum_entity_id, map_id, room_id } = {}) {
    const vacuumEntityId = vacuum_entity_id ?? this.state?.vacuumEntityId?.();
    const mapId          = map_id          ?? this.state?.activeMapId?.();
    if (!vacuumEntityId || !mapId || !room_id) return null;

    const result = await this.callService(
      DOMAIN,
      SERVICE_REBUILD_ROOM_BOUNDS,
      { vacuum_entity_id: vacuumEntityId, map_id: String(mapId), room_id: String(room_id) },
      true,
    );
    return result?.response ?? result;
  };
}
