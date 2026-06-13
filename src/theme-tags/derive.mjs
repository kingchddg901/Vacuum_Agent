/**
 * ============================================================
 * THEME TAGS — derive objective, searchable tags from a palette
 * ============================================================
 *
 * Pure and dependency-free, so the SAME logic runs in the card (at runtime, from
 * state.resolvedTheme().tokens) AND in the gallery builder (at build time). Tags
 * are computed on the fly and never stored, so tweaking the taxonomy updates every
 * surface at once and they can't go stale.
 *
 * deriveThemeTags(tokens, opts) -> string[]   (the DERIVED tags only)
 *   tokens       : flat map of `--evcc-*` -> value (6/8-char hex or rgb()/rgba()).
 *                  Missing canonical tokens fall back to the foundation defaults.
 *   opts.builtIn : when true, add the `core` status tag (theme ships in the system).
 *
 * The EFFECTIVE tag set for a theme = deriveThemeTags(...) ∪ its manual `tags` field
 * (the non-inferable "vibe" tags authored in the theme JSON / submission form).
 *
 * Facets produced:
 *   mode          dark | light
 *   accent        red | orange | gold | green | teal | cyan | blue | purple | pink | mono
 *   temperature   warm | cool | neutral        (omitted for mono accents)
 *   contrast      high-contrast | soft         (only the extremes; "normal" is untagged)
 *   accessibility colorblind-safe              (semantics + accent separable under deutan/protan)
 *   surface       deep | vivid | muted
 *   status        core                          (only when opts.builtIn)
 * ============================================================
 */

// Foundation defaults for the canonical tokens we read (mirrors foundation.js / the
// HA-var fallbacks resolved to concrete values), so a theme that omits a token is
// still classified against the colour the card would actually render.
const DEFAULTS = {
  "--evcc-surface-base":  "#1c2127",
  "--evcc-accent":        "#3b82f6",
  "--evcc-text-primary":  "#f0f2f5",
  "--evcc-sem-success":   "#4caf6e",
  "--evcc-sem-warning":   "#f5a623",
  "--evcc-sem-error":     "#e05252",
  "--evcc-sem-info":      "#5a90d6",
};

/* ---------- colour parsing + math ---------- */

export function parseColor(v) {
  if (typeof v !== "string") return null;
  const s = v.trim();
  let m = s.match(/^#([0-9a-fA-F]{3,8})$/);
  if (m) {
    let h = m[1];
    if (h.length === 3 || h.length === 4) h = h.slice(0, 3).split("").map((c) => c + c).join("");
    if (h.length >= 6) {
      return { r: parseInt(h.slice(0, 2), 16), g: parseInt(h.slice(2, 4), 16), b: parseInt(h.slice(4, 6), 16) };
    }
    return null;
  }
  m = s.match(/^rgba?\(([^)]+)\)$/i);
  if (m) {
    const p = m[1].split(",").map((x) => parseFloat(x));
    if (p.length >= 3 && p.slice(0, 3).every((n) => Number.isFinite(n))) {
      return { r: p[0], g: p[1], b: p[2] };
    }
  }
  return null;
}

const _lin = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
export const luminance = ({ r, g, b }) => 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b);
export function contrastRatio(a, b) {
  const la = luminance(a), lb = luminance(b);
  const hi = Math.max(la, lb), lo = Math.min(la, lb);
  return (hi + 0.05) / (lo + 0.05);
}
export function rgbToHsl({ r, g, b }) {
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
  const l = (max + min) / 2;
  const sat = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1));
  let h = 0;
  if (d !== 0) {
    if (max === r) h = (((g - b) / d) % 6 + 6) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h *= 60;
  }
  return [h, sat, l];
}

function hueFamily(h) {
  if (h < 15 || h >= 352) return "red";
  if (h < 40)  return "orange";
  if (h < 66)  return "gold";
  if (h < 160) return "green";
  if (h < 195) return "teal";
  if (h < 215) return "cyan";
  if (h < 255) return "blue";
  if (h < 290) return "purple";
  return "pink";
}
function temperature(h) {
  if (h < 66 || h >= 290) return "warm";   // red / orange / gold / pink / magenta
  if (h >= 160 && h < 290) return "cool";  // teal / cyan / blue / purple
  return "neutral";                         // green
}

