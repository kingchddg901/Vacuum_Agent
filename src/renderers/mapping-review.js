/**
 * ============================================================
 * RENDERERS: MAPPING REVIEW
 * ============================================================
 *
 * Renders the Mapping Bounds Review view — per-room accumulated
 * bounds derived from job history, with outlier exclusion controls.
 *
 * ============================================================
 */

import { badgeMark } from "./badge-marks.js";

/**
 * Leave-one-out bounds-outlier detection for a single job run.
 *
 * Builds the union bbox of all OTHER non-excluded runs (the baseline), derives a
 * per-axis 10% tolerance from that baseline's span, and flags the target run on each
 * of the four sides when it exceeds the baseline edge by more than the tolerance.
 *
 * Pure/deterministic: no i18n, no DOM. The renderer maps the returned side flags to
 * this.t() labels. With no other active runs there is no baseline, so nothing is flagged
 * (this also protects the very first / only run, which has nothing to compare against).
 *
 * @param {{min_x:number,max_x:number,min_y:number,max_y:number,excluded?:boolean}} job
 *   The run under test.
 * @param {Array<{min_x:number,max_x:number,min_y:number,max_y:number,excluded?:boolean}>} otherRuns
 *   The OTHER runs (already leave-one-out filtered by the caller); excluded ones are ignored here.
 * @returns {{ max_x:boolean, min_x:boolean, max_y:boolean, min_y:boolean, isOutlier:boolean }}
 *   Per-side outlier flags plus a convenience isOutlier = any side flagged.
 */
export function computeJobBoundsOutlier(job, otherRuns) {
  const flags = { max_x: false, min_x: false, max_y: false, min_y: false, isOutlier: false };
  if (job?.excluded) return flags;

  const others = (otherRuns ?? []).filter(e => !e.excluded);
  if (others.length === 0) return flags;

  const ob = {
    min_x: Math.min(...others.map(e => e.min_x)),
    max_x: Math.max(...others.map(e => e.max_x)),
    min_y: Math.min(...others.map(e => e.min_y)),
    max_y: Math.max(...others.map(e => e.max_y)),
  };
  const tX = (ob.max_x - ob.min_x) * 0.10;
  const tY = (ob.max_y - ob.min_y) * 0.10;

  flags.max_x = job.max_x > ob.max_x + tX;
  flags.min_x = job.min_x < ob.min_x - tX;
  flags.max_y = job.max_y > ob.max_y + tY;
  flags.min_y = job.min_y < ob.min_y - tY;
  flags.isOutlier = flags.max_x || flags.min_x || flags.max_y || flags.min_y;
  return flags;
}

