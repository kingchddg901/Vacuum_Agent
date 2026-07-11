// Service wrappers for the learning system: dashboard snapshot, estimates, reanchor, next room, logs.

import { DOMAIN } from "../constants.js";

/* === LEARNING SERVICE CONSTANTS === */

const SERVICE_RUN_LEARNING_ESTIMATE      = "run_learning_estimate";
const SERVICE_REANCHOR_LEARNING_TIMELINE = "reanchor_learning_timeline";
const SERVICE_GET_NEXT_ROOM              = "get_next_room";
const SERVICE_GET_ROOM_LEARNING_ESTIMATES = "get_room_learning_estimates";
const SERVICE_GET_DASHBOARD_SNAPSHOT     = "get_dashboard_snapshot";
const SERVICE_GET_INCOMPLETE_RUN_LOG     = "get_incomplete_run_log";
const SERVICE_GET_TROUBLE_ROOMS_LOG      = "get_trouble_rooms_log";
const SERVICE_SET_LEARNING_PROCESSING    = "set_learning_processing";
const SERVICE_PROCESS_PENDING_RUNS       = "process_pending_runs";

export function applyLearningActions(proto) {

  /**
   * Fetch the backend-authored dashboard snapshot (primary card read model).
   * @returns {Promise<object|null>}
   */
  proto.getDashboardSnapshot = async function ({
    vacuum_entity_id,
    map_id,
  } = {}) {
    const vacuumEntityId = vacuum_entity_id ?? this.state?.vacuumEntityId?.();
    const mapId = map_id ?? this.state?.activeMapId?.();

    if (!vacuumEntityId || !mapId) return null;

    const result = await this.callService(
      DOMAIN,
      SERVICE_GET_DASHBOARD_SNAPSHOT,
      {
        vacuum_entity_id: vacuumEntityId,
        map_id: String(mapId),
      },
      true
    );

    return result?.response ?? result;
  };

  /**
   * Request the full pre-job learning estimate payload.
   * @param {object} opts
   * @param {number} [opts.current_battery]
   * @param {string} [opts.started_at] - omit for pre-start calls
   * @returns {Promise<object|null>}
   */
  proto.runLearningEstimate = async function ({
    vacuum_entity_id,
    map_id,
    current_battery,
    started_at,
  } = {}) {
    const vacuumEntityId = vacuum_entity_id ?? this.state?.vacuumEntityId?.();
    const mapId = map_id ?? this.state?.activeMapId?.();
    const battery = Number.isFinite(Number(current_battery))
      ? Number(current_battery)
      : this.state?.batteryLevel?.();

    if (!vacuumEntityId || !mapId) return null;

    const data = {
      vacuum_entity_id: vacuumEntityId,
      map_id: String(mapId),
      current_battery: Number.isFinite(Number(battery)) ? Number(battery) : 0,
    };

    // Pre-start calls should omit started_at entirely.
    if (started_at) {
      data.started_at = String(started_at);
    }

    const result = await this.callService(
      DOMAIN,
      SERVICE_RUN_LEARNING_ESTIMATE,
      data,
      true
    );

    return result?.response ?? result;
  };

  /**
   * Recompute remaining ETAs after rooms have completed mid-job.
   * RULES: original_estimate is the full stored payload; completed_rooms must be cumulative.
   * @returns {Promise<object|null>}
   */
  proto.reanchorLearningTimeline = async function ({
    original_estimate,
    completed_rooms,
    reanchor_at,
    current_battery,
  } = {}) {
    if (!original_estimate) return null;

    const data = {
      original_estimate,
      completed_rooms: Array.isArray(completed_rooms) ? completed_rooms : [],
      reanchor_at: reanchor_at
        ? String(reanchor_at)
        : new Date().toISOString(),
    };

    if (current_battery !== undefined && current_battery !== null) {
      const battery = Number(current_battery);
      if (Number.isFinite(battery)) {
        data.current_battery = battery;
      }
    }

    const result = await this.callService(
      DOMAIN,
      SERVICE_REANCHOR_LEARNING_TIMELINE,
      data,
      true
    );

    return result?.response ?? result;
  };

  /**
   * Resolve the live-job banner payload from the latest reanchored estimate.
   * @param {object} opts
   * @param {object} opts.reanchored_estimate
   * @returns {Promise<object|null>} room payload, or {} when all rooms are complete
   */
  proto.getNextLearningRoom = async function ({
    reanchored_estimate,
  } = {}) {
    if (!reanchored_estimate) return null;

    const result = await this.callService(
      DOMAIN,
      SERVICE_GET_NEXT_ROOM,
      { reanchored_estimate },
      true
    );

    return result?.response ?? result;
  };
  
  /**
   * Fetch the last incomplete run log (cancelled, failed, or interrupted job).
   * Returns null when no log exists or the payload has no record_type.
   */
  proto.getIncompleteRunLog = async function ({ vacuum_entity_id } = {}) {
    const vacuumEntityId = vacuum_entity_id ?? this.state?.vacuumEntityId?.();
    if (!vacuumEntityId) return null;

    const result = await this.callService(
      DOMAIN,
      SERVICE_GET_INCOMPLETE_RUN_LOG,
      { vacuum_entity_id: vacuumEntityId },
      true
    );

    const payload = result?.response ?? result;
    // Empty object means no log exists
    if (!payload || typeof payload !== "object" || !payload.record_type) return null;
    return payload;
  };

  /**
   * Fetch the chronic trouble rooms log (room_id → miss stats).
   * Returns null when no log exists or the payload has no record_type.
   */
  proto.getTroubleRoomsLog = async function ({ vacuum_entity_id } = {}) {
    const vacuumEntityId = vacuum_entity_id ?? this.state?.vacuumEntityId?.();
    if (!vacuumEntityId) return null;

    const result = await this.callService(
      DOMAIN,
      SERVICE_GET_TROUBLE_ROOMS_LOG,
      { vacuum_entity_id: vacuumEntityId },
      true
    );

    const payload = result?.response ?? result;
    if (!payload || typeof payload !== "object" || !payload.record_type) return null;
    return payload;
  };

  /**
   * Fetch per-room learning estimates independent of queue state.
   * Read-only; safe to call frequently.
   */
  proto.getRoomLearningEstimates = async function ({
  vacuum_entity_id,
  map_id,
  current_battery,
} = {}) {
  const vacuumEntityId = vacuum_entity_id ?? this.state?.vacuumEntityId?.();
  const mapId = map_id ?? this.state?.activeMapId?.();

  if (!vacuumEntityId || !mapId) return null;

  const data = {
    vacuum_entity_id: vacuumEntityId,
    map_id: String(mapId),
  };

  if (current_battery !== undefined && current_battery !== null) {
    const battery = Number(current_battery);
    if (Number.isFinite(battery)) {
      data.current_battery = battery;
    }
  }

  const result = await this.callService(
    DOMAIN,
    SERVICE_GET_ROOM_LEARNING_ESTIMATES,
    data,
    true
  );

  return result?.response ?? result;
};

  /**
   * Box-level learning-processing toggle (flips ALL vacuums). Turning it on runs the
   * backlog catch-up server-side, then per-run processing resumes.
   */
  proto.setLearningProcessing = async function (enabled) {
    return this.callService(
      DOMAIN,
      SERVICE_SET_LEARNING_PROCESSING,
      { enabled: !!enabled },
      true
    );
  };

  /**
   * Reprocess the backlog collected while processing was off (a full rebuild from
   * history), WITHOUT turning per-run processing back on. Flips all vacuums.
   */
  proto.processPendingRuns = async function () {
    return this.callService(DOMAIN, SERVICE_PROCESS_PENDING_RUNS, {}, true);
  };
}
