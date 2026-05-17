/**
 * ============================================================
 * RENDERER: THEME EDITOR
 * ============================================================
 *
 * Renders the theme editor UI — preset selector, palette, and
 * grouped token editor with unified alpha/color rail for color
 * tokens and range slider for numeric tokens.
 *
 * ============================================================
 */

import {
  THEME_TOKEN_REGISTRY,
  THEME_GROUPS,
} from "../theme-tokens/index.js";

/* =========================================================
   COLOR-MIX PARSER
   ========================================================= */

/**
 * Parse a CSS color-mix(in srgb, COLOR1 R%, COLOR2 R2%) expression.
 * Returns { color1, ratio, color2, ratio2 } or null if not a color-mix.
 */
function _parseColorMix(value) {
  if (!value) return null;
  const v = String(value).trim();
  if (!/^color-mix\(/i.test(v)) return null;

  const parenOpen = v.indexOf("(");
  const parenClose = v.lastIndexOf(")");
  if (parenOpen === -1 || parenClose === -1) return null;

  const inner = v.slice(parenOpen + 1, parenClose);
  const withoutColorspace = inner.replace(/^\s*in\s+\w+\s*,\s*/i, "");

  // Each stop is "<color> <pct>%" — split at the comma between them
  const splitMatch = withoutColorspace.match(
    /^(.*?\s+\d+(?:\.\d+)?%)\s*,\s*(.*?\s+\d+(?:\.\d+)?%)\s*$/
  );
  if (!splitMatch) return null;

  const stopRe = /^(.*?)\s+(\d+(?:\.\d+)?)%$/;
  const m1 = splitMatch[1].trim().match(stopRe);
  const m2 = splitMatch[2].trim().match(stopRe);
  if (!m1 || !m2) return null;

  return {
    color1: m1[1].trim(),
    ratio: parseFloat(m1[2]),
    color2: m2[1].trim(),
    ratio2: parseFloat(m2[2]),
  };
}

function _serializeColorMix(color1, ratio, color2) {
  const r = Math.max(0, Math.min(100, Math.round(ratio)));
  return `color-mix(in srgb, ${color1} ${r}%, ${color2} ${100 - r}%)`;
}

/* =========================================================
   PALETTE TOKEN EXCLUSION
   ========================================================= */

const PALETTE_KEYS = new Set([
  "--evcc-accent",
  "--evcc-surface-base",
  "--evcc-text-primary",
  "--evcc-radius-card",
]);

/* =========================================================
   SLIDER CONFIG
   =========================================================
   Group-based ranges keep controls useful without requiring
   per-token config everywhere.
   ========================================================= */

const SLIDER_CONFIG = {
  "Shared Foundations": { min: 0, max: 64, step: 2 },
  "Cards & Surfaces": { min: 0, max: 32, step: 1 },
  "Borders & Shadows": { min: 0, max: 32, step: 1 },
  "Chips": { min: 20, max: 48, step: 1 },
  "Room Cards": { min: 0, max: 32, step: 1 },
  "Floor Textures":              { min: 0, max: 1, step: 0.01 },
  "Floor Textures — Tile":       { min: 0, max: 1, step: 0.01 },
  "Floor Textures — Wood":       { min: 0, max: 1, step: 0.01 },
  "Floor Textures — Marble":     { min: 0, max: 1, step: 0.01 },
  "Floor Textures — Concrete":   { min: 0, max: 1, step: 0.01 },
  "Floor Textures — Carpet Low": { min: 0, max: 1, step: 0.01 },
  "Floor Textures — Carpet High":{ min: 0, max: 1, step: 0.01 },
  "Floor Textures — Granite":    { min: 0, max: 1, step: 0.01 },
  "Queue & Ordering": { min: 0, max: 32, step: 1 },
  "Status, Confidence & Alerts": { min: 0, max: 32, step: 1 },
  "Learning & Metrics": { min: 0, max: 32, step: 1 },
  "Modals & Overlays": { min: 0, max: 32, step: 1 },
};

/* =========================================================
   HELPERS
   ========================================================= */

function parseNumericThemeValue(value) {
  const numeric = parseFloat(String(value || "").trim());
  return Number.isNaN(numeric) ? null : numeric;
}

function parseScalarThemeValue(token, value) {
  const trimmed = String(value || "").trim();

  if (!trimmed) {
    return { numeric: null, unit: defaultScalarUnitForToken(token) };
  }

  if (token.type === "number") {
    const numeric = parseNumericThemeValue(trimmed);
    return { numeric, unit: "" };
  }

  if (token.type === "size") {
    const match = trimmed.match(/^(-?\d*\.?\d+)\s*(px|rem|em|%|vh|vw|vmin|vmax|ch|ex)$/i);
    if (!match) {
      return { numeric: null, unit: defaultScalarUnitForToken(token) };
    }

    return {
      numeric: Number(match[1]),
      unit: match[2].toLowerCase(),
    };
  }

  if (token.type === "duration") {
    const match = trimmed.match(/^(-?\d*\.?\d+)\s*(ms|s)$/i);
    if (!match) {
      return { numeric: null, unit: defaultScalarUnitForToken(token) };
    }

    return {
      numeric: Number(match[1]),
      unit: match[2].toLowerCase(),
    };
  }

  return { numeric: null, unit: "" };
}

function defaultScalarUnitForToken(token) {
  if (token.type === "size") return "px";
  if (token.type === "duration") return "ms";
  return "";
}

function isScalarThemeType(token) {
  return token.type === "size" || token.type === "number" || token.type === "duration";
}

function canUseNumericControl(token, value) {
  if (!isScalarThemeType(token)) {
    return false;
  }

  if (value === undefined || value === null || value === "") {
    return true;
  }

  return parseScalarThemeValue(token, value).numeric !== null;
}

function clampPercent(value) {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return 100;
  return Math.max(0, Math.min(100, numeric));
}

function alphaPercentFromHex(value) {
  const trimmed = String(value || "").trim();

  if (/^#[0-9a-fA-F]{8}$/.test(trimmed)) {
    const alphaHex = trimmed.slice(7, 9);
    const alpha = parseInt(alphaHex, 16) / 255;
    return clampPercent(Math.round(alpha * 100));
  }

  return 100;
}

/**
 * Mix theme editor renderer methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applyThemeRenderers(proto) {
  proto.renderThemeView = function () {
    const state = this.card._state._ensureThemeState();
    const { tokens, sources } = this.card._state.resolvedTheme();
    const activeTab = state.activeSubTab || "presets";

    return `
      <div class="evcc-view evcc-view--theme">
        ${this._renderThemeHeader(state)}

        <div class="evcc-chips evcc-theme-tabs" role="tablist">
          <button
            class="evcc-chip ${activeTab === "presets" ? "active" : ""}"
            data-theme-tab="presets"
          >
            Themes
          </button>

          <button
            class="evcc-chip ${activeTab === "palette" ? "active" : ""}"
            data-theme-tab="palette"
          >
            Palette
          </button>

          <button
            class="evcc-chip ${activeTab === "tokens" ? "active" : ""}"
            data-theme-tab="tokens"
          >
            Tokens
          </button>
        </div>

        <div class="evcc-view-content">
          ${activeTab === "presets" ? this._renderThemePresets(state) : ""}
          ${activeTab === "palette" ? this._renderThemePalette(tokens, sources) : ""}
          ${activeTab === "tokens" ? this._renderThemeTokenEditor(tokens, sources) : ""}
        </div>

        ${this._renderThemeFooter(state)}
      </div>
    `;
  };

  proto._renderThemeHeader = function (state) {
    return `
      <div class="evcc-theme-header">
        <div class="evcc-search-box">
          <ha-icon icon="mdi:magnify"></ha-icon>
          <input
            type="text"
            placeholder="Search tokens..."
            value="${this.escapeHtml(state.tokenSearchQuery || "")}"
            data-theme-search
          />
        </div>

        <label class="evcc-modified-toggle">
          <ha-checkbox
            ?checked="${state.modifiedOnly}"
            data-theme-modified-only
          ></ha-checkbox>
          <span>Modified Only</span>
        </label>
      </div>
    `;
  };

  proto._renderThemeGroupFilters = function () {
    const selectedFilter = this.card._state.getThemeGroupFilter();

    const chips = [
      { value: "all", label: "All" },
      { value: "modified", label: "Modified" },
      ...THEME_GROUPS.map((group) => ({ value: group, label: group })),
    ];

    return `
      <div class="evcc-chips evcc-theme-filters">
        ${chips.map((chip) => `
          <button
            class="evcc-chip ${selectedFilter === chip.value ? "active" : ""}"
            data-theme-group-filter="${this.escapeHtml(chip.value)}"
          >
            ${this.escapeHtml(chip.label)}
          </button>
        `).join("")}
      </div>
    `;
  };

  proto._renderThemePresets = function (state) {
    const library = state.library || {};
    const ids = Object.keys(library);

    if (ids.length === 0) {
      return `<div class="evcc-empty">No themes available.</div>`;
    }

    return `
      <div class="evcc-preset-grid">
        ${ids.map((id) => {
          const theme = library[id];
          const isActive = state.activeThemeId === id;

          const previewStyle = [
            ...Object.entries(theme.tokens || {}),
            ...Object.entries(theme.colors || {}),
            ...Object.entries(theme.alpha || {}),
          ]
            .map(([k, v]) => `${k}:${v}`)
            .join(";");

          return `
            <div
              class="evcc-preset-card ${isActive ? "active" : ""}"
              data-theme-preset="${this.escapeHtml(id)}"
            >
              ${id !== state.defaultThemeId ? `
                <button
                  class="evcc-preset-delete"
                  data-action="delete-preset"
                  data-preset-id="${this.escapeHtml(id)}"
                >
                  <ha-icon icon="mdi:close-circle"></ha-icon>
                </button>
              ` : ""}

              <div class="evcc-preset-preview" style="${previewStyle}">
                <div class="preview-swatch accent"></div>
                <div class="preview-swatch surface"></div>
              </div>

              <div class="evcc-preset-label">
                ${this.escapeHtml(theme.name || id)}
                ${isActive ? `<span class="evcc-chip evcc-chip--active">Active</span>` : ""}
              </div>
            </div>
          `;
        }).join("")}
      </div>
    `;
  };

  proto._renderThemePalette = function (tokens, sources) {
    const paletteTokens = THEME_TOKEN_REGISTRY.filter((token) =>
      PALETTE_KEYS.has(token.key)
    );

    return `
      <div class="evcc-theme-editor-pane">
        ${this._renderThemePreviewPane()}

        <div class="evcc-theme-editor-main evcc-theme-editor-main--palette">
          <div class="evcc-theme-editor-scrollbox">
          <div class="evcc-token-list evcc-token-list--palette">
          ${paletteTokens.map((token) =>
            this._renderThemeTokenRow(
              token,
              tokens[token.key],
              sources[token.key]
            )
          ).join("")}
          </div>
          </div>
        </div>
      </div>
    `;
  };

  proto._renderThemeTokenEditor = function (tokens, sources) {
    const selectedGroupFilter = this.card._state.getThemeGroupFilter();

    // Build parent→children map from " — " naming convention
    const childrenOf = {};
    const isChild    = new Set();
    for (const group of THEME_GROUPS) {
      const sep = group.indexOf(" — ");
      if (sep === -1) continue;
      const parent = group.slice(0, sep);
      if (!THEME_GROUPS.includes(parent)) continue;
      (childrenOf[parent] = childrenOf[parent] ?? []).push(group);
      isChild.add(group);
    }

    const renderGroup = (group, nested = false) => {
      const groupTokens = this.card._state.filteredThemeTokensForGroup(
        group,
        THEME_TOKEN_REGISTRY,
        { excludeKeys: PALETTE_KEYS }
      );
      const groupSearchQuery  = this.card._state.getThemeGroupSearchQuery(group);
      const hasActiveSearch   = String(groupSearchQuery || "").trim().length > 0;
      const isPinned          = selectedGroupFilter === group || hasActiveSearch;
      const children          = childrenOf[group] ?? [];
      const childHtml         = children.map((c) => renderGroup(c, true)).filter(Boolean).join("");

      if (!groupTokens.length && !isPinned && !childHtml) return "";

      const counts = this.card._state.themeGroupCounts(
        group,
        THEME_TOKEN_REGISTRY,
        { excludeKeys: PALETTE_KEYS }
      );
      const forceOpen = this.card._state.shouldForceThemeGroupOpenForSearch(
        group,
        THEME_TOKEN_REGISTRY,
        { excludeKeys: PALETTE_KEYS }
      );
      const isOpen = forceOpen || this.card._state.isThemeGroupOpen(group);

      // Strip the parent prefix from nested group titles ("Floor Textures — Tile" → "Tile")
      const displayTitle = nested
        ? group.slice(group.lastIndexOf(" — ") + 3)
        : group;

      return `
        <div
          class="evcc-token-group ${isOpen ? "is-open" : "is-closed"} ${nested ? "evcc-token-group--child" : ""}"
          data-theme-group-name="${this.escapeHtml(group)}"
        >
          <div
            class="evcc-token-group-header"
            data-theme-group-toggle="${this.escapeHtml(group)}"
          >
            <div class="group-title">
              ${this.escapeHtml(displayTitle)} (${counts.modified} / ${counts.total})
            </div>

            <div class="group-actions">
              ${counts.modified > 0 ? `
                <button
                  class="evcc-chip"
                  data-theme-group-reset="${this.escapeHtml(group)}"
                >
                  Reset
                </button>
              ` : ""}

              <span class="group-toggle">
                ${isOpen ? "â–¾" : "â–¸"}
              </span>
            </div>
          </div>

          ${isOpen ? `
            <div class="evcc-token-group-body">
              ${groupTokens.length ? `
                <div class="evcc-token-group-search">
                  <input
                    type="text"
                    placeholder="Search ${this.escapeHtml(displayTitle)}..."
                    value="${this.escapeHtml(groupSearchQuery)}"
                    data-theme-group-search="${this.escapeHtml(group)}"
                  />
                </div>

                ${groupTokens.map((token) =>
                  this._renderThemeTokenRow(
                    token,
                    tokens[token.key],
                    sources[token.key]
                  )
                ).join("")}

                ${!groupTokens.length && hasActiveSearch ? `
                  <div class="evcc-empty evcc-empty--theme-group-search">
                    No tokens in ${this.escapeHtml(displayTitle)} match "${this.escapeHtml(groupSearchQuery)}".
                  </div>
                ` : ""}
              ` : ""}

              ${childHtml}
            </div>
          ` : ""}
        </div>
      `;
    };

    const renderedGroups = THEME_GROUPS
      .filter((group) => !isChild.has(group))
      .map((group) => renderGroup(group))
      .filter(Boolean);

    return `
      <div class="evcc-theme-editor-pane">
        ${this._renderThemePreviewPane()}

        <div class="evcc-theme-editor-main">
        <div class="evcc-theme-editor-scrollbox">
        <div class="evcc-token-editor">
          ${this._renderThemeGroupFilters()}

          <div class="evcc-token-list">
          ${renderedGroups.length ? renderedGroups.join("") : `
            <div class="evcc-empty evcc-empty--theme-group-search">
              No tokens match the current theme filters.
            </div>
          `}
          </div>
        </div>
        </div>
        </div>
      </div>
    `;

  };

  proto._renderThemeTokenRow = function (token, value, source) {
    const isDraft = source === "draft";
    const safeValue = value || "";

    if (token.type === "color") {
      if (_parseColorMix(safeValue)) {
        return this._renderThemeColorMixTokenRow(token, safeValue, isDraft);
      }
      return this._renderThemeColorTokenRow(token, safeValue, isDraft);
    }

    if (canUseNumericControl(token, safeValue)) {
      return this._renderThemeNumericTokenRow(token, safeValue, isDraft);
    }

    return this._renderThemeTextTokenRow(token, safeValue, isDraft);
  };

  proto._renderThemeColorTokenRow = function (token, value, isDraft) {
    const safeValue = String(value || "").trim();
    const colorInputValue = this._safeColorInputValue(safeValue);
    const alphaPercent = alphaPercentFromHex(safeValue);
    // Strip alpha from rail color so the gradient always spans transparent→opaque.
    // Without this, --rail-color on an 8-char hex makes the right endpoint
    // semi-transparent, so the gradient shows "color at current alpha" instead of
    // the full range from invisible to solid.
    const opaqueRailColor = /^#[0-9a-fA-F]{8}$/.test(safeValue)
      ? `#${safeValue.slice(1, 7)}`
      : safeValue;

    return `
      <div class="evcc-token-row evcc-token-row--color ${isDraft ? "is-draft" : ""}">
        <div class="token-top-strip">
          <input
            type="text"
            class="token-input token-input--hex"
            value="${this.escapeHtml(safeValue)}"
            placeholder="#RRGGBB"
            data-theme-token="${this.escapeHtml(token.key)}"
            inputmode="text"
            autocapitalize="off"
            spellcheck="false"
          />

          ${isDraft ? `
            <button
              class="evcc-chip"
              data-theme-reset="${this.escapeHtml(token.key)}"
            >
              Reset
            </button>
          ` : ""}

          <div class="token-hint">
            Drag for opacity · Double tap for color
          </div>
        </div>

        <div class="token-head">
          <div class="token-label">
            ${this.escapeHtml(token.label)}
          </div>
        </div>

        <div class="token-control-row token-control-row--color">
          <div class="token-color-combined-control" title="${this.escapeHtml(token.label)}">
            <div
              class="token-alpha-shell"
              style="
                --rail-color: ${opaqueRailColor || `var(${token.key})`};
                --thumb-color: ${safeValue || `var(${token.key})`};
              "
            >
              <div class="token-alpha-rail">
                <div class="token-alpha-rail-fill"></div>
                <div class="token-alpha-rail-track"></div>

                <input
                  type="range"
                  class="token-alpha-input"
                  min="0"
                  max="100"
                  step="1"
                  value="${alphaPercent}"
                  data-theme-alpha="${this.escapeHtml(token.key)}"
                  data-color-swatch="${this.escapeHtml(token.key)}"
                  aria-label="${this.escapeHtml(token.label)} opacity"
                />

                <div
                  class="token-alpha-indicator"
                  data-theme-alpha-indicator="${this.escapeHtml(token.key)}"
                  style="left: ${alphaPercent}%"
                ></div>
              </div>

              <div
                class="token-slider-bubble token-slider-bubble--alpha"
                data-theme-alpha-bubble="${this.escapeHtml(token.key)}"
                style="left: ${alphaPercent}%"
              >
                ${alphaPercent}%
              </div>
            </div>
          </div>

          <input
            type="color"
            class="hidden-color-input"
            value="${colorInputValue}"
            data-theme-color-input="${this.escapeHtml(token.key)}"
            tabIndex="-1"
          />
        </div>
      </div>
    `;
  };

  proto._renderThemeColorMixTokenRow = function (token, value, isDraft) {
    const parsed = _parseColorMix(value);
    if (!parsed) return this._renderThemeColorTokenRow(token, value, isDraft);

    const { color1, ratio, color2 } = parsed;
    const preview = this.escapeHtml(_serializeColorMix(color1, ratio, color2));

    return `
      <div class="evcc-token-row evcc-token-row--color-mix ${isDraft ? "is-draft" : ""}">
        <div class="token-head">
          <div class="token-label">${this.escapeHtml(token.label)}</div>
          <div class="token-head-actions">
            ${isDraft ? `
              <button class="evcc-chip" data-theme-reset="${this.escapeHtml(token.key)}">
                Reset
              </button>
            ` : ""}
          </div>
        </div>

        <div class="token-hint">Drag ratio · Edit color references</div>

        <div class="token-colormix-colors">
          <div class="token-colormix-slot">
            <div class="token-colormix-swatch" style="background: ${this.escapeHtml(color1)}"></div>
            <input
              type="text"
              class="token-input token-colormix-color"
              data-theme-colormix="${this.escapeHtml(token.key)}"
              data-colormix-part="color1"
              value="${this.escapeHtml(color1)}"
              spellcheck="false"
              autocapitalize="off"
            />
          </div>

          <div class="token-colormix-ratio-label" data-colormix-ratio-label="${this.escapeHtml(token.key)}">
            ${ratio}%
          </div>

          <div class="token-colormix-slot">
            <div class="token-colormix-swatch" style="background: ${this.escapeHtml(color2)}"></div>
            <input
              type="text"
              class="token-input token-colormix-color"
              data-theme-colormix="${this.escapeHtml(token.key)}"
              data-colormix-part="color2"
              value="${this.escapeHtml(color2)}"
              spellcheck="false"
              autocapitalize="off"
            />
          </div>
        </div>

        <div class="token-colormix-slider-row">
          <input
            type="range"
            class="token-colormix-ratio-input"
            min="0"
            max="100"
            step="1"
            value="${ratio}"
            data-theme-colormix="${this.escapeHtml(token.key)}"
            data-colormix-part="ratio"
          />
        </div>

        <div
          class="token-colormix-preview"
          style="background: ${preview}"
        ></div>
      </div>
    `;
  };

  proto._renderThemeNumericTokenRow = function (token, value, isDraft) {
    const config = SLIDER_CONFIG[token.group] || { min: 0, max: 64, step: 1 };
    const scalarValue = parseScalarThemeValue(token, value);
    const numericValue = scalarValue.numeric ?? config.min;
    const unit = scalarValue.unit || defaultScalarUnitForToken(token);
    const bubbleSuffix = token.type === "number" ? "" : unit;

    const rangeMin = Math.min(config.min, numericValue);
    const rangeMax = Math.max(config.max, numericValue);

    return `
      <div
        class="evcc-token-row evcc-token-row--numeric ${isDraft ? "is-draft" : ""}"
        data-theme-token-unit="${this.escapeHtml(unit)}"
      >
        <div class="token-head">
          <div class="token-label">
            ${this.escapeHtml(token.label)}
            <span class="evcc-chip">${this.escapeHtml(token.type)}</span>
          </div>

          <div class="token-head-actions">
            ${isDraft ? `
              <button
                class="evcc-chip"
                data-theme-reset="${this.escapeHtml(token.key)}"
              >
                Reset
              </button>
            ` : ""}
          </div>
        </div>

        <div class="token-control-row token-control-row--slider">
          <div class="slider-wrap">
            <input
              type="range"
              class="token-input token-input--slider"
              min="${rangeMin}"
              max="${rangeMax}"
              step="${config.step}"
              value="${numericValue}"
              data-theme-token="${this.escapeHtml(token.key)}"
            />

            <div
              class="token-slider-bubble"
              data-theme-slider-bubble="${this.escapeHtml(token.key)}"
            >
              ${numericValue}${this.escapeHtml(bubbleSuffix)}
            </div>
          </div>
        </div>

        <div class="token-control-row token-control-row--number">
          <input
            type="number"
            class="token-input token-input--number"
            min="${rangeMin}"
            max="${rangeMax}"
            step="${config.step}"
            value="${numericValue}"
            data-theme-token="${this.escapeHtml(token.key)}"
          />
        </div>
      </div>
    `;
  };

  proto._renderThemeTextTokenRow = function (token, value, isDraft) {
    return `
      <div class="evcc-token-row evcc-token-row--text ${isDraft ? "is-draft" : ""}">
        <div class="token-head">
          <div class="token-label">
            ${this.escapeHtml(token.label)}
            <span class="evcc-chip">${this.escapeHtml(token.type)}</span>
            ${isDraft ? `<span class="evcc-chip evcc-chip--custom">Draft</span>` : ""}
          </div>

          <div class="token-head-actions">
            ${isDraft ? `
              <button
                class="evcc-chip"
                data-theme-reset="${this.escapeHtml(token.key)}"
              >
                Reset
              </button>
            ` : ""}
          </div>
        </div>

        <div class="token-control-row token-control-row--text">
          <input
            type="text"
            class="token-input"
            value="${this.escapeHtml(value)}"
            placeholder="Default"
            data-theme-token="${this.escapeHtml(token.key)}"
          />
        </div>
      </div>
    `;
  };

  proto._renderThemeFooter = function (state) {
    const hasDraft = !!state.draftDirty;
    const hasActiveTheme = !!state.activeThemeId;

    return `
      <div class="evcc-view-footer">
        <div class="footer-left">
          <button
            class="evcc-chip"
            data-action="export-theme"
            title="Copy theme JSON to clipboard"
          >
            Export
          </button>

          <button
            class="evcc-chip"
            data-action="import-theme"
            title="Paste theme JSON from clipboard"
          >
            Import
          </button>

          <button
            class="evcc-chip"
            data-action="download-theme"
            title="Download theme as a .json file"
          >
            Download
          </button>

          <button
            class="evcc-chip"
            data-action="upload-theme"
            title="Upload a theme .json file"
          >
            Upload
          </button>
        </div>

        <div class="footer-right">
          <button
            class="evcc-chip"
            data-action="reset-draft"
            ${!hasDraft ? "disabled" : ""}
          >
            Discard
          </button>

          <button
            class="evcc-chip evcc-chip--save"
            data-action="save-theme"
            ${!hasDraft ? "disabled" : ""}
          >
            ${hasActiveTheme ? "Save Changes" : "Save as New"}
          </button>
        </div>
      </div>
    `;
  };

  proto._safeColorInputValue = function (value) {
    const trimmed = String(value || "").trim();

    if (/^#[0-9a-fA-F]{6}$/.test(trimmed)) {
      return trimmed;
    }

    if (/^#[0-9a-fA-F]{8}$/.test(trimmed)) {
      return `#${trimmed.slice(1, 7)}`;
    }

    return "#000000";
  };
}
