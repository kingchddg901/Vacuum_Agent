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

export const fontStyles = `
  /* Regular + Bold only. Italic and Bold-Italic are deliberately not shipped:
     the card renders no italic body text, and each face is another ~115KB the
     browser might fetch for nothing. Synthetic oblique is an acceptable
     degradation for the rare emphasis; two unused faces are not. */
  @font-face {
    font-family: "OpenDyslexic";
    src: url("${FONT_BASE}/OpenDyslexic-Regular.woff2") format("woff2");
    font-weight: 400;
    font-style: normal;
    /* swap: show the fallback immediately and re-render when the face arrives.
       On an accessibility typeface, invisible text while a 115KB file loads is
       the worst possible failure mode. */
    font-display: swap;
  }

  @font-face {
    font-family: "OpenDyslexic";
    src: url("${FONT_BASE}/OpenDyslexic-Bold.woff2") format("woff2");
    font-weight: 700;
    font-style: normal;
    font-display: swap;
  }

  /* The override. Set on the shell ROOT so it beats a theme that also sets
     --evcc-font-family: the user's accessibility choice must win over a theme's
     aesthetic one, and a theme cannot reach inside this attribute selector.
     Every surface already reads the token (styles/index.js, theme-preview.js),
     so this one declaration switches the whole card.

     The stack stays a real fallback CHAIN. A glyph OpenDyslexic lacks — a
     Cyrillic room name the user typed, a CJK label — falls through to the theme
     font rather than rendering as tofu. That is required robustness, not a
     failure: the coverage gate promises the card's own translated CHROME
     renders in the font, never that arbitrary user data does. */
  :host([data-evcc-font="opendyslexic"]),
  [data-evcc-font="opendyslexic"] {
    --evcc-font-family: "OpenDyslexic", var(--paper-font-body1_-_font-family), sans-serif;
  }

  /* The picker's own option renders IN the font it offers, so the user can see
     what they are choosing before choosing it — the one place the font must
     apply regardless of the current setting. Not the token: this option must
     stay OpenDyslexic even while the card is on the default. */
  .evcc-font-sample-opendyslexic {
    font-family: "OpenDyslexic", var(--paper-font-body1_-_font-family), sans-serif;
  }
`;
