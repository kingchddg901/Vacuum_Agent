/**
 * Pseudo-locale generator for LAYOUT-pressure testing.
 *
 * Transforms the English catalog (src/i18n/en.js) into a same-keyed catalog
 * whose every value is deliberately LONGER — simulating the width blow-up of
 * German/Russian/etc. without hand-translating anything. Registered into the
 * harness via window.__evcc.registerLocale and rendered with opts.lang to find
 * where translated text breaks the layout (overflow, mid-phrase wrap, clipped
 * controls) BEFORE any real locale ships.
 *
 * INVARIANTS (the traps the audit called out):
 *  - RECURSE plural objects: a // plural key's value is an OBJECT of CLDR forms
 *    ({one,other,...}); transform each FORM string, never the object, or the
 *    catalog emits "[object Object]" on the highest-risk count-driven chips.
 *  - PRESERVE {placeholders} and <markup> verbatim: the expansion is APPENDED,
 *    so `{count}` still interpolates and authored tRaw markup stays valid HTML.
 *  - SHORT strings expand MOST: chips/tabs/badges (the protected zones) are
 *    where i18n actually breaks, so the expansion factor is largest for them.
 *  - The pad word carries diacritics (no markup/quote chars) so it doubles as a
 *    font/encoding probe AND a detectable marker proving the locale applied.
 */
import { en } from "../../src/i18n/en.js";

// Diacritic-bearing, markup-free, space-joinable so it can wrap at spaces;
// also the marker we grep the rendered DOM for to prove the locale switched.
export const PSEUDO_MARKER = "lÄngerêr";

function expand(s) {
  // Visible length excludes {placeholders} and <tags> so the factor reflects
  // the text the user actually reads, not interpolation/markup scaffolding.
  const visible = s.replace(/\{[^}]+\}/g, "").replace(/<[^>]+>/g, "");
  const len = visible.length;
  const factor = len <= 8 ? 1.6 : len <= 16 ? 1.0 : len <= 32 ? 0.6 : 0.35;
  const extraChars = Math.max(9, Math.ceil(len * factor));
  const n = Math.max(1, Math.round(extraChars / (PSEUDO_MARKER.length + 1)));
  return `${s} ${Array(n).fill(PSEUDO_MARKER).join(" ")}`;
}

function transform(v) {
  if (typeof v === "string") return expand(v);
  if (v && typeof v === "object") {
    const o = {};
    for (const k of Object.keys(v)) o[k] = transform(v[k]); // each CLDR plural form
    return o;
  }
  return v; // non-string/object (shouldn't occur) passes through untouched
}

/** Build the pseudo-long catalog: same keys as en.js, every value expanded. */
export function makePseudoLong() {
  const out = {};
  for (const [k, v] of Object.entries(en)) out[k] = transform(v);
  return out;
}
