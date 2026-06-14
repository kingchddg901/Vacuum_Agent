/**
 * ============================================================
 * BINDINGS: THEME EDITOR
 * ============================================================
 *
 * PURPOSE
 * -------
 * Connect theme-editor UI controls to backend theme services and
 * card-side editor state.
 *
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * This file owns interaction wiring for the theme editor:
 * - tabs
 * - preset/theme selection
 * - token editing
 * - alpha editing
 * - per-token reset
 * - per-group reset
 * - group collapse / expand
 * - global group filter chips
 * - global search
 * - group-local search
 * - alpha-input double tap → color picker behavior
 *
 * It does NOT own:
 * - persisted theme state
 * - token rendering
 * - registry definitions
 * - theme preview resolution
 *
 *
 * SOURCE OF TRUTH
 * ---------------
 * The backend remains the source of truth for persisted theme data.
 * This file may update the live preview optimistically for
 * responsiveness, but persistent changes always flow through the
 * backend draft / theme services.
 *
 *
 * DRAFT SHAPE COMPATIBILITY
 * ------------------------
 * The theme editor now understands both:
 * - legacy draft buckets (colors / alpha)
 * - emerging flat token draft payloads (tokens)
 *
 * This keeps the editor ready for richer token metadata without
 * breaking older backend payloads during the transition.
 *
 *
 * INTERACTION RULES
 * -----------------
 * - color text fields use input
 * - sliders / number inputs use input
 * - color picker uses change
 * - alpha slider uses input
 * - alpha input double tap opens color picker
 * - drag movement cancels picker tap detection
 * - reset removes draft override rather than duplicating fallback
 *
 * ============================================================
 */

import { applyThemeToCard } from "../styles/apply-theme.js";
import { THEME_GROUPS, THEME_TOKEN_MAP, THEME_TOKEN_REGISTRY } from "../theme-tokens/index.js";
import { sliceThemeByTypes, themeKeyCount, detectFloorScope, clampThemeScalars } from "../theme-tokens/floor-scope.js";
import { MARBLE_PRESETS } from "../theme-tokens/floor-presets.js";

/* =========================================================
   HELPERS
   ========================================================= */

/**
 * Convert an rgb() / rgba() string returned by getComputedStyle into
 * a "#RRGGBB" hex string suitable for <input type="color">.
 * Returns null if the string cannot be parsed.
 */
function _rgbToHex(rgb) {
  if (!rgb) return null;
  const match = rgb.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
  if (!match) return null;
  const [, r, g, b] = match;
  return (
    "#" +
    [r, g, b]
      .map((n) => parseInt(n, 10).toString(16).padStart(2, "0"))
      .join("")
  );
}

/* =========================================================
   PALETTE EXCLUSION
   ========================================================= */

const PALETTE_KEYS = new Set([
  "--evcc-accent",
  "--evcc-surface-base",
  "--evcc-text-primary",
  "--evcc-radius-card",
]);

/* =========================================================
   DOUBLE-TAP CONFIG
   ========================================================= */

const DOUBLE_TAP_DELAY_MS = 300;
const DOUBLE_TAP_MOVE_THRESHOLD_PX = 6;

/**
 * Mix theme editor binding methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardBindings prototype to extend.
 */
