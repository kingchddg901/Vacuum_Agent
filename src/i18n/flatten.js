/**
 * ============================================================
 * I18N: NESTED-AUTHORING FLATTEN
 * ============================================================
 *
 * Locales may be AUTHORED in a context-scoped nested shape (commons + per-tab /
 * per-subtab sections with staged fallback, mirroring the theme-token chain).
 * The RUNTIME stays flat: translate() + every call site use flat dotted keys
 * (e.g. t("rooms.empty")). This module flattens a nested locale against the
 * English key manifest into the flat catalog the runtime consumes — so the
 * organizational/dedup benefits live in the FILE, never on the render hot path.
 *
 * Resolution for a flat key `s1.s2…sL` (leaf `sL`), most-specific first:
 *   0. a literal flat dotted key   (nested["s1.s2…sL"]) — a flat locale is the
 *      degenerate valid case, so existing flat files keep working untouched;
 *   1. the leaf at the deepest existing scope, walking UP the path
 *      (nested.s1.s2.sL → nested.s1.sL): a leaf placed at an ancestor scope
 *      applies to all descendants (the staged override);
 *   2. nested.commons[sL]  (the "true commons" default — the dedup);
 *   3. English (the key is omitted; translate() falls back to en).
 *
 * A leaf VALUE is a string or a plural object; a SECTION is any other object.
 * Plural vs section is decided by the CLDR-category rule (see isPluralLeaf).
 *
 * The returned `coverage` classifies every manifest key so the fall-through is
 * VISIBLE: `commons`/`untranslated` are the inherited/English ones a translator
 * should review (exactly the high-frequency shared nouns that often must diverge
 * per language); `explicit`/`scoped` are deliberate.
 *
 * ============================================================
 */

const CLDR_CATEGORIES = new Set(["zero", "one", "two", "few", "many", "other"]);

const isObject = (v) => v != null && typeof v === "object" && !Array.isArray(v);

/** An object is a PLURAL leaf iff every key is a CLDR plural category. */
export function isPluralLeaf(v) {
  if (!isObject(v)) return false;
  const keys = Object.keys(v);
  return keys.length > 0 && keys.every((k) => CLDR_CATEGORIES.has(k));
}

/** A leaf VALUE is a string or a plural object (not a section). */
function isLeafValue(v) {
  return typeof v === "string" || isPluralLeaf(v);
}

/**
 * Resolve one flat manifest key against a nested (or flat) locale.
 * @returns {{ value: string|object|undefined, source: 'explicit'|'scoped'|'commons'|'en' }}
 */
function resolveKey(nested, key) {
  // 0. Literal flat dotted key (back-compat with flat locale files).
  if (isLeafValue(nested[key])) return { value: nested[key], source: "explicit" };

  const path = key.split(".");
  const leaf = path[path.length - 1];

  // 1. Leaf at the deepest existing scope, walking up to the section.
  for (let depth = path.length - 1; depth >= 1; depth--) {
    let node = nested;
    let reachable = true;
    for (let i = 0; i < depth; i++) {
      node = node && node[path[i]];
      if (!isObject(node)) { reachable = false; break; }
    }
    if (reachable && node && isLeafValue(node[leaf])) {
      return { value: node[leaf], source: depth === path.length - 1 ? "explicit" : "scoped" };
    }
  }

  // 2. Commons default.
  if (isObject(nested.commons) && isLeafValue(nested.commons[leaf])) {
    return { value: nested.commons[leaf], source: "commons" };
  }

  // 3. English fallback (omit the key; translate() resolves it to en).
  return { value: undefined, source: "en" };
}

/**
 * Flatten a nested (or flat) locale against the English key manifest.
 *
 * @param {Record<string, unknown>} nested - the authored locale (nested or flat).
 * @param {Record<string, string|object>} enManifest - the English base = the
 *   complete key set + the final fallback.
 * @returns {{ flat: Record<string, string|object>,
 *             coverage: { explicit: string[], scoped: string[], commons: string[], untranslated: string[] } }}
 *   `flat` is a SUBSET (untranslated keys are omitted so translate() falls back
 *   to en); `coverage` accounts for every manifest key.
 */
export function flattenLocale(nested, enManifest) {
  const flat = {};
  const coverage = { explicit: [], scoped: [], commons: [], untranslated: [] };
  const manifest = enManifest && typeof enManifest === "object" ? enManifest : {};
  if (!isObject(nested)) {
    coverage.untranslated = Object.keys(manifest);
    return { flat, coverage };
  }
  for (const key of Object.keys(manifest)) {
    const { value, source } = resolveKey(nested, key);
    if (source === "en" || value === undefined) {
      coverage.untranslated.push(key);
      continue; // omit — translate() falls back to English
    }
    flat[key] = value;
    coverage[source].push(key);
  }
  return { flat, coverage };
}
