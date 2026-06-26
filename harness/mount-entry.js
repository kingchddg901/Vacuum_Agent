/**
 * ============================================================
 * HARNESS: HEADLESS MOUNT ENTRY (browser bundle)
 * ============================================================
 *
 * Bundled by harness/build.mjs (esbuild → harness/dist/mount.js,
 * IIFE) and loaded into a Playwright Chromium page. Exposes
 * `window.__evcc` so the Node side can render any tab and screenshot
 * it.
 *
 * THE LOAD-BEARING PROPERTY
 * -------------------------
 * Renderers are pure: `render(ctx) -> HTML string`, reading state
 * only through the narrow `ctx.state` accessor. So we recreate the
 * EXACT ship path — `renderHeader(ctx) + renderView(ctx)` composed
 * into the same shadow-DOM frame as src/main.js, with the same
 * STYLES injected — and feed it a stub `state` plus a flat
 * `--evcc-*` bundle. Identical path, recolored only by the bundle:
 * zero test/prod skew. The harness is the only genuinely new piece;
 * everything it renders already ships.
 *
 * Structure and color are orthogonal inputs to one render: the
 * fixture (stub state) decides which states are present; the bundle
 * decides their color. Neither knows about the other.
 *
 * ============================================================
 */

import { VacuumCardRenderers } from "../src/renderers/index.js";
import { VacuumCardState } from "../src/state/index.js";
import {
  buildRenderContext,
  renderHeader,
  renderView,
  VIEWS,
  VIEW_ORDER,
} from "../src/render-cycle.js";
import { STYLES, MODAL_HOST_STYLES } from "../src/styles/index.js";
import { makeStubState, makeNullObject } from "./fixtures/stub-state.js";
import { GALLERY } from "./fixtures/gallery.js";
import { SEMANTIC_COLOR_TOKENS } from "./semantic-tokens.js";
import { BADGE_MARK_PATHS, MARK_VIEWBOX } from "../src/renderers/badge-marks.js";
import { detectFloorScope, clampThemeScalars } from "../src/theme-tokens/floor-scope.js";
import { THEME_TOKEN_MAP } from "../src/theme-tokens/index.js";

/* =========================================================
   GLOBAL STUB: window.AnimalSVG
   =========================================================
   The one known purity breach: src/renderers/rooms.js reads
   window.AnimalSVG directly at render time (a renderer reaching
   outside its ctx contract). We stub it headlessly; routing it
   through ctx is the idiomatic fix, tracked as a follow-up.
   ========================================================= */

if (typeof window !== "undefined" && !window.AnimalSVG) {
  window.AnimalSVG = {
    list: () => ["cat", "dog", "raccoon", "parrot", "snake"],
    has: () => true,
    get: (name) => ({
      id: name,
      key: name,
      label: name,
      name,
      viewBox: "0 0 100 100",
      svg: `<svg viewBox="0 0 100 100" aria-hidden="true"></svg>`,
      markup: `<svg viewBox="0 0 100 100" aria-hidden="true"></svg>`,
      paths: [],
    }),
  };
}

/* =========================================================
   HA `ha-card` CHROME SHIM (harness-only)
   =========================================================
   The real host frame is <ha-card>, a Home Assistant element that
   supplies display:block + a card background/border/shadow. It does
   not exist headlessly, so we emulate its chrome here. This stands
   in for HA — it is NOT shipped. Card content styling still comes
   entirely from the real STYLES (`:host` + `.evcc-*`).
   ========================================================= */

const HA_CARD_SHIM = `
  ha-card {
    display: block;
    background: var(--ha-card-background, var(--card-background-color, #1c2127));
    border-radius: var(--ha-card-border-radius, 12px);
    border: 1px solid var(--ha-card-border-color, rgba(255, 255, 255, 0.08));
    box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0, 0, 0, 0.25));
    color: var(--primary-text-color, #e1e2e4);
    overflow: hidden;
  }
`;

// Freeze animations/transitions for deterministic capture (Wave 3 uses
// this; harmless in Wave 1). Applied only when opts.freeze is set.
const FREEZE_STYLE = `
  *, *::before, *::after {
    animation-delay: 0s !important;
    animation-duration: 0s !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0s !important;
    transition-delay: 0s !important;
    caret-color: transparent !important;
  }
`;

/* =========================================================
   FRAME (byte-faithful to src/main.js _ensureShellFrame)
   ========================================================= */

