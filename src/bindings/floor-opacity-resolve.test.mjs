// FTX-VEIN-1 / R3-BUG-2 — the map must resolve a floor layer's opacity the way the
// CARD's CSS does: hand the token/default expression to the browser and read the
// computed number back. It used to `parseFloat` the raw text instead.
//
// The bug that motivated this: marble's two vein layers point `opacityToken` at
// `--evcc-floor-marble-vein-{major,minor}-opacity-eff`, tokens nothing defines in CSS,
// with a `clamp(0,calc(var(--evcc-floor-marble-vein-opacity,0.5) + …),1)` STRING as the
// registry default. `parseFloat("clamp(...)")` is NaN, so the map fell back to 1 and
// composited both veins at FULL strength, while the card — which bakes the same
// expression into `var(token, default)` and lets CSS evaluate it — rendered 0.5 / 0.38.
// The three theme-editor sliders feeding that clamp therefore moved the card swatch and
// nothing on the map.
//
// ABOUT THE STUB: node has no CSS engine, so `getComputedStyle` here REPLAYS values
// measured in real Chromium via Playwright rather than reinventing CSS semantics:
//
//   opacity: clamp(0,calc(var(--…vein-opacity,0.5) + var(--…major-opacity,0)),1)   -> "0.5"
//   opacity: clamp(0,calc(var(--…vein-opacity,0.5) + var(--…minor-opacity,-0.12)),1) -> "0.38"
//   with --…vein-opacity themed to 0.8                                    -> "0.8" / "0.68"
//   opacity: 0.87                                                          -> "0.87"
//   opacity: not-a-number      -> REJECTED (el.style.opacity stays "")     -> computed "1"
//
// So what these specs actually prove is the WIRING — that the expression reaches a CSS
// evaluator at all — which is precisely what was missing. The evaluation itself is a
// browser fact, verified separately.
//
// Run: node --test src/bindings/floor-opacity-resolve.test.mjs
//
// Coverage (FVO = Floor Vein Opacity):
//   [FVO-1] a clamp()/calc()/var() default resolves to its CSS value, not the NaN->1 fallback
//   [FVO-2] the raw expression is ASSIGNED to style.opacity (handed to CSS, not parsed)
//   [FVO-3] a themed master token reaches the map (the editor slider does something)
//   [FVO-4] a plain numeric default is unchanged — the fix's blast radius is marble only
//   [FVO-5] a value CSS rejects falls back to the registry default, not to a bogus read
//   [FVO-6] with no DOM at all the numeric path still works

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyMapBindings } from "./map.js";

const MAJOR = "clamp(0,calc(var(--evcc-floor-marble-vein-opacity,0.5) + var(--evcc-floor-marble-vein-major-opacity,0)),1)";
const MINOR = "clamp(0,calc(var(--evcc-floor-marble-vein-opacity,0.5) + var(--evcc-floor-marble-vein-minor-opacity,-0.12)),1)";

/** Measured in Chromium — see the header. `null` = CSS rejects the value. */
const CHROME = new Map([
  [MAJOR, "0.5"],
  [MINOR, "0.38"],
  ["0.87", "0.87"],
  ["90%", "0.9"],
  ["not-a-number", null],
]);

/**
 * @param {object} [opts]
 * @param {Record<string,string>} [opts.tokens] - custom properties the probe "inherits".
 * @param {Map<string,string|null>} [opts.css]  - value -> computed opacity.
 */
