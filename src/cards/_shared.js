// Helpers shared by the standalone Vacuum Agent Lovelace cards (the single-room
// room-card and the multi-room dashboard card). Kept small, pure, and DOM-light
// so both cards have ONE source of truth for escaping, vocab localization, the
// room-switch readers, and the chip-row markup.

import { translate, resolveLang, ensureLocalesLoaded, listLocales } from "../i18n/index.js";
import { getStoredLang, setStoredLang } from "../i18n/lang-store.js";

export { translate, resolveLang, ensureLocalesLoaded, listLocales };
// The per-user language store (HA frontend user-data, cross-device) — the SAME key
// the sidebar panel uses, so a language picked in a card and the panel stay in sync.
export { getStoredLang, setStoredLang };

/** HTML-escape a value for safe interpolation into innerHTML. */
export function esc(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * Localize a setting VALUE through `vocab.<field>.<slug>`, falling back to a
 * provided label (escaped) when there's no catalog entry. `t` is the card's
 * bound translate function (locale already resolved).
 */
export function vocab(t, field, value, fallback) {
  if (value == null || value === "") return esc(fallback ?? "");
  const slug = String(value).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  const out = t(`vocab.${field}.${slug}`);
  return out === `vocab.${field}.${slug}` ? esc(fallback ?? String(value)) : out;
}

/**
 * Every per-room switch managed by one vacuum, read live from hass.states.
 * Each carries the room_id + the adapter-declared option lists + current
 * per-room settings as attributes (populated by the backend room entity).
 * @returns {Array<{entityId: string, state: string, attrs: object}>}
 */
export function roomSwitchesFor(hass, vacuumEntityId) {
  const states = hass?.states;
  if (!states || !vacuumEntityId) return [];
  return Object.entries(states)
    .filter(([id, s]) =>
      id.startsWith("switch.") &&
      s.attributes?.vacuum_entity_id === vacuumEntityId &&
      s.attributes?.room_id != null
    )
    .map(([id, s]) => ({ entityId: id, state: s.state, attrs: s.attributes ?? {} }));
}

/** Read an adapter-declared option list `[{value,label},…]` off switch attrs. */
export function adapterOptions(attrs, attrName) {
  const list = attrs?.[attrName];
  return Array.isArray(list) ? list : [];
}

/** The committed (saved) per-room field values off a room switch's attributes. */
export function committedRoomFields(attrs = {}) {
  return {
    clean_mode:      attrs.clean_mode      ?? "vacuum",
    fan_speed:       attrs.fan_speed       ?? null,
    water_level:     attrs.water_level     ?? null,
    clean_intensity: attrs.clean_intensity ?? null,
    clean_passes:    Number(attrs.clean_passes ?? 1),
    edge_mopping:    Boolean(attrs.edge_mopping ?? false),
  };
}

/** True for any mode whose name contains "mop" (vacuum_mop, mop, …). */
export function isMopMode(mode) {
  return String(mode ?? "").toLowerCase().replace(/[\s_-]/g, "").includes("mop");
}

/**
 * Build a chip-row of mutually-exclusive options. `tVocabFn(field, value, label)`
 * returns the localized chip label. `idPrefix` namespaces the data-attrs so a
 * card with many rows can route clicks back to the right room.
 */
export function chipRow(label, fieldKey, options, currentVal, tVocabFn, idPrefix = "") {
  if (!options.length) return "";
  const pre = idPrefix ? `data-scope="${esc(idPrefix)}" ` : "";
  return `
    <div class="field-group">
      <div class="field-label">${esc(label)}</div>
      <div class="chips">
        ${options.map((opt) => `
          <button
            class="chip ${String(currentVal ?? "").toLowerCase() === String(opt.value ?? "").toLowerCase() ? "active" : ""}"
            ${pre}data-field="${esc(fieldKey)}"
            data-value="${esc(opt.value)}"
          >${tVocabFn(fieldKey, opt.value, opt.label)}</button>
        `).join("")}
      </div>
    </div>
  `;
}

/**
 * Response-capable service call (snapshot / saved-profile reads). Mirrors the
 * panel's actions/core.js helper: target undefined, notifyOnError false,
 * returnResponse true. Returns the unwrapped `response` payload, or null on any
 * failure (never throws into the render cycle).
 */
export async function callResponse(hass, domain, service, data = {}) {
  if (!hass?.callService) return null;
  try {
    const res = await hass.callService(domain, service, data, undefined, false, true);
    return res?.response ?? res ?? null;
  } catch (err) {
    console.error(`[vacuum-agent] ${domain}.${service} failed`, { data, err });
    return null;
  }
}

/**
 * Drop keys whose value is null/undefined. A per-room draft is seeded from the
 * room's committed fields, which carry null for any unset setting (a vacuum-only
 * room has no water_level/clean_intensity). update_room_fields types those as
 * optional STRINGS and rejects a PRESENT null, which would abort the whole call —
 * so send only the fields that actually have a value (there's no UI to set null).
 */
export function stripNull(obj) {
  return Object.fromEntries(Object.entries(obj ?? {}).filter(([, v]) => v != null));
}

/* =========================================================
   LANGUAGE CONTROL — a card-native globe + locale menu, shared by both standalone
   cards. The CHOICE persists per-user via getStoredLang/setStoredLang (the same
   store the panel uses), so the language stays consistent across the panel + cards.
   ========================================================= */

/**
 * Render the globe button + (when open) the locale menu.
 * @param {{t:function, override:string, currentLang:string, open:boolean}} o
 *   t           - the card's bound translate fn
 *   override    - the raw per-user choice ("auto" | code) — marks the active row
 *   currentLang - the RESOLVED language (the button badge, e.g. "EN")
 *   open        - whether the menu is open
 */
export function renderLangControl({ t, override, currentLang, open }) {
  const active = override && override !== "auto" ? String(override) : "auto";
  const badge = String(currentLang || "en").split("-")[0].toUpperCase();
  const rows = [{ code: "auto", label: t("language.auto") }, ...listLocales().map((l) => ({ code: l.code, label: l.label }))];
  const items = rows.map((r) => {
    const on = r.code === active;
    return `<button type="button" role="menuitemradio" aria-checked="${on}" class="va-lang-opt ${on ? "active" : ""}" data-lang="${esc(r.code)}">${on ? "✓ " : ""}${esc(r.label)}</button>`;
  }).join("");
  return `
    <div class="va-lang ${open ? "is-open" : ""}">
      <button type="button" class="va-lang-btn" id="lang-toggle" aria-haspopup="menu" aria-expanded="${open}" title="${esc(t("language.button_title"))}">
        <span aria-hidden="true">🌐</span><span class="va-lang-code">${esc(badge)}</span>
      </button>
      ${open
        ? `<div class="va-lang-backdrop" id="lang-backdrop"></div>
           <div class="va-lang-menu" role="menu" aria-label="${esc(t("language.heading"))}">
             <div class="va-lang-head">${esc(t("language.heading"))}</div>${items}
           </div>`
        : ""}
    </div>`;
}

/** Wire the globe control. Callbacks: toggle() / close() / set(code). */
export function wireLangControl(shadowRoot, { toggle, close, set }) {
  shadowRoot.getElementById("lang-toggle")?.addEventListener("click", (e) => { e.stopPropagation(); toggle(); });
  shadowRoot.getElementById("lang-backdrop")?.addEventListener("click", () => close());
  shadowRoot.querySelectorAll(".va-lang-opt").forEach((b) => b.addEventListener("click", () => set(b.dataset.lang)));
}

/** CSS for the language control — uses theme tokens with literal fallbacks. */
export const LANG_CSS = `
  .va-lang { position: relative; flex-shrink: 0; }
  .va-lang-btn { display: inline-flex; align-items: center; gap: 3px; padding: 3px 8px; border-radius: 999px; border: 1px solid var(--evcc-border-default, rgba(255,255,255,0.12)); background: transparent; color: var(--evcc-text-muted, rgba(240,242,245,0.55)); font-size: 0.72rem; font-weight: 700; cursor: pointer; -webkit-tap-highlight-color: transparent; }
  .va-lang-btn:hover { color: var(--evcc-text-primary, #f0f2f5); }
  .va-lang-backdrop { position: fixed; inset: 0; z-index: 20; }
  .va-lang-menu { position: absolute; right: 0; top: calc(100% + 4px); z-index: 21; min-width: 168px; max-height: 264px; overflow: auto; background: var(--evcc-surface-card, #1c2127); border: 1px solid var(--evcc-border-default, rgba(255,255,255,0.14)); border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,0.4); padding: 4px; }
  .va-lang-head { font-size: 0.64rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--evcc-text-muted, rgba(240,242,245,0.5)); padding: 6px 8px 4px; }
  .va-lang-opt { display: block; width: 100%; text-align: left; padding: 6px 8px; border: none; background: transparent; color: var(--evcc-text-primary, #f0f2f5); font-size: 0.82rem; cursor: pointer; border-radius: 5px; }
  .va-lang-opt:hover { background: rgba(255,255,255,0.08); }
  .va-lang-opt.active { color: var(--evcc-accent, #3b82f6); font-weight: 600; }
`;

/** Register a card in window.customCards once (idempotent across reloads). */
export function registerCard(entry) {
  window.customCards = window.customCards || [];
  if (!window.customCards.some((c) => c.type === entry.type)) {
    window.customCards.push(entry);
  }
}

/**
 * Define a custom element ONCE. The standalone cards ship in TWO bundles — the
 * panel bundle (loaded when the sidebar panel opens) and the global cards bundle
 * (loaded on every page via add_extra_module_url so the card is defined on a cold
 * dashboard). Both try to define the same elements; a plain customElements.define
 * throws "already defined" on the second. This guard makes it idempotent.
 */
export function defineCard(name, cls) {
  if (!customElements.get(name)) customElements.define(name, cls);
}
