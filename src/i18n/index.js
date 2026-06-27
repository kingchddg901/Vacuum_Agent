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
import { flattenLocale } from "./flatten.js";

// English is the ONLY catalog bundled into the card — it is the manifest (the
// complete key set) and the universal fallback. The other locales (de/fr/es/nl/
// it/pt/ru) were RIPPED OUT of the minified bundle: they ship as nested JSON
// served assets (custom_components/eufy_vacuum/frontend/locales/<code>.json) and
// load + flatten at runtime (see loadLocale / loadDroppedLocales, and main.js's
// _maybeLoadBundledLocales). Their METADATA (status/endonym/draft-word below)
// stays bundled so the picker + draft-gate work before the catalogs arrive.

/**
 * lang code -> { key: string | PluralForms }. English is always present as the
 * base. A value is a plain string, or — for a count-driven key — an object of
 * CLDR plural forms (e.g. { one, other }); see translate/pluralForm. Non-English
 * catalogs are registered at runtime (registerLocale) once their JSON loads.
 */
const CATALOGS = { en };

/**
 * Review status per bundled locale. A `draft` locale is AI-generated and not yet
 * native-reviewed — it must NOT auto-activate from the HA system language (it can
 * only be reached by an EXPLICIT choice: a config.i18n.locale pin or the display-
 * language override). Promote to `stable` after native review (a one-line change).
 * English is always stable. See resolveLang for the gate, and TRANSLATION_NOTES.md.
 */
const LOCALE_STATUS = {
  en: "stable",
  ru: "draft", de: "draft", fr: "draft", es: "draft", nl: "draft", it: "draft", pt: "draft",
};

// Endonyms (language's own name) + its own word for "draft" — so the override
// picker is readable even to a user currently stuck in a bad translation.
const LOCALE_ENDONYMS = {
  en: "English", ru: "Русский", de: "Deutsch", fr: "Français",
  es: "Español", nl: "Nederlands", it: "Italiano", pt: "Português",
};
const DRAFT_WORD = {
  en: "draft", ru: "черновик", de: "Entwurf", fr: "brouillon",
  es: "borrador", nl: "concept", it: "bozza", pt: "rascunho",
};

/**
 * Locales registered at RUNTIME rather than bundled — drop-in JSON files (see
 * loadDroppedLocales) and tests. Keyed by code -> { status }. Lets the picker
 * surface them and the draft-gate treat an unreviewed dropped locale ("custom")
 * exactly like a bundled draft (explicit-choice only).
 */
const DYNAMIC_LOCALES = new Map();

/** Review status ('stable' | 'draft' | 'custom' | 'unknown') for a code, base-language aware. */
export function localeStatus(lang) {
  const code = String(lang || "");
  const dyn = DYNAMIC_LOCALES.get(code);
  // A runtime drop-in ("custom") for a code WINS — it is the catalog translate()
  // actually uses (registerLocale overwrote it), so its status is authoritative.
  // This keeps the picker honest when a drop-in shadows a bundled draft.
  return (
    (dyn && dyn.status) ||
    LOCALE_STATUS[code] ||
    LOCALE_STATUS[code.split("-")[0]] ||
    "unknown"
  );
}

/**
 * An unreviewed locale that must NOT auto-activate from the system language — a
 * bundled AI "draft" OR a dropped "custom" locale. Both are reachable only by an
 * explicit pin / override / in-card pick (a deliberate choice), never implicitly.
 */
function isDraftLocale(lang) {
  const s = localeStatus(lang);
  return s === "draft" || s === "custom";
}

/**
 * The bundled locales for an override picker: each as
 * `{ code, status, endonym, label }` where `label` is the language's own name
 * plus, for drafts, its own word for "draft" (e.g. "Deutsch (Entwurf)"). English
 * first, then the rest alphabetically by endonym.
 */
export function listBundledLocales() {
  const codes = Object.keys(LOCALE_STATUS);
  return codes
    .map((code) => {
      const status = LOCALE_STATUS[code];
      const endonym = LOCALE_ENDONYMS[code] || code;
      const label = status === "draft" ? `${endonym} (${DRAFT_WORD[code] || "draft"})` : endonym;
      return { code, status, endonym, label };
    })
    .sort((a, b) =>
      a.code === "en" ? -1 : b.code === "en" ? 1 : a.endonym.localeCompare(b.endonym),
    );
}

/** The language's own name (endonym) for a code, via Intl.DisplayNames. */
function endonymFor(code) {
  try {
    const name = new Intl.DisplayNames([code], { type: "language" }).of(code);
    if (name && name !== code) return name.charAt(0).toUpperCase() + name.slice(1);
  } catch { /* unknown code / ancient engine — fall through to the code */ }
  return code;
}

