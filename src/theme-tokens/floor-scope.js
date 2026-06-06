/**
 * ============================================================
 * THEME TOKENS: FLOOR-TYPE SCOPE
 * ============================================================
 *
 * PURPOSE
 * -------
 * Registry-driven helpers for slicing a theme by FLOOR TYPE — the
 * basis of targeted (per-floor-type) theme export/import.
 *
 * A "scope unit" is one floor type's token namespace: every
 * --evcc-floor-{type}-* key, across all three theme sections
 * (tokens, colors, alpha). A floor type's keys appear in more than
 * one section (e.g. marble has color keys in `colors`, their alpha
 * in `alpha`, and numeric controls in `tokens`), so scoping must
 * span all three.
 *
 * GENERIC OVER FLOOR TYPES — never hardcode a type's token set. The
 * valid type list comes from FLOOR_TEXTURE_REGISTRY, so any floor
 * type added there is automatically supported. Names are OPAQUE:
 * match whole names by prefix, never split on dashes (that would
 * mis-bucket "carpet-low" into "carpet" + "low"). On overlap the
 * longest matching name wins.
 *
 * ============================================================
 */

import { FLOOR_TEXTURE_REGISTRY } from "../textures/floor-texture-registry.js";

/** Common prefix of every floor token, before the type segment. */
export const FLOOR_TOKEN_PREFIX = "--evcc-floor-";

/**
 * Valid floor-type names for this build, derived from the registry.
 * Registry keys use underscores (carpet_low); token namespaces use
 * hyphens (--evcc-floor-carpet-low-*), so we map _ -> -. "default" is
 * the fallback entry, not a real floor type, so it is excluded.
 *
 * @returns {string[]} sorted type names, e.g. ["carpet-high","carpet-low","concrete","granite-light","marble","tile","wood"]
 */
export function floorTypeNames() {
  return Object.keys(FLOOR_TEXTURE_REGISTRY)
    .filter((key) => key !== "default")
    .map((key) => key.replace(/_/g, "-"))
    .sort();
}

/** The token-key prefix that scopes one floor type's namespace. */
export function floorTypePrefix(name) {
  return `${FLOOR_TOKEN_PREFIX}${name}-`;
}

/**
 * Whole-name match: does `key` belong to floor type `name`?
 * (Prefix match on --evcc-floor-{name}- — never a dash-split.)
 */
export function keyInType(key, name) {
  return typeof key === "string" && key.startsWith(floorTypePrefix(name));
}

/**
 * Resolve which floor type a single floor key belongs to, choosing the
 * LONGEST matching valid name so "carpet-low" wins over a hypothetical
 * "carpet". Returns null if the key is a floor key of no KNOWN type.
 */
function typeOfFloorKey(key, validNames) {
  let best = null;
  for (const name of validNames) {
    if (key.startsWith(floorTypePrefix(name)) && (!best || name.length > best.length)) {
      best = name;
    }
  }
  return best;
}

/**
 * Inspect an export envelope (or a bare theme) and report which floor
 * types it carries.
 *
 * @param {object} envelope - {theme:{tokens,colors,alpha}} or a bare theme.
 * @returns {{known:string[], unknown:string[]}}
 *   known   - KNOWN floor types present (registry-validated, sorted).
 *   unknown - distinct --evcc-floor-* namespaces this build's registry
 *             does NOT recognise (e.g. a Terrazzo preset on an older
 *             version). Surfaced so an import can skip them as
 *             "unsupported" instead of dropping them silently.
 */
export function detectFloorScope(envelope) {
  const theme = (envelope && typeof envelope === "object" && envelope.theme) || envelope || {};
  const valid = floorTypeNames();
  const known = new Set();
  const unknown = new Set();

  for (const bucket of ["tokens", "colors", "alpha"]) {
    const dict = theme[bucket];
    if (!dict || typeof dict !== "object") continue;
    for (const key of Object.keys(dict)) {
      if (!key.startsWith(FLOOR_TOKEN_PREFIX)) continue;
      const type = typeOfFloorKey(key, valid);
      if (type) {
        known.add(type);
      } else {
        // Bucket the unknown by its segment after the prefix, up to the
        // next dash — best-effort label for the "skipped" notice. Names
        // can be multi-segment, so this is a display hint only.
        const rest = key.slice(FLOOR_TOKEN_PREFIX.length);
        unknown.add(rest.split("-")[0] || rest);
      }
    }
  }

  return {
    known: [...known].sort(),
    unknown: [...unknown].sort(),
  };
}

