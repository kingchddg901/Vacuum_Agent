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
   * @param {string} [opts.status]
   * @param {boolean} [opts.used_for_learning]
   * @param {number}  [opts.limit]
   * @returns {Promise<object|null>}
   */
  proto.getLearningHistorySnapshot = async function ({
    vacuum_entity_id,
    room_slug,
    profile_key,
    status,
    used_for_learning,
    limit,
  } = {}) {
    const vacuumEntityId = vacuum_entity_id ?? this.state?.vacuumEntityId?.();
    if (!vacuumEntityId) return null;

    const data = { vacuum_entity_id: vacuumEntityId };
    if (room_slug) data.room_slug = String(room_slug);
    if (profile_key) data.profile_key = String(profile_key);
    if (status) data.status = String(status);
    if (typeof used_for_learning === "boolean") data.used_for_learning = used_for_learning;
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
