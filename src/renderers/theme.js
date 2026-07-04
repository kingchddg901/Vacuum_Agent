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
import { floorTypeNames } from "../theme-tokens/floor-scope.js";
import { MARBLE_PRESETS } from "../theme-tokens/floor-presets.js";
import { FACETS, orderTags, facetOf, SUGGESTED_VIBE_TAGS } from "../theme-tags/index.mjs";

// The public Pages "store" — the card links out to it (no auto-download).
const THEME_GALLERY_URL = "https://kingchddg901.github.io/Vacuum_Agent/";

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

// Named exports for unit testing of the pure parsing/serialization helpers.
// Bodies are unchanged; this only widens visibility.
export {
  _parseColorMix,
  _serializeColorMix,
  parseScalarThemeValue,
  clampPercent,
  alphaPercentFromHex,
};

/**
 * Mix theme editor renderer methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applyThemeRenderers(proto) {
  proto.renderThemeView = function () {
    const state = this.card._state._ensureThemeState();
    const { tokens, sources } = this.card._state.resolvedTheme();
    const isMobile = this.card._state.isMobileViewport();
    // Mobile = theme PICKING only: force the Themes (presets) sub-tab and drop the
    // Palette/Tokens editors — they need too many panels for a phone.
    const activeTab = isMobile ? "presets" : (state.activeSubTab || "presets");

    return `
      <div class="evcc-view evcc-view--theme">
        ${activeTab === "presets" ? "" : this._renderThemeHeader(state)}

        ${isMobile ? "" : `
        <div class="evcc-chips evcc-theme-tabs" role="tablist">
          <button
            class="evcc-chip ${activeTab === "presets" ? "active" : ""}"
            data-theme-tab="presets"
          >
            ${this.t("theme.tab_themes")}
          </button>

          <button
            class="evcc-chip ${activeTab === "palette" ? "active" : ""}"
            data-theme-tab="palette"
          >
            ${this.t("theme.tab_palette")}
          </button>

          <button
            class="evcc-chip ${activeTab === "tokens" ? "active" : ""}"
            data-theme-tab="tokens"
          >
            ${this.t("theme.tab_tokens")}
          </button>
        </div>`}

        <div class="evcc-view-content">
          ${activeTab === "presets" ? this._renderThemePresets(state) : ""}
          ${!isMobile && activeTab === "palette" ? this._renderThemePalette(tokens, sources) : ""}
          ${!isMobile && activeTab === "tokens" ? this._renderThemeTokenEditor(tokens, sources) : ""}
        </div>

        ${this._renderThemeFooter(state)}
      </div>
    `;
  };

  /**
   * Export / Import theme JSON modal. Export shows the JSON in a read-only
   * textarea (one-shot — gone when the modal closes); Import takes a paste.
   * Renders into the body-level modal host via _updateModalHost.
   */
  proto.renderThemeJsonModal = function (ctx) {
    const { state } = ctx;
    if (!state.isThemeJsonModalOpen()) return "";

    const isExport = state.themeJsonModalMode() === "export";
    const text = state.themeJsonModalText();

    return `
      <div class="evcc-modal-backdrop" data-action="close-theme-json">
        <div class="evcc-modal evcc-modal--theme-json" data-stop-propagation>

          <div class="evcc-modal-header">
            <div class="evcc-modal-title">${isExport ? this.t("theme.json_modal_title_export") : this.t("theme.json_modal_title_import")}</div>
            <button type="button" class="evcc-chip evcc-chip--icon" data-action="close-theme-json" title="${this.t("common.close")}">✕</button>
          </div>

          <div class="evcc-modal-body">
            <p class="evcc-theme-json-hint">${isExport
              ? this.t("theme.json_modal_hint_export")
              : this.t("theme.json_modal_hint_import")}</p>
            <textarea
              class="evcc-theme-json-area"
              data-theme-json-area
              spellcheck="false"
              ${isExport ? "readonly" : `placeholder="${this.t("theme.json_modal_paste_placeholder")}"`}
            >${this.escapeHtml(text)}</textarea>
            ${isExport ? "" : `<p class="evcc-theme-json-error" data-theme-json-error hidden></p>`}
          </div>

          <div class="evcc-modal-footer">
            <button type="button" class="evcc-chip" data-action="close-theme-json">${isExport ? this.t("common.close") : this.t("common.cancel")}</button>
            ${isExport
              ? `<button type="button" class="evcc-chip" data-action="notify-theme-json" title="${this.t("theme.json_modal_notify_title")}">${this.t("theme.json_modal_send_to_ha")}</button>
                 <button type="button" class="evcc-chip evcc-chip--save" data-action="copy-theme-json">${this.t("theme.json_modal_copy")}</button>`
              : `<button type="button" class="evcc-chip evcc-chip--save" data-action="confirm-theme-import">${this.t("theme.json_modal_import")}</button>`}
          </div>

        </div>
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
            placeholder="${this.t("theme.search_tokens_placeholder")}"
            value="${this.escapeHtml(state.tokenSearchQuery || "")}"
            data-theme-search
          />
        </div>

        <label class="evcc-modified-toggle">
          <ha-checkbox
            ?checked="${state.modifiedOnly}"
            data-theme-modified-only
          ></ha-checkbox>
          <span>${this.t("theme.modified_only")}</span>
        </label>
      </div>
    `;
  };

  proto._renderThemeGroupFilters = function () {
    const selectedFilter = this.card._state.getThemeGroupFilter();

    const chips = [
      { value: "all", label: this.t("theme.filter_all") },
      { value: "modified", label: this.t("theme.filter_modified") },
      ...THEME_GROUPS.map((group) => {
        // Match the group-header display: nested groups show only their suffix.
        // Animal subgroups have no theme_group key, so tVocab falls back to the
        // suffix — the protected animal name (Cat/Dog/…), never translated.
        const sep = group.indexOf(" — ");
        const nested = sep !== -1 && THEME_GROUPS.includes(group.slice(0, sep));
        const display = nested ? group.slice(group.lastIndexOf(" — ") + 3) : group;
        return { value: group, label: this.tVocab("theme_group", group, display) };
      }),
    ];

    return `
      <div class="evcc-chips evcc-theme-filters">
        ${chips.map((chip) => `
          <button
            class="evcc-chip ${selectedFilter === chip.value ? "active" : ""}"
            data-theme-group-filter="${this.escapeHtml(chip.value)}"
          >
            ${chip.label}
          </button>
        `).join("")}
      </div>
    `;
  };

  proto._renderPresetFilters = function (state) {
    const present = this.card._state.presentPresetTags();

    // One labelled row per facet; only facets/tags that occur in the library.
    const facetRows = FACETS.map((facet) => {
      const tags = facet.tags.filter((t) => present.has(t));
      if (!tags.length) return "";
      return `
        <div class="evcc-preset-facet">
          <span class="evcc-preset-facet-label">${this.tVocab("theme_facet", facet.key, facet.label)}</span>
          ${tags.map((t) => `
            <button
              class="evcc-chip evcc-preset-facet-chip ${this.card._state.isPresetFacetActive(facet.key, t) ? "active" : ""}"
              data-preset-facet="${this.escapeHtml(facet.key)}"
              data-preset-facet-value="${this.escapeHtml(t)}"
            >${this.tVocab("theme_tag", t, t)}</button>
          `).join("")}
        </div>`;
    }).filter(Boolean).join("");

    const hasFilters = this.card._state.hasActivePresetFilters();
    const filtersOpen = this.card._state.getPresetFiltersOpen();
    const facetCount = this.card._state.activePresetFacetCount();
    const canFilter = !!facetRows;

    return `
      <div class="evcc-preset-filters">
        <div class="evcc-preset-filters-top">
          <div class="evcc-search-box evcc-preset-search">
            <ha-icon icon="mdi:magnify"></ha-icon>
            <input
              type="text"
              placeholder="${this.t("theme.search_themes_placeholder")}"
              value="${this.escapeHtml(state.presetSearchQuery || "")}"
              data-preset-search
            />
          </div>
          ${canFilter ? `
            <button
              class="evcc-chip evcc-preset-filters-toggle ${filtersOpen ? "active" : ""}"
              data-preset-filters-toggle
              aria-expanded="${filtersOpen ? "true" : "false"}"
            >
              <ha-icon icon="mdi:filter-variant"></ha-icon>
              ${facetCount ? this.t("theme.filters_count", { count: facetCount }) : this.t("theme.filters")}
              <ha-icon class="evcc-preset-filters-caret" icon="mdi:chevron-down"></ha-icon>
            </button>
          ` : ""}
          ${hasFilters ? `
            <button class="evcc-chip evcc-preset-clear" data-preset-clear>${this.t("theme.clear_filters")}</button>
          ` : ""}
          <a
            class="evcc-preset-gallery-link"
            href="${THEME_GALLERY_URL}"
            target="_blank"
            rel="noopener noreferrer"
            title="${this.t("theme.gallery_link_title")}"
          >
            ${this.t("theme.browse_gallery")} <ha-icon icon="mdi:open-in-new"></ha-icon>
          </a>
        </div>
        ${canFilter && filtersOpen ? `<div class="evcc-preset-facets">${facetRows}</div>` : ""}
      </div>
      <datalist id="evcc-vibe-suggest">
        ${SUGGESTED_VIBE_TAGS.map((t) => `<option value="${this.escapeHtml(t)}"></option>`).join("")}
      </datalist>
    `;
  };

  proto._renderThemePresets = function (state) {
    const library = state.library || {};
    const allIds = Object.keys(library);

    if (allIds.length === 0) {
      return `<div class="evcc-empty">${this.t("theme.presets_empty")}</div>`;
    }

    const ids = this.card._state.filteredPresetIds();

    const grid = ids.length === 0
      ? `<div class="evcc-empty">${this.t("theme.presets_no_match")}</div>`
      : `
        <div class="evcc-preset-grid">
          ${(() => {
            const activeId = this.card._state.effectiveActiveThemeId();
            return ids.map((id) => {
            const theme = library[id];
            const isActive = activeId === id;

            const previewStyle = [
              ...Object.entries(theme.tokens || {}),
              ...Object.entries(theme.colors || {}),
              ...Object.entries(theme.alpha || {}),
            ]
              .map(([k, v]) => `${k}:${v}`)
              .join(";");

            const tags = this.card._state.presetTagsFor(id);
            // On the small cards, show only the most identifying tags — mode,
            // accent, and the two "status" tags (colorblind-safe / source). The
            // filter bar covers temperature/surface/contrast.
            const shownTags = orderTags(tags).filter((t) =>
              ["mode", "accent", "a11y", "cvd", "source"].includes(facetOf(t))
            );
            const tagChips = shownTags.length
              ? `<div class="evcc-preset-tags">${shownTags
                  .map((t) => `<span class="evcc-preset-tag" data-facet="${facetOf(t)}">${this.tVocab("theme_tag", t, t)}</span>`)
                  .join("")}</div>`
              : "";

            // Inline vibe-tag editor for this one card (only the user's free-text
            // tags are editable; facet tags above stay read-only/derived).
            const isEditing = this.card._state.getPresetTagEditId() === id;
            const editor = isEditing
              ? `<div class="evcc-preset-tag-editor" data-preset-tag-editor>
                  <div class="evcc-preset-vibe-chips">
                    ${this.card._state.presetVibeTags(id).map((t) => `
                      <span class="evcc-preset-vibe-chip">${this.escapeHtml(t)}<button
                        class="evcc-preset-vibe-remove"
                        data-preset-tag-remove="${this.escapeHtml(id)}"
                        data-tag="${this.escapeHtml(t)}"
                        title="${this.t("theme.tag_remove_title")}">×</button></span>`).join("")}
                  </div>
                  <div class="evcc-preset-tag-add">
                    <input
                      class="evcc-preset-tag-input"
                      type="text"
                      list="evcc-vibe-suggest"
                      placeholder="${this.t("theme.tag_add_placeholder")}"
                      maxlength="32"
                      data-preset-tag-add="${this.escapeHtml(id)}"
                    >
                    <button class="evcc-preset-tag-done" data-preset-tag-done title="${this.t("theme.tag_done_title")}">
                      <ha-icon icon="mdi:check"></ha-icon>
                    </button>
                  </div>
                </div>`
              : "";

            return `
              <div
                class="evcc-preset-card ${isActive ? "active" : ""} ${isEditing ? "editing" : ""}"
                data-theme-preset="${this.escapeHtml(id)}"
              >
                <button
                  class="evcc-preset-tag-edit ${isEditing ? "active" : ""}"
                  data-preset-tag-edit="${this.escapeHtml(id)}"
                  title="${this.t("theme.tag_edit_title")}"
                >
                  <ha-icon icon="mdi:tag-multiple-outline"></ha-icon>
                </button>
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
                  ${isActive ? `<span class="evcc-chip evcc-chip--active">${this.t("theme.preset_active")}</span>` : ""}
                </div>
                ${tagChips}
                ${editor}
              </div>
            `;
          }).join("");
          })()}
        </div>`;

    // Mode bar (system vs this-device) + fixed filter bar + scrolling grid.
    return `${this._renderThemeModeBar(state)}${this._renderPresetFilters(state)}<div class="evcc-preset-scroll">${grid}</div>`;
  };

  proto._renderThemeModeBar = function (state) {
    const isDevice = this.card._state.isDeviceThemeMode();
    const activeId = this.card._state.effectiveActiveThemeId();
    const activeName = state.library?.[activeId]?.name || "—";

    return `
      <div class="evcc-theme-mode">
        <div class="evcc-theme-mode-row">
          <span class="evcc-theme-mode-label">${this.t("theme.mode_label")}</span>
          <button class="evcc-chip ${isDevice ? "" : "active"}" data-theme-mode="system">${this.t("theme.mode_follow_system")}</button>
          <button class="evcc-chip ${isDevice ? "active" : ""}" data-theme-mode="device">${this.t("theme.mode_this_device")}</button>
        </div>
        ${isDevice ? `
          <div class="evcc-theme-mode-detail">
            <div class="evcc-theme-mode-state">
              <span><span class="k">${this.t("theme.mode_active_theme")}</span> ${this.escapeHtml(activeName)}</span>
              <span><span class="k">${this.t("theme.mode_mode")}</span> ${this.t("theme.mode_this_device_only")}</span>
            </div>
            <div class="evcc-theme-mode-actions">
              <button class="evcc-chip" data-action="theme-use-everywhere">${this.t("theme.mode_use_everywhere")}</button>
              <button class="evcc-chip" data-action="theme-clear-device">${this.t("theme.mode_clear_device")}</button>
            </div>
            <p class="evcc-theme-mode-note">${this.tRaw("theme.mode_note")}</p>
          </div>
        ` : ""}
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
              ${this.tVocab("theme_group", group, displayTitle)} (${counts.modified} / ${counts.total})
            </div>

            <div class="group-actions">
              ${counts.modified > 0 ? `
                <button
                  class="evcc-chip"
                  data-theme-group-reset="${this.escapeHtml(group)}"
                >
                  ${this.t("common.reset")}
                </button>
              ` : ""}

              <span class="group-toggle">
                ${isOpen ? "\u25be" : "\u25b8"}
              </span>
            </div>
          </div>

          ${isOpen ? `
            <div class="evcc-token-group-body">
              ${groupTokens.length ? `
                <div class="evcc-token-group-search">
                  <input
                    type="text"
                    placeholder="${this.t("theme.group_search_placeholder", { title: this.tVocab("theme_group", group, displayTitle) })}"
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
                    ${this.t("theme.group_no_match", { title: this.tVocab("theme_group", group, displayTitle), query: this.escapeHtml(groupSearchQuery) })}
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
              ${this.t("theme.no_tokens_match_filters")}
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
              ${this.t("common.reset")}
            </button>
          ` : ""}

          <div class="token-hint">
            ${this.t("theme.color_hint")}
          </div>
        </div>

        <div class="token-head">
          <div class="token-label">
            ${this.tVocab("theme_token", token.key, token.label)}
          </div>
        </div>

        <div class="token-control-row token-control-row--color">
          <div class="token-color-combined-control" title="${this.tVocab("theme_token", token.key, token.label)}">
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
                  aria-label="${this.t("theme.alpha_aria_label", { label: this.tVocab("theme_token", token.key, token.label) })}"
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
          <div class="token-label">${this.tVocab("theme_token", token.key, token.label)}</div>
          <div class="token-head-actions">
            ${isDraft ? `
              <button class="evcc-chip" data-theme-reset="${this.escapeHtml(token.key)}">
                ${this.t("common.reset")}
              </button>
            ` : ""}
          </div>
        </div>

        <div class="token-hint">${this.t("theme.colormix_hint")}</div>

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
    const groupConfig = SLIDER_CONFIG[token.group] || { min: 0, max: 64, step: 1 };
    // Per-token range (from the semantic helper methods: .unit/.blur/.angle/
    // .signed) is the single source of truth for the slider AND the import
    // clamp, so they can't drift. Fall back to the group config for rangeless
    // tokens (bare .number). This is also why the marble blur/hue/chroma
    // sliders aren't capped at the group's 0-1 anymore.
    const config = {
      min:  Number.isFinite(token.min)  ? token.min  : groupConfig.min,
      max:  Number.isFinite(token.max)  ? token.max  : groupConfig.max,
      step: Number.isFinite(token.step) ? token.step : groupConfig.step,
    };
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
            ${this.tVocab("theme_token", token.key, token.label)}
            <span class="evcc-chip">${this.escapeHtml(token.type)}</span>
          </div>

          <div class="token-head-actions">
            ${isDraft ? `
              <button
                class="evcc-chip"
                data-theme-reset="${this.escapeHtml(token.key)}"
              >
                ${this.t("common.reset")}
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
            ${this.tVocab("theme_token", token.key, token.label)}
            <span class="evcc-chip">${this.escapeHtml(token.type)}</span>
            ${isDraft ? `<span class="evcc-chip evcc-chip--custom">${this.t("theme.token_draft")}</span>` : ""}
          </div>

          <div class="token-head-actions">
            ${isDraft ? `
              <button
                class="evcc-chip"
                data-theme-reset="${this.escapeHtml(token.key)}"
              >
                ${this.t("common.reset")}
              </button>
            ` : ""}
          </div>
        </div>

        <div class="token-control-row token-control-row--text">
          <input
            type="text"
            class="token-input"
            value="${this.escapeHtml(value)}"
            placeholder="${this.t("theme.token_default_placeholder")}"
            data-theme-token="${this.escapeHtml(token.key)}"
          />
        </div>
      </div>
    `;
  };

  proto._renderThemeFooter = function (state) {
    const hasDraft = !!state.draftDirty;
    const hasActiveTheme = !!state.activeThemeId;
    // Mobile = picking only: keep theme-level Export/Import/Download/Upload; drop
    // the floor-preset + draft (Save/Discard) controls, which belong to the
    // desktop-only token editor.
    const isMobile = this.card._state.isMobileViewport();

    return `
      <div class="evcc-view-footer">
        <div class="footer-left">
          <button
            class="evcc-chip"
            data-action="export-theme"
            title="${this.t("theme.export_title")}"
          >
            ${this.t("theme.export")}
          </button>

          <button
            class="evcc-chip"
            data-action="import-theme"
            title="${this.t("theme.import_title")}"
          >
            ${this.t("theme.import")}
          </button>

          <button
            class="evcc-chip"
            data-action="download-theme"
            title="${this.t("theme.download_title")}"
          >
            ${this.t("theme.download")}
          </button>

          <button
            class="evcc-chip"
            data-action="upload-theme"
            title="${this.t("theme.upload_title")}"
          >
            ${this.t("theme.upload")}
          </button>

          ${isMobile ? "" : `
          <select
            class="evcc-chip evcc-floor-scope-select"
            data-theme-floor-scope
            title="${this.t("theme.floor_scope_title")}"
          >
            ${floorTypeNames().map((name) => `<option value="${name}">${name}</option>`).join("")}
          </select>

          <button
            class="evcc-chip"
            data-action="download-floor-theme"
            title="${this.t("theme.download_floor_title")}"
          >
            ${this.t("theme.download_floor")}
          </button>

          <select
            class="evcc-chip evcc-floor-scope-select"
            data-floor-preset
            title="${this.t("theme.marble_preset_title")}"
          >
            ${MARBLE_PRESETS.map((p) => `<option value="${p.id}">${this.escapeHtml(p.name)}</option>`).join("")}
          </select>

          <button
            class="evcc-chip"
            data-action="apply-floor-preset"
            title="${this.t("theme.apply_preset_title")}"
          >
            ${this.t("theme.apply_preset")}
          </button>`}
        </div>

        ${isMobile ? "" : `
        <div class="footer-right">
          <button
            class="evcc-chip"
            data-action="reset-draft"
            ${!hasDraft ? "disabled" : ""}
          >
            ${this.t("theme.discard")}
          </button>

          <button
            class="evcc-chip evcc-chip--save"
            data-action="save-theme"
            ${!hasDraft ? "disabled" : ""}
          >
            ${hasActiveTheme ? this.t("theme.save_changes") : this.t("theme.save_as_new")}
          </button>
        </div>`}
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
