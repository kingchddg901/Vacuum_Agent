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

import { translate, resolveLang } from "../i18n/index.js";

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
   * `this.t("rooms.exclude_room_aria", { name: this.escapeHtml(room.name) })`.
   *
   * For the short, AUDITED set of strings that carry authored markup, use
   * `this.tRaw` (below). Prefer keeping markup in the template and keying only
   * the text run over reaching for tRaw.
   *
   * @param {string} key - dot-namespaced string key (e.g. "rooms.empty").
   * @param {Record<string, unknown>} [vars] - interpolation values (raw).
   * @returns {string} the resolved, interpolated, escaped string.
   */
  // anchor: RNZQ33ZP  the ESCAPED/RAW translator pairing -- the replica set. t/tRaw and
  // tVocab/tVocabRaw are two copies of one contract: the Raw half returns unescaped for
  // call sites the renderer escapes again later. Change the escaping on one pair and not
  // the other and a translated "l'eau" either double-escapes or reaches innerHTML raw.
  proto.t = function (key, vars) {
    return translate(this._i18nLanguage(), key, vars);
  };

  /**
   * Translate a key whose English carries AUTHORED markup (e.g. <strong>):
   * skips escaping of the CATALOG STRING so that markup survives. Reserved for
   * the audited markup allowlist — see `proto.t`.
   *
   * INTERPOLATED VALUES ARE INSERTED RAW — exactly as in `t()`. This docstring
   * used to claim tRaw "STILL escapes interpolated values"; it never has
   * (i18n/index.js: the `raw` option skips `esc(s)` on the catalog string, and
   * the `{name}` substitution below it is unconditional). live:I18N-1.
   *
   * THE CALLER ESCAPES AT THE SINK, for both functions. Every tRaw call site
   * today does — the bind_setup.* handlers pass err.message into a sink that
   * escapes, and the block-reason sinks escapeHtml their result — so this was a
   * documentation defect, not a live hole. The reason it still mattered: a
   * future caller who trusted the old sentence and therefore skipped escaping
   * at a NEW sink would open one, with the docstring reading as justification.
   *
   * Pinned by renderers/i18n-escaping-contract.test.mjs so the two cannot
   * disagree again.
   *
   * @param {string} key - dot-namespaced string key.
   * @param {Record<string, unknown>} [vars] - interpolation values, inserted RAW.
   * @returns {string} the resolved string with authored markup preserved; the
   *   CALLER must escape it (and any interpolated user data) at the sink.
   */
  proto.tRaw = function (key, vars) {
    return translate(this._i18nLanguage(), key, vars, { raw: true });
  };

  /**
   * Translate a backend/adapter VOCABULARY value (a fan-speed, clean-mode,
   * status, scope, floor type, …) that the integration hands us as an English
   * label. The card holds the stable `value`; we key the translation on it
   * (`vocab.<field>.<value>`, value normalized to a key-safe slug) and FALL BACK
   * to the backend label for any value we haven't keyed — so a different brand /
   * model / a new value renders its English label unchanged (no regression),
   * never a raw key. Returns an HTML-escaped string (like escapeHtml(label) did).
   *
   * @param {string} field - vocabulary field, e.g. "fan_speed", "clean_mode".
   * @param {string} value - the stable value, e.g. "max", "vacuum_mop".
   * @param {string} [fallback] - the backend English label (used when unkeyed).
   * @returns {string} escaped, localized label.
   */
  proto.tVocab = function (field, value, fallback) {
    if (value == null || value === "") return this.escapeHtml(fallback ?? "");
    const slug = String(value).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
    // The template literal lives INSIDE the t() call so check:i18n's template
    // scan reaches every `vocab.<field>.<value>` key (a dynamic this.t(varKey)
    // would read as a dead key). t() escapes its result and returns the key
    // verbatim on a miss -> fall back to the backend label.
    const out = this.t(`vocab.${field}.${slug}`);
    return out === `vocab.${field}.${slug}` ? this.escapeHtml(fallback ?? String(value)) : out;
  };

  /**
    * REPLICA RNZQ33ZP -- primary: the t/tRaw pair above.
   * Like `tVocab`, but returns the RAW (unescaped) localized label — for the few
   * call sites that drop the value into a data object the renderer escapes again
   * later (e.g. room-estimate's summary rows do `escapeHtml(row.value)`). Using
   * `tVocab` there would double-escape, so a translated "l'eau"/"A & B" would
   * render its entities literally. The CALLER must escape (these do). Mirrors the
   * `tRaw`↔`t` pairing; uses the same inline `vocab.<field>.<slug>` template so
   * check:i18n still reaches every vocab key.
   *
   * @param {string} field
   * @param {string} value
   * @param {string} [fallback]
   * @returns {string} unescaped, localized label (caller escapes).
   */
  proto.tVocabRaw = function (field, value, fallback) {
    if (value == null || value === "") return fallback ?? "";
    const slug = String(value).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
    const out = this.tRaw(`vocab.${field}.${slug}`);
    return out === `vocab.${field}.${slug}` ? (fallback ?? String(value)) : out;
  };

  /**
   * Resolve the active UI language from hass: locale.language -> language -> en.
   *
   * Read hass off `this.card` — these methods run on the VacuumCardRenderers
   * INSTANCE (render-cycle.js calls `renderers.t(...)`), and only `this.card`
   * is set on it (the constructor); `this._hass` is undefined here, so reading
   * it pinned EVERY renderer string to English regardless of the user's HA
   * language. (`this._hass ||` is kept first as a defensive no-op for any path
   * where `this` is the card itself.) Mirrors the `this.card._hass` reach the
   * other renderers already use (e.g. setup.js).
   */
  proto._i18nLanguage = function () {
    // hass + config live on the card the renderers are bound to: render-cycle
    // calls renderers.t on the INSTANCE, where only this.card is set (this._hass
    // is undefined here — the bug that pinned everything to English). Falls back
    // to `this` for any path where the proto is mixed onto the card itself.
    const c = this.card || this;
    return resolveLang(c._hass, c._config, c._langOverride);
  };

  /**
   * Format an ISO timestamp (or anything Date.parse can consume) as a
   * short "ago" string. Returns null when the input is missing or
   * unparseable so callers can hide the pill entirely.
   *
   * Buckets: just now / {n}m / {n}h / yesterday / {n}d / {n}w / {n}mo / {n}y ago.
   * Strings come from the i18n `relative.*` catalog, so the pill localizes with
   * the user's HA language (the buckets/thresholds stay fixed). The local parsed
   * timestamp is `ts` (renamed from `t`) to keep it distinct from `this.t`.
   *
   * @param {string|number|null|undefined} value
   * @returns {string|null}
   */
  proto.formatRelativeAgo = function (value) {
    if (value == null || value === "") return null;
    const ts = Date.parse(String(value));
    if (!Number.isFinite(ts)) return null;
    const diffMs = Date.now() - ts;
    if (diffMs < 0) return null;
    const minutes = diffMs / 60000;
    if (minutes < 1) return this.t("relative.just_now");
    if (minutes < 60) return this.t("relative.minutes_ago", { count: Math.round(minutes) });
    const hours = minutes / 60;
    if (hours < 24) return this.t("relative.hours_ago", { count: Math.round(hours) });
    const days = hours / 24;
    if (days < 1.5) return this.t("relative.yesterday");
    if (days < 7) return this.t("relative.days_ago", { count: Math.round(days) });
    if (days < 30) return this.t("relative.weeks_ago", { count: Math.round(days / 7) });
    if (days < 365) return this.t("relative.months_ago", { count: Math.round(days / 30) });
    return this.t("relative.years_ago", { count: Math.round(days / 365) });
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
   * Parse a backend UTC ISO timestamp and format it for DISPLAY, in the user's
   * local timezone and in the CARD'S language.
   *
   * The locale argument used to be `[]`, which means the BROWSER/OS locale — not
   * Home Assistant's language and not the card's. Every other string on a card
   * pinned to Arabic (globe override, or `config.i18n.locale`) came out Arabic
   * while the dates stayed in whatever the browser happened to be set to. The
   * language now comes from `_i18nLanguage()`, the same resolver behind `t()`, so
   * timestamps move with the rest of the card. The old first line of this
   * docstring said only "in the user's local timezone" — the timezone was never
   * the question, and naming only it is why `[]` read as intentional.
   *
   * DISPLAY ONLY — never route an IDENTIFIER through here. A job record is stored
   * as `<job_id>.json` where the id is built from local wall-clock time
   * (`jobs/active_job.py::_generate_job_id` -> `job_2026-08-05T02-52-05`), and
   * the user pastes that string straight back into `exclude_learning_job` /
   * `restore_learning_job` (docs/advanced/03-services.md). Localizing it reorders
   * the fields, translates the month, and under a locale with a non-Latin
   * numbering system (`ar-EG`: "٤ أغسطس، ٧:٥٢ م") renumbers the digits — the
   * displayed id stops matching the filename and the job cannot be found. The two
   * surfaces that show an id (renderers/review.js `evcc-review-job-title`,
   * renderers/job-summary.js `evcc-job-summary-subtitle`) print `job.job_id`
   * VERBATIM and deliberately do not call this function; keep it that way.
   *
   * The tag is USER-SUPPLIED — `config.i18n.locale` is hand-written YAML — and
   * `toLocaleString` throws RangeError on a structurally invalid one (`pt_BR`
   * with an underscore is enough; an unknown-but-well-formed tag just falls back
   * inside ICU). Renderers assemble one HTML string, so that throw would escape
   * and blank the whole card over a typo. Only RangeError is absorbed: anything
   * else is our bug, not their config, and must not be swallowed here.
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

    // Stringify FIRST, default after — same trap as maintenance.js:1048.
    const lang = String(this._i18nLanguage?.() ?? "");
    try {
      return date.toLocaleString(lang || [], options);
    } catch (err) {
      if (!(err instanceof RangeError)) throw err;
      return date.toLocaleString([], options);
    }
  };
}
