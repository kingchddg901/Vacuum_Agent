// Service wrappers for dock actions (wash mop, dry mop, empty dust) and pause-timeout settings.
import {
  DOMAIN,
  SERVICE_GET_PAUSE_TIMEOUT_SETTINGS,
  SERVICE_SET_PAUSE_TIMEOUT_SETTINGS,
} from "../constants.js";

const SERVICE_GET_DOCK_ACTION_STATUS = "get_dock_action_status";
const SERVICE_WASH_MOP = "wash_mop";
const SERVICE_DRY_MOP = "dry_mop";
const SERVICE_STOP_DRY_MOP = "stop_dry_mop";
const SERVICE_EMPTY_DUST = "empty_dust";

export function applyDockActions(proto) {
  /**
   * Fetch the current dock action availability and status from the backend.
   * @param {object} [opts]
   * @param {string} [opts.vacuum_entity_id]
   * @param {string} [opts.map_id]
   * @returns {Promise<object|null>}
   */
  proto.getDockActionStatus = async function ({
    vacuum_entity_id,
    map_id,
  } = {}) {
    const vacuumEntityId = vacuum_entity_id ?? this.state?.vacuumEntityId?.();
    const mapId = map_id ?? this.state?.activeMapId?.();
    if (!vacuumEntityId || !mapId) return null;

    const result = await this.callService(
      DOMAIN,
      SERVICE_GET_DOCK_ACTION_STATUS,
      {
        vacuum_entity_id: vacuumEntityId,
        map_id: String(mapId),
      },
      true
    );

    return result?.response ?? result;
  };

  /** Trigger a mop wash cycle at the dock. */
  proto.washMop = async function () {
    return this._runDockAction(SERVICE_WASH_MOP);
  };

  /** Trigger a mop drying cycle at the dock. */
  proto.dryMop = async function () {
    return this._runDockAction(SERVICE_DRY_MOP);
  };

  /** Cancel a mop drying cycle in progress. */
  proto.stopDryMop = async function () {
    return this._runDockAction(SERVICE_STOP_DRY_MOP);
  };

  /** Trigger a dust bin emptying cycle at the dock. */
  proto.emptyDust = async function () {
    return this._runDockAction(SERVICE_EMPTY_DUST);
  };

  // Resolves vacuum/map IDs and calls the given dock service.
  proto._runDockAction = async function (service) {
    const vacuumEntityId = this.state?.vacuumEntityId?.();
    const mapId = this.state?.activeMapId?.();
    if (!vacuumEntityId || !mapId) return null;

    return this.callService(DOMAIN, service, {
      vacuum_entity_id: vacuumEntityId,
      map_id: String(mapId),
    });
  };

  /**
   * Fetch the configured pause-timeout settings for the vacuum.
   * @param {object} [opts]
   * @param {string} [opts.vacuum_entity_id]
   * @returns {Promise<object|null>}
   */
  proto.getPauseTimeoutSettings = async function ({
    vacuum_entity_id,
  } = {}) {
    const vacuumEntityId = vacuum_entity_id ?? this.state?.vacuumEntityId?.();
    if (!vacuumEntityId) return null;

    const result = await this.callService(
      DOMAIN,
      SERVICE_GET_PAUSE_TIMEOUT_SETTINGS,
      {
        vacuum_entity_id: vacuumEntityId,
      },
      true
    );

    return result?.response ?? result;
  };

  /**
   * Persist the default pause-timeout duration.
   * @param {object} opts
   * @param {string} [opts.vacuum_entity_id]
   * @param {number} opts.pause_timeout_minutes_default
   * @returns {Promise<object|null>}
   */
  proto.setPauseTimeoutSettings = async function ({
    vacuum_entity_id,
    pause_timeout_minutes_default,
  } = {}) {
    const vacuumEntityId = vacuum_entity_id ?? this.state?.vacuumEntityId?.();
    if (!vacuumEntityId) return null;

    const result = await this.callService(
      DOMAIN,
      SERVICE_SET_PAUSE_TIMEOUT_SETTINGS,
      {
        vacuum_entity_id: vacuumEntityId,
        pause_timeout_minutes_default: Number(pause_timeout_minutes_default),
      },
      true
    );

    return result?.response ?? result;
  };
}