export function applyThemeBindings(proto) {

  // Apply a SCOPED theme envelope — an uploaded per-floor file OR a built-in
  // preset — onto the ACTIVE theme. Validate types against the registry,
  // confirm the exact "Replace" list, clamp values to range, skip unknown
  // namespaces. Shared by the scoped Upload path and Apply Preset.
  proto._applyScopedThemeImport = async function (envelope, sourceLabel) {
    const { known, unknown } = detectFloorScope(envelope);
    if (!known.length) {
      alert(
        `${sourceLabel} has no floor types this version recognises` +
        (unknown.length ? ` (unsupported: ${unknown.join(", ")}).` : ".")
      );
      return false;
    }
    const proceed = confirm(
      `Replace these floor types on the active theme:\n  ${known.join(", ")}` +
      (unknown.length
        ? `\n\nSkipped — unsupported in this version:\n  ${unknown.join(", ")}`
        : "") +
      `\n\nThis overwrites those types. Continue?`
    );
    if (!proceed) return false;

    const { envelope: clamped, corrected } = clampThemeScalars(envelope, THEME_TOKEN_MAP);
    await this.card._actions.importTheme(
      { ...clamped, scope: known },
      this.card._config.vacuum_entity_id
    );
    await this._refreshThemeFromBackend();
    alert(
      `Replaced ${known.join(", ")} from ${sourceLabel}.` +
      (corrected ? ` ${corrected} value(s) clamped to range.` : "") +
      (unknown.length ? ` Skipped: ${unknown.join(", ")}.` : "")
    );
    return true;
  };

  proto._bindThemeEditor = function () {
    this._bindThemeTabs();
    this._bindThemePresets();
    this._bindPresetFilters();
    this._bindThemeGroupFilters();
    this._bindThemeGroupToggles();
    this._bindThemeGlobalSearch();
    this._bindThemeGroupSearch();
    this._bindThemeTokenEdits();
    this._bindThemeAlphaEdits();
    this._bindThemeColorMixEdits();
    this._bindThemeTokenResets();
    this._bindThemeGroupResets();
    this._bindThemeColorPickerFromAlphaInput();
    this._bindThemeActions();
  };

  /* =========================================================
     TABS
     ========================================================= */

  proto._bindThemeTabs = function () {
    this.card._onAll("[data-theme-tab]", "click", (e) => {
      const tab = e.currentTarget.dataset.themeTab;
      this.card._state.setThemeSubTab(tab);
      this.card._scheduleRender();
    });
  };

  /* =========================================================
     PRESETS / THEMES
     ========================================================= */

  proto._bindThemePresets = function () {
    this.card._onAll("[data-theme-preset]", "click", async (e) => {
      const themeId = e.currentTarget.dataset.themePreset;
      if (!themeId) return;

      const result = await this.card._actions.setActiveTheme(
        this.card._config.vacuum_entity_id,
        themeId
      );

      if (result?.ok === false) {
        alert(result.reason || "Unable to select theme.");
        return;
      }

      const activeThemeId =
        result?.active_theme_id ??
        result?.theme_id ??
        themeId;

      this.card._state.applyThemeActivation(activeThemeId, {
        clearDraft: result?.draft_dirty === false,
      });
      applyThemeToCard(this.card);
      this.card._scheduleRender();

      await this._refreshThemeFromBackend({
        fallbackActiveThemeId: activeThemeId,
        fallbackDraftDirty: false,
      });
    });
  };

  /* =========================================================
     PRESET FACET FILTER + SEARCH (Themes grid)
     ========================================================= */

  proto._bindPresetFilters = function () {
    this.card._onAll("[data-preset-facet]", "click", (e) => {
      const facet = e.currentTarget.dataset.presetFacet;
      const value = e.currentTarget.dataset.presetFacetValue;
      if (!facet || !value) return;
      this.card._state.togglePresetFacet(facet, value);
      this.card._scheduleRender();
    });

    this.card._on(this.card.$("[data-preset-search]"), "input", (e) => {
      this.card._state.setPresetSearchQuery(e.target.value);
      this.card._scheduleRender();
    });

    this.card._onAll("[data-preset-clear]", "click", () => {
      this.card._state.clearPresetFilters();
      this.card._scheduleRender();
    });
  };

  /* =========================================================
     GROUP FILTER CHIPS
     ========================================================= */

  proto._bindThemeGroupFilters = function () {
    this.card._onAll("[data-theme-group-filter]", "click", (e) => {
      const filterValue = e.currentTarget.dataset.themeGroupFilter || "all";
      this.card._state.setThemeGroupFilter(filterValue);
      if (THEME_GROUPS.includes(filterValue)) {
        this.card._state.setThemeFocusedGroup(filterValue);
      }
      this._autoOpenMatchingThemeGroups();
      this.card._scheduleRender();
    });
  };

  /* =========================================================
     GROUP COLLAPSE / EXPAND
     ========================================================= */

  proto._bindThemeGroupToggles = function () {
    this.card._onAll("[data-theme-group-toggle]", "click", (e) => {
      const group = e.currentTarget.dataset.themeGroupToggle;
      if (!group) return;

      this.card._state.setThemeFocusedGroup(group);
      this.card._state.toggleThemeGroup(group);
      this.card._scheduleRender();
    });
  };

  /* =========================================================
     GLOBAL SEARCH
     ========================================================= */

  proto._bindThemeGlobalSearch = function () {
    this.card._on(this.card.$("[data-theme-search]"), "input", (e) => {
      this.card._state.setThemeSearchQuery(e.target.value);
      this._autoOpenMatchingThemeGroups();
      this.card._scheduleRender();
    });

    this.card._on(this.card.$("[data-theme-modified-only]"), "change", (e) => {
      this.card._state.setThemeModifiedOnly(e.target.checked);
      this._autoOpenMatchingThemeGroups();
      this.card._scheduleRender();
    });
  };

  /* =========================================================
     GROUP-LOCAL SEARCH
     ========================================================= */

  proto._bindThemeGroupSearch = function () {
    this.card._onAll("[data-theme-group-search]", "input", (e) => {
      const group = e.currentTarget.dataset.themeGroupSearch;
      if (!group) return;

      this.card._state.setThemeFocusedGroup(group);
      this.card._state.setThemeGroupSearchQuery(group, e.target.value);
      this.card._scheduleRender();
    });
  };

  /* =========================================================
     TOKEN EDITING
     ========================================================= */

  proto._bindThemeTokenEdits = function () {
    this.card._onAll("[data-theme-token]", "input", async (e) => {
      const token = e.currentTarget.dataset.themeToken;
      const tokenDef = THEME_TOKEN_MAP[token];
      if (!tokenDef) return;

      const isRange = e.currentTarget.type === "range";

      let value = e.currentTarget.value;

      this.card._state.setThemeFocusedGroup(tokenDef.group);
      this._syncThemeRowInputs(e.currentTarget, token);

      if (this._isScalarThemeType(tokenDef.type)) {
        value = this._formatScalarThemeValue(value, tokenDef, e.currentTarget);
      }

      const payload = this._buildDraftPayload(token, value, tokenDef);
      if (!Object.keys(payload).length) return;

      // Range sliders flood `input` on every drag pixel — skip the backend call
      // here and let `change` handle persistence so the drag stays smooth.
      // For color tokens, also skip if the value is a partial/invalid expression
      // (e.g. the user is mid-way through typing a color-mix() string).
      const shouldPersist = !isRange && this._isSettledThemeValue(value, tokenDef);
      if (shouldPersist) {
        await this.card._actions.updateWorkingDraft(
          this.card._config.vacuum_entity_id,
          payload
        );
      }

      this.card._state.applyThemeDraftPatch(payload);
      applyThemeToCard(this.card);
    });

    this.card._onAll("[data-theme-color-input]", "change", async (e) => {
      const token = e.currentTarget.dataset.themeColorInput;
      const tokenDef = THEME_TOKEN_MAP[token];
      if (!tokenDef) return;

      const value = e.currentTarget.value || "";
      this.card._state.setThemeFocusedGroup(tokenDef.group);
      this._syncThemeRowInputs(e.currentTarget, token, value);

      const payload = this._buildDraftPayload(token, value, tokenDef);
      if (!Object.keys(payload).length) return;

      await this.card._actions.updateWorkingDraft(
        this.card._config.vacuum_entity_id,
        payload
      );

      this.card._state.applyThemeDraftPatch(payload);
      applyThemeToCard(this.card);
      this.card._scheduleDeferredRender?.();
    });

    this.card._onAll("[data-theme-token]", "change", async (e) => {
      const isRange = e.currentTarget.type === "range";

      if (isRange) {
        const token = e.currentTarget.dataset.themeToken;
        const tokenDef = THEME_TOKEN_MAP[token];
        if (tokenDef) {
          let value = e.currentTarget.value;
          if (this._isScalarThemeType(tokenDef.type)) {
            value = this._formatScalarThemeValue(value, tokenDef, e.currentTarget);
          }
          const payload = this._buildDraftPayload(token, value, tokenDef);
          if (Object.keys(payload).length) {
            await this.card._actions.updateWorkingDraft(
              this.card._config.vacuum_entity_id,
              payload
            );
            this.card._state.applyThemeDraftPatch(payload);
            applyThemeToCard(this.card);
          }
        }
      }

      this.card._scheduleDeferredRender?.();
    });
  };

  /* =========================================================
     ALPHA EDITING
     ========================================================= */

  proto._bindThemeAlphaEdits = function () {
    this.card._onAll("[data-theme-alpha]", "input", (e) => {
      const token = e.currentTarget.dataset.themeAlpha;
      if (!token) return;
      const tokenDef = THEME_TOKEN_MAP[token];
      if (tokenDef?.group) {
        this.card._state.setThemeFocusedGroup(tokenDef.group);
      }

      const percent = this._clampThemeAlphaPercent(e.currentTarget.value);
      this._syncThemeAlphaControls(token, percent, e.currentTarget);

      // Apply locally so CSS vars update every frame while dragging —
      // no service call here to avoid flooding the backend and blocking
      // the double-tap gesture with async re-renders.
      this.card._state.applyThemeDraftPatch({ alpha: { [token]: percent / 100 } });
      applyThemeToCard(this.card);
    });

    this.card._onAll("[data-theme-alpha]", "change", async (e) => {
      const token = e.currentTarget.dataset.themeAlpha;
      if (!token) return;
      const percent = this._clampThemeAlphaPercent(e.currentTarget.value);

      await this.card._actions.updateWorkingDraft(
        this.card._config.vacuum_entity_id,
        { alpha: { [token]: percent / 100 } }
      );

      applyThemeToCard(this.card);
      this.card._scheduleDeferredRender?.();
    });
  };

  proto._clampThemeAlphaPercent = function (value) {
    const numeric = Number(value);
    if (Number.isNaN(numeric)) return 100;
    return Math.max(0, Math.min(100, Math.round(numeric)));
  };

  /**
   * Keep alpha slider visuals aligned while dragging.
   *
   * Bubble and indicator live in different containers:
   * - indicator stays inside the clipped rail
   * - bubble lives in the outer shell so it can extend past edges
   */
  proto._syncThemeAlphaControls = function (token, percent, sourceElement = null) {
    const row = sourceElement
      ? sourceElement.closest(".evcc-token-row")
      : this.card
          .shadowRoot
          ?.querySelector(`[data-theme-alpha="${token}"]`)
          ?.closest(".evcc-token-row");

    if (!row) return;

    const slider = row.querySelector(`[data-theme-alpha="${token}"]`);
    const bubble = row.querySelector(`[data-theme-alpha-bubble="${token}"]`);
    const indicator = row.querySelector(`[data-theme-alpha-indicator="${token}"]`);
    const shell = row.querySelector(".token-alpha-shell");
    const rail = row.querySelector(".token-alpha-rail");

    if (slider) {
      slider.value = String(percent);
    }

    if (!slider) return;

    const min = Number(slider.min) || 0;
    const max = Number(slider.max) || 100;
    const sliderValue = Number(slider.value) || 0;
    const ratio = max === min ? 0 : (sliderValue - min) / (max - min);

    if (indicator && rail) {
      const railWidth = rail.clientWidth;
      const indicatorX = ratio * railWidth;
      indicator.style.left = `${indicatorX}px`;
    }

    if (bubble && shell) {
      const shellWidth = shell.clientWidth;
      const bubbleX = ratio * shellWidth;
      bubble.style.left = `${bubbleX}px`;
      bubble.textContent = `${sliderValue}%`;
    }
  };

  /**
   * Keep paired controls inside one token row synchronized.
   */
  proto._syncThemeRowInputs = function (sourceElement, token, forcedValue = null) {
    const row = sourceElement.closest(".evcc-token-row");
    if (!row) return;

    const value = forcedValue ?? sourceElement.value;

    row.querySelectorAll(
      `[data-theme-token="${token}"], [data-theme-color-input="${token}"]`
    ).forEach((el) => {
      if (el !== sourceElement) {
        el.value = value;
      }
    });

    this._syncThemeScalarControls(row, token, value);
  };

  proto._syncThemeScalarControls = function (row, token, value) {
    if (!row) return;

    const bubble = row.querySelector(`[data-theme-slider-bubble="${token}"]`);
    if (!bubble) return;

    const suffix = row.dataset.themeTokenUnit || "";
    const slider = row.querySelector(`input[type="range"][data-theme-token="${token}"]`);

    if (slider) {
      slider.value = value;
    }

    bubble.textContent = `${value}${suffix}`;
  };

  /**
   * Returns true when a token value is complete enough to persist to the backend.
   * For color tokens, partial strings (mid-typing color-mix, incomplete hex) are
   * held back so we don't flood the backend with invalid CSS values.
   */
  proto._isSettledThemeValue = function (value, tokenDef) {
    if (!tokenDef || tokenDef.type !== "color") return true;
    const v = String(value || "").trim();
    if (!v) return true;
    if (/^#[0-9a-fA-F]{6}$/.test(v)) return true;
    if (/^#[0-9a-fA-F]{8}$/.test(v)) return true;
    // Valid complete color-mix: must have both closing parentheses and a %
    if (/^color-mix\(.*%.*\)$/is.test(v)) return true;
    // Named CSS color or var() reference — let it through
    if (/^var\(--[\w-]+\)$/.test(v)) return true;
    return false;
  };

  proto._isScalarThemeType = function (type) {
    return type === "size" || type === "number" || type === "duration";
  };

  proto._extractThemeScalarUnit = function (tokenDef, currentValue = "") {
    const current = String(currentValue || "").trim();

    if (tokenDef?.type === "duration") {
      const durationMatch = current.match(/^-?\d*\.?\d+\s*(ms|s)$/i);
      return durationMatch ? durationMatch[1].toLowerCase() : "ms";
    }

    if (tokenDef?.type === "size") {
      const sizeMatch = current.match(/^-?\d*\.?\d+\s*(px|rem|em|%|vh|vw|vmin|vmax|ch|ex)$/i);
      return sizeMatch ? sizeMatch[1].toLowerCase() : "px";
    }

    return "";
  };

  /**
   * Scalar controls preserve lightweight units where needed while
   * still emitting plain numbers for number-only tokens.
   */
  proto._formatScalarThemeValue = function (value, tokenDef, sourceElement = null) {
    const numeric = parseFloat(String(value || "").trim());
    if (Number.isNaN(numeric)) {
      return "";
    }

    if (tokenDef?.type === "number") {
      return `${numeric}`;
    }

    const row = sourceElement?.closest(".evcc-token-row") || null;
    const currentValue = row?.dataset.themeTokenUnit
      ? `${numeric}${row.dataset.themeTokenUnit}`
      : value;
    const unit = this._extractThemeScalarUnit(tokenDef, currentValue);

    return `${numeric}${unit}`;
  };

  /**
   * Map one token edit into the current backend draft payload shape.
   */
  proto._buildDraftPayload = function (token, value, tokenDef = null) {
    const def = tokenDef || THEME_TOKEN_MAP[token];
    if (!def) return {};

    if (def.type === "color") {
      return {
        tokens: { [token]: value },
        colors: { [token]: value },
      };
    }

    if (def.type === "alpha") {
      return { alpha: { [token]: value } };
    }

    return { tokens: { [token]: value } };
  };

  /* =========================================================
     COLOR-MIX EDITING
     ========================================================= */

  proto._bindThemeColorMixEdits = function () {
    // Ratio slider — local sync on input, backend on change
    this.card._onAll("[data-theme-colormix][data-colormix-part='ratio']", "input", (e) => {
      const token = e.currentTarget.dataset.themeColormix;
      if (!token) return;
      const row = e.currentTarget.closest(".evcc-token-row");
      if (!row) return;

      const ratio = Math.max(0, Math.min(100, Math.round(Number(e.currentTarget.value))));
      const label = row.querySelector(`[data-colormix-ratio-label="${token}"]`);
      if (label) label.textContent = `${ratio}%`;

      const expr = this._readColorMixExpr(row, token, { ratio });
      if (!expr) return;
      this.card._state.applyThemeDraftPatch({ tokens: { [token]: expr }, colors: { [token]: expr } });
      applyThemeToCard(this.card);
      this._syncColorMixPreview(row, expr);
    });

    this.card._onAll("[data-theme-colormix][data-colormix-part='ratio']", "change", async (e) => {
      const token = e.currentTarget.dataset.themeColormix;
      if (!token) return;
      const row = e.currentTarget.closest(".evcc-token-row");
      const ratio = Math.max(0, Math.min(100, Math.round(Number(e.currentTarget.value))));
      const expr = this._readColorMixExpr(row, token, { ratio });
      if (!expr) return;
      const payload = { tokens: { [token]: expr }, colors: { [token]: expr } };
      await this.card._actions.updateWorkingDraft(this.card._config.vacuum_entity_id, payload);
      this.card._state.applyThemeDraftPatch(payload);
      applyThemeToCard(this.card);
      this.card._scheduleDeferredRender?.();
    });

    // Color reference text inputs — backend on change only (typing)
    this.card._onAll(
      "[data-theme-colormix][data-colormix-part='color1'], [data-theme-colormix][data-colormix-part='color2']",
      "change",
      async (e) => {
        const token = e.currentTarget.dataset.themeColormix;
        if (!token) return;
        const row = e.currentTarget.closest(".evcc-token-row");
        const expr = this._readColorMixExpr(row, token);
        if (!expr) return;
        const payload = { tokens: { [token]: expr }, colors: { [token]: expr } };
        await this.card._actions.updateWorkingDraft(this.card._config.vacuum_entity_id, payload);
        this.card._state.applyThemeDraftPatch(payload);
        applyThemeToCard(this.card);
        this._syncColorMixPreview(row, expr);
        this.card._scheduleDeferredRender?.();
      }
    );

    // Live swatch + preview on text input (no backend call)
    this.card._onAll(
      "[data-theme-colormix][data-colormix-part='color1'], [data-theme-colormix][data-colormix-part='color2']",
      "input",
      (e) => {
        const token = e.currentTarget.dataset.themeColormix;
        if (!token) return;
        const row = e.currentTarget.closest(".evcc-token-row");
        const expr = this._readColorMixExpr(row, token);
        if (!expr) return;
        this._syncColorMixPreview(row, expr);
      }
    );
  };

  proto._readColorMixExpr = function (row, token, overrides = {}) {
    if (!row) return null;
    const color1El = row.querySelector(`[data-colormix-part="color1"]`);
    const color2El = row.querySelector(`[data-colormix-part="color2"]`);
    const ratioEl  = row.querySelector(`[data-colormix-part="ratio"]`);
    if (!color1El || !color2El || !ratioEl) return null;

    const color1 = (color1El.value || "").trim();
    const color2 = (color2El.value || "").trim();
    const ratio  = "ratio" in overrides
      ? overrides.ratio
      : Math.max(0, Math.min(100, Math.round(Number(ratioEl.value))));

    if (!color1 || !color2) return null;
    return `color-mix(in srgb, ${color1} ${ratio}%, ${color2} ${100 - ratio}%)`;
  };

  proto._syncColorMixPreview = function (row, expr) {
    if (!row || !expr) return;
    const preview = row.querySelector(".token-colormix-preview");
    if (preview) preview.style.background = expr;
  };

  /* =========================================================
     PER-TOKEN RESET
     ========================================================= */

  proto._bindThemeTokenResets = function () {
    this.card._onAll("[data-theme-reset]", "click", async (e) => {
      const token = e.currentTarget.dataset.themeReset;
      const tokenDef = THEME_TOKEN_MAP[token];
      if (!tokenDef) return;

      this.card._state.setThemeFocusedGroup(tokenDef.group);
      const payload = this._buildDraftResetPayload(token, tokenDef);
      if (!Object.keys(payload).length) {
        return;
      }

      await this.card._actions.updateWorkingDraft(
        this.card._config.vacuum_entity_id,
        payload
      );

      this.card._state.applyThemeDraftPatch(payload);
      await this._refreshThemeFromBackend();
    });
  };

  proto._buildDraftResetPayload = function (token, tokenDef) {
    if (tokenDef.type === "color") {
      return {
        tokens: { [token]: null },
        colors: { [token]: null },
        alpha: { [token]: null },
      };
    }

    if (tokenDef.type === "alpha") {
      return { alpha: { [token]: null } };
    }

    return { tokens: { [token]: null } };
  };

  /* =========================================================
     PER-GROUP RESET
     ========================================================= */

  proto._bindThemeGroupResets = function () {
    this.card._onAll("[data-theme-group-reset]", "click", async (e) => {
      e.stopPropagation();

      const group = e.currentTarget.dataset.themeGroupReset;
      if (!group) return;

      this.card._state.setThemeFocusedGroup(group);
      const resetPayload = this._buildThemeGroupResetPayload(group);
      if (!resetPayload) return;

      await this.card._actions.updateWorkingDraft(
        this.card._config.vacuum_entity_id,
        resetPayload
      );

      await this._refreshThemeFromBackend();
    });
  };

  proto._buildThemeGroupResetPayload = function (group) {
    const groupTokens = this.card._state.filteredThemeTokensForGroup(
      group,
      THEME_TOKEN_REGISTRY,
      { excludeKeys: PALETTE_KEYS }
    );

    const { sources } = this.card._state.resolvedTheme();

    const tokens = {};
    const colors = {};
    const alpha = {};
    let hasAny = false;

    groupTokens.forEach((tokenDef) => {
      const source = sources[tokenDef.key] || "ha";
      if (source !== "draft") return;

      if (tokenDef.type === "color") {
        tokens[tokenDef.key] = null;
        colors[tokenDef.key] = null;
        alpha[tokenDef.key] = null;
        hasAny = true;
      } else if (tokenDef.type === "alpha") {
        alpha[tokenDef.key] = null;
        hasAny = true;
      } else {
        tokens[tokenDef.key] = null;
        hasAny = true;
      }
    });

    if (!hasAny) return null;

    const payload = {};
    if (Object.keys(tokens).length) payload.tokens = tokens;
    if (Object.keys(colors).length) payload.colors = colors;
    if (Object.keys(alpha).length) payload.alpha = alpha;
    return payload;
  };

  /* =========================================================
     ALPHA INPUT DOUBLE-TAP → PICKER
     =========================================================
     The alpha input owns all interaction:
     * drag = native alpha slider
     * double tap = open hidden color picker
     *
     * Movement between pointerdown and pointerup cancels the tap so
     * normal slider drags do not accidentally trigger the picker.
     ========================================================= */

  proto._bindThemeColorPickerFromAlphaInput = function () {
    // lastTapMap lives on `this` so it survives re-renders — a fresh Map on
    // every bindEvents() call loses tap-1 state when a render fires between taps.
    if (!this._alphaTapMap) {
      this._alphaTapMap = new Map();
    }
    const lastTapMap = this._alphaTapMap;

    this.card._onAll("[data-color-swatch]", "pointerdown", (e) => {
      const input = e.currentTarget;
      const token = input.dataset.colorSwatch;
      if (!token) return;

      const startX = e.clientX;
      const startY = e.clientY;
      let moved = false;

      const onMove = (ev) => {
        const dx = Math.abs(ev.clientX - startX);
        const dy = Math.abs(ev.clientY - startY);

        if (dx > DOUBLE_TAP_MOVE_THRESHOLD_PX || dy > DOUBLE_TAP_MOVE_THRESHOLD_PX) {
          moved = true;
        }
      };

      const cleanup = () => {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        window.removeEventListener("pointercancel", onCancel);
      };

      const onUp = () => {
        const now = Date.now();
        const lastTap = lastTapMap.get(token) || 0;
        const isDoubleTap = !moved && (now - lastTap < DOUBLE_TAP_DELAY_MS);

        lastTapMap.set(token, now);

        if (isDoubleTap) {
          // Re-query from live DOM — `input` may be detached if a render
          // happened between the two taps.
          const liveSlider = this.card.shadowRoot
            ?.querySelector(`[data-theme-alpha="${token}"]`);
          const picker = liveSlider
            ?.closest(".evcc-token-row")
            ?.querySelector(`[data-theme-color-input="${token}"]`);

          if (picker) {
            // Resolve the actual rendered color so tokens with computed values
            // (color-mix, var references, etc.) open the picker at the right hue
            // instead of the #000000 fallback from the static render.
            const resolved = this._resolveTokenColorHex(token);
            if (resolved) {
              picker.value = resolved;
            }
            picker.click();
          }
        }

        cleanup();
      };

      const onCancel = () => {
        cleanup();
      };

      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
      window.addEventListener("pointercancel", onCancel);
    });
  };

  /* =========================================================
     TOKEN COLOR RESOLUTION
     ========================================================= */

  /**
   * Measure the actual rendered color of a CSS token by injecting a
   * 1×1 element into the shadow root (so it inherits the card's CSS
   * custom properties) and reading getComputedStyle.
   *
   * This handles tokens whose value is a CSS expression like
   * color-mix() or var() — things that can't be converted to a picker
   * hex at render time but CAN be resolved in the live DOM.
   *
   * Returns a "#RRGGBB" string, or null if resolution fails.
   */
  proto._resolveTokenColorHex = function (token) {
    const root = this.card.shadowRoot;
    if (!root) return null;

    try {
      const el = document.createElement("div");
      el.style.cssText = `
        position: absolute;
        left: -9999px;
        width: 1px;
        height: 1px;
        background-color: var(${token});
        pointer-events: none;
      `;
      root.appendChild(el);
      const rgb = getComputedStyle(el).backgroundColor;
      root.removeChild(el);
      return _rgbToHex(rgb);
    } catch {
      return null;
    }
  };

  /* =========================================================
     THEME ACTIONS
     ========================================================= */

  proto._bindThemeActions = function () {
    this.card._on(this.card.$("[data-action='save-theme']"), "click", async () => {
      const state = this.card._state._ensureThemeState();

      let result;
      if (state.activeThemeId) {
        result = await this.card._actions.overwriteTheme(
          this.card._config.vacuum_entity_id,
          state.activeThemeId
        );
      } else {
        const name = prompt("Enter a name for your new theme:");
        if (!name) return;

        result = await this.card._actions.saveThemeAsNew(
          this.card._config.vacuum_entity_id,
          name,
          false
        );
      }

      // Apply the service response directly — don't read the sensor here,
      // it may lag. The response carries the authoritative post-save state.
      if (result?.ok !== false) {
        const savedThemeId =
          result?.active_theme_id ?? result?.theme_id ?? state.activeThemeId;
        this.card._state.applyThemeActivation(savedThemeId, { clearDraft: true });
      }

      await this._refreshThemeFromBackend();
    });

    this.card._on(this.card.$("[data-action='reset-draft']"), "click", async () => {
      const state = this.card._state._ensureThemeState();
      const result = await this.card._actions.revertDraft(
        this.card._config.vacuum_entity_id
      );

      if (result?.ok !== false) {
        const revertedThemeId =
          result?.active_theme_id ?? state.activeThemeId;
        this.card._state.applyThemeActivation(revertedThemeId, { clearDraft: true });
      }

      await this._refreshThemeFromBackend();
    });

    this.card._onAll("[data-action='delete-preset']", "click", async (e) => {
      e.stopPropagation();

      const themeId = e.currentTarget.dataset.presetId;
      if (!themeId) return;
      if (!confirm(`Delete theme "${themeId}"?`)) return;

      await this.card._actions.deleteTheme(themeId);
      await this._refreshThemeFromBackend();
    });

    this.card._on(this.card.$("[data-action='export-theme']"), "click", async () => {
      const state = this.card._state._ensureThemeState();
      const themeId = state.activeThemeId;

      if (!themeId) {
        alert("No active theme to export.");
        return;
      }

      const result = await this.card._actions.exportTheme(themeId);
      const themeStr = JSON.stringify(result, null, 2);

      try {
        await navigator.clipboard.writeText(themeStr);
        alert("Theme copied to clipboard!");
      } catch {
        console.log(themeStr);
        alert("Copied to console instead.");
      }
    });

    this.card._on(this.card.$("[data-action='import-theme']"), "click", async () => {
      const input = prompt("Paste theme JSON here:");
      if (!input) return;

      try {
        const payload = JSON.parse(input);

        await this.card._actions.importTheme(payload);
        await this._refreshThemeFromBackend();

        alert("Theme imported successfully.");
      } catch {
        alert("Invalid theme JSON.");
      }
    });

    /* =========================================================
       DOWNLOAD / UPLOAD — file-based variants of export/import
       =========================================================
       The clipboard export/import works inside one HA session.
       File download/upload exists so users can:
         - back up a theme to disk
         - share a theme by attaching a file
         - migrate themes between HA installs (the primary use case
           — themes are one of the few things portable between the
           current and the next major version of this integration)
       ========================================================= */

    this.card._on(this.card.$("[data-action='download-theme']"), "click", async () => {
      const state = this.card._state._ensureThemeState();
      const themeId = state.activeThemeId;

      if (!themeId) {
        alert("No active theme to download.");
        return;
      }

      let result;
      try {
        result = await this.card._actions.exportTheme(themeId);
      } catch (err) {
        alert(`Failed to export theme: ${err?.message ?? String(err)}`);
        return;
      }

      const themeStr = JSON.stringify(result, null, 2);

      // Derive a filename from the theme name (or fall back to ID).
      // Strip filesystem-unfriendly characters; collapse whitespace.
      const rawName = String(result?.name ?? result?.theme_id ?? themeId);
      const safeName = rawName
        .replace(/[^\w\s.-]/g, "")
        .trim()
        .replace(/\s+/g, "-")
        .toLowerCase() || "theme";
      const stamp = new Date().toISOString().slice(0, 10);
      const filename = `evcc-theme-${safeName}-${stamp}.json`;

      // Trigger download via temp anchor. Anchor must live on the
      // top document (not the shadow root) for the browser's
      // download dispatch to pick it up. URL.revokeObjectURL releases
      // the blob URL after the click is processed.
      const blob = new Blob([themeStr], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.style.display = "none";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 0);
    });

    this.card._on(this.card.$("[data-action='upload-theme']"), "click", () => {
      // Create a hidden file input and trigger it. The file picker
      // is a user-action consequence (the click handler runs in
      // the click event handler stack), which browsers require for
      // file-dialog access.
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".json,application/json";
      input.style.display = "none";

      input.addEventListener("change", async (event) => {
        const file = event.target?.files?.[0];
        if (!file) {
          document.body.removeChild(input);
          return;
        }

        try {
          const text = await file.text();
          const payload = JSON.parse(text);

          if (Array.isArray(payload?.scope) && payload.scope.length) {
            // SCOPED import — replace the file's floor namespaces on the active
            // theme (confirm + clamp + skip-unknown live in the shared helper).
            await this._applyScopedThemeImport(payload, `"${file.name}"`);
          } else {
            // Full import — adds a new library theme (legacy behavior).
            await this.card._actions.importTheme(payload);
            await this._refreshThemeFromBackend();
            alert(`Theme imported from ${file.name}.`);
          }
        } catch (err) {
          alert(
            `Failed to import "${file.name}": ${err?.message ?? String(err)}`
          );
        } finally {
          if (input.parentNode === document.body) {
            document.body.removeChild(input);
          }
        }
      });

      document.body.appendChild(input);
      input.click();
    });

    // Scoped export: download ONE floor type's namespace as a shareable
    // preset. Slices the full export by --evcc-floor-{type}-* across
    // tokens/colors/alpha and stamps scope:[type]. Mirrors download-theme.
    this.card._on(this.card.$("[data-action='download-floor-theme']"), "click", async () => {
      const state = this.card._state._ensureThemeState();
      const themeId = state.activeThemeId;
      if (!themeId) {
        alert("No active theme to export.");
        return;
      }

      const select = this.card.$("[data-theme-floor-scope]");
      const type = select?.value;
      if (!type) {
        alert("Pick a floor type to export.");
        return;
      }

      let result;
      try {
        result = await this.card._actions.exportTheme(themeId);
      } catch (err) {
        alert(`Failed to export theme: ${err?.message ?? String(err)}`);
        return;
      }

      const scoped = sliceThemeByTypes(result, [type]);
      if (!themeKeyCount(scoped)) {
        alert(
          `This theme has no customised "${type}" floor settings to export. ` +
          `Adjust and Save the ${type} tokens first.`
        );
        return;
      }

      const themeStr = JSON.stringify(scoped, null, 2);
      const safeName =
        String(result?.theme?.name ?? "theme")
          .replace(/[^a-z0-9._-]+/gi, "-")
          .toLowerCase() || "theme";
      const stamp = new Date().toISOString().slice(0, 10);
      const filename = `evcc-floor-${type}-${safeName}-${stamp}.json`;

      const blob = new Blob([themeStr], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.style.display = "none";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 0);
    });

    // Apply a built-in MARBLE preset (Carrara / Portoro / Calacatta) onto the
    // active theme — marble-scoped, via the shared scoped-import helper.
    this.card._on(this.card.$("[data-action='apply-floor-preset']"), "click", async () => {
      const select = this.card.$("[data-floor-preset]");
      const preset = MARBLE_PRESETS.find((p) => p.id === select?.value);
      if (!preset) {
        alert("Pick a preset to apply.");
        return;
      }
      await this._applyScopedThemeImport(preset.envelope, `the ${preset.name} preset`);
    });
  };

  /* =========================================================
     BACKEND REFRESH
     ========================================================= */

  proto._refreshThemeFromBackend = async function (options = {}) {
    const fallbackActiveThemeId = options?.fallbackActiveThemeId ?? null;
    const fallbackDraftDirty = options?.fallbackDraftDirty;

    // Do NOT read sensor.attributes here — the sensor state may still be the
    // pre-change snapshot (up to 30s stale on the default poll cycle). The
    // caller already applied the correct state optimistically via
    // applyThemeActivation. The next hass push will sync setBackendThemeState
    // once the backend sensor reflects the change (immediately, now that the
    // sensor has a push callback).
    const library = await this.card._actions.getThemeLibrary();
    if (library) {
      this.card._state.setThemeLibrary(library);
    }

    if (
      fallbackActiveThemeId &&
      this.card._state.getActiveTheme()?.id !== fallbackActiveThemeId &&
      this.card._state._ensureThemeState().activeThemeId !== fallbackActiveThemeId
    ) {
      this.card._state.applyThemeActivation(fallbackActiveThemeId, {
        clearDraft: fallbackDraftDirty === false,
      });
    }

    this._autoOpenMatchingThemeGroups();
    applyThemeToCard(this.card);
    this.card._scheduleRender();
  };

  /* =========================================================
     SEARCH / FILTER ASSIST
     ========================================================= */

  proto._autoOpenMatchingThemeGroups = function () {
    const state = this.card._state._ensureThemeState();

    THEME_GROUPS.forEach((group) => {
      if (
        this.card._state.shouldForceThemeGroupOpenForSearch(
          group,
          THEME_TOKEN_REGISTRY,
          { excludeKeys: PALETTE_KEYS }
        )
      ) {
        state.groupOpen[group] = true;
      }
    });
  };
}
