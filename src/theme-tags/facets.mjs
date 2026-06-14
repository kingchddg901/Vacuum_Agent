/**
 * ============================================================
 * THEME TAGS — facet grouping (the filter-bar vocabulary)
 * ============================================================
 *
 * The flat tag list from effectiveThemeTags() is grouped into FACETS so a filter
 * bar can show "Accent: red orange gold…" instead of one undifferentiated row.
 * This is the ONE source of truth the Pages gallery AND the card's theme picker
 * both import — same facets, same order, same labels, so the two surfaces filter
 * identically.
 *
 * Filter semantics both surfaces implement: OR within a facet (purple OR cyan),
 * AND across facets (accent:purple AND mode:dark). The free-text VIBE tags
 * (aurora, cosmic…) are NOT faceted — they're shown on cards and matched by the
 * search box, but they don't get filter chips (open vocabulary, too many).
 * ============================================================
 */

/** Ordered facets. `tags` is the controlled, ordered vocabulary for that facet. */
export const FACETS = [
  { key: "mode", label: "Mode", tags: ["dark", "light"] },
  { key: "accent", label: "Accent", tags: ["red", "orange", "gold", "green", "teal", "cyan", "blue", "purple", "pink", "mono"] },
  { key: "temperature", label: "Temp", tags: ["warm", "cool", "neutral"] },
  { key: "surface", label: "Surface", tags: ["deep", "vivid", "muted"] },
  { key: "contrast", label: "Contrast", tags: ["soft", "high-contrast"] },
  { key: "a11y", label: "Access", tags: ["colorblind-safe"] },
  { key: "source", label: "Source", tags: ["core", "community", "generated", "manual"] },
];

/** tag -> facet key, for grouping a theme's own tags and colouring chips. */
export const TAG_FACET = (() => {
  const m = new Map();
  for (const f of FACETS) for (const t of f.tags) m.set(t, f.key);
  return m;
})();

/** Which facet a tag belongs to; "vibe" for free-text tags outside the vocabulary. */
export const facetOf = (tag) => TAG_FACET.get(tag) || "vibe";

/** A short curated hint list for the free-text vibe-tag editor — suggestions
 *  only, NOT a controlled vocabulary (the user can type anything). Avoids system
 *  words, which are stripped anyway. Shared so the card and submission UI agree. */
export const SUGGESTED_VIBE_TAGS = [
  "aurora", "cosmic", "galaxy", "nebula", "ocean", "sunset", "forest", "nature",
  "winter", "autumn", "spring", "summer", "neon", "retro", "vaporwave", "pastel",
  "moody", "cozy", "minimal", "vibrant", "earthy", "candy", "dreamy", "bold",
];

/** Order tags by facet order then within-facet order; vibe tags last, alphabetical. */
export function orderTags(tags) {
  const order = [];
  for (const f of FACETS) for (const t of f.tags) order.push(t);
  const rank = (t) => {
    const i = order.indexOf(t);
    return i === -1 ? order.length : i;
  };
  return [...tags].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
}
