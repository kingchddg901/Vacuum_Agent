// Root custom element for the Eufy Vacuum Command Center Lovelace card.

import { CARD_NAME, CARD_VERSION }            from "./constants.js";
import { VacuumCardState }                    from "./state/index.js";
import { VacuumCardRenderers }                from "./renderers/index.js";
import { VacuumCardBindings }                 from "./bindings/index.js";
import { VacuumCardActions }                  from "./actions/index.js";
import { applyCardDomHelpers }                from "./bindings/core.js";
import { buildRenderContext, renderHeader, renderView, VIEW_ORDER, VIEWS } from "./render-cycle.js";
import { STYLES, MODAL_HOST_STYLES }          from "./styles/index.js";
import { applyThemeToCard }                   from "./styles/apply-theme.js";

import { LearningController }                 from "./controllers/learning-controller.js";

/* =========================================================
   CARD CLASS
   ========================================================= */

class EufyVacuumCommandCenter extends HTMLElement {

  constructor() {
    super();
    this.attachShadow({ mode: "open" });

    this._hass      = null;
    this._config    = null;
    this._state     = null;
    this._renderers = null;
    this._bindings  = null;
    this._actions   = null;
    this._view      = VIEWS.ROOMS;
    this._renderScheduled      = false;
    this._deferredRenderTimer  = null;
    this._startStatusTimer     = null;
    this._dashboardSnapshotTimer = null;
    this._dockActionStatusTimer = null;
    this._pauseTimeoutSettingsTimer = null;
    this._metricsTimer = null;
    this._learningHistoryTimer = null;
    this._runProfilesTimer = null;
    this._incompleteRunLogTimer = null;
    this._incompleteRunLogLoaded = false;
    this._troubleRoomsLogTimer = null;
    this._troubleRoomsLogLoaded = false;
    this._themeLibrary = {};
    this._modalHost = null;
    this._lastLoadedRoomEstimateMapId = null;
    this._lastLoadedRoomEstimateVacuumEntityId = null;
    this._themeLoaded = false;
    this._setupStatusTimer = null;

    this._learningController = null;

    // Mobile overflow ("More") sheet visibility. Toggled by the bottom
    // nav's More button and closed by backdrop tap or sheet-item tap.
    // Only consulted by render when isMobileViewport() is true.
    this._mobileMoreOpen = false;

    // Optional card-config override for mobile shell. Set by setConfig
    // when the user has `mobile_shell: true | false` in YAML. When
    // explicit, suppresses width-based viewport detection so the
    // user's choice sticks across resizes.
    this._mobileShellOverride = "auto";

    /* =====================================================
       PANEL RESUME HANDLERS
       Bound once so add/remove are symmetric.
       ===================================================== */
    this._boundHandleVisibilityChange  = () => this._handleVisibilityChange();
    this._boundHandlePanelResume       = () => this._handlePanelResume();
    this._boundHandleLocationChanged   = () => this._handlePanelResume();
    this._boundHandlePageShow          = (e) => { if (e.persisted) this._handlePanelResume(); };

    /* =====================================================
       VIEWPORT HANDLER
       ResizeObserver on the card host itself, not the window.
       Lovelace can embed this card in a grid cell narrower than
       the browser viewport — window.innerWidth lies in that case.
       Observing `this` (the custom-element host) gives us the
       actual rendered card width, which is what the layout
       decision should be based on.

       Debounced via setViewportFromWidth's own change-detection
       (it returns false when the mobile/desktop boundary isn't
       crossed). Re-renders only when the boundary actually changes.
       ===================================================== */
    this._resizeObserver = null;
    this._boundHandleResize = (entries) => {
      if (!this._state) return;
      // Honor the config override even on resize.
      if (this._mobileShellOverride === true || this._mobileShellOverride === false) return;
      const width = (entries?.[0]?.contentRect?.width)
                    ?? this.getBoundingClientRect().width
                    ?? window.innerWidth;
      if (this._state.setViewportFromWidth(width)) {
        this._scheduleRender();
      }
    };

    applyCardDomHelpers(this);
  }

  /**
   * Best-effort measurement of the card's own rendered width.
   * Falls back to the window's innerWidth if the card isn't
   * laid out yet (first-mount race). Used for initial viewport
   * detection before the ResizeObserver fires.
   */
  _measureCardWidth() {
    const rect = this.getBoundingClientRect?.();
    if (rect && rect.width > 0) return rect.width;
    return (typeof window !== "undefined") ? window.innerWidth : 1024;
  }

