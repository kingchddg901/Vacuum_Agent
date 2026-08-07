/**
 * ============================================================
 * FONTS — the user-selectable card typeface
 * ============================================================
 *
 * ACCESSIBILITY FEATURE, deliberately two states: the theme/paper default, and
 * OpenDyslexic. Nothing else ships. The mechanism underneath is generic (see
 * i18n/font-store.js's FONT_SUPPORT) so a second font or a second locale is a
 * data edit, not a rewrite — but the SHIPPED surface is one font, one verified
 * locale, one preference.
 *
 * ------------------------------------------------------------
 * WHY THE FILES ARE SERVED, NOT EMBEDDED AS data: URIs
 * ------------------------------------------------------------
 * The design called for data URIs on a "~100KB base64" estimate. The real
 * release is 115KB + 120KB of woff2 — about 314KB once base64'd, three times
 * the estimate. That matters more than usual here: the cards bundle is
 * registered with `add_extra_js_url`, so it loads on EVERY Home Assistant page,
 * and every user would pay those bytes on every page whether or not they use
 * the font.
 *
 * Served instead, from /eufy_vacuum/fonts (registered in __init__.py with
 * cache_headers=True). A browser fetches an @font-face src only when something
 * actually renders in that family, so the cost is zero until the toggle is on,
 * and cached afterwards.
 *
 * The design's actual GOALS are all still met: the files ship inside the same
 * HACS package, they are same-origin, and there is no CDN and no external fetch.
 * What was given up is "literally one file", which was never the requirement.
 *
 * ------------------------------------------------------------
 * LICENCE — SIL Open Font License 1.1, RESERVED FONT NAME
 * ------------------------------------------------------------
 * OpenDyslexic (c) 2019-07-29 Abbie Gonzalez (https://abbiecod.es),
 * with Reserved Font Name OpenDyslexic. Copyright (c) 12/2012 - 2019.
 *
 * The OFL REQUIRES the notice to travel with the font: the full licence text
 * ships beside the woff2 files at frontend/fonts/OFL.txt and must not be
 * removed. "Reserved Font Name" means a MODIFIED version may not be distributed
 * under the name OpenDyslexic — these files are unmodified, which is why the
 * name is used here.
 *
 * ============================================================
 */

/** Where __init__.py serves frontend/fonts/. Kept in one place. */
const FONT_BASE = "/eufy_vacuum/fonts";

/**
 * THE font table — everything CSS-side about a selectable font, one entry per
 * font. Adding a font = add its woff2 files to frontend/fonts/, add one entry
 * here, and add its verified locales to i18n/font-store.js FONT_SUPPORT (the
 * ids must match — TF-11 pins that) + a `font.<id>` label key. Every rule
 * below (@font-face, the a11y-token setters, the picker sample class) is
 * GENERATED from this table, so there is no hand-written per-font CSS to
 * forget (live:FONT-1 was three copies of exactly that class of miss).
 *
 * `stack` MUST be a full fallback chain, and every inner var() MUST carry a
 * fallback — a fallback-less var() on a setup where that var is unset poisons
 * the whole declaration to guaranteed-invalid (TF-10).
 */
export const FONT_DEFS = [
  {
    id: "opendyslexic",
    family: "OpenDyslexic",
    stack: `"OpenDyslexic", var(--paper-font-body1_-_font-family, sans-serif)`,
    /* Regular + Bold only. Italic and Bold-Italic are deliberately not
       shipped: the card renders no italic body text, and each face is another
       ~115KB the browser might fetch for nothing. */
    faces: [
      { file: "OpenDyslexic-Regular.woff2", weight: 400 },
      { file: "OpenDyslexic-Bold.woff2", weight: 700 },
    ],
  },
];

/**
 * Curated stacks the theme editor offers as CHIPS on the Font Family token —
 * instead of a bare text entry (the text input stays as the escape hatch).
 * Labels are typeface/product NAMES, rendered verbatim in every locale by
 * Chris's ruling — names are not translated, so no i18n keys. Every FONT_DEFS
 * font is appended automatically (TF-13), so a newly added card font shows up
 * as a theme chip with zero extra wiring. Every var() in every stack MUST
 * carry a fallback (TF-10 — the guaranteed-invalid trap).
 */