/**
 * Every SELECTABLE locale for the override picker: the bundled ones plus any
 * registered at runtime (drop-in JSON files). Each `{ code, status, endonym,
 * label }`. A drop-in that SHADOWS a bundled code reports as "custom" — its
 * catalog is the one translate() uses, so the label must agree (never show a
 * stale "(draft)" for overridden strings). Bundled endonyms come from the
 * curated table; unknown (dropped) codes derive theirs from Intl.DisplayNames.
 * English first, then alphabetical by endonym.
 */
export function listLocales() {
  const codes = new Set([...Object.keys(LOCALE_STATUS), ...DYNAMIC_LOCALES.keys()]);
  return [...codes]
    .map((code) => {
      const status = localeStatus(code); // drop-in "custom" wins over bundled "draft"
      const endonym = LOCALE_ENDONYMS[code] || endonymFor(code);
      const label =
        status === "draft"
          ? `${endonym} (${DRAFT_WORD[code] || "draft"})`
          : status === "custom"
            ? `${endonym} (custom)`
            : endonym;
      return { code, status, endonym, label };
    })
    .sort((a, b) =>
      a.code === "en" ? -1 : b.code === "en" ? 1 : a.endonym.localeCompare(b.endonym),
    );
}

/**
 * Register (or replace) a locale catalog at runtime. Most locales will instead
 * be imported + added to CATALOGS above so they ship in the bundle; this exists
 * for lazy/optional locales and tests.
 *
 * @param {string} lang - BCP-47 language code (e.g. "ru", "de", "pt-BR").
 * @param {Record<string, string | Record<string, string>>} catalog - key ->
 *   translated string, or for a plural key an object of CLDR forms.
 * @param {{ status?: string }} [meta] - optional review status for a runtime
 *   locale (e.g. "custom" for a drop-in file); recorded for the picker + gate.
 */
export function registerLocale(lang, catalog, meta) {
  if (lang && catalog && typeof catalog === "object") {
    const code = String(lang);
    CATALOGS[code] = catalog;
    // A runtime-registered locale records its status (e.g. "custom" for a
    // drop-in file) so localeStatus/listLocales/the draft-gate know about it.
    if (meta && meta.status) DYNAMIC_LOCALES.set(code, { status: String(meta.status) });
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
 * Resolve the active UI language from a runtime override + hass + card config —
 * the SINGLE resolver the card (main.js), the renderers (shared.js), and the
 * standalone room-card all share (they each used to inline this).
 *
 * Order (most explicit wins):
 *   0. `override` — the in-card language control's per-user choice (lang-store.js,
 *      persisted server-side via HA user-data). The most deliberate choice of all.
 *   1. `config.i18n.locale` — a per-dashboard author pin.
 *   2. `hass.locale.language` / `hass.language` — the HA system language.
 *   3. "en".
 *
 * Both the override and the pin BYPASS the draft-gate — each is a deliberate
 * opt-in, so an unreviewed AI-draft locale is reachable that way. Only the
 * auto/system step is gated (a draft must never auto-activate from the system
 * language). The literal "auto" (or empty) at either explicit layer defers down
 * the chain, so the control can map an "Auto (system)" choice back to HA.
 *
 * @param {object} [hass] - Home Assistant connection (reads locale.language / language).
 * @param {object} [config] - card config; reads `config.i18n.locale`.
 * @param {string} [override] - per-user runtime choice (a code, "auto", or empty).
 * @returns {string} a BCP-47 code (translate() falls back to English for unknowns).
 */
export function resolveLang(hass, config, override) {
  // 0. The in-card control's per-user choice is the most explicit source and
  //    wins over everything, BYPASSING the draft-gate. "auto"/empty defers.
  if (override && override !== "auto") return String(override);
  // 1. An explicit pin wins next and also BYPASSES the draft-gate — the
  //    dashboard deliberately chose this locale (the per-dashboard override).
  const pinned = config && config.i18n && config.i18n.locale;
  if (pinned && pinned !== "auto") return String(pinned);
  // 2. Auto: the HA system language.
  const auto =
    (hass && hass.locale && hass.locale.language) ||
    (hass && hass.language) ||
    "en";
  // 3. DRAFT-GATE: an unreviewed (AI-draft) bundled locale must not auto-activate
  //    from the system language — fall back to English. A draft is only reachable
  //    by the explicit override/pin above. Stable + non-bundled locales are
  //    unaffected (non-bundled still returns its code; translate() falls back
  //    to en for it).
  if (isDraftLocale(auto)) return "en";
  return auto;
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
 * @param {{ fetchImpl?: typeof fetch, status?: string }} [opts] - injectable
 *   fetch (for tests); `status` tags a runtime locale (e.g. "custom").
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
    // Locale files are authored NESTED (commons + scoped sections); flatten
    // against the English manifest into the flat catalog validateLocale expects.
    // A flat file is the degenerate case and passes through unchanged.
    const { flat } = flattenLocale(data, CATALOGS.en);
    const { clean, warnings, errors } = validateLocale(flat);
    report.warnings = warnings;
    report.errors = errors;
    registerLocale(lang, clean, opts.status ? { status: opts.status } : undefined);
    report.loaded = Object.keys(clean).length;
    report.ok = true;
  } catch (e) {
    report.errors.push(`load error: ${String((e && e.message) || e)}`);
  }
  return report;
}