  /**
   * Apply card configuration. Called by HA after the card is placed or the config is edited.
   * @param {object} config - Lovelace card config; must include vacuum_entity_id.
   */
  setConfig(config) {
    if (!config?.vacuum_entity_id) {
      throw new Error(
        "[eufy-vacuum-command-center] vacuum_entity_id is required in card config."
      );
    }

    this._config = config;
    this._themeLibrary = config.theme_library ?? {};
    this._themeLoaded = false;

    if (this._state) {
      this._state.sync(this._hass, config);
    } else {
      this._state = new VacuumCardState(this._hass, config);
      // Seed viewport before first render. setConfig runs before the
      // element is necessarily in the DOM, so getBoundingClientRect
      // may return 0; falls back to window.innerWidth in that case.
      // connectedCallback + ResizeObserver correct this once layout
      // settles.
      this._state.setViewportFromWidth(this._measureCardWidth());
    }

    // Honor explicit mobile_shell override from card config. Useful
    // for previewing the mobile layout without resizing the window
    // or fighting the HA app's WebView cache:
    //   mobile_shell: true   → always render mobile shell
    //   mobile_shell: false  → always render desktop shell
    //   mobile_shell: "auto" → width-based detection (default)
    if (config.mobile_shell === true) {
      this._state.setViewport("mobile");
    } else if (config.mobile_shell === false) {
      this._state.setViewport("desktop");
    }
    this._mobileShellOverride = config.mobile_shell;

    if (!this._renderers) {
      this._renderers = new VacuumCardRenderers(this);
    }

    if (!this._actions) {
      this._actions = new VacuumCardActions(this._hass, this._state);
    } else {
      this._actions.sync?.(this._hass, this._state);
    }

    if (!this._bindings) {
      this._bindings = new VacuumCardBindings(this);
    }

    if (!this._learningController) {
      this._learningController = new LearningController(this);
    }

    this._scheduleRender();
  }

  /** Panel mode setter — ha-panel-custom pushes config through this property. */
  set panel(panel) {
    this._panel = panel;
    if (panel?.config?.vacuum_entity_id) {
      this.setConfig(panel.config);
    }
  }

  set narrow(narrow) {
    this._narrow = narrow;
  }

  /**
   * HA hass setter — called on every state update.
   * Syncs all subsystems, refreshes scheduled data, and triggers a render.
   */
  set hass(hass) {
    this._hass = hass;

    if (this._state)   this._state.sync(hass, this._config);
    if (this._actions) this._actions.sync?.(hass, this._state);

    /* -----------------------------------------------------
       LIVE THEME SENSOR SYNC
       -----------------------------------------------------
       The integration is the source of truth for theme state.
       On every HA update we mirror the latest theme sensor
       attributes into card state so preview/render stays aligned
       with backend changes.
       ----------------------------------------------------- */
    if (this._config?.vacuum_entity_id && this._state) {
      const sensor = this._findThemeSensor(hass);
      if (sensor?.attributes) {
        this._state.setBackendThemeState?.(sensor.attributes);
      }
    }

    this._scheduleRender();
    this._scheduleStartStatusRefresh();
    this._scheduleDashboardSnapshotRefresh();
    this._scheduleDockActionStatusRefresh();
    this._schedulePauseTimeoutSettingsRefresh();
    this._scheduleMetricsRefresh();
    this._scheduleLearningHistoryRefresh();
    this._scheduleRunProfilesRefresh();
    this._scheduleIncompleteRunLogRefresh();
    this._scheduleTroubleRoomsLogRefresh();
    this._loadInitialThemeState();
  }

  getCardSize() {
    return 6;
  }

  static getStubConfig() {
    return {
      type:             `custom:${CARD_NAME}`,
      vacuum_entity_id: "vacuum.your_vacuum",
    };
  }

  /* =========================================================
     VIEW MANAGEMENT
     ========================================================= */
  setView(view) {
    if (view === VIEWS.MAPPING_ARCHIVE) {
      view = VIEWS.ROOMS;
    }

    if (this._view === view) return;
    this._view = view;
    if (view === VIEWS.LEARNING_REVIEW) {
      this._scheduleLearningHistoryRefresh();
    }
    if (view === VIEWS.METRICS) {
      this._scheduleMetricsRefresh();
    }
    if (view === VIEWS.BASE_STATION) {
      this._scheduleDockActionStatusRefresh();
      this._schedulePauseTimeoutSettingsRefresh();
    }
    if (view === VIEWS.ROOMS) {
      this._scheduleRunProfilesRefresh();
    }
    if (view === VIEWS.SETUP) {
      this._scheduleSetupStatusRefresh();
    }
    if (view === VIEWS.MAPPING_REVIEW) {
      this._scheduleMappingBoundsRefresh();
    }
    this._scheduleRender();
  }

  /* =========================================================
     START STATUS REFRESH
     ========================================================= */
  _scheduleStartStatusRefresh() {
    if (!this._state || !this._actions) return;

    clearTimeout(this._startStatusTimer);
    this._startStatusTimer = setTimeout(async () => {
      const vacuumEntityId = this._state.vacuumEntityId();
      const mapId          = this._state.activeMapId();
      if (!vacuumEntityId || !mapId) return;

      const result = await this._actions.callService(
        "eufy_vacuum",
        "get_start_status",
        { vacuum_entity_id: vacuumEntityId, map_id: mapId },
        true
      );

      const payload = result?.response ?? result;

      if (payload && this._state) {
        this._state._startStatus = payload;
        this._scheduleRender();
      }
    }, 800);
  }

