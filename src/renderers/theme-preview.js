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

    const body = typeof this[entry.method] === "function"
      ? this[entry.method]()
      : "";

    if (!body) {
      return "";
    }

    return `
      <aside class="evcc-theme-preview-column">
        <section class="evcc-theme-preview-pane">
          <div class="evcc-theme-preview-header">
            <div class="evcc-theme-preview-eyebrow">Contextual Preview</div>
            <div class="evcc-theme-preview-title">
              ${this.escapeHtml(entry.title)}
            </div>
            <div class="evcc-theme-preview-description">
              ${this.escapeHtml(entry.description)}
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
          <div class="evcc-theme-preview-shell-kicker">EVCC Shell</div>
          <h2 class="evcc-theme-preview-heading">Premium vacuum control, calmly organized.</h2>
          <p class="evcc-theme-preview-copy">
            Primary and secondary text plus accent styling define the card’s voice before any specific feature surface appears.
          </p>
          <div class="evcc-theme-preview-inline-actions">
            <span class="evcc-theme-preview-linkish">Open Metrics</span>
            <span class="evcc-theme-preview-accent-pill">Accent</span>
          </div>
        </section>

        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">Text Stack</div>
          <div class="evcc-theme-preview-text-stack">
            <div class="evcc-theme-preview-text-primary">Primary text anchors the main reading path.</div>
            <div class="evcc-theme-preview-text-secondary">Secondary text supports controls and summaries without overpowering them.</div>
            <div class="evcc-theme-preview-text-muted">Muted text handles metadata, helper copy, and low-priority hints.</div>
          </div>
        </section>
      </div>
    `;
  };

  proto._renderThemePreviewCardsSurfaces = function () {
    return `
      <div class="evcc-theme-preview-grid">
        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">Raised Card</div>
          <div class="evcc-theme-preview-surface-card">
            <div class="evcc-theme-preview-surface-title">Card Surface</div>
            <div class="evcc-theme-preview-text-secondary">Shared card background, gap, padding, and surface treatment.</div>
          </div>
        </section>

        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">Panel + Input</div>
          <div class="evcc-theme-preview-surface-panel">
            <div class="evcc-theme-preview-text-secondary">Panel surfaces and nested inputs preview layered elevation.</div>
            <div class="evcc-theme-preview-input">Search tokens...</div>
          </div>
        </section>
      </div>
    `;
  };

  proto._renderThemePreviewBordersShadows = function () {
    return `
      <div class="evcc-theme-preview-grid">
        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">Border Strength</div>
          <div class="evcc-theme-preview-border-stack">
            <div class="evcc-theme-preview-border-sample evcc-theme-preview-border-sample--subtle">Subtle border</div>
            <div class="evcc-theme-preview-border-sample evcc-theme-preview-border-sample--default">Default border</div>
            <div class="evcc-theme-preview-border-sample evcc-theme-preview-border-sample--strong">Strong border</div>
          </div>
        </section>

        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">Shadow Depth</div>
          <div class="evcc-theme-preview-shadow-stack">
            <div class="evcc-theme-preview-shadow-sample evcc-theme-preview-shadow-sample--card">Card shadow</div>
            <div class="evcc-theme-preview-shadow-sample evcc-theme-preview-shadow-sample--hover">Hover shadow</div>
          </div>
        </section>
      </div>
    `;
  };

  proto._renderThemePreviewChips = function () {
    return `
      <div class="evcc-theme-preview-card">
        <div class="evcc-theme-preview-section-title">Chip Matrix</div>
        <div class="evcc-theme-preview-chip-grid">
          <span class="evcc-chip">Default</span>
          <span class="evcc-chip active">Active</span>
          <span class="evcc-chip evcc-theme-preview-chip--hover">Hover</span>
          <span class="evcc-chip evcc-theme-preview-chip--included">Included</span>
          <span class="evcc-chip evcc-theme-preview-chip--excluded">Excluded</span>
          <span class="evcc-chip evcc-theme-preview-chip--success">Success</span>
          <span class="evcc-chip evcc-theme-preview-chip--warning">Warning</span>
        </div>
      </div>
    `;
  };

  proto._renderThemePreviewRoomCards = function () {
    return `
      <div class="evcc-theme-preview-grid evcc-theme-preview-grid--rooms">
        <section class="evcc-theme-preview-room-card">
          <div class="evcc-theme-preview-room-header">
            <div class="evcc-theme-preview-room-name">Kitchen</div>
            <span class="evcc-chip evcc-theme-preview-room-order">#1</span>
          </div>

          <div class="evcc-theme-preview-room-detail-row">
            <span class="evcc-theme-preview-detail-label">Profile</span>
            <span class="evcc-chip evcc-theme-preview-profile-chip">Daily Vacuum</span>
          </div>

          <div class="evcc-theme-preview-room-detail-row">
            <span class="evcc-theme-preview-detail-label">Room</span>
            <span class="evcc-chip evcc-theme-preview-room-chip">Hardwood</span>
          </div>
        </section>

        <section class="evcc-theme-preview-room-card evcc-theme-preview-room-card--filled">
          <div class="evcc-theme-preview-room-header">
            <div class="evcc-theme-preview-room-name">Hallway</div>
            <span class="evcc-chip evcc-theme-preview-room-order">#2</span>
          </div>

          <div class="evcc-theme-preview-room-detail-row">
            <span class="evcc-theme-preview-detail-label">Profile</span>
            <span class="evcc-chip evcc-theme-preview-profile-chip evcc-theme-preview-profile-chip--custom">Custom Profile</span>
          </div>

          <div class="evcc-theme-preview-room-detail-row">
            <span class="evcc-theme-preview-detail-label">Room</span>
            <span class="evcc-chip evcc-theme-preview-room-chip">Area Rug</span>
          </div>
        </section>
      </div>
    `;
  };

  proto._renderThemePreviewFloorTextures = function () {
    const FLOOR_TYPES = [
      { key: "tile",          name: "Tile"         },
      { key: "wood",          name: "Wood"         },
      { key: "marble",        name: "Marble"       },
      { key: "concrete",      name: "Concrete"     },
      { key: "carpet_low",    name: "Carpet Low"   },
      { key: "carpet_high",   name: "Carpet High"  },
      { key: "granite_light", name: "Granite"      },
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
    }, null);
  };

  proto._renderThemePreviewFloorTextureTile     = function () { return this._renderFloorPreviewCard("tile",          "Tile");        };
  proto._renderThemePreviewFloorTextureWood     = function () { return this._renderFloorPreviewCard("wood",          "Wood");        };
  proto._renderThemePreviewFloorTextureMarble   = function () { return this._renderFloorPreviewCard("marble",        "Marble");      };
  proto._renderThemePreviewFloorTextureConcrete = function () { return this._renderFloorPreviewCard("concrete",      "Concrete");    };
  proto._renderThemePreviewFloorTextureCarpetLow  = function () { return this._renderFloorPreviewCard("carpet_low",  "Carpet Low");  };
  proto._renderThemePreviewFloorTextureCarpetHigh = function () { return this._renderFloorPreviewCard("carpet_high", "Carpet High"); };
  proto._renderThemePreviewFloorTextureGranite  = function () { return this._renderFloorPreviewCard("granite_light", "Granite");    };

  proto._renderThemePreviewQueueOrdering = function () {
    return `
      <div class="evcc-theme-preview-card">
        <div class="evcc-theme-preview-section-title">Queue Strip</div>
        <div class="evcc-theme-preview-queue-strip">
          <div class="evcc-theme-preview-queue-chip evcc-theme-preview-queue-chip--current">
            <span class="evcc-chip evcc-theme-preview-order-chip">1</span>
            Kitchen
          </div>
          <div class="evcc-theme-preview-queue-chip evcc-theme-preview-queue-chip--pending">
            <span class="evcc-chip evcc-theme-preview-order-chip">2</span>
            Cat Room
          </div>
          <div class="evcc-theme-preview-queue-chip evcc-theme-preview-queue-chip--completed">
            <span class="evcc-chip evcc-theme-preview-order-chip">3</span>
            Entry
          </div>
          <div class="evcc-theme-preview-queue-chip evcc-theme-preview-queue-chip--inferred">
            <span class="evcc-chip evcc-theme-preview-order-chip">4</span>
            Office
          </div>
        </div>

        <div class="evcc-theme-preview-reorder-row">
          <div class="evcc-theme-preview-drag-card">Dragging</div>
          <div class="evcc-theme-preview-order-target">Drop target</div>
        </div>
      </div>
    `;
  };

  proto._renderThemePreviewStatusAlerts = function () {
    return `
      <div class="evcc-theme-preview-grid">
        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">Status Dots</div>
          <div class="evcc-theme-preview-status-dots">
            <span class="evcc-theme-preview-status-dot evcc-theme-preview-status-dot--idle">Idle</span>
            <span class="evcc-theme-preview-status-dot evcc-theme-preview-status-dot--cleaning">Cleaning</span>
            <span class="evcc-theme-preview-status-dot evcc-theme-preview-status-dot--docked">Docked</span>
            <span class="evcc-theme-preview-status-dot evcc-theme-preview-status-dot--error">Error</span>
          </div>
        </section>

        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">Confidence & Alerts</div>
          <div class="evcc-theme-preview-chip-grid">
            <span class="evcc-chip evcc-theme-preview-confidence-high">High confidence</span>
            <span class="evcc-chip evcc-theme-preview-confidence-medium">Medium confidence</span>
            <span class="evcc-chip evcc-theme-preview-confidence-low">Low confidence</span>
          </div>
          <div class="evcc-theme-preview-alert evcc-theme-preview-alert--info">Information surface</div>
          <div class="evcc-theme-preview-alert evcc-theme-preview-alert--warning">Warning surface</div>
          <div class="evcc-theme-preview-alert evcc-theme-preview-alert--error">Error surface</div>
        </section>
      </div>
    `;
  };

  proto._renderThemePreviewLearningMetrics = function () {
    return `
      <div class="evcc-theme-preview-grid">
        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">Estimate Badges</div>
          <div class="evcc-theme-preview-chip-grid">
            <span class="evcc-chip evcc-theme-preview-estimate-default">~18 min default</span>
            <span class="evcc-chip evcc-theme-preview-estimate-learned">~14 min learned</span>
            <span class="evcc-chip evcc-theme-preview-learning-confidence-high">High confidence</span>
            <span class="evcc-chip evcc-theme-preview-learning-confidence-medium">Building confidence</span>
          </div>
        </section>

        <section class="evcc-theme-preview-learning-panel">
          <div class="evcc-theme-preview-section-title">Learning Panel</div>
          <div class="evcc-theme-preview-text-primary">Estimated water use: 410 ml</div>
          <div class="evcc-theme-preview-text-secondary">Tank after run: 850 ml (28%)</div>
          <div class="evcc-theme-preview-note">Re-anchor suggested after a long interrupted run.</div>
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
              <div class="evcc-theme-preview-modal-title">Maintenance Reset</div>
              <div class="evcc-theme-preview-text-muted">Overlay shell preview</div>
            </div>
            <span class="evcc-chip">X</span>
          </div>

          <div class="evcc-theme-preview-modal-body">
            <div class="evcc-chip evcc-theme-preview-modal-accent-chip">Accent chip</div>
            <div class="evcc-theme-preview-input">Type a note...</div>
            <div class="evcc-theme-preview-alert evcc-theme-preview-alert--warning">This action cannot be undone.</div>
          </div>

          <div class="evcc-theme-preview-modal-footer">
            <span class="evcc-chip">Cancel</span>
            <span class="evcc-chip evcc-chip--save">Confirm</span>
          </div>
        </div>
      </div>
    `;
  };

  // Shared battery-state row config for all animal previews.
  const _ANIMAL_PREVIEW_BATTERY_STATES = [
    { id: "good",     label: "Good",     hint: "battery > 50%" },
    { id: "mid",      label: "Mid",      hint: "25–50%" },
    { id: "warn",     label: "Warn",     hint: "15–25%" },
    { id: "low",      label: "Low",      hint: "≤ 15%" },
    { id: "charging", label: "Charging", hint: "pulses" },
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

    const bodyRows = _ANIMAL_PREVIEW_BATTERY_STATES.map(({ id, label, hint }) => `
      <div class="evcc-theme-preview-animal-row">
        <div class="evcc-theme-preview-animal-rowlabel">
          <span class="evcc-theme-preview-animal-rowlabel-title">${this.escapeHtml(label)}</span>
          <span class="evcc-theme-preview-animal-rowlabel-hint">${this.escapeHtml(hint)}</span>
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
      `Tokens in this <em>parent</em> group apply across <strong>every</strong>
       animal. The five eye-color tokens (<code>--evcc-animal-eye-*</code>) drive
       the rows; the global palette tokens (<code>--evcc-animal-fur</code>,
       <code>--evcc-animal-pupil</code>, etc.) drive every body. Use the
       per-animal sub-groups below to override for a single animal.`
    );
  };

  // Per-animal previews. Each passes the matching animal name (and the
  // corresponding per-animal token prefix in the footer note) to the
  // shared renderer.
  function _animalNote(name, prefix) {
    return `Tokens in this sub-group (prefixed
      <code>${prefix}-…</code>) override the global Animal Companion tokens for
      just the ${name}. Leave any token unset to inherit the parent value
      (or the ${name}'s own built-in default if no theme value is set).`;
  }

  proto._renderThemePreviewAnimalCat = function () {
    return this._renderAnimalPreviewGrid(["cat"], _animalNote("cat", "--evcc-animal-cat"));
  };
  proto._renderThemePreviewAnimalDog = function () {
    return this._renderAnimalPreviewGrid(["dog"], _animalNote("dog", "--evcc-animal-dog"));
  };
  proto._renderThemePreviewAnimalRaccoon = function () {
    return this._renderAnimalPreviewGrid(["raccoon"], _animalNote("raccoon", "--evcc-animal-raccoon"));
  };
  proto._renderThemePreviewAnimalParrot = function () {
    return this._renderAnimalPreviewGrid(["parrot"], _animalNote("parrot", "--evcc-animal-parrot"));
  };
  proto._renderThemePreviewAnimalSnake = function () {
    return this._renderAnimalPreviewGrid(["snake"], _animalNote("snake", "--evcc-animal-snake"));
  };

  proto._renderThemePreviewSharedFoundations = function () {
    return `
      <div class="evcc-theme-preview-grid">
        <section class="evcc-theme-preview-card evcc-theme-preview-foundation-card">
          <div class="evcc-theme-preview-section-title">Surface Stack</div>
          <div class="evcc-theme-preview-surface-panel">
            <div class="evcc-theme-preview-input">Foundation input</div>
            <div class="evcc-theme-preview-chip-grid">
              <span class="evcc-chip">Chip</span>
              <span class="evcc-chip active">Active</span>
            </div>
          </div>
        </section>

        <section class="evcc-theme-preview-room-card">
          <div class="evcc-theme-preview-room-header">
            <div class="evcc-theme-preview-room-name">Mixed Surface</div>
            <span class="evcc-chip evcc-theme-preview-order-chip">3</span>
          </div>
          <div class="evcc-theme-preview-text-secondary">
            Shared gap, radius, font, hover lift, and transition values show up here together.
          </div>
        </section>

        <section class="evcc-theme-preview-learning-panel">
          <div class="evcc-theme-preview-section-title">Composite Sample</div>
          <div class="evcc-theme-preview-status-dots">
            <span class="evcc-theme-preview-status-dot evcc-theme-preview-status-dot--cleaning">Cleaning</span>
          </div>
          <div class="evcc-theme-preview-copy">
            Foundations touch multiple systems, so the preview intentionally mixes a few representative surfaces.
          </div>
        </section>
      </div>
    `;
  };
}
