/**
 * ============================================================
 * RENDERERS: SHARED
 * ============================================================
 *
 * Low-level rendering utilities shared by every renderer module:
 * HTML escaping (XSS boundary), select/chip-select controls,
 * status badge, and timestamp formatter.
 *
 * Must be applied first in the renderers combiner.
 *
 * ============================================================
 */

import { translate } from "../i18n/index.js";

/**
 * Mix shared renderer utility methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applySharedRenderers(proto) {

  /* =========================================================
     SECURITY
     ========================================================= */

  /**
   * Sanitize a value before injecting it into innerHTML.
   * XSS boundary — all HA entity data and user config must pass through this.
   *
   * @param {*} value - Value to escape.
   * @returns {string} HTML-safe string.
   */
  proto.escapeHtml = function (value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  };

  /**
   * Translate a UI string key for the current user's language.
   *
   * TRUST MODEL B: `t()` HTML-escapes its result by default, because locales may
   * be community-contributed and a translated value must never reach the
   * innerHTML sink raw. The catalog (i18n/en.js) is the English source of truth;
   * other locales fall back to English, then to the key itself (a visible miss).
   * Language is read live from `hass.locale.language`. Interpolation uses
   * `{name}` placeholders; interpolated values are inserted RAW and the caller
   * escapes user data at the sink as before:
   * `this.t("rooms.exclude_room", { name: this.escapeHtml(room.name) })`.
   *
   * For the short, AUDITED set of strings that carry authored markup, use
   * `this.tRaw` (below). Prefer keeping markup in the template and keying only
   * the text run over reaching for tRaw.
   *
   * @param {string} key - dot-namespaced string key (e.g. "rooms.empty").
   * @param {Record<string, unknown>} [vars] - interpolation values (raw).
   * @returns {string} the resolved, interpolated, escaped string.
   */
  proto.t = function (key, vars) {
    return translate(this._i18nLanguage(), key, vars);
  };

  /**
   * Translate a key whose English carries AUTHORED markup (e.g. <strong>):
   * skips string-escaping so the markup survives, but STILL escapes interpolated
   * values. Reserved for the audited markup allowlist — see `proto.t`.
   *
   * @param {string} key - dot-namespaced string key.
   * @param {Record<string, unknown>} [vars] - interpolation values (raw).
   * @returns {string} the resolved string with authored markup preserved.
   */
  proto.tRaw = function (key, vars) {
    return translate(this._i18nLanguage(), key, vars, { raw: true });
  };

  /** Resolve the active UI language from hass: locale.language -> language -> en. */
  proto._i18nLanguage = function () {
    const hass = this._hass;
    return (
      (hass && hass.locale && hass.locale.language) ||
      (hass && hass.language) ||
      "en"
    );
  };

  /**
   * Format an ISO timestamp (or anything Date.parse can consume) as a
   * short "ago" string. Returns null when the input is missing or
   * unparseable so callers can hide the pill entirely.
   *
   * Buckets: "<1m", "Nm", "Nh", "today", "yesterday", "Nd", "Nw", "Nmo".
   *
   * @param {string|number|null|undefined} value
   * @returns {string|null}
   */
  proto.formatRelativeAgo = function (value) {
    if (value == null || value === "") return null;
    const t = Date.parse(String(value));
    if (!Number.isFinite(t)) return null;
    const diffMs = Date.now() - t;
    if (diffMs < 0) return null;
    const minutes = diffMs / 60000;
    if (minutes < 1) return "just now";
    if (minutes < 60) return `${Math.round(minutes)}m ago`;
    const hours = minutes / 60;
    if (hours < 24) return `${Math.round(hours)}h ago`;
    const days = hours / 24;
    if (days < 1.5) return "yesterday";
    if (days < 7) return `${Math.round(days)}d ago`;
    if (days < 30) return `${Math.round(days / 7)}w ago`;
    if (days < 365) return `${Math.round(days / 30)}mo ago`;
    return `${Math.round(days / 365)}y ago`;
  };

  /* =========================================================
     GENERIC CONTROLS
     ========================================================= */

  /**
   * Render a labelled `<select>` element.
   *
   * @param {string} label - Field label text.
   * @param {string} className - CSS class on the `<select>`.
   * @param {Array<string|{value:*,label:string}>} options - Option list.
   * @param {*} selected - Currently selected value.
   * @param {boolean} [disabled=false] - Whether the select is disabled.
   * @returns {string} HTML string.
   */
  proto.renderSelect = function (label, className, options, selected, disabled = false) {
    const safeOptions = Array.isArray(options) ? options : [];

    return `
      <label class="evcc-field">
        <span class="evcc-field-label">${this.escapeHtml(label)}</span>
        <select class="${this.escapeHtml(className)}" ${disabled ? "disabled" : ""}>
          ${safeOptions.map((opt) => {
            const value = typeof opt === "object" ? opt.value : opt;
            const text  = typeof opt === "object" ? opt.label : opt;
            const sel   = String(value) === String(selected) ? "selected" : "";
            return `<option value="${this.escapeHtml(String(value ?? ""))}" ${sel}>
                      ${this.escapeHtml(String(text ?? ""))}
                    </option>`;
          }).join("")}
        </select>
      </label>
    `;
  };

  /**
   * Render a row of selectable chip buttons (fan speed, water level, etc.).
   *
   * @param {string} label - Group label, or empty string to omit.
   * @param {string} className - CSS class on the chip-select wrapper.
   * @param {Array<string|{value:*,label:string}>} options - Option list.
   * @param {*} selected - Currently selected value.
   * @param {boolean} [disabled=false] - Whether all chips are disabled.
   * @returns {string} HTML string.
   */
  proto.renderChipSelect = function (label, className, options, selected, disabled = false) {
    const safeOptions = Array.isArray(options) ? options : [];

    return `
      <div class="evcc-chip-select ${this.escapeHtml(className)}">
        ${label ? `<div class="evcc-field-label">${this.escapeHtml(label)}</div>` : ""}
        <div class="evcc-chips" role="listbox">
          ${safeOptions.map((opt) => {
            const value    = typeof opt === "object" ? opt.value : opt;
            const text     = typeof opt === "object" ? opt.label : opt;
            const isActive = String(value) === String(selected);
            return `<button
                      type="button"
                      class="evcc-chip ${isActive ? "active" : ""}"
                      data-value="${this.escapeHtml(String(value ?? ""))}"
                      ${disabled ? "disabled" : ""}
                    >${this.escapeHtml(String(text ?? ""))}</button>`;
          }).join("")}
        </div>
      </div>
    `;
  };

  /**
   * Render a small coloured status badge (e.g. "Docked", "Cleaning", "Error").
   *
   * @param {string} text - Badge label.
   * @param {string} [modifier=""] - BEM modifier class for colour variant.
   * @returns {string} HTML string.
   */
  proto.renderStatusBadge = function (text, modifier = "") {
    return `
      <span class="evcc-status-badge ${this.escapeHtml(modifier)}">
        ${this.escapeHtml(text)}
      </span>
    `;
  };

  /**
   * Parse a backend UTC ISO timestamp and format it in the user's local timezone.
   *
   * @param {string|null|undefined} value - ISO 8601 timestamp string.
   * @param {Intl.DateTimeFormatOptions} [options={}] - Locale format options.
   * @param {string} [invalidFallback=""] - Return value when `value` is absent or invalid.
   * @returns {string} Formatted date string, or `invalidFallback`.
   */
  proto.formatTimestamp = function (value, options = {}, invalidFallback = "") {
    if (!value) return invalidFallback;

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return invalidFallback;

    return date.toLocaleString([], options);
  };
}