  async refreshDashboardSnapshot() {
    if (!this._state || !this._actions) return null;

    const vacuumEntityId = this._state.vacuumEntityId();
    const mapId = this._state.activeMapId();
    if (!vacuumEntityId || !mapId) return null;

    const payload = await this._actions.getDashboardSnapshot({
      vacuum_entity_id: vacuumEntityId,
      map_id: mapId,
    });

    if (!payload || !this._state) return null;

    this._state.setDashboardSnapshot?.(payload);

    const startStatusPayload =
      payload?.job_control ??
      payload?.start_status ??
      null;

    if (startStatusPayload) {
      this._state._startStatus = startStatusPayload;
    }

    this._scheduleRender();
    return payload;
  }

  _scheduleDashboardSnapshotRefresh() {
    if (!this._state || !this._actions) return;

    clearTimeout(this._dashboardSnapshotTimer);
    this._dashboardSnapshotTimer = setTimeout(() => {
      this.refreshDashboardSnapshot();
    }, 500);
  }

  async refreshDockActionStatus() {
    if (!this._state || !this._actions) return null;

    const vacuumEntityId = this._state.vacuumEntityId();
    const mapId = this._state.activeMapId();
    if (!vacuumEntityId || !mapId) return null;

    const payload = await this._actions.getDockActionStatus({
      vacuum_entity_id: vacuumEntityId,
      map_id: mapId,
    });

    if (!payload || !this._state) return null;

    this._state.setDockActionStatus?.(payload);
    this._scheduleRender();
    return payload;
  }

  async refreshPauseTimeoutSettings() {
    if (!this._state || !this._actions) return null;

    const vacuumEntityId = this._state.vacuumEntityId();
    if (!vacuumEntityId) return null;

    const payload = await this._actions.getPauseTimeoutSettings({
      vacuum_entity_id: vacuumEntityId,
    });

    this._state.setPauseTimeoutSettings?.(payload);
    this._scheduleRender();
    return payload;
  }

  _schedulePauseTimeoutSettingsRefresh() {
    if (!this._state || !this._actions) return;

    clearTimeout(this._pauseTimeoutSettingsTimer);
    this._pauseTimeoutSettingsTimer = setTimeout(() => {
      this.refreshPauseTimeoutSettings();
    }, 350);
  }

  _scheduleDockActionStatusRefresh() {
    if (!this._state || !this._actions) return;

    clearTimeout(this._dockActionStatusTimer);
    this._dockActionStatusTimer = setTimeout(() => {
      this.refreshDockActionStatus();
    }, 600);
  }

  async refreshMetricsSnapshot() {
    if (!this._state || !this._actions) return null;

    const filters = this._state.metricsFilters?.() ?? {};
    const payload = await this._actions.getMetricsSnapshot({
      vacuum_entity_id: this._state.vacuumEntityId?.(),
      room_slug: filters.room_slug || undefined,
      profile_key: filters.profile_key || undefined,
      status: filters.status || undefined,
      used_for_learning:
        filters.used_for_learning === "true"
          ? true
          : filters.used_for_learning === "false"
            ? false
            : undefined,
    });

    if (!payload || !this._state) return null;

    this._state.setMetricsSnapshot?.(payload);
    this._scheduleRender();
    return payload;
  }

  _scheduleMetricsRefresh() {
    if (!this._state || !this._actions) return;
    if (this._view !== VIEWS.METRICS) return;

    clearTimeout(this._metricsTimer);
    this._metricsTimer = setTimeout(() => {
      this.refreshMetricsSnapshot();
    }, 500);
  }

  async refreshLearningHistorySnapshot() {
    if (!this._state || !this._actions) return null;

    const filters = this._state.learningHistoryFilters?.() ?? {};
    const payload = await this._actions.getLearningHistorySnapshot({
      vacuum_entity_id: this._state.vacuumEntityId?.(),
      room_slug: filters.room_slug || undefined,
      profile_key: filters.profile_key || undefined,
      status: filters.status || undefined,
      used_for_learning:
        filters.used_for_learning === "true"
          ? true
          : filters.used_for_learning === "false"
            ? false
            : undefined,
      limit: filters.limit,
    });

    if (!payload || !this._state) return null;

    this._state.setLearningHistorySnapshot?.(payload);
    this._scheduleRender();
    return payload;
  }

  _scheduleLearningHistoryRefresh() {
    if (!this._state || !this._actions) return;
    if (this._view !== VIEWS.LEARNING_REVIEW) return;

    clearTimeout(this._learningHistoryTimer);
    this._learningHistoryTimer = setTimeout(() => {
      this.refreshLearningHistorySnapshot();
    }, 500);
  }

  async refreshMappingBoundsSnapshot() {
    if (!this._state || !this._actions) return null;

    const payload = await this._actions.getMappingBoundsSnapshot?.();
    if (!payload || !this._state) return null;

    this._state.setMappingBoundsSnapshot?.(payload);
    this._scheduleRender();
    return payload;
  }

  _scheduleMappingBoundsRefresh() {
    if (!this._state || !this._actions) return;
    if (this._view !== VIEWS.MAPPING_REVIEW) return;

    clearTimeout(this._mappingBoundsTimer);
    this._mappingBoundsTimer = setTimeout(() => {
      this.refreshMappingBoundsSnapshot();
    }, 500);
  }

