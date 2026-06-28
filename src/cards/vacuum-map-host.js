// <eufy-vacuum-map> — the embeddable FULL map host (W2b).
//
// Mounts the EXISTING map subsystem (the same VacuumCardState / Renderers / Bindings
// / Actions classes the panel uses) on a small, self-contained custom element, so the
// dashboard card shows the VA-rendered room-blob map with rotate / pan / zoom /
// overlays / zone-draw — reusing every line of the map code rather than rewriting it.
//
// This module statically imports that heavy class graph; the dashboard card loads it
// ONLY via a dynamic import of this bundle's served URL when show_map is on, so the
// always-loaded cards bundle stays lean.
//
// The host provides exactly the surface the map renderer + bindings + actions reach:
// shadowRoot, _on/_onAll (applyCardDomHelpers), _state/_renderers/_actions/_bindings,
// _scheduleRender, _view, setView (stub), showToast, the transient scratch flags, and
// the two frame pollers. isMapViewActive is forced true INSTANCE-locally (never
// setMapViewActive — that writes the panel's localStorage).

import { VacuumCardState } from "../state/index.js";
import { VacuumCardRenderers } from "../renderers/index.js";
import { VacuumCardBindings } from "../bindings/index.js";
import { VacuumCardActions } from "../actions/index.js";
import { applyCardDomHelpers } from "../bindings/core.js";
import { VIEWS } from "../render-cycle.js";
import { mapStyles } from "../styles/map.js";

const ANIMAL_SVG_URL = "/eufy_vacuum/frontend/animal-svg/manifest.js";
let _animalSvgLoaded = false;

// The panel lays the map + its control panels out in a 2-column workspace; the narrow
// embedded card stacks them vertically instead (map on top, controls below).
const EMBED_CSS = `
  .evcc-map-embed { display: flex; flex-direction: column; gap: 10px; }
  .evcc-map-embed-controls { display: flex; flex-direction: column; gap: 10px; }
  .evcc-map-embed-controls:empty { display: none; }
  .map-mascot-bar { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .map-collapse-head { display: flex; align-items: center; gap: 8px; width: 100%; cursor: pointer; background: transparent; border: none; padding: 6px 4px; color: var(--evcc-text-muted, rgba(240,242,245,0.48)); font: 600 0.72rem/1.4 sans-serif; text-transform: uppercase; letter-spacing: 0.05em; }
  .map-collapse-chev { margin-left: auto; transition: transform 150ms ease; }
  .map-collapse:not(.is-collapsed) .map-collapse-chev { transform: rotate(180deg); }
  .map-collapse .evcc-map-layers-title { display: none; }
`;

