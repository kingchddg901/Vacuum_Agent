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
// Bundled locales — AI-generated DRAFTS pending native review (each file's header
// notes this). Auto-activate by hass.locale.language; English fills any gap.
// Russian is the pilot (a Russian-speaking user reviews it live).
import { ru } from "./ru.js";
import { de } from "./de.js";
import { fr } from "./fr.js";
import { es } from "./es.js";
import { nl } from "./nl.js";
import { it } from "./it.js";
import { pt } from "./pt.js";

/**
 * lang code -> { key: string | PluralForms }. English is always present as the
 * base. A value is a plain string, or — for a count-driven key — an object of
 * CLDR plural forms (e.g. { one, other }); see translate/pluralForm.
 */
const CATALOGS = { en, ru, de, fr, es, nl, it, pt };

/**
 * Register (or replace) a locale catalog at runtime. Most locales will instead
 * be imported + added to CATALOGS above so they ship in the bundle; this exists
 * for lazy/optional locales and tests.
 *
 * @param {string} lang - BCP-47 language code (e.g. "ru", "de", "pt-BR").
 * @param {Record<string, string | Record<string, string>>} catalog - key ->
 *   translated string, or for a plural key an object of CLDR forms.
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

// --- Plurals -------------------------------------------------------------
// A plural key's catalog value is an OBJECT keyed by CLDR plural category
// ("zero"|"one"|"two"|"few"|"many"|"other"). The right form is chosen from
// `vars.count` using the language's native plural rules. English ships
// one/other; a locale ships whatever its language needs (e.g. Russian
// one/few/many/other) — no per-language logic lives here, Intl.PluralRules
// owns the CLDR rules for every language.

/** Intl.PluralRules instances are reused per language (construction is costly). */
const PLURAL_RULES = new Map();
function pluralRules(lang) {
  let r = PLURAL_RULES.get(lang);
  if (r === undefined) {
    try {
      r = new Intl.PluralRules(lang);
    } catch {
      r = null; // unknown code / ancient engine — fall back to one-vs-other below
    }
    PLURAL_RULES.set(lang, r);
  }
  return r;
}

/**
 * Select a plural form from an object entry for `vars.count`.
 * Within the entry: chosen CLDR category -> `other` -> `one`. Returns undefined
 * when the entry carries none of those, so the caller can fall back to English.
 */