function frameHtml(view, headerHtml, viewHtml, freeze, modalHtml) {
  // Body-level modal host, mirroring main.js _renderModals(): in the live card,
  // modals mount to document.body with their OWN MODAL_HOST_STYLES (the shadow
  // modalStyles are inert). We reproduce that as a sibling of <ha-card> in the
  // shadow root so it inherits the host's --evcc-* tokens and Playwright's
  // shadow-piercing clip can crop straight to the modal.
  const modalBlock = modalHtml
    ? `<style data-evcc-modal-host-style>${MODAL_HOST_STYLES}</style>`
      + `<div class="evcc-modal-host" data-evcc-modal-host>${modalHtml}</div>`
    : "";
  return `
    <style data-evcc-style-root>${STYLES}</style>
    <style data-evcc-harness-chrome>${HA_CARD_SHIM}</style>
    ${freeze ? `<style data-evcc-harness-freeze>${FREEZE_STYLE}</style>` : ""}

    <ha-card>
      <div class="evcc-shell" data-viewport="desktop">
        <div data-evcc-header-root>${headerHtml}</div>
        <div class="evcc-view-stage" data-evcc-view-stage data-view="${view}">
          <div class="evcc-view-root" data-evcc-view-root="${view}" aria-hidden="false">${viewHtml}</div>
        </div>
        <div data-evcc-bottom-nav-root></div>
        <div data-evcc-mobile-overlay-root></div>
      </div>
    </ha-card>
    ${modalBlock}
  `;
}

/* =========================================================
   RENDER ONE TAB
   ========================================================= */

/**
 * Render a single tab headlessly into #root's shadow DOM and apply a
 * token bundle. Returns a serialisable result (never throws to the
 * page) so the Node side can assert on it.
 *
 * @param {string} view - a VIEWS value (e.g. "rooms").
 * @param {object} [opts]
 * @param {object} [opts.bundle]    - flat `--evcc-*` -> value map (default {}).
 * @param {object} [opts.overrides] - per-accessor real state returns.
 * @param {number} [opts.width]     - host width in px (default 500).
 * @param {boolean}[opts.freeze]    - freeze animations for determinism.
 * @param {string} [opts.modal]     - a renderer method name (e.g.
 *   "renderExternalWizardModal") to render as a body-level modal host. Opt-in
 *   because the stub null-object makes every modal's isOpen() accessor truthy.
 * @returns {{view,ok,error?,stack?,headerLen?,viewLen?,misses:{state:string[],hass:string[]}}}
 */
// A fixed instant for DETERMINISTIC relative-time rendering. The live-progress
// overlay (and any "N ago" pill) computes against Date.now(), so without this the
// gallery-rooms-active baseline flaps by a line as wall-clock advances between
// runs. Freezing Date.now() + argless `new Date()` — while leaving `new Date(iso)`
// parsing of fixture timestamps intact — pins every render to the same moment.
// Active only when `freeze` is set (every visual-regression render passes it).
const FROZEN_NOW = Date.parse("2026-06-07T12:00:00Z");
function freezeClock() {
  const RealDate = Date;
  class FrozenDate extends RealDate {
    constructor(...args) { super(...(args.length ? args : [FROZEN_NOW])); }
    static now() { return FROZEN_NOW; }
  }
  globalThis.Date = FrozenDate;
  return () => { globalThis.Date = RealDate; };
}

