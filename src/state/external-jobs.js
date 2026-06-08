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

  /* --- adapter-provided brand (for card copy) ------------------------ */

  proto.externalBrand = function () {
    return typeof this._externalBrand === "string" && this._externalBrand
      ? this._externalBrand
      : null;
  };

  proto.setExternalBrand = function (brand) {
    this._externalBrand =
      typeof brand === "string" && brand.trim() ? brand.trim() : null;
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
      rooms: Array.isArray(run?.rooms) ? run.rooms : [],
      // v2: the server owns segmentation. `candidates` is the full boundary menu;
      // `activeBoundaries` are the cuts currently producing `segments`. The count
      // stepper / split-here / merge-up call resegment_external_run and replace
      // these (applyResegmentResult). v1 records (no samples) fall back to the
      // legacy client-side `splits` grouping (merge-only).
      candidates: Array.isArray(run?.candidates) ? run.candidates : [],
      activeBoundaries: Array.isArray(run?.active_boundaries) ? run.active_boundaries.map(Number) : [],
      resegmentable: !!run?.resegmentable,
      suggestedRoomCount: Number(run?.suggested_room_count ?? segments.length) || segments.length,
      resegmentMeta: null,
      step: 1,
      blocked: null,
      busy: false,
      error: null,
    };
  };

  /**
   * Replace the wizard's segmentation with a server re-segment result (the count
   * stepper / split-here / merge-up). The boundary set changed, so room
   * assignments are rebuilt from the new segments' shortlists (room picks happen
   * in step 2, after the boundaries are settled in step 1).
   */
  proto.applyResegmentResult = function (record) {
    const w = this._extWizard;
    if (!w || !record) return;
    const segments = Array.isArray(record.segments) ? record.segments : [];
    const assignments = {};
    for (const seg of segments) {
      const order = Number(seg?.order ?? 0);
      const top = Array.isArray(seg?.shortlist) && seg.shortlist[0] ? seg.shortlist[0] : null;
      assignments[order] = { room_id: top ? top.room_id : null, edge_mopping: false, override: false, overrides: {} };
    }
    w.segments = segments;
    w.assignments = assignments;
    if (Array.isArray(record.candidates)) w.candidates = record.candidates;
    w.activeBoundaries = Array.isArray(record.active_boundaries) ? record.active_boundaries.map(Number) : [];
    if (record.suggested_room_count != null) w.suggestedRoomCount = Number(record.suggested_room_count);
    w.resegmentMeta = (record.capped || record.message)
      ? { capped: !!record.capped, capped_at: record.capped_at, message: record.message || null }
      : null;
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
    if (w.resegmentable) {
      // v2: the server already produced the room-level segmentation — one segment
      // per room (the split/merge happened server-side). No client grouping.
      return (w.segments || []).map((seg) => ({
        orders: [Number(seg?.order ?? 0)], lead: seg, segments: [seg],
      }));
    }
    // v1 (legacy, no samples): client-side merge grouping via the split toggles.
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
