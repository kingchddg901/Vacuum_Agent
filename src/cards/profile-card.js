// Standalone Lovelace card: inspect-and-run ONE saved run profile.
//
// A run profile is now a full routine (room groups, per-room settings, repeated
// rooms, charge-to-% stops, wait steps, phased strict order) — a name alone isn't
// always enough on a dashboard. This card shows what the routine WILL do (the
// "Runs As" step manifest, slice b) before you press Run. It is inspect-and-run
// ONLY: no Save / Edit / Delete / profile-manager surfaces — those live in the
// full panel. Config is via the visual editor (slice c), not YAML.
//
// Reuse: the card/editor scaffold mirrors room-card.js + dashboard-card.js; the
// data comes from the get_saved_run_profiles service (each profile carries its
// enriched metadata + `steps`); Run dispatches start_run_profile (which owns the
// whole stepped sequence). The step manifest is the shared renderStepsManifest
// helper (slice b) so this card and the full panel can't drift.

import { translate, resolveLang, ensureLocalesLoaded } from "../i18n/index.js";
import { esc, callResponse, defineCard, getStoredLang } from "./_shared.js";
import { renderStepsManifest } from "../state/steps-manifest.js";

const CARD_NAME = "vacuum-agent-profile-card";
const CARD_EDITOR = "vacuum-agent-profile-card-editor";
const DOMAIN = "eufy_vacuum";

const CARD_CSS = `
  :host { display: block; }
  .evcc-pcard {
    background: var(--ha-card-background, var(--card-background-color, #fff));
    border-radius: var(--ha-card-border-radius, 12px);
    box-shadow: var(--ha-card-box-shadow, none);
    border: var(--ha-card-border-width, 1px) solid var(--divider-color, #e0e0e0);
    padding: 16px;
    color: var(--primary-text-color);
    font-family: var(--paper-font-body1_-_font-family, inherit);
  }
  .evcc-pcard-name { font-size: 1.15rem; font-weight: 600; line-height: 1.2; }
  .evcc-pcard-meta { color: var(--secondary-text-color); font-size: 0.85rem; margin-top: 4px; }
  .evcc-pcard-meta-rooms { color: var(--secondary-text-color); font-size: 0.85rem; margin-top: 2px; }
  .evcc-pcard-manifest { margin-top: 12px; }
  .evcc-pcard-footer { margin-top: 16px; display: flex; justify-content: flex-end; }
  .evcc-pcard-run {
    appearance: none; border: none; cursor: pointer;
    background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff);
    font: inherit; font-weight: 600; padding: 8px 20px; border-radius: 999px;
  }
  .evcc-pcard-run[disabled] { opacity: 0.5; cursor: default; }
  .evcc-pcard-empty { color: var(--secondary-text-color); font-size: 0.9rem; padding: 8px 0; }

  /* "Runs As" step manifest — class names match the shared renderStepsManifest
     output. Tokens fall back panel-theme → HA var → hardcoded so the manifest
     styles even on a cold dashboard with no panel loaded (aliased to distinct
     names to avoid a self-referential custom-property cycle). */
  .evcc-pcard-manifest {
    --_seq-primary:   var(--evcc-text-primary,   var(--primary-text-color, #212121));
    --_seq-secondary: var(--evcc-text-secondary, var(--secondary-text-color, #727272));
    --_seq-muted:     var(--evcc-text-muted,     var(--disabled-text-color, #9e9e9e));
    --_seq-surface:   var(--evcc-surface-input,  var(--secondary-background-color, #e8e8e8));
  }
  .evcc-run-profiles-sequence { display: flex; flex-direction: column; gap: 6px; }
  .evcc-run-profiles-label {
    font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.06em; color: var(--_seq-muted);
  }
  .evcc-run-profiles-seq-list {
    list-style: none; margin: 0; padding: 0; display: flex;
    flex-direction: column; gap: 4px; counter-reset: evcc-seq;
  }
  .evcc-run-profiles-seq-step {
    display: flex; align-items: center; gap: 6px;
    font-size: 0.78rem; color: var(--_seq-secondary);
  }
  .evcc-run-profiles-seq-step::before {
    counter-increment: evcc-seq; content: counter(evcc-seq);
    flex: 0 0 auto; width: 16px; height: 16px; display: inline-flex;
    align-items: center; justify-content: center; border-radius: 50%;
    font-size: 0.62rem; font-weight: 700;
    color: var(--_seq-muted); background: var(--_seq-surface);
  }
  .evcc-run-profiles-seq-step--charge,
  .evcc-run-profiles-seq-step--wait { color: var(--_seq-primary); font-weight: 600; }
  .evcc-run-profiles-seq-kind { font-weight: 700; color: var(--_seq-primary); }
  .evcc-run-profiles-seq-mode {
    font-size: 0.64rem; text-transform: uppercase; letter-spacing: 0.05em;
    padding: 1px 5px; border-radius: 999px;
    color: var(--_seq-muted); background: var(--_seq-surface);
  }
`;

class VacuumAgentProfileCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
    this._library = null;       // { profile_id: enriched-profile } for the vacuum/map
    this._fetchedFor = null;    // "vac|map" key the current _library belongs to
    this._fetching = false;
    this._running = false;
    this._langOverride = "auto";
    this._langLoaded = false;
  }

  setConfig(config) {
    this._config = config ?? {};
    this._fetchedFor = null;    // re-fetch for the new vacuum/map
    this._library = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._maybeLoadLang();
    ensureLocalesLoaded(() => this._render());
    this._ensureData();
    this._render();
  }

  _maybeLoadLang() {
    if (this._langLoaded || !this._hass) return;
    this._langLoaded = true;
    getStoredLang(this._hass).then((code) => {
      if (code == null || code === this._langOverride) return;
      this._langOverride = code;
      this._render();
    });
  }

  t(key, vars) { return translate(resolveLang(this._hass, this._config, this._langOverride), key, vars); }

  _vacuumId() { return this._config?.vacuum_entity_id ?? null; }
  _mapId() { return this._config?.map_id != null ? String(this._config.map_id) : null; }
  _profileId() { return this._config?.profile_id ?? null; }

  // Fetch the saved run profiles for the configured vacuum/map ONCE (storm-proof:
  // claim before the await; a failed fetch isn't retried every state tick). We read
  // the `library` dict (full enriched profiles WITH steps), not the `profiles`
  // summary array (no steps). get_saved_run_profiles REQUIRES map_id.
  async _ensureData() {
    const vid = this._vacuumId();
    const mid = this._mapId();
    const key = `${vid}|${mid}`;
    if (!this._hass || !vid || mid == null || this._fetching || this._fetchedFor === key) return;
    this._fetching = true;
    this._fetchedFor = key;
    try {
      const out = await callResponse(this._hass, DOMAIN, "get_saved_run_profiles", {
        vacuum_entity_id: vid,
        map_id: mid,
      });
      if (this._vacuumId() !== vid) return;  // config changed mid-flight
      this._library = out && typeof out.library === "object" && out.library ? out.library : {};
    } catch (_e) {
      this._library = {};
    } finally {
      this._fetching = false;
      this._render();
    }
  }

  _profile() {
    const pid = this._profileId();
    if (!pid || !this._library || typeof this._library !== "object") return null;
    return this._library[pid] ?? null;
  }

  // Room-id → name from the profile's OWN enriched arrays (parallel room_ids /
  // room_names). The steps only ever reference this profile's rooms, so no map
  // fetch is needed for the manifest labels.
  _nameById(profile) {
    const ids = Array.isArray(profile.room_ids) ? profile.room_ids : [];
    const names = Array.isArray(profile.room_names) ? profile.room_names : [];
    const map = {};
    ids.forEach((id, i) => { map[String(id)] = names[i]; });
    return map;
  }

  // Shared "Runs As" manifest — identical output to the full panel (same helper).
  _renderManifest(profile) {
    return renderStepsManifest({
      steps: profile.steps,
      nameById: this._nameById(profile),
      t: (key, vars) => this.t(key, vars),
      escapeHtml: esc,
    });
  }

  _render() {
    if (!this.shadowRoot) return;
    const style = `<style>${CARD_CSS}</style>`;

    if (!this._vacuumId() || !this._mapId() || !this._profileId()) {
      this.shadowRoot.innerHTML = `${style}<div class="evcc-pcard"><div class="evcc-pcard-empty">${this.t("profile_card.configure")}</div></div>`;
      return;
    }
    if (this._library == null) {
      this.shadowRoot.innerHTML = `${style}<div class="evcc-pcard"><div class="evcc-pcard-empty">${this.t("profile_card.loading")}</div></div>`;
      return;
    }
    const profile = this._profile();
    if (!profile) {
      this.shadowRoot.innerHTML = `${style}<div class="evcc-pcard"><div class="evcc-pcard-empty">${this.t("profile_card.not_found")}</div></div>`;
      return;
    }

    const roomCount = Number(profile.room_count ?? profile.room_ids?.length ?? 0);
    // exposed_as_button already carries its own leading "· " separator.
    const exposed = profile.expose_as_button
      ? ` ${this.t("run_profiles.exposed_as_button")}`
      : "";
    const roomNames = Array.isArray(profile.room_names) ? profile.room_names : [];

    this.shadowRoot.innerHTML = `
      ${style}
      <div class="evcc-pcard">
        <div class="evcc-pcard-name">${esc(profile.name ?? this.t("profile_card.untitled"))}</div>
        <div class="evcc-pcard-meta">${this.t("run_profiles.room_count", { count: esc(String(roomCount)) })}${exposed}</div>
        ${roomNames.length ? `<div class="evcc-pcard-meta-rooms">${esc(roomNames.join(", "))}</div>` : ""}
        <div class="evcc-pcard-manifest">${this._renderManifest(profile)}</div>
        <div class="evcc-pcard-footer">
          <button class="evcc-pcard-run" id="run-btn" ${this._running ? "disabled" : ""}>${this.t("run_profiles.run")}</button>
        </div>
      </div>
    `;
    this.shadowRoot.getElementById("run-btn")?.addEventListener("click", () => this._handleRun());
  }

  // Run = apply + start the profile through the protected path. No side effects
  // until pressed (the dispatch-arming safety pattern, trivial for one action).
  async _handleRun() {
    if (this._running || !this._hass) return;
    const vid = this._vacuumId();
    const mid = this._mapId();
    const pid = this._profileId();
    if (!vid || mid == null || !pid) return;
    this._running = true;
    this._render();
    try {
      await this._hass.callService(DOMAIN, "start_run_profile", {
        vacuum_entity_id: vid,
        map_id: mid,
        profile_id: pid,
      });
    } finally {
      this._running = false;
      this._render();
    }
  }

  getCardSize() { return 3; }

  static getConfigElement() { return document.createElement(CARD_EDITOR); }

  static getStubConfig(hass) {
    const states = hass?.states ?? {};
    const vacuum = Object.keys(states).find((id) => id.startsWith("vacuum.")) ?? "";
    // Pre-fill the vacuum's first managed map (from a room switch) so a fresh card
    // only needs the profile picked. profile_id stays empty (user chooses).
    const firstMap = Object.entries(states).find(
      ([id, s]) => id.startsWith("switch.") &&
        s.attributes?.vacuum_entity_id === vacuum && s.attributes?.map_id != null
    );
    return {
      vacuum_entity_id: vacuum,
      map_id: firstMap ? String(firstMap[1].attributes.map_id) : "",
      profile_id: "",
    };
  }
}

