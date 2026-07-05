/**
 * ============================================================
 * STATE: THEME EDITOR
 * ============================================================
 *
 * PURPOSE
 * -------
 * Owns all card-side UI state for the theme editor.
 *
 * This file is intentionally limited to editor state and selector
 * logic. It does not implement persistence, backend mutation, or
 * token rendering. The integration remains the source of truth for
 * saved theme state, while this file tracks how the editor is being
 * viewed and filtered right now.
 *
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * Backend-owned theme state mirrored here:
 * - active theme id
 * - working draft
 * - draft dirty flag
 * - theme library
 *
 * Card-owned editor state owned here:
 * - active theme sub-tab
 * - global search query
 * - group-local search queries
 * - selected group filter
 * - group open / closed state
 *
 *
 * SOURCE OF TRUTH BOUNDARY
 * ------------------------
 * The resolved preview model is:
 *
 *   active theme tokens
 *   + working draft overrides
 *
 * Reset behavior must remove draft override semantics rather than
 * writing fallback values back into the editor state. This keeps the
 * card aligned with the backend overlay model and avoids duplicating
 * resolved values into draft state.
 *
 *
 * DESIGN RULES
 * ------------
 * - No frontend theme persistence model
 * - No preset override engine
 * - No duplicated backend logic
 * - Group visibility, filter selection, and search behavior live here
 * - Renderer consumes selectors from here rather than rebuilding
 *   filter rules ad hoc
 *
 * ============================================================
 */

import { THEME_GROUPS, THEME_TOKEN_MAP } from "../theme-tokens/index.js";
import { effectiveThemeTags } from "../theme-tags/index.mjs";
import { ROOM_FILL_PALETTE } from "../cards/map-room-color.js";
import { FLOOR_TEXTURE_REGISTRY } from "../textures/floor-texture-registry.js";

/**
 * Bake an alpha multiplier (0–1) into a CSS hex color string.
 * Strips any existing alpha channel from the hex, then appends the new one.
 * Returns the original value unchanged if it is not a valid 6- or 8-char hex.
 */
function _hexWithAlpha(colorHex, alpha) {
  const trimmed = String(colorHex || "").trim();

  let base6;
  if (/^#[0-9a-fA-F]{8}$/.test(trimmed)) {
    base6 = `#${trimmed.slice(1, 7)}`;
  } else if (/^#[0-9a-fA-F]{6}$/.test(trimmed)) {
    base6 = trimmed;
  } else {
    return trimmed;
  }

  if (alpha === null || alpha === undefined) {
    return trimmed;
  }

  const clamped = Math.max(0, Math.min(1, Number(alpha)));
  if (Number.isNaN(clamped)) return trimmed;
  const alphaHex = Math.round(clamped * 255).toString(16).padStart(2, "0").toLowerCase();
  return `${base6}${alphaHex}`;
}

