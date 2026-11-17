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

/**
 * Build a single-value SLIDER for a continuous axis (Dreame wetness 1..32), the
 * sibling of `chipRow` for a brand that declares `*_range` rather than `*_options`.
 * The stored field value is a numeric STRING; the binding commits `input.value`.
 * `range` is `{min,max,step,labels:{min_label,mid_label,max_label}}`. An unset value
 * starts the thumb at the midpoint rather than at 0. `tVocabFn` is slot 5 and `idPrefix`
 * slot 6 — that order matters, because a stale caller passing a room id into the
 * translator slot loses `data-scope` and commits every slider to the wrong room.
 */
export function sliderRow(label, fieldKey, range, currentVal, tVocabFn, idPrefix = "") {
  if (!range) return "";
  const pre = idPrefix ? `data-scope="${esc(idPrefix)}" ` : "";
  const min = Number(range.min);
  const max = Number(range.max);
  const step = Number(range.step ?? 1);
  // The band words arrive as the ADAPTER's English labels ("Slightly Dry"), so they are
  // vocabulary VALUES and not authored text: localize each through `vocab.<fieldKey>.<slug>`
  // and keep the adapter's own word as the fallback, so a custom-declared range (any words
  // at all, config_schema.py allows them) still reads as its author wrote it.
  //
  // Localizing HERE, once, is what fixes the live word too: the three data-word-* attrs
  // below are what the slider bindings copy into the chip on every input event
  // (bindings/index.js, dashboard-card.js, room-card.js), so a fix at the initial render
  // alone would flip back to English on the first drag.
  //
  // `tVocabFn` returns an ALREADY-ESCAPED string on both arms — a catalog hit through
  // translate()'s Trust-Model-B escape, a miss through vocab()'s own esc(fallback) — so
  // every sink below interpolates it RAW. Escaping again would render a translated
  // "Légèrement sec" as `L&#39;...` (reference_i18n_double_escape).
  const rawLbls = range.labels ?? {};
  const band = (word) =>
    word == null || word === ""
      ? ""
      : (typeof tVocabFn === "function" ? tVocabFn(fieldKey, word, word) : esc(word));
  const lbls = {
    min_label: band(rawLbls.min_label),
    mid_label: band(rawLbls.mid_label),
    max_label: band(rawLbls.max_label),
  };
  const mid = Math.round((min + max) / 2);
  const parsed = currentVal == null || currentVal === "" ? mid : Number(currentVal);
  const val = Number.isFinite(parsed) ? Math.min(max, Math.max(min, parsed)) : mid;
  return `
    <div class="field-group">
      <div class="field-label">${label}</div>
      <div class="slider-row">
        <input type="range" class="range-slider"
          ${pre}data-slider-field="${esc(fieldKey)}"
          data-word-low="${lbls.min_label}"
          data-word-mid="${lbls.mid_label}"
          data-word-high="${lbls.max_label}"
          min="${min}" max="${max}" step="${step}" value="${val}"
          aria-label="${esc(label)}" />
        <output class="slider-value">${val}</output>
        <span class="slider-word-wrap"><span class="slider-word" data-slider-word>${sliderWord(val, min, max, lbls)}</span></span>
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
  .range-slider { flex: 1 1 auto; min-width: 0;
    /* The thumb and filled track are painted by the UA, which uses the
       browser/HA accent and ignores every --evcc-* around it. One property
       hands it to the card's own accent; on a default install the two are
       the same value, so this only shows once a theme moves the accent. */
    accent-color: var(--evcc-accent, #3b82f6); }
  .slider-value {
    flex: 0 0 auto;
    padding: 3px 12px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface-subtle, var(--evcc-surface-subtle, rgba(255,255,255,0.04)));
    color: var(--text-primary);
    font-weight: 700; font-size: calc(0.80rem * var(--evcc-card-font-scale, 1));
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
    font-size: calc(0.78rem * var(--evcc-card-font-scale, 1)); font-weight: 600;
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

/**
 * Is an optional card section switched on?
 *
 * The `show_*` family (`show_profiles`, `show_scenes`, `show_dock`, `show_map`,
 * `show_companion`) all default ON and are all written by the editor as a plain
 * boolean, so the test is `!== false` and NOT truthiness: a config saved before an
 * option existed carries no key at all, and must keep behaving exactly as it did.
 * `!config.show_x` would hide the section on every one of those older configs.
 *
 * WHY THIS IS A FUNCTION AND NOT FOUR INLINE COMPARISONS. It is deliberately NOT a
 * sweep of the existing four — those are one comparison each, at one site each, and
 * rewriting working render paths to route through a helper buys nothing. It exists
 * because `show_companion` is asked TWICE, in two different places that must agree
 * (the control row and the sprite, see vacuum-map-host.js), and because the map host
 * cannot be imported outside a browser — it extends HTMLElement at module scope and
 * calls customElements.define, so neither node nor the Playwright harness bundle can
 * load it (harness/build.mjs externalises it by served URL). Putting the predicate
 * here is what gives it a test at all.
 */
export function cardSectionEnabled(config, key) {
  return (config ?? {})[key] !== false;
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
  .va-lang-btn { display: inline-flex; align-items: center; gap: 3px; padding: 3px 8px; border-radius: var(--evcc-radius-chip, 999px); border: 1px solid var(--evcc-border-default, rgba(255,255,255,0.12)); background: transparent; color: var(--evcc-text-muted, rgba(240,242,245,0.55)); font-size: calc(0.72rem * var(--evcc-card-font-scale, 1)); font-weight: 700; cursor: pointer; -webkit-tap-highlight-color: transparent; }
  .va-lang-btn:hover { color: var(--evcc-text-primary, #f0f2f5); }
  .va-lang-backdrop { position: fixed; inset: 0; z-index: 20; }
  .va-lang-menu { position: absolute; inset-inline-end: 0; top: calc(100% + 4px); z-index: 21; min-width: 168px; max-height: 264px; overflow: auto; background: var(--evcc-surface-card, #1c2127); border: 1px solid var(--evcc-border-default, rgba(255,255,255,0.14)); border-radius: var(--evcc-radius-inner, 8px); box-shadow: var(--evcc-shadow-card, 0 8px 24px rgba(0,0,0,0.4)); padding: 4px; }
  .va-lang-head { font-size: calc(0.64rem * var(--evcc-card-font-scale, 1)); font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--evcc-text-muted, rgba(240,242,245,0.5)); padding: 6px 8px 4px; }
  .va-lang-opt { display: block; width: 100%; text-align: start; padding: 6px 8px; border: none; background: transparent; color: var(--evcc-text-primary, #f0f2f5); font-size: calc(0.82rem * var(--evcc-card-font-scale, 1)); cursor: pointer; border-radius: 5px; }
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

/* ================================================================
   SECTIONS-VIEW GRID SIZING
   ================================================================
   Home Assistant's sections view warns "This card does not fully support resizing yet"
   for any custom card that does not declare `getGridOptions()`. All three of ours did
   not, so the warning showed on every one.

   THE NUMBERS ARE MEASURED, NOT PICKED. Read off the live cards on a real dashboard
   2026-11-16, and the grid they sit in was read the same way rather than taken from the
   docs -- which say 12 columns and are out of date. The section grid is TWENTY-FOUR
   columns of 21.25px with 8px gaps, and every one of our cards renders at 343px, which
   is exactly 12 columns (12 x 21.25 + 11 x 8 = 343). So `columns: 12` is not a new
   choice: it is what the cards already do, written down so HA stops guessing.

       eufy-room-card              343 x 489
       vacuum-agent-profile-card   343 x 268
       vacuum-agent-dashboard      343 x 1083

   `rows: "auto"` because all three are content-sized -- confirmed as valid by reading
   `hui-entities-card.getGridOptions()` on the same install, which returns
   {columns: 12, min_columns: 3, rows: "auto"}.

   `min_columns` IS DELIBERATELY PERMISSIVE. HIS CALL 2026-11-16: "min columns is going to
   vary based on names and other things lets the users tune". The first cut floored these
   at 6/6/8, guessed from English cards on one dashboard -- and the guess is unknowable in
   principle, because the narrowest usable width depends on the ROOM NAMES and the LOCALE,
   not on the card. The same card holding "Kitchen" and "Vysávání a vytírání" needs
   different room to breathe, and a floor derived from English would block precisely the
   users who most need to widen or narrow it.

   3 matches HA's own `hui-entities-card`, which is the most permissive built-in. The card
   does not get to decide that its user is wrong about their own dashboard; a bad width is
   visible immediately and reversible by dragging. */
export const GRID_ROOM_CARD      = { columns: 12, min_columns: 3, rows: "auto" };
export const GRID_PROFILE_CARD   = { columns: 12, min_columns: 3, rows: "auto" };
export const GRID_DASHBOARD_CARD = { columns: 12, min_columns: 3, rows: "auto" };
/* =========================================================
   LINK FROM A CARD'S EDITOR TO ITS THEME PANEL
   =========================================================
   His ask 2026-11-16, and it is the editor-over-YAML principle again: the tokens a card
   reads are edited in the panel's Theme tab, and nothing in the card's own config UI said
   where that was. Someone configuring a card had to already know.

   ONE IMPLEMENTATION, THREE EDITORS. The room, Dashboard Mode and Profile editors all
   need it, and three copies of a url-builder plus three click handlers is exactly the
   replica shape this repo keeps paying for.

   THE PANEL IS PER VACUUM. panels.py registers `eufy-vacuum-<object_id>` for each managed
   vacuum, so the link is only correct once a vacuum is chosen -- and only exists for a
   vacuum the integration manages. Both are checked before the link renders, because a
   button that navigates to a 404 is worse than no button.
   ========================================================= */

/**
 * The frontend path of a vacuum's panel.
 *
 * REPLICA RNPCW1RC -- the primary is panels.py's `panel_url_for`, which carries the
 * reasoning. The python builds the same string and is what Home Assistant actually
 * registers; the two cannot be derived from one another across the language boundary.
 * Pinned by [PNL-1], which reads the python and compares.
 */
export function themePanelPath(vacuumEntityId) {
  const objectId = String(vacuumEntityId ?? "").split(".").slice(-1)[0];
  return objectId ? `eufy-vacuum-${objectId}` : "";
}

/**
 * The view id the panel opens on arrival.
 *
 * REPLICA RN91VM9P -- the primary is VIEWS.THEME in src/render-cycle.js. Not imported:
 * this module is in the CARDS bundle, and render-cycle pulls the whole panel view
 * machinery in behind it. Pinned by [PNL-2].
 */
export const THEME_VIEW_HASH = "theme";

/**
 * Markup for the link, or "" when it would not work.
 *
 * Returns nothing unless a vacuum is chosen AND Home Assistant actually has that panel
 * registered. `hass.panels` is HA's own map of registered panels keyed by url path, which
 * is the direct truth rather than an inference from room switches -- a vacuum could be
 * mid-setup, or its panel removed, and the room switches would still be there.
 */
export function renderThemePanelLink({ t, hass, vacuumEntityId }) {
  const path = themePanelPath(vacuumEntityId);
  if (!path) return "";
  if (!hass?.panels || !hass.panels[path]) return "";
  return `
      <div class="field">
        <button type="button" class="va-theme-panel-link" data-va-theme-panel="${esc(path)}">
          ${t("room_card.editor_open_theme_panel")}
        </button>
        <div class="hint">${t("room_card.editor_open_theme_panel_hint")}</div>
      </div>`;
}

/** CSS for the link. Kept beside the markup so a copy cannot drift from a copy. */
export const THEME_PANEL_LINK_CSS = `
  .va-theme-panel-link {
    width: 100%;
    padding: 8px 10px;
    cursor: pointer;
    border: 1px solid var(--divider-color, rgba(255,255,255,0.12));
    border-radius: 6px;
    background: var(--secondary-background-color, #282828);
    color: var(--primary-text-color, #f0f2f5);
    font-size: 0.9rem;
    text-align: start;
  }
  .va-theme-panel-link:hover { border-color: var(--primary-color, #3b82f6); }
`;

/**
 * Wire the link. Navigates the Home Assistant way -- pushState plus a `location-changed`
 * event -- rather than setting location.href, which would reload the whole frontend.
 *
 * NOTE this leaves the card-edit dialog, because navigating does. That is the honest
 * behaviour for a link that says it opens another page, and it is why the button sits
 * under its own hint rather than beside a field someone is mid-edit in.
 */
export function wireThemePanelLink(shadowRoot) {
  const btn = shadowRoot?.querySelector("[data-va-theme-panel]");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const path = btn.dataset.vaThemePanel;
    if (!path) return;
    const url = `/${path}#${THEME_VIEW_HASH}`;
    try {
      window.history.pushState(null, "", url);
      window.dispatchEvent(new CustomEvent("location-changed", {
        bubbles: true, composed: true, detail: { replace: false },
      }));
    } catch (_) {
      // A frontend that refuses pushState still gets the user there.
      window.location.assign(url);
    }
  });
}

/* =========================================================
   PER-INSTANCE THEME VALUES FROM YAML  (`theme_vars`)
   =========================================================
   His ruling 2026-11-16: "YAML can be the winner its set directly after all". This is the
   TOP rung of the card styling ladder, above the Vacuum Agent theme, because it is set on
   one card instance rather than on every card a theme touches:

     1. theme_vars on THIS card          <- here
     2. the Vacuum Agent theme            (va_theme: true)
     3. --evcc-card-<card>-<thing>        (themes.yaml, per card type)
     4. --evcc-card-<thing>               (themes.yaml, all cards)
     5. --ha-card-*                       (the Home Assistant theme)
     6. the shipped default

   A GENERIC MAP, not named options: "everything we exposed" is the whole registry and it
   grows every release, so keying by token name covers all of it -- including tokens that
   do not exist yet -- while the shipped config surface stays one key.
   ========================================================= */

/** The card-config key carrying per-instance theme values. */
export const CARD_THEME_VARS_KEY = "theme_vars";

/* A token name, with or without the leading dashes. Deliberately a SHAPE check rather
   than a lookup against the registry: importing it would pull the whole token layer into
   the cards bundle, and a shape check also accepts tokens added after this shipped. */
const THEME_VAR_NAME = /^--evcc-[a-z0-9]+(?:-[a-z0-9]+)*$/;

/* A custom property holds an arbitrary token stream, so a value containing `;` or `}`
   cannot escape this element -- it only makes the declarations that var() it invalid at
   computed-value time. Rejected anyway: the failure is invisible and far from its cause,
   and "my card went blank" is a worse answer than "that value was ignored". */
const THEME_VAR_VALUE_REJECT = /[;{}]|<\//;

/**
 * Canonical `--evcc-…` form of a theme-var name, or null when it is not one.
 * Accepts the YAML-friendly `evcc-card-frame-background` as well as `--evcc-…`, because
 * Home Assistant themes are written without the dashes and people copy that habit.
 */
export function normaliseThemeVarName(name) {
  const raw = String(name ?? "").trim();
  if (!raw) return null;
  const dashed = raw.startsWith("--") ? raw : `--${raw}`;
  return THEME_VAR_NAME.test(dashed) ? dashed : null;
}

/**
 * The usable entries of a card's `theme_vars`, plus the ones that were refused.
 * @returns {{vars: Array<[string, string]>, rejected: string[]}}
 */
export function readCardThemeVars(config) {
  const raw = (config ?? {})[CARD_THEME_VARS_KEY];
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return { vars: [], rejected: [] };

  const vars = [];
  const rejected = [];
  for (const [name, value] of Object.entries(raw)) {
    const key = normaliseThemeVarName(name);
    if (!key) { rejected.push(String(name)); continue; }
    if (value === null || value === undefined || value === "") { continue; }
    const v = String(value);
    if (THEME_VAR_VALUE_REJECT.test(v)) { rejected.push(String(name)); continue; }
    vars.push([key, v]);
  }
  return { vars, rejected };
}

/**
 * Write a card's `theme_vars` onto `host` as inline properties, and drop any it set last
 * time that have since gone.
 *
 * MUST RUN AFTER applyVaThemeToCard. Both write inline on the same element and the theme
 * removeProperty()s every registry token it does not carry, so running this first would
 * have the theme erase it on the very same tick.
 *
 * @param {HTMLElement} host
 * @param {object} config
 * @param {Set<string>|undefined} previous names written by the last call
 * @param {(hex: string) => string|null} [animalComponents] conversion for --evcc-animal-*
 * @returns {Set<string>} the names written this time; pass it back as `previous`
 */
export function applyCardThemeVars(host, config, previous, animalComponents) {
  const applied = new Set();
  if (!host || !host.style) return applied;

  const { vars } = readCardThemeVars(config);
  for (const [key, value] of vars) {
    const out = (animalComponents && key.startsWith("--evcc-animal-"))
      ? (animalComponents(value) ?? value)
      : value;
    host.style.setProperty(key, out);
    applied.add(key);
  }

  // Removing what we previously set is what makes editing the YAML live: without it a
  // deleted key keeps painting until a reload, and the card disagrees with its own config.
  if (previous) {
    for (const key of previous) {
      if (!applied.has(key)) host.style.removeProperty(key);
    }
  }
  return applied;
}