export const FONT_STACK_PRESETS = [
  { id: "system", label: "System UI", stack: `system-ui, "Segoe UI", Roboto, sans-serif` },
  { id: "ha", label: "Home Assistant", stack: `var(--paper-font-body1_-_font-family, sans-serif)` },
  { id: "georgia", label: "Georgia", stack: `Georgia, "Times New Roman", serif` },
  { id: "mono", label: "Consolas", stack: `ui-monospace, Consolas, "Cascadia Mono", monospace` },
  ...FONT_DEFS.map((def) => ({ id: def.id, label: def.family, stack: def.stack })),
];

/* The face declarations, alone. Injected into document.head by
   ensureFontFacesInDocument() below — Chromium does NOT register @font-face
   rules that live only inside a shadow tree, so a shadow-stylesheet copy of
   these is inert there (live:FONT-1: four comments asserted "registered
   document-wide"; nothing performed it, and document.fonts.check() exonerated
   the gap because check() returns true for a family with no registered faces
   at all). The rules also remain part of fontStyles for engines that do read
   them from shadow sheets — duplicate registration of an identical face is a
   no-op.
   font-display: swap — show the fallback immediately and re-render when the
   face arrives. On an accessibility typeface, invisible text while a 115KB
   file loads is the worst possible failure mode. */
export const FONT_FACE_CSS = FONT_DEFS.map((def) => def.faces.map((face) => `
  @font-face {
    font-family: "${def.family}";
    src: url("${FONT_BASE}/${face.file}") format("woff2");
    font-weight: ${face.weight};
    font-style: normal;
    font-display: swap;
  }
`).join("")).join("");

/**
 * The a11y-token setter rules for one host selector pattern. Used for the
 * card's shadow sheet below and re-used by styles/index.js for the modal and
 * toast hosts (document.body children cannot inherit a token declared on the
 * card's :host, and applyDynamicTheme writes THEME tokens inline on those
 * hosts — the a11y token stays a SEPARATE, sheet-declared token that every
 * font-family read consults FIRST; see the chain comment below).
 *
 * @param {(id: string) => string} selectorFor - font id -> full selector.
 * @returns {string} CSS rules, one per FONT_DEFS entry.
 */
export function fontTokenRules(selectorFor) {
  return tokenRulesFor(FONT_DEFS, selectorFor);
}

function tokenRulesFor(defs, selectorFor) {
  return defs.map((def) => `
  ${selectorFor(def.id)} {
    --evcc-a11y-font-family: ${def.stack};
  }
`).join("");
}

/* =========================================================
   USER DROP-IN FONTS (runtime)
   =========================================================
   config/eufy_vacuum/fonts/ holds user-supplied typefaces — one SUBDIRECTORY
   per font: font.json + its woff2 files + its licence. The BACKEND owns
   discovery, validation, cmap parsing, and per-locale verification
   (user_fonts.py, fontTools): the descriptor does not even declare which
   locales it supports — the font FILE is the evidence, and catalog.json is
   the canonical, backend-derived font-library response. The card consumes
   the catalog generically: register faces, generate the a11y setters and
   picker samples, offer per verified locale. No FONT_DEFS edit, no rebuild,
   no release — drop files, restart HA, refresh.

   The card deliberately does NOT render-verify in the browser: rendered-text
   checks (document.fonts.check(), canvas width heuristics) can lie through
   per-glyph fallback — the exact instrument class that false-exonerated
   live:FONT-1. It DOES still sanitize every catalog field before it becomes
   CSS (defense in depth; the catalog file rides a user-writable directory).

   Catalog entry shape:
     { "id": "atkinson", "family": "Atkinson Hyperlegible",
       "label": "Atkinson Hyperlegible", "dir": "atkinson",
       "faces": [{ "file": "Atkinson-Regular.woff2", "weight": 400 }],
       "fallback": ["Arial", "sans-serif"],
       "locales": ["en", "de"], "status": "verified" } */

const USER_FONT_BASE = "/eufy_vacuum/user_fonts";

const RUNTIME_FONT_DEFS = [];

const ID_RE = /^[a-z0-9][a-z0-9_-]{0,31}$/;
const DIR_RE = /^[\w-]{1,64}$/;
const FILE_RE = /^[\w][\w.-]*\.woff2$/;
const LANG_RE = /^[a-z]{2,3}(-[a-z0-9]{2,8})?$/i;
const GENERIC_FALLBACKS = new Set(["sans-serif", "serif", "monospace"]);
const FALLBACK_NAME_RE = /^[A-Za-z][A-Za-z0-9 -]{0,31}$/;