function makeBindings({ tokens = {}, css = CHROME } = {}) {
  const proto = {};
  applyMapBindings(proto);
  const bindings = Object.create(proto);

  const parent = { children: [] };
  parent.appendChild = (el) => { el.parentNode = parent; parent.children.push(el); };
  parent.removeChild = (el) => { el.parentNode = null; };
  const host = { parentNode: parent };

  const assigned = [];   // every value handed to style.opacity, in order
  const el = {
    parentNode: null,
    setAttribute() {},
    style: {
      cssText: "",
      color: "",
      _opacity: "",
      get opacity() { return this._opacity; },
      set opacity(v) {
        assigned.push(v);
        // A browser IGNORES a value it cannot parse, leaving the property untouched;
        // an accepted one sticks. That distinction is what the resolver's guard reads.
        if (v === "") { this._opacity = ""; return; }
        this._opacity = css.get(v) === null ? "" : v;
      },
    },
  };

  globalThis.document = { createElement: () => el };
  globalThis.getComputedStyle = (node) => ({
    getPropertyValue: (name) => tokens[name] ?? "",
    // Only meaningful for the probe; mirrors Chromium's default of "1".
    get opacity() { return node === el && el.style._opacity ? css.get(el.style._opacity) ?? "1" : "1"; },
  });

  return { bindings, host, assigned };
}

function clearDom() {
  delete globalThis.document;
  delete globalThis.getComputedStyle;
}

test("[FVO-1] a clamp()/calc()/var() default resolves to its CSS value, not the NaN->1 fallback", () => {
  const { bindings, host } = makeBindings();
  try {
    assert.equal(
      bindings._resolveFloorOpacity("--evcc-floor-marble-vein-major-opacity-eff", MAJOR, host),
      0.5,
      "the vein composited at full strength — parseFloat swallowed the clamp again",
    );
    assert.equal(
      bindings._resolveFloorOpacity("--evcc-floor-marble-vein-minor-opacity-eff", MINOR, host),
      0.38,
    );
  } finally { clearDom(); }
});

test("[FVO-2] the raw expression is handed to CSS, not parsed", () => {
  const { bindings, host, assigned } = makeBindings();
  try {
    bindings._resolveFloorOpacity("--evcc-floor-marble-vein-major-opacity-eff", MAJOR, host);
    assert.ok(
      assigned.includes(MAJOR),
      "the clamp expression never reached style.opacity — nothing evaluated it",
    );
  } finally { clearDom(); }
});

test("[FVO-3] a themed master token reaches the map", () => {
  // The editor writes --evcc-floor-marble-vein-opacity; the -eff token stays undefined,
  // so the registry default is what gets evaluated — against the themed var.
  const css = new Map([[MAJOR, "0.8"], [MINOR, "0.68"]]);
  const { bindings, host } = makeBindings({ css });
  try {
    assert.equal(
      bindings._resolveFloorOpacity("--evcc-floor-marble-vein-major-opacity-eff", MAJOR, host),
      0.8,
      "the Marble Vein Opacity slider still does nothing on the map",
    );
  } finally { clearDom(); }
});

test("[FVO-4] a plain numeric default is unchanged (blast radius is marble only)", () => {
  const { bindings, host } = makeBindings();
  try {
    assert.equal(
      bindings._resolveFloorOpacity("--evcc-floor-tile-face-opacity", "0.87", host),
      0.87,
    );
    assert.equal(bindings._resolveFloorOpacity("--evcc-floor-tile-face-opacity", "90%", host), 0.9);
  } finally { clearDom(); }
});

test("[FVO-5] a value CSS rejects falls back to the registry default", () => {
  const { bindings, host } = makeBindings({ tokens: { "--evcc-floor-tile-face-opacity": "not-a-number" } });
  try {
    assert.equal(
      bindings._resolveFloorOpacity("--evcc-floor-tile-face-opacity", "0.87", host),
      0.87,
      "a junk theme value must not win — the registry default is the floor",
    );
  } finally { clearDom(); }
});

test("[FVO-6] with no DOM the numeric path still works", () => {
  const proto = {};
  applyMapBindings(proto);
  const bindings = Object.create(proto);
  clearDom();
  assert.equal(bindings._resolveFloorOpacity("--x", "0.62", null), 0.62);
  assert.equal(bindings._resolveFloorOpacity("--x", "nonsense", null), 1);
});
