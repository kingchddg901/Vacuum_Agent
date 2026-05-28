// Render cycle helpers: view constants, render context builder, header/nav HTML, and view router.

/* =========================================================
   VIEW CONSTANTS
   ========================================================= */

export const VIEWS = {
  ROOMS:           "rooms",
  MAINTENANCE:     "maintenance",
  BASE_STATION:    "base_station",
  METRICS:         "metrics",
  LEARNING_REVIEW: "learning_review",
  ROOM_RULES:      "room_rules",
  THEME:           "theme",
  MAPPING_ARCHIVE: "mapping",
  MAP_CONFIG:      "map_config",
  MAPPING_REVIEW:  "mapping_review",
  SETUP:           "setup",
};

export const VIEW_ORDER = [
  VIEWS.ROOMS,
  VIEWS.MAINTENANCE,
  VIEWS.BASE_STATION,
  VIEWS.METRICS,
  VIEWS.LEARNING_REVIEW,
  VIEWS.ROOM_RULES,
  VIEWS.THEME,
  VIEWS.MAP_CONFIG,
  VIEWS.MAPPING_REVIEW,
  VIEWS.SETUP,
];

/* =========================================================
   CONTEXT
   ========================================================= */

/**
 * Build the shared render context object passed to every renderer.
 * @param {EufyVacuumCommandCenter} card
 * @returns {{ card, state, renderers, vacuumName, vacuumStatus, battery, view }}
 */
export function buildRenderContext(card) {
  const state     = card._state;
  const renderers = card._renderers;

  return {
    card,
    state,
    renderers,
    vacuumName:        state.vacuumDisplayName(),
    vacuumStatus:      state.vacuumState() ?? "unknown",
    vacuumStatusLabel: state.vacuumStateLabel?.() ?? null,
    dockStatus:        state.dockStatus?.() ?? null,
    dockStatusLabel:   state.dockStatusLabel?.() ?? null,
    battery:           state.batteryLevel(),
    view:              card._view ?? VIEWS.ROOMS,
  };
}

/* =========================================================
   STATUS DOT CLASS MAPPING
   ========================================================= */

function getStatusClass(status) {
  return {
    cleaning:  "cleaning",
    docked:    "docked",
    returning: "returning",
    error:     "error",
    paused:    "paused",
  }[status] || "";
}

/**
 * Defensive fallback for the brief window before the dashboard
 * snapshot has populated vacuum_state_label / dock_status_label.
 * Backend-provided labels are the source of truth; this exists so
 * the header doesn't show a lowercase `docked` for one paint cycle.
 *
 * "docked" → "Docked", "returning_to_base" → "Returning To Base".
 */
function fallbackTitleCase(raw) {
  return String(raw ?? "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\w\S*/g, (word) =>
      word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
    );
}

/**
 * Map a dock status value (from the dock_status sensor) to a status dot
 * class. Falls back to the empty string for unknown/idle so the dot uses
 * the default muted colour.
 */
function getDockStatusClass(dockStatus) {
  const key = String(dockStatus ?? "").trim().toLowerCase();
  return {
    cleaning:  "cleaning",
    washing:   "cleaning",
    drying:    "returning",
    emptying:  "returning",
    charging:  "charging",
    error:     "error",
    fault:     "error",
    offline:   "offline",
    unavailable: "unavailable",
    idle:      "docked",
    standby:   "docked",
  }[key] || "";
}

/* =========================================================
   HEADER
   ========================================================= */

/**
 * Render the card header (vacuum name/status) and navigation tabs.
 * @param {{ renderers, vacuumName, vacuumStatus, battery, view }} ctx
 * @returns {string} HTML string
 */
