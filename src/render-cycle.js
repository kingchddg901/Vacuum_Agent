// Render cycle helpers: view constants, render context builder, header/nav HTML, and view router.

import { renderLanguageControl } from "./renderers/language-control.js";

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
  VIEWS.SETUP,
];

/**
 * Whether a view's nav TAB should be shown for the active adapter. Capability-
 * gated via the dashboard snapshot (default true = show, so Eufy and older
 * backends are unaffected). The view ROOT still exists in VIEW_ORDER — only the
 * tab button is hidden — so the view stays routable internally (mirrors how
 * MAP_CONFIG is rendered without a tab). The single source of truth shared by the
 * desktop header, the mobile shell, and the active/persisted-view fallback so the
 * three never drift.
 *
 * @param {string} view - a VIEWS.* value.
 * @param {object|null|undefined} state - VacuumCardState (carries the snapshot).
 * @returns {boolean}
 */
export function isViewAvailable(view, state) {
  if (view === VIEWS.BASE_STATION) return state?.supportsBaseStation?.() !== false;
  return true;
}

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
    // Header language control: the raw per-user choice (marks the active row),
    // the resolved language (the button badge), and the dropdown open flag.
    // All card-level so they survive the periodic header re-render.
    langOverride:      card._langOverride ?? "auto",
    currentLang:       card._i18nLanguage?.() ?? "en",
    languageMenuOpen:  !!card._languageMenuOpen,
    autoInfo:          card._autoLangInfo?.() ?? { systemLang: "en", gatedToEnglish: false },
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
  const { state, renderers, vacuumName, vacuumStatus, vacuumStatusLabel,
          dockStatus, dockStatusLabel, battery, view,
          langOverride, currentLang, languageMenuOpen, autoInfo } = ctx;

  const batteryText = battery != null ? `${battery}%` : "";

  // Prefer the backend-provided label (server-side _display_label) so
  // adapter vocabulary stays the source of truth. Title-case fallback
  // covers the first frame after mount, before the dashboard snapshot
  // has populated.
  // Localize the device-status VALUE (Docked / Idle / Cleaning / Washing …) via
  // the adapter vocab, falling back to the backend-provided label (then a
  // title-cased raw) for any state not yet keyed. tVocabRaw — the sink escapes.
  const vacuumText = renderers.tVocabRaw("device_status", vacuumStatus, vacuumStatusLabel ?? fallbackTitleCase(vacuumStatus));
  const dockText = dockStatus
    ? renderers.tVocabRaw("device_status", dockStatus, dockStatusLabel ?? fallbackTitleCase(dockStatus))
    : "";

  return `
    <div class="evcc-header">

      <div class="evcc-header-left">
        <div class="evcc-vacuum-name">
          ${renderers.escapeHtml(vacuumName)}
        </div>

        <div class="evcc-vacuum-status">
          <span class="evcc-status-dot ${getStatusClass(vacuumStatus)}"></span>
          <span class="evcc-status-prefix">${renderers.t("nav.vacuum_status")}</span>
          <span>${renderers.escapeHtml(vacuumText)}</span>
          ${batteryText
            ? `<span class="evcc-battery">${renderers.escapeHtml(batteryText)}</span>`
            : ""}
        </div>

        ${dockText ? `
          <div class="evcc-vacuum-status evcc-dock-status">
            <span class="evcc-status-dot ${getDockStatusClass(dockStatus)}"></span>
            <span class="evcc-status-prefix">${renderers.t("nav.dock_status")}</span>
            <span>${renderers.escapeHtml(dockText)}</span>
          </div>
        ` : ""}
      </div>

      <div class="evcc-header-right">
        ${renderLanguageControl(renderers, {
          langOverride, currentLang, open: languageMenuOpen, autoInfo,
        })}
      </div>

    </div>

    <div class="evcc-nav">

      <button class="evcc-nav-tab ${view === VIEWS.ROOMS ? "active" : ""}"
              data-view="${VIEWS.ROOMS}">
        ${renderers.t("nav.tab_rooms")}
      </button>

      <button class="evcc-nav-tab ${view === VIEWS.MAINTENANCE ? "active" : ""}"
              data-view="${VIEWS.MAINTENANCE}">
        ${renderers.t("nav.tab_maintenance")}
      </button>

      ${isViewAvailable(VIEWS.BASE_STATION, state) ? `
      <button class="evcc-nav-tab ${view === VIEWS.BASE_STATION ? "active" : ""}"
              data-view="${VIEWS.BASE_STATION}">
        ${renderers.t("nav.tab_base_station")}
      </button>
      ` : ""}

      <button class="evcc-nav-tab ${view === VIEWS.METRICS ? "active" : ""}"
              data-view="${VIEWS.METRICS}">
        ${renderers.t("nav.tab_metrics")}
      </button>

      <button class="evcc-nav-tab ${view === VIEWS.LEARNING_REVIEW ? "active" : ""}"
              data-view="${VIEWS.LEARNING_REVIEW}">
        ${renderers.t("nav.tab_learning_review")}
      </button>

      <button class="evcc-nav-tab ${view === VIEWS.ROOM_RULES ? "active" : ""}"
              data-view="${VIEWS.ROOM_RULES}">
        ${renderers.t("nav.tab_room_rules")}
      </button>

      <button class="evcc-nav-tab ${view === VIEWS.THEME ? "active" : ""}"
              data-view="${VIEWS.THEME}">
        ${renderers.t("nav.tab_theme")}
      </button>

      <button class="evcc-nav-tab ${view === VIEWS.SETUP ? "active" : ""}"
              data-view="${VIEWS.SETUP}">
        ${renderers.t("nav.tab_setup")}
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
        ?? `<div class="evcc-empty">${renderers.t("nav.unavailable_rooms")}</div>`;

    case VIEWS.MAINTENANCE:
      return renderers.renderMaintenanceView?.(ctx)
        ?? `<div class="evcc-empty">${renderers.t("nav.unavailable_maintenance")}</div>`;

    case VIEWS.BASE_STATION:
      return renderers.renderBaseStationView?.(ctx)
        ?? `<div class="evcc-empty">${renderers.t("nav.unavailable_base_station")}</div>`;

    case VIEWS.METRICS:
      return renderers.renderMetricsView?.(ctx)
        ?? `<div class="evcc-empty">${renderers.t("nav.unavailable_metrics")}</div>`;

    case VIEWS.LEARNING_REVIEW:
      return renderers.renderLearningReviewView?.(ctx)
        ?? `<div class="evcc-empty">${renderers.t("nav.unavailable_learning_review")}</div>`;

    case VIEWS.ROOM_RULES:
      return renderers.renderRoomRulesView?.(ctx)
        ?? `<div class="evcc-empty">${renderers.t("nav.unavailable_room_rules")}</div>`;

    case VIEWS.THEME:
      return renderers.renderThemeView?.(ctx)
        ?? `<div class="evcc-empty">${renderers.t("nav.unavailable_theme")}</div>`;

    case VIEWS.MAP_CONFIG:
      return renderers.renderMapConfigView?.(ctx)
        ?? `<div class="evcc-empty">${renderers.t("nav.unavailable_map_config")}</div>`;

    case VIEWS.SETUP:
      return renderers.renderSetupView?.(ctx)
        ?? `<div class="evcc-empty">${renderers.t("nav.unavailable_setup")}</div>`;

    default:
      return `<div class="evcc-empty">${renderers.t("nav.unavailable_unknown")}</div>`;
  }
}