/**
 * Validate + normalize one CATALOG entry. Returns a def or null; never
 * throws. Rejections are conservative: an id collision with a shipped font,
 * a quoted/backslashed family, a face or dir that is not a bare path
 * segment — anything that could smuggle CSS or a traversal — kills the
 * whole entry. Mirrors user_fonts.py's validate_descriptor.
 */
export function sanitizeUserFontDef(raw) {
  if (!raw || typeof raw !== "object") return null;
  const id = typeof raw.id === "string" ? raw.id : "";
  if (!ID_RE.test(id)) return null;
  if (FONT_DEFS.some((d) => d.id === id)) return null;
  if (RUNTIME_FONT_DEFS.some((d) => d.id === id)) return null;

  const dir = typeof raw.dir === "string" ? raw.dir : "";
  if (!DIR_RE.test(dir) || dir.includes("..")) return null;

  const family = typeof raw.family === "string" ? raw.family.trim() : "";
  if (!family || family.length > 64 || /["\\\n\r{};]/.test(family)) return null;

  const label = typeof raw.label === "string" && raw.label.trim()
    ? raw.label.trim().slice(0, 64).replace(/[<>"\\\n\r]/g, "")
    : family;

  const fallback = [];
  for (const item of Array.isArray(raw.fallback) ? raw.fallback.slice(0, 4) : []) {
    if (typeof item !== "string") continue;
    if (GENERIC_FALLBACKS.has(item) || FALLBACK_NAME_RE.test(item)) fallback.push(item);
  }
  if (!fallback.length || !GENERIC_FALLBACKS.has(fallback[fallback.length - 1])) {
    fallback.push("sans-serif");
  }

  const rawFaces = Array.isArray(raw.faces) ? raw.faces.slice(0, 4) : [];
  const faces = [];
  for (const f of rawFaces) {
    if (!f || typeof f !== "object") continue;
    const file = typeof f.file === "string" ? f.file : "";
    if (!FILE_RE.test(file) || file.includes("..")) continue;
    const weight = Number.isInteger(f.weight) && f.weight >= 100 && f.weight <= 900
      ? f.weight
      : 400;
    faces.push({ file, weight });
  }
  if (!faces.length) return null;

  // The backend-verified offering. An unverified font sanitizes to zero
  // locales — catalogued, renderable in principle, never offered.
  const locales = [];
  for (const lang of Array.isArray(raw.locales) ? raw.locales.slice(0, 32) : []) {
    if (typeof lang === "string" && LANG_RE.test(lang)) locales.push(lang.toLowerCase());
  }

  return {
    id,
    family,
    label,
    stack: `"${family}", var(--paper-font-body1_-_font-family, ${fallback.join(", ")})`,
    faces,
    locales,
    base: `${USER_FONT_BASE}/${dir}`,
    runtime: true,
  };
}

/**
 * Fetch the backend-built catalog and register every valid entry.
 * Best-effort end to end: any failure (no HA, missing catalog, bad JSON,
 * bad entry) is a skip, never a throw — the shipped fonts must be untouched
 * by a broken drop-in. Returns the defs added THIS call.
 */
export async function loadUserFonts(fetchFn = globalThis.fetch) {
  if (typeof fetchFn !== "function") return [];
  let entries;
  try {
    const res = await fetchFn(`${USER_FONT_BASE}/catalog.json`, { cache: "no-store" });
    if (!res.ok) return [];
    entries = await res.json();
  } catch {
    return [];
  }
  if (!Array.isArray(entries)) return [];
  const added = [];
  for (const raw of entries.slice(0, 32)) {
    const def = sanitizeUserFontDef(raw);
    if (def) {
      RUNTIME_FONT_DEFS.push(def);
      added.push(def);
    }
  }
  return added;
}

/** All fonts the card knows about right now — shipped first, then drop-ins. */
export function allFontDefs() {
  return [...FONT_DEFS, ...RUNTIME_FONT_DEFS];
}

/** Theme-editor chips for the drop-ins (labels verbatim — names). */
export function runtimeFontPresets() {
  return RUNTIME_FONT_DEFS.map((def) => ({ id: def.id, label: def.label, stack: def.stack }));
}

/** @font-face rules for the drop-ins (their files live under def.base). */
export function runtimeFontFaceCss() {
  return RUNTIME_FONT_DEFS.map((def) => def.faces.map((face) => `
  @font-face {
    font-family: "${def.family}";
    src: url("${def.base}/${face.file}") format("woff2");
    font-weight: ${face.weight};
    font-style: normal;
    font-display: swap;
  }
`).join("")).join("");
}

/** a11y-token setters for the drop-ins, same seam as fontTokenRules. */
export function runtimeFontTokenRules(selectorFor) {
  return tokenRulesFor(RUNTIME_FONT_DEFS, selectorFor);
}

/**
 * Everything the card's SHADOW sheet needs for the drop-ins: faces (for
 * engines that read them there), the :host setters, and the picker samples.
 * Injected by main.js as a second shadow <style> once drop-ins load.
 */
export function runtimeShadowFontCss() {
  return `
  ${runtimeFontFaceCss()}
  ${runtimeFontTokenRules((id) => `:host([data-evcc-font="${id}"]),\n  [data-evcc-font="${id}"]`)}
  ${RUNTIME_FONT_DEFS.map((def) => `
  .evcc-font-sample-${def.id} {
    font-family: ${def.stack};
  }
`).join("")}
`;
}

const USER_FONT_FACE_STYLE_ID = "eufy-vacuum-user-font-faces";

/**
 * Document-level registration for the drop-in faces — same Chromium
 * shadow-tree rule as the shipped fonts (TF-6). Content-keyed rather than
 * id-guarded: drop-ins can grow after first injection.
 */
export function ensureUserFontFacesInDocument(doc = globalThis.document) {
  if (!doc || !doc.head) return;
  const css = runtimeFontFaceCss();
  if (!css.trim()) return;
  let style = doc.getElementById(USER_FONT_FACE_STYLE_ID);
  if (!style) {
    style = doc.createElement("style");
    style.id = USER_FONT_FACE_STYLE_ID;
    doc.head.appendChild(style);
  }
  if (style.textContent !== css) style.textContent = css;
}

const FONT_FACE_STYLE_ID = "eufy-vacuum-font-faces";

/**
 * Register the typeface's @font-face rules on the DOCUMENT, where every
 * browser honours them. Idempotent (id-guarded); safe to call from every
 * bundle entry — whichever loads first wins and the rest no-op. No-op outside
 * a browser (tests, node).
 */
export function ensureFontFacesInDocument(doc = globalThis.document) {
  if (!doc || !doc.head || doc.getElementById(FONT_FACE_STYLE_ID)) return;
  const style = doc.createElement("style");
  style.id = FONT_FACE_STYLE_ID;
  style.textContent = FONT_FACE_CSS;
  doc.head.appendChild(style);
}

export const fontStyles = `
  ${FONT_FACE_CSS}

  /* The override — one generated rule per FONT_DEFS entry, set on the shell
     ROOT. A SEPARATE token, deliberately not --evcc-font-family: the theme's
     Font Family token is written INLINE by applyDynamicTheme and inline beats
     any sheet rule — so instead of fighting the cascade, precedence lives in
     the fallback chain. Every font-family read is
       var(--evcc-a11y-font-family, var(--evcc-font-family, …))
     — accessibility first, theme second, HA default last. Unset (default, and
     every non-verified locale via the glyph-coverage gate) it falls straight
     through to the theme (live:FONT-1 remainder #2, 2026-08-06).

     Each stack stays a real fallback CHAIN. A glyph the font lacks — a
     Cyrillic room name the user typed, a CJK label — falls through to the
     theme font rather than rendering as tofu. That is required robustness:
     the coverage gate promises the card's own translated CHROME renders in
     the font, never that arbitrary user data does. */
  ${fontTokenRules((id) => `:host([data-evcc-font="${id}"]),\n  [data-evcc-font="${id}"]`)}

  /* FORM CONTROLS DO NOT INHERIT FONTS. input/select/textarea/button default
     to the UA font, so without this every text box ignores the selected
     typeface (and the theme font) — found live: the theme-search placeholder
     rendered the system font under OpenDyslexic. Element-level specificity, so
     any feature rule that sets its own font still wins. */
  input, textarea, select, button {
    font-family: inherit;
  }

  /* The picker's own option renders IN the font it offers, so the user can see
     what they are choosing before choosing it — the one place the font must
     apply regardless of the current setting. Not the token: this option must
     stay in its own face even while the card is on the default. Generated per
     FONT_DEFS entry as .evcc-font-sample-<id>. */
  ${FONT_DEFS.map((def) => `
  .evcc-font-sample-${def.id} {
    font-family: ${def.stack};
  }
`).join("")}
`;
