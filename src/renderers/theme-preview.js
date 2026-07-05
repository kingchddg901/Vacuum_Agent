/**
 * ============================================================
 * RENDERER: THEME PREVIEW
 * ============================================================
 *
 * Renders the contextual theme preview pane in the theme editor.
 * Mounts only the surfaces affected by the focused token group
 * rather than mirroring the full card on every keystroke.
 *
 * ============================================================
 */

import { THEME_PREVIEW_REGISTRY } from "./theme-preview-registry.js";

/**
 * Mix theme preview renderer methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applyThemePreviewRenderers(proto) {
  /**
   * Render the preview pane for the currently focused theme token group.
   * Returns an empty string when no matching preview exists.
   *
   * @returns {string} HTML string.
   */
  proto._renderThemePreviewPane = function () {
    const group = this.card._state.currentThemePreviewGroup();
    const entry = THEME_PREVIEW_REGISTRY[group];

    if (!entry) {
      return "";
    }

    const args = Array.isArray(entry.methodArgs) ? entry.methodArgs : [];
    const body = typeof this[entry.method] === "function"
      ? this[entry.method](...args)
      : "";

    if (!body) {
      return "";
    }

    // The registry carries stable i18n keys (titleKey/descKey) plus any
    // interpolation vars (titleVars/descVars). Translate at the render site so
    // the registry stays a pure data module. `this.t` escapes the catalog
    // string; per-animal vars are escaped here at the sink.
    const title = entry.titleKey
      ? this.t(entry.titleKey, entry.titleVars)
      : this.escapeHtml(entry.title || "");
    const description = entry.descKey
      ? this.t(entry.descKey, entry.descVars)
      : this.escapeHtml(entry.description || "");

    return `
      <aside class="evcc-theme-preview-column">
        <section class="evcc-theme-preview-pane">
          <div class="evcc-theme-preview-header">
            <div class="evcc-theme-preview-eyebrow">${this.t("theme_preview.eyebrow")}</div>
            <div class="evcc-theme-preview-title">
              ${title}
            </div>
            <div class="evcc-theme-preview-description">
              ${description}
            </div>
          </div>

          <div class="evcc-theme-preview-body">
            ${body}
          </div>
        </section>
      </aside>
    `;
  };

  proto._renderThemePreviewShellTypography = function () {
    return `
      <div class="evcc-theme-preview-grid evcc-theme-preview-grid--shell">
        <section class="evcc-theme-preview-card evcc-theme-preview-card--hero">
          <div class="evcc-theme-preview-shell-kicker">${this.t("theme_preview.shell.kicker")}</div>
          <h2 class="evcc-theme-preview-heading">${this.t("theme_preview.shell.heading")}</h2>
          <p class="evcc-theme-preview-copy">
            ${this.t("theme_preview.shell.copy")}
          </p>
          <div class="evcc-theme-preview-inline-actions">
            <span class="evcc-theme-preview-linkish">${this.t("theme_preview.shell.open_metrics")}</span>
            <span class="evcc-theme-preview-accent-pill">${this.t("theme_preview.shell.accent")}</span>
          </div>
        </section>

        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">${this.t("theme_preview.shell.text_stack")}</div>
          <div class="evcc-theme-preview-text-stack">
            <div class="evcc-theme-preview-text-primary">${this.t("theme_preview.shell.text_primary")}</div>
            <div class="evcc-theme-preview-text-secondary">${this.t("theme_preview.shell.text_secondary")}</div>
            <div class="evcc-theme-preview-text-muted">${this.t("theme_preview.shell.text_muted")}</div>
          </div>
        </section>
      </div>
    `;
  };

  proto._renderThemePreviewCardsSurfaces = function () {
    return `
      <div class="evcc-theme-preview-grid">
        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">${this.t("theme_preview.surfaces.raised_card")}</div>
          <div class="evcc-theme-preview-surface-card">
            <div class="evcc-theme-preview-surface-title">${this.t("theme_preview.surfaces.card_surface")}</div>
            <div class="evcc-theme-preview-text-secondary">${this.t("theme_preview.surfaces.card_desc")}</div>
          </div>
        </section>

        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">${this.t("theme_preview.surfaces.panel_input")}</div>
          <div class="evcc-theme-preview-surface-panel">
            <div class="evcc-theme-preview-text-secondary">${this.t("theme_preview.surfaces.panel_desc")}</div>
            <div class="evcc-theme-preview-input">${this.t("theme_preview.surfaces.search_tokens")}</div>
          </div>
        </section>
      </div>
    `;
  };

  proto._renderThemePreviewBordersShadows = function () {
    return `
      <div class="evcc-theme-preview-grid">
        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">${this.t("theme_preview.borders.border_strength")}</div>
          <div class="evcc-theme-preview-border-stack">
            <div class="evcc-theme-preview-border-sample evcc-theme-preview-border-sample--subtle">${this.t("theme_preview.borders.subtle")}</div>
            <div class="evcc-theme-preview-border-sample evcc-theme-preview-border-sample--default">${this.t("theme_preview.borders.default")}</div>
            <div class="evcc-theme-preview-border-sample evcc-theme-preview-border-sample--strong">${this.t("theme_preview.borders.strong")}</div>
          </div>
        </section>

        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">${this.t("theme_preview.borders.shadow_depth")}</div>
          <div class="evcc-theme-preview-shadow-stack">
            <div class="evcc-theme-preview-shadow-sample evcc-theme-preview-shadow-sample--card">${this.t("theme_preview.borders.card_shadow")}</div>
            <div class="evcc-theme-preview-shadow-sample evcc-theme-preview-shadow-sample--hover">${this.t("theme_preview.borders.hover_shadow")}</div>
          </div>
        </section>
      </div>
    `;
  };

  proto._renderThemePreviewChips = function () {
    return `
      <div class="evcc-theme-preview-card">
        <div class="evcc-theme-preview-section-title">${this.t("theme_preview.chips.matrix")}</div>
        <div class="evcc-theme-preview-chip-grid">
          <span class="evcc-chip">${this.t("theme_preview.chips.default")}</span>
          <span class="evcc-chip active">${this.t("theme_preview.chips.active")}</span>
          <span class="evcc-chip evcc-theme-preview-chip--hover">${this.t("theme_preview.chips.hover")}</span>
          <span class="evcc-chip evcc-theme-preview-chip--included">${this.t("theme_preview.chips.included")}</span>
          <span class="evcc-chip evcc-theme-preview-chip--excluded">${this.t("theme_preview.chips.excluded")}</span>
          <span class="evcc-chip evcc-theme-preview-chip--success">${this.t("theme_preview.chips.success")}</span>
          <span class="evcc-chip evcc-theme-preview-chip--warning">${this.t("theme_preview.chips.warning")}</span>
        </div>
      </div>
    `;
  };

  proto._renderThemePreviewRoomCards = function () {
    return `
      <div class="evcc-theme-preview-grid evcc-theme-preview-grid--rooms">
        <section class="evcc-theme-preview-room-card">
          <div class="evcc-theme-preview-room-header">
            <div class="evcc-theme-preview-room-name">${this.t("theme_preview.rooms.kitchen")}</div>
            <span class="evcc-chip evcc-theme-preview-room-order">#1</span>
          </div>

          <div class="evcc-theme-preview-room-detail-row">
            <span class="evcc-theme-preview-detail-label">${this.t("theme_preview.rooms.profile_label")}</span>
            <span class="evcc-chip evcc-theme-preview-profile-chip">${this.t("theme_preview.rooms.daily_vacuum")}</span>
          </div>

          <div class="evcc-theme-preview-room-detail-row">
            <span class="evcc-theme-preview-detail-label">${this.t("theme_preview.rooms.room_label")}</span>
            <span class="evcc-chip evcc-theme-preview-room-chip">${this.t("theme_preview.rooms.hardwood")}</span>
          </div>
        </section>

        <section class="evcc-theme-preview-room-card evcc-theme-preview-room-card--filled">
          <div class="evcc-theme-preview-room-header">
            <div class="evcc-theme-preview-room-name">${this.t("theme_preview.rooms.hallway")}</div>
            <span class="evcc-chip evcc-theme-preview-room-order">#2</span>
          </div>

          <div class="evcc-theme-preview-room-detail-row">
            <span class="evcc-theme-preview-detail-label">${this.t("theme_preview.rooms.profile_label")}</span>
            <span class="evcc-chip evcc-theme-preview-profile-chip evcc-theme-preview-profile-chip--custom">${this.t("theme_preview.rooms.custom_profile")}</span>
          </div>

          <div class="evcc-theme-preview-room-detail-row">
            <span class="evcc-theme-preview-detail-label">${this.t("theme_preview.rooms.room_label")}</span>
            <span class="evcc-chip evcc-theme-preview-room-chip">${this.t("theme_preview.rooms.area_rug")}</span>
          </div>
        </section>
      </div>
    `;
  };

  proto._renderThemePreviewFloorTextures = function () {
    const FLOOR_TYPES = [
      { key: "tile",          name: this.t("theme_preview.floor.tile")        },
      { key: "wood",          name: this.t("theme_preview.floor.wood")        },
      { key: "marble",        name: this.t("theme_preview.floor.marble")      },
      { key: "concrete",      name: this.t("theme_preview.floor.concrete")    },
      { key: "carpet_low",    name: this.t("theme_preview.floor.carpet_low")  },
      { key: "carpet_high",   name: this.t("theme_preview.floor.carpet_high") },
      { key: "granite_light", name: this.t("theme_preview.floor.granite")     },
    ];

    const cards = FLOOR_TYPES.map(({ key, name }) => this._renderFloorPreviewCard(key, name)).join("");

    return `<div class="evcc-theme-preview-ftx-card-grid">${cards}</div>`;
  };

  proto._renderFloorPreviewCard = function (floorTypeKey, name) {
    return this.renderRoomCard({
      id:         `preview-ftx-${floorTypeKey}`,
      name:       name ?? floorTypeKey,
      floor_type: floorTypeKey,
      enabled:    true,
      order:      1,
      // Always render the material here even when room-card textures are toggled off — a
      // preview must preview (see _renderFloorTextureLayer's forceFloorTexture bypass).
      force_floor_texture: true,
    }, null);
  };

  proto._renderThemePreviewFloorTextureTile     = function () { return this._renderFloorPreviewCard("tile",          this.t("theme_preview.floor.tile"));        };
  proto._renderThemePreviewFloorTextureWood     = function () { return this._renderFloorPreviewCard("wood",          this.t("theme_preview.floor.wood"));        };
  proto._renderThemePreviewFloorTextureMarble   = function () { return this._renderFloorPreviewCard("marble",        this.t("theme_preview.floor.marble"));      };
  proto._renderThemePreviewFloorTextureConcrete = function () { return this._renderFloorPreviewCard("concrete",      this.t("theme_preview.floor.concrete"));    };
  proto._renderThemePreviewFloorTextureCarpetLow  = function () { return this._renderFloorPreviewCard("carpet_low",  this.t("theme_preview.floor.carpet_low"));  };
  proto._renderThemePreviewFloorTextureCarpetHigh = function () { return this._renderFloorPreviewCard("carpet_high", this.t("theme_preview.floor.carpet_high")); };
  proto._renderThemePreviewFloorTextureGranite  = function () { return this._renderFloorPreviewCard("granite_light", this.t("theme_preview.floor.granite"));    };

  proto._renderThemePreviewQueueOrdering = function () {
    return `
      <div class="evcc-theme-preview-card">
        <div class="evcc-theme-preview-section-title">${this.t("theme_preview.queue.strip")}</div>
        <div class="evcc-theme-preview-queue-strip">
          <div class="evcc-theme-preview-queue-chip evcc-theme-preview-queue-chip--current">
            <span class="evcc-chip evcc-theme-preview-order-chip">1</span>
            ${this.t("theme_preview.rooms.kitchen")}
          </div>
          <div class="evcc-theme-preview-queue-chip evcc-theme-preview-queue-chip--pending">
            <span class="evcc-chip evcc-theme-preview-order-chip">2</span>
            ${this.t("theme_preview.queue.cat_room")}
          </div>
          <div class="evcc-theme-preview-queue-chip evcc-theme-preview-queue-chip--completed">
            <span class="evcc-chip evcc-theme-preview-order-chip">3</span>
            ${this.t("theme_preview.queue.entry")}
          </div>
          <div class="evcc-theme-preview-queue-chip evcc-theme-preview-queue-chip--inferred">
            <span class="evcc-chip evcc-theme-preview-order-chip">4</span>
            ${this.t("theme_preview.queue.office")}
          </div>
        </div>

        <div class="evcc-theme-preview-reorder-row">
          <div class="evcc-theme-preview-drag-card">${this.t("theme_preview.queue.dragging")}</div>
          <div class="evcc-theme-preview-order-target">${this.t("theme_preview.queue.drop_target")}</div>
        </div>
      </div>
    `;
  };

  proto._renderThemePreviewStatusAlerts = function () {
    return `
      <div class="evcc-theme-preview-grid">
        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">${this.t("theme_preview.status.dots")}</div>
          <div class="evcc-theme-preview-status-dots">
            <span class="evcc-theme-preview-status-dot evcc-theme-preview-status-dot--idle">${this.t("theme_preview.status.idle")}</span>
            <span class="evcc-theme-preview-status-dot evcc-theme-preview-status-dot--cleaning">${this.t("theme_preview.status.cleaning")}</span>
            <span class="evcc-theme-preview-status-dot evcc-theme-preview-status-dot--docked">${this.t("theme_preview.status.docked")}</span>
            <span class="evcc-theme-preview-status-dot evcc-theme-preview-status-dot--error">${this.t("theme_preview.status.error")}</span>
          </div>
        </section>

        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">${this.t("theme_preview.status.confidence_alerts")}</div>
          <div class="evcc-theme-preview-chip-grid">
            <span class="evcc-chip evcc-theme-preview-confidence-high">${this.t("theme_preview.confidence.high")}</span>
            <span class="evcc-chip evcc-theme-preview-confidence-medium">${this.t("theme_preview.confidence.medium")}</span>
            <span class="evcc-chip evcc-theme-preview-confidence-low">${this.t("theme_preview.confidence.low")}</span>
          </div>
          <div class="evcc-theme-preview-alert evcc-theme-preview-alert--info">${this.t("theme_preview.status.info_surface")}</div>
          <div class="evcc-theme-preview-alert evcc-theme-preview-alert--warning">${this.t("theme_preview.status.warning_surface")}</div>
          <div class="evcc-theme-preview-alert evcc-theme-preview-alert--error">${this.t("theme_preview.status.error_surface")}</div>
        </section>
      </div>
    `;
  };

  proto._renderThemePreviewLearningMetrics = function () {
    return `
      <div class="evcc-theme-preview-grid">
        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">${this.t("theme_preview.learning.estimate_badges")}</div>
          <div class="evcc-theme-preview-chip-grid">
            <span class="evcc-chip evcc-theme-preview-estimate-default">${this.t("theme_preview.learning.estimate_default", { min: 18 })}</span>
            <span class="evcc-chip evcc-theme-preview-estimate-learned">${this.t("theme_preview.learning.estimate_learned", { min: 14 })}</span>
            <span class="evcc-chip evcc-theme-preview-learning-confidence-high">${this.t("theme_preview.confidence.high")}</span>
            <span class="evcc-chip evcc-theme-preview-learning-confidence-medium">${this.t("theme_preview.confidence.building")}</span>
          </div>
        </section>

        <section class="evcc-theme-preview-learning-panel">
          <div class="evcc-theme-preview-section-title">${this.t("theme_preview.learning.panel")}</div>
          <div class="evcc-theme-preview-text-primary">${this.t("theme_preview.learning.water_use", { ml: 410 })}</div>
          <div class="evcc-theme-preview-text-secondary">${this.t("theme_preview.learning.tank_after", { ml: 850, pct: 28 })}</div>
          <div class="evcc-theme-preview-note">${this.t("theme_preview.learning.reanchor_note")}</div>
        </section>
      </div>
    `;
  };

  proto._renderThemePreviewModalsOverlays = function () {
    return `
      <div class="evcc-theme-preview-modal-stage">
        <div class="evcc-theme-preview-modal-backdrop"></div>
        <div class="evcc-theme-preview-modal">
          <div class="evcc-theme-preview-modal-header">
            <div>
              <div class="evcc-theme-preview-modal-title">${this.t("theme_preview.modal.title")}</div>
              <div class="evcc-theme-preview-text-muted">${this.t("theme_preview.modal.subtitle")}</div>
            </div>
            <span class="evcc-chip">X</span>
          </div>

          <div class="evcc-theme-preview-modal-body">
            <div class="evcc-chip evcc-theme-preview-modal-accent-chip">${this.t("theme_preview.modal.accent_chip")}</div>
            <div class="evcc-theme-preview-input">${this.t("theme_preview.modal.type_note")}</div>
            <div class="evcc-theme-preview-alert evcc-theme-preview-alert--warning">${this.t("theme_preview.modal.cannot_undo")}</div>
          </div>

          <div class="evcc-theme-preview-modal-footer">
            <span class="evcc-chip">${this.t("common.cancel")}</span>
            <span class="evcc-chip evcc-chip--save">${this.t("theme_preview.modal.confirm")}</span>
          </div>
        </div>
      </div>
    `;
  };

  // Shared battery-state row config for all animal previews. The visible
  // label/hint are i18n keys resolved at the render site (this.t); `id` is the
  // battery-state data attribute and stays literal.
  const _ANIMAL_PREVIEW_BATTERY_STATES = [
    { id: "good",     labelKey: "theme_preview.animal.battery_good_label",     hintKey: "theme_preview.animal.battery_good_hint" },
    { id: "mid",      labelKey: "theme_preview.animal.battery_mid_label",      hintKey: "theme_preview.animal.battery_mid_hint" },
    { id: "warn",     labelKey: "theme_preview.animal.battery_warn_label",     hintKey: "theme_preview.animal.battery_warn_hint" },
    { id: "low",      labelKey: "theme_preview.animal.battery_low_label",      hintKey: "theme_preview.animal.battery_low_hint" },
    { id: "charging", labelKey: "theme_preview.animal.battery_charging_label", hintKey: "theme_preview.animal.battery_charging_hint" },
  ];

  /**
   * Renders the battery-state × animal preview grid. The parent
   * "Animal Companion" preview passes all registered animals; each
   * per-animal sub-group preview passes a single-element list.
   *
   * @private
   * @param {string[]} animals   list of animal names (columns)
   * @param {string}  noteHtml   contextual footer note for this group
   */
  proto._renderAnimalPreviewGrid = function (animals, noteHtml) {
    const headerRow = `
      <div class="evcc-theme-preview-animal-row evcc-theme-preview-animal-row--header">
        <div class="evcc-theme-preview-animal-rowlabel"></div>
        ${animals.map((a) => `
          <div class="evcc-theme-preview-animal-collabel">${this.escapeHtml(a)}</div>
        `).join("")}
      </div>
    `;

    const bodyRows = _ANIMAL_PREVIEW_BATTERY_STATES.map(({ id, labelKey, hintKey }) => `
      <div class="evcc-theme-preview-animal-row">
        <div class="evcc-theme-preview-animal-rowlabel">
          <span class="evcc-theme-preview-animal-rowlabel-title">${this.t(labelKey)}</span>
          <span class="evcc-theme-preview-animal-rowlabel-hint">${this.t(hintKey)}</span>
        </div>
        ${animals.map((a) => `
          <div class="evcc-theme-preview-animal-cell">
            <animal-svg
              animal="${this.escapeHtml(a)}"
              pose="standing"
              battery-state="${this.escapeHtml(id)}"
              width="${animals.length === 1 ? "140" : "80"}px"
              height="${animals.length === 1 ? "96" : "55"}px"></animal-svg>
          </div>
        `).join("")}
      </div>
    `).join("");

    return `
      <div class="evcc-theme-preview-animal-grid${animals.length === 1 ? " evcc-theme-preview-animal-grid--single" : ""}">
        ${headerRow}
        ${bodyRows}
      </div>
      <div class="evcc-theme-preview-animal-note">${noteHtml}</div>
    `;
  };

  proto._renderThemePreviewAnimalCompanion = function () {
    // Parent group preview: every registered animal in a column. If the
    // animal-svg module hasn't finished loading the cells render the
    // built-in "unknown animal" fallback — itself a useful signal.
    const animals = (window.AnimalSVG && window.AnimalSVG.list)
      ? window.AnimalSVG.list()
      : ["cat", "dog", "raccoon", "parrot", "snake"];
    return this._renderAnimalPreviewGrid(
      animals,
      this.tRaw("theme_preview.animal.parent_note")
    );
  };

  /**
   * Parameterized per-animal preview. Driven by the dynamic entries
   * theme-preview-registry generates from the live AnimalSVG list —
   * the entry passes the animal name through methodArgs.
   *
   * @param {string} animalName
   */
  proto._renderThemePreviewAnimal = function (animalName) {
    const safe = String(animalName || "").replace(/[^a-z0-9-]/gi, "");
    if (!safe) return "";
    // Authored markup (<code>) with the sanitized animal name interpolated raw,
    // exactly as the original literal did (safe is [a-z0-9-]-only).
    const note = this.tRaw("theme_preview.animal.subgroup_note", { animal: safe });
    return this._renderAnimalPreviewGrid([safe], note);
  };

  proto._renderThemePreviewSharedFoundations = function () {
    return `
      <div class="evcc-theme-preview-grid">
        <section class="evcc-theme-preview-card evcc-theme-preview-foundation-card">
          <div class="evcc-theme-preview-section-title">${this.t("theme_preview.foundations.surface_stack")}</div>
          <div class="evcc-theme-preview-surface-panel">
            <div class="evcc-theme-preview-input">${this.t("theme_preview.foundations.foundation_input")}</div>
            <div class="evcc-theme-preview-chip-grid">
              <span class="evcc-chip">${this.t("theme_preview.foundations.chip")}</span>
              <span class="evcc-chip active">${this.t("theme_preview.chips.active")}</span>
            </div>
          </div>
        </section>

        <section class="evcc-theme-preview-room-card">
          <div class="evcc-theme-preview-room-header">
            <div class="evcc-theme-preview-room-name">${this.t("theme_preview.foundations.mixed_surface")}</div>
            <span class="evcc-chip evcc-theme-preview-order-chip">3</span>
          </div>
          <div class="evcc-theme-preview-text-secondary">
            ${this.t("theme_preview.foundations.mixed_desc")}
          </div>
        </section>

        <section class="evcc-theme-preview-learning-panel">
          <div class="evcc-theme-preview-section-title">${this.t("theme_preview.foundations.composite_sample")}</div>
          <div class="evcc-theme-preview-status-dots">
            <span class="evcc-theme-preview-status-dot evcc-theme-preview-status-dot--cleaning">${this.t("theme_preview.status.cleaning")}</span>
          </div>
          <div class="evcc-theme-preview-copy">
            ${this.t("theme_preview.foundations.composite_desc")}
          </div>
        </section>
      </div>
    `;
  };
}
