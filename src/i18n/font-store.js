/**
 * ============================================================
 * FONT STORE — the per-user card typeface preference
 * ============================================================
 *
 * Sibling of lang-store.js, storing `ui_font` in the SAME `eufy_vacuum_card`
 * user-data object the globe writes `ui_language` into. That object's comment
 * anticipated exactly this ("future per-user preferences"), so the preference
 * is per-user and cross-device for free, and both writers merge rather than
 * clobber.
 *
 * ------------------------------------------------------------
 * THE COVERAGE GATE, and what it does and does not promise
 * ------------------------------------------------------------
 * A font is OFFERED for a locale only after its glyph coverage has been
 * verified against THAT LOCALE'S SHIPPED CATALOGUE — the card's own translated
 * chrome. Not against "languages that look Latin": proof, never assumption.
 * (The proof instrument is cmap inspection — user_fonts.py runs it for
 * drop-ins at setup; the shipped set below was widened 2026-08-06 by the same
 * instrument after the original hand-judgement proved wrong in both
 * directions on the actual files.)
 *
 * What the gate promises: the card's own chrome renders fully in the font.
 * What it explicitly does NOT promise: that arbitrary USER DATA does. A user's
 * Cyrillic room name under English chrome falls back to the theme font, and
 * that is correct — the CSS stack is a real fallback chain, and a fallback
 * glyph is necessary robustness rather than a failure.
 *
 * FONT_SUPPORT is the generic shape from day one so adding a font or a locale
 * is a data edit rather than a rewrite. It ships with exactly one entry.
 *
 * ============================================================
 */

import { USER_DATA_KEY } from "./lang-store.js";

/** The field name inside the shared user-data object. */
const FIELD = "ui_font";

/** The "use whatever the theme says" state. Stored as absence, not as a value. */
export const FONT_DEFAULT = "default";

/**
 * fontId -> the locales whose SHIPPED CATALOGUE that font has been verified to
 * cover. Read by the gate; never a hardcoded `lang === "en"`.
 */
// anchor: RNHME6XA  the FONT ID SPACE -- the replica set. styles/fonts.js carries the CSS
// half of every font and these ids MUST match it; TF-11 pins that. Adding a font means
// both, plus a font.<id> label key -- one edit short and the picker offers a font that
// styles nothing, or styles a font nobody can pick.
export const FONT_SUPPORT = {
  // Verified 2026-08-06 by cmap inspection (fontTools, the same evidence the
  // drop-in gate uses): the shipped OpenDyslexic-Regular/Bold carry 1586
  // codepoints including Latin Extended (ł ą ř ů ı İ ğ) and Cyrillic — the
  // earlier en-only judgement ("missing Polish/Czech/Turkish glyphs") was
  // measured against the wrong release. Hebrew and CJK are genuinely absent
  // from the cmap; Arabic additionally needs shaping. The header-comment
  // doctrine stands: locales are PROVEN, never assumed — this list is the
  // proof's output.
  opendyslexic: new Set([
    "cs", "de", "en", "es", "fr", "id", "it", "nl", "pl", "pt", "ru", "tr",
  ]),
};

/** The human-verified entries above, frozen at load — a runtime (drop-in)
 * registration may add NEW ids but can never widen a shipped font's set. */
const SHIPPED_FONT_IDS = new Set(Object.keys(FONT_SUPPORT));

/**
 * Register a locale a RUNTIME (drop-in) font has been verified for — called
 * only after the coverage gate passes (i18n/font-coverage.js, "option c").
 * This is what makes a drop-in offerable, choosable, and restorable: the
 * picker consults FONT_SUPPORT via availableFonts(), and getStoredFont /
 * setStoredFont validate ids against the same object. Shipped-font entries
 * are never touched — a drop-in cannot widen a shipped font's verified set.
 *
 * @param {string} fontId - sanitized drop-in id.
 * @param {string} lang - resolved UI language code the gate verified.
 */
