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
