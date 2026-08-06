/**
 * ============================================================
 * STATE: JOB SUMMARY MODAL
 * ============================================================
 *
 * Owns which job the summary modal is showing.
 *
 * WHY IT EXISTS. There was a gap between the job JSON and the job-history row:
 * the row said "3 errors" and the rest lived in a file only someone who knows it
 * exists would open. For the person this card is built for, whatever is not in the
 * card does not exist. This modal is that surface.
 *
 * Holds a job_id, NOT a job object. The history snapshot is refetched on a poll,
 * so a captured object would go stale while the modal is open; re-looking it up
 * each render means the modal tracks the data. If the job vanishes from the
 * snapshot (filter change, list refresh), the lookup returns null and the modal
 * closes itself rather than rendering a frozen copy.
 *
 * ============================================================
 */

export function applyJobSummaryState(proto) {
  /** Open the summary for one job id. */
  proto.openJobSummary = function (jobId) {
    const id = String(jobId ?? "").trim();
    if (!id) return;
    this._jobSummaryJobId = id;
  };

  proto.closeJobSummary = function () {
    this._jobSummaryJobId = null;
  };

  proto.isJobSummaryOpen = function () {
    return !!this._jobSummaryJobId;
  };

  proto.jobSummaryJobId = function () {
    return this._jobSummaryJobId ?? null;
  };

  /**
   * The job this modal is showing, looked up fresh from the current snapshot.
   *
   * @returns {object|null} null when nothing is open OR the job is no longer in
   *   the snapshot — the renderer treats both the same way, which is what makes a
   *   disappearing job close the modal instead of freezing it.
   */
  proto.activeJobSummary = function () {
    const id = this._jobSummaryJobId;
    if (!id) return null;
    const jobs = this.learningHistoryJobs?.();
    if (!Array.isArray(jobs)) return null;
    return jobs.find((job) => String(job?.job_id ?? "") === String(id)) ?? null;
  };

  /**
   * Fault rows for the open job, already shaped for display.
   *
   * The backend resolves label_key and source at READ time, so this works on
   * every historical job rather than only ones finalized since the labels
   * shipped. `recovered` is recovery state ONLY — nothing in the record
   * establishes that a fault ended a run, so the card must not imply it did.
   */
  proto.jobSummaryFaults = function () {
    const job = this.activeJobSummary();
    const rows = job?.run_errors;
    return Array.isArray(rows) ? rows.filter((r) => r && typeof r === "object") : [];
  };

  /** Per-room rows for the open job (settings as dispatched + what happened). */
  proto.jobSummaryRooms = function () {
    const job = this.activeJobSummary();
    const rows = job?.room_detail;
    return Array.isArray(rows) ? rows.filter((r) => r && typeof r === "object") : [];
  };

  /**
   * Recharge block, or null. Derived backend-side from the accumulators, so a
   * record written before RECHARGE-FLAG-1 still answers correctly.
   */
  proto.jobSummaryRecharge = function () {
    const rc = this.activeJobSummary()?.recharge;
    return rc && typeof rc === "object" && rc.observed ? rc : null;
  };

  /** True when this run was captured from the vendor app rather than dispatched. */
  proto.jobSummaryIsExternal = function () {
    const job = this.activeJobSummary();
    return String(job?.origin ?? "").trim().toLowerCase() === "external";
  };
}