export function registerRuntimeFontSupport(fontId, lang) {
  if (typeof fontId !== "string" || !fontId || fontId === FONT_DEFAULT) return;
  if (SHIPPED_FONT_IDS.has(fontId)) return; // human-verified sets are immutable
  const code = String(lang || "").trim().toLowerCase();
  if (!code) return;
  if (!Object.hasOwn(FONT_SUPPORT, fontId)) FONT_SUPPORT[fontId] = new Set();
  FONT_SUPPORT[fontId].add(code);
}

/**
 * Whether `fontId` may be offered for `lang`.
 *
 * @param {string} fontId
 * @param {string} lang - resolved UI language code.
 * @returns {boolean}
 */
export function fontSupportsLang(fontId, lang) {
  if (fontId === FONT_DEFAULT) return true;      // the theme font is always available
  const locales = FONT_SUPPORT[fontId];
  if (!locales) return false;
  const code = String(lang || "").trim().toLowerCase();
  // Match the base tag too, so "en-GB" resolves against "en" — the catalogue is
  // keyed by the code the card actually ships.
  return locales.has(code) || locales.has(code.split("-")[0]);
}

/**
 * The fonts offerable for `lang`, always including the default.
 *
 * @param {string} lang
 * @returns {string[]}
 */
export function availableFonts(lang) {
  return [
    FONT_DEFAULT,
    ...Object.keys(FONT_SUPPORT).filter((fontId) => fontSupportsLang(fontId, lang)),
  ];
}

function canWS(hass) {
  return Boolean(hass && typeof hass.callWS === "function");
}

/**
 * Read the per-user font choice. Resolves to a font id, or FONT_DEFAULT when
 * none is stored or anything goes wrong.
 *
 * @param {object} hass
 * @returns {Promise<string>}
 */
export async function getStoredFont(hass) {
  if (!canWS(hass)) return FONT_DEFAULT;
  try {
    const res = await hass.callWS({
      type: "frontend/get_user_data",
      key: USER_DATA_KEY,
    });
    const value = res && res.value;
    const fontId = value && typeof value === "object" ? value[FIELD] : null;
    // Validated on READ as well as write: a value edited directly in storage —
    // or one left behind by a release that offered a font this one does not —
    // must not reach the DOM as an attribute nothing styles.
    return typeof fontId === "string" && Object.hasOwn(FONT_SUPPORT, fontId)
      ? fontId
      : FONT_DEFAULT;
  } catch (err) {
    console.warn(
      "[eufy-vacuum-command-center] font: could not read stored font (using default):",
      err,
    );
    return FONT_DEFAULT;
  }
}

/**
 * Persist the per-user font choice, MERGING into the shared object so
 * `ui_language` survives — the globe and this write the same key.
 *
 * FONT_DEFAULT is stored by DELETING the field rather than writing "default":
 * absence already means "use the theme font", and two representations of one
 * state is how they drift apart.
 *
 * Never throws — a failed write means the choice does not survive a reload,
 * which is strictly better than breaking the toggle.
 *
 * @param {object} hass
 * @param {string} fontId
 * @returns {Promise<boolean>} true if acknowledged.
 */
export async function setStoredFont(hass, fontId) {
  if (!canWS(hass)) return false;
  const next = String(fontId || FONT_DEFAULT);
  if (next !== FONT_DEFAULT && !Object.hasOwn(FONT_SUPPORT, next)) {
    console.warn(
      `[eufy-vacuum-command-center] font: refusing to store unknown font "${next}"`,
    );
    return false;
  }
  try {
    let current = {};
    try {
      const res = await hass.callWS({
        type: "frontend/get_user_data",
        key: USER_DATA_KEY,
      });
      if (res && res.value && typeof res.value === "object" && !Array.isArray(res.value)) {
        current = res.value;
      }
    } catch {
      // Read-before-write is best-effort; fall back to a fresh object.
    }

    const value = { ...current };
    if (next === FONT_DEFAULT) {
      delete value[FIELD];
    } else {
      value[FIELD] = next;
    }

    await hass.callWS({
      type: "frontend/set_user_data",
      key: USER_DATA_KEY,
      value,
    });
    return true;
  } catch (err) {
    console.warn(
      "[eufy-vacuum-command-center] font: could not persist font choice:",
      err,
    );
    return false;
  }
}
