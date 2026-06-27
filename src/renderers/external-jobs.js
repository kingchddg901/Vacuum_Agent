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
    const extLabel = count > 0
      ? this.t("external_jobs.subtab_external_count", { count })
      : this.t("external_jobs.subtab_external");
    return `
      <div class="evcc-review-subtabs">
        <button class="evcc-review-subtab ${sub === "history" ? "is-active" : ""}"
                data-action="set-review-subtab" data-subtab="history">${this.t("external_jobs.subtab_history")}</button>
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
      const appPhrase = brand
        ? this.t("external_jobs.empty_app_branded", { brand: this.escapeHtml(brand) })
        : this.t("external_jobs.empty_app_generic");
      return `
        <div class="evcc-empty evcc-external-empty">
          ${this.t("external_jobs.empty", { appPhrase })}
        </div>
      `;
    }
    return `<div class="evcc-external-list">${runs.map((r) => this._renderExternalRunCard(r)).join("")}</div>`;
  };

  proto._renderExternalRunCard = function (run) {
    const segs = Array.isArray(run.segments) ? run.segments : [];
    const totalArea = segs.reduce((acc, s) => acc + (Number(s.area_m2) || 0), 0);
    const when = (this._formatReviewTimestamp && this._formatReviewTimestamp(run.detection_ts))
      || run.detection_ts || this.t("external_jobs.unknown_time");
    const rooms = run.suggested_room_count ?? segs.length;
    const roomsPhrase = this.t("external_jobs.card_rooms", { count: rooms });
    const segsPhrase = this.t("external_jobs.card_segments", { count: segs.length });
    const pid = this.escapeHtml(String(run.pending_job_id || ""));
    return `
      <div class="evcc-external-card">
        <div class="evcc-external-card-main">
          <div class="evcc-external-card-title">${this.escapeHtml(String(when))}</div>
          <div class="evcc-external-card-meta">
            ${roomsPhrase} · ${totalArea.toFixed(0)} m² ·
            ${segsPhrase}
          </div>
        </div>
        <div class="evcc-external-card-actions">
          <button class="evcc-btn evcc-btn-primary" data-action="open-external-wizard" data-pending-id="${pid}">${this.t("external_jobs.review")}</button>
          <button class="evcc-btn evcc-btn-ghost" data-action="discard-external-run" data-pending-id="${pid}">${this.t("external_jobs.discard")}</button>
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
            <div class="evcc-modal-title">${this.t("external_jobs.wizard_title")}</div>
            <div class="evcc-modal-subtitle">${this.t("external_jobs.wizard_step_of", {
              step: w.step,
              phase: w.step === 1 ? this.t("external_jobs.wizard_phase_count") : this.t("external_jobs.wizard_phase_name"),
            })}</div>
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
    return w.resegmentable
      ? this._renderExtWizardStep1V2(w)
      : this._renderExtWizardStep1Legacy(w, groups);
  };

  proto._segFacts = function (seg) {
    const settings = seg.settings || {};
    // The captured clean_mode is an adapter VOCAB value (vacuum / vacuum_mop /
    // mop) — localize it like the room editor does, not raw. tVocab escapes.
    const mode = settings.clean_mode
      ? this.tVocab("clean_mode", settings.clean_mode, String(settings.clean_mode))
      : this.t("external_jobs.clean_mode_unknown");
    return `${(Number(seg.area_m2) || 0).toFixed(0)} m² · `
      + `${Math.round((Number(seg.time_wall_s) || 0) / 60)} min · `
      + `${mode} · ${seg.pass_count || 1}×`;
  };

  // v2 (samples saved) — the count stepper + per-boundary split/merge re-segment
  // server-side. Buttons say what they DO (action-first): "Merge up" collapses a
  // room into the one above; "Split here" reopens a detected cut inside a room.
  proto._renderExtWizardStep1V2 = function (w) {
    const segments = w.segments || [];
    const count = segments.length;
    const candidates = Array.isArray(w.candidates) ? w.candidates : [];
    const maxRooms = candidates.length + 1;
    const busy = !!w.busy;

    const activeSet = new Set((w.activeBoundaries || []).map(Number));
    const inactive = candidates.filter((c) => !activeSet.has(Number(c.id)));
    // A segment owns the inactive cuts whose tick position falls inside its span
    // (start position .. the next room's start). Positions are stable integers.
    const starts = segments.map((s, i) => (i === 0 ? 0 : Number(s.boundary_id)));
    const nextStart = (i) => (i + 1 < segments.length ? starts[i + 1] : Infinity);

    const stepper = `
      <div class="evcc-ext-count">
        <span class="evcc-ext-count-label">${this.t("external_jobs.rooms_label")}</span>
        <div class="evcc-ext-stepper">
          <button class="evcc-btn evcc-ext-step" data-action="ext-count-dec" ${busy || count <= 1 ? "disabled" : ""}>−</button>
          <strong class="evcc-ext-count-n">${count}</strong>
          <button class="evcc-btn evcc-ext-step" data-action="ext-count-inc" ${busy || count >= maxRooms ? "disabled" : ""}>+</button>
        </div>
        <span class="evcc-ext-hint">${this.t("external_jobs.count_hint")}</span>
      </div>`;

    const rows = segments.map((seg, idx) => {
      const bid = seg.boundary_id;
      const head = idx === 0
        ? `<span class="evcc-ext-seg-start">${this.t("external_jobs.first_room")}</span>`
        : `<button class="evcc-ext-merge" data-action="ext-merge-up" data-boundary-id="${bid}" ${busy ? "disabled" : ""}>↥ ${this.t("external_jobs.merge_up")}</button>`;
      const within = inactive.filter(
        (c) => Number(c.id) > starts[idx] && Number(c.id) < nextStart(idx)
      );
      const splitBtns = within.map((c) => `
        <button class="evcc-ext-split-here" data-action="ext-split-here" data-boundary-id="${c.id}" ${busy ? "disabled" : ""}>
          ↳ ${c.confident ? this.t("external_jobs.split_here") : this.t("external_jobs.split_here_uncertain")}
        </button>`).join("");
      return `
        <div class="evcc-ext-seg is-v2">
          <div class="evcc-ext-seg-row">
            ${head}
            <span class="evcc-ext-seg-facts">${this.t("external_jobs.room_n", { n: idx + 1 })} · ${this._segFacts(seg)}</span>
          </div>
          ${splitBtns ? `<div class="evcc-ext-splits">${splitBtns}</div>` : ""}
        </div>`;
    }).join("");

    // Localize via the backend reason CODE (vocab.resegment_reason.*), falling
    // back to the backend English message, then the static key. tVocab escapes.
    const rm = w.resegmentMeta;
    const cap = rm && rm.capped
      ? `<div class="evcc-ext-blocked">${this.tVocab("resegment_reason", rm.reason, rm.message || this.t("external_jobs.capped_message"))}</div>`
      : "";

    return `${stepper}${cap}<div class="evcc-ext-seglist">${rows}</div>`;
  };

  // v1 (legacy, no samples) — client-side merge-only via the split toggles.
  proto._renderExtWizardStep1Legacy = function (w, groups) {
    const rows = (w.segments || []).map((seg) => {
      const order = Number(seg.order ?? 0);
      let head;
      if (order === 0) {
        head = `<div class="evcc-ext-seg-start">${this.t("external_jobs.first_room")}</div>`;
      } else {
        const split = !!w.splits[order];
        const confident = !!seg.confident_boundary;
        const splitLabel = split
          ? (confident ? this.t("external_jobs.split_label") : this.t("external_jobs.split_label_uncertain"))
          : (confident ? this.t("external_jobs.merged_label") : this.t("external_jobs.merged_label_uncertain"));
        head = `
          <button class="evcc-ext-split ${split ? "is-split" : "is-merged"}"
                  data-action="toggle-external-split" data-order="${order}">
            ${split ? "✂" : "↳"} ${splitLabel}
          </button>`;
      }
      return `<div class="evcc-ext-seg">${head}<div class="evcc-ext-seg-facts">${this.t("external_jobs.seg_n", { n: order })} · ${this._segFacts(seg)}</div></div>`;
    }).join("");
    return `
      <div class="evcc-ext-count">
        ${this.tRaw("external_jobs.detected_rooms", { count: groups.length })}
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
    const modeChips = [
      ["vacuum", this.t("external_jobs.mode_vacuum")],
      ["vacuum_mop", this.t("external_jobs.mode_vacuum_mop")],
      ["mop", this.t("external_jobs.mode_mop")],
    ].map(
      ([val, label]) => `<button class="evcc-chip ${modeCur === val ? "active" : ""}"
        data-action="ext-set-override" data-order="${order}" data-key="clean_mode" data-value="${val}">${label}</button>`
    ).join("");

    const passCur = Number(ov.clean_passes ?? lead.pass_count ?? 1);
    const passChips = [1, 2].map((p) => `<button class="evcc-chip ${passCur === p ? "active" : ""}"
      data-action="ext-set-override" data-order="${order}" data-key="clean_passes" data-value="${p}">${p}×</button>`).join("");

    // Settings capture is best-effort, so every setting is editable. Options come
    // from the adapter vocabulary (same source as the room editor); the captured
    // value is pre-selected. Water only applies to a mop mode.
    const isMop = modeCur === "mop" || modeCur === "vacuum_mop";
    const opt = (fn) => (typeof ctx.state[fn] === "function" ? ctx.state[fn]() : []);
    const suctionRow = this._extSettingRow(order, this.t("external_jobs.setting_suction"), "fan_speed",
      opt("suctionLevelOptions"), ov.fan_speed ?? settings.fan_speed);
    const intensityRow = this._extSettingRow(order, this.t("external_jobs.setting_cleaning_path"), "clean_intensity",
      opt("cleanIntensityOptions"), ov.clean_intensity ?? settings.clean_intensity);
    const waterRow = isMop
      ? this._extSettingRow(order, this.t("external_jobs.setting_water"), "water_level",
          opt("waterLevelOptions"), ov.water_level ?? settings.water_level)
      : "";

    return `
      <div class="evcc-ext-room">
        <div class="evcc-ext-room-head">${this.t("external_jobs.room_n", { n: idx + 1 })} · ${area.toFixed(0)} m²
          ${group.orders.length > 1 ? `· ${this.t("external_jobs.segments_merged", { count: group.orders.length })}` : ""}</div>
        <div class="evcc-editor-field-group">
          <div class="evcc-field-label">${this.t("external_jobs.which_room")}</div>
          <div class="evcc-chip-row">${roomChips}${this._extAllRoomsOptions(ctx, order, a.room_id)}</div>
        </div>
        <div class="evcc-editor-field-group">
          <div class="evcc-field-label">${this.t("external_jobs.mode")}</div>
          <div class="evcc-chip-row">${modeChips}</div>
        </div>
        <div class="evcc-editor-field-group">
          <div class="evcc-field-label">${this.t("external_jobs.passes")}</div>
          <div class="evcc-chip-row">${passChips}</div>
        </div>
        ${suctionRow}
        ${intensityRow}
        ${waterRow}
        <div class="evcc-editor-field-group evcc-ext-edge">
          <div class="evcc-field-label">${this.t("external_jobs.edge_mop")} <span class="evcc-ext-hint">${this.t("external_jobs.edge_mop_hint")}</span></div>
          <div class="evcc-chip-row">
            <button class="evcc-chip ${a.edge_mopping ? "active" : ""}"
              data-action="ext-set-edge" data-order="${order}" data-value="true">${this.t("common.on")}</button>
            <button class="evcc-chip ${!a.edge_mopping ? "active" : ""}"
              data-action="ext-set-edge" data-order="${order}" data-value="false">${this.t("common.off")}</button>
          </div>
        </div>
      </div>
    `;
  };

  proto._extSettingRow = function (order, label, key, options, current) {
    if (!Array.isArray(options) || !options.length) return "";
    const cur = String(current ?? "");
    const chips = options.map((o) => {
      const val = String(o.value ?? "");
      const active = cur && cur.toLowerCase() === val.toLowerCase() ? "active" : "";
      // key is the adapter vocab field (fan_speed / clean_intensity /
      // water_level) — localize the option label via tVocab like the room
      // editor, falling back to the backend label. tVocab escapes.
      return `<button class="evcc-chip ${active}"
        data-action="ext-set-override" data-order="${order}" data-key="${key}"
        data-value="${this.escapeHtml(val)}">${this.tVocab(key, o.value, String(o.label || val))}</button>`;
    }).join("");
    return `
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">${this.escapeHtml(label)}</div>
        <div class="evcc-chip-row">${chips}</div>
      </div>`;
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
        <option value="">${this.t("external_jobs.pick_another_room")}</option>${opts}
      </select>`;
  };

  proto._renderExtWizardFooter = function (w, groups) {
    const blocked = Array.isArray(w.blocked) ? w.blocked : [];
    const blockedText = this.t("external_jobs.blocked", { count: blocked.length });
    const blockedHtml = blocked.length
      ? `<div class="evcc-ext-blocked">⚠ ${blockedText}</div>`
      : "";
    let left;
    let right;
    if (w.step === 1) {
      left = `<button class="evcc-btn evcc-btn-ghost" data-action="close-external-wizard">${this.t("common.cancel")}</button>`;
      right = `<button class="evcc-btn evcc-btn-primary" data-action="ext-wizard-next">${this.t("external_jobs.next_name_rooms")} →</button>`;
    } else {
      left = `<button class="evcc-btn evcc-btn-ghost" data-action="ext-wizard-back">← ${this.t("external_jobs.back")}</button>`;
      right = `
        <button class="evcc-btn evcc-btn-primary" data-action="ext-wizard-confirm" ${w.busy ? "disabled" : ""}>
          ${w.busy ? this.t("common.saving") : this.t("external_jobs.confirm")}
        </button>
        ${blocked.length ? `<button class="evcc-btn evcc-btn-warn" data-action="ext-wizard-override">${this.t("external_jobs.keep_anyway")}</button>` : ""}`;
    }
    return `<div class="evcc-modal-footer">${blockedHtml}<div class="evcc-modal-footer-row">${left}${right}</div></div>`;
  };
}
