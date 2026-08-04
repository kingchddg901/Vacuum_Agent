/**
 * ============================================================
 * CODED LABELS — one resolver for backend {code, params, message}
 * ============================================================
 *
 * The backend refuses things in two vocabularies: access-graph ISSUES
 * (`room_access.issue.*`, A6-AGX-4) and start BLOCK REASONS
 * (`rooms.block_reason.*`, A5-AG-2). The vocabularies differ; the QUESTION does
 * not — "resolve a code plus its params to a translated sentence, preferring
 * the code, never showing a bare key, never showing blank." Two copies of that
 * answer is how the shorter copy becomes the bug, so it lives here once and the
 * callers supply only their namespace.
 *
 * `message` is DELIBERATELY still emitted by the backend and is the last
 * fallback. It is the documented response-service surface that automations and
 * non-card consumers read, and it is what keeps a code this card release has
 * never heard of from rendering blank — a newer backend can add a reason
 * without the card going silent.
 *
 * Pure functions, no DOM and no `this`, so they are unit-testable directly.
 *
 * ============================================================
 */

/**
 * Join a list param with the LOCALE's separator.
 *
 * Backends ship list params unjoined (cycle chains, blocking rooms, inbound
 * sources) precisely so the CARD picks the separator — joining them server-side
 * would bake an English list convention into every locale.
 *
 * @param {string[]} keys - separator keys, most specific first.
 * @param {(key: string) => string} t
 * @returns {string}
 */
function listSeparator(keys, t) {
  for (const key of keys) {
    const sep = t(key);
    // The card's translate echoes the KEY on a miss, so that is how an
    // undefined separator is detected — fall through rather than gluing room
    // names together with a raw i18n key.
    if (sep && sep !== key) return sep;
  }
  return ", ";
}

/**
 * Stringify params, joining any list-valued one. Everything else passes through
 * untouched.
 *
 * @param {Record<string, unknown>} params
 * @param {string[]} separatorKeys
 * @param {(key: string) => string} t
 * @returns {Record<string, string>}
 */
function flattenParams(params, separatorKeys, t) {
  const out = {};
  for (const [key, value] of Object.entries(params ?? {})) {
    if (Array.isArray(value)) {
      const glue = listSeparator(separatorKeys, t);
      out[key] = value.map((entry) => String(entry)).join(glue);
    } else {
      out[key] = String(value ?? "");
    }
  }
  return out;
}

/**
 * Resolve one backend descriptor to a user-facing string.
 *
 * @param {{code?: string, params?: object, message?: string}|string|null} descriptor
 * @param {(key: string, vars?: object) => string} t - the card's translate fn.
 * @param {object} options
 * @param {string[]} options.prefixes - key prefixes to try, most specific first
 *   (e.g. ["room_access.issue.card.", "room_access.issue."]). The code is
 *   appended to each.
 * @param {string[]} [options.separatorKeys] - list-separator keys to try.
 * @param {string} [options.genericKey] - key used when the descriptor carries
 *   neither a resolvable code nor a message. Omit for "" instead.
 * @returns {string}
 */
export function resolveCodedLabel(descriptor, t, options = {}) {
  if (!descriptor || typeof descriptor !== "object") return String(descriptor ?? "");

  const prefixes = options.prefixes ?? [];
  const separatorKeys = options.separatorKeys ?? ["common.list_separator"];

  const code = String(descriptor.code ?? "").trim();
  if (code && typeof t === "function" && prefixes.length) {
    const vars = flattenParams(descriptor.params, separatorKeys, t);
    for (const prefix of prefixes) {
      const key = `${prefix}${code}`;
      const resolved = t(key, vars);
      // A miss returns the key itself (a VISIBLE miss, by design), so that is
      // how an unknown code is detected — fall through rather than showing a
      // bare key to the user.
      if (resolved && resolved !== key) return resolved;
    }
  }

  if (descriptor.message) return String(descriptor.message);
  // Nothing translatable and nothing said. Prefer the generic sentence; failing
  // that the raw code, which at least names the condition; never blank, and
  // never a silent success.
  if (options.genericKey && typeof t === "function") {
    const generic = t(options.genericKey);
    if (generic && generic !== options.genericKey) return generic;
  }
  return code;
}
