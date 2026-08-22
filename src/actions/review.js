// Service wrappers for the Learning Review view: history snapshot, exclude, and restore.
import { DOMAIN } from "../constants.js";

const SERVICE_GET_LEARNING_HISTORY_SNAPSHOT = "get_learning_history_snapshot";
const SERVICE_EXCLUDE_LEARNING_JOB = "exclude_learning_job";
const SERVICE_RESTORE_LEARNING_JOB = "restore_learning_job";

export function applyReviewActions(proto) {
  /**
   * Fetch a filtered learning history snapshot from the backend.
   * @param {object} [opts]
   * @param {string} [opts.vacuum_entity_id]
   * @param {string} [opts.room_slug]
   * @param {string} [opts.profile_key]
   * @param {string} [opts.profile_name]
   * @param {string} [opts.status]
   * @param {boolean} [opts.used_for_learning]
   * @param {string} [opts.origin] external | internal
   * @param {number}  [opts.limit]
   * @returns {Promise<object|null>}
   */
  proto.getLearningHistorySnapshot = async function ({
    vacuum_entity_id,
    room_slug,
    profile_key,
    profile_name,
    status,
    used_for_learning,
    origin,
    limit,
  } = {}) {
    const vacuumEntityId = vacuum_entity_id ?? this.state?.vacuumEntityId?.();
    if (!vacuumEntityId) return null;

    const data = { vacuum_entity_id: vacuumEntityId };
    if (room_slug) data.room_slug = String(room_slug);
    if (profile_key) data.profile_key = String(profile_key);
    // R2-BUG-2. Separate axis from profile_key (a per-room settings signature); this is
    // the saved-profile name. Unlisted params are silently dropped by this destructure,
    // so a new filter that is not named here reaches the service as nothing at all.
    if (profile_name) data.profile_name = String(profile_name);
    if (status) data.status = String(status);
    if (typeof used_for_learning === "boolean") data.used_for_learning = used_for_learning;
    if (origin) data.origin = String(origin);
    if (Number.isFinite(Number(limit))) data.limit = Number(limit);

    const result = await this.callService(
      DOMAIN,
      SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
      data,
      true
    );

    return result?.response ?? result;
  };

  /**
   * Mark a learning job as excluded from model training.
   * @param {object} opts
   * @param {string} opts.job_id
   * @param {string} [opts.reason]
   * @param {boolean} [opts.rebuild_csv=true]
   */
  proto.excludeLearningJob = async function ({
    vacuum_entity_id,
    job_id,
    reason,
    rebuild_csv = true,
  } = {}) {
    const vacuumEntityId = vacuum_entity_id ?? this.state?.vacuumEntityId?.();
    if (!vacuumEntityId || !job_id) return null;

    const result = await this.callService(
      DOMAIN,
      SERVICE_EXCLUDE_LEARNING_JOB,
      {
        vacuum_entity_id: vacuumEntityId,
        job_id: String(job_id),
        ...(reason ? { reason: String(reason) } : {}),
        // ENQZV7VH: the export is where ANALYSIS lives. The card is a glance surface --
        // history and column-by-column reading belong here, and a request for more
        // density on the card is usually a request for this instead.
        rebuild_csv: rebuild_csv !== false,
      },
      true
    );

    return result?.response ?? result;
  };

  /**
   * Restore a previously excluded learning job back into model training.
   * @param {object} opts
   * @param {string} opts.job_id
   * @param {boolean} [opts.rebuild_csv=true]
   */
  proto.restoreLearningJob = async function ({
    vacuum_entity_id,
    job_id,
    rebuild_csv = true,
  } = {}) {
    const vacuumEntityId = vacuum_entity_id ?? this.state?.vacuumEntityId?.();
    if (!vacuumEntityId || !job_id) return null;

    const result = await this.callService(
      DOMAIN,
      SERVICE_RESTORE_LEARNING_JOB,
      {
        vacuum_entity_id: vacuumEntityId,
        job_id: String(job_id),
        rebuild_csv: rebuild_csv !== false,
      },
      true
    );

    return result?.response ?? result;
  };
}
