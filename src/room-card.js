// Standalone per-room Lovelace card with settings chips, save, and quick-start for managed vacuums.

import { translate } from "./i18n/index.js";

const ROOM_CARD_NAME   = "eufy-room-card";
const ROOM_CARD_EDITOR = "eufy-room-card-editor";

const _rcLang = (hass) => (hass && hass.locale && hass.locale.language) || (hass && hass.language) || "en";

/* ================================================================
   EDITOR
   ================================================================ */

class EufyRoomCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass   = null;
    this._config = {};
  }

  setConfig(config) { this._config = config ?? {}; this._render(); }

  set hass(hass) { this._hass = hass; this._render(); }

  t(key, vars)    { return translate(_rcLang(this._hass), key, vars); }
  tRaw(key, vars) { return translate(_rcLang(this._hass), key, vars, { raw: true }); }

  _vacuumEntities() {
    if (!this._hass) return [];
    return Object.keys(this._hass.states).filter((id) => id.startsWith("vacuum.")).sort();
  }

  _roomSwitchesFor(vacuumEntityId) {
    if (!this._hass || !vacuumEntityId) return [];
    return Object.entries(this._hass.states)
      .filter(([id, s]) =>
        id.startsWith("switch.") &&
        s.attributes?.vacuum_entity_id === vacuumEntityId &&
        s.attributes?.room_id != null
      )
      .map(([, s]) => ({
        room_id:   s.attributes.room_id,
        room_name: s.attributes.room_name ?? s.attributes.friendly_name ?? this.t("room_card.room_fallback", { room_id: s.attributes.room_id }),
      }))
      .sort((a, b) => String(a.room_name).localeCompare(String(b.room_name)));
  }

  _fire(config) {
    if (!config?.vacuum_entity_id || config?.room_id == null) return;
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
  }

  _render() {
    const vacuums        = this._vacuumEntities();
    const selectedVacuum = this._config.vacuum_entity_id ?? "";
    const rooms          = this._roomSwitchesFor(selectedVacuum);
    const selectedRoom   = this._config.room_id != null ? String(this._config.room_id) : "";
    const nameOverride   = this._config.name ?? "";

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; font-family: var(--paper-font-body1_-_font-family, sans-serif); }
        .field { display: flex; flex-direction: column; gap: 4px; margin-bottom: 16px; }
        label {
          font-size: 0.80rem; font-weight: 500;
          color: var(--secondary-text-color, #888);
          text-transform: uppercase; letter-spacing: 0.04em;
        }
        select, input {
          width: 100%; box-sizing: border-box; padding: 8px 10px;
          border: 1px solid var(--divider-color, rgba(255,255,255,0.12));
          border-radius: 6px;
          background: var(--card-background-color, #1c2127);
          color: var(--primary-text-color, #f0f2f5);
          font-size: 0.92rem; appearance: none; -webkit-appearance: none;
        }
        select:focus, input:focus { outline: none; border-color: var(--primary-color, #3b82f6); }
        .hint  { font-size: 0.75rem; color: var(--secondary-text-color, #888); margin-top: 2px; }
        .no-rooms {
          font-size: 0.85rem; color: var(--warning-color, #f59e0b);
          padding: 8px 10px; border: 1px solid currentColor; border-radius: 6px; opacity: 0.8;
        }
      </style>

      <div class="field">
        <label>${this.t("room_card.editor_vacuum_label")}</label>
        <select id="vacuum">
          <option value="" disabled ${!selectedVacuum ? "selected" : ""}>${this.t("room_card.editor_pick_vacuum")}</option>
          ${vacuums.map((v) => `<option value="${_esc(v)}" ${v === selectedVacuum ? "selected" : ""}>${_esc(v)}</option>`).join("")}
        </select>
      </div>

      <div class="field">
        <label>${this.t("room_card.editor_room_label")}</label>
        ${!selectedVacuum
          ? `<div class="hint">${this.t("room_card.editor_select_vacuum_first")}</div>`
          : rooms.length === 0
          ? `<div class="no-rooms">${this.t("room_card.editor_no_room_switches", { vacuum: _esc(selectedVacuum) })}</div>`
          : `<select id="room">
               <option value="" disabled ${!selectedRoom ? "selected" : ""}>${this.t("room_card.editor_pick_room")}</option>
               ${rooms.map((r) => `<option value="${_esc(String(r.room_id))}" ${String(r.room_id) === selectedRoom ? "selected" : ""}>${_esc(r.room_name)}</option>`).join("")}
             </select>`}
      </div>

      <div class="field">
        <label>${this.t("room_card.editor_name_override_label")} <span style="font-weight:400;text-transform:none">${this.t("room_card.editor_optional")}</span></label>
        <input id="name" type="text" placeholder="${this.t("room_card.editor_name_placeholder")}" value="${_esc(nameOverride)}">
        <div class="hint">${this.t("room_card.editor_name_hint")}</div>
      </div>
    `;

    this.shadowRoot.getElementById("vacuum")?.addEventListener("change", (e) => {
      this._fire({ ...this._config, vacuum_entity_id: e.target.value, room_id: undefined });
    });
    this.shadowRoot.getElementById("room")?.addEventListener("change", (e) => {
      const val = e.target.value;
      const asNum = Number(val);
      this._fire({ ...this._config, room_id: Number.isFinite(asNum) ? asNum : val });
    });
    this.shadowRoot.getElementById("name")?.addEventListener("change", (e) => {
      const val = e.target.value.trim();
      const next = { ...this._config };
      if (val) next.name = val; else delete next.name;
      this._fire(next);
    });
  }

  static getConfigElement() { return document.createElement(ROOM_CARD_EDITOR); }

  static getStubConfig(hass) {
    const states   = hass?.states ?? {};
    const vacuum   = Object.keys(states).find((id) => id.startsWith("vacuum.")) ?? "";
    const firstRoom = Object.entries(states).find(
      ([id, s]) =>
        id.startsWith("switch.") &&
        s.attributes?.vacuum_entity_id === vacuum &&
        s.attributes?.room_id != null
    );
    return { vacuum_entity_id: vacuum, room_id: firstRoom?.[1]?.attributes?.room_id ?? null };
  }
}

customElements.define(ROOM_CARD_EDITOR, EufyRoomCardEditor);

/* ================================================================
   CARD
   ================================================================ */

class EufyRoomCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass     = null;
    this._config   = null;
    this._fields   = null;   // unsaved local overrides
    this._saving   = false;
    this._starting = false;
  }

  setConfig(config) {
    this._config = config ?? {};
    this._fields = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  t(key, vars)    { return translate(_rcLang(this._hass), key, vars); }
  tRaw(key, vars) { return translate(_rcLang(this._hass), key, vars, { raw: true }); }

  /* =========================================================
     ENTITY FINDERS
     ========================================================= */

  _objectId() {
    return (this._config?.vacuum_entity_id ?? "").split(".")[1] ?? "";
  }

  _allRoomSwitches() {
    const { states } = this._hass ?? {};
    const vacuumId   = this._config?.vacuum_entity_id;
    if (!states || !vacuumId) return [];
    return Object.entries(states)
      .filter(([id, s]) =>
        id.startsWith("switch.") &&
        s.attributes?.vacuum_entity_id === vacuumId &&
        s.attributes?.room_id != null
      )
      .map(([id, s]) => ({ entityId: id, state: s.state, attrs: s.attributes ?? {} }));
  }

  _targetSwitch() {
    const roomId = String(this._config?.room_id ?? "");
    return this._allRoomSwitches().find((s) => String(s.attrs.room_id) === roomId) ?? null;
  }

  /* =========================================================
     OPTION LISTS
     ========================================================= */

  /**
   * Read an adapter-declared option list from the target room switch's
   * attributes. Each list is `[{value, label}, ...]` populated by
   * EufyVacuumRoomEntity in the backend. Falls back to an empty array
   * when the attribute is absent (older backend, attribute not yet
   * surfaced) — the caller's chipRow hides empty groups.
   *
   * @param {string} attrName - "clean_mode_options" / "fan_speed_options" /
   *                            "water_level_options" / "clean_intensity_options"
   * @returns {Array<{value: string, label: string}>}
   */
  _adapterOptions(attrName) {
    const sw = this._targetSwitch();
    const list = sw?.attrs?.[attrName];
    return Array.isArray(list) ? list : [];
  }

  _cleanModeOptions() {
    return this._adapterOptions("clean_mode_options");
  }

  _suctionOptions() {
    return this._adapterOptions("fan_speed_options");
  }

  _waterLevelOptions() {
    return this._adapterOptions("water_level_options");
  }

  _cleanIntensityOptions(_slug, _mapId) {
    // slug/mapId no longer needed — the option list is per-vacuum
    // (declared once by the adapter), not per-room. Parameters
    // retained for call-site compatibility.
    return this._adapterOptions("clean_intensity_options");
  }

  _isMopMode(mode) {
    return String(mode ?? "").toLowerCase().replace(/[\s_-]/g, "").includes("mop");
  }

  /* =========================================================
     FIELD STATE
     ========================================================= */

  _committedFields() {
    const sw = this._targetSwitch()?.attrs ?? {};
    return {
      clean_mode:      sw.clean_mode      ?? "vacuum",
      fan_speed:       sw.fan_speed       ?? null,
      water_level:     sw.water_level     ?? null,
      clean_intensity: sw.clean_intensity ?? null,
      clean_passes:    Number(sw.clean_passes   ?? 1),
      edge_mopping:    Boolean(sw.edge_mopping  ?? false),
    };
  }

  _currentFields() {
    return this._fields ?? this._committedFields();
  }

  _isDirty() {
    if (!this._fields) return false;
    const committed = this._committedFields();
    return Object.keys(this._fields).some((k) => this._fields[k] !== committed[k]);
  }

  _setField(key, value) {
    this._fields = { ...this._currentFields(), [key]: value };
    this._render();
  }

  /* =========================================================
     RENDER
     ========================================================= */

  _render() {
    if (!this._config?.vacuum_entity_id || this._config?.room_id == null) {
      this.shadowRoot.innerHTML = "";
      return;
    }

    const sw        = this._targetSwitch();
    const swAttrs   = sw?.attrs ?? {};
    const isEnabled = sw?.state === "on";
    const name      = this._config.name ?? swAttrs.room_name ?? this.t("room_card.room_fallback", { room_id: this._config.room_id });
    const slug      = swAttrs.slug ?? "";
    const mapId     = String(swAttrs.map_id ?? "");
    const isCarpet  = Boolean(swAttrs.carpet ?? false);

    const fields    = this._currentFields();
    const dirty     = this._isDirty();
    const isMop     = this._isMopMode(fields.clean_mode);

    const cleanModes       = this._cleanModeOptions();
    const suctionLevels    = this._suctionOptions();
    const waterLevels      = isMop && !isCarpet ? this._waterLevelOptions() : [];
    const cleanIntensities = this._cleanIntensityOptions(slug, mapId);
    const showEdgeMopping  = isMop && !isCarpet;

    const chipRow = (label, fieldKey, options, currentVal) => {
      if (!options.length) return "";
      return `
        <div class="field-group">
          <div class="field-label">${_esc(label)}</div>
          <div class="chips">
            ${options.map((opt) => `
              <button
                class="chip ${String(currentVal ?? "").toLowerCase() === String(opt.value ?? "").toLowerCase() ? "active" : ""}"
                data-field="${_esc(fieldKey)}"
                data-value="${_esc(opt.value)}"
              >${_esc(opt.label)}</button>
            `).join("")}
          </div>
        </div>
      `;
    };

    const passesRow = () => `
      <div class="field-group">
        <div class="field-label">${this.t("room_card.passes_label")}</div>
        <div class="chips">
          <button class="chip ${fields.clean_passes === 1 ? "active" : ""}" data-field="clean_passes" data-value="1">${this.t("room_card.passes_1")}</button>
          <button class="chip ${fields.clean_passes === 2 ? "active" : ""}" data-field="clean_passes" data-value="2">${this.t("room_card.passes_2")}</button>
        </div>
      </div>
    `;

    const edgeMopRow = () => !showEdgeMopping ? "" : `
      <div class="field-group">
        <div class="field-label">${this.t("room_card.edge_mopping_label")}</div>
        <div class="chips">
          <button class="chip ${fields.edge_mopping ? "active" : ""}" data-field="edge_mopping" data-value="true">${this.t("common.on")}</button>
          <button class="chip ${!fields.edge_mopping ? "active" : ""}" data-field="edge_mopping" data-value="false">${this.t("common.off")}</button>
        </div>
      </div>
    `;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          --accent:       var(--evcc-accent, #3b82f6);
          --surface:      var(--evcc-surface-card, #1c2127);
          --border:       var(--evcc-border-default, rgba(255,255,255,0.10));
          --text-primary: var(--evcc-text-primary, #f0f2f5);
          --text-muted:   var(--evcc-text-muted, rgba(240,242,245,0.48));
          --radius:       var(--evcc-radius-card, 12px);
        }

        .card {
          background:   var(--surface);
          border:       1px solid var(--border);
          border-radius: var(--radius);
          overflow:     hidden;
        }

        /* ---- header ---- */
        .header {
          display:     flex;
          align-items: center;
          gap:         10px;
          padding:     14px 16px 12px;
          cursor:      pointer;
          user-select: none;
          -webkit-tap-highlight-color: transparent;
        }

        .indicator {
          width: 9px; height: 9px;
          border-radius: 50%; flex-shrink: 0;
          background: var(--border);
          transition: background 150ms ease;
        }

        .is-enabled .indicator {
          background: var(--accent);
          box-shadow: 0 0 6px color-mix(in srgb, var(--accent) 60%, transparent);
        }

        .room-name {
          font-size: 0.96rem; font-weight: 700;
          color: var(--text-primary); flex: 1; min-width: 0;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }

        .dirty-badge {
          font-size: 0.70rem; font-weight: 600;
          color: var(--accent);
          background: color-mix(in srgb, var(--accent) 12%, transparent);
          border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent);
          border-radius: 4px; padding: 1px 6px;
          flex-shrink: 0;
        }

        /* ---- carpet notice ---- */
        .carpet-notice {
          margin: 0 16px 8px;
          font-size: 0.78rem;
          color: var(--text-muted);
          background: rgba(255,255,255,0.04);
          border: 1px solid var(--border);
          border-radius: 6px;
          padding: 6px 10px;
        }

        /* ---- fields ---- */
        .fields {
          display: flex; flex-direction: column; gap: 12px;
          padding: 0 16px 14px;
        }

        .field-group { display: flex; flex-direction: column; gap: 6px; }

        .field-label {
          font-size: 0.72rem; font-weight: 600;
          color: var(--text-muted);
          text-transform: uppercase; letter-spacing: 0.05em;
        }

        .chips { display: flex; flex-wrap: wrap; gap: 6px; }

        .chip {
          padding: 5px 12px;
          border-radius: 999px;
          border: 1px solid var(--border);
          background: rgba(255,255,255,0.04);
          color: var(--text-muted);
          font-size: 0.80rem; font-weight: 500;
          cursor: pointer;
          transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
          -webkit-tap-highlight-color: transparent;
        }

        .chip:hover { background: rgba(255,255,255,0.08); color: var(--text-primary); }

        .chip.active {
          background:   color-mix(in srgb, var(--accent) 18%, transparent);
          border-color: color-mix(in srgb, var(--accent) 50%, transparent);
          color:        color-mix(in srgb, var(--accent) 90%, white);
        }

        /* ---- footer ---- */
        .footer {
          display: flex; justify-content: flex-end; align-items: center; gap: 8px;
          padding: 10px 16px;
          border-top: 1px solid var(--border);
        }

        .btn {
          display: flex; align-items: center; gap: 6px;
          padding: 7px 16px;
          border-radius: 999px;
          border: 1px solid var(--border);
          background: transparent;
          color: var(--text-muted);
          font-size: 0.82rem; font-weight: 600;
          cursor: pointer;
          transition: background 120ms ease, color 120ms ease, border-color 120ms ease;
          -webkit-tap-highlight-color: transparent;
        }

        .btn:disabled { opacity: 0.4; cursor: default; }

        .btn-save {
          color: var(--accent);
          border-color: color-mix(in srgb, var(--accent) 40%, transparent);
          background: color-mix(in srgb, var(--accent) 8%, transparent);
        }

        .btn-save:hover:not(:disabled) {
          background: color-mix(in srgb, var(--accent) 18%, transparent);
        }

        .btn-start {
          color: #fff;
          border-color: transparent;
          background: var(--accent);
        }

        .btn-start:hover:not(:disabled) {
          background: color-mix(in srgb, var(--accent) 85%, white);
        }

        .btn-start:active:not(:disabled) { transform: scale(0.96); }

        @keyframes spin { to { transform: rotate(360deg); } }
        .spinning { animation: spin 0.9s linear infinite; display: inline-block; }
      </style>

      <div class="card">

        <div class="header ${isEnabled ? "is-enabled" : ""}" role="button" aria-pressed="${isEnabled}" tabindex="0">
          <div class="indicator"></div>
          <span class="room-name">${_esc(name)}</span>
          ${dirty ? `<span class="dirty-badge">${this.t("room_card.unsaved_badge")}</span>` : ""}
        </div>

        ${isCarpet ? `<div class="carpet-notice">🪵 ${this.t("room_card.carpet_notice")}</div>` : ""}

        <div class="fields">
          ${chipRow(this.t("room_card.cleaning_mode_label"), "clean_mode", cleanModes, fields.clean_mode)}
          ${chipRow(this.t("room_card.suction_level_label"), "fan_speed", suctionLevels, fields.fan_speed)}
          ${waterLevels.length ? chipRow(this.t("room_card.water_level_label"), "water_level", waterLevels, fields.water_level) : ""}
          ${chipRow(this.t("room_card.cleaning_path_label"), "clean_intensity", cleanIntensities, fields.clean_intensity)}
          ${passesRow()}
          ${edgeMopRow()}
        </div>

        <div class="footer">
          ${dirty ? `
          <button class="btn btn-save" id="save-btn" ${this._saving ? "disabled" : ""}>
            ${this._saving ? `<span class="spinning">↻</span> ${this.t("common.saving")}` : this.t("common.save")}
          </button>` : ""}
          <button class="btn btn-start" id="start-btn" ${this._starting ? "disabled" : ""}>
            ${this._starting
              ? `<span class="spinning">↻</span> ${this.t("room_card.starting")}`
              : `<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" style="margin-right:2px"><polygon points="5,3 19,12 5,21"/></svg> ${this.t("room_card.start")}`}
          </button>
        </div>

      </div>
    `;

    /* ---- toggle header ---- */
    const toggleArea = this.shadowRoot.querySelector(".header");
    toggleArea.addEventListener("click", () => this._handleToggle());
    toggleArea.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); this._handleToggle(); }
    });

    /* ---- chip clicks ---- */
    this.shadowRoot.querySelectorAll(".chip").forEach((btn) => {
      btn.addEventListener("click", () => {
        const { field, value } = btn.dataset;
        let parsed = value;
        if (field === "clean_passes") parsed = Number(value);
        if (field === "edge_mopping") parsed = value === "true";
        this._setField(field, parsed);
      });
    });

    /* ---- save / start ---- */
    this.shadowRoot.getElementById("save-btn")?.addEventListener("click", () => this._handleSave());
    this.shadowRoot.getElementById("start-btn")?.addEventListener("click", () => this._handleStart());
  }

  // Toggle this room on (exclusive) or off. Turns off all other enabled rooms first.
  async _handleToggle() {
    if (!this._hass) return;
    const target     = this._targetSwitch();
    const all        = this._allRoomSwitches();
    const wasEnabled = target?.state === "on";
    await Promise.all(
      all.filter((s) => s.state === "on")
        .map((s) => this._hass.callService("switch", "turn_off", { entity_id: s.entityId }))
    );
    if (!wasEnabled && target) {
      await this._hass.callService("switch", "turn_on", { entity_id: target.entityId });
    }
  }

  // Turn off all enabled rooms and turn this one on — used before start to ensure exclusive selection.
  async _selectExclusive() {
    const target = this._targetSwitch();
    const all    = this._allRoomSwitches();
    await Promise.all(
      all.filter((s) => s.state === "on")
        .map((s) => this._hass.callService("switch", "turn_off", { entity_id: s.entityId }))
    );
    if (target) {
      await this._hass.callService("switch", "turn_on", { entity_id: target.entityId });
    }
  }

  async _handleSave() {
    if (this._saving || !this._hass || !this._fields) return;
    const sw = this._targetSwitch();
    if (!sw) return;
    this._saving = true;
    this._render();
    try {
      await this._hass.callService("eufy_vacuum", "update_room_fields", {
        vacuum_entity_id: this._config.vacuum_entity_id,
        map_id:           String(sw.attrs.map_id),
        room_id:          this._config.room_id,
        ...this._fields,
      });
      this._fields = null;
    } finally {
      this._saving = false;
      this._render();
    }
  }

  async _handleStart() {
    if (this._starting || !this._hass) return;
    const sw = this._targetSwitch();
    if (!sw) return;
    this._starting = true;
    this._render();
    try {
      if (this._isDirty()) {
        await this._hass.callService("eufy_vacuum", "update_room_fields", {
          vacuum_entity_id: this._config.vacuum_entity_id,
          map_id:           String(sw.attrs.map_id),
          room_id:          this._config.room_id,
          ...this._fields,
        });
        this._fields = null;
      }
      await this._selectExclusive();
      await this._hass.callService("eufy_vacuum", "start_selected_rooms", {
        vacuum_entity_id: this._config.vacuum_entity_id,
        map_id:           String(sw.attrs.map_id),
      });
    } finally {
      this._starting = false;
      this._render();
    }
  }

  static getConfigElement() { return document.createElement(ROOM_CARD_EDITOR); }

  static getStubConfig(hass) {
    const states    = hass?.states ?? {};
    const vacuum    = Object.keys(states).find((id) => id.startsWith("vacuum.")) ?? "";
    const firstRoom = Object.entries(states).find(
      ([id, s]) =>
        id.startsWith("switch.") &&
        s.attributes?.vacuum_entity_id === vacuum &&
        s.attributes?.room_id != null
    );
    return { vacuum_entity_id: vacuum, room_id: firstRoom?.[1]?.attributes?.room_id ?? null };
  }
}

/* ================================================================
   SHARED UTIL
   ================================================================ */

function _esc(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

customElements.define(ROOM_CARD_NAME, EufyRoomCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type:        ROOM_CARD_NAME,
  name:        "Eufy Room Card",
  description: "Single-room settings and quick-start card for managed vacuums.",
});
