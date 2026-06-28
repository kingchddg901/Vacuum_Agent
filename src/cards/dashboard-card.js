// Vacuum Agent — Dashboard Mode: a compact, embeddable multi-room control card.
//
// Drop it on a dashboard (next to the lights) to pick rooms + per-room settings,
// run a saved profile or a vendor-app scene, and start / dock — without opening
// the full sidebar panel. Sibling to the single-room eufy-room-card; both share
// the helpers in ./_shared.js. The run-launcher logic is the pure, unit-tested
// module ./dashboard-dispatch.js — this element only renders + executes its plan.
//
// CONTRACT: arm-only. Toggling rooms / picking a profile or scene mutates card
// LOCAL state only; nothing reaches the vacuum until Start. (Load-bearing for the
// Eufy scene, where select_option IS the run.) Exactly one run SOURCE is ever
// armed — see dashboard-dispatch.nextArmed.

import {
  translate, resolveLang, ensureLocalesLoaded,
  esc, vocab, roomSwitchesFor, adapterOptions, committedRoomFields, isMopMode,
  chipRow, callResponse, registerCard,
} from "./_shared.js";
import { emptyArmed, nextArmed, roomsDisabled, planStart, armedIsValid } from "./dashboard-dispatch.js";

const CARD_NAME   = "vacuum-agent-dashboard";
const CARD_EDITOR = "vacuum-agent-dashboard-editor";
const DOMAIN      = "eufy_vacuum";

/* ================================================================
   EDITOR
   ================================================================ */

class EufyDashboardCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = {};
  }

  setConfig(config) { this._config = config ?? {}; this._render(); }

  set hass(hass) {
    this._hass = hass;
    ensureLocalesLoaded(() => this._render());
    this._render();
  }

  t(key, vars) { return translate(resolveLang(this._hass, this._config), key, vars); }

  _vacuumEntities() {
    if (!this._hass) return [];
    return Object.keys(this._hass.states).filter((id) => id.startsWith("vacuum.")).sort();
  }

  _fire(config) {
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
  }

  _render() {
    const vacuums = this._vacuumEntities();
    const selected = this._config.vacuum_entity_id ?? "";
    const bool = (k, dflt) => (this._config[k] ?? dflt) !== false;

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; font-family: var(--paper-font-body1_-_font-family, sans-serif); }
        .field { display: flex; flex-direction: column; gap: 4px; margin-bottom: 16px; }
        label { font-size: 0.80rem; font-weight: 500; color: var(--secondary-text-color, #888); text-transform: uppercase; letter-spacing: 0.04em; }
        select, input[type=text] {
          width: 100%; box-sizing: border-box; padding: 8px 10px;
          border: 1px solid var(--divider-color, rgba(255,255,255,0.12)); border-radius: 6px;
          background: var(--card-background-color, #1c2127); color: var(--primary-text-color, #f0f2f5);
          font-size: 0.92rem; appearance: none; -webkit-appearance: none;
        }
        .toggles { display: flex; flex-direction: column; gap: 10px; }
        .toggle { display: flex; align-items: center; gap: 8px; font-size: 0.9rem; color: var(--primary-text-color, #f0f2f5); }
        .hint { font-size: 0.75rem; color: var(--secondary-text-color, #888); margin-top: 2px; }
      </style>

      <div class="field">
        <label>${this.t("room_card.editor_vacuum_label")}</label>
        <select id="vacuum">
          <option value="" disabled ${!selected ? "selected" : ""}>${this.t("room_card.editor_pick_vacuum")}</option>
          ${vacuums.map((v) => `<option value="${esc(v)}" ${v === selected ? "selected" : ""}>${esc(v)}</option>`).join("")}
        </select>
      </div>

      <div class="field">
        <label>${this.t("vacuum_card.editor_title_label")} <span style="font-weight:400;text-transform:none">${this.t("room_card.editor_optional")}</span></label>
        <input id="title" type="text" placeholder="${this.t("vacuum_card.editor_title_placeholder")}" value="${esc(this._config.title ?? "")}">
      </div>

      <div class="field">
        <label>${this.t("vacuum_card.editor_sections_label")}</label>
        <div class="toggles">
          <label class="toggle"><input id="show_profiles" type="checkbox" ${bool("show_profiles", true) ? "checked" : ""}> ${this.t("vacuum_card.editor_show_profiles")}</label>
          <label class="toggle"><input id="show_scenes" type="checkbox" ${bool("show_scenes", true) ? "checked" : ""}> ${this.t("vacuum_card.editor_show_scenes")}</label>
          <label class="toggle"><input id="show_dock" type="checkbox" ${bool("show_dock", true) ? "checked" : ""}> ${this.t("vacuum_card.editor_show_dock")}</label>
        </div>
        <div class="hint">${this.t("vacuum_card.editor_sections_hint")}</div>
      </div>
    `;

    this.shadowRoot.getElementById("vacuum")?.addEventListener("change", (e) => {
      this._fire({ ...this._config, vacuum_entity_id: e.target.value });
    });
    this.shadowRoot.getElementById("title")?.addEventListener("change", (e) => {
      const val = e.target.value.trim();
      const next = { ...this._config };
      if (val) next.title = val; else delete next.title;
      this._fire(next);
    });
    for (const key of ["show_profiles", "show_scenes", "show_dock"]) {
      this.shadowRoot.getElementById(key)?.addEventListener("change", (e) => {
        this._fire({ ...this._config, [key]: e.target.checked });
      });
    }
  }

  static getConfigElement() { return document.createElement(CARD_EDITOR); }

  static getStubConfig(hass) {
    const vacuum = Object.keys(hass?.states ?? {}).find((id) => id.startsWith("vacuum.")) ?? "";
    return { vacuum_entity_id: vacuum };
  }
}

customElements.define(CARD_EDITOR, EufyDashboardCardEditor);

/* ================================================================
   CARD
   ================================================================ */

class EufyDashboardCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
    this._armed = emptyArmed();
    this._rowFields = {};        // roomId -> draft field overrides (unsaved)
    this._expanded = new Set();  // roomIds whose settings body is open
    this._snapshot = null;       // get_dashboard_snapshot payload (fetched once)
    this._profiles = [];         // get_saved_run_profiles list (fetched once)
    this._fetchedFor = null;     // vacuum id the above were fetched for
    this._fetching = false;
    this._starting = false;
  }

  setConfig(config) {
    if (!config?.vacuum_entity_id) throw new Error("vacuum-agent-dashboard: vacuum_entity_id is required");
    this._config = config;
    this._armed = emptyArmed();
    this._rowFields = {};
    this._expanded = new Set();
    this._starting = false;
    this._snapshot = null;
    this._profiles = [];
    this._fetchedFor = null;     // re-fetch snapshot/profiles for the new vacuum
    this._render();
  }

  set hass(hass) {
    const prev = this._hass;
    this._hass = hass;
    ensureLocalesLoaded(() => this._render());
    const relevant = this._shouldRender(prev, hass);
    // If the card loaded before the integration was ready, the one-shot fetch
    // failed and left no snapshot. Retry it — but ONLY on a relevant change (not
    // every tick), so a persistently-failing fetch can't storm.
    if (relevant && !this._snapshot && !this._fetching) this._fetchedFor = null;
    this._ensureData();
    // Re-render only when something the card actually shows changed. HA pushes a
    // new hass on ANY entity update; a blind re-render would rebuild innerHTML and
    // slam shut an open profile/scene <select> mid-pick. Local interactions call
    // _render() directly, so this guard only short-circuits irrelevant ticks.
    if (relevant) this._render();
  }

  /** True iff the vacuum, a managed room switch, or the scene entity changed. */
  _shouldRender(prev, hass) {
    if (!prev) return true;
    const vid = this._vacuumId();
    if (prev.states?.[vid] !== hass.states?.[vid]) return true;
    const ids = new Set();
    for (const r of roomSwitchesFor(hass, vid)) ids.add(r.entityId);
    for (const r of roomSwitchesFor(prev, vid)) ids.add(r.entityId);
    for (const id of ids) if (prev.states?.[id] !== hass.states?.[id]) return true;
    const scene = this._snapshot?.scene_select;
    if (scene && prev.states?.[scene] !== hass.states?.[scene]) return true;
    return false;
  }

  getCardSize() { return 4; }

  /* ---- i18n shims ---- */
  t(key, vars) { return translate(resolveLang(this._hass, this._config), key, vars); }
  _tVocab(field, value, fallback) { return vocab((k, v) => this.t(k, v), field, value, fallback); }

  _vacuumId() { return this._config?.vacuum_entity_id ?? ""; }

  /* =========================================================
     DATA — snapshot + saved profiles (fetched once per vacuum)
     ========================================================= */

  async _ensureData() {
    const vid = this._vacuumId();
    if (!this._hass || !vid || this._fetching || this._fetchedFor === vid) return;
    // Claim BEFORE the await so rapid hass updates don't double-fetch, and so a
    // failed fetch (snapshot/profiles null) isn't retried on every state tick
    // (storm-proof). The rooms path works without this data; reloading the page
    // or changing the configured vacuum re-fetches.
    this._fetching = true;
    this._fetchedFor = vid;
    try {
      const [snap, profs] = await Promise.all([
        callResponse(this._hass, DOMAIN, "get_dashboard_snapshot", { vacuum_entity_id: vid }),
        callResponse(this._hass, DOMAIN, "get_saved_run_profiles", { vacuum_entity_id: vid }),
      ]);
      // The configured vacuum may have changed while these were in flight; drop
      // stale results so the new vacuum isn't rendered against the old snapshot.
      if (this._vacuumId() !== vid) return;
      this._snapshot = snap ?? null;
      this._profiles = Array.isArray(profs?.profiles) ? profs.profiles : [];
    } finally {
      this._fetching = false;
      this._render();
    }
  }

  _rooms() { return roomSwitchesFor(this._hass, this._vacuumId()); }

  _activeMapId() {
    if (this._snapshot?.map_id != null) return String(this._snapshot.map_id);
    const mapId = this._rooms()[0]?.attrs?.map_id;
    // undefined (not "") when unknown, so planStart omits map_id and the backend
    // resolves the active map itself rather than receiving an empty string.
    return mapId != null ? String(mapId) : undefined;
  }

  _sceneEntityId() {
    if (this._config?.show_scenes === false) return null;
    return this._snapshot?.scene_select ?? null;
  }

  _sceneOptions() {
    const id = this._sceneEntityId();
    const opts = id ? this._hass?.states?.[id]?.attributes?.options : null;
    return Array.isArray(opts) ? opts : [];
  }

  _profilesShown() {
    if (this._config?.show_profiles === false) return false;
    if (this._snapshot && this._snapshot.supports_room_profiles === false) return false;
    return this._profiles.length > 0;
  }

  /* =========================================================
     PER-ROOM DRAFT FIELDS
     ========================================================= */

  _roomFields(room) {
    const id = String(room.attrs.room_id);
    return this._rowFields[id] ?? committedRoomFields(room.attrs);
  }

  _roomDirty(room) {
    const id = String(room.attrs.room_id);
    if (!this._rowFields[id]) return false;
    const committed = committedRoomFields(room.attrs);
    return Object.keys(this._rowFields[id]).some((k) => this._rowFields[id][k] !== committed[k]);
  }

  _setRoomField(roomId, key, value) {
    const id = String(roomId);
    const attrs = this._roomByIdAttrs(id);
    // Switch dropped out between render and click — don't seed a draft from
    // all-defaults (it would flag every field dirty and overwrite real values).
    if (!this._rowFields[id] && !Object.keys(attrs).length) return;
    const base = this._rowFields[id] ?? committedRoomFields(attrs);
    this._rowFields[id] = { ...base, [key]: value };
    this._render();
  }

  _roomByIdAttrs(roomId) {
    return this._rooms().find((r) => String(r.attrs.room_id) === String(roomId))?.attrs ?? {};
  }

  /* =========================================================
     RENDER
     ========================================================= */

  _render() {
    if (!this._config?.vacuum_entity_id) { this.shadowRoot.innerHTML = ""; return; }

    const vid = this._vacuumId();
    const vacuumState = this._hass?.states?.[vid];
    const title = this._config.title ?? vacuumState?.attributes?.friendly_name ?? vid;
    const rooms = this._rooms();
    const disabled = roomsDisabled(this._armed);
    const armedSomething = this._armed.source != null;

    this.shadowRoot.innerHTML = `
      <style>${CARD_CSS}</style>
      <div class="card">
        ${this._renderHeader(title, vacuumState)}
        ${rooms.length
          ? `<div class="section rooms ${disabled ? "is-disabled" : ""}">
               <div class="section-label">${this.t("vacuum_card.rooms_label")}</div>
               ${rooms.map((r) => this._renderRoomRow(r)).join("")}
             </div>`
          : `<div class="empty">${this.t("vacuum_card.no_rooms")}</div>`}
        ${this._renderLauncher()}
        <div class="footer">
          ${this._config.show_dock === false ? "" : `
            <button class="btn" id="dock-btn">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M4 4h16v2H4zm2 4h12l-1 8H7z"/></svg>
              ${this.t("vacuum_card.dock")}
            </button>`}
          <button class="btn btn-start" id="start-btn" ${(!armedSomething || this._starting) ? "disabled" : ""}>
            ${this._starting
              ? `<span class="spin">↻</span> ${this.t("vacuum_card.starting")}`
              : `<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg> ${this.t("vacuum_card.start")}`}
          </button>
        </div>
      </div>
    `;

    this._wire();
  }

  _renderHeader(title, vacuumState) {
    const state = vacuumState?.state ?? "unknown";
    // Inline template so check-i18n sees vacuum_card.status.* as reachable.
    const statusTxt = this.t(`vacuum_card.status.${state}`);
    const status = statusTxt === `vacuum_card.status.${state}` ? esc(state) : statusTxt;
    // Coerce + finite-check (the codebase idiom): a transient "unknown"/"" firmware
    // report must suppress the chip, not render "🔋 NaN%" / "🔋 0%".
    const battery = Number(vacuumState?.attributes?.battery_level);
    return `
      <div class="header">
        <span class="title">${esc(title)}</span>
        <span class="meta">
          ${status}
          ${Number.isFinite(battery) ? `<span class="batt">🔋 ${esc(Math.round(battery))}%</span>` : ""}
        </span>
      </div>
    `;
  }

  _renderRoomRow(room) {
    const attrs = room.attrs;
    const roomId = String(attrs.room_id);
    const name = attrs.room_name ?? attrs.friendly_name ?? this.t("room_card.room_fallback", { room_id: roomId });
    const selected = this._armed.selectedRoomIds.some((x) => String(x) === roomId);
    const isOpen = this._expanded.has(roomId);
    return `
      <div class="room-row ${selected ? "is-selected" : ""} ${isOpen ? "is-open" : ""}">
        <div class="room-head">
          <button class="include" data-room="${esc(roomId)}" role="checkbox" aria-checked="${selected}" title="${this.t("vacuum_card.include_room")}">
            <span class="box"></span>
          </button>
          <span class="room-name" data-expand="${esc(roomId)}">${esc(name)}</span>
          ${this._roomDirty(room) ? `<span class="dot" title="${this.t("room_card.unsaved_badge")}"></span>` : ""}
          <button class="chevron" data-expand="${esc(roomId)}" aria-expanded="${isOpen}">▾</button>
        </div>
        ${isOpen ? `<div class="room-body">${this._renderRoomBody(room)}</div>` : ""}
      </div>
    `;
  }

  _renderRoomBody(room) {
    const attrs = room.attrs;
    const roomId = String(attrs.room_id);
    const fields = this._roomFields(room);
    const isCarpet = Boolean(attrs.carpet ?? false);
    const isMop = isMopMode(fields.clean_mode);
    const tv = (f, v, l) => this._tVocab(f, v, l);

    const cleanModes = adapterOptions(attrs, "clean_mode_options");
    const suction    = adapterOptions(attrs, "fan_speed_options");
    const water      = isMop && !isCarpet ? adapterOptions(attrs, "water_level_options") : [];
    const intensity  = adapterOptions(attrs, "clean_intensity_options");
    const showEdge   = isMop && !isCarpet;
    // Clamp to [2, 9] (mirrors room-editor's maxCleanPasses) so a bad snapshot
    // value can't spin a huge chip loop.
    const maxPasses  = Math.min(Number(this._snapshot?.max_clean_passes ?? 2) || 2, 9);

    const passesRow = () => {
      const chips = [];
      for (let p = 1; p <= Math.max(2, maxPasses); p++) {
        chips.push(`<button class="chip ${fields.clean_passes === p ? "active" : ""}" data-scope="${esc(roomId)}" data-field="clean_passes" data-value="${p}">${this.t("vacuum_card.passes_n", { count: p })}</button>`);
      }
      return `<div class="field-group"><div class="field-label">${this.t("room_card.passes_label")}</div><div class="chips">${chips.join("")}</div></div>`;
    };

    const edgeRow = () => !showEdge ? "" : `
      <div class="field-group"><div class="field-label">${this.t("room_card.edge_mopping_label")}</div>
        <div class="chips">
          <button class="chip ${fields.edge_mopping ? "active" : ""}" data-scope="${esc(roomId)}" data-field="edge_mopping" data-value="true">${this.t("common.on")}</button>
          <button class="chip ${!fields.edge_mopping ? "active" : ""}" data-scope="${esc(roomId)}" data-field="edge_mopping" data-value="false">${this.t("common.off")}</button>
        </div>
      </div>`;

    return `
      ${isCarpet ? `<div class="carpet">🪵 ${this.t("room_card.carpet_notice")}</div>` : ""}
      ${chipRow(this.t("room_card.cleaning_mode_label"), "clean_mode", cleanModes, fields.clean_mode, tv, roomId)}
      ${chipRow(this.t("room_card.suction_level_label"), "fan_speed", suction, fields.fan_speed, tv, roomId)}
      ${water.length ? chipRow(this.t("room_card.water_level_label"), "water_level", water, fields.water_level, tv, roomId) : ""}
      ${chipRow(this.t("room_card.cleaning_path_label"), "clean_intensity", intensity, fields.clean_intensity, tv, roomId)}
      ${passesRow()}
      ${edgeRow()}
    `;
  }

  _renderLauncher() {
    const showProfiles = this._profilesShown();
    const scenes = this._sceneOptions();
    const showScenes = scenes.length > 0;
    if (!showProfiles && !showScenes) return "";

    const armedProfile = this._armed.source === "profile" ? this._armed.profileId : "";
    const armedScene = this._armed.source === "scene" ? this._armed.sceneOption : "";

    const profileSel = !showProfiles ? "" : `
      <div class="launch-group">
        <div class="section-label">${this.t("vacuum_card.profiles_label")}</div>
        <select id="profile-select">
          <option value="" ${!armedProfile ? "selected" : ""}>${this.t("vacuum_card.profiles_placeholder")}</option>
          ${this._profiles.map((p) => `<option value="${esc(p.id)}" ${p.id === armedProfile ? "selected" : ""}>${esc(p.name)}${p.summary ? ` — ${esc(p.summary)}` : ""}</option>`).join("")}
        </select>
      </div>`;

    const sceneSel = !showScenes ? "" : `
      <div class="launch-group">
        <div class="section-label">${this.t("vacuum_card.scenes_label")}</div>
        <select id="scene-select">
          <option value="" ${!armedScene ? "selected" : ""}>${this.t("vacuum_card.scenes_placeholder")}</option>
          ${scenes.map((s) => `<option value="${esc(s)}" ${s === armedScene ? "selected" : ""}>${esc(s)}</option>`).join("")}
        </select>
        <div class="hint">${this.t("vacuum_card.scenes_hint")}</div>
      </div>`;

    return `<div class="section launcher">${profileSel}${sceneSel}</div>`;
  }

  /* =========================================================
     EVENT WIRING
     ========================================================= */

  _wire() {
    // Room include toggles
    this.shadowRoot.querySelectorAll(".include").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (roomsDisabled(this._armed)) return;
        const roomId = btn.dataset.room;
        this._armed = nextArmed(this._armed, { type: "toggleRoom", roomId: Number.isFinite(Number(roomId)) ? Number(roomId) : roomId });
        this._render();
      });
    });
    // Expand / collapse a room's settings body
    this.shadowRoot.querySelectorAll("[data-expand]").forEach((el) => {
      el.addEventListener("click", () => {
        const roomId = el.dataset.expand;
        if (this._expanded.has(roomId)) this._expanded.delete(roomId);
        else this._expanded.add(roomId);
        this._render();
      });
    });
    // Per-row setting chips
    this.shadowRoot.querySelectorAll(".chip").forEach((btn) => {
      btn.addEventListener("click", () => {
        const { scope, field, value } = btn.dataset;
        if (!scope) return;
        let parsed = value;
        if (field === "clean_passes") parsed = Number(value);
        if (field === "edge_mopping") parsed = value === "true";
        this._setRoomField(scope, field, parsed);
      });
    });
    // Run-launcher dropdowns (arm only — never fire here)
    this.shadowRoot.getElementById("profile-select")?.addEventListener("change", (e) => {
      this._armed = nextArmed(this._armed, { type: "pickProfile", profileId: e.target.value });
      this._render();
    });
    this.shadowRoot.getElementById("scene-select")?.addEventListener("change", (e) => {
      this._armed = nextArmed(this._armed, { type: "pickScene", option: e.target.value });
      this._render();
    });
    // Actions
    this.shadowRoot.getElementById("start-btn")?.addEventListener("click", () => this._handleStart());
    this.shadowRoot.getElementById("dock-btn")?.addEventListener("click", () => this._handleDock());
  }

  /* =========================================================
     ACTIONS — the ONLY place a run is dispatched
     ========================================================= */

  _startContext() {
    const rooms = this._rooms().map((r) => {
      const id = String(r.attrs.room_id);
      const dirty = this._roomDirty(r);
      return {
        entityId: r.entityId,
        roomId: Number.isFinite(Number(id)) ? Number(id) : id,
        mapId: r.attrs.map_id != null ? String(r.attrs.map_id) : undefined,
        currentlyOn: r.state === "on",
        dirty,
        fields: dirty ? this._rowFields[id] : undefined,
      };
    });
    return {
      vacuumEntityId: this._vacuumId(),
      mapId: this._activeMapId(),
      sceneEntityId: this._sceneEntityId(),
      rooms,
    };
  }

  async _handleStart() {
    if (this._starting || !this._hass) return;
    // Re-validate the armed source against LIVE data before dispatching: a scene
    // option or saved profile can vanish (vendor-app / library edit) between
    // arming and Start. Never fire select_option for a removed scene — selecting
    // IS the run, so a stale value would be an accidental clean.
    if (!armedIsValid(this._armed, {
      sceneOptions: this._sceneOptions(),
      profileIds: this._profiles.map((p) => p.id),
    })) {
      this._armed = emptyArmed();
      this._render();
      return;
    }
    const plan = planStart(this._armed, this._startContext());
    if (!plan.length) return;
    // Only the rooms this run actually persists should have their drafts cleared,
    // so unsaved edits on rooms NOT in the run survive (no silent data loss).
    const persistedRoomIds = this._armed.source === "rooms"
      ? this._armed.selectedRoomIds.map(String)
      : [];
    this._starting = true;
    this._render();
    try {
      for (const call of plan) {
        await this._hass.callService(call.domain, call.service, call.data);
      }
      for (const id of persistedRoomIds) delete this._rowFields[id];
    } catch (err) {
      // A mid-plan service failure must not vanish silently — surface a toast so
      // the user knows the run didn't start (and the spinner clearing isn't read
      // as success). Next Start re-reads live state and re-reconciles.
      console.error("[vacuum-agent] start failed mid-dispatch", err);
      this.dispatchEvent(new CustomEvent("hass-notification", {
        detail: { message: this.t("vacuum_card.start_failed") },
        bubbles: true, composed: true,
      }));
    } finally {
      this._starting = false;
      this._render();
    }
  }

  async _handleDock() {
    if (!this._hass) return;
    await this._hass.callService("vacuum", "return_to_base", { entity_id: this._vacuumId() });
  }

  static getConfigElement() { return document.createElement(CARD_EDITOR); }

  static getStubConfig(hass) {
    const vacuum = Object.keys(hass?.states ?? {}).find((id) => id.startsWith("vacuum.")) ?? "";
    return { vacuum_entity_id: vacuum };
  }
}

/* ================================================================
   STYLES (own shadow root — sibling cards carry their own CSS)
   ================================================================ */

const CARD_CSS = `
  :host {
    display: block;
    --accent:       var(--evcc-accent, #3b82f6);
    --surface:      var(--evcc-surface-card, #1c2127);
    --border:       var(--evcc-border-default, rgba(255,255,255,0.10));
    --text-primary: var(--evcc-text-primary, #f0f2f5);
    --text-muted:   var(--evcc-text-muted, rgba(240,242,245,0.48));
    --radius:       var(--evcc-radius-card, 12px);
  }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }

  .header { display: flex; align-items: baseline; gap: 10px; padding: 14px 16px 10px; flex-wrap: wrap; }
  .title { font-size: 1.0rem; font-weight: 700; color: var(--text-primary); }
  .meta { font-size: 0.80rem; color: var(--text-muted); display: inline-flex; align-items: center; gap: 8px; }
  .batt { white-space: nowrap; }

  .section { padding: 4px 12px 8px; }
  .section-label { font-size: 0.70rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; padding: 6px 4px 4px; }
  .rooms.is-disabled { opacity: 0.4; pointer-events: none; }
  .empty { padding: 16px; font-size: 0.85rem; color: var(--text-muted); }

  .room-row { border: 1px solid var(--border); border-radius: 8px; margin: 4px 0; overflow: hidden; }
  .room-row.is-selected { border-color: color-mix(in srgb, var(--accent) 55%, transparent); background: color-mix(in srgb, var(--accent) 6%, transparent); }
  .room-head { display: flex; align-items: center; gap: 10px; padding: 8px 10px; }
  .include { width: 22px; height: 22px; flex-shrink: 0; border: none; background: transparent; cursor: pointer; padding: 0; }
  .include .box { display: block; width: 18px; height: 18px; border-radius: 5px; border: 2px solid var(--text-muted); transition: all 120ms ease; }
  .room-row.is-selected .include .box { background: var(--accent); border-color: var(--accent); box-shadow: inset 0 0 0 2px var(--surface); }
  .room-name { flex: 1; min-width: 0; font-size: 0.92rem; font-weight: 600; color: var(--text-primary); cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--accent); flex-shrink: 0; }
  .chevron { background: transparent; border: none; color: var(--text-muted); cursor: pointer; font-size: 0.9rem; transition: transform 150ms ease; }
  .room-row.is-open .chevron { transform: rotate(180deg); }

  .room-body { display: flex; flex-direction: column; gap: 10px; padding: 4px 12px 12px; border-top: 1px solid var(--border); }
  .carpet { font-size: 0.78rem; color: var(--text-muted); background: rgba(255,255,255,0.04); border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px; }
  .field-group { display: flex; flex-direction: column; gap: 6px; }
  .field-label { font-size: 0.70rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .chip { padding: 5px 12px; border-radius: 999px; border: 1px solid var(--border); background: rgba(255,255,255,0.04); color: var(--text-muted); font-size: 0.80rem; font-weight: 500; cursor: pointer; transition: all 120ms ease; }
  .chip:hover { background: rgba(255,255,255,0.08); color: var(--text-primary); }
  .chip.active { background: color-mix(in srgb, var(--accent) 18%, transparent); border-color: color-mix(in srgb, var(--accent) 50%, transparent); color: color-mix(in srgb, var(--accent) 90%, white); }

  .launcher { display: flex; flex-direction: column; gap: 10px; }
  .launch-group { display: flex; flex-direction: column; gap: 4px; }
  select { width: 100%; box-sizing: border-box; padding: 8px 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); color: var(--text-primary); font-size: 0.88rem; appearance: none; -webkit-appearance: none; }
  .hint { font-size: 0.72rem; color: var(--text-muted); padding: 0 2px; }

  .footer { display: flex; justify-content: flex-end; align-items: center; gap: 8px; padding: 10px 16px; border-top: 1px solid var(--border); }
  .btn { display: inline-flex; align-items: center; gap: 6px; padding: 7px 16px; border-radius: 999px; border: 1px solid var(--border); background: transparent; color: var(--text-muted); font-size: 0.82rem; font-weight: 600; cursor: pointer; transition: all 120ms ease; }
  .btn:hover { color: var(--text-primary); }
  .btn-start { color: #fff; border-color: transparent; background: var(--accent); }
  .btn-start:hover { background: color-mix(in srgb, var(--accent) 85%, white); }
  .btn-start:disabled { opacity: 0.4; cursor: default; background: var(--accent); }
  .btn-start:active:not(:disabled) { transform: scale(0.96); }
  @keyframes spin { to { transform: rotate(360deg); } }
  .spin { animation: spin 0.9s linear infinite; display: inline-block; }
`;

customElements.define(CARD_NAME, EufyDashboardCard);

registerCard({
  type: CARD_NAME,
  name: "Vacuum Agent — Dashboard Mode",
  description: "Compact multi-room control card: pick rooms + settings, run a saved profile or app scene, start / dock.",
  preview: true,
});
