// Helpers shared by the standalone Vacuum Agent Lovelace cards (the single-room
// room-card and the multi-room dashboard card). Kept small, pure, and DOM-light
// so both cards have ONE source of truth for escaping, vocab localization, the
// room-switch readers, and the chip-row markup.

import { translate, resolveLang, ensureLocalesLoaded, listLocales, applyDir } from "../i18n/index.js";
import { getStoredLang, setStoredLang } from "../i18n/lang-store.js";
// ISSUE #48: the ONE card-side clean_mode fold. Re-exported so the standalone
// cards keep importing it from here, but owned by a dependency-free module the
// pure steps-manifest builder can also reach.
import { canonicalCleanMode } from "../clean-mode.js";

export { translate, resolveLang, ensureLocalesLoaded, listLocales, applyDir };
// The per-user language store (HA frontend user-data, cross-device) — the SAME key
// the sidebar panel uses, so a language picked in a card and the panel stay in sync.
export { getStoredLang, setStoredLang };
export { canonicalCleanMode };

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
export function vocab(t, field, value, fallback, brand) {
  if (value == null || value === "") return esc(fallback ?? "");
  const slug = String(value).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  // anchor: RN6F7RW6  brand-scoped vocab resolution — the replica set
  // REPLICA RN6F7RW6 — twins: renderers/shared.js::tVocab and room-card.js::tVocab (two
  // classes). All resolve a vocabulary label the SAME way and must agree.
  //
  // A brand OWNS its value's word (doc 20 · f/eufy_is_not_the_default): try
  // `vocab.<brand>.<field>.<value>` FIRST, so a brand whose declared label differs from
  // the shared catalog (Dreame fan_speed "turbo" → "Max" vs the shared Eufy-origin
  // "Turbo") is NOT overridden by another brand's word. Then the shared
  // `vocab.<field>.<value>`, then the adapter's declared label. Eufy/Roborock declare no
  // `vocab.<brand>.*` keys, so they fall straight through — byte-identical. The key
  // template stays INSIDE t() so check:i18n's template scan reaches it (3 segments →
  // vocab.<seg>.<seg>.<seg>). brand is the adapter_id from the dashboard snapshot.
  if (brand) {
    const bo = t(`vocab.${brand}.${field}.${slug}`);
    if (bo !== `vocab.${brand}.${field}.${slug}`) return bo;
  }
  const out = t(`vocab.${field}.${slug}`);
  return out === `vocab.${field}.${slug}` ? esc(fallback ?? String(value)) : out;
}

/**
 * Every per-room switch managed by one vacuum, read live from hass.states.
 * Each carries the room_id + the adapter-declared option lists + current
 * per-room settings as attributes (populated by the backend room entity).
 * @returns {Array<{entityId: string, state: string, attrs: object}>}
 */
// anchor: RN60D6C4  the per-room SWITCH FILTER -- the replica set. card-suggestions.js
// restates it locally and says why: 'kept local so this module stays dependency-free'.
// LOAD-BEARING -- dissolving it adds the dependency the copy exists to avoid.
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

/**
 * Read an adapter-declared CONTINUOUS axis `{min,max,step,labels}` off switch attrs
 * (Dreame wetness 1..32). Returns null when absent or malformed — a brand declares
 * EITHER options (chip row) OR a range (slider), never both, so the caller branches
 * on which is non-empty.
 */
