/**
 * ============================================================
 * THEME TOKENS: ENVELOPE FLATTEN (tokens / colors / alpha -> CSS)
 * ============================================================
 *
 * PURPOSE
 * -------
 * ONE answer to "how do the three theme buckets become CSS-ready
 * values?". The envelope keeps `colors` (base hex) and `alpha`
 * (0-1 multiplier) apart so an alpha-only edit can never clobber a
 * stored hex; every consumer that wants a flat `key -> value` map
 * therefore has to RECOMBINE them, not merely concatenate them.
 *
 * THE HAZARD THIS MODULE EXISTS TO KILL
 * -------------------------------------
 * Concatenating the buckets in write order (tokens, colors, alpha)
 * makes `alpha[k]` OVERWRITE `colors[k]` for every key present in
 * both — the token resolves to the bare number `0.76`, which is not
 * a colour. Nothing reports it: `var(--evcc-text-secondary)` IS
 * defined, so the CSS fallback never fires and the built-in default
 * paints instead. Paired keys are the theme editor's NORMAL output
 * (the opacity rail on a colour row writes `alpha[key]`), so this
 * silently voids real themes. Three sites flattened independently;
 * only the state resolver got it right.
 *
 * SEMANTIC (taken from the canonical resolver, state/theme.js)
 * -----------------------------------------------------------
 *   1. `tokens`  — seed; already-CSS-ready values.
 *   2. `colors`  — overwrite; the base hex wins over a pre-baked
 *                  token value, so an alpha-only change re-bakes.
 *   3. `alpha`   — COMPOSE onto the colour from step 2, never
 *                  overwrite. Alpha with no colour applies to
 *                  nothing (reported, not written as a bare number).
 *
 * ============================================================
 */

/** 6- or 8-digit hex — the only colour form an alpha multiplier can bake into. */
const HEX_RE = /^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/;

/**
 * Bake an alpha multiplier (0–1) into a CSS hex color string.
 * Strips any existing alpha channel from the hex, then appends the new one.
 * Returns the original value (trimmed) unchanged if it is not a valid 6- or
 * 8-char hex, or if `alpha` is absent / not a number.
 *
 * @param {string} colorHex - `#rrggbb` or `#rrggbbaa` (anything else passes through).
 * @param {number|null|undefined} alpha - 0–1 multiplier; clamped.
 * @returns {string} CSS-ready colour value.
 */
export function hexWithAlpha(colorHex, alpha) {
  const trimmed = String(colorHex || "").trim();

  let base6;
  if (/^#[0-9a-fA-F]{8}$/.test(trimmed)) {
    base6 = `#${trimmed.slice(1, 7)}`;
  } else if (/^#[0-9a-fA-F]{6}$/.test(trimmed)) {
    base6 = trimmed;
  } else {
    return trimmed;
  }

  if (alpha === null || alpha === undefined) {
    return trimmed;
  }

  const clamped = Math.max(0, Math.min(1, Number(alpha)));
  if (Number.isNaN(clamped)) return trimmed;
  const alphaHex = Math.round(clamped * 255).toString(16).padStart(2, "0").toLowerCase();
  return `${base6}${alphaHex}`;
}

/**
 * Would `hexWithAlpha` actually apply this alpha? Reporting-only predicate —
 * it answers "did the author's alpha reach the output, or vanish?", which the
 * return value of hexWithAlpha alone cannot (baking 1.0 onto `#112233ff` is a
 * no-op that DID apply). Shares HEX_RE with the baker so the two can't drift.
 *
 * @returns {boolean} false for a non-hex base (`rgb()`, `color-mix()`, `""`)
 *                    or a non-numeric alpha — both silently drop the alpha.
 */
export function alphaApplies(colorValue, alpha) {
  if (alpha === null || alpha === undefined) return false;
  if (!Number.isFinite(Number(alpha))) return false;
  return HEX_RE.test(String(colorValue || "").trim());
}

/**
 * Flatten a theme's three buckets into one CSS-ready `key -> value` map,
 * composing `alpha` onto `colors` rather than overwriting it.
 *
 * The two report lists exist so a caller can stop claiming an all-clear it
 * hasn't earned: `composed` is positive evidence the alpha path fired, and
 * `unappliedAlpha` names every alpha entry that reached nothing — an orphan
 * (no colour for that key) or a base no alpha can bake into (`rgb()`,
 * `color-mix()`). Both were previously invisible.
 *
 * @param {object} theme - `{ tokens?, colors?, alpha? }`; any bucket may be
 *                         absent or malformed (non-objects are ignored).
 * @returns {{bundle: object, composed: string[], unappliedAlpha: string[]}}
 */
export function flattenThemeBuckets(theme = {}) {
  const dict = (d) => (d && typeof d === "object" && !Array.isArray(d) ? d : {});
  const tokens = dict(theme?.tokens);
  const colors = dict(theme?.colors);
  const alpha = dict(theme?.alpha);

  const bundle = {};
  const composed = [];
  const unappliedAlpha = [];

  // 1. tokens — already CSS-ready, written as authored.
  for (const [key, value] of Object.entries(tokens)) bundle[key] = value;

  // 2 + 3. colors, with any paired alpha baked in. `colors` wins over a
  // pre-baked `tokens` value so an alpha-only change re-bakes correctly.
  for (const [key, value] of Object.entries(colors)) {
    const a = key in alpha ? alpha[key] : null;
    bundle[key] = hexWithAlpha(value, a);
    if (a !== null && a !== undefined) {
      (alphaApplies(value, a) ? composed : unappliedAlpha).push(key);
    }
  }

  // An alpha with no colour composes onto nothing. Writing the bare number
  // would define the property as an invalid colour — the original bug — so
  // it is dropped and named instead.
  for (const key of Object.keys(alpha)) {
    if (!(key in colors)) unappliedAlpha.push(key);
  }

  return { bundle, composed, unappliedAlpha };
}