export function renderHeader(ctx) {
  const { renderers, vacuumName, vacuumStatus, vacuumStatusLabel,
          dockStatus, dockStatusLabel, battery, view } = ctx;

  const batteryText = battery != null ? `${battery}%` : "";

  // Prefer the backend-provided label (server-side _display_label) so
  // adapter vocabulary stays the source of truth. Title-case fallback
  // covers the first frame after mount, before the dashboard snapshot
  // has populated.
  const vacuumText = vacuumStatusLabel ?? fallbackTitleCase(vacuumStatus);
  const dockText = dockStatusLabel
    ?? (dockStatus ? fallbackTitleCase(dockStatus) : "");

  return `
    <div class="evcc-header">

      <div class="evcc-header-left">
        <div class="evcc-vacuum-name">
          ${renderers.escapeHtml(vacuumName)}
        </div>

        <div class="evcc-vacuum-status">
          <span class="evcc-status-dot ${getStatusClass(vacuumStatus)}"></span>
          <span class="evcc-status-prefix">Vacuum Status:</span>
          <span>${renderers.escapeHtml(vacuumText)}</span>
          ${batteryText
            ? `<span class="evcc-battery">${renderers.escapeHtml(batteryText)}</span>`
            : ""}
        </div>

        ${dockText ? `
          <div class="evcc-vacuum-status evcc-dock-status">
            <span class="evcc-status-dot ${getDockStatusClass(dockStatus)}"></span>
            <span class="evcc-status-prefix">Dock Status:</span>
            <span>${renderers.escapeHtml(dockText)}</span>
          </div>
        ` : ""}
      </div>

    </div>

    <div class="evcc-nav">

      <button class="evcc-nav-tab ${view === VIEWS.ROOMS ? "active" : ""}"
              data-view="${VIEWS.ROOMS}">
        Rooms
      </button>

      <button class="evcc-nav-tab ${view === VIEWS.MAINTENANCE ? "active" : ""}"
              data-view="${VIEWS.MAINTENANCE}">
        Maintenance
      </button>

      <button class="evcc-nav-tab ${view === VIEWS.BASE_STATION ? "active" : ""}"
              data-view="${VIEWS.BASE_STATION}">
        Base Station
      </button>

      <button class="evcc-nav-tab ${view === VIEWS.METRICS ? "active" : ""}"
              data-view="${VIEWS.METRICS}">
        Metrics
      </button>

      <button class="evcc-nav-tab ${view === VIEWS.LEARNING_REVIEW ? "active" : ""}"
              data-view="${VIEWS.LEARNING_REVIEW}">
        Learning Review
      </button>

      <button class="evcc-nav-tab ${view === VIEWS.ROOM_RULES ? "active" : ""}"
              data-view="${VIEWS.ROOM_RULES}">
        Room Rules
      </button>

      <button class="evcc-nav-tab ${view === VIEWS.THEME ? "active" : ""}"
              data-view="${VIEWS.THEME}">
        Theme
      </button>

      <button class="evcc-nav-tab ${view === VIEWS.MAPPING_REVIEW ? "active" : ""}"
              data-view="${VIEWS.MAPPING_REVIEW}">
        Map Bounds
      </button>

      <button class="evcc-nav-tab ${view === VIEWS.SETUP ? "active" : ""}"
              data-view="${VIEWS.SETUP}">
        Setup
      </button>

    </div>
  `;
}

/* =========================================================
   VIEW ROUTER
   ========================================================= */

/**
 * Dispatch to the active view renderer by name.
 * @param {{ view, renderers }} ctx
 * @returns {string} HTML string
 */
export function renderView(ctx) {
  const { view, renderers } = ctx;

  switch (view) {
    case VIEWS.ROOMS:
      return renderers.renderRoomsView?.(ctx)
        ?? `<div class="evcc-empty">Rooms view unavailable</div>`;

    case VIEWS.MAINTENANCE:
      return renderers.renderMaintenanceView?.(ctx)
        ?? `<div class="evcc-empty">Maintenance view unavailable</div>`;

    case VIEWS.BASE_STATION:
      return renderers.renderBaseStationView?.(ctx)
        ?? `<div class="evcc-empty">Base station view unavailable</div>`;

    case VIEWS.METRICS:
      return renderers.renderMetricsView?.(ctx)
        ?? `<div class="evcc-empty">Metrics view unavailable</div>`;

    case VIEWS.LEARNING_REVIEW:
      return renderers.renderLearningReviewView?.(ctx)
        ?? `<div class="evcc-empty">Learning review view unavailable</div>`;

    case VIEWS.ROOM_RULES:
      return renderers.renderRoomRulesView?.(ctx)
        ?? `<div class="evcc-empty">Room rules view unavailable</div>`;

    case VIEWS.THEME:
      return renderers.renderThemeView?.(ctx)
        ?? `<div class="evcc-empty">Theme view unavailable</div>`;

    case VIEWS.MAP_CONFIG:
      return renderers.renderMapConfigView?.(ctx)
        ?? `<div class="evcc-empty">Map config unavailable</div>`;

    case VIEWS.MAPPING_REVIEW:
      return renderers.renderMappingReviewView?.(ctx)
        ?? `<div class="evcc-empty">Mapping bounds review unavailable</div>`;

    case VIEWS.SETUP:
      return renderers.renderSetupView?.(ctx)
        ?? `<div class="evcc-empty">Setup unavailable</div>`;

    default:
      return `<div class="evcc-empty">Unknown view</div>`;
  }
}