  async refreshRunProfiles() {
    if (!this._state || !this._actions) return null;
    if (this._view !== VIEWS.ROOMS) return null;

    const vacuumEntityId = this._state.vacuumEntityId();
    const mapId = this._state.activeMapId();
    if (!vacuumEntityId || !mapId) return null;

    const payload = await this._actions.getSavedRunProfiles({
      vacuum_entity_id: vacuumEntityId,
      map_id: mapId,
    });

    this._state.setRunProfilesLibrary?.(payload);
    this._scheduleRender();
    return payload;
  }

  async refreshRoomProfiles() {
    if (!this._state || !this._actions) return null;

    const payload = await this._actions.getRoomProfiles();
    if (!payload) return null;

    this._state.setRoomProfilesLibrary?.(payload);
    this._scheduleRender();
    return payload;
  }

  _scheduleRunProfilesRefresh() {
    if (!this._state || !this._actions) return;
    if (this._view !== VIEWS.ROOMS) return;

    clearTimeout(this._runProfilesTimer);
    this._runProfilesTimer = setTimeout(() => {
      this.refreshRunProfiles();
    }, 450);
  }

  async refreshIncompleteRunLog() {
    if (!this._state || !this._actions) return null;

    const vacuumEntityId = this._state.vacuumEntityId();
    if (!vacuumEntityId) return null;

    const payload = await this._actions.getIncompleteRunLog?.({
      vacuum_entity_id: vacuumEntityId,
    });

    this._incompleteRunLogLoaded = true;

    if (!this._state) return null;

    this._state.setIncompleteRunLog?.(payload ?? null);
    this._scheduleRender();
    return payload;
  }

  _scheduleIncompleteRunLogRefresh() {
    if (!this._state || !this._actions) return;
    if (this._incompleteRunLogLoaded) return;

    clearTimeout(this._incompleteRunLogTimer);
    this._incompleteRunLogTimer = setTimeout(() => {
      this.refreshIncompleteRunLog();
    }, 1200);
  }

  async refreshTroubleRoomsLog() {
    if (!this._state || !this._actions) return null;

    const vacuumEntityId = this._state.vacuumEntityId();
    if (!vacuumEntityId) return null;

    const payload = await this._actions.getTroubleRoomsLog?.({
      vacuum_entity_id: vacuumEntityId,
    });

    this._troubleRoomsLogLoaded = true;

    if (!this._state) return null;

    this._state.setTroubleRoomsLog?.(payload ?? null);
    this._scheduleRender();
    return payload;
  }

  _scheduleTroubleRoomsLogRefresh() {
    if (!this._state || !this._actions) return;
    if (this._troubleRoomsLogLoaded) return;

    clearTimeout(this._troubleRoomsLogTimer);
    this._troubleRoomsLogTimer = setTimeout(() => {
      this.refreshTroubleRoomsLog();
    }, 1400);
  }

  async refreshSetupStatus() {
    if (!this._state || !this._actions) return;

    this._state.setSetupLoading?.(true);
    this._scheduleRender();

    try {
      const payload = await this._actions.getSetupStatus?.();
      if (payload && this._state) {
        this._state.setSetupStatus?.(payload);
      }
    } finally {
      this._state.setSetupLoading?.(false);
      this._scheduleRender();
    }
  }

  _scheduleSetupStatusRefresh() {
    if (!this._state || !this._actions) return;
    if (this._view !== VIEWS.SETUP) return;

    clearTimeout(this._setupStatusTimer);
    this._setupStatusTimer = setTimeout(() => {
      this.refreshSetupStatus();
    }, 400);
  }

  /**
   * Find the theme state sensor for the configured vacuum.
   *
   * The expected entity ID is sensor.{objectId}_theme_state, but HA may
   * append a suffix (_2, _3 …) if there was a naming collision in the
   * entity registry. The sensor always exposes a vacuum_entity_id attribute,
   * so we fall back to scanning hass.states when the primary ID is absent.
   */
  _findThemeSensor(hass) {
    const vacuum = this._config?.vacuum_entity_id;
    if (!vacuum || !hass) return null;

    const objectId = vacuum.split(".")[1];
    const primaryId = `sensor.${objectId}_theme_state`;

    if (hass.states[primaryId]) return hass.states[primaryId];

    return (
      Object.values(hass.states).find(
        (s) =>
          s.entity_id.startsWith("sensor.") &&
          s.entity_id.includes("_theme_state") &&
          s.attributes?.vacuum_entity_id === vacuum
      ) ?? null
    );
  }

