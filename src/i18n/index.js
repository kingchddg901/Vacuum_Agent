/**
 * ============================================================
 * I18N — runtime UI-string translation
 * ============================================================
 *
 * The card's interface text is authored in English directly in the renderer
 * and binding modules. Home Assistant localizes config flows and entity names
 * for an integration, but it gives a custom Lovelace card NOTHING for its own
 * markup — every literal in the renderers is English regardless of the user's
 * HA language. This module is the seam that closes that gap.
 *
 * Usage (from a renderer/binding mixed onto the card prototype):
 *
 *     `${this.t("rooms.empty")}`
 *     `${this.t("rooms.n_selected", { count: n })}`
 *
 * `this.t` is defined in renderers/shared.js; it resolves the user's language
 * from `hass.locale.language` on every call and delegates to `translate`.
 *
 * Resolution order: exact locale -> base language (e.g. "pt-BR" -> "pt") ->
 * English base -> the key itself. The key fallback means an untranslated or
 * mistyped string is VISIBLE in dev (you see "rooms.empty"), never a blank.
 *
 * Locales are plain key->string maps. English (`en.js`) is the source of truth
 * and always ships in the bundle; additional locales are imported here (or
 * registered via `registerLocale`) and can be contributed incrementally — a
 * translation is data, not code.
 *
 * ============================================================
 */

import { en } from "./en.js";

/** lang code -> { key: string }. English is always present as the base. */
const CATALOGS = { en };

/**
 * Register (or replace) a locale catalog at runtime. Most locales will instead
 * be imported + added to CATALOGS above so they ship in the bundle; this exists
 * for lazy/optional locales and tests.
 *
 * @param {string} lang - BCP-47 language code (e.g. "ru", "de", "pt-BR").
 * @param {Record<string, string>} catalog - key -> translated string.
 */
export function registerLocale(lang, catalog) {
  if (lang && catalog && typeof catalog === "object") {
    CATALOGS[String(lang)] = catalog;
  }
}

const HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

/** HTML-escape a value before it is injected into innerHTML. */
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);
}

/**
 * Translate a key for a language, with base-language + English + key fallback,
 * `{name}` interpolation, and HTML escaping (TRUST MODEL B).
 *
 * Trust model: locales may be community-contributed (mirroring the theme/animal
 * intake path), so the CATALOG STRING is HTML-escaped by DEFAULT — a contributed
 * value carrying markup must never reach the innerHTML sink raw. `options.raw`
 * opts a string OUT of that escaping, for the short audited set of first-party
 * AUTHORED markup strings (exposed as `this.tRaw`).
 *
 * Interpolated VALUES are NOT escaped here — they are inserted raw and the
 * caller escapes user/cloud data at the sink exactly as the original literal
 * did: `this.t("rooms.exclude_room", { name: this.escapeHtml(room.name) })`.
 * The var XSS boundary is unchanged; only the translation string gained
 * escaping.
 *
 * @param {string} lang - language code; unknown codes fall back to English.
 * @param {string} key - dot-namespaced string key (e.g. "rooms.empty").
 * @param {Record<string, unknown>} [vars] - interpolation values for `{name}`,
 *   already escaped by the caller where they carry user data.
 * @param {{ raw?: boolean }} [options] - raw:true preserves authored markup.
 * @returns {string} the resolved, interpolated string.
 */
export function translate(lang, key, vars, options) {
  const base = CATALOGS.en || {};
  const code = String(lang || "en");
  const loc = CATALOGS[code] || CATALOGS[code.split("-")[0]] || base;

  let s = loc[key];
  if (s == null) s = base[key];
  if (s == null) s = key; // visible miss: render the key, never a blank

  // Escape the catalog string (skipped for tRaw): neutralizes markup in a
  // community-contributed locale value before it can reach the innerHTML sink.
  if (!(options && options.raw)) s = esc(s);

  // Vars are inserted RAW — the caller escapes user data at the sink (unchanged).
  if (vars) {
    s = s.replace(/\{(\w+)\}/g, (match, name) =>
      Object.prototype.hasOwnProperty.call(vars, name) ? String(vars[name]) : match,
    );
  }
  return s;
}