export function adapterRange(attrs, attrName) {
  const r = attrs?.[attrName];
  if (!r || typeof r !== "object" || r.min == null || r.max == null) return null;
  return r;
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
 * Is this chip the selected one? Every field compares case-insensitively, and
 * clean_mode ALSO folds display spellings — the stored value is a label, the
 * option value is a token, and lowercasing alone never made them equal.
 */
function _chipIsActive(fieldKey, currentVal, optValue) {
  if (fieldKey === "clean_mode") {
    return canonicalCleanMode(currentVal) === canonicalCleanMode(optValue);
  }
  return String(currentVal ?? "").toLowerCase() === String(optValue ?? "").toLowerCase();
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
      <div class="field-label">${label}</div>
      <div class="chips">
        ${options.map((opt) => `
          <button
            class="chip ${_chipIsActive(fieldKey, currentVal, opt.value) ? "active" : ""}"
            ${pre}data-field="${esc(fieldKey)}"
            data-value="${esc(opt.value)}"
          >${tVocabFn(fieldKey, opt.value, opt.label)}</button>
        `).join("")}
      </div>
    </div>
  `;
}

/**
 * Build a single-value SLIDER for a continuous axis (Dreame wetness 1..32), the
 * sibling of `chipRow` for a brand that declares `*_range` rather than `*_options`.
 * The stored field value is a numeric STRING; the binding commits `input.value`.
 * `range` is `{min,max,step,labels:{min_label,mid_label,max_label}}`. An unset value
 * starts the thumb at the midpoint rather than at 0. `idPrefix` namespaces the
 * data-attrs so a card with many rooms routes the input back to the right one.
 */
/**
 * The band WORD for a continuous value — a single live label that shifts across the
 * range (Dreame wetness: Slightly Dry -> Moist -> Wet) rather than showing all three
 * endpoints at once. Thirds of [min,max]; used by the render (initial) and the slider
 * binding (live on input), which recompute it identically from data-word-* attrs.
 */
export function sliderWord(val, min, max, labels) {
  const l = labels || {};
  const third = (max - min) / 3;
  if (val <= min + third) return l.min_label ?? "";
  if (val >= max - third) return l.max_label ?? "";
  return l.mid_label ?? "";
}

export function sliderRow(label, fieldKey, range, currentVal, idPrefix = "") {
  if (!range) return "";
  const pre = idPrefix ? `data-scope="${esc(idPrefix)}" ` : "";
  const min = Number(range.min);
  const max = Number(range.max);
  const step = Number(range.step ?? 1);
  const lbls = range.labels ?? {};
  const mid = Math.round((min + max) / 2);
  const parsed = currentVal == null || currentVal === "" ? mid : Number(currentVal);
  const val = Number.isFinite(parsed) ? Math.min(max, Math.max(min, parsed)) : mid;
  return `
    <div class="field-group">
      <div class="field-label">${label}</div>
      <div class="slider-row">
        <input type="range" class="range-slider"
          ${pre}data-slider-field="${esc(fieldKey)}"
          data-word-low="${esc(lbls.min_label ?? "")}"
          data-word-mid="${esc(lbls.mid_label ?? "")}"
          data-word-high="${esc(lbls.max_label ?? "")}"
          min="${min}" max="${max}" step="${step}" value="${val}"
          aria-label="${esc(label)}" />
        <output class="slider-value">${val}</output>
        <span class="slider-word-wrap"><span class="slider-word" data-slider-word>${esc(sliderWord(val, min, max, lbls))}</span></span>
      </div>
    </div>
  `;
}

//: Shared CSS for the sliderRow() output (.slider-*). Interpolated into BOTH card
//: shadow roots (dashboard-card CARD_CSS + room-card) so the wetness slider reads the
//: same on every surface — the value as a small pill chip beside the slider, the live
//: word (Slightly Dry / Moist / Wet) as a chip on its own line below. Mirrors the modal's
//: .evcc-slider-* block in styles/modal-host.js. Tokens are chosen to resolve in either
//: card (--surface-subtle in room-card, --evcc-surface-subtle in dashboard-card).
export const SLIDER_ROW_CSS = `
  .slider-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .range-slider { flex: 1 1 auto; min-width: 0; }
  .slider-value {
    flex: 0 0 auto;
    padding: 3px 12px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface-subtle, var(--evcc-surface-subtle, rgba(255,255,255,0.04)));
    color: var(--text-primary);
    font-weight: 700; font-size: 0.80rem;
    font-variant-numeric: tabular-nums;
  }
  .slider-word-wrap { flex: 0 0 100%; }
  .slider-word {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface-subtle, var(--evcc-surface-subtle, rgba(255,255,255,0.04)));
    color: var(--text-muted);
    font-size: 0.78rem; font-weight: 600;
    white-space: nowrap;
  }