  /**
   * =========================================================
   * THEME INITIAL LOAD
   * =========================================================
   *
   * Loads theme state from:
   * - theme sensor (per-vacuum state)
   * - theme library (global)
   *
   * This replaces the old getThemeState() system.
   */
  async _loadInitialThemeState() {
    if (this._themeLoaded || !this._actions || !this._hass) return;

    const vacuum = this._config?.vacuum_entity_id;
    if (!vacuum) return;

    /* -------------------------------------------------------
       1. LOAD FROM THEME SENSOR (SOURCE OF TRUTH)
       ------------------------------------------------------- */
    const sensor = this._findThemeSensor(this._hass);
    if (sensor?.attributes) {
      this._state.setBackendThemeState?.(sensor.attributes);
    }

    /* -------------------------------------------------------
       2. LOAD THEME LIBRARY
       ------------------------------------------------------- */
    const library = await this._actions.getThemeLibrary();
    if (library) {
      this._state.setThemeLibrary?.(library);
    }

    this._themeLoaded = true;

    /* -------------------------------------------------------
       3. APPLY + RENDER
       ------------------------------------------------------- */
    applyThemeToCard(this);
    this._scheduleRender();
  }

  /* =========================================================
     RENDER SCHEDULING
     ========================================================= */
  _scheduleRender() {
    if (this._renderScheduled) return;
    this._renderScheduled = true;

    Promise.resolve().then(() => {
      this._renderScheduled = false;
      this._render();
    });
  }

  /**
   * Deferred render — used by theme controls (color pickers, alpha sliders,
   * text token inputs) so that badge / modified-indicator updates happen
   * after the user has finished interacting, not mid-gesture.
   *
   * Calling this while a picker is still open just resets the timer.
   * The render fires 600 ms after the last call with no further activity.
   */
  _scheduleDeferredRender() {
    if (this._deferredRenderTimer) {
      window.clearTimeout(this._deferredRenderTimer);
    }
    this._deferredRenderTimer = window.setTimeout(() => {
      this._deferredRenderTimer = null;
      this._scheduleRender();
    }, 600);
  }

  /* =========================================================
     RENDER
     ========================================================= */
  _render() {
    if (!this._config || !this._hass || !this._state || !this._renderers) return;

    applyThemeToCard(this);

    this._maybeLoadRoomEstimates();

    // Defensive viewport re-measurement at the start of every render.
    // ResizeObserver handles ongoing changes, but this guards against
    // initial-load lifecycle races (e.g. setConfig running before the
    // element is in the DOM, or HA reloading the card without
    // re-running setConfig). Uses the card's own width, not the
    // window, so Lovelace grid embeds get the right answer.
    //
    // If the user has explicitly overridden via mobile_shell config,
    // skip the width-based detection — keep their forced choice.
    if (this._mobileShellOverride !== true && this._mobileShellOverride !== false) {
      this._state.setViewportFromWidth?.(this._measureCardWidth());
    }

    const ctx = buildRenderContext(this);
    const focusSnapshot = this._captureShadowFocusState();
    const scrollSnapshot = this._captureShadowScrollState();
    const frame = this._ensureShellFrame(STYLES);
    const isMobile = this._state.isMobileViewport?.() ?? false;

    // Tag the shell so CSS can adjust spacing / fixed positioning
    // based on which chrome is active.
    const shellEl = this.shadowRoot.querySelector(".evcc-shell");
    if (shellEl) {
      shellEl.dataset.viewport = isMobile ? "mobile" : "desktop";
    }

    // Header content forks by viewport: desktop has nav tabs in the
    // header; mobile shows just vacuum name + status (nav is at the
    // bottom). Both compose from the same context object.
    const headerHtml = isMobile
      ? this._renderers.renderMobileHeader?.(ctx) ?? ""
      : renderHeader(ctx);

    let viewHtml;
    try {
      viewHtml = renderView(ctx);
    } catch (err) {
      console.error("[eufy-vacuum-command-center] renderView threw for view:", ctx.view, err);
      viewHtml = `<div class="evcc-empty">View error — check console (${ctx.view})</div>`;
    }

    // Mobile-only chrome regions: bottom nav and the overflow sheet
    // overlay. Empty strings on desktop so the regions exist but
    // render nothing.
    const bottomNavHtml = isMobile
      ? this._renderers.renderMobileBottomNav?.(ctx.view) ?? ""
      : "";
    const mobileOverlayHtml = isMobile
      ? this._renderers.renderMobileOverlay?.(ctx) ?? ""
      : "";

    if (frame.header.dataset.renderedHtml !== headerHtml) {
      frame.header.innerHTML = headerHtml;
      frame.header.dataset.renderedHtml = headerHtml;
    }

    if (frame.bottomNav && frame.bottomNav.dataset.renderedHtml !== bottomNavHtml) {
      frame.bottomNav.innerHTML = bottomNavHtml;
      frame.bottomNav.dataset.renderedHtml = bottomNavHtml;
    }

    if (frame.mobileOverlay && frame.mobileOverlay.dataset.renderedHtml !== mobileOverlayHtml) {
      frame.mobileOverlay.innerHTML = mobileOverlayHtml;
      frame.mobileOverlay.dataset.renderedHtml = mobileOverlayHtml;
    }

    frame.viewStage.dataset.view = ctx.view;

    Object.entries(frame.viewRoots).forEach(([viewName, root]) => {
      const isActive = viewName === ctx.view;
      root.hidden = !isActive;
      root.setAttribute("aria-hidden", isActive ? "false" : "true");
    });

    const activeViewRoot = frame.viewRoots[ctx.view];
    if (activeViewRoot && activeViewRoot.dataset.renderedHtml !== viewHtml) {
      activeViewRoot.innerHTML = viewHtml;
      activeViewRoot.dataset.renderedHtml = viewHtml;
    }

    this._updateModalHost();
    this._bindings?.bindEvents();
    this._restoreShadowFocusState(focusSnapshot);
    this._restoreShadowScrollState(scrollSnapshot);
  }