export function applyThemeState(proto) {
  proto._emptyThemeDraft = function () {
    return {
      tokens: {},
      colors: {},
      alpha: {},
    };
  };

  proto._themeDraftHasOverrides = function (draft) {
    return (
      Object.keys(draft.tokens).length > 0 ||
      Object.keys(draft.colors).length > 0 ||
      Object.keys(draft.alpha).length > 0
    );
  };

  proto._applyThemeDraftBucket = function (targetBucket, patchBucket) {
    if (!patchBucket || typeof patchBucket !== "object") {
      return;
    }

    Object.entries(patchBucket).forEach(([key, value]) => {
      if (value === null || value === undefined || value === "") {
        delete targetBucket[key];
        return;
      }

      targetBucket[key] = value;
    });
  };

  proto._normalizeThemeDraft = function (payload) {
    const draft = this._emptyThemeDraft();

    if (!payload || typeof payload !== "object") {
      return draft;
    }

    this._applyThemeDraftBucket(draft.tokens, payload.tokens);
    this._applyThemeDraftBucket(draft.colors, payload.colors);
    this._applyThemeDraftBucket(draft.alpha, payload.alpha);

    return draft;
  };

  proto.applyThemeDraftPatch = function (patch) {
    const state = this._ensureThemeState();

    this._applyThemeDraftBucket(state.workingDraft.tokens, patch?.tokens);
    this._applyThemeDraftBucket(state.workingDraft.colors, patch?.colors);
    this._applyThemeDraftBucket(state.workingDraft.alpha, patch?.alpha);

    state.draftDirty = this._themeDraftHasOverrides(state.workingDraft);
  };

  /**
   * Apply a successful theme activation locally so the editor can
   * reflect selection immediately instead of waiting for the next
   * Home Assistant sensor round-trip.
   */
  proto.applyThemeActivation = function (themeId, options = {}) {
    const state = this._ensureThemeState();
    const clearDraft = options.clearDraft !== false;

    state.activeThemeId = themeId ?? null;

    if (clearDraft) {
      state.workingDraft = this._emptyThemeDraft();
      state.draftDirty = false;
    }
  };

  proto._ensureThemeState = function () {
    if (!this._themeState) {
      this._themeState = {
        /* -----------------------------------------------------
           BACKEND-MIRRORED THEME STATE
           ----------------------------------------------------- */
        library: {},
        librarySummary: [],
        defaultThemeId: null,

        activeThemeId: null,
        workingDraft: this._emptyThemeDraft(),
        draftDirty: false,
        editorMode: "live",

        /* -----------------------------------------------------
           CARD-OWNED EDITOR UI STATE
           ----------------------------------------------------- */
        selectedThemeId: null,
        activeSubTab: "presets",
        focusedGroup: "",

        tokenSearchQuery: "",
        selectedGroupFilter: "all",

        groupOpen: {},
        groupSearchQueryByName: {},

        modifiedOnly: false,

        /* Preset (theme) facet filter + search — mirrors the Pages gallery,
           driven by the shared src/theme-tags core. `_presetTags` is a lazy
           cache (id -> derived tags) invalidated whenever the library changes. */
        presetFacets: {},
        presetSearchQuery: "",
        _presetTags: null,
        // Facet rows collapse by default so the theme grid gets the space; the
        // search box + a Filters toggle stay visible.
        presetFiltersOpen: false,
        // Which theme's free-text vibe tags are being edited inline (or null).
        presetTagEditId: null,
        // Transient Export/Import JSON modal — { open, mode: "export"|"import",
        // text }. The export text is one-shot: held only while the modal is open.
        themeJsonModal: { open: false, mode: null, text: "" },

        /* -----------------------------------------------------
           PER-DEVICE THEME SELECTION (browser-local)
           -----------------------------------------------------
           The library + edits + backend active theme are shared
           (per-system). This is the ONE per-browser piece: which
           theme THIS device wants to show. Loaded from localStorage
           (scoped per vacuum) below. */
        themeMode: "system", // "system" (follow backend) | "device" (local override)
        deviceThemeId: null,
      };
      this._loadDeviceTheme(); // hydrate the two fields above from localStorage
    }
    return this._themeState;
  };

  /* =========================================================
     PER-DEVICE THEME SELECTION
     -----------------------------------------------------------
     Mirrors the per-browser last-view pattern (main.js): a scoped
     localStorage key so one browser viewing several cards keeps each
     card's choice independent. Only the SELECTION is local — never
     the library or edits.
     ========================================================= */

  proto._deviceThemeKey = function () {
    const id = this.config?.vacuum_entity_id ?? "default";
    return `evcc_theme_device_${id}`;
  };

  proto._loadDeviceTheme = function () {
    const state = this._themeState;
    try {
      const raw = localStorage.getItem(this._deviceThemeKey());
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (parsed?.mode === "device" || parsed?.mode === "system") state.themeMode = parsed.mode;
      if (typeof parsed?.themeId === "string") state.deviceThemeId = parsed.themeId;
    } catch (_) {
      /* corrupt / unavailable storage -> stay on system default */
    }
  };

  proto._persistDeviceTheme = function () {
    const state = this._ensureThemeState();
    try {
      localStorage.setItem(
        this._deviceThemeKey(),
        JSON.stringify({ mode: state.themeMode, themeId: state.deviceThemeId }),
      );
    } catch (_) {}
  };

  proto.getThemeMode = function () {
    return this._ensureThemeState().themeMode;
  };

  proto.isDeviceThemeMode = function () {
    return this._ensureThemeState().themeMode === "device";
  };

  proto.getDeviceThemeId = function () {
    return this._ensureThemeState().deviceThemeId;
  };

  /**
   * The theme id the card should actually display, resolved through the safe
   * fallback chain:
   *   1. device override (device mode + the theme still exists) -> use it
   *   2. stale override (theme deleted) -> clear it, fall through
   *   3. backend active theme
   */
  proto.effectiveActiveThemeId = function () {
    const state = this._ensureThemeState();
    if (state.themeMode === "device" && state.deviceThemeId) {
      if (state.library?.[state.deviceThemeId]) return state.deviceThemeId;
      // The pin isn't in the library. Only treat it as STALE (and clear it) once
      // the library has actually loaded — otherwise the first render (which runs
      // before getThemeLibrary resolves, library still {}) would wipe a valid pin
      // from state AND localStorage. Until then, fall through without clearing.
      if (Object.keys(state.library || {}).length > 0) {
        state.deviceThemeId = null; // the pinned theme is genuinely gone
        this._persistDeviceTheme();
      }
    }
    return state.activeThemeId;
  };

  proto.setThemeMode = function (mode) {
    const state = this._ensureThemeState();
    state.themeMode = mode === "device" ? "device" : "system";
    // Entering device mode with no pick yet: pin whatever is showing now, so the
    // switch is visually a no-op until the user chooses a different theme.
    if (state.themeMode === "device" && !state.deviceThemeId) {
      state.deviceThemeId = state.activeThemeId;
    }
    this._persistDeviceTheme();
  };

  proto.setDeviceThemeId = function (themeId) {
    const state = this._ensureThemeState();
    state.deviceThemeId = themeId || null;
    this._persistDeviceTheme();
  };

  proto.clearDeviceOverride = function () {
    const state = this._ensureThemeState();
    state.deviceThemeId = null;
    state.themeMode = "system";
    this._persistDeviceTheme();
  };

  /* =========================================================
     BACKEND STATE INGESTION
     ========================================================= */

  /**
   * Apply the current per-vacuum theme state mirrored from the
   * backend theme sensor.
   */
  proto.setBackendThemeState = function (payload) {
    const state = this._ensureThemeState();

    state.activeThemeId = payload?.active_theme_id ?? null;
    state.workingDraft = this._normalizeThemeDraft(payload?.working_draft);
    state.draftDirty = payload?.draft_dirty ?? this._themeDraftHasOverrides(state.workingDraft);
    state.editorMode = payload?.editor_mode ?? "live";
  };

  /**
   * Apply the theme library returned by the backend theme service.
   */
  proto.setThemeLibrary = function (payload) {
    const state = this._ensureThemeState();

    state.library = payload?.library ?? {};
    state.librarySummary = payload?.themes ?? [];
    state.defaultThemeId = payload?.default_theme_id ?? null;
    state._presetTags = null; // library changed -> rebuild derived-tag cache lazily
  };

  /* =========================================================
     PREVIEW RESOLUTION
     ========================================================= */

  /**
   * Build the current effective theme preview from:
   * 1. active theme base
   * 2. working draft overlay
   *
   * The returned sources map is used by the editor to determine
   * whether a token is currently draft-owned.
   */
  proto.resolvedTheme = function () {
    const state = this._ensureThemeState();

    // `tokens` holds the final CSS-ready values for every key.
    // `colorMap` and `alphaMap` are kept separate so color hex strings
    // and alpha multipliers (0–1 numbers) never overwrite each other during
    // the merge — they are combined with _hexWithAlpha() at the very end.
    const tokens = {};
    const sources = {};
    const colorMap = {};
    const alphaMap = {};

    // Effective active = the device override (if pinned) else the backend active.
    const activeTheme = state.library?.[this.effectiveActiveThemeId()] || null;

    /* -------------------------------------------------------
       0. SEED: ROOM-FILL PALETTE DEFAULTS
       The room-fill tokens carry no default in styles/index.js (the map
       render supplies its own fallback via roomFillCss/roomFillRgb). But
       the theme editor reads its picker value from this map, so an unset
       token would render an empty, un-openable swatch. Seed the palette
       here so every room-fill token has a resolvable value. The seed EQUALS
       the render's own default palette, so a themeless card is net-zero —
       an active theme or working draft still overrides below.
       ------------------------------------------------------- */
    ROOM_FILL_PALETTE.forEach((hex, i) => {
      const key = `--evcc-room-fill-${i + 1}`;
      colorMap[key] = hex;
      sources[key] = "default";
    });

    /* -------------------------------------------------------
       0b. SEED: FLOOR-TEXTURE MATERIAL DEFAULTS
       Floor color/opacity tokens carry their defaults in the RENDER
       registry (baked as the var() fallback at paint time in
       renderers/floor-texture-surface.js: `var(colorToken,colorDefault)`
       / `var(opacityToken,opacityDefault)`), NOT in styles/. Like the
       room-fill palette above, the editor reads its picker value from
       this map, so without a seed every floor token renders an empty,
       un-openable swatch — the exact failure the room-fill seed fixes,
       which floor tokens never received. Seed each REAL editor floor
       token (present in THEME_TOKEN_MAP) from its registry-layer default
       so the colour swatch opens at the material's actual colour and each
       layer-opacity slider starts at its intended value. The seed EQUALS
       the render's own var() fallback, so a themeless card is net-zero; an
       active theme / working draft still overrides below. The
       THEME_TOKEN_MAP gate skips computed "-eff" vein layers (marble),
       whose oklch()/calc() defaults are not editor tokens.
       ------------------------------------------------------- */
    for (const material of Object.values(FLOOR_TEXTURE_REGISTRY)) {
      for (const layer of material?.layers || []) {
        const ct = layer?.colorToken;
        if (ct && ct in THEME_TOKEN_MAP && layer.colorDefault != null) {
          colorMap[ct] = layer.colorDefault;
          sources[ct] = "default";
        }
        const ot = layer?.opacityToken;
        if (ot && ot in THEME_TOKEN_MAP && layer.opacityDefault != null) {
          tokens[ot] = String(layer.opacityDefault);
          sources[ot] = "default";
        }
      }
    }
    // Global map-texture rotation defaults to 0 (as-authored) so its editor slider starts
    // centred rather than at the angle-range minimum. 0 = no rotation = net-zero on render.
    if ("--evcc-floor-texture-map-rotate" in THEME_TOKEN_MAP) {
      tokens["--evcc-floor-texture-map-rotate"] = "0";
      sources["--evcc-floor-texture-map-rotate"] = "default";
    }

    /* -------------------------------------------------------
       1. BASE: ACTIVE THEME
       ------------------------------------------------------- */
    if (activeTheme) {
      Object.entries(activeTheme.colors || {}).forEach(([k, v]) => {
        colorMap[k] = v;
        sources[k] = "theme";
      });

      Object.entries(activeTheme.alpha || {}).forEach(([k, v]) => {
        alphaMap[k] = v;
        if (!sources[k]) sources[k] = "theme";
      });

      Object.entries(activeTheme.tokens || {}).forEach(([k, v]) => {
        tokens[k] = v;
        sources[k] = "theme";
      });
    }

    /* -------------------------------------------------------
       2. OVERLAY: WORKING DRAFT
       ------------------------------------------------------- */
    Object.entries(state.workingDraft.colors).forEach(([k, v]) => {
      colorMap[k] = v;
      sources[k] = "draft";
    });

    Object.entries(state.workingDraft.alpha).forEach(([k, v]) => {
      alphaMap[k] = v;
      sources[k] = "draft";
    });

    Object.entries(state.workingDraft.tokens).forEach(([k, v]) => {
      tokens[k] = v;
      sources[k] = "draft";
    });

    /* -------------------------------------------------------
       3. COMBINE COLOR + ALPHA
       For any key that has a hex color, apply the corresponding
       alpha (if any) to produce a single 8-char hex value.
       This overwrites any pre-baked value from the tokens bucket
       so that an alpha-only draft change is reflected correctly.
       ------------------------------------------------------- */
    Object.entries(colorMap).forEach(([k, color]) => {
      const alpha = k in alphaMap ? alphaMap[k] : null;
      tokens[k] = _hexWithAlpha(color, alpha);
    });

    return { tokens, sources };
  };

  /* =========================================================
     UI STATE MUTATORS
     ========================================================= */

  proto.setThemeSubTab = function (tab) {
    this._ensureThemeState().activeSubTab = tab;
  };

  proto.setThemeSearchQuery = function (query) {
    this._ensureThemeState().tokenSearchQuery = String(query || "").toLowerCase();
  };

  proto.setThemeModifiedOnly = function (enabled) {
    this._ensureThemeState().modifiedOnly = !!enabled;
  };

  proto.setSelectedTheme = function (themeId) {
    this._ensureThemeState().selectedThemeId = themeId;
  };

  proto.setThemeFocusedGroup = function (group) {
    const state = this._ensureThemeState();
    const normalized = String(group || "").trim();
    state.focusedGroup = THEME_GROUPS.includes(normalized) ? normalized : "";
  };

  proto.getThemeFocusedGroup = function () {
    const group = String(this._ensureThemeState().focusedGroup || "").trim();
    return THEME_GROUPS.includes(group) ? group : "";
  };

  proto.currentThemePreviewGroup = function () {
    const state = this._ensureThemeState();
    const activeFilter = String(state.selectedGroupFilter || "").trim();
    const activeTab = String(state.activeSubTab || "presets").trim().toLowerCase();

    if (THEME_GROUPS.includes(activeFilter)) {
      return activeFilter;
    }

    const focusedGroup = this.getThemeFocusedGroup();
    if (THEME_GROUPS.includes(focusedGroup)) {
      return focusedGroup;
    }

    if (activeTab === "palette") {
      return "Shared Foundations";
    }

    const firstOpenGroup = THEME_GROUPS.find((group) => this.isThemeGroupOpen(group));
    if (firstOpenGroup) {
      return firstOpenGroup;
    }

    return "Shared Foundations";
  };

  /**
   * Global token-group filter used by the token editor chips.
   *
   * Supported values:
   * - "all"
   * - "modified"
   * - exact group name
   */
  proto.setThemeGroupFilter = function (filterValue) {
    const state = this._ensureThemeState();
    state.selectedGroupFilter = String(filterValue || "all");
  };

  proto.toggleThemeGroup = function (group) {
    const state = this._ensureThemeState();
    state.groupOpen[group] = !this.isThemeGroupOpen(group);
  };

  /**
   * Groups default open on first visit.
   * After that, the remembered open state wins.
   */
  proto.isThemeGroupOpen = function (group) {
    const state = this._ensureThemeState();

    if (!(group in state.groupOpen)) {
      return true;
    }

    return !!state.groupOpen[group];
  };

  proto.setThemeGroupSearchQuery = function (group, query) {
    const state = this._ensureThemeState();
    state.groupSearchQueryByName[group] = String(query || "").toLowerCase();
  };

  proto.getThemeGroupSearchQuery = function (group) {
    const state = this._ensureThemeState();
    return state.groupSearchQueryByName[group] || "";
  };

  /* =========================================================
     SIMPLE SELECTORS
     ========================================================= */

  proto.getSelectedTheme = function () {
    const state = this._ensureThemeState();
    return state.library?.[state.selectedThemeId] || null;
  };

  proto.getActiveTheme = function () {
    const state = this._ensureThemeState();
    return state.library?.[this.effectiveActiveThemeId()] || null;
  };

  proto.getThemeGroupFilter = function () {
    return this._ensureThemeState().selectedGroupFilter || "all";
  };

  /* =========================================================
     PRESET (THEME) TAG FILTERING
     -----------------------------------------------------------
     The Themes grid is filtered by the same facet vocabulary the
     Pages gallery uses. Tags are DERIVED from each library theme's
     palette via the shared theme-tags core (cached per library),
     so the card and the gallery agree without the card duplicating
     any logic.
     ========================================================= */

  /** Lazy cache of derived tags per library id: { [id]: { tags, set } }. */
  proto._presetTagsForLibrary = function () {
    const state = this._ensureThemeState();
    if (state._presetTags) return state._presetTags;

    const out = {};
    const library = state.library || {};
    Object.keys(library).forEach((id) => {
      const entry = library[id] || {};
      const { tags } = effectiveThemeTags(entry);
      // Add `source` as a filter token: community/generated/manual aren't derived
      // tags (only `core` is, via the built-in flag), so without this the Source
      // facet could only ever match core. The Set dedups the core overlap. Mirrors
      // the gallery's filterTokens so both surfaces filter identically.
      const source = entry.source ? String(entry.source).toLowerCase() : "";
      const tokens = source ? [...new Set([...tags, source])] : tags;
      out[id] = { tags: tokens, set: new Set(tokens) };
    });
    state._presetTags = out;
    return out;
  };

  /** Derived tags for one library theme (ordered as stored). */
  proto.presetTagsFor = function (id) {
    return (this._presetTagsForLibrary()[id] || { tags: [] }).tags;
  };

  /** Every facet tag that occurs across the library — so the filter bar only
   *  offers chips that actually match a theme. */
  proto.presentPresetTags = function () {
    const tagsById = this._presetTagsForLibrary();
    const present = new Set();
    Object.keys(tagsById).forEach((id) => {
      tagsById[id].tags.forEach((t) => present.add(t));
    });
    return present;
  };

  proto.togglePresetFacet = function (facet, value) {
    const state = this._ensureThemeState();
    const current = Array.isArray(state.presetFacets[facet])
      ? [...state.presetFacets[facet]]
      : [];
    const idx = current.indexOf(value);
    if (idx === -1) current.push(value);
    else current.splice(idx, 1);

    if (current.length) state.presetFacets[facet] = current;
    else delete state.presetFacets[facet];
  };

  proto.isPresetFacetActive = function (facet, value) {
    const sel = this._ensureThemeState().presetFacets[facet];
    return Array.isArray(sel) && sel.includes(value);
  };

  proto.setPresetSearchQuery = function (query) {
    this._ensureThemeState().presetSearchQuery = String(query || "").toLowerCase();
  };

  proto.clearPresetFilters = function () {
    const state = this._ensureThemeState();
    state.presetFacets = {};
    state.presetSearchQuery = "";
  };

  proto.hasActivePresetFilters = function () {
    const state = this._ensureThemeState();
    return Object.keys(state.presetFacets).length > 0 || !!state.presetSearchQuery;
  };

  /** Total selected facet chips across all facets (for the Filters toggle badge). */
  proto.activePresetFacetCount = function () {
    const facets = this._ensureThemeState().presetFacets;
    return Object.keys(facets).reduce((n, k) => n + (facets[k]?.length || 0), 0);
  };

  proto.getPresetFiltersOpen = function () {
    return !!this._ensureThemeState().presetFiltersOpen;
  };

  proto.togglePresetFilters = function () {
    const state = this._ensureThemeState();
    state.presetFiltersOpen = !state.presetFiltersOpen;
  };

  /* --- Export / Import JSON modal ------------------------------------------ */

  proto.openThemeExportModal = function (text) {
    this._ensureThemeState().themeJsonModal = { open: true, mode: "export", text: String(text || "") };
  };

  proto.openThemeImportModal = function () {
    this._ensureThemeState().themeJsonModal = { open: true, mode: "import", text: "" };
  };

  proto.closeThemeJsonModal = function () {
    // Clear the text too — the export JSON is one-shot, gone when the modal closes.
    this._ensureThemeState().themeJsonModal = { open: false, mode: null, text: "" };
  };

  proto.isThemeJsonModalOpen = function () {
    return !!this._ensureThemeState().themeJsonModal.open;
  };

  proto.themeJsonModalMode = function () {
    return this._ensureThemeState().themeJsonModal.mode;
  };

  proto.themeJsonModalText = function () {
    return this._ensureThemeState().themeJsonModal.text || "";
  };

  /* --- Inline vibe-tag editor ---------------------------------------------
     Only the user's free-text tags (`entry.tags`) are editable; facet tags and
     colorblind-safe are derived/verified and never stored, so they can't be set
     here. Editing one theme at a time keeps the grid uncluttered. */

  proto.getPresetTagEditId = function () {
    return this._ensureThemeState().presetTagEditId || null;
  };

  proto.setPresetTagEditId = function (id) {
    this._ensureThemeState().presetTagEditId = id || null;
  };

  /** The theme's own free-text vibe tags (the editable, removable ones). */
  proto.presetVibeTags = function (id) {
    const entry = this._ensureThemeState().library?.[id] || {};
    return Array.isArray(entry.tags) ? entry.tags.slice() : [];
  };

  /**
   * Apply a new vibe-tag set to the local library entry immediately (optimistic),
   * so the chips update without waiting for the backend sensor round-trip. The
   * derived-tag cache is invalidated so effective tags re-compute with the change.
   */
  proto.applyThemeTagsLocal = function (id, tags) {
    const state = this._ensureThemeState();
    const entry = state.library?.[id];
    if (!entry) return;
    const clean = [];
    const seen = new Set();
    (Array.isArray(tags) ? tags : []).forEach((t) => {
      const v = String(t || "").trim().toLowerCase();
      if (v && !seen.has(v)) {
        seen.add(v);
        clean.push(v);
      }
    });
    if (clean.length) entry.tags = clean;
    else delete entry.tags;
    state._presetTags = null; // effective tags now include the new vibe set
  };

  /**
   * Library ids after facet + search filtering, original order preserved.
   * Facet semantics match the gallery: OR within a facet, AND across facets.
   * Search matches the theme name and any derived tag.
   */
  proto.filteredPresetIds = function () {
    const state = this._ensureThemeState();
    const library = state.library || {};
    const tagsById = this._presetTagsForLibrary();
    const facets = state.presetFacets;
    const facetKeys = Object.keys(facets);
    const query = state.presetSearchQuery;

    return Object.keys(library).filter((id) => {
      const entry = tagsById[id] || { tags: [], set: new Set() };

      for (const facet of facetKeys) {
        const selected = facets[facet];
        if (selected.length && !selected.some((t) => entry.set.has(t))) {
          return false; // this facet has selections but none match -> drop
        }
      }

      if (query) {
        const haystack =
          String(library[id]?.name || id).toLowerCase() +
          " " +
          entry.tags.join(" ");
        if (!haystack.includes(query)) return false;
      }

      return true;
    });
  };

  /* =========================================================
     TOKEN FILTERING / MATCHING
     ========================================================= */

  /**
   * Determine whether a token matches the global search query.
   *
   * Search is future-safe:
   * - label
   * - key
   * - current value
   * - aliases (optional metadata)
   * - usage (optional metadata)
   * - affects (optional metadata)
   *
   * Optional metadata may be absent today. The selector treats
   * missing fields as empty arrays so the registry schema can grow
   * later without changing search logic.
   */
  proto.tokenMatchesGlobalThemeSearch = function (tokenDef, currentValue = "", query = "") {
    const normalizedQuery = String(query || "").toLowerCase();
    if (!normalizedQuery) return true;

    const label = String(tokenDef?.label || "").toLowerCase();
    const key = String(tokenDef?.key || "").toLowerCase();
    const value = String(currentValue || "").toLowerCase();

    const aliases = Array.isArray(tokenDef?.aliases)
      ? tokenDef.aliases.map((entry) => String(entry || "").toLowerCase())
      : [];

    const usage = Array.isArray(tokenDef?.usage)
      ? tokenDef.usage.map((entry) => String(entry || "").toLowerCase())
      : [];

    const affects = Array.isArray(tokenDef?.affects)
      ? tokenDef.affects.map((entry) => String(entry || "").toLowerCase())
      : [];

    if (label.includes(normalizedQuery)) return true;
    if (key.includes(normalizedQuery)) return true;
    if (value.includes(normalizedQuery)) return true;
    if (aliases.some((entry) => entry.includes(normalizedQuery))) return true;
    if (usage.some((entry) => entry.includes(normalizedQuery))) return true;
    if (affects.some((entry) => entry.includes(normalizedQuery))) return true;

    return false;
  };

  /**
   * Determine whether a token matches a group-local search query.
   * This uses the same metadata-aware matching logic as global
   * search, but the query is sourced from one expanded group.
   */
  proto.tokenMatchesThemeGroupSearch = function (tokenDef, currentValue = "", group) {
    const localQuery = this.getThemeGroupSearchQuery(group);
    return this.tokenMatchesGlobalThemeSearch(tokenDef, currentValue, localQuery);
  };

  /**
   * Returns the token registry filtered by:
   * - palette exclusion if provided
   * - selected group filter
   * - modified-only toggle
   * - global search
   *
   * Group-local search is intentionally applied later per-group so
   * each expanded section can narrow its own visible rows without
   * affecting sibling groups.
   */
  proto.filteredThemeTokens = function (allTokensRegistry, options = {}) {
    const state = this._ensureThemeState();
    const { tokens, sources } = this.resolvedTheme();

    const query = state.tokenSearchQuery;
    const modifiedOnly = state.modifiedOnly;
    const selectedGroupFilter = state.selectedGroupFilter || "all";
    const excludeKeys = options.excludeKeys instanceof Set ? options.excludeKeys : new Set();

    return allTokensRegistry.filter((tokenDef) => {
      const key = tokenDef.key;
      const value = tokens[key] || "";
      const source = sources[key] || "ha";
      const group = tokenDef.group || "";

      /* -----------------------------------------------------
         PALETTE EXCLUSION
         ----------------------------------------------------- */
      if (excludeKeys.has(key)) {
        return false;
      }

      /* -----------------------------------------------------
         MODIFIED FILTER
         ----------------------------------------------------- */
      if (modifiedOnly && source !== "draft") {
        return false;
      }

      /* -----------------------------------------------------
         GROUP FILTER
         ----------------------------------------------------- */
      if (selectedGroupFilter === "modified") {
        if (source !== "draft") {
          return false;
        }
      } else if (selectedGroupFilter !== "all" &&
                 group !== selectedGroupFilter &&
                 !group.startsWith(selectedGroupFilter + " — ")) {
        return false;
      }

      /* -----------------------------------------------------
         GLOBAL SEARCH
         ----------------------------------------------------- */
      if (!this.tokenMatchesGlobalThemeSearch(tokenDef, value, query)) {
        return false;
      }

      return true;
    });
  };

  /**
   * Returns the filtered tokens for one specific group after
   * applying the group-local search query.
   */
  proto.filteredThemeTokensForGroup = function (group, allTokensRegistry, options = {}) {
    const { tokens } = this.resolvedTheme();

    return this.filteredThemeTokens(allTokensRegistry, options).filter((tokenDef) => {
      if (tokenDef.group !== group) {
        return false;
      }

      const value = tokens[tokenDef.key] || "";
      return this.tokenMatchesThemeGroupSearch(tokenDef, value, group);
    });
  };

  /**
   * Count visible total and draft-modified tokens for a group after
   * all active filter rules are applied.
   *
   * This is used by group headers for:
   *   Group Name (modified / total)
   */
  proto.themeGroupCounts = function (group, allTokensRegistry, options = {}) {
    const { sources } = this.resolvedTheme();

    const visibleGroupTokens = this.filteredThemeTokensForGroup(group, allTokensRegistry, options);

    const total = visibleGroupTokens.length;
    const modified = visibleGroupTokens.filter((tokenDef) => {
      const source = sources[tokenDef.key] || "ha";
      return source === "draft";
    }).length;

    return { modified, total };
  };

  /**
   * Search should not feel broken when matches are hidden inside a
   * collapsed group. If global search is active and a group has at
   * least one visible match, the renderer can use this selector to
   * force that group open.
   */
  proto.shouldForceThemeGroupOpenForSearch = function (group, allTokensRegistry, options = {}) {
    const state = this._ensureThemeState();
    if (!state.tokenSearchQuery) return false;

    const counts = this.themeGroupCounts(group, allTokensRegistry, options);
    return counts.total > 0;
  };
}
