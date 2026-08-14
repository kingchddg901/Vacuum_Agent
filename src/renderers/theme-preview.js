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
        <section class="evcc-theme-preview-card evcc-theme-preview-shell-frame">
          ${this.renderMobileHeader({
            // THE REAL HEADER, not a drawing of one. What stood here was a hero
            // card with a kicker, a marketing heading, body copy, a link and an
            // accent pill — a surface that exists NOWHERE in this product. It was
            // the most invented preview in the file, so it previewed nothing.
            //
            // The doc's build order said to DELETE this preview, on the grounds
            // that the shell is on screen directly above the editor. That is true
            // on desktop and FALSE on a phone, and the renderer says so itself:
            //   const compactChrome = ctx?.view === "theme";
            // On the Theme view the status block is dropped for vertical budget,
            // so the status rows, dots and battery band are exactly what a phone
            // user CANNOT see while editing the tokens that paint them.
            //
            // Passing a non-theme `view` renders the FULL header on purpose: the
            // preview's job here is to show what the compact chrome takes away.
            view: "rooms",
            vacuumName: this.t("theme_preview.shell.kicker"),
            vacuumStatus: "docked",
            vacuumStatusLabel: null,
            dockStatus: "charging",
            dockStatusLabel: null,
            battery: 100,
            langOverride: "auto",
            currentLang: "en",
            languageMenuOpen: false,
            autoInfo: null,
            uiFont: null,
            // NOT null. renderMobileHeader calls this._renderMapSwitch?.(ctx.state),
            // and that `?.` guards the METHOD existing — not the argument. The body
            // dereferences state.mapSwitcher immediately, so a null state throws and
            // takes the ENTIRE Theme view down for anyone on this group. Both
            // accessors return undefined here, which is the no-switcher case the
            // renderer already handles by returning "".
            state: { mapSwitcher: () => null, mapSwitchPending: () => null },
          })}
        </section>
      </div>
    `;
  };
  /* A text-stack section used to sit here: three sentences of demo copy
     explaining what primary, secondary and muted text are. Removed — it failed
     the same test the hero card above it failed. The rule is that a preview
     earns its space only for surfaces you CANNOT see while editing, and text at
     all three levels is on screen everywhere at once: the header specimen above
     uses them, and so does the editor around it (group title primary, hint
     muted, labels secondary). It was demo copy competing for the pane's budget
     with the one thing here that is genuinely hidden — the status block the
     Theme view's compact chrome drops.

     Also makes this a SINGLE-section preview, so it drops under the 22vh phone
     cap instead of scrolling inside it. */

  /* =========================================================
     ROOM-CARD PREVIEWS - render the product, never a drawing
     =========================================================

     Hand-copies drift. The Modals preview invented two elements the real modal
     does not have and missed four it does; nobody noticed, because a drawing
     cannot disagree with anything. Calling the real renderer makes that class of
     bug impossible: the preview IS the product.

     THE FIXTURE IS DERIVED FROM WHAT renderRoomCard READS, never invented. Every
     field below came from _normalizeRoomDisplayData's own fallback chain
     (rooms.js) and from the card's state-accessor calls. A mock that agrees with
     the CALLER instead of the callee is how this project's theme layout gate once
     passed four tests against an empty editor.

     Largely self-checking, which the drawings never were: a missing field
     produces a card visibly missing its badge. You cannot get a
     plausible-but-wrong picture, only a wrong card, and a wrong card looks wrong.

     DELIBERATELY ABSENT: last_cleaned_at. It renders a RELATIVE time, which would
     drift the tab-theme visual baseline every day it is not re-pinned.
  */
  proto._themePreviewRoom = function (over = {}) {
    return {
      id: 9001,
      name: this.t("theme_preview.rooms.kitchen"),
      slug: "kitchen",
      enabled: true,
      order: 1,
      clean_mode: "vacuum_and_mop",
      fan_speed: "max",
      water_level: "high",
      clean_intensity: "deep",
      clean_passes: 2,
      edge_mopping: true,
      floor_type: "wood",
      ...over,
    };
  };

  // The card calls these six accessors on `state` and nothing else - verified by
  // reading renderRoomCard, not by guessing. Defaults are the quiet case; each
  // preview opts in to only what its own token family needs to show.
  proto._themePreviewState = function (over = {}) {
    return {
      hasActiveRun: () => false,
      orderDragItemId: () => null,
      orderDragOverItemId: () => null,
      troubleRoomForRoom: () => null,
      dashboardPlannedWaterRoomForRoom: () => null,
      roomEstimateForRoom: () => null,
      ...over,
    };
  };

  // Shape taken from the card's own reads: it gates on `error == null`, branches
  // on `source`, formats `minutes`, and drives the card's confidence class from
  // confidence_breakpoint.ui_variant (success -> high, warning -> medium, else low).
  proto._themePreviewEstimate = function (uiVariant = "success") {
    return {
      error: null,
      source: "learned",
      minutes: 12.5,
      battery: 8,
      sample_count: 14,
      confidence_breakpoint: { ui_variant: uiVariant },
    };
  };

  // The REAL grid class, not a preview-only one: .evcc-room-grid is what consumes
  // --evcc-room-grid-gap / -columns / -min and --evcc-grid-gap, so a relationship
  // token edited here moves the preview exactly as it moves the Rooms view.
  proto._themePreviewRoomGrid = function (rooms, state = null) {
    const cards = rooms.map((r) => this.renderRoomCard(r, state)).join("");
    return '<div class="evcc-room-grid evcc-theme-preview-room-grid">' + cards + '</div>';
  };

  proto._renderThemePreviewCardsSurfaces = function () {
    // Card background, radius and the surface scale, on the actual card.
    return this._themePreviewRoomGrid([this._themePreviewRoom()]);
  };

  proto._renderThemePreviewBordersShadows = function () {
    // A chip INSIDE a card: a border is the edge of a card or chip and the shadow
    // sits beneath it, so one composed object carries both. The old preview drew
    // five boxes on a subtle/default/strong SCALE, which is exactly why
    // --evcc-border-warning had no sample anywhere - it is a semantic colour
    // applied to an edge, not a step on that scale.
    return this._themePreviewRoomGrid([this._themePreviewRoom()]);
  };

  proto._renderThemePreviewChips = function () {
    // Every chip the card can show at once: mode, water (mop mode gates it),
    // power, passes and edge-mopping.
    return this._themePreviewRoomGrid([this._themePreviewRoom()]);
  };

  proto._renderThemePreviewRoomCards = function () {
    // The workhorse. Two cards, one disabled, so the enabled and disabled
    // surfaces are visible together rather than one at a time.
    return this._themePreviewRoomGrid([
      this._themePreviewRoom(),
      this._themePreviewRoom({
        id: 9002,
        name: this.t("theme_preview.rooms.hallway"),
        slug: "hallway",
        order: 2,
        enabled: false,
        clean_mode: "vacuum",
        water_level: "",
        edge_mopping: false,
        clean_passes: 1,
        floor_type: "tile",
      }),
    ]);
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
    // A RELATIONSHIP subject - order, gap, columns. You cannot show the space
    // between two cards with one card, so this is one of only two previews that
    // legitimately renders a second area.
    return this._themePreviewRoomGrid([
      this._themePreviewRoom(),
      this._themePreviewRoom({
        id: 9002,
        name: this.t("theme_preview.rooms.hallway"),
        slug: "hallway",
        order: 2,
        floor_type: "tile",
      }),
    ]);
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
    // Needs a state stub: the estimate chip AND the card's confidence class both
    // come from state.roomEstimateForRoom(), so with state=null (the call shape
    // the floor-texture previews use) neither renders and the family previews
    // nothing at all.
    return this._themePreviewRoomGrid(
      [this._themePreviewRoom()],
      this._themePreviewState({
        roomEstimateForRoom: () => this._themePreviewEstimate("success"),
      }),
    );
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
    // The other relationship case: --evcc-gap / --evcc-grid-gap are the space
    // BETWEEN things, so a single card cannot show them.
    return this._themePreviewRoomGrid([
      this._themePreviewRoom(),
      this._themePreviewRoom({
        id: 9002,
        name: this.t("theme_preview.rooms.hallway"),
        slug: "hallway",
        order: 2,
        floor_type: "tile",
      }),
    ]);
  };
}