  _ensureShellFrame(styles) {
    let styleRoot = this.shadowRoot?.querySelector("[data-evcc-style-root]");
    let header = this.shadowRoot?.querySelector("[data-evcc-header-root]");
    let viewStage = this.shadowRoot?.querySelector("[data-evcc-view-stage]");
    let bottomNav = this.shadowRoot?.querySelector("[data-evcc-bottom-nav-root]");
    let mobileOverlay = this.shadowRoot?.querySelector("[data-evcc-mobile-overlay-root]");
    let viewRoots = this._collectViewRoots();

    // Treat the shell as missing if either of the new slots is absent
    // — happens on first mount and during HACS update when the frame
    // is reset. The mobile slots are always built; CSS hides them on
    // desktop based on the shell's data-viewport attribute.
    const missingFrame = !styleRoot || !header || !viewStage
      || !bottomNav || !mobileOverlay
      || Object.keys(viewRoots).length !== VIEW_ORDER.length;

    if (missingFrame) {
      this.shadowRoot.innerHTML = `
        <style data-evcc-style-root>${styles}</style>

        <ha-card>
          <div class="evcc-shell">
            <div data-evcc-header-root></div>
            <div class="evcc-view-stage" data-evcc-view-stage data-view="${this._view ?? VIEWS.ROOMS}">
              ${VIEW_ORDER.map((viewName) => `
                <div
                  class="evcc-view-root"
                  data-evcc-view-root="${viewName}"
                  ${viewName === (this._view ?? VIEWS.ROOMS) ? "" : "hidden"}
                  aria-hidden="${viewName === (this._view ?? VIEWS.ROOMS) ? "false" : "true"}"
                ></div>
              `).join("")}
            </div>
            <div data-evcc-bottom-nav-root></div>
            <div data-evcc-mobile-overlay-root></div>
          </div>
        </ha-card>
      `;

      styleRoot = this.shadowRoot?.querySelector("[data-evcc-style-root]");
      header = this.shadowRoot?.querySelector("[data-evcc-header-root]");
      viewStage = this.shadowRoot?.querySelector("[data-evcc-view-stage]");
      bottomNav = this.shadowRoot?.querySelector("[data-evcc-bottom-nav-root]");
      mobileOverlay = this.shadowRoot?.querySelector("[data-evcc-mobile-overlay-root]");
      viewRoots = this._collectViewRoots();
    } else if (styleRoot.textContent !== styles) {
      styleRoot.textContent = styles;
    }

    return {
      styleRoot,
      header,
      viewStage,
      bottomNav,
      mobileOverlay,
      viewRoots,
    };
  }

  _collectViewRoots() {
    if (!this.shadowRoot) return {};

    return VIEW_ORDER.reduce((roots, viewName) => {
      const root = this.shadowRoot.querySelector(`[data-evcc-view-root="${viewName}"]`);
      if (root instanceof HTMLElement) {
        roots[viewName] = root;
      }
      return roots;
    }, {});
  }

  /* =========================================================
     MODAL HOST
     ========================================================= */
  _updateModalHost() {
    const ctx = {
      state: this._state,
      renderers: this._renderers,
    };

    const roomEditorHtml =
      typeof this._renderers.renderRoomEditorModal === "function"
        ? this._renderers.renderRoomEditorModal(ctx)
        : "";

    const roomAccessHtml =
      typeof this._renderers.renderRoomAccessModal === "function"
        ? this._renderers.renderRoomAccessModal(ctx)
        : "";

    const roomEstimateHtml =
      typeof this._renderers.renderRoomEstimateModal === "function"
        ? this._renderers.renderRoomEstimateModal(ctx)
        : "";

    const orderModalHtml =
      typeof this._renderers.renderOrderSelectorModal === "function"
        ? this._renderers.renderOrderSelectorModal(ctx)
        : "";

    const maintenanceModalHtml =
      typeof this._renderers.renderMaintenanceItemModal === "function"
        ? this._renderers.renderMaintenanceItemModal(ctx)
        : "";

    const html = `${roomEditorHtml}${roomAccessHtml}${roomEstimateHtml}${orderModalHtml}${maintenanceModalHtml}`;

    if (!html) {
      if (this._modalHost) {
        this._modalHost.remove();
        this._modalHost = null;
      }
      return;
    }

    if (!this._modalHost) {
      this._modalHost = document.createElement("div");
      this._modalHost.className = "evcc-modal-host";
      document.body.appendChild(this._modalHost);
    }

    const modalMarkup = `<style>${MODAL_HOST_STYLES}</style>${html}`;
    if (this._modalHost.dataset.renderedHtml !== modalMarkup) {
      this._modalHost.innerHTML = modalMarkup;
      this._modalHost.dataset.renderedHtml = modalMarkup;
    }

    this._bindings?.bindModalHostEvents(this._modalHost);
  }

