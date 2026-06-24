/**
 * Mobile shell renderers.
 *
 * Provides the chrome pieces (compact header, bottom-tab nav,
 * overflow sheet) that wrap the existing per-view content when the
 * card is rendered on a mobile viewport (<600px wide).
 *
 * Design choice: the card's existing render path keeps per-view DOM
 * roots alive across renders (so switching tabs preserves scroll
 * position, focus, etc.). We don't want to throw that away on
 * mobile. So instead of replacing the entire shell, the mobile path
 * just swaps the header content (no top nav) and adds two extra
 * regions at the bottom of the card: a bottom-tab nav and an
 * optional overflow sheet. The view-stage and view-roots in between
 * are shared with the desktop path.
 *
 * Layout shape:
 *   ┌─────────────────────────────┐
 *   │ Header: vacuum + status     │  ← evcc-mobile-header (top)
 *   ├─────────────────────────────┤
 *   │                             │
 *   │ View content                │  ← shared view-stage / view-roots
 *   │ (same view-root DOM         │     (desktop reuses the same)
 *   │ persistence as desktop)     │
 *   │                             │
 *   ├─────────────────────────────┤
 *   │ ⌂ Rooms │🔧 │ 📊 │ ⋯ More   │  ← evcc-mobile-nav (bottom)
 *   └─────────────────────────────┘
 *
 * Tab split:
 *   Primary (always visible at the bottom):
 *     Rooms, Upkeep (Maintenance), Dock (Base Station), Stats (Metrics)
 *   Overflow (in the "More" sheet):
 *     Learning Review, Room Rules, Theme, Map Config, Map Bounds, Setup
 *
 * The split reflects everyday use: Rooms is the daily flow; Upkeep,
 * Dock, and Stats are the next-most-frequent. The rest are config
 * surfaces touched rarely.
 */

import { VIEWS, isViewAvailable } from "../render-cycle.js";

/* =========================================================
   TAB CONFIGURATION
   ========================================================= */

const PRIMARY_MOBILE_TABS = [
  { id: VIEWS.ROOMS,        labelKey: "mobile.tab_rooms",  icon: _iconRooms()  },
  { id: VIEWS.MAINTENANCE,  labelKey: "mobile.tab_upkeep", icon: _iconWrench() },
  { id: VIEWS.BASE_STATION, labelKey: "mobile.tab_dock",   icon: _iconHome()   },
  { id: VIEWS.METRICS,      labelKey: "mobile.tab_stats",  icon: _iconChart()  },
];

/**
 * Overflow tabs on mobile. Theme is included for PICKING only — the
 * Theme tab renders just its preset grid (filter / mode / tags) at phone
 * widths; the Palette and Tokens EDITORS stay desktop-only (they need too
 * many panels visible at once). So on mobile you can browse, activate, and
 * device-pin themes, but fine token editing happens on desktop.
 */
const OVERFLOW_MOBILE_TABS = [
  { id: VIEWS.LEARNING_REVIEW, labelKey: "mobile.tab_learning_review" },
  { id: VIEWS.ROOM_RULES,      labelKey: "mobile.tab_room_rules"      },
  { id: VIEWS.THEME,           labelKey: "mobile.tab_theme"           },
  { id: VIEWS.MAP_CONFIG,      labelKey: "mobile.tab_map_config"      },
  { id: VIEWS.MAPPING_REVIEW,  labelKey: "mobile.tab_map_bounds"      },
  { id: VIEWS.SETUP,           labelKey: "mobile.tab_setup"           },
];

/* =========================================================
   STATUS DOT (shared visual with desktop)
   ========================================================= */

function _statusDotClass(status) {
  return {
    cleaning:  "cleaning",
    docked:    "docked",
    returning: "returning",
    error:     "error",
    paused:    "paused",
  }[status] || "";
}

// Defensive title-case fallback used only before the dashboard
// snapshot has populated the backend-provided label. Once it has,
// the renderer uses ctx.vacuumStatusLabel / ctx.dockStatusLabel
// directly — adapter vocabulary stays server-side.
function _fallbackTitleCase(raw) {
  return String(raw ?? "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\w\S*/g, (word) =>
      word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
    );
}