`;

/**
  * REPLICA RNGP3ZBE -- primary: src/actions/core.js::callService.
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
  // r.label is pre-escaped here (t() escapes by trust-model B; raw endonyms get esc'd
  // once) so it interpolates directly below — re-esc()'ing it would double-escape (e.g.
  // an apostrophe → &#39; → &amp;#39;, rendered literally).
  const rows = [{ code: "auto", label: t("language.auto") }, ...listLocales().map((l) => ({ code: l.code, label: esc(l.label) }))];
  const items = rows.map((r) => {
    const on = r.code === active;
    return `<button type="button" role="menuitemradio" aria-checked="${on}" class="va-lang-opt ${on ? "active" : ""}" data-lang="${esc(r.code)}">${on ? "✓ " : ""}${r.label}</button>`;
  }).join("");
  return `
    <div class="va-lang ${open ? "is-open" : ""}">
      <button type="button" class="va-lang-btn" id="lang-toggle" aria-haspopup="menu" aria-expanded="${open}" title="${t("language.button_title")}">
        <span aria-hidden="true">🌐</span><span class="va-lang-code">${esc(badge)}</span>
      </button>
      ${open
        ? `<div class="va-lang-backdrop" id="lang-backdrop"></div>
           <div class="va-lang-menu" role="menu" aria-label="${t("language.heading")}">
             <div class="va-lang-head">${t("language.heading")}</div>${items}
           </div>`
        : ""}
    </div>`;
}

/** Wire the globe control. Callbacks: toggle() / close() / set(code). */
export function wireLangControl(shadowRoot, { toggle, close, set }) {
  const btn = shadowRoot.getElementById("lang-toggle");
  btn?.addEventListener("click", (e) => { e.stopPropagation(); toggle(); });
  shadowRoot.getElementById("lang-backdrop")?.addEventListener("click", () => close());
  shadowRoot.querySelectorAll(".va-lang-opt").forEach((b) =>
    b.addEventListener("click", (e) => { e.stopPropagation(); set(b.dataset.lang); }));
  // Position the OPEN menu as fixed (viewport-relative) so it escapes the card's
  // overflow:hidden clip and never spills off a narrow card: anchored under the
  // globe, flipped above when there's no room below, clamped to the viewport.
  const menu = shadowRoot.querySelector(".va-lang-menu");
  if (menu && btn) {
    const r = btn.getBoundingClientRect();
    menu.style.position = "fixed";
    menu.style.right = "auto";
    menu.style.bottom = "auto";
    const mh = menu.offsetHeight || 260;
    const mw = menu.offsetWidth || 184;
    const below = r.bottom + 4;
    menu.style.top = `${(below + mh <= window.innerHeight - 8) ? below : Math.max(8, r.top - mh - 4)}px`;
    menu.style.left = `${Math.max(8, Math.min(r.right - mw, window.innerWidth - mw - 8))}px`;
  }
}

/** CSS for the language control — uses theme tokens with literal fallbacks. */
export const LANG_CSS = `
  .va-lang { position: relative; flex-shrink: 0; }
  .va-lang-btn { display: inline-flex; align-items: center; gap: 3px; padding: 3px 8px; border-radius: 999px; border: 1px solid var(--evcc-border-default, rgba(255,255,255,0.12)); background: transparent; color: var(--evcc-text-muted, rgba(240,242,245,0.55)); font-size: 0.72rem; font-weight: 700; cursor: pointer; -webkit-tap-highlight-color: transparent; }
  .va-lang-btn:hover { color: var(--evcc-text-primary, #f0f2f5); }
  .va-lang-backdrop { position: fixed; inset: 0; z-index: 20; }
  .va-lang-menu { position: absolute; inset-inline-end: 0; top: calc(100% + 4px); z-index: 21; min-width: 168px; max-height: 264px; overflow: auto; background: var(--evcc-surface-card, #1c2127); border: 1px solid var(--evcc-border-default, rgba(255,255,255,0.14)); border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,0.4); padding: 4px; }
  .va-lang-head { font-size: 0.64rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--evcc-text-muted, rgba(240,242,245,0.5)); padding: 6px 8px 4px; }
  .va-lang-opt { display: block; width: 100%; text-align: start; padding: 6px 8px; border: none; background: transparent; color: var(--evcc-text-primary, #f0f2f5); font-size: 0.82rem; cursor: pointer; border-radius: 5px; }
  .va-lang-opt:hover { background: var(--evcc-surface-action-hover, rgba(255,255,255,0.08)); }
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
