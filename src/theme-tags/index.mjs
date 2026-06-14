/**
 * ============================================================
 * THEME TAGS — effective tag set (the public entry point)
 * ============================================================
 *
 * effectiveThemeTags(theme) is the ONE function every surface (card picker, Pages
 * gallery, submission bot) calls. It combines:
 *   - DERIVED facet tags (mode / accent / temperature / surface / contrast) from the
 *     palette — authoritative, the author can't override them,
 *   - the `core` status from `source: "core"`,
 *   - the author's free-text VIBE tags (aurora, cosmic, winter…), with any
 *     system-owned word stripped so it can't be spoofed,
 *   - `colorblind-safe` ONLY when verifyColorblindSafe() actually passes.
 *
 * It also returns the colour-vision verdict (requested? verified? why-not?) so a
 * submission form or the card can show exactly why a requested `colorblind-safe`
 * tag was withheld.
 * ============================================================
 */
import { deriveThemeTags, themeMetrics } from "./derive.mjs";
import { verifyColorblindSafe } from "./colorblind.mjs";

export { deriveThemeTags, themeMetrics } from "./derive.mjs";
export { verifyColorblindSafe, CVD_DELTA_E } from "./colorblind.mjs";
export { parseColor, rgbToHsl, luminance, contrastRatio, THRESHOLDS } from "./derive.mjs";
export { FACETS, TAG_FACET, facetOf, orderTags, SUGGESTED_VIBE_TAGS } from "./facets.mjs";

// Every tag the SYSTEM owns (derived facets + verified + status). Authors may not
// free-text these — they're computed, so a hand-typed one is stripped from `tags`.
export const SYSTEM_VOCAB = new Set([
  "dark", "light",
  "red", "orange", "gold", "green", "teal", "cyan", "blue", "purple", "pink", "mono",
  "warm", "cool", "neutral",
  "deep", "vivid", "muted", "soft", "high-contrast",
  "colorblind-safe", "red-green", "blue-yellow", "core",
]);

const norm = (s) => String(s).toLowerCase().trim();

/**
 * @param {object} theme  a theme envelope's `theme` object: { colors, tokens, tags?, source? }.
 * @returns {{ tags: string[], colorblind: { requested:boolean, verified:boolean, reasons:Array, minDeltaE:number } }}
 */
export function effectiveThemeTags(theme = {}) {
  const tokens = { ...(theme.tokens || {}), ...(theme.colors || {}) };
  const source = norm(theme.source || "");

  const derived = deriveThemeTags(tokens, { builtIn: source === "core" });

  const manual = (Array.isArray(theme.tags) ? theme.tags : []).map(norm).filter(Boolean);
  const requestedCb = manual.includes("colorblind-safe");
  const vibe = manual.filter((t) => !SYSTEM_VOCAB.has(t)); // strip system-owned words

  const cb = verifyColorblindSafe(tokens);

  const tags = new Set([...derived, ...vibe]);
  if (cb.pass) {
    tags.add("colorblind-safe"); // verified only
    if (cb.bestBucket) tags.add(cb.bestBucket); // red-green / blue-yellow it's strongest for
  }

  return {
    tags: [...tags],
    colorblind: {
      requested: requestedCb,
      verified: cb.pass,
      minDeltaE: cb.minDeltaE,
      weakest: cb.weakest,
      buckets: cb.buckets,
      bestBucket: cb.bestBucket,
      perCvd: cb.perCvd,
      reasons: cb.reasons,
    },
  };
}

const SOURCES = new Set(["core", "community", "generated", "manual"]);

/**
 * Normalised attribution / provenance for a theme — one read-point for the gallery
 * and the card picker (display name + credit link + where it came from).
 * @param {object} theme  a theme envelope's `theme` object.
 */
export function themeAttribution(theme = {}) {
  const s = norm(theme.source || "");
  return {
    author: theme.author ? String(theme.author).trim() : null,
    authorUrl: theme.author_url ? String(theme.author_url).trim() : null,
    source: SOURCES.has(s) ? s : null,
    submittedBy: theme.submitted_by ? String(theme.submitted_by).trim() : null,
  };
}
