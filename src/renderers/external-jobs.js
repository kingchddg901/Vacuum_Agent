/**
 * ============================================================
 * RENDERERS: EXTERNAL JOBS (review of app-started runs)
 * ============================================================
 *
 * The "External Jobs" subtab of the Learning Review view (list of pending
 * app-started runs) + a two-step review wizard modal:
 *   Step 1 — confirm the room count (split/merge the uncertain cuts)
 *   Step 2 — name each room (shortlist pick + correct settings + edge-mop)
 *
 * Reuses the shared modal + chip/field classes from the room editor. The
 * subtab strip is rendered here and reused by the Learning Review renderer.
 * ============================================================
 */

export function applyExternalJobsRenderers(proto) {

  /* --- subtab strip (shared with the history view) ------------------- */

  proto._renderReviewSubtabStrip = function (state) {
    const sub = state.reviewSubtab();
    const count = state.externalPendingRuns().length;
    const extLabel = count > 0 ? `External Jobs (${count})` : "External Jobs";
    return `
      <div class="evcc-review-subtabs">
        <button class="evcc-review-subtab ${sub === "history" ? "is-active" : ""}"
                data-action="set-review-subtab" data-subtab="history">Learning History</button>
        <button class="evcc-review-subtab ${sub === "external" ? "is-active" : ""}"
                data-action="set-review-subtab" data-subtab="external">${extLabel}</button>
      </div>
    `;
  };

  /* --- the subtab body (pending run list) ---------------------------- */

  proto.renderExternalJobsSubtab = function (ctx) {
    const { state } = ctx;
    const runs = state.externalPendingRuns();
    if (!runs.length) {
      const brand = state.externalBrand?.();
      const appPhrase = brand ? `the ${this.escapeHtml(brand)} app` : "your robot's app";
      return `
        <div class="evcc-empty evcc-external-empty">
          No app-started runs awaiting review. Start a clean from ${appPhrase} and the
          run will appear here to confirm which rooms it cleaned.
        </div>
      `;
    }
    return `<div class="evcc-external-list">${runs.map((r) => this._renderExternalRunCard(r)).join("")}</div>`;
  };

  proto._renderExternalRunCard = function (run) {
    const segs = Array.isArray(run.segments) ? run.segments : [];
    const totalArea = segs.reduce((acc, s) => acc + (Number(s.area_m2) || 0), 0);
    const when = (this._formatReviewTimestamp && this._formatReviewTimestamp(run.detection_ts))
      || run.detection_ts || "Unknown time";
    const rooms = run.suggested_room_count ?? segs.length;
    const pid = this.escapeHtml(String(run.pending_job_id || ""));
    return `
      <div class="evcc-external-card">
        <div class="evcc-external-card-main">
          <div class="evcc-external-card-title">${this.escapeHtml(String(when))}</div>
          <div class="evcc-external-card-meta">
            ~${rooms} room${rooms === 1 ? "" : "s"} · ${totalArea.toFixed(0)} m² ·
            ${segs.length} segment${segs.length === 1 ? "" : "s"}
          </div>
        </div>
        <div class="evcc-external-card-actions">
          <button class="evcc-btn evcc-btn-primary" data-action="open-external-wizard" data-pending-id="${pid}">Review</button>
          <button class="evcc-btn evcc-btn-ghost" data-action="discard-external-run" data-pending-id="${pid}">Discard</button>
        </div>
      </div>
    `;
  };

  /* --- the wizard modal --------------------------------------------- */

  proto.renderExternalWizardModal = function (ctx) {
    const { state } = ctx;
    if (!state.isExternalWizardOpen()) return "";
    const w = state.externalWizard();
    const groups = state.externalWizardGroups();
    const body = w.step === 1
      ? this._renderExtWizardStep1(w, groups)
      : this._renderExtWizardStep2(ctx, w, groups);
    return `
      <div class="evcc-modal-backdrop" data-action="close-external-wizard">
        <div class="evcc-modal evcc-external-wizard-modal" data-stop-propagation>
          <div class="evcc-modal-header">
            <div class="evcc-modal-title">Review app-started run</div>
            <div class="evcc-modal-subtitle">Step ${w.step} of 2 — ${w.step === 1 ? "how many rooms?" : "name each room"}</div>
          </div>
          <div class="evcc-modal-body">
            ${w.error ? `<div class="evcc-external-error">${this.escapeHtml(String(w.error))}</div>` : ""}
            ${body}
          </div>
          ${this._renderExtWizardFooter(w, groups)}
        </div>
      </div>
    `;
  };

  proto._renderExtWizardStep1 = function (w, groups) {
    const rows = (w.segments || []).map((seg) => {
      const order = Number(seg.order ?? 0);
      const settings = seg.settings || {};
      const facts = `seg ${order} · ${(Number(seg.area_m2) || 0).toFixed(0)} m² · `
        + `${Math.round((Number(seg.time_wall_s) || 0) / 60)} min · `
        + `${this.escapeHtml(String(settings.clean_mode || "?"))} · ${seg.pass_count || 1}×`;
      let head;
      if (order === 0) {
        head = `<div class="evcc-ext-seg-start">First room</div>`;
      } else {
        const split = !!w.splits[order];
        const confident = !!seg.confident_boundary;
        head = `
          <button class="evcc-ext-split ${split ? "is-split" : "is-merged"}"
                  data-action="toggle-external-split" data-order="${order}">
            ${split ? "✂ split here" : "↳ merged"}${confident ? "" : " · uncertain"}
          </button>`;
      }
      return `<div class="evcc-ext-seg">${head}<div class="evcc-ext-seg-facts">${facts}</div></div>`;
    }).join("");
    return `
      <div class="evcc-ext-count">
        Detected <strong>${groups.length}</strong> room${groups.length === 1 ? "" : "s"}.
        Merge any over-split before continuing.
      </div>
      <div class="evcc-ext-seglist">${rows}</div>
    `;
  };

  proto._renderExtWizardStep2 = function (ctx, w, groups) {
    return groups.map((g, idx) => this._renderExtRoomPanel(ctx, w, g, idx)).join("");
  };

  proto._renderExtRoomPanel = function (ctx, w, group, idx) {
    const lead = group.lead || {};
    const order = Number(lead.order ?? 0);
    const a = w.assignments[order] || { overrides: {} };
    const area = (group.segments || []).reduce((s, seg) => s + (Number(seg.area_m2) || 0), 0);
    const settings = lead.settings || {};
    const ov = a.overrides || {};

    const shortlist = Array.isArray(lead.shortlist) ? lead.shortlist : [];
    const roomChips = shortlist.map((r) => `
      <button class="evcc-chip ${a.room_id === r.room_id ? "active" : ""}"
              data-action="ext-pick-room" data-order="${order}" data-room-id="${r.room_id}">
        ${this.escapeHtml(String(r.name || r.slug || r.room_id))}${r.learned_area_m2 ? ` · ${Number(r.learned_area_m2).toFixed(0)} m²` : ""}
      </button>`).join("");

    const modeCur = ov.clean_mode ?? settings.clean_mode;
    const modeChips = [["vacuum", "Vacuum"], ["vacuum_mop", "Vac & Mop"], ["mop", "Mop"]].map(
      ([val, label]) => `<button class="evcc-chip ${modeCur === val ? "active" : ""}"
        data-action="ext-set-override" data-order="${order}" data-key="clean_mode" data-value="${val}">${label}</button>`
    ).join("");

    const passCur = Number(ov.clean_passes ?? lead.pass_count ?? 1);
    const passChips = [1, 2].map((p) => `<button class="evcc-chip ${passCur === p ? "active" : ""}"
      data-action="ext-set-override" data-order="${order}" data-key="clean_passes" data-value="${p}">${p}×</button>`).join("");

    const detected = [];
    if (settings.fan_speed) detected.push(`Suction ${this.escapeHtml(String(settings.fan_speed))}`);
    if (settings.water_level) detected.push(`Water ${this.escapeHtml(String(settings.water_level))}`);
    if (settings.clean_intensity) detected.push(`Intensity ${this.escapeHtml(String(settings.clean_intensity))}`);

    return `
      <div class="evcc-ext-room">
        <div class="evcc-ext-room-head">Room ${idx + 1} · ${area.toFixed(0)} m²
          ${group.orders.length > 1 ? `· ${group.orders.length} segments merged` : ""}</div>
        <div class="evcc-editor-field-group">
          <div class="evcc-field-label">Which room?</div>
          <div class="evcc-chip-row">${roomChips}${this._extAllRoomsOptions(ctx, order, a.room_id)}</div>
        </div>
        <div class="evcc-editor-field-group">
          <div class="evcc-field-label">Mode</div>
          <div class="evcc-chip-row">${modeChips}</div>
        </div>
        <div class="evcc-editor-field-group">
          <div class="evcc-field-label">Passes</div>
          <div class="evcc-chip-row">${passChips}</div>
        </div>
        <div class="evcc-editor-field-group evcc-ext-edge">
          <div class="evcc-field-label">Edge mop? <span class="evcc-ext-hint">not detected — please set</span></div>
          <div class="evcc-chip-row">
            <button class="evcc-chip ${a.edge_mopping ? "active" : ""}"
              data-action="ext-set-edge" data-order="${order}" data-value="true">On</button>
            <button class="evcc-chip ${!a.edge_mopping ? "active" : ""}"
              data-action="ext-set-edge" data-order="${order}" data-value="false">Off</button>
          </div>
        </div>
        ${detected.length ? `<div class="evcc-ext-detected">Detected: ${detected.join(" · ")}</div>` : ""}
      </div>
    `;
  };

  proto._extAllRoomsOptions = function (ctx, order, selectedId) {
    // Full room list (every room on the run's map), attached to the pending
    // record by get_external_pending_runs. This is the fallback when the right
    // room isn't in the top-3 shortlist — without it the user is stuck.
    const w = ctx.state.externalWizard?.();
    const rooms = Array.isArray(w?.rooms) ? w.rooms : [];
    if (!rooms.length) return "";
    const opts = rooms.map((r) => {
      const id = r.room_id ?? r.id;
      const name = r.name || r.slug || id;
      const sel = String(id) === String(selectedId) ? "selected" : "";
      return `<option value="${id}" ${sel}>${this.escapeHtml(String(name))}</option>`;
    }).join("");
    return `
      <select class="evcc-ext-allrooms" data-action="ext-pick-room-select" data-order="${order}">
        <option value="">… pick another room</option>${opts}
      </select>`;
  };

  proto._renderExtWizardFooter = function (w, groups) {
    const blocked = Array.isArray(w.blocked) ? w.blocked : [];
    const blockedHtml = blocked.length
      ? `<div class="evcc-ext-blocked">⚠ ${blocked.length} room${blocked.length === 1 ? "" : "s"} don't match the picked area — re-pick, or keep anyway.</div>`
      : "";
    let left;
    let right;
    if (w.step === 1) {
      left = `<button class="evcc-btn evcc-btn-ghost" data-action="close-external-wizard">Cancel</button>`;
      right = `<button class="evcc-btn evcc-btn-primary" data-action="ext-wizard-next">Next: name rooms →</button>`;
    } else {
      left = `<button class="evcc-btn evcc-btn-ghost" data-action="ext-wizard-back">← Back</button>`;
      right = `
        <button class="evcc-btn evcc-btn-primary" data-action="ext-wizard-confirm" ${w.busy ? "disabled" : ""}>
          ${w.busy ? "Saving…" : "Confirm"}
        </button>
        ${blocked.length ? `<button class="evcc-btn evcc-btn-warn" data-action="ext-wizard-override">Keep anyway</button>` : ""}`;
    }
    return `<div class="evcc-modal-footer">${blockedHtml}<div class="evcc-modal-footer-row">${left}${right}</div></div>`;
  };
}