// HCIRN-style deutan/protan simulation in sRGB (heuristic, good enough for tagging).
function simulate({ r, g, b }, kind) {
  if (kind === "protan") return { r: 0.567 * r + 0.433 * g, g: 0.558 * r + 0.442 * g, b: 0.242 * g + 0.758 * b };
  return { r: 0.625 * r + 0.375 * g, g: 0.70 * r + 0.30 * g, b: 0.30 * g + 0.70 * b }; // deutan
}
const _dist = (a, b) => Math.hypot(a.r - b.r, a.g - b.g, a.b - b.b);

// The minimum pairwise distance among the given colours after the worst-case of
// deutan/protan simulation — low means two roles collapse for a CVD viewer.
export function cvdMinSeparation(colors) {
  let min = Infinity;
  for (const kind of ["deutan", "protan"]) {
    const sim = colors.map((c) => simulate(c, kind));
    for (let i = 0; i < sim.length; i++) {
      for (let j = i + 1; j < sim.length; j++) min = Math.min(min, _dist(sim[i], sim[j]));
    }
  }
  return min;
}

/* ---------- tunable thresholds ---------- */
export const THRESHOLDS = {
  lightLum:      0.5,    // surface-base luminance above this => light theme
  monoSat:       0.15,   // accent saturation below this => no hue family (mono)
  highContrast:  18,     // text-primary : surface-base ratio at/above => high-contrast (reserved for genuine max-contrast)
  softContrast:  13,     // ...below => soft (gentle / cozy)
  cvdSafe:       33,     // min CVD separation among the 4 semantics at/above => colorblind-safe
  deepLum:       0.006,  // surface-base luminance below this => deep (near-black)
  vividSat:      0.50,   // surface-base saturation at/above => vivid
  mutedSat:      0.20,   // surface-base saturation below this => muted
};

/** Raw metrics behind the tags — exported for tuning, debugging, and "why this tag". */
export function themeMetrics(tokens) {
  const get = (k) => parseColor(tokens?.[k]) || parseColor(DEFAULTS[k]);
  const base = get("--evcc-surface-base");
  const accent = get("--evcc-accent");
  const textPrimary = get("--evcc-text-primary");
  const sems = ["success", "warning", "error", "info"].map((s) => get(`--evcc-sem-${s}`));
  const [ah, asat] = rgbToHsl(accent);
  const [, bsat] = rgbToHsl(base);
  return {
    baseLum: luminance(base),
    baseSat: bsat,
    accentHue: ah,
    accentSat: asat,
    textContrast: contrastRatio(textPrimary, base),
    cvdMin: cvdMinSeparation(sems),
  };
}

/** Derive the objective tag set for a theme from its resolved token map. */
export function deriveThemeTags(tokens, opts = {}) {
  const m = themeMetrics(tokens);
  const t = THRESHOLDS;
  const tags = new Set();

  tags.add(m.baseLum > t.lightLum ? "light" : "dark");

  if (m.accentSat < t.monoSat) {
    tags.add("mono");
  } else {
    tags.add(hueFamily(m.accentHue));
    tags.add(temperature(m.accentHue));
  }

  if (m.textContrast >= t.highContrast) tags.add("high-contrast");
  else if (m.textContrast < t.softContrast) tags.add("soft");

  // `colorblind-safe` is intentionally NOT auto-derived. A crude palette metric
  // over-claims — it would tag themes the a11y audit rejected, and a false safety
  // claim is worse than none. It is a VERIFIED manual tag, set when a theme passes
  // the generation a11y audit (or authored). cvdMin is exposed in themeMetrics for
  // that audit, not used for tagging here.

  if (m.baseLum < t.deepLum) tags.add("deep");
  if (m.baseSat >= t.vividSat) tags.add("vivid");
  else if (m.baseSat < t.mutedSat) tags.add("muted");

  if (opts.builtIn) tags.add("core");

  return [...tags];
}
