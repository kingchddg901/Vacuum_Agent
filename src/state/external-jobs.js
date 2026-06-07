/**
 * ============================================================
 * STATE: EXTERNAL JOBS (review of app-started runs)
 * ============================================================
 *
 * Holds the "External Jobs" review subtab selection, the list of pending
 * external records (fetched via get_external_pending_runs), and the review
 * wizard: which run is open, the per-boundary split toggles (a confident
 * boundary defaults split; an uncertain one defaults merged), and the
 * per-segment assignment (room pick + edge-mop + setting overrides).
 *
 * Pure state — no rendering, no service calls. The card derives room groups
 * from the segments + split toggles; the actions layer submits them.
 * ============================================================
 */

export function applyExternalJobsState(proto) {

  /* --- review subtab (History | External Jobs) ----------------------- */

  proto.reviewSubtab = function () {
    return this._reviewSubtab === "external" ? "external" : "history";
  };

  proto.setReviewSubtab = function (value) {
    this._reviewSubtab = value === "external" ? "external" : "history";
  };

  /* --- pending list -------------------------------------------------- */

  proto.externalPendingRuns = function () {
    return Array.isArray(this._externalPending) ? this._externalPending : [];
  };

  proto.setExternalPendingRuns = function (list) {
    this._externalPending = Array.isArray(list) ? list : [];
  };

  /* --- wizard -------------------------------------------------------- */

  proto.isExternalWizardOpen = function () {
    return this._extWizard != null;
  };

  proto.externalWizard = function () {
    return this._extWizard || null;
  };

  proto.openExternalWizard = function (run) {
    const segments = Array.isArray(run?.segments) ? run.segments : [];
    const splits = {};
    const assignments = {};
    for (const seg of segments) {
      const order = Number(seg?.order ?? 0);
      if (order > 0) {
        // confident boundary -> split by default; uncertain -> merged (off).
        splits[order] = !!seg?.confident_boundary;
      }
      const top = Array.isArray(seg?.shortlist) && seg.shortlist[0] ? seg.shortlist[0] : null;
      assignments[order] = {
        room_id: top ? top.room_id : null,
        edge_mopping: false,
        override: false,
        overrides: {},
      };
    }
    this._extWizard = {
      pendingJobId: run?.pending_job_id || null,
      mapId: run?.map_id || null,
      segments,
      splits,
      assignments,
      step: 1,
      blocked: null,
      busy: false,
      error: null,
    };
  };

  proto.closeExternalWizard = function () {
    this._extWizard = null;
  };

  proto.setExternalWizardStep = function (step) {
    if (this._extWizard) this._extWizard.step = Number(step) || 1;
  };

  proto.toggleExternalSplit = function (order) {
    const w = this._extWizard;
    if (w && Object.prototype.hasOwnProperty.call(w.splits, order)) {
      w.splits[order] = !w.splits[order];
    }
  };

  proto.setExternalAssignment = function (order, patch) {
    const w = this._extWizard;
    if (!w) return;
    const current = w.assignments[order] || { overrides: {} };
    w.assignments[order] = { ...current, ...patch };
  };

  proto.setExternalAssignmentOverride = function (order, key, value) {
    const w = this._extWizard;
    if (!w) return;
    const current = w.assignments[order] || { overrides: {} };
    const overrides = { ...(current.overrides || {}), [key]: value };
    w.assignments[order] = { ...current, overrides };
  };

  proto.setExternalWizardBlocked = function (blocked) {
    if (this._extWizard) this._extWizard.blocked = Array.isArray(blocked) ? blocked : null;
  };

  proto.setExternalWizardBusy = function (busy) {
    if (this._extWizard) this._extWizard.busy = !!busy;
  };

  proto.setExternalWizardError = function (error) {
    if (this._extWizard) this._extWizard.error = error || null;
  };

  /**
   * Derive room groups from the segments + split toggles. A segment starts a
   * new group when it is order 0 or its boundary is split (on); otherwise it
   * merges into the previous group. Returns [{orders:[...], lead: segment}].
   */
  proto.externalWizardGroups = function () {
    const w = this._extWizard;
    if (!w) return [];
    const groups = [];
    for (const seg of w.segments) {
      const order = Number(seg?.order ?? 0);
      const startsGroup = order === 0 || w.splits[order];
      if (startsGroup || groups.length === 0) {
        groups.push({ orders: [order], lead: seg, segments: [seg] });
      } else {
        const g = groups[groups.length - 1];
        g.orders.push(order);
        g.segments.push(seg);
      }
    }
    return groups;
  };
}