function render(view, opts = {}) {
  const { bundle = {}, overrides = {}, controller = null, width = 500, freeze = false, modal = null } = opts;
  const restoreClock = freeze ? freezeClock() : null;

  const stateMisses = new Set();
  const hassMisses = new Set();
  const result = { view, ok: false, misses: { state: [], hass: [] } };

  try {
    const state = makeStubState({ overrides, record: stateMisses });

    // Minimal card stub: renderers read exactly _config/_state/_renderers/
    // _view/_mobileMoreOpen. _hass is a recording null-object so any direct
    // hass reach (another contract breach) is surfaced, not silently fed.
    const card = {
      _config: {},
      _state: state,
      _renderers: null,
      _view: view,
      _mobileMoreOpen: false,
      _learningController: controller,
      _hass: makeNullObject(hassMisses, "_hass"),
    };
    const renderers = new VacuumCardRenderers(card);
    card._renderers = renderers;

    const ctx = buildRenderContext(card); // real builder; view comes from card._view
    const headerHtml = renderHeader(ctx);
    const viewHtml = renderView(ctx);
    // Body-level modals (main.js _renderModals) live outside renderView, so a
    // fixture that wants one names its renderer via opts.modal. We render only
    // that one — NOT every modal renderer — because the null-object would make
    // each modal's isOpen() guard truthy and emit garbage for unrelated shots.
    const modalHtml =
      modal && typeof renderers[modal] === "function" ? renderers[modal](ctx) : "";

    const root = document.getElementById("root");
    root.innerHTML = "";
    const host = document.createElement("div");
    host.id = "evcc-host";
    host.style.width = `${width}px`;
    root.appendChild(host);

    const shadow = host.attachShadow({ mode: "open" });
    shadow.innerHTML = frameHtml(view, headerHtml, viewHtml, freeze, modalHtml);

    // Apply the bundle exactly as src/styles/apply-theme.js does:
    // inline custom properties on the shadow host.
    for (const [key, value] of Object.entries(bundle)) {
      if (value !== null && value !== undefined && value !== "") {
        host.style.setProperty(key, value);
      }
    }

    // Mirror apply-theme.js step 2 (applyDynamicTheme(card._modalHost)):
    // the body-level modal host gets the resolved layer on its OWN node
    // too, so an explicit --evcc-modal-* override outranks the canonical-
    // derived stylesheet defaults in MODAL_HOST_STYLES — exactly as it
    // does on the live card.
    const modalHostEl = modalHtml ? shadow.querySelector("[data-evcc-modal-host]") : null;
    if (modalHostEl) {
      for (const [key, value] of Object.entries(bundle)) {
        if (value !== null && value !== undefined && value !== "") {
          modalHostEl.style.setProperty(key, value);
        }
      }
    }

    result.ok = true;
    result.headerLen = headerHtml.length;
    result.viewLen = viewHtml.length;
    result.modalLen = modalHtml.length;
  } catch (err) {
    result.ok = false;
    result.error = String((err && err.message) || err);
    result.stack = err && err.stack
      ? String(err.stack).split("\n").slice(0, 8).join("\n")
      : null;
  }

  if (restoreClock) restoreClock();
  result.misses.state = [...stateMisses].sort();
  result.misses.hass = [...hassMisses].sort();
  return result;
}

/* =========================================================
   EXPOSE
   ========================================================= */

/**
 * Render a named gallery entry (a fixture that forces every colored
 * branch of a tab). Returns the render result plus the entry's clip
 * selector and label for the Node-side capture.
 */
function renderGallery(id, opts = {}) {
  const entry = GALLERY.find((g) => g.id === id);
  if (!entry) return { id, ok: false, error: `unknown gallery id: ${id}`, misses: { state: [], hass: [] } };
  const res = render(entry.view, {
    overrides: entry.state,
    controller: entry.controller ?? null,
    bundle: { ...(entry.bundle || {}), ...(opts.bundle || {}) },
    width: opts.width,
    freeze: opts.freeze,
    modal: entry.modal ?? null,
  });
  return { ...res, id, clip: entry.clip ?? null, label: entry.label };
}

/**
 * Ingest gate — turn an UNTRUSTED theme export into a safe flat bundle, the
 * same validate + clamp path import_theme uses. Pure data in, pure data out:
 *   - keep only known registry `--evcc-*` keys (drops unknown keys AND
 *     unknown floor-type namespaces this build doesn't recognise);
 *   - clamp bounded scalars to each token's range (clampThemeScalars);
 *   - drop non-primitive values; never eval.
 * The returned values are applied downstream via host.style.setProperty
 * (CSS-validated), never injected into HTML — so running a stranger's export
 * in CI is safe.
 *
 * @param {object} envelope - parsed export ({ theme:{tokens,colors,alpha}, scope? }).
 * @returns {{ bundle: object, scope: string[], report: object }}
 */
function ingestTheme(envelope) {
  const report = { ok: false, reason: null, keyCount: 0, clamped: 0, skippedKeys: [], unknownFloor: [] };
  if (!envelope || typeof envelope !== "object" || Array.isArray(envelope)) {
    report.reason = "not an object";
    return { bundle: {}, scope: [], report };
  }
  if (!envelope.theme || typeof envelope.theme !== "object") {
    report.reason = "missing theme";
    return { bundle: {}, scope: [], report };
  }

  report.unknownFloor = detectFloorScope(envelope).unknown;
  const { envelope: clamped, corrected } = clampThemeScalars(envelope, THEME_TOKEN_MAP);
  report.clamped = corrected;

  const theme = clamped.theme || {};
  const bundle = {};
  for (const bucket of ["tokens", "colors", "alpha"]) {
    const dict = theme[bucket];
    if (!dict || typeof dict !== "object") continue;
    for (const [key, value] of Object.entries(dict)) {
      if (typeof key !== "string" || !key.startsWith("--evcc-") || !THEME_TOKEN_MAP[key]) {
        report.skippedKeys.push(key);
        continue;
      }
      if (value == null || typeof value === "object" || typeof value === "function") {
        report.skippedKeys.push(key);
        continue;
      }
      bundle[key] = value;
    }
  }
  report.keyCount = Object.keys(bundle).length;
  report.ok = true;
  const scope = Array.isArray(envelope.scope) ? envelope.scope.slice() : detectFloorScope(envelope).known;
  return { bundle, scope, report };
}