class EufyVacuumMap extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    applyCardDomHelpers(this);   // installs $, $all, _on, _onAll (idempotent binder)
    this._hass = null;
    this._config = null;
    this._view = VIEWS.ROOMS;
    this._renderScheduled = false;
    this._layersCollapsed = true;   // the layers checklist folds by default
    // Transient scratch flags the map bindings read/write on the host.
    this._mapDragOccurred = false;
    this._mapVariantDeleteArmTimer = null;
    this._furnishedGestureActive = false;
    this._renderDataMapId = null;
    this._vaRenderFetching = false;
    this._vaImageCache = new Map();
    this._scrimCache = null;
  }

  /* =========================================================
     INPUTS — the parent dashboard card drives these
     ========================================================= */

  set config(c) {
    this._config = c;
    if (this._state) this._state.sync(this._hass, c);
    else this._initStack();
    this._scheduleRender();
  }

  set hass(h) {
    this._hass = h;
    if (this._state) {
      this._state.sync(h, this._config);
      this._actions?.sync?.(h, this._state);
    } else if (this._config) {
      this._initStack();
    }
    this._scheduleRender();
    this._scheduleLiveMapRefresh();
    this._scheduleLivePosePoll();
  }

  // The parent already fetched get_dashboard_snapshot — push it in (no duplicate fetch).
  setSnapshot(payload) {
    if (payload && this._state?.setDashboardSnapshot) {
      this._state.setDashboardSnapshot(payload);
      this._maybeDefaultVaRender();   // supports_va_render is known only after the snapshot
      this._scheduleRender();
      this._scheduleLiveMapRefresh();
      this._scheduleLivePosePoll();
    }
  }

  // Prefer the VA-rendered room-blob backdrop when the brand supports it (the clean
  // look, not the raw camera image); the user can still toggle it in the map. Once.
  _maybeDefaultVaRender() {
    if (this._vaDefaulted || !this._state) return;
    try {
      if (this._state.supportsVaRender?.() && this._state.useVaRender
          && !this._state.useVaRender() && this._state.setUseVaRender) {
        this._state.setUseVaRender(true);
      }
    } catch { /* best-effort default */ }
    this._vaDefaulted = true;
  }

  _initStack() {
    if (this._state || !this._config) return;
    this._state = new VacuumCardState(this._hass, this._config);
    this._renderers = new VacuumCardRenderers(this);
    this._actions = new VacuumCardActions(this._hass, this._state);
    this._bindings = new VacuumCardBindings(this);
    // The embedded map is ALWAYS the active map view — force it instance-locally so
    // the map gates fire, WITHOUT writing the panel's per-vacuum localStorage key.
    this._state.isMapViewActive = () => true;
  }

  /* =========================================================
     HOST SHIM — methods the map bindings call on the host
     ========================================================= */

  _scheduleRender() {
    if (this._furnishedGestureActive) return;   // don't interrupt an alignment drag
    if (this._renderScheduled) return;
    this._renderScheduled = true;
    Promise.resolve().then(() => { this._renderScheduled = false; this._render(); });
  }

  // The embedded map never opens the composer / map-config view.
  setView() { /* no-op */ }

  showToast(message, opts = {}) {
    if (!this._state?.pushToast) return null;
    const id = this._state.pushToast(message, opts);
    this._scheduleRender();
    const ttl = Number.isFinite(opts?.ttl) ? Math.max(1000, opts.ttl) : 3500;
    setTimeout(() => this._scheduleRender(), ttl + 80);
    return id;
  }

  /* =========================================================
     FRAME POLLERS — copied from main.js (self-contained on _state/_actions)
     ========================================================= */

  _scheduleLiveMapRefresh() {
    const REFRESH_MS = 2000;
    const liveCamera =
      !!this._state?.isMapViewActive?.() &&
      !!this._state?.isLiveBackdropActive?.() &&
      !!this._state?.liveMapImageEntity?.()?.startsWith?.("camera.");
    if (!liveCamera) {
      if (this._liveMapRefreshTimer) { clearInterval(this._liveMapRefreshTimer); this._liveMapRefreshTimer = null; }
      return;
    }
    if (this._liveMapRefreshTimer) return;
    this._liveMapRefreshTimer = setInterval(() => {
      if (!this._state?.isMapViewActive?.() || !this._state?.isLiveBackdropActive?.()) {
        clearInterval(this._liveMapRefreshTimer); this._liveMapRefreshTimer = null; return;
      }
      if (document.hidden) return;
      this._state.bumpLiveMapTick?.();
      this._scheduleRender();
    }, REFRESH_MS);
  }

  _scheduleLivePosePoll() {
    const REFRESH_MS = 2000;
    const wantPoll =
      !this._livePoseUnsupported &&
      !!this._state?.isMapViewActive?.() &&
      !!this._state?.overlaysAligned?.() &&
      !!this._state?.mapStateSource?.()?.present;
    if (!wantPoll) {
      if (this._livePosePollTimer) { clearInterval(this._livePosePollTimer); this._livePosePollTimer = null; }
      return;
    }
    if (this._livePosePollTimer) return;
    const tick = async () => {
      if (this._livePoseUnsupported || !this._state?.isMapViewActive?.() || !this._state?.overlaysAligned?.()) {
        clearInterval(this._livePosePollTimer); this._livePosePollTimer = null; return;
      }
      if (document.hidden) return;
      try {
        const resp = await this._actions?.getMapLivePose?.();
        if (resp == null) return;
        if (resp.present === false && resp.reason === "not_configured") {
          this._livePoseUnsupported = true;
          this._state?.setLivePose?.(null);
          clearInterval(this._livePosePollTimer); this._livePosePollTimer = null;
          this._scheduleRender();
          return;
        }
        this._state?.setLivePose?.(resp);
        this._scheduleRender();
      } catch { /* transient WS drop — keep last pose, retry next tick */ }
    };
    this._livePosePollTimer = setInterval(tick, REFRESH_MS);
    tick();
  }

  /* =========================================================
     LIFECYCLE
     ========================================================= */

  connectedCallback() {
    this._loadAnimalSvg();
    this._scheduleRender();
    this._scheduleLiveMapRefresh();
    this._scheduleLivePosePoll();
  }

  disconnectedCallback() {
    if (this._liveMapRefreshTimer) { clearInterval(this._liveMapRefreshTimer); this._liveMapRefreshTimer = null; }
    if (this._livePosePollTimer) { clearInterval(this._livePosePollTimer); this._livePosePollTimer = null; }
  }

  _loadAnimalSvg() {
    if (_animalSvgLoaded) return;
    _animalSvgLoaded = true;
    import(ANIMAL_SVG_URL).then(() => this._scheduleRender()).catch(() => { /* mascot renders empty */ });
  }

  /* =========================================================
     RENDER — the map fragment + its bindings, in our own shadowRoot
     ========================================================= */

  _render() {
    if (!this._hass || !this._config || !this._state || !this._renderers) return;
    const state = this._state;
    const r = this._renderers;
    // Minimal ctx — renderMapRoomView only reads ctx.{state,vacuumStatus} + this.* helpers.
    const ctx = { card: this, state, renderers: r, vacuumStatus: state.vacuumState?.() ?? "unknown" };
    try {
      const map = r.renderMapRoomView(ctx);
      // The map's CONTROL panels render in the panel's sidebar column, NOT inside
      // renderMapRoomView — bring them in (stacked under the map for the narrow card):
      //   - the ZONE panel (settings + drawn-zone list + Clean/Clear) when draw mode is on,
      //   - the render-LAYERS panel (VA-render toggle + overlay visibility) when overlays align.
      // Same gates + signatures as renderers/rooms.js; _bindMap (below) wires both.
      const mascot = (state.isMapViewActive?.() && typeof r._renderMapAnimalControls === "function")
        ? `<div class="map-mascot-bar">${r._renderMapAnimalControls(state)}</div>`
        : "";
      const zonePanel =
        (state.isMapViewActive?.() && (state.canDrawZone?.() ?? false) && (state.zoneDrawMode?.() ?? false))
          ? r._renderZonePanel(state, state.zoneDrafts?.() ?? [], state.zoneCount?.() ?? 0, state.zoneMax?.() ?? 10)
          : "";
      const layersPanel =
        (state.isMapViewActive?.() && (state.overlaysAligned?.() ?? false) && typeof r._renderMapLayersPanel === "function")
          ? r._renderMapLayersPanel(state)
          : "";
      // The layers panel folds behind a collapse header (it's a tall checklist).
      const layersSection = layersPanel ? `
        <div class="map-collapse ${this._layersCollapsed ? "is-collapsed" : ""}">
          <button class="map-collapse-head" id="map-layers-toggle" aria-expanded="${!this._layersCollapsed}">
            <span>${r.t("map.layers_title")}</span><span class="map-collapse-chev">▾</span>
          </button>
          ${this._layersCollapsed ? "" : layersPanel}
        </div>` : "";
      this.shadowRoot.innerHTML =
        `<style>:host{display:block}${mapStyles}${EMBED_CSS}</style>` +
        `<div class="evcc-map-embed">${map}` +
        `<div class="evcc-map-embed-controls">${mascot}${zonePanel}${layersSection}</div></div>`;
      this._bindings._bindMap();
      // Host-added collapse toggle (not a map binding); wire after _bindMap. Fresh
      // element each render (innerHTML wipe) so addEventListener never double-binds.
      const lt = this.shadowRoot.getElementById("map-layers-toggle");
      if (lt) lt.addEventListener("click", () => { this._layersCollapsed = !this._layersCollapsed; this._scheduleRender(); });
    } catch (err) {
      console.error("[eufy-vacuum-map] render failed", err);
    }
  }
}

if (!customElements.get("eufy-vacuum-map")) {
  customElements.define("eufy-vacuum-map", EufyVacuumMap);
}

export { EufyVacuumMap };
