// Root custom element for the Eufy Vacuum Command Center Lovelace card.

import { CARD_NAME, CARD_VERSION }            from "./constants.js";
import { VacuumCardState }                    from "./state/index.js";
import { VacuumCardRenderers }                from "./renderers/index.js";
import { VacuumCardBindings }                 from "./bindings/index.js";
import { VacuumCardActions }                  from "./actions/index.js";
import { applyCardDomHelpers }                from "./bindings/core.js";
import { buildRenderContext, renderHeader, renderView, isViewAvailable, VIEW_ORDER, VIEWS } from "./render-cycle.js";
import { STYLES, MODAL_HOST_STYLES, TOAST_HOST_STYLES } from "./styles/index.js";
import { applyThemeToCard }                   from "./styles/apply-theme.js";
import { translate, resolveLang, loadLocale, ensureLocalesLoaded, localeSource, listBundledLocales, localeStatus } from "./i18n/index.js";
import { getStoredLang, setStoredLang }     from "./i18n/lang-store.js";

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

    // Language control state (the header globe). _langOverride is the per-user
    // choice ("auto" | locale code), loaded once from HA user-data; the menu
    // starts closed; _langOverrideLoaded is the one-shot load guard;
    // _langUserPicked blocks a late server read from clobbering a fresh
    // in-session pick (see _maybeLoadLangOverride / setLanguageOverride).
    this._langOverride = "auto";
    this._languageMenuOpen = false;
    this._langOverrideLoaded = false;
    this._langUserPicked = false;

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
    // ESC closes the topmost modal. One document-level listener;
    // bindModalHostEvents would re-attach on every modal render,
    // so we anchor it on connectedCallback instead and let the
    // modal host's close action handle the actual close logic.
    this._boundHandleKeydown = (e) => this._handleGlobalKeydown(e);
    // Re-render whenever a new animal registers so the animal companion
    // dropdown always reflects the live AnimalSVG registry. Bound per-
    // instance so it fires on the correct card regardless of which
    // instance triggered the manifest.js load (static flag means only
    // one instance fires _loadAnimalSvg().then(), but all instances need
    // the updated list).
    this._boundHandleAnimalRegistered  = () => this._scheduleRender();

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
    // Fallback panel mode: the integration registered this panel with an
    // empty config because no managed vacuum exists yet. Render a setup
    // placeholder pointing the user back to Settings → Devices & Services
    // → Vacuum Agent → Configure to add their vacuum. Don't init
    // any state machinery — there's no vacuum to bind to.
    if (!config?.vacuum_entity_id) {
      this._config = config ?? {};
      // setConfig runs before the first `set hass`, so the language isn't known
      // yet — the placeholder renders in English now and re-localizes once hass
      // (hence locale.language) arrives. Re-arm that one-shot here.
      this._placeholderLocalized = false;
      this._renderNoVacuumPlaceholder();
      return;
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
    // Note: setConfig now accepts empty config and renders a setup
    // placeholder instead of throwing, so pass through unconditionally.
    if (panel?.config !== undefined) {
      this.setConfig(panel.config);
    }
  }

  /**
   * Self-contained "no vacuum configured" placeholder. Rendered when the
   * integration's fallback panel ships an empty config to the card on
   * fresh installs. Doesn't touch the state machinery, theme system, or
   * any external dependency — just dumps a static message into the
   * shadow root with enough styling to look like an HA panel.
   */
  _renderNoVacuumPlaceholder() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          width: 100%;
          min-height: 100%;
          background: var(--primary-background-color, #111);
          color: var(--primary-text-color, #e6e6e6);
          font-family: var(--paper-font-body1_-_font-family, system-ui, sans-serif);
        }
        .evcc-setup-wrap {
          max-width: 640px;
          margin: 0 auto;
          padding: 48px 24px;
          line-height: 1.55;
        }
        .evcc-setup-title {
          font-size: 1.6em;
          font-weight: 600;
          margin: 0 0 12px 0;
        }
        .evcc-setup-lede {
          font-size: 1.05em;
          color: var(--secondary-text-color, #9aa0a6);
          margin: 0 0 24px 0;
        }
        .evcc-setup-card {
          background: var(--card-background-color, #1c2127);
          border: 1px solid var(--divider-color, rgba(255, 255, 255, 0.12));
          border-radius: 12px;
          padding: 20px 22px;
          margin: 0 0 16px 0;
        }
        .evcc-setup-card h3 {
          margin: 0 0 8px 0;
          font-size: 1.05em;
          font-weight: 600;
        }
        .evcc-setup-card p, .evcc-setup-card ol {
          margin: 0 0 8px 0;
        }
        .evcc-setup-card ol {
          padding-left: 22px;
        }
        .evcc-setup-card li + li {
          margin-top: 4px;
        }
        code {
          background: rgba(255, 255, 255, 0.06);
          padding: 1px 5px;
          border-radius: 3px;
          font-size: 0.9em;
        }
        a {
          color: var(--primary-color, #3b82f6);
        }
      </style>
      <div class="evcc-setup-wrap">
        <h1 class="evcc-setup-title">${this.t("shell.setup_title")}</h1>
        <p class="evcc-setup-lede">
          ${this.t("shell.setup_lede")}
        </p>
        <div class="evcc-setup-card">
          <h3>${this.t("shell.setup_add_title")}</h3>
          <ol>
            <li>${this.tRaw("shell.setup_step_open")}</li>
            <li>${this.tRaw("shell.setup_step_find")}</li>
            <li>${this.tRaw("shell.setup_step_configure")}</li>
            <li>${this.tRaw("shell.setup_step_pick")}</li>
          </ol>
          <p>
            ${this.t("shell.setup_reload_note")}
          </p>
        </div>
        <div class="evcc-setup-card">
          <h3>${this.t("shell.setup_no_entity_title")}</h3>
          <p>
            ${this.tRaw("shell.setup_no_entity_body")}
          </p>
          <p>
            ${this.tRaw("shell.setup_eufy_note")}
          </p>
        </div>
      </div>
    `;
  }

  /* =========================================================
     CARD-LEVEL I18N — for the few strings rendered BEFORE this._renderers
     exists (the no-vacuum placeholder above). Renderer strings translate
     through this._renderers.t; these go straight to the i18n module.
     ========================================================= */

  /**
   * Resolve the active UI language (shared resolver). Honors, in order: the
   * per-user in-card override (this._langOverride), then config.i18n.locale,
   * then the HA system language.
   */
  _i18nLanguage() {
    return resolveLang(this._hass, this._config, this._langOverride);
  }

  /**
   * What the header's "Auto" row should disclose. When the user has no per-dash
   * pin and their HA system language is an unreviewed draft, "Auto" silently
   * resolves to English (the draft-gate) — surface that so Auto doesn't look
   * broken. Returns { systemLang, gatedToEnglish }.
   */
  _autoLangInfo() {
    const systemLang = String(
      (this._hass && this._hass.locale && this._hass.locale.language) ||
      (this._hass && this._hass.language) || "en",
    ).split("-")[0];
    const pinned = this._config && this._config.i18n && this._config.i18n.locale;
    const hasPin = pinned && pinned !== "auto";
    const status = localeStatus(systemLang);
    const gatedToEnglish = !hasPin && systemLang !== "en" && (status === "draft" || status === "custom");
    return { systemLang, gatedToEnglish };
  }

  /** Translate a card-level UI string (HTML-escaped; trust model B). */
  t(key, vars) { return translate(this._i18nLanguage(), key, vars); }

  /** Translate a card-level string preserving authored markup (see `t`). */
  tRaw(key, vars) { return translate(this._i18nLanguage(), key, vars, { raw: true }); }

  /**
   * Load the external locale declared in `config.i18n`, ONCE per resolved
   * (locale,url). On success the validated catalog (validateLocale) is
   * registered and the card re-renders so the new strings replace English.
   * Fails soft — a missing/invalid/cross-origin file just keeps English (logged).
   */
  _maybeLoadLocale() {
    const src = localeSource(this._config, resolveLang(this._hass, this._config, this._langOverride));
    if (!src || this._localeLoadKey === src.key) return;
    // Same-origin only: never fetch a cross-origin url a shared dashboard config
    // might point at (privacy + trust). Relative urls (e.g. /local/...) pass.
    let abs;
    try { abs = new URL(src.url, location.href); } catch { return; }
    if (abs.origin !== location.origin) {
      console.warn(`[eufy-vacuum-command-center] i18n: refusing cross-origin locale url "${src.url}"`);
      return;
    }
    this._localeLoadKey = src.key; // one-shot: don't refetch on every hass update
    loadLocale(src.url, src.lang).then((report) => {
      if (!report.ok) {
        console.warn(`[eufy-vacuum-command-center] i18n: locale "${src.lang}" not loaded (${src.url}): ${report.errors.join("; ")}`);
        return;
      }
      if (report.errors.length || report.warnings.length) {
        console.warn(`[eufy-vacuum-command-center] i18n: locale "${src.lang}" — ${report.loaded} keys, ${report.errors.length} dropped, ${report.warnings.length} warning(s)`);
      }
      // Re-render so the registered strings replace the English fallback.
      if (this._config?.vacuum_entity_id) this._scheduleRender();
      else this._renderNoVacuumPlaceholder();
    });
  }

  /* =========================================================
     LANGUAGE OVERRIDE — the header globe control. The choice is stored
     per-user, server-side (i18n/lang-store.js), so it follows the HA login
     across devices. resolveLang() consumes `this._langOverride` as its
     highest-priority source (above config + system), bypassing the draft-gate.
     ========================================================= */

  /**
   * Load the per-user language choice ONCE, the first time hass is available.
   * Fails soft to no-override (English/config/system) — see lang-store.js. A
   * change made on another device is picked up on the next load (the documented
   * tradeoff of the per-user-data store), not in real time.
   */
  _maybeLoadLangOverride() {
    if (this._langOverrideLoaded) return;
    this._langOverrideLoaded = true; // one-shot, set before the await
    getStoredLang(this._hass).then((code) => {
      // If the user already picked this session, their choice wins — never let
      // a late server read (possibly a stale value, or one racing our own write)
      // clobber a fresh in-session pick.
      if (this._langUserPicked) return;
      if (code == null || code === this._langOverride) return;
      this._langOverride = code;
      // Re-render so the stored language replaces the current paint.
      if (this._config?.vacuum_entity_id) this._scheduleRender();
      else this._renderNoVacuumPlaceholder();
    });
  }

  /**
   * Load the runtime locale catalogs, ONCE. Two sources, in order:
   *   1. SHIPPED — de/fr/es/nl/it/pt/ru, ripped out of the bundle and served as
   *      nested JSON at /eufy_vacuum/frontend/locales/ (no status arg → each
   *      keeps its bundled LOCALE_STATUS, i.e. "draft").
   *   2. USER DROP-INS — config/eufy_vacuum/locales/ (status "custom", gated).
   * Drops load AFTER shipped so a drop-in OVERRIDES the shipped locale of the
   * same code (the user's correction wins). Both flatten the nested JSON and
   * fail soft — English (bundled) covers anything that doesn't load.
   */
  _maybeLoadExternalLocales() {
    // Shared, module-guarded load (CATALOGS is shared across all cards in the
    // bundle, incl. the standalone room-card) — see ensureLocalesLoaded.
    ensureLocalesLoaded(() => {
      if (this._config?.vacuum_entity_id) this._scheduleRender();
      else this._renderNoVacuumPlaceholder();
    });
  }

  /** Open/close the header language dropdown (card-level so it survives re-render). */
  toggleLanguageMenu() {
    this._languageMenuOpen = !this._languageMenuOpen;
    this._scheduleRender();
  }

  /** Close the header language dropdown (no-op if already closed). */
  closeLanguageMenu() {
    if (!this._languageMenuOpen) return;
    this._languageMenuOpen = false;
    this._scheduleRender();
  }

  /**
   * Apply a language choice from the control: update the live override
   * immediately (optimistic), close the menu, re-render, and persist per-user in
   * the background (fire-and-forget; a failed write just doesn't survive reload).
   *
   * @param {string} code - a bundled locale code, or "auto" to defer to config/system.
   */
  setLanguageOverride(code) {
    this._langUserPicked = true; // an in-session pick wins over a late server read
    this._langOverride = code;
    this._languageMenuOpen = false;
    this._scheduleRender();
    setStoredLang(this._hass, code);
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

    // Load an external locale (config.i18n) once the language is known — runs in
    // BOTH the placeholder and the normal path (one-shot, see _maybeLoadLocale).
    this._maybeLoadLocale();

    // Load the per-user language override once hass (and its websocket) exist —
    // one-shot, runs in both the placeholder and normal paths (see method).
    this._maybeLoadLangOverride();

    // Load the runtime locale catalogs (shipped + user drop-ins) — one-shot.
    this._maybeLoadExternalLocales();

    // Setup-placeholder mode: no vacuum configured yet, the static
    // placeholder is already in the DOM, and we have no state to sync.
    // Bail before any of the refresh schedulers run (they all assume
    // _state exists).
    if (!this._config?.vacuum_entity_id) {
      // Localize the onboarding placeholder once, now that hass (and the user's
      // language) is available — setConfig rendered it before the first hass.
      if (!this._placeholderLocalized) {
        this._placeholderLocalized = true;
        this._renderNoVacuumPlaceholder();
      }
      return;
    }

    if (this._state)   this._state.sync(hass, this._config);
    if (this._actions) this._actions.sync?.(hass, this._state);

    // Wire the confirmation registry's auto-clear render trigger
    // exactly once. setConfirmationsRenderTrigger is idempotent — it
    // just replaces the stored callback — but we only need to do
    // this once per card instance.
    if (this._state && !this._confirmationsWired) {
      this._confirmationsWired = true;
      this._state.setConfirmationsRenderTrigger?.(() => this._scheduleRender());
    }

    // Restore last-active view exactly once on first hass sync.
    // Persisted under evcc_last_view_<vacuum_entity_id>; setView writes it.
    this._restoreLastView();

    // Detect active map id changes — happens after a map switch or
    // after the active map is deleted. Any cached map-derived state
    // (segments data, image variants, overlays, zoom transform) is
    // now stale and would otherwise keep rendering the previous map's
    // tiles. setMapSegmentsData(null) clears that whole slice; the
    // next map-config navigation re-fetches fresh data.
    if (this._state) {
      const currentMapId = this._state.activeMapId?.();
      if (currentMapId != null) {
        if (this._lastSeenActiveMapId != null && this._lastSeenActiveMapId !== currentMapId) {
          this._state.setMapSegmentsData?.(null);
          this._incompleteRunLogLoaded = false;
        }
        this._lastSeenActiveMapId = currentMapId;
      }
    }

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
    this._scheduleSavedZonesRefresh();
    this._scheduleIncompleteRunLogRefresh();
    this._scheduleTroubleRoomsLogRefresh();
    this._scheduleLiveMapRefresh();
    this._scheduleLivePosePoll();
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

  // Visual config editor (per-dashboard): entity + a display-language override
  // that writes config.i18n.locale. See EufyVacuumCardEditor near registration.
  static getConfigElement() { return document.createElement(CARD_EDITOR_NAME); }

  /* =========================================================
     VIEW MANAGEMENT
     ========================================================= */
  /**
   * localStorage key for the per-vacuum last-active view. Scoped by
   * vacuum_entity_id so a single browser viewing multiple cards keeps
   * each card's view independently.
   */
  _viewStorageKey() {
    const id = this._config?.vacuum_entity_id ?? "default";
    return `evcc_last_view_${id}`;
  }

  /**
   * One-shot restore on first hass sync. Reads the persisted view name
   * and switches to it iff it's a real, currently-allowed view.
   * Idempotent — flips `_viewRestored` so subsequent renders don't
   * re-apply the stored value over a user-driven switch.
   */
  _restoreLastView() {
    if (this._viewRestored) return;
    this._viewRestored = true;

    let stored;
    try {
      stored = localStorage.getItem(this._viewStorageKey());
    } catch (_) {
      stored = null;
    }
    if (!stored) return;
    if (stored === this._view) return;
    if (!Object.values(VIEWS).includes(stored)) return;
    if (stored === VIEWS.MAPPING_ARCHIVE) return; // legacy, always rerouted to Rooms
    // Don't restore a capability-gated tab the active adapter doesn't show
    // (e.g. a stored Base Station / Map Bounds on a no-dock/no-CV vacuum). If the
    // snapshot hasn't loaded yet, isViewAvailable defaults true and the render
    // path's fallback re-corrects once capabilities arrive.
    if (!isViewAvailable(stored, this._state)) return;
    this._view = stored;
    this._scheduleRender();
  }

  setView(view) {
    if (view === VIEWS.MAPPING_ARCHIVE) {
      view = VIEWS.ROOMS;
    }

    // Never switch to a capability-gated tab the adapter doesn't show — closes
    // the programmatic back-door (a hidden view would otherwise fire its
    // capability-specific refresh schedulers against an adapter that lacks it).
    if (!isViewAvailable(view, this._state)) {
      view = VIEWS.ROOMS;
    }

    if (this._view === view) return;
    this._view = view;
    try {
      localStorage.setItem(this._viewStorageKey(), String(view));
    } catch (_) {}

    // Drop every armed transient confirmation on nav. Registry-backed
    // confirmations (cancel-run, clear-queue, per-variant delete) all
    // disarm here in one call — including cancelling their auto-clear
    // timers. start-confirmation and maintenance-reset live outside
    // the registry (preflight workflow / modal-scoped) so they stay
    // explicit.
    this._state?.disarmAllConfirmations?.();
    this._state?.clearStartConfirmation?.();
    this._state?.cancelMaintenanceResetConfirmation?.();
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
      this._scheduleSavedZonesRefresh();
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

  /* Poll the live-map CAMERA backdrop on the frame cadence.
     A camera.* live entity pushes new frames WITHOUT a state change (HA dedupes identical
     state+attrs), so last_updated barely moves and the <img> shows a frozen frame until a
     manual refresh. While a live camera backdrop is on the map view, bump a tick + re-render
     every REFRESH_MS so the cache-bust advances and the image refetches. image.* live
     entities self-bust (token rotates per frame) -> no poll needed. Idempotent: set hass is
     frequent, so we never reset a running timer (that would starve it). */
  _scheduleLiveMapRefresh() {
    const REFRESH_MS = 2000; // eufy-clean pushes a new map frame ~every 2s

    const liveCamera =
      !!this._state?.isMapViewActive?.() &&
      !!this._state?.isLiveBackdropActive?.() &&
      !!this._state?.liveMapImageEntity?.()?.startsWith?.("camera.");

    if (!liveCamera) {
      if (this._liveMapRefreshTimer) {
        clearInterval(this._liveMapRefreshTimer);
        this._liveMapRefreshTimer = null;
      }
      return;
    }
    if (this._liveMapRefreshTimer) return; // already polling

    this._liveMapRefreshTimer = setInterval(() => {
      if (!this._state?.isMapViewActive?.() || !this._state?.isLiveBackdropActive?.()) {
        clearInterval(this._liveMapRefreshTimer);
        this._liveMapRefreshTimer = null;
        return;
      }
      if (document.hidden) return; // tab backgrounded — skip the fetch, keep the timer alive
      this._state.bumpLiveMapTick?.();
      this._scheduleRender();
    }, REFRESH_MS);
  }

  /* Poll the fork's in-memory LIVE POSE on the frame cadence (Phase B). The snapshot
     carries the moving overlays (robot/dock/current-room/path) but only as fresh as its
     slow cadence, so a cleaning robot visibly lags. While the device overlays are shown
     (live image or VA render) on the map view, read the fork's fresh in-memory pose every
     REFRESH_MS and override those fields. The read is in-memory + loop-safe (no .storage),
     and SELF-DISABLES for a brand with no live_pose block (Roborock is frame-fresh via the
     snapshot): the first not_configured response latches the poll off for the session.
     Idempotent like _scheduleLiveMapRefresh — never resets a running timer. */
  _scheduleLivePosePoll() {
    const REFRESH_MS = 2000; // matches the fork's ~2s map-frame cadence

    const wantPoll =
      !this._livePoseUnsupported &&
      !!this._state?.isMapViewActive?.() &&
      !!this._state?.overlaysAligned?.() &&
      !!this._state?.mapStateSource?.()?.present;

    if (!wantPoll) {
      if (this._livePosePollTimer) {
        clearInterval(this._livePosePollTimer);
        this._livePosePollTimer = null;
      }
      return;
    }
    if (this._livePosePollTimer) return; // already polling

    const tick = async () => {
      if (this._livePoseUnsupported
          || !this._state?.isMapViewActive?.()
          || !this._state?.overlaysAligned?.()) {
        clearInterval(this._livePosePollTimer);
        this._livePosePollTimer = null;
        return;
      }
      if (document.hidden) return; // tab backgrounded — skip the fetch, keep the timer alive
      try {
        const resp = await this._actions?.getMapLivePose?.();
        // callService swallows a WS drop and RETURNS null (it does not throw), so the catch
        // below is dead code for that case. Guard null explicitly: a transient failure keeps
        // the last pose + timer and retries next tick, rather than clearing the override
        // (which would snap the robot back to the lagged snapshot for a frame). Only an
        // explicit present:false from the backend means "genuinely no pose".
        if (resp == null) return;
        if (resp.present === false && resp.reason === "not_configured") {
          this._livePoseUnsupported = true;        // latch off — this brand is frame-fresh
          this._state?.setLivePose?.(null);
          clearInterval(this._livePosePollTimer);
          this._livePosePollTimer = null;
          this._scheduleRender();
          return;
        }
        this._state?.setLivePose?.(resp);
        this._scheduleRender();
      } catch (err) {
        // transient WS drop — keep the last pose + the timer, retry next tick
      }
    };

    this._livePosePollTimer = setInterval(tick, REFRESH_MS);
    tick(); // fire immediately so the first override doesn't wait a full interval
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

  async refreshSavedZones() {
    if (!this._state || !this._actions) return null;
    if (this._view !== VIEWS.ROOMS) return null;

    const mapId = this._state.activeMapId();
    const vacuumEntityId = this._state.vacuumEntityId();
    if (!vacuumEntityId || !mapId) return null;

    // Fetch into the ISOLATED saved-zones slot — NOT through setMapSegmentsData — so a
    // background refresh can't drop the map's optimistic overlays (mirrors
    // refreshRunProfiles, which writes its own library slot).
    const zones = await this._actions.getSavedZones({
      vacuum_entity_id: vacuumEntityId,
      map_id: mapId,
    });
    this._state.setSavedZonesLibrary?.(zones ?? []);
    this._scheduleRender();
    return zones;
  }

  _scheduleSavedZonesRefresh() {
    if (!this._state || !this._actions) return;
    if (this._view !== VIEWS.ROOMS) return;

    clearTimeout(this._savedZonesTimer);
    this._savedZonesTimer = setTimeout(() => {
      this.refreshSavedZones();
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
    // A furnished-art alignment gesture (pointer-drag or fine-trim slider) updates the art
    // element's transform INLINE and must not be interrupted by a re-render: the live-map
    // poll AND frequent `set hass` updates would otherwise rebuild the DOM mid-gesture,
    // detach the dragged element, and lose the move (its pointer listeners die on the
    // detached node). Suppress renders for the gesture's duration; the gesture's finish
    // handler clears the flag and calls _scheduleRender once to settle the committed result.
    if (this._furnishedGestureActive) return;
    if (this._renderScheduled) return;
    this._renderScheduled = true;

    Promise.resolve().then(() => {
      this._renderScheduled = false;
      this._render();
    });
  }

  /* =========================================================
     TOASTS
     =========================================================
     Card-level convenience wrapper around state.pushToast that
     also schedules a follow-up render after the TTL so expired
     toasts disappear from the DOM without a click. Call sites:
     any binding that wants to surface a service result as a
     visible "did this land?" cue.
     ========================================================= */
  showToast(message, opts = {}) {
    if (!this._state?.pushToast) return null;
    const id = this._state.pushToast(message, opts);
    this._scheduleRender();
    const ttl = Number.isFinite(opts?.ttl) ? Math.max(1000, opts.ttl) : 3500;
    setTimeout(() => {
      // The renderer also filters expired toasts, but we still need a
      // re-render to actually clear them from the DOM.
      this._scheduleRender();
    }, ttl + 80);
    return id;
  }

  /* =========================================================
     CARD-NATIVE DIALOGS  (confirm / alert / prompt)
     =========================================================
     Drop-in async replacements for window.confirm/alert/prompt — they
     follow the card's per-user language and work inside the HA app /
     webview (where window.confirm is often suppressed). Each opens a
     dialog in the modal host and returns a Promise that settles when the
     user acts. If state isn't ready, they fail safe (confirm -> false,
     prompt -> null, alert -> resolves) rather than blocking. */

  /** @returns {Promise<boolean>} true if confirmed, false if cancelled. */
  _confirm(message, opts = {}) {
    if (!this._state?.openDialog) return Promise.resolve(false);
    return new Promise((resolve) => {
      this._state.openDialog({ ...opts, kind: "confirm", message, resolve });
      this._scheduleRender();
    });
  }

  /** @returns {Promise<void>} resolves when acknowledged. */
  _alert(message, opts = {}) {
    if (!this._state?.openDialog) return Promise.resolve();
    return new Promise((resolve) => {
      this._state.openDialog({ ...opts, kind: "alert", message, resolve });
      this._scheduleRender();
    });
  }

  /** @returns {Promise<string|null>} the entered text, or null if cancelled. */
  _prompt(message, opts = {}) {
    if (!this._state?.openDialog) return Promise.resolve(null);
    return new Promise((resolve) => {
      this._state.openDialog({ ...opts, kind: "prompt", message, defaultValue: opts.defaultValue ?? "", resolve });
      this._scheduleRender();
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

    // If the active view's tab is no longer available for this adapter (a
    // capability-gated tab the user was on, or a persisted view that slipped
    // through restore before the snapshot landed), fall back to Rooms so the
    // user never sits on a view whose tab is hidden. Snapshot-driven, so this
    // self-corrects on the next render once capabilities arrive.
    if (!isViewAvailable(this._view ?? VIEWS.ROOMS, this._state)) {
      this._view = VIEWS.ROOMS;
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
      viewHtml = `<div class="evcc-empty">${ctx.renderers.t("shell.view_error", { view: ctx.view })}</div>`;
    }

    // Mobile-only chrome regions: bottom nav and the overflow sheet
    // overlay. Empty strings on desktop so the regions exist but
    // render nothing.
    const bottomNavHtml = isMobile
      ? this._renderers.renderMobileBottomNav?.(ctx) ?? ""
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

    // Toast stack — rendered into a body-level host so it always
    // stacks above the modal host (which is also body-level).
    // Inside the shadow root we couldn't out-stack a sibling div
    // appended to document.body, hence the external host.
    this._updateToastHost(ctx);

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

    const externalWizardHtml =
      typeof this._renderers.renderExternalWizardModal === "function"
        ? this._renderers.renderExternalWizardModal(ctx)
        : "";

    const themeJsonHtml =
      typeof this._renderers.renderThemeJsonModal === "function"
        ? this._renderers.renderThemeJsonModal(ctx)
        : "";

    // Dialog (confirm / alert / prompt) is rendered LAST so it stacks above
    // whatever modal triggered it (e.g. the run-profile editor below it).
    const dialogHtml =
      typeof this._renderers.renderDialogModal === "function"
        ? this._renderers.renderDialogModal(ctx)
        : "";

    const html = `${roomEditorHtml}${roomAccessHtml}${roomEstimateHtml}${orderModalHtml}${maintenanceModalHtml}${externalWizardHtml}${themeJsonHtml}${dialogHtml}`;

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
      // Preserve each open modal body's scroll across the innerHTML swap. Without
      // this, every in-modal interaction (room pick, setting tap) re-renders and
      // jumps the modal back to the top. Bodies map by index (modal order is stable).
      const prevScroll = Array.from(
        this._modalHost.querySelectorAll(".evcc-modal-body"),
        (el) => el.scrollTop,
      );
      this._modalHost.innerHTML = modalMarkup;
      this._modalHost.dataset.renderedHtml = modalMarkup;
      const bodies = this._modalHost.querySelectorAll(".evcc-modal-body");
      prevScroll.forEach((top, i) => {
        if (top && bodies[i]) bodies[i].scrollTop = top;
      });

      // Bind ONLY after an actual innerHTML swap. The swap recreates every modal
      // element (dropping its old listeners), so this attaches exactly one set.
      // Re-binding on every render — including a background status/battery push
      // while a modal sits open with UNCHANGED markup — would stack duplicate
      // click listeners on the same buttons (double-firing save / rename /
      // delete). Same-markup renders keep their already-attached listeners.
      this._bindings?.bindModalHostEvents(this._modalHost);
    }
  }

  /* =========================================================
     TOAST HOST
     =========================================================
     Body-level sibling of the modal host. Toasts MUST live above
     the modal host in the document stacking order so save / reset
     / dock-action feedback is visible while a modal is open.
     Sharing the same shadow root with the card put them below
     the modal host's z-index:9999. Hence the external host with
     z-index:10000.
     ========================================================= */
  /* =========================================================
     GLOBAL KEYDOWN
     =========================================================
     ESC closes whichever modal is currently rendered in the
     body-level modal host. Each modal has its own state slice
     and dedicated close method; we walk them in stacking order
     (most recently opened wins) and call the first close that
     actually has something to do.
     ========================================================= */
  _handleGlobalKeydown(event) {
    if (event?.key !== "Escape") return;
    if (!this._modalHost) return;
    if (!this._state) return;

    // A card-native dialog stacks ABOVE every other modal, so Escape must
    // cancel IT — not the modal underneath. (Native confirm/prompt were
    // document-blocking; Escape never reached the page. Preserve that.)
    if (this._state.cancelDialog?.()) {
      this._scheduleRender();
      event.preventDefault();
      return;
    }

    const closers = [
      ["maintenance",   "activeMaintenanceModalItem", "closeMaintenanceModal"],
      ["room-estimate", "isRoomEstimateModalOpen",    "closeRoomEstimateModal"],
      ["room-access",   "isRoomAccessOpen",           "closeRoomAccess"],
      ["order",         "isOrderSelectorOpen",        "closeOrderSelector"],
      ["room-editor",   "isRoomEditorOpen",           "closeRoomEditor"],
    ];

    for (const [, isOpenKey, closeKey] of closers) {
      const opener = this._state[isOpenKey];
      const closer = this._state[closeKey];
      if (typeof opener !== "function" || typeof closer !== "function") continue;
      if (!opener.call(this._state)) continue;
      closer.call(this._state);
      this._scheduleRender();
      event.preventDefault();
      return;
    }
  }

  _updateToastHost(ctx) {
    const html = this._renderers.renderToasts?.(ctx) ?? "";

    if (!html) {
      if (this._toastHost) {
        this._toastHost.remove();
        this._toastHost = null;
      }
      return;
    }

    if (!this._toastHost) {
      this._toastHost = document.createElement("div");
      this._toastHost.className = "evcc-toast-host";
      document.body.appendChild(this._toastHost);
    }

    const markup = `<style>${TOAST_HOST_STYLES}</style>${html}`;
    if (this._toastHost.dataset.renderedHtml !== markup) {
      this._toastHost.innerHTML = markup;
      this._toastHost.dataset.renderedHtml = markup;
    }

    // Dismiss bindings — toast host lives outside shadow root, so
    // the per-card _on / _onAll helpers don't see it. Wire dismiss
    // here directly, idempotent via dataset marker.
    this._toastHost.querySelectorAll("[data-action='dismiss-toast']").forEach((btn) => {
      if (btn.dataset.evccBoundClick === "1") return;
      btn.dataset.evccBoundClick = "1";
      btn.addEventListener("click", () => {
        const id = btn.dataset.toastId;
        if (!id) return;
        this._state.dismissToast?.(id);
        this._scheduleRender();
      });
    });
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
    document.addEventListener("keydown", this._boundHandleKeydown);
    document.addEventListener("animal-svg-registered", this._boundHandleAnimalRegistered);

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
    document.removeEventListener("keydown", this._boundHandleKeydown);
    document.removeEventListener("animal-svg-registered", this._boundHandleAnimalRegistered);
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
      this._resizeObserver = null;
    }

    if (this._modalHost) {
      this._modalHost.remove();
      this._modalHost = null;
    }

    if (this._toastHost) {
      this._toastHost.remove();
      this._toastHost = null;
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
    clearInterval(this._liveMapRefreshTimer);
    this._liveMapRefreshTimer = null;
    clearInterval(this._livePosePollTimer);
    this._livePosePollTimer = null;
    this._state?.flushMapTransform?.();   // persist a last-moment pan/zoom + kill its pending timer
    this._bindings?._teardownMapResize?.();   // drop the map container ResizeObserver
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

    // Generic fallback so ANY text input/textarea/select survives a re-render — not
    // only the hardcoded data-attrs above. The old allow-list SILENTLY dropped focus
    // for every input it didn't know about (run-profile name, metrics/review
    // chip-search, the dialog input, setup rename/delete, the custom-layout name),
    // so typing lost focus each keystroke (issue #37). These are single-instance
    // editors, so a valued data-* attr or a class selector is unique in the active
    // view. This closes the whole family, not just the one reported field.
    const tag = String(element.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") {
      const typeValue = element.getAttribute("type");
      const typeSelector = typeValue ? `[type="${CSS.escape(typeValue)}"]` : "";
      const valuedData = Array.from(element.attributes || []).find(
        (a) => a.name.startsWith("data-") && a.value !== ""
      );
      if (valuedData) {
        return `${tag}[${valuedData.name}="${CSS.escape(valuedData.value)}"]${typeSelector}`;
      }
      const classSelector = Array.from(element.classList || [])
        .filter(Boolean)
        .map((className) => `.${CSS.escape(className)}`)
        .join("");
      if (classSelector) {
        return `${tag}${classSelector}${typeSelector}`;
      }
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
   CONFIG EDITOR (per-dashboard)
   =========================================================
   A minimal visual editor for the card's Lovelace config: the vacuum entity
   plus a "Display language" override that writes `config.i18n.locale`. The pin
   bypasses the draft-gate (resolveLang), so a user can opt into any bundled
   language or force English regardless of the HA system language — per this
   card/dashboard only. (Advanced/runtime settings live in the in-card Setup
   tab + backend; the Lovelace config stays minimal.) */

const CARD_EDITOR_NAME = `${CARD_NAME}-editor`;

function _editorEsc(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

class EufyVacuumCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = {};
  }

  setConfig(config) { this._config = config ?? {}; this._render(); }
  set hass(hass) { this._hass = hass; this._render(); }

  // Editor labels follow the editor's own resolved language (English fallback
  // for any locale that hasn't translated the card_editor.* keys yet).
  t(key, vars) { return translate(resolveLang(this._hass, this._config), key, vars); }

  _vacuumEntities() {
    if (!this._hass) return [];
    return Object.keys(this._hass.states).filter((id) => id.startsWith("vacuum.")).sort();
  }

  _fire(config) {
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config }, bubbles: true, composed: true,
    }));
  }

  _render() {
    if (!this.shadowRoot) return;
    const vacuums = this._vacuumEntities();
    const selectedVacuum = this._config.vacuum_entity_id ?? "";
    const selectedLang = (this._config.i18n && this._config.i18n.locale) || "auto";
    const locales = listBundledLocales();

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; font-family: var(--paper-font-body1_-_font-family, sans-serif); }
        .field { display: flex; flex-direction: column; gap: 4px; margin-bottom: 16px; }
        label {
          font-size: 0.80rem; font-weight: 500;
          color: var(--secondary-text-color, #888);
          text-transform: uppercase; letter-spacing: 0.04em;
        }
        select {
          width: 100%; box-sizing: border-box; padding: 8px 10px;
          border: 1px solid var(--divider-color, rgba(255,255,255,0.12));
          border-radius: 6px;
          background: var(--card-background-color, #1c2127);
          color: var(--primary-text-color, #f0f2f5);
          font-size: 0.92rem; appearance: none; -webkit-appearance: none;
        }
        select:focus { outline: none; border-color: var(--primary-color, #3b82f6); }
        .hint { font-size: 0.75rem; color: var(--secondary-text-color, #888); margin-top: 2px; }
      </style>

      <div class="field">
        <label>${this.t("card_editor.vacuum_label")}</label>
        <select id="vacuum">
          <option value="" disabled ${!selectedVacuum ? "selected" : ""}>${this.t("card_editor.pick_vacuum")}</option>
          ${vacuums.map((v) => `<option value="${_editorEsc(v)}" ${v === selectedVacuum ? "selected" : ""}>${_editorEsc(v)}</option>`).join("")}
        </select>
      </div>

      <div class="field">
        <label>${this.t("card_editor.language_label")}</label>
        <select id="lang">
          <option value="auto" ${selectedLang === "auto" ? "selected" : ""}>${this.t("card_editor.language_auto")}</option>
          ${locales.map((l) => `<option value="${_editorEsc(l.code)}" ${l.code === selectedLang ? "selected" : ""}>${_editorEsc(l.label)}</option>`).join("")}
        </select>
        <div class="hint">${this.t("card_editor.language_hint")}</div>
      </div>
    `;

    this.shadowRoot.getElementById("vacuum")?.addEventListener("change", (e) => {
      this._fire({ ...this._config, vacuum_entity_id: e.target.value });
    });
    this.shadowRoot.getElementById("lang")?.addEventListener("change", (e) => {
      const val = e.target.value;
      // "auto" is stored explicitly (resolveLang treats it as defer-to-HA); a
      // language code pins it. Either way write into config.i18n.locale.
      const next = { ...this._config, i18n: { ...(this._config.i18n || {}), locale: val } };
      this._fire(next);
    });
  }
}

customElements.define(CARD_EDITOR_NAME, EufyVacuumCardEditor);

/* =========================================================
   REGISTRATION
   ========================================================= */

// Class-level flag — animal-svg module is shared across all card instances.
EufyVacuumCommandCenter._animalSvgLoaded = false;

customElements.define(CARD_NAME, EufyVacuumCommandCenter);

