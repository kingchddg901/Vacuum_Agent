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
import {
  buildRenderContext,
  renderHeader,
  renderView,
  VIEWS,
  VIEW_ORDER,
} from "../src/render-cycle.js";
import { STYLES } from "../src/styles/index.js";
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

function frameHtml(view, headerHtml, viewHtml, freeze) {
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
 * @returns {{view,ok,error?,stack?,headerLen?,viewLen?,misses:{state:string[],hass:string[]}}}
 */
function render(view, opts = {}) {
  const { bundle = {}, overrides = {}, controller = null, width = 500, freeze = false } = opts;

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

    const root = document.getElementById("root");
    root.innerHTML = "";
    const host = document.createElement("div");
    host.id = "evcc-host";
    host.style.width = `${width}px`;
    root.appendChild(host);

    const shadow = host.attachShadow({ mode: "open" });
    shadow.innerHTML = frameHtml(view, headerHtml, viewHtml, freeze);

    // Apply the bundle exactly as src/styles/apply-theme.js does:
    // inline custom properties on the shadow host.
    for (const [key, value] of Object.entries(bundle)) {
      if (value !== null && value !== undefined && value !== "") {
        host.style.setProperty(key, value);
      }
    }

    result.ok = true;
    result.headerLen = headerHtml.length;
    result.viewLen = viewHtml.length;
  } catch (err) {
    result.ok = false;
    result.error = String((err && err.message) || err);
    result.stack = err && err.stack
      ? String(err.stack).split("\n").slice(0, 8).join("\n")
      : null;
  }

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

window.__evcc = {
  version: 1,
  VIEWS,
  VIEW_ORDER,
  render,
  renderGallery,
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
  })),
};