  /* =========================================================
     LIFECYCLE
     ========================================================= */

  connectedCallback() {
    this._learningController?.connect();

    // Load the animal-svg custom element + all animal definitions.
    // Done once per document lifetime (static flag). After all animals are
    // registered we schedule a re-render so any <animal-svg> elements that
    // were upgraded before the registry was populated get a fresh paint.
    this._loadAnimalSvg();

    // Panel mode: browsers throttle microtasks in background tabs, so the
    // Promise.resolve() render scheduling in _scheduleRender() may not fire
    // until HA pushes the next hass update. Attach resume listeners so we
    // recover immediately when the tab/window regains visibility without
    // waiting for a state push.
    document.addEventListener("visibilitychange", this._boundHandleVisibilityChange);
    window.addEventListener("focus", this._boundHandlePanelResume);
    window.addEventListener("location-changed", this._boundHandleLocationChanged);
    window.addEventListener("pageshow", this._boundHandlePageShow);

    // Initial viewport measurement. setConfig may have run before
    // connectedCallback (so _state already exists); re-measure now that
    // the element is in the document and laid out — getBoundingClientRect
    // returns real numbers, which is more accurate than setConfig's
    // window.innerWidth fallback.
    if (this._state) {
      this._state.setViewportFromWidth(this._measureCardWidth());
    }

    // ResizeObserver on the card host. Fires whenever the card's own
    // box dimensions change — whether from window resize, Lovelace
    // grid reflow, sidebar collapse, or anything else that shrinks
    // or grows our cell. Always fires once on observe() so initial
    // measurement is also covered.
    if (typeof ResizeObserver !== "undefined") {
      this._resizeObserver = new ResizeObserver(this._boundHandleResize);
      this._resizeObserver.observe(this);
    }

    // Schedule a render on (re)connection — panel navigation or initial mount
    // may happen before the first hass setter call in panel mode.
    this._scheduleRender();
  }

  /* =========================================================
     ANIMAL SVG MODULE LOADER
     =========================================================
     Dynamically imports /eufy_vacuum/frontend/animal-svg/manifest.js
     (served by the integration's static path) which:
       1. loads animal-svg.js (defines <animal-svg>)
       2. loads all animal definition modules in parallel
     Uses a class-level flag so the import fires only once even
     if multiple card instances exist or connectedCallback fires
     more than once.  After all animals are registered a render
     is scheduled to upgrade any elements already in the DOM.

     WHY served by the integration (not /local/www): textures got
     migrated for the same reason — assets in <config>/www/ exist
     only on the developer's machine; fresh installs 404'd silently
     and lost the feature. Shipping them inside the integration's
     frontend/ directory makes them available on every install.
     ========================================================= */

  _loadAnimalSvg() {
    if (EufyVacuumCommandCenter._animalSvgLoaded) return;
    EufyVacuumCommandCenter._animalSvgLoaded = true;
    import("/eufy_vacuum/frontend/animal-svg/manifest.js")
      .then(() => this._scheduleRender())
      .catch((err) =>
        console.warn("[eufy-vacuum-command-center] animal-svg load failed:", err)
      );
  }

  disconnectedCallback() {
    document.removeEventListener("visibilitychange", this._boundHandleVisibilityChange);
    window.removeEventListener("focus", this._boundHandlePanelResume);
    window.removeEventListener("location-changed", this._boundHandleLocationChanged);
    window.removeEventListener("pageshow", this._boundHandlePageShow);
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
      this._resizeObserver = null;
    }

    if (this._modalHost) {
      this._modalHost.remove();
      this._modalHost = null;
    }

    this._learningController?.disconnect();