/**
 * Mix mapping bounds review renderer methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applyMappingReviewRenderers(proto) {

  /**
   * Render the Mapping Bounds Review view.
   * Returns a loading or unavailable placeholder when data is absent.
   *
   * @param {{ state: object }} ctx - Render context.
   * @returns {string} HTML string.
   */
  proto.renderMappingReviewView = function (ctx) {
    const { state } = ctx;
    const snapshot = state.mappingBoundsSnapshot?.();

    if (!snapshot) {
      return `<div class="evcc-empty">${this.t("mapping_review.loading")}</div>`;
    }

    if (snapshot.available === false) {
      return `
        <div class="evcc-mrev-view">
          <div class="evcc-empty">${this.escapeHtml(snapshot.message) || this.t("mapping_review.unavailable")}</div>
        </div>`;
    }

    const rooms = snapshot.rooms ?? {};

    const filter     = state.mappingBoundsFilter?.() ?? "all";
    const filterOpts = state.mappingBoundsFilterOptions?.() ?? [];

    const allRoomIds = Object.keys(rooms);
    const withBounds = allRoomIds.filter(id => rooms[id]?.bounds);
    const noBounds   = allRoomIds.filter(id => !rooms[id]?.bounds);
    const totalJobs  = allRoomIds.reduce((n, id) => n + (rooms[id]?.job_bounds_history?.length ?? 0), 0);

    const visibleIds = allRoomIds.filter(id => {
      if (filter === "has_bounds") return !!rooms[id]?.bounds;
      if (filter === "no_bounds")  return !rooms[id]?.bounds;
      return true;
    });

    const sorted = [...visibleIds].sort((a, b) => {
      const aHas = !!rooms[a]?.bounds;
      const bHas = !!rooms[b]?.bounds;
      if (aHas !== bHas) return aHas ? -1 : 1;
      return Number(a) - Number(b);
    });

    return `
      <div class="evcc-mrev-view">

        <section class="evcc-review-panel">
          <div class="evcc-review-panel-header">
            <div>
              <div class="evcc-review-panel-title">${this.t("mapping_review.title")}</div>
              <div class="evcc-review-panel-subtitle">
                ${this.t("mapping_review.subtitle")}
              </div>
            </div>
          </div>
          <div class="evcc-review-stats">
            ${this._renderReviewStat(this.t("mapping_review.stat_rooms"), allRoomIds.length)}
            ${this._renderReviewStat(this.t("mapping_review.stat_with_bounds"), withBounds.length)}
            ${this._renderReviewStat(this.t("mapping_review.stat_no_bounds"), noBounds.length)}
            ${this._renderReviewStat(this.t("mapping_review.stat_total_runs"), totalJobs)}
          </div>
        </section>

        <section class="evcc-review-panel evcc-review-panel--wide">
          <div class="evcc-review-chip-filter">
            <div class="evcc-mrev-filter-label">${this.t("mapping_review.filter")}</div>
            <div class="evcc-chips evcc-review-filter-chips">
              ${filterOpts.map(opt => `
                <button class="evcc-chip ${filter === opt.value ? "active" : ""}"
                        data-mrev-filter="${this.escapeHtml(opt.value)}">
                  ${opt.value === "has_bounds" ? this.t("mapping_review.filter_has_bounds")
                    : opt.value === "no_bounds" ? this.t("mapping_review.filter_no_bounds")
                    : this.t("mapping_review.filter_all_rooms")}
                </button>
              `).join("")}
            </div>
          </div>
        </section>

        <div class="evcc-mrev-grid">
          ${sorted.map(roomId =>
            this._renderMappingRoomCard(roomId, rooms[roomId], state)
          ).join("")}
        </div>

      </div>
    `;
  };

  proto._renderMappingRoomCard = function (roomId, roomEntry, state) {
    const name       = roomEntry?.name ?? this.t("mapping_review.room_fallback", { id: roomId });
    const bounds     = roomEntry?.bounds ?? null;
    const history    = roomEntry?.job_bounds_history ?? [];
    const hasArchive = !!roomEntry?.has_archive;
    const pending    = state.isMappingBoundsClearPending?.(roomId);
    const rebuildPending = state.isMappingRebuildPending?.(roomId);

    const activeCount   = history.filter(e => !e.excluded).length;
    const excludedCount = history.filter(e => e.excluded).length;
    const CONFIDENCE_MIN_RUNS = 4;
    const isConfident   = activeCount >= CONFIDENCE_MIN_RUNS;

    const statusBadge = bounds
      ? isConfident
        ? `<span class="evcc-mrev-badge evcc-mrev-badge--ok">${badgeMark("ok")}${this.t("mapping_review.badge_runs_samples", { runs: activeCount, samples: bounds.sample_count ?? 0 })}</span>`
        : `<span class="evcc-mrev-badge evcc-mrev-badge--likely">${badgeMark("likely")}${this.t("mapping_review.badge_runs_likely", { runs: activeCount, count: activeCount })}</span>`
      : `<span class="evcc-mrev-badge evcc-mrev-badge--warn">${badgeMark("warn")}${this.t("mapping_review.badge_no_bounds")}</span>`;

    return `
      <div class="evcc-mrev-card">
        <div class="evcc-mrev-card-header">
          <div class="evcc-mrev-room-name">${this.escapeHtml(name)}</div>
          <div class="evcc-mrev-room-meta">
            <span class="evcc-mrev-room-id">${this.t("mapping_review.room_id", { id: this.escapeHtml(roomId) })}</span>
            ${statusBadge}
            ${excludedCount > 0
              ? `<span class="evcc-mrev-badge evcc-mrev-badge--excluded">${badgeMark("excluded")}${this.t("mapping_review.badge_n_excluded", { count: excludedCount })}</span>`
              : ""}
          </div>
        </div>

        ${bounds
          ? `<div class="evcc-mrev-bounds-block">
               ${this._renderBoundsTable(bounds)}
             </div>`
          : hasArchive
            ? `<div class="evcc-mrev-no-bounds">${this.t("mapping_review.no_active_bounds_archive")}</div>`
            : `<div class="evcc-mrev-no-bounds">${this.t("mapping_review.run_solo")}</div>`
        }

        ${history.length > 0 ? `
          <div class="evcc-mrev-history">
            <div class="evcc-mrev-history-label">${this.t("mapping_review.run_history", { count: history.length })}</div>
            ${history.map((entry, idx) =>
              this._renderJobBoundsEntry(entry, idx, roomId, bounds, history, state)
            ).join("")}
          </div>` : ""}

        <div class="evcc-mrev-card-footer">
          ${!bounds && hasArchive ? `
            <button class="evcc-chip evcc-mrev-rebuild-btn ${rebuildPending ? "evcc-mrev-clear-btn--disabled" : ""}"
                    data-mrev-rebuild="${this.escapeHtml(roomId)}"
                    ${rebuildPending ? "disabled" : ""}>
              ${rebuildPending ? this.t("mapping_review.rebuilding") : this.t("mapping_review.rebuild_from_archive")}
            </button>` : ""}
          <button class="evcc-chip evcc-mrev-clear-btn ${!bounds || pending ? "evcc-mrev-clear-btn--disabled" : ""}"
                  data-mrev-clear="${this.escapeHtml(roomId)}"
                  ${!bounds || pending ? "disabled" : ""}>
            ${pending ? this.t("mapping_review.clearing") : this.t("mapping_review.clear_all")}
          </button>
        </div>
      </div>
    `;
  };

  proto._renderBoundsTable = function (bounds) {
    const w   = Math.round(bounds.max_x - bounds.min_x);
    const h   = Math.round(bounds.max_y - bounds.min_y);
    const fmt = v => Math.round(v).toLocaleString();
    return `
      <div class="evcc-mrev-bounds-grid">
        <div class="evcc-mrev-bounds-row">
          <span class="evcc-mrev-bounds-key">X</span>
          <span class="evcc-mrev-bounds-val">${fmt(bounds.min_x)} – ${fmt(bounds.max_x)}</span>
          <span class="evcc-mrev-bounds-dim">${this.t("mapping_review.dim_width", { value: fmt(w) })}</span>
        </div>
        <div class="evcc-mrev-bounds-row">
          <span class="evcc-mrev-bounds-key">Y</span>
          <span class="evcc-mrev-bounds-val">${fmt(bounds.min_y)} – ${fmt(bounds.max_y)}</span>
          <span class="evcc-mrev-bounds-dim">${this.t("mapping_review.dim_height", { value: fmt(h) })}</span>
        </div>
        ${bounds.updated_at ? `
        <div class="evcc-mrev-bounds-row evcc-mrev-bounds-row--sub">
          <span class="evcc-mrev-bounds-key">${this.t("mapping_review.updated")}</span>
          <span class="evcc-mrev-bounds-val">${this._mrevFmtDate(bounds.updated_at)}</span>
          <span class="evcc-mrev-bounds-dim"></span>
        </div>` : ""}
      </div>
    `;
  };

  proto._renderJobBoundsEntry = function (job, jobIndex, roomId, accBounds, history, state) {
    const fmt        = v => Math.round(v).toLocaleString();
    const isExcluded = !!job.excluded;
    const isPending  = state.isMappingJobActionPending?.(roomId, jobIndex);

    // Leave-one-out outlier detection: compare this run against the union of all
    // other active runs. No other active runs → no baseline → skip detection.
    // This also protects the first job, which has nothing to compare against.
    // Pure computation lives in computeJobBoundsOutlier(); labels are mapped here.
    const others = isExcluded ? [] : history.filter((e, i) => i !== jobIndex && !e.excluded);
    const sides  = computeJobBoundsOutlier(isExcluded ? { ...job, excluded: true } : job, others);
    const outlierFlags = [];
    if (sides.max_x) outlierFlags.push(this.t("mapping_review.outlier_max_x"));
    if (sides.min_x) outlierFlags.push(this.t("mapping_review.outlier_min_x"));
    if (sides.max_y) outlierFlags.push(this.t("mapping_review.outlier_max_y"));
    if (sides.min_y) outlierFlags.push(this.t("mapping_review.outlier_min_y"));

    // outlierFlags are this.t() results — already HTML-escaped by trust model B,
    // and first-party catalog strings with no user data — so they interpolate into
    // outlier_label raw; re-escaping here would double-encode a translated value.
    const isOutlier = outlierFlags.length > 0;
    const jobLabel  = this._mrevFmtJobId(job.job_id);
    const dateLabel = job.recorded_at ? this._mrevFmtDate(job.recorded_at) : "";

    // The oldest entry (last in newest-first array) is the baseline and is always protected.
    const isBaseline  = jobIndex === history.length - 1;
    const activeCount = history.filter(e => !e.excluded).length;
    const canExclude  = !isExcluded && !isPending && !isBaseline && activeCount > 1;
    const canRestore  = isExcluded  && !isPending && !isBaseline;

    return `
      <div class="evcc-mrev-job-entry ${isExcluded ? "evcc-mrev-job-entry--excluded" : ""} ${isOutlier ? "evcc-mrev-job-entry--outlier" : ""}">
        <div class="evcc-mrev-job-header">
          <span class="evcc-mrev-job-id ${isExcluded ? "evcc-mrev-job-id--excluded" : ""}">${this.escapeHtml(jobLabel)}</span>
          ${dateLabel ? `<span class="evcc-mrev-job-date">${this.escapeHtml(dateLabel)}</span>` : ""}
          ${isExcluded
            ? `<span class="evcc-mrev-badge evcc-mrev-badge--excluded">${badgeMark("excluded")}${this.t("mapping_review.excluded")}</span>`
            : isOutlier
              ? `<span class="evcc-mrev-badge evcc-mrev-badge--outlier">${badgeMark("outlier")}${this.t("mapping_review.outlier_label", { flags: outlierFlags.join(", ") })}</span>`
              : `<span class="evcc-mrev-badge evcc-mrev-badge--ok">${badgeMark("ok")}${this.t("mapping_review.ok")}</span>`}
          ${isBaseline ? `<span class="evcc-mrev-badge evcc-mrev-badge--baseline">${badgeMark("baseline")}${this.t("mapping_review.baseline")}</span>` : ""}
          <div class="evcc-mrev-job-actions">
            ${canExclude ? `
              <button class="evcc-chip evcc-chip--sm evcc-mrev-job-action-btn"
                      data-mrev-job-action="exclude"
                      data-mrev-room-id="${this.escapeHtml(roomId)}"
                      data-mrev-job-index="${jobIndex}">
                ${this.t("mapping_review.exclude")}
              </button>` : ""}
            ${canRestore ? `
              <button class="evcc-chip evcc-chip--sm evcc-mrev-job-action-btn"
                      data-mrev-job-action="restore"
                      data-mrev-room-id="${this.escapeHtml(roomId)}"
                      data-mrev-job-index="${jobIndex}">
                ${this.t("mapping_review.restore")}
              </button>` : ""}
            ${isPending ? `<span class="evcc-mrev-job-pending">…</span>` : ""}
          </div>
        </div>
        <div class="evcc-mrev-bounds-grid evcc-mrev-bounds-grid--compact ${isExcluded ? "evcc-mrev-bounds-grid--muted" : ""}">
          <div class="evcc-mrev-bounds-row">
            <span class="evcc-mrev-bounds-key">X</span>
            <span class="evcc-mrev-bounds-val">${fmt(job.min_x)} – ${fmt(job.max_x)}</span>
            <span class="evcc-mrev-bounds-dim">${this.t("mapping_review.dim_width", { value: fmt(job.max_x - job.min_x) })}</span>
          </div>
          <div class="evcc-mrev-bounds-row">
            <span class="evcc-mrev-bounds-key">Y</span>
            <span class="evcc-mrev-bounds-val">${fmt(job.min_y)} – ${fmt(job.max_y)}</span>
            <span class="evcc-mrev-bounds-dim">${this.t("mapping_review.dim_height", { value: fmt(job.max_y - job.min_y) })}</span>
          </div>
          <div class="evcc-mrev-bounds-row evcc-mrev-bounds-row--sub">
            <span class="evcc-mrev-bounds-key">${this.t("mapping_review.samples")}</span>
            <span class="evcc-mrev-bounds-val">${job.sample_count ?? "—"}</span>
            <span class="evcc-mrev-bounds-dim"></span>
          </div>
        </div>
      </div>
    `;
  };

  proto._mrevFmtJobId = function (jobId) {
    if (!jobId) return this.t("mapping_review.job_unknown");
    if (jobId === "pre_migration") return this.t("mapping_review.job_pre_migration");
    const m = String(jobId).match(/job_(\d{4}-\d{2}-\d{2})T(\d{2}-\d{2})/);
    return m ? `${m[1]} ${m[2].replace("-", ":")}` : String(jobId).slice(-16);
  };

  proto._mrevFmtDate = function (iso) {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleString(undefined, {
        month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
      });
    } catch {
      return String(iso).slice(0, 16);
    }
  };
}
