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
import { FONT_STACK_PRESETS, runtimeFontPresets } from "../styles/fonts.js";
import { MARBLE_PRESETS } from "../theme-tokens/floor-presets.js";
import { FACETS, orderTags, facetOf, SUGGESTED_VIBE_TAGS } from "../theme-tags/index.mjs";

// The public Pages "store" — the card links out to it (no auto-download).
const THEME_GALLERY_URL = "https://kingchddg901.github.io/Vacuum_Agent/";

/* The Theme view is fully editable on a phone — presets, Palette, Tokens and the
   draft footer. An earlier revision made it PICKING-ONLY there, reasoning that the
   editors "need too many panels for a phone"; on-device testing said otherwise. The
   token list already scrolls in its own container (.evcc-theme-editor-scrollbox,
   styles/theme.js:537) with the contextual preview and footer OUTSIDE it, the
   <=1100px query hoists the preview full-width above the editor, and the group chips
   are tappable by hand. The real constraint is vertical BUDGET, not layout — which is
   what the paired compact chrome in styles/mobile.js addresses. */

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
    const activeTab = state.activeSubTab || "presets";

    /* The caret takes the sub-tab strip WITH it. Collapsing only the search row
       reclaimed ~26px — measured on device, and visibly not worth a control.
       The strip is the rest of the chrome above the editor, and the caret can
       carry "which tab" in a label far cheaper than three buttons can.

       Only when the header is on screen to expand from: the presets tab renders
       no header, so there would be no caret and the strip would be unreachable. */
    const chromeCollapsed = activeTab !== "presets" && !!state.searchCollapsed;

    return `
      <div class="evcc-view evcc-view--theme">
        ${activeTab === "presets" ? "" : this._renderThemeHeader(state, activeTab)}

        ${chromeCollapsed ? "" : `
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
          ${activeTab === "palette" ? this._renderThemePalette(tokens, sources) : ""}
          ${activeTab === "tokens" ? this._renderThemeTokenEditor(tokens, sources) : ""}
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

  /* COLLAPSIBLE, because this row is the most expensive thing in the frame.
     At 390px the search box (38px) and the Modified Only toggle do not fit on
     one line — see the wrap rule in styles/theme.js — so the row costs ~90px,
     more than the whole category chip band. Collapsed it is a caret.

     The caret CARRIES THE FILTER STATE, and by name rather than by colour.
     Colour alone would fail twice over: it cannot say WHICH filter is on, and
     this is a theme editor, so the one channel the user can accidentally paint
     into invisibility is colour. Text cannot be themed away. The accent tint is
     reinforcement on top of the label, never the thing carrying the meaning —
     and it is the accent token, not an error token, because a filter being on
     is the user doing a normal thing on purpose, not a fault. */
  proto._renderThemeHeader = function (state, activeTab) {
    const query = state.tokenSearchQuery || "";
    const reason = query
      ? { kind: "search", value: query }
      : state.modifiedOnly
        ? { kind: "modified", value: "" }
        : null;

    const badge = reason
      ? `<span class="evcc-theme-filter-badge">${
          reason.kind === "search"
            ? this.escapeHtml(reason.value)
            : this.t("theme.modified_only")
        }</span>`
      : "";

    /* Collapsed, the caret names the SUB-TAB it is standing in for. Hiding the
       Themes/Palette/Tokens strip is most of what collapsing buys — the search
       row alone was ~26px, which is not worth a control — but a hidden nav that
       does not say where you are is a trap. With the label it reads as what it
       now is: a dropdown showing the current section. */
    const TAB_KEY = {
      presets: "theme.tab_themes",
      palette: "theme.tab_palette",
      tokens: "theme.tab_tokens",
    };
    const tabLabel =
      state.searchCollapsed && TAB_KEY[activeTab]
        ? `<span class="evcc-theme-collapsed-tab">${this.t(TAB_KEY[activeTab])}</span>`
        : "";

    /* One control, one place, both states — the caret does not move when the
       row opens, so it never has to be re-found. */
    const toggle = `
      <button
        type="button"
        class="evcc-theme-search-toggle"
        data-theme-search-toggle
        aria-expanded="${state.searchCollapsed ? "false" : "true"}"
        aria-label="${this.t("theme.search_toggle")}"
      >
        ${state.searchCollapsed ? tabLabel + badge : ""}
        <ha-icon icon="${
          state.searchCollapsed ? "mdi:chevron-down" : "mdi:chevron-up"
        }"></ha-icon>
      </button>
    `;

    if (state.searchCollapsed) {
      return `<div class="evcc-theme-header evcc-theme-header--collapsed">${toggle}</div>`;
    }

    return `
      <div class="evcc-theme-header">
        ${toggle}

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

  /**
   * PROGRESSIVE DISCLOSURE — one level at a time.
   *
   * Every group used to render at once: 26 chips, seven rows on a phone, roughly
   * a third of the visible card spent on navigation before a single token was in
   * reach. Now only one level shows, and descending swaps the row for that
   * branch's children.
   *
   * NO NEW STATE. The level is DERIVED from the existing group filter, because
   * the parent/child relationship is already inferred from the group name's
   * " — " separator (this function has always computed `nested`; it just then
   * rendered every child anyway). Selecting IS descending and Back IS selecting
   * the parent, so the row and the filter are the same variable and cannot drift
   * apart — the failure mode a separate `openBranch` flag would have introduced.
   *
   * COST, accepted: hopping between two sibling categories is now two taps where
   * it used to be one. Browse speed traded for vertical space, deliberately.
   *
   * No new i18n: Back reuses the parent's own label (or theme.filter_all at the
   * top), and the chevron is punctuation.
   */
  proto._renderThemeGroupFilters = function () {
    const selectedFilter = this.card._state.getThemeGroupFilter();

    // Nested groups show only their suffix, matching the group-header display.
    // Animal subgroups have no theme_group key, so tVocab falls back to the
    // suffix — the protected animal name (Cat/Dog/…), never translated.
    const parentOf = (group) => {
      const sep = group.indexOf(" — ");
      if (sep === -1) return null;
      const parent = group.slice(0, sep);
      return THEME_GROUPS.includes(parent) ? parent : null;
    };
    const labelFor = (group) => {
      const display = parentOf(group) ? group.slice(group.lastIndexOf(" — ") + 3) : group;
      return this.tVocab("theme_group", group, display);
    };
    const childrenOf = (parent) => THEME_GROUPS.filter((g) => parentOf(g) === parent);

    const selectedParent = parentOf(selectedFilter);
    const selectedChildren = selectedParent ? [] : childrenOf(selectedFilter);

    let chips;
    if (selectedParent) {
      // Inside a branch: step up, then this child's siblings with it active.
      chips = [
        { value: selectedParent, label: `‹ ${labelFor(selectedParent)}`, back: true },
        ...childrenOf(selectedParent).map((g) => ({ value: g, label: labelFor(g) })),
      ];
    } else if (selectedChildren.length) {
      // A parent that has children: step up to the top, itself, then its children.
      chips = [
        { value: "all", label: `‹ ${this.t("theme.filter_all")}`, back: true },
        { value: selectedFilter, label: labelFor(selectedFilter) },
        ...selectedChildren.map((g) => ({ value: g, label: labelFor(g) })),
      ];
    } else {
      // Top level — all / modified / a childless group. Only parents render.
      chips = [
        { value: "all", label: this.t("theme.filter_all") },
        { value: "modified", label: this.t("theme.filter_modified") },
        ...THEME_GROUPS.filter((g) => parentOf(g) === null).map((g) => ({ value: g, label: labelFor(g) })),
      ];
    }

    return `
      <div class="evcc-chips evcc-theme-filters">
        ${chips.map((chip) => `
          <button
            class="evcc-chip ${chip.back ? "evcc-chip--back " : ""}${selectedFilter === chip.value ? "active" : ""}"
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

    /* How many tokens a group owns ITSELF, counted from the registry and NOT
       through the filters. themeGroupCounts() reports the FILTERED total, which
       is the right number for a header and the wrong one for a structural
       question: under an active search a populated parent transiently counts 0,
       and deciding hierarchy from that would restructure the tree as you type. */
    const ownTokenCount = {};
    for (const def of THEME_TOKEN_REGISTRY) {
      if (PALETTE_KEYS.has(def.key)) continue;
      const g = def.group || "";
      ownTokenCount[g] = (ownTokenCount[g] ?? 0) + 1;
    }

    /* ONE-MEMBER FAMILY — a parent that owns no tokens and has exactly one
       child is a heading wrapped around a heading. "Animal Companion" owns
       global tokens, so its parent row always has something to say; the
       memorial parent "Rainbow Bridge" owns none, so it rendered as
       `Rainbow Bridge (0 / 0)` above `Mittens (0 / 6)` — two disclosure rows
       and a zero count in front of six real tokens.

       Collapse the pair into one row. The CHILD keeps ownership: it holds the
       tokens, so open/closed state, per-group search and reset all continue to
       address the group they actually affect. Only the visible title is
       composed.

       Deliberately conditional on there being exactly one child, so this undoes
       itself the moment a second memorial animal is registered and the parent
       becomes a real grouping again. Safe for the chip filter, which already
       matches descendants via `startsWith(filter + " — ")` — selecting either
       chip still resolves to these tokens. */
    const soleChildOf = (group) =>
      (childrenOf[group] ?? []).length === 1 && !(ownTokenCount[group] > 0)
        ? childrenOf[group][0]
        : null;

    /* Set while rendering: does anything on screen actually take a colour
       gesture? The hint below is hoisted out of the rows, so it must not
       promise a drag to someone looking at a list of numbers and sizes. */
    let anyColorRow = false;

    const renderGroup = (group, nested = false, titleOverride = null) => {
      const groupTokens = this.card._state.filteredThemeTokensForGroup(
        group,
        THEME_TOKEN_REGISTRY,
        { excludeKeys: PALETTE_KEYS }
      );
      if (groupTokens.some((t) => t.type === "color")) anyColorRow = true;
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

      /* Resolved ONCE. The title reaches three sinks — the header, the
         per-group search placeholder and the no-match message — and they must
         agree, or a collapsed one-member family would search under a name it
         never displays. */
      const groupTitle =
        titleOverride ?? this.tVocab("theme_group", group, displayTitle);

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
              ${groupTitle} (${counts.modified} / ${counts.total})
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
              ${(groupTokens.length > 0 || hasActiveSearch) ? `
                <div class="evcc-token-group-search">
                  <input
                    type="text"
                    placeholder="${this.t("theme.group_search_placeholder", { title: groupTitle })}"
                    value="${this.escapeHtml(groupSearchQuery)}"
                    data-theme-group-search="${this.escapeHtml(group)}"
                  />
                </div>
              ` : ""}

              ${groupTokens.length ? `
                ${groupTokens.map((token) =>
                  this._renderThemeTokenRow(
                    token,
                    tokens[token.key],
                    sources[token.key]
                  )
                ).join("")}
              ` : (hasActiveSearch ? `
                <div class="evcc-empty evcc-empty--theme-group-search">
                  ${this.t("theme.group_no_match", { title: groupTitle, query: this.escapeHtml(groupSearchQuery) })}
                </div>
              ` : "")}

              ${childHtml}
            </div>
          ` : ""}
        </div>
      `;
    };

    const renderedGroups = THEME_GROUPS
      .filter((group) => !isChild.has(group))
      .map((group) => {
        const only = soleChildOf(group);
        if (!only) return renderGroup(group);

        /* Render the CHILD in the parent's place, titled with both. The parent
           half is translated ("Rainbow Bridge"); the child half goes through
           tVocab with its own display name as the fallback, which is what keeps
           a memorial animal's name UNTRANSLATED — `vocab.theme_group.*` has a
           key for every floor texture and deliberately none for a pet, because
           a pet's name is not vocabulary. Composing two already-escaped tVocab
           results around a literal separator is safe. */
        const childDisplay = only.slice(only.lastIndexOf(" — ") + 3);
        const title =
          `${this.tVocab("theme_group", group, group)} — ` +
          `${this.tVocab("theme_group", only, childDisplay)}`;
        return renderGroup(only, false, title);
      })
      .filter(Boolean);

    return `
      <div class="evcc-theme-editor-pane">
        ${this._renderThemePreviewPane()}

        <div class="evcc-theme-editor-main">
        ${/* THE SELECTOR IS NOT PART OF WHAT IT SELECTS.
              The chip row used to render INSIDE .evcc-theme-editor-scrollbox,
              so scrolling to a token scrolled the selector off the top — you
              lost your place and had to scroll back up to change group. It has
              its own bounded, scrollable frame, but nesting that inside a
              larger scroll made the bound pointless.
              Hoisted out: chips are pinned above, the token list scrolls
              beneath. Two frames, two scrolls, neither able to push the other
              off screen. */""}
        ${this._renderThemeGroupFilters()}

        <div class="evcc-theme-editor-scrollbox">
        ${/* SAID ONCE, NOT 303 TIMES.
              This hint used to render inside every colour row, on its own line
              — measured at 390px: 12px per row across 303 rows, 3636px of
              scroll spent repeating one sentence. It is also the string that
              overflowed in ru, precisely because a per-row copy had to fit
              beside the input and could only be clipped.
              Hoisted and made sticky, it is stated once, stays on screen while
              you scroll the list it describes, and can WRAP freely — a second
              line costs 14px once instead of 14px times 303. */""}
        ${anyColorRow ? `
          <div class="evcc-token-hint-sticky">${this.t("theme.color_hint")}</div>
        ` : ""}
        <div class="evcc-token-editor">
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
              class="evcc-chip evcc-chip--iconable"
              data-theme-reset="${this.escapeHtml(token.key)}"
              title="${this.escapeHtml(this.t("common.reset"))}"
              aria-label="${this.escapeHtml(this.t("common.reset"))}"
            >
              <span class="evcc-chip-icon">${_iconUndo()}</span>
              <span class="evcc-chip-label">${this.t("common.reset")}</span>
            </button>
          ` : ""}

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
              <button
                class="evcc-chip evcc-chip--iconable"
                data-theme-reset="${this.escapeHtml(token.key)}"
                title="${this.escapeHtml(this.t("common.reset"))}"
                aria-label="${this.escapeHtml(this.t("common.reset"))}"
              >
                <span class="evcc-chip-icon">${_iconUndo()}</span>
                <span class="evcc-chip-label">${this.t("common.reset")}</span>
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
            <span class="evcc-chip">${this.tVocab("token_type", token.type, token.type)}</span>
          </div>

          <div class="token-head-actions">
            ${isDraft ? `
              <button
                class="evcc-chip evcc-chip--iconable"
                data-theme-reset="${this.escapeHtml(token.key)}"
                title="${this.escapeHtml(this.t("common.reset"))}"
                aria-label="${this.escapeHtml(this.t("common.reset"))}"
              >
                <span class="evcc-chip-icon">${_iconUndo()}</span>
                <span class="evcc-chip-label">${this.t("common.reset")}</span>
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
    // The Font Family token gets preset CHIPS (curated stacks + every shipped
    // card font, from FONT_STACK_PRESETS) above the text input — the input
    // stays as the free-form escape hatch. Keyed on the TOKEN, not the
    // "typography" type: font-weight tokens share the type and must not grow
    // font chips. Labels are typeface names, rendered verbatim (never
    // translated). Each chip previews ITSELF via --evcc-font-preview (set as a
    // custom property so the inline-style rule stays within the sanctioned
    // data->CSS escape hatch).
    const fontPresets = token.key === "--evcc-font-family" ? `
        <div class="token-control-row token-control-row--font-presets">
          ${[...FONT_STACK_PRESETS, ...runtimeFontPresets()].map((preset) => `
            <button
              class="evcc-chip evcc-font-preset${value === preset.stack ? " is-active" : ""}"
              style="--evcc-font-preview: ${this.escapeHtml(preset.stack)}"
              data-theme-font-preset="${this.escapeHtml(preset.stack)}"
              data-theme-font-target="${this.escapeHtml(token.key)}"
            >${this.escapeHtml(preset.label)}</button>
          `).join("")}
        </div>` : "";

    return `
      <div class="evcc-token-row evcc-token-row--text ${isDraft ? "is-draft" : ""}">
        <div class="token-head">
          <div class="token-label">
            ${this.tVocab("theme_token", token.key, token.label)}
            <span class="evcc-chip">${this.tVocab("token_type", token.type, token.type)}</span>
            ${isDraft ? `<span class="evcc-chip evcc-chip--custom">${this.t("theme.token_draft")}</span>` : ""}
          </div>

          <div class="token-head-actions">
            ${isDraft ? `
              <button
                class="evcc-chip evcc-chip--iconable"
                data-theme-reset="${this.escapeHtml(token.key)}"
                title="${this.escapeHtml(this.t("common.reset"))}"
                aria-label="${this.escapeHtml(this.t("common.reset"))}"
              >
                <span class="evcc-chip-icon">${_iconUndo()}</span>
                <span class="evcc-chip-label">${this.t("common.reset")}</span>
              </button>
            ` : ""}
          </div>
        </div>
${fontPresets}
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
    // The floor-preset and draft (Save/Discard) controls belong to the token editor,
    // which is reachable at every width — so they ship at every width too. A token
    // editor you cannot Save is worse than none.

    return `
      <div class="evcc-view-footer">
        <div class="footer-left">
          <button
            class="evcc-chip evcc-chip--iconable"
            data-action="export-theme"
            title="${this.t("theme.export_title")}"
            aria-label="${this.escapeHtml(this.t("theme.export"))}"
          >
            <span class="evcc-chip-icon">${_iconTextUp()}</span>
            <span class="evcc-chip-label">${this.t("theme.export")}</span>
          </button>

          <button
            class="evcc-chip evcc-chip--iconable"
            data-action="import-theme"
            title="${this.t("theme.import_title")}"
            aria-label="${this.escapeHtml(this.t("theme.import"))}"
          >
            <span class="evcc-chip-icon">${_iconTextDown()}</span>
            <span class="evcc-chip-label">${this.t("theme.import")}</span>
          </button>

          <button
            class="evcc-chip evcc-chip--iconable"
            data-action="download-theme"
            title="${this.t("theme.download_title")}"
            aria-label="${this.escapeHtml(this.t("theme.download"))}"
          >
            <span class="evcc-chip-icon">${_iconFolderDown()}</span>
            <span class="evcc-chip-label">${this.t("theme.download")}</span>
          </button>

          <button
            class="evcc-chip evcc-chip--iconable"
            data-action="upload-theme"
            title="${this.t("theme.upload_title")}"
            aria-label="${this.escapeHtml(this.t("theme.upload"))}"
          >
            <span class="evcc-chip-icon">${_iconFolderUp()}</span>
            <span class="evcc-chip-label">${this.t("theme.upload")}</span>
          </button>

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
          </button>
        </div>

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
            ${hasActiveTheme ? this.t("common.save") : this.t("theme.save_as_new")}
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

/* =========================================================
   INLINE ICONS — single-color SVGs, inherit currentColor
   =========================================================
   For the four import/export controls in the theme footer.
   The markup carries BOTH an icon and a label at every width
   and CSS chooses between them (mobile.js), which is the same
   contract .evcc-mobile-nav-label uses — no isMobile branch in
   the renderer, and the accessible name comes from aria-label
   so it survives the label being display:none.

   Pairing: T = the TEXT paths (export/import go through the
   paste-JSON modal), folder = the FILE paths (download/upload).
   Arrow direction follows the verb the user reads, not the
   direction the data travels.
   ========================================================= */

function _iconTextUp() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M4 6h9"/>
    <path d="M8.5 6v12"/>
    <path d="M18 19v-9"/>
    <path d="M15.5 12.5 18 10l2.5 2.5"/>
  </svg>`;
}

function _iconTextDown() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M4 6h9"/>
    <path d="M8.5 6v12"/>
    <path d="M18 10v9"/>
    <path d="M15.5 16.5 18 19l2.5-2.5"/>
  </svg>`;
}

function _iconFolderDown() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M3 8V6.5A1.5 1.5 0 0 1 4.5 5h4l2 2h9A1.5 1.5 0 0 1 21 8.5V18a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18V8z"/>
    <path d="M12 10.5v4.5"/>
    <path d="M9.75 12.75 12 15l2.25-2.25"/>
  </svg>`;
}

/* Per-token reset. Counter-clockwise arrow = undo, the shape users already
   read as "put it back" — and it only ever renders on a MODIFIED token, so it
   is a revert of your own edit rather than a destructive action. */
function _iconUndo() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M4 8h9a5.5 5.5 0 0 1 0 11h-6"/>
    <path d="M7.5 4.5 4 8l3.5 3.5"/>
  </svg>`;
}

function _iconFolderUp() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M3 8V6.5A1.5 1.5 0 0 1 4.5 5h4l2 2h9A1.5 1.5 0 0 1 21 8.5V18a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18V8z"/>
    <path d="M12 15v-4.5"/>
    <path d="M9.75 12.75 12 10.5l2.25 2.25"/>
  </svg>`;
}