/**
 * Slice a full export envelope down to the given floor type(s).
 * Returns a NEW scoped envelope — same shape as a full export plus a
 * `scope` list — containing only those types' keys across all three
 * sections. Keys of other types and non-floor keys are dropped.
 *
 * @param {object} envelope - a full export envelope from exportTheme.
 * @param {string[]|string} names - floor type name(s) to keep.
 * @returns {object} {ok, version, exported_at, scope:[...], theme:{name,tokens,colors,alpha}}
 */
export function sliceThemeByTypes(envelope, names) {
  const theme = (envelope && typeof envelope === "object" && envelope.theme) || {};
  const wanted = (Array.isArray(names) ? names : [names]).filter(Boolean);

  const sliceDict = (dict) => {
    const out = {};
    if (dict && typeof dict === "object") {
      for (const [key, value] of Object.entries(dict)) {
        if (wanted.some((name) => keyInType(key, name))) out[key] = value;
      }
    }
    return out;
  };

  return {
    ok: true,
    version: envelope?.version ?? 1,
    exported_at: envelope?.exported_at ?? null,
    scope: [...wanted],
    theme: {
      name: theme.name ?? "",
      tokens: sliceDict(theme.tokens),
      colors: sliceDict(theme.colors),
      alpha: sliceDict(theme.alpha),
    },
  };
}

/** Total key count across the three sections of a (scoped) theme. */
export function themeKeyCount(envelope) {
  const theme = (envelope && typeof envelope === "object" && envelope.theme) || {};
  return (
    Object.keys(theme.tokens || {}).length +
    Object.keys(theme.colors || {}).length +
    Object.keys(theme.alpha || {}).length
  );
}

/**
 * Clamp an envelope's bounded-scalar values to each token's declared range, so
 * a hand-edited or cross-version file can't inject out-of-range values that
 * invert behavior (e.g. negative opacity, a chroma that exceeds the cap).
 *
 * Validation partition:
 *   - bounded scalar (token has finite min/max) → clamp numeric value.
 *   - color / rangeless / non-numeric           → pass through unchanged
 *     (any hex is valid; legibility is decoupled, so colors are never clamped).
 *
 * Single source: the min/max come from the same token spec that drives the
 * editor slider — the editor can't emit a value its own importer would reject.
 *
 * @param {object} envelope - export envelope ({theme:{tokens,colors,alpha}}).
 * @param {object} tokenMap - key -> token entry (carrying optional min/max).
 * @returns {{envelope:object, corrected:number}} clamped copy + count corrected.
 */
export function clampThemeScalars(envelope, tokenMap) {
  const theme = (envelope && typeof envelope === "object" && envelope.theme) || {};
  const map = tokenMap || {};
  let corrected = 0;

  const clampDict = (dict) => {
    const out = {};
    if (!dict || typeof dict !== "object") return out;
    for (const [key, value] of Object.entries(dict)) {
      const spec = map[key];
      const min = spec && Number.isFinite(spec.min) ? spec.min : null;
      const max = spec && Number.isFinite(spec.max) ? spec.max : null;
      const num = Number(value);

      if ((min !== null || max !== null) && Number.isFinite(num)) {
        let clamped = num;
        if (min !== null && clamped < min) clamped = min;
        if (max !== null && clamped > max) clamped = max;
        if (clamped !== num) corrected += 1;
        out[key] = clamped;
      } else {
        // color, rangeless (.number), or non-numeric — never clamped.
        out[key] = value;
      }
    }
    return out;
  };

  return {
    envelope: {
      ...envelope,
      theme: {
        ...theme,
        tokens: clampDict(theme.tokens),
        colors: clampDict(theme.colors),
        alpha: clampDict(theme.alpha),
      },
    },
    corrected,
  };
}