/**
 * Discover + load drop-in locale JSON files the integration serves at
 * `${baseUrl}/index.json` — an auto-generated list of "<code>.json" filenames
 * (see custom_components/eufy_vacuum/__init__.py, which regenerates it at
 * startup from config/eufy_vacuum/locales/, and the shipped set from the
 * served frontend dir). Each file is loaded via loadLocale (same-origin fetch ->
 * flatten -> validateLocale -> registerLocale). `en.json` is refused (the base).
 *
 * Status is the CALLER's choice: pass { status: "custom" } for user drop-ins (so
 * the draft-gate keeps them explicit-only); omit it for the SHIPPED locales so
 * each keeps its bundled LOCALE_STATUS (e.g. "draft").
 *
 * NEVER throws: a missing folder / index / file just yields a soft report. The
 * filename stem IS the locale code (de.json -> "de", pt-BR.json -> "pt-BR").
 *
 * @param {string} [baseUrl] - served locales dir (default /eufy_vacuum/locales).
 * @param {{ fetchImpl?: typeof fetch, status?: string }} [opts] - injectable
 *   fetch (for tests); `status` tags the loaded locales (e.g. "custom").
 * @returns {Promise<{ ok: boolean, loaded: string[], errors: string[] }>}
 */
export async function loadDroppedLocales(baseUrl = "/eufy_vacuum/locales", opts = {}) {
  const result = { ok: false, loaded: [], errors: [] };
  const doFetch = opts.fetchImpl || (typeof fetch === "function" ? fetch : null);
  if (!doFetch) { result.errors.push("no fetch available"); return result; }

  let files;
  try {
    const resp = await doFetch(`${baseUrl}/index.json`, { credentials: "same-origin" });
    if (!resp || !resp.ok) {
      result.errors.push(`index fetch failed (status ${resp ? resp.status : "none"})`);
      return result;
    }
    files = await resp.json();
  } catch (e) {
    result.errors.push(`index load error: ${String((e && e.message) || e)}`);
    return result;
  }
  if (!Array.isArray(files)) {
    result.errors.push("index is not an array");
    return result;
  }

  for (const file of files) {
    if (typeof file !== "string" || !file.endsWith(".json") || file === "index.json") continue;
    const code = file.replace(/\.json$/, "");
    if (code === "en") {
      // The English base is the universal fallback source of truth — a partial
      // or hostile en.json would break fallback for every other locale. Refuse.
      result.errors.push("en.json refused (the English base is not overridable via drop-in)");
      continue;
    }
    // Status is the CALLER's call: shipped locales (no status) keep their
    // bundled LOCALE_STATUS; user drop-ins pass { status: "custom" } to be gated.
    const report = await loadLocale(`${baseUrl}/${file}`, code, opts);
    if (report.ok) result.loaded.push(code);
    else result.errors.push(`${file}: ${report.errors.join("; ")}`);
  }
  result.ok = true;
  return result;
}

let _localesRequested = false;

/**
 * Load the runtime locale catalogs (the SHIPPED non-English locales, then user
 * DROP-INS) ONCE per module. The non-English catalogs were ripped out of the
 * bundle, and CATALOGS is shared across EVERY card in the bundle — the main
 * command-center AND the standalone room-card — so a single module-guarded load
 * covers them all (a room-card on a view with no main card would otherwise stay
 * English-only). Shipped first, then drops, so a drop-in overrides a shipped
 * locale of the same code. Fails soft. `onLoaded` (the first caller's) re-renders
 * promptly once strings arrive; every card also re-renders on the next hass push.
 *
 * @param {() => void} [onLoaded]
 */
export function ensureLocalesLoaded(onLoaded) {
  if (_localesRequested) return;
  _localesRequested = true;
  const ping = (r) => {
    if (r && r.loaded && r.loaded.length && typeof onLoaded === "function") onLoaded();
  };
  loadDroppedLocales("/eufy_vacuum/frontend/locales")
    .then(ping)
    .then(() => loadDroppedLocales("/eufy_vacuum/locales", { status: "custom" }))
    .then(ping);
}