function _dockDotClass(dockStatus) {
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
   PUBLIC API — applied to VacuumCardRenderers.prototype
   ========================================================= */

export function applyMobileShellRenderer(proto) {

  /**
   * Compact header for mobile: vacuum name on one line, status +
   * battery on the second. No nav tabs here — those live at the
   * bottom on mobile.
   */
  proto.renderMobileHeader = function (ctx) {
    const { vacuumName, vacuumStatus, vacuumStatusLabel,
            dockStatus, dockStatusLabel, battery } = ctx;
    const batteryText = battery != null ? `${battery}%` : "";
    const vacuumText = vacuumStatusLabel ?? _fallbackTitleCase(vacuumStatus);
    const dockText = dockStatusLabel
      ?? (dockStatus ? _fallbackTitleCase(dockStatus) : "");

    return `
      <div class="evcc-mobile-header">
        <div class="evcc-mobile-vacuum-name">
          ${this.escapeHtml(vacuumName)}
        </div>
        <div class="evcc-mobile-vacuum-status">
          <span class="evcc-status-dot ${_statusDotClass(vacuumStatus)}"></span>
          <span class="evcc-mobile-vacuum-status-label">
            <span class="evcc-status-prefix">${this.t("mobile.vacuum_status_label")}</span>
            ${this.escapeHtml(vacuumText)}
          </span>
          ${batteryText
            ? `<span class="evcc-mobile-battery">${this.escapeHtml(batteryText)}</span>`
            : ""}
        </div>
        ${dockText ? `
          <div class="evcc-mobile-vacuum-status evcc-mobile-dock-status">
            <span class="evcc-status-dot ${_dockDotClass(dockStatus)}"></span>
            <span class="evcc-mobile-vacuum-status-label">
              <span class="evcc-status-prefix">${this.t("mobile.dock_status_label")}</span>
              ${this.escapeHtml(dockText)}
            </span>
          </div>
        ` : ""}
      </div>
    `;
  };

  /**
   * Bottom-tab nav. Four primary tabs plus a "More" trigger for the
   * overflow sheet. Tabs are equal-width via flex:1, with icons +
   * short labels stacked vertically for thumb-friendly targets.
   */
  proto.renderMobileBottomNav = function (ctx) {
    const activeView = ctx?.view;
    const state = ctx?.state;
    // Capability-gate the primary tabs (e.g. drop "Dock"/Base Station on a
    // no-dock adapter) — same source of truth as the desktop header.
    const primaryTabs = PRIMARY_MOBILE_TABS.filter((t) => isViewAvailable(t.id, state));
    const overflowActive = OVERFLOW_MOBILE_TABS.some((t) => t.id === activeView);

    return `
      <nav class="evcc-mobile-nav" aria-label="${this.t("mobile.nav_primary_aria")}">
        ${primaryTabs.map((tab) => {
          const label = this.t(tab.labelKey);
          return `
          <button
            class="evcc-mobile-nav-tab${activeView === tab.id ? " active" : ""}"
            data-view="${tab.id}"
            aria-label="${this.escapeHtml(label)}"
            aria-current="${activeView === tab.id ? "page" : "false"}"
          >
            <span class="evcc-mobile-nav-icon">${tab.icon}</span>
            <span class="evcc-mobile-nav-label">${this.escapeHtml(label)}</span>
          </button>
        `;
        }).join("")}
        <button
          class="evcc-mobile-nav-tab evcc-mobile-nav-tab--more${overflowActive ? " active" : ""}"
          data-action="mobile-more-toggle"
          aria-label="${this.t("mobile.more")}"
          aria-haspopup="menu"
        >
          <span class="evcc-mobile-nav-icon">${_iconMore()}</span>
          <span class="evcc-mobile-nav-label">${this.t("mobile.more")}</span>
        </button>
      </nav>
    `;
  };

  /**
   * Overflow sheet — rendered when card._mobileMoreOpen is true. List
   * of every non-primary tab. Tap selects a view and closes the
   * sheet; backdrop tap closes without selecting.
   */
  proto.renderMobileOverlay = function (ctx) {
    if (!ctx.card?._mobileMoreOpen) return "";
    const activeView = ctx.view;
    // Capability-gate the overflow tabs (e.g. drop "Map Bounds" on a no-CV
    // adapter) — same source of truth as the desktop header.
    const overflowTabs = OVERFLOW_MOBILE_TABS.filter((t) => isViewAvailable(t.id, ctx.state));

    return `
      <div class="evcc-mobile-more-backdrop"
           data-action="mobile-more-close"
           aria-hidden="true"></div>
      <div class="evcc-mobile-more-sheet"
           role="menu"
           aria-label="${this.t("mobile.more_sheet_aria")}">
        <div class="evcc-mobile-more-handle"></div>
        ${overflowTabs.map((tab) => `
          <button
            class="evcc-mobile-more-item${activeView === tab.id ? " active" : ""}"
            data-view="${tab.id}"
            data-action="mobile-more-select"
            role="menuitem"
          >
            ${this.escapeHtml(this.t(tab.labelKey))}
          </button>
        `).join("")}
      </div>
    `;
  };
}

/* =========================================================
   INLINE ICONS — single-color SVGs, inherit currentColor
   ========================================================= */

function _iconRooms() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M3 12 12 3l9 9"/>
    <path d="M5 10v10h14V10"/>
  </svg>`;
}

function _iconWrench() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M14.7 6.3a4 4 0 0 0-5.4 5.4l-6.6 6.6 3 3 6.6-6.6a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.5-2.5 2-2z"/>
  </svg>`;
}

function _iconHome() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <rect x="3" y="9"  width="18" height="12" rx="1.5"/>
    <path d="M6 9V5h12v4"/>
    <line x1="9" y1="14" x2="15" y2="14"/>
  </svg>`;
}

function _iconChart() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <line x1="4" y1="20" x2="20" y2="20"/>
    <rect x="6"  y="11" width="3" height="9"/>
    <rect x="11" y="6"  width="3" height="14"/>
    <rect x="16" y="14" width="3" height="6"/>
  </svg>`;
}

function _iconMore() {
  return `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <circle cx="5"  cy="12" r="2"/>
    <circle cx="12" cy="12" r="2"/>
    <circle cx="19" cy="12" r="2"/>
  </svg>`;
}