    clearTimeout(this._startStatusTimer);
    clearTimeout(this._dashboardSnapshotTimer);
    clearTimeout(this._dockActionStatusTimer);
    clearTimeout(this._pauseTimeoutSettingsTimer);
    clearTimeout(this._metricsTimer);
    clearTimeout(this._learningHistoryTimer);
    clearTimeout(this._runProfilesTimer);
    clearTimeout(this._setupStatusTimer);
    clearTimeout(this._deferredRenderTimer);
    this._deferredRenderTimer = null;
  }

  _handleVisibilityChange() {
    if (document.visibilityState === "visible") {
      this._handlePanelResume();
    }
  }

  _handlePanelResume() {
    // offsetHeight read forces the browser to re-evaluate compositing layers,
    // fixing GPU blackout after aggressive background throttling (Windows sleep,
    // Chrome sleeping tabs).
    void this.offsetHeight;
    this._scheduleRender();
    this._scheduleDashboardSnapshotRefresh();
    this._scheduleStartStatusRefresh();
  }

  /* =========================================================
     ROOM ESTIMATE LOADING (UI TRIGGER)
     ========================================================= */
  _maybeLoadRoomEstimates() {
    const state = this._state;
    const controller = this._learningController;
    const config = this._config;

    if (!state || !controller || !config) return;

    const mapId = String(state.activeMapId?.() ?? "");
    const vacuumEntityId = String(config.vacuum_entity_id ?? "");

    if (!mapId || !vacuumEntityId) return;

    // Only load for Rooms view (prevents unnecessary calls)
    if (this._view !== VIEWS.ROOMS) return;

    const sameMap = mapId === String(this._lastLoadedRoomEstimateMapId ?? "");
    const sameVacuum = vacuumEntityId === String(this._lastLoadedRoomEstimateVacuumEntityId ?? "");

    if (sameMap && sameVacuum) return;

    controller.loadRoomEstimates();
    this._lastLoadedRoomEstimateMapId = mapId;
    this._lastLoadedRoomEstimateVacuumEntityId = vacuumEntityId;
  }

  /* =========================================================
     FOCUS RESTORATION
     ========================================================= */

  _captureShadowFocusState() {
    const active = this._getDeepActiveElement();
    if (!(active instanceof HTMLElement)) return null;

    const selector = this._buildFocusRestoreSelector(active);
    if (!selector) return null;

    const supportsSelection =
      active instanceof HTMLInputElement ||
      active instanceof HTMLTextAreaElement;

    return {
      selector,
      selectionStart: supportsSelection ? active.selectionStart : null,
      selectionEnd: supportsSelection ? active.selectionEnd : null,
      selectionDirection: supportsSelection ? active.selectionDirection : null,
    };
  }

  _getDeepActiveElement() {
    let active = document.activeElement;

    while (active?.shadowRoot?.activeElement) {
      active = active.shadowRoot.activeElement;
    }

    if (active instanceof HTMLElement && this.shadowRoot?.contains(active)) {
      return active;
    }

    const shadowActive = this.shadowRoot?.activeElement;
    if (shadowActive instanceof HTMLElement) {
      return shadowActive;
    }

    return null;
  }

  _restoreShadowFocusState(snapshot) {
    if (!snapshot?.selector || !this.shadowRoot) return;

    const target = this.shadowRoot.querySelector(snapshot.selector);
    if (!(target instanceof HTMLElement)) return;

    target.focus({ preventScroll: true });

    const supportsSelection =
      target instanceof HTMLInputElement ||
      target instanceof HTMLTextAreaElement;

    if (!supportsSelection) return;
    if (snapshot.selectionStart == null || snapshot.selectionEnd == null) return;

    try {
      target.setSelectionRange(
        snapshot.selectionStart,
        snapshot.selectionEnd,
        snapshot.selectionDirection ?? "none"
      );
    } catch (_) {
      // Some input types (for example color/range) do not support selection ranges.
    }
  }

  _buildFocusRestoreSelector(element) {
    const attrSelectors = [
      "data-theme-search",
      "data-theme-group-search",
      "data-theme-token",
      "data-theme-color-input",
      "data-theme-alpha",
      "data-rule-input",
      "data-rule-select",
      "data-rule-number-input",
      "data-theme-modified-only",
      "data-room-id",
      "data-rule-id",
    ];

    for (const attr of attrSelectors) {
      if (!element.hasAttribute(attr)) continue;
      const value = element.getAttribute(attr);
      const tagName = String(element.tagName || "").toLowerCase();
      const typeValue = element.getAttribute("type");
      const typeSelector = typeValue ? `[type="${CSS.escape(typeValue)}"]` : "";
      const classSelector = Array.from(element.classList || [])
        .filter(Boolean)
        .map((className) => `.${CSS.escape(className)}`)
        .join("");

      if (value == null || value === "") {
        return `${tagName}[${attr}]${typeSelector}${classSelector}`;
      }
      return `${tagName}[${attr}="${CSS.escape(value)}"]${typeSelector}${classSelector}`;
    }

    if (element.id) {
      return `#${CSS.escape(element.id)}`;
    }

    return null;
  }

  _captureShadowScrollState() {
    if (!this.shadowRoot) return [];

    const selectors = [
      ".evcc-view-stage",
      ".evcc-theme-editor-scrollbox",
      ".evcc-room-rules-content",
      ".evcc-rule-editor-body",
      ".evcc-rule-entity-search",
    ];

    return selectors.flatMap((selector) => {
      return Array.from(this.shadowRoot.querySelectorAll(selector)).map((element, index) => ({
        selector,
        index,
        scrollTop: element.scrollTop,
        scrollLeft: element.scrollLeft,
      }));
    });
  }

  _restoreShadowScrollState(snapshot = []) {
    if (!this.shadowRoot || !Array.isArray(snapshot) || !snapshot.length) return;

    snapshot.forEach((entry) => {
      const matches = this.shadowRoot.querySelectorAll(entry.selector);
      const target = matches?.[entry.index];
      if (!(target instanceof HTMLElement)) return;

      target.scrollTop = entry.scrollTop ?? 0;
      target.scrollLeft = entry.scrollLeft ?? 0;
    });
  }
}

/* =========================================================
   REGISTRATION
   ========================================================= */

// Class-level flag — animal-svg module is shared across all card instances.
EufyVacuumCommandCenter._animalSvgLoaded = false;

customElements.define(CARD_NAME, EufyVacuumCommandCenter);

