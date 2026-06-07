/**
 * ============================================================
 * ACTIONS: EXTERNAL JOBS
 * ============================================================
 *
 * Service calls for the External Jobs review subtab:
 *   - fetchExternalPendingRuns -> eufy_vacuum.get_external_pending_runs
 *   - confirmExternalRun       -> eufy_vacuum.confirm_external_run
 *
 * Both use callService(..., returnResponse=true) (see actions/core.js) and
 * unwrap the {response} envelope HA wraps supports_response results in.
 * ============================================================
 */

import { DOMAIN } from "../constants.js";

export function applyExternalJobsActions(proto) {

  proto.fetchExternalPendingRuns = async function () {
    const vacuum = this.state?.vacuumEntityId?.();
    if (!vacuum) return { pending: [], brand: null };
    const res = await this.callService(
      DOMAIN,
      "get_external_pending_runs",
      { vacuum_entity_id: vacuum },
      true,
    );
    const data = res?.response ?? res;
    return {
      pending: Array.isArray(data?.pending) ? data.pending : [],
      brand: typeof data?.brand === "string" ? data.brand : null,
    };
  };

  proto.confirmExternalRun = async function (pendingJobId, mapId, roomAssignments) {
    const vacuum = this.state?.vacuumEntityId?.();
    if (!vacuum || !pendingJobId) return { ok: false, error: "missing_args" };
    const res = await this.callService(
      DOMAIN,
      "confirm_external_run",
      {
        vacuum_entity_id: vacuum,
        map_id: String(mapId ?? ""),
        pending_job_id: pendingJobId,
        room_assignments: Array.isArray(roomAssignments) ? roomAssignments : [],
        rebuild_stats: true,
      },
      true,
    );
    return res?.response ?? res ?? { ok: false };
  };

  proto.discardExternalRun = async function (pendingJobId) {
    const vacuum = this.state?.vacuumEntityId?.();
    if (!vacuum || !pendingJobId) return { ok: false };
    const res = await this.callService(
      DOMAIN,
      "discard_external_run",
      { vacuum_entity_id: vacuum, pending_job_id: pendingJobId },
      true,
    );
    return res?.response ?? res ?? { ok: false };
  };
}
