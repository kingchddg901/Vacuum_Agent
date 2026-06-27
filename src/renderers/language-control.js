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
export function renderLanguageControl(renderers, { langOverride, currentLang, open } = {}) {
  const t = (k, v) => renderers.t(k, v);
  const active = langOverride && langOverride !== "auto" ? String(langOverride) : "auto";
  const badge = String(currentLang || "en").split("-")[0].toUpperCase();

  // Rows: "Auto (system)" first, then every selectable locale (English first,
  // bundled alphabetically, then any drop-in "custom" locales). listLocales
  // orders them and labels drafts in their own language (e.g. "Русский
  // (черновик)") + custom drop-ins as "<Endonym> (custom)".
  const rows = [
    { code: "auto", label: t("language.auto") },
    ...listLocales().map((l) => ({ code: l.code, label: l.label })),
  ];

  const items = rows
    .map((r) => {
      const isActive = r.code === active;
      return `
        <button type="button" role="menuitemradio" aria-checked="${isActive}"
                class="evcc-lang-option${isActive ? " is-active" : ""}"
                data-action="set-language" data-lang="${esc(r.code)}">
          <span class="evcc-lang-check" aria-hidden="true">${isActive ? "✓" : ""}</span>
          <span class="evcc-lang-label">${esc(r.label)}</span>
        </button>`;
    })
    .join("");

  return `
    <div class="evcc-lang${open ? " is-open" : ""}">
      <button type="button" class="evcc-lang-button"
              data-action="toggle-language-menu"
              aria-haspopup="menu" aria-expanded="${open ? "true" : "false"}"
              title="${esc(t("language.button_title"))}"
              aria-label="${esc(t("language.button_title"))}">
        <span class="evcc-lang-globe" aria-hidden="true">🌐</span>
        <span class="evcc-lang-code">${esc(badge)}</span>
      </button>
      ${open
        ? `<div class="evcc-lang-backdrop" data-action="close-language-menu"></div>
           <div class="evcc-lang-menu" role="menu" aria-label="${esc(t("language.heading"))}">
             <div class="evcc-lang-menu-heading">${esc(t("language.heading"))}</div>
             ${items}
           </div>`
        : ""}
    </div>
  `;
}