// Visual config editor — vacuum → map → profile cascade (NO YAML). Vacuum + map
// dropdowns are derived client-side from the managed room switches; the profile
// dropdown is fetched live via get_saved_run_profiles for the picked vacuum/map.
class VacuumAgentProfileCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = {};
    this._profiles = null;        // [{id,name}] for the current vac|map (null = loading)
    this._profFetchedFor = null;  // "vac|map" the current _profiles belong to
    this._profFetching = false;
  }

  setConfig(config) { this._config = config ?? {}; this._ensureProfiles(); this._render(); }

  set hass(hass) {
    this._hass = hass;
    ensureLocalesLoaded(() => this._render());
    this._ensureProfiles();
    this._render();
  }

  t(key, vars) { return translate(resolveLang(this._hass, this._config), key, vars); }

  _vacuumEntities() {
    if (!this._hass) return [];
    return Object.keys(this._hass.states).filter((id) => id.startsWith("vacuum.")).sort();
  }

  // Maps for a vacuum come from the managed room switches (attrs.vacuum_entity_id +
  // attrs.map_id), the same client-side source the dashboard card uses. Labels
  // prefer attrs.map_name, else "Map {id}".
  _mapsForVacuum(vid) {
    if (!this._hass || !vid) return [];
    const seen = new Map();
    for (const [eid, s] of Object.entries(this._hass.states)) {
      if (!eid.startsWith("switch.")) continue;
      const a = s?.attributes;
      if (!a || a.vacuum_entity_id !== vid || a.map_id == null) continue;
      const id = String(a.map_id);
      if (!seen.has(id)) seen.set(id, a.map_name ?? null);
    }
    return [...seen.entries()]
      .map(([id, name]) => ({ id, name: name || `Map ${id}` }))
      .sort((x, y) => x.id.localeCompare(y.id, undefined, { numeric: true }));
  }

  _mid() {
    return this._config.map_id != null && this._config.map_id !== "" ? String(this._config.map_id) : null;
  }

  // Fetch the profiles for the picked vacuum/map ONCE per pair (loading→null).
  async _ensureProfiles() {
    const vid = this._config.vacuum_entity_id;
    const mid = this._mid();
    const key = `${vid}|${mid}`;
    if (!this._hass || !vid || mid == null || this._profFetching || this._profFetchedFor === key) return;
    this._profFetching = true;
    this._profFetchedFor = key;
    this._profiles = null;
    try {
      const out = await callResponse(this._hass, DOMAIN, "get_saved_run_profiles",
        { vacuum_entity_id: vid, map_id: mid });
      this._profiles = Array.isArray(out?.profiles) ? out.profiles : [];
    } catch (_e) {
      this._profiles = [];
    } finally {
      this._profFetching = false;
      this._render();
    }
  }

  _fire(config) {
    this._config = config;
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
    this._ensureProfiles();
    this._render();
  }

  _render() {
    if (!this.shadowRoot) return;
    const vacuums = this._vacuumEntities();
    const selVac = this._config.vacuum_entity_id ?? "";
    const maps = selVac ? this._mapsForVacuum(selVac) : [];
    const selMap = this._mid() ?? "";
    const selProf = this._config.profile_id ?? "";
    const profReady = selMap && this._profFetchedFor === `${selVac}|${selMap}` && Array.isArray(this._profiles);

    const opt = (value, label, selected) =>
      `<option value="${esc(value)}" ${value === selected ? "selected" : ""}>${esc(label)}</option>`;

    const profileField = () => {
      if (!selMap) {
        return `<select id="profile" disabled><option>${esc(this.t("profile_card.editor_pick_profile"))}</option></select>`;
      }
      if (!profReady) {
        return `<select id="profile" disabled><option>${esc(this.t("profile_card.loading"))}</option></select>`;
      }
      if (!this._profiles.length) {
        return `<select id="profile" disabled><option>${esc(this.t("profile_card.editor_no_profiles"))}</option></select>`;
      }
      return `<select id="profile">
        <option value="" disabled ${!selProf ? "selected" : ""}>${esc(this.t("profile_card.editor_pick_profile"))}</option>
        ${this._profiles.map((p) => opt(p.id, p.name || p.id, selProf)).join("")}
      </select>`;
    };

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; font-family: var(--paper-font-body1_-_font-family, sans-serif); }
        .field { display: flex; flex-direction: column; gap: 4px; margin-bottom: 16px; }
        label { font-size: 0.80rem; font-weight: 500; color: var(--secondary-text-color, #888); text-transform: uppercase; letter-spacing: 0.04em; }
        select {
          width: 100%; box-sizing: border-box; padding: 8px 10px;
          border: 1px solid var(--divider-color, rgba(255,255,255,0.12)); border-radius: 6px;
          background: var(--card-background-color, #1c2127); color: var(--primary-text-color, #f0f2f5);
          font-size: 0.92rem; appearance: none; -webkit-appearance: none;
        }
        select[disabled] { opacity: 0.6; }
        .hint { font-size: 0.75rem; color: var(--secondary-text-color, #888); margin-top: 2px; }
      </style>

      <div class="field">
        <label>${this.t("room_card.editor_vacuum_label")}</label>
        <select id="vacuum">
          <option value="" disabled ${!selVac ? "selected" : ""}>${esc(this.t("room_card.editor_pick_vacuum"))}</option>
          ${vacuums.map((v) => opt(v, v, selVac)).join("")}
        </select>
      </div>

      <div class="field">
        <label>${this.t("profile_card.editor_map_label")}</label>
        <select id="map" ${!selVac ? "disabled" : ""}>
          <option value="" disabled ${!selMap ? "selected" : ""}>${esc(this.t("profile_card.editor_pick_map"))}</option>
          ${maps.map((m) => opt(m.id, m.name, selMap)).join("")}
        </select>
        ${selVac && !maps.length ? `<div class="hint">${esc(this.t("profile_card.editor_no_maps"))}</div>` : ""}
      </div>

      <div class="field">
        <label>${this.t("profile_card.editor_profile_label")}</label>
        ${profileField()}
      </div>
    `;

    this.shadowRoot.getElementById("vacuum")?.addEventListener("change", (e) => {
      this._fire({ ...this._config, vacuum_entity_id: e.target.value, map_id: "", profile_id: "" });
    });
    this.shadowRoot.getElementById("map")?.addEventListener("change", (e) => {
      this._fire({ ...this._config, map_id: e.target.value, profile_id: "" });
    });
    this.shadowRoot.getElementById("profile")?.addEventListener("change", (e) => {
      this._fire({ ...this._config, profile_id: e.target.value });
    });
  }
}

defineCard(CARD_NAME, VacuumAgentProfileCard);
defineCard(CARD_EDITOR, VacuumAgentProfileCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: CARD_NAME,
  name: "Vacuum Agent Profile Card",
  description: "Inspect and run one saved run profile (shows its step sequence).",
});

export { VacuumAgentProfileCard, VacuumAgentProfileCardEditor };