/**
 * Render the Themes (presets) grid with a REAL state seeded with a theme
 * library. The stub null-object can't exercise the facet filter (every accessor
 * returns a truthy null-object), so this gives the theme picker a faithful
 * fixture: derived tags, facet bar, search, and Browse link rendered as they
 * ship. `themes` is an array of library entries ({id,name,tokens,colors,alpha,
 * source?}); `bundle` themes the host; `activeThemeId` marks one Active.
 */
function renderThemePresets(themes, opts = {}) {
  const { bundle = {}, width = 760, height = null, activeThemeId = null, facets = null, search = "", editId = null, filtersOpen = false, themeMode = null, deviceThemeId = null } = opts;
  const result = { ok: false };
  try {
    const list = Array.isArray(themes) ? themes : [];
    const card = {
      _config: {},
      _renderers: null,
      _view: "theme",
      _mobileMoreOpen: false,
      _hass: makeNullObject(new Set(), "_hass"),
    };
    const state = new VacuumCardState({}, {});
    const library = {};
    for (const t of list) library[t.id] = t;
    state.setThemeLibrary({
      library,
      themes: list.map((t) => ({ id: t.id, name: t.name })),
      default_theme_id: list[0]?.id || null,
    });
    state.setThemeSubTab("presets");
    if (activeThemeId) state.applyThemeActivation(activeThemeId, { clearDraft: true });
    // Pre-seed the filter exactly as the binding would (togglePresetFacet /
    // setPresetSearchQuery), so a screenshot can show a filtered state and the
    // returned `shown` exercises filteredPresetIds in-browser.
    if (facets) {
      for (const [facet, values] of Object.entries(facets)) {
        for (const v of values) state.togglePresetFacet(facet, v);
      }
    }
    if (search) state.setPresetSearchQuery(search);
    if (editId) state.setPresetTagEditId(editId);
    if (filtersOpen) state.togglePresetFilters();
    if (themeMode === "device") {
      state.setThemeMode("device");
      if (deviceThemeId) state.setDeviceThemeId(deviceThemeId);
    }
    result.shown = state.filteredPresetIds();
    card._state = state;
    const renderers = new VacuumCardRenderers(card);
    card._renderers = renderers;

    const presetsHtml = renderers._renderThemePresets(state._ensureThemeState());
    const viewHtml = `<div class="evcc-view evcc-view--theme"><div class="evcc-view-content">${presetsHtml}</div></div>`;

    const root = document.getElementById("root");
    root.innerHTML = "";
    const host = document.createElement("div");
    host.id = "evcc-host";
    host.style.width = `${width}px`;
    // A fixed height lets the grid's scroll container flex (mirrors the live
    // card, where the view sits in a bounded shell); omit for natural height.
    if (height) host.style.height = `${height}px`;
    root.appendChild(host);
    const shadow = host.attachShadow({ mode: "open" });
    shadow.innerHTML = frameHtml("theme", "", viewHtml, false, "");
    for (const [key, value] of Object.entries(bundle)) {
      if (value !== null && value !== undefined && value !== "") host.style.setProperty(key, value);
    }
    result.ok = true;
  } catch (err) {
    result.ok = false;
    result.error = String((err && err.message) || err);
    result.stack = err && err.stack ? String(err.stack).split("\n").slice(0, 8).join("\n") : null;
  }
  return result;
}

window.__evcc = {
  version: 1,
  VIEWS,
  VIEW_ORDER,
  render,
  renderGallery,
  renderThemePresets,
  VacuumCardState, // exposed so tooling can drive real state (e.g. per-device theme)
  semanticTokens: SEMANTIC_COLOR_TOKENS,
  badgeMarks: BADGE_MARK_PATHS,
  markViewBox: MARK_VIEWBOX,
  ingestTheme,
  tokenMap: THEME_TOKEN_MAP,
  gallery: GALLERY.map((g) => ({
    id: g.id,
    view: g.view,
    label: g.label,
    tokens: g.tokens,
    clip: g.clip ?? null,
    modal: g.modal ?? null,
  })),
};
