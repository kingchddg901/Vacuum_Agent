/**
 * ============================================================
 * ACTIONS: EXTERNAL JOBS
 * ============================================================
 *
 * Service calls for the External Jobs review subtab:
 *   - fetchExternalPendingRuns -> eufy_vacuum.get_external_pending_runs
 *   - resegmentExternalRun     -> eufy_vacuum.resegment_external_run
 *   - confirmExternalRun       -> eufy_vacuum.confirm_external_run
 *   - discardExternalRun       -> eufy_vacuum.discard_external_run
 *
 * All use callService(..., returnResponse=true) (see actions/core.js) and
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

  proto.resegmentExternalRun = async function (pendingJobId, mapId, opts) {
    // Server-side re-segmentation: send a target room count OR an explicit active
    // boundary set; the server re-runs the real segmenter on the saved samples and
    // returns the new (sample-stripped) record + cap meta. The card just re-renders.
    const vacuum = this.state?.vacuumEntityId?.();
    if (!vacuum || !pendingJobId) return { ok: false, error: "missing_args" };
    const data = {
      vacuum_entity_id: vacuum,
      map_id: String(mapId ?? ""),
      pending_job_id: pendingJobId,
    };
    if (opts && opts.expectedRooms != null) {
      data.expected_rooms = Number(opts.expectedRooms);
    } else if (opts && Array.isArray(opts.activeBoundaries)) {
      data.active_boundaries = opts.activeBoundaries.map(Number);
    }
    const res = await this.callService(DOMAIN, "resegment_external_run", data, true);
    return res?.response ?? res ?? { ok: false };
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
