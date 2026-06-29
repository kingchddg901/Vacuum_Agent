/**
 * ============================================================
 * RENDERER: HEADER LANGUAGE CONTROL
 * ============================================================
 *
 * A globe button in the header that opens a dropdown of the bundled locales
 * (plus "Auto (system)"), letting the user switch the card's display language
 * regardless of the HA system language. The choice persists per-user, server-
 * side (see i18n/lang-store.js), so it follows the login across devices.
 *
 * Shared by the desktop header (render-cycle.js) and the mobile header
 * (mobile-shell.js) so the control is identical on both. The caller passes its
 * `renderers` object (for `t`) plus the card-level UI state.
 *
 * OPEN STATE lives on the CARD (ctx.languageMenuOpen), not in the DOM, because
 * the header re-renders whenever vacuum status/battery change — a DOM-only open
 * flag would snap shut on every state push. A transparent full-bleed backdrop
 * closes the menu on outside click, mirroring the card's modal pattern.
 *
 * ============================================================
 */

import { listLocales } from "../i18n/index.js";

/** Minimal HTML escape — labels come from our own endonym table, escaped for defence in depth. */
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]),
  );
}

/**
 * Render the header language control.
 *
 * @param {{ t: (key: string, vars?: object) => string }} renderers - the card's
 *   renderers object (or the renderers prototype instance on mobile); only `t`
 *   is used.
 * @param {{ langOverride?: string, currentLang?: string, open?: boolean }} ctx
 *   - `langOverride`: the raw per-user choice ("auto" | code) — marks the active
 *     menu row;
 *   - `currentLang`: the RESOLVED language — shown as a short badge on the button;
 *   - `open`: whether the dropdown is open.
 * @returns {string} HTML
 */
export function renderLanguageControl(renderers, { langOverride, currentLang, open, autoInfo } = {}) {
  const t = (k, v) => renderers.t(k, v);
  const active = langOverride && langOverride !== "auto" ? String(langOverride) : "auto";
  const badge = String(currentLang || "en").split("-")[0].toUpperCase();

  const locales = listLocales();

  // When the user has no pin and their HA system language is an unreviewed
  // draft, "Auto" silently resolves to English (the draft-gate). Disclose that
  // on the Auto row so the control doesn't look broken — name the drafted
  // language and point at its (manually selectable) row below.
  let autoNote = "";
  if (autoInfo && autoInfo.gatedToEnglish) {
    const sys = locales.find((l) => l.code === autoInfo.systemLang);
    const sysName = sys ? sys.endonym : autoInfo.systemLang;
    autoNote = t("language.auto_draft_note", { lang: esc(sysName) });
  }

  // Rows: "Auto (system)" first, then every selectable locale (English first,
  // bundled alphabetically, then any drop-in "custom" locales). listLocales
  // orders them and labels drafts in their own language (e.g. "Русский
  // (черновик)") + custom drop-ins as "<Endonym> (custom)".
  // label is pre-escaped (t() escapes by trust-model B; raw endonyms get esc'd once)
  // so it interpolates directly below — re-esc()'ing would double-escape (apostrophe
  // → &#39; → &amp;#39;, shown literally).
  const rows = [
    { code: "auto", label: t("language.auto"), note: autoNote },
    ...locales.map((l) => ({ code: l.code, label: esc(l.label) })),
  ];

  const items = rows
    .map((r) => {
      const isActive = r.code === active;
      // r.note is already a t()-escaped string with an esc()'d {lang} var — insert
      // raw, as a flex sibling so it wraps to its own full-width line below.
      const noteHtml = r.note ? `<span class="evcc-lang-note">${r.note}</span>` : "";
      return `
        <button type="button" role="menuitemradio" aria-checked="${isActive}"
                class="evcc-lang-option${isActive ? " is-active" : ""}"
                data-action="set-language" data-lang="${esc(r.code)}">
          <span class="evcc-lang-check" aria-hidden="true">${isActive ? "✓" : ""}</span>
          <span class="evcc-lang-label">${r.label}</span>
          ${noteHtml}
        </button>`;
    })
    .join("");

  return `
    <div class="evcc-lang${open ? " is-open" : ""}">
      <button type="button" class="evcc-lang-button"
              data-action="toggle-language-menu"
              aria-haspopup="menu" aria-expanded="${open ? "true" : "false"}"
              title="${t("language.button_title")}"
              aria-label="${t("language.button_title")}">
        <span class="evcc-lang-globe" aria-hidden="true">🌐</span>
        <span class="evcc-lang-code">${esc(badge)}</span>
      </button>
      ${open
        ? `<div class="evcc-lang-backdrop" data-action="close-language-menu"></div>
           <div class="evcc-lang-menu" role="menu" aria-label="${t("language.heading")}">
             <div class="evcc-lang-menu-heading">${t("language.heading")}</div>
             ${items}
           </div>`
        : ""}
    </div>
  `;
}