function pluralForm(lang, entry, vars) {
  const n = Number(vars && vars.count);
  let cat = "other";
  if (Number.isFinite(n)) {
    const rules = pluralRules(lang);
    cat = rules ? rules.select(n) : n === 1 ? "one" : "other";
  }
  if (entry[cat] != null) return entry[cat];
  if (entry.other != null) return entry.other;
  if (entry.one != null) return entry.one;
  return undefined;
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
 * PLURALS: a key whose value is an OBJECT is plural — the form is chosen from
 * `vars.count` via the language's CLDR rules (see pluralForm). A locale that
 * omits a category falls back through its own `other` to the English object,
 * so a partial locale still renders. Escaping/interpolation are identical for
 * the selected form — trust model B is unchanged for plurals.
 *
 * @param {string} lang - language code; unknown codes fall back to English.
 * @param {string} key - dot-namespaced string key (e.g. "rooms.empty").
 * @param {Record<string, unknown>} [vars] - interpolation values for `{name}`,
 *   already escaped by the caller where they carry user data. Plural keys read
 *   `vars.count` to choose the form.
 * @param {{ raw?: boolean }} [options] - raw:true preserves authored markup.
 * @returns {string} the resolved, interpolated string.
 */
export function translate(lang, key, vars, options) {
  const base = CATALOGS.en || {};
  const code = String(lang || "en");
  const loc = CATALOGS[code] || CATALOGS[code.split("-")[0]] || base;

  let entry = loc[key];
  if (entry == null) entry = base[key];

  let s;
  if (entry == null) {
    s = key; // visible miss: render the key, never a blank
  } else if (typeof entry === "object") {
    // Plural: pick the form for vars.count. If the resolved entry (a partial
    // locale) lacks the category and any fallback form, drop to the English
    // object; if even that is absent, fall back to the key.
    s = pluralForm(code, entry, vars);
    if (s == null && typeof base[key] === "object" && base[key] !== entry) {
      s = pluralForm(code, base[key], vars);
    }
    if (s == null) s = key;
  } else {
    s = entry;
  }

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

/**
 * Resolve the active UI language from hass + card config — the SINGLE resolver
 * the card (main.js), the renderers (shared.js), and the standalone room-card
 * all share (they each used to inline this).
 *
 * Order: an explicit `config.i18n.locale` pins the language (unless it is
 * "auto") -> `hass.locale.language` -> `hass.language` -> "en". The pin lets a
 * dashboard force a locale regardless of the HA UI language; "auto" defers to HA.
 *
 * @param {object} [hass] - Home Assistant connection (reads locale.language / language).
 * @param {object} [config] - card config; reads `config.i18n.locale`.
 * @returns {string} a BCP-47 code (translate() falls back to English for unknowns).
 */
export function resolveLang(hass, config) {
  const pinned = config && config.i18n && config.i18n.locale;
  if (pinned && pinned !== "auto") return String(pinned);
  return (
    (hass && hass.locale && hass.locale.language) ||
    (hass && hass.language) ||
    "en"
  );
}

/** Extract the `{placeholder}` token set from a string or a plural-form object. */
function placeholderSet(value) {
  const set = new Set();
  const scan = (s) => {
    for (const m of String(s).matchAll(/\{(\w+)\}/g)) set.add(m[1]);
  };
  if (typeof value === "string") scan(value);
  else if (value && typeof value === "object") {
    for (const k of Object.keys(value)) if (typeof value[k] === "string") scan(value[k]);
  }
  return set;
}

// Keys that must never be copied into a catalog object — a JSON locale could
// carry an own "__proto__" (JSON.parse makes it an OWN property) and assigning
// it would pollute the prototype.
const UNSAFE_KEYS = new Set(["__proto__", "constructor", "prototype"]);

/**
 * Validate an UNTRUSTED locale catalog against the English base before it is
 * registered — the gate for community/user-supplied locale files (which ride
 * the same untrusted-intake path as themes/animals; see TRUST MODEL B).
 *
 * Never throws: a bad entry is dropped (recorded in `errors`) and the rest load,
 * and the returned `clean` is a SUBSET of valid keys — so English fallback is
 * always intact (translate() falls back to en for any dropped/missing key) and a
 * locale can never remove it.
 *
 * Rules:
 *  - catalog must be a plain object (else everything is dropped).
 *  - each value is a string OR a plural object whose every form is a string;
 *    anything else (number, array, null, nested object, empty object) is dropped.
 *  - unsafe keys (__proto__/constructor/prototype) are dropped (no pollution).
 *  - placeholder parity vs English (UNION across plural forms): a MISSING
 *    placeholder is an error (the key is dropped — a lost {name} would render
 *    wrong); an EXTRA placeholder is a warning (it renders literally, harmless).
 *  - a key not present in English is kept but warned (dead until en adds it).
 *  - PLURAL detection is by typeof===object, NOT a source comment — `// plural`
 *    is stripped at build, and a deliberate plural-but-string key
 *    (mapping_review.badge_runs_samples) must validate as the string it is.
 *
 * @param {Record<string, unknown>} catalog - the parsed locale to validate.
 * @param {Record<string, unknown>} [base] - the English base (default CATALOGS.en).
 * @returns {{ clean: Record<string, string|object>, warnings: string[], errors: string[] }}
 */
export function validateLocale(catalog, base = CATALOGS.en) {
  const warnings = [];
  const errors = [];
  const clean = {};
  if (!catalog || typeof catalog !== "object" || Array.isArray(catalog)) {
    errors.push("locale is not a plain object — ignored entirely");
    return { clean, warnings, errors };
  }
  const baseMap = base || {};
  for (const key of Object.keys(catalog)) {
    if (UNSAFE_KEYS.has(key)) {
      errors.push(`"${key}": unsafe key dropped`);
      continue;
    }
    const value = catalog[key];
    const isString = typeof value === "string";
    const isObject = value != null && typeof value === "object" && !Array.isArray(value);
    if (!isString && !isObject) {
      errors.push(`"${key}": value must be a string or plural object — dropped`);
      continue;
    }
    if (isObject) {
      const forms = Object.keys(value);
      const badForm = forms.find((f) => typeof value[f] !== "string");
      if (forms.length === 0 || badForm !== undefined) {
        errors.push(`"${key}": plural forms must each be a string — dropped`);
        continue;
      }
    }
    if (!Object.prototype.hasOwnProperty.call(baseMap, key)) {
      warnings.push(`"${key}": not in English base (extra key)`);
    } else {
      const want = placeholderSet(baseMap[key]);
      const got = placeholderSet(value);
      const missing = [...want].filter((p) => !got.has(p));
      const extra = [...got].filter((p) => !want.has(p));
      if (missing.length) {
        errors.push(`"${key}": missing placeholder(s) {${missing.join("}, {")}} — dropped`);
        continue;
      }
      if (extra.length) {
        warnings.push(`"${key}": extra placeholder(s) {${extra.join("}, {")}}`);
      }
    }
    clean[key] = value;
  }
  return { clean, warnings, errors };
}

/**
 * Resolve which external locale file to load from the card's `config.i18n`, for
 * a resolved language. Two shapes (from the design doc):
 *   i18n: { locale: "de", url: "/local/vacuum-agent/i18n/de.json" }
 *   i18n: { locale: "auto", url_map: { de: "…/de.json", ru: "…/ru.json" } }
 * `url` wins if present; otherwise `url_map[lang]` then `url_map[<base lang>]`.
 *
 * @param {object} [config] - the card config.
 * @param {string} lang - the resolved language (see resolveLang).
 * @returns {{ lang: string, url: string, key: string } | null} source + a
 *   (lang|url) identity key for one-shot loading, or null when none applies.
 */
export function localeSource(config, lang) {
  const i18n = config && config.i18n;
  if (!i18n || typeof i18n !== "object") return null;
  const code = String(lang || "");
  const baseLang = code.split("-")[0];
  let url = null;
  if (typeof i18n.url === "string" && i18n.url) {
    url = i18n.url;
  } else if (i18n.url_map && typeof i18n.url_map === "object") {
    url = i18n.url_map[code] || i18n.url_map[baseLang] || null;
  }
  if (!url || typeof url !== "string") return null;
  return { lang: code, url, key: `${code}|${url}` };
}

/**
 * Fetch + validate + register an external locale JSON file. Async; NEVER throws
 * — every failure (network, !ok, non-JSON, bad shape) resolves to a report with
 * `ok:false` so the caller keeps rendering English. On success the VALIDATED
 * subset (validateLocale) is registered under `lang`; dropped/extra keys are
 * reported. The fetch is JSON-only (no eval/import), so a hostile file can at
 * worst contribute escaped strings (TRUST MODEL B) or be rejected outright.
 *
 * @param {string} url - same-origin locale JSON url (caller vets the origin).
 * @param {string} lang - language code to register the catalog under.
 * @param {{ fetchImpl?: typeof fetch }} [opts] - injectable fetch (for tests).
 * @returns {Promise<{ ok: boolean, lang: string, url: string, loaded: number, warnings: string[], errors: string[] }>}
 */
export async function loadLocale(url, lang, opts = {}) {
  const report = { ok: false, lang, url, loaded: 0, warnings: [], errors: [] };
  const doFetch = opts.fetchImpl || (typeof fetch === "function" ? fetch : null);
  if (!doFetch) { report.errors.push("no fetch available"); return report; }
  try {
    const resp = await doFetch(url, { credentials: "same-origin" });
    if (!resp || !resp.ok) {
      report.errors.push(`fetch failed (status ${resp ? resp.status : "none"})`);
      return report;
    }
    const data = await resp.json();
    const { clean, warnings, errors } = validateLocale(data);
    report.warnings = warnings;
    report.errors = errors;
    registerLocale(lang, clean);
    report.loaded = Object.keys(clean).length;
    report.ok = true;
  } catch (e) {
    report.errors.push(`load error: ${String((e && e.message) || e)}`);
  }
  return report;
}
