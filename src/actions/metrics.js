// Service wrapper for fetching the Metrics view snapshot.
import { DOMAIN } from "../constants.js";

const SERVICE_GET_METRICS_SNAPSHOT = "get_metrics_snapshot";

export function applyMetricsActions(proto) {
  /**
   * Fetch the filtered metrics snapshot from the backend.
   * @param {object} [opts]
   * @param {string} [opts.vacuum_entity_id]
   * @param {string} [opts.room_slug]
   * @param {string} [opts.profile_key]
   * @param {string} [opts.status]
   * @param {boolean} [opts.used_for_learning]
   * @returns {Promise<object|null>}
   */
  proto.getMetricsSnapshot = async function ({
    vacuum_entity_id,
    room_slug,
    profile_key,
    status,
    used_for_learning,
  } = {}) {
    const vacuumEntityId = vacuum_entity_id ?? this.state?.vacuumEntityId?.();
    if (!vacuumEntityId) return null;

    const data = { vacuum_entity_id: vacuumEntityId };
    if (room_slug) data.room_slug = String(room_slug);
    if (profile_key) data.profile_key = String(profile_key);
    if (status) data.status = String(status);
    if (typeof used_for_learning === "boolean") data.used_for_learning = used_for_learning;

    const result = await this.callService(
      DOMAIN,
      SERVICE_GET_METRICS_SNAPSHOT,
      data,
      true
    );

    return result?.response ?? result;
  };
}
