// Run: node --test src/renderers/mascot-bar-collapse.test.mjs
//
// [MBC-*] THE COMPANION CONTROL ROW COLLAPSES, AND THE CARET SURVIVES IT.
//
// ISSUE #82. The reporter sent a screenshot with a red line drawn under the whole mascot
// row — the animal picker, the size slider and the follow/physics toggles — and asked for
// an option to hide it. The option looked like it already existed: there is a paw toggle
// with a per-robot key, a binding and a render gate, and two separate reviews concluded
// "already possible, tap the paw".
//
// It was not possible. The paw hides the SPRITE. `_renderMapAnimalControls` is gated on
// `isMapViewActive` and never on the companion, so every control stayed on screen steering
// something that was no longer drawn. Nothing in the code says otherwise; only the
// screenshot does, which is why neither review caught it.
//
// THE ONE THAT CAN STRAND A USER is [MBC-3]. The caret that collapses the row lives INSIDE
// the row, so the hide rule has to exclude it by `data-action`. That makes the renderer's
// attribute and the CSS selector a replica pair: rename either alone and the collapse
// swallows its own control, leaving no way to expand it again — on a per-session setting,
// with no error, on a surface the user has already said they do not want. The suite that
// checks the class is applied cannot see that at all.
//
// Coverage:
//   [MBC-1] expanded is the default, and every control is rendered
//   [MBC-2] collapsed adds the modifier class, and the caret flips its glyph and aria
//   [MBC-3] the CSS hide rule EXCLUDES exactly the caret the renderer emits (replica pair)
//   [MBC-4] the collapse PERSISTS per robot, and absent storage reads as EXPANDED
//   [MBC-5] a storage that throws degrades to expanded rather than taking the row away

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyMapRenderers } from "./map.js";
import { mapStyles } from "../styles/map.js";
import { applyMapState } from "../state/map.js";

/** The one attribute both halves have to agree on. Written once here on purpose: if this
 *  test spelled it twice it could pass while the two sides disagreed. */
const CARET_ACTION = "toggle-mascot-bar";

// The animal picker reads `window.AnimalSVG?.list?.()`. Optional chaining guards the
// PROPERTY, not the `window` reference itself, so in node the bare identifier throws.
// Stubbed rather than guarded in the renderer: it only ever runs in a browser, and
// softening production code to suit a test harness is the wrong direction. An empty
// object makes it take its own documented fallback roster.
globalThis.window = globalThis.window ?? {};

function makeRenderer() {
  const proto = {};
  applyMapRenderers(proto);
  const r = Object.create(proto);
  // Translate to the KEY, not to English: the assertions below must not depend on
  // copy, and a missing key shows up as the key rather than as a silent empty string.
  r.t = (k) => k;
  r.tVocab = (_g, v, fb) => String(v ?? fb ?? "");
  r.escapeHtml = (v) => String(v ?? "");
  return r;
}

const state = (collapsed) => ({
  isMascotBarCollapsed: () => collapsed,
  mapAnimalEnabled: () => true,
  mapAnimalScale: () => 1.0,
  mapAnimalFollowsRobot: () => false,
  mapAnimalMoonwalk: () => false,
  mapAnimalId: () => "",
  vacuumObjectId: () => "robot",
});

test("[MBC-1] expanded by default, with the whole control row present", () => {
  const html = makeRenderer()._renderMapAnimalControls(state(false));

  assert.ok(html.includes("evcc-mascot-group"), "the group must render");
  assert.ok(!html.includes("evcc-mascot-group--collapsed"),
    "expanded is the default — a fresh session must not hide controls the user never collapsed");
  assert.ok(html.includes('aria-expanded="true"'));

  // The controls the reporter drew a line under. If a later edit omits them from the
  // DOM instead of hiding them by class, this is the test that says so.
  for (const action of ["map-animal-select", "map-animal-scale", "map-animal-toggle",
                        "map-animal-follow-toggle", "map-animal-moonwalk-toggle"]) {
    assert.ok(html.includes(action), `${action} must be present when expanded`);
  }
});

test("[MBC-2] collapsed sets the modifier class, and the caret reverses", () => {
  const open = makeRenderer()._renderMapAnimalControls(state(false));
  const shut = makeRenderer()._renderMapAnimalControls(state(true));

  assert.ok(shut.includes("evcc-mascot-group--collapsed"), "collapsed must carry the modifier");
  assert.ok(shut.includes('aria-expanded="false"'));

  // Glyph and label both reverse, and they are checked together: a caret that turns but
  // keeps saying "hide" is the shape a screen-reader user cannot recover from.
  assert.ok(open.includes("▾") && open.includes("rooms.mascot_bar_hide"),
    "expanded: down caret, and the label offers to HIDE");
  assert.ok(shut.includes("▸") && shut.includes("rooms.mascot_bar_show"),
    "collapsed: right caret, and the label offers to SHOW");
});

test("[MBC-3] the hide rule excludes exactly the caret the renderer emits", () => {
  // THE STRANDING GUARD. The caret sits inside the group it collapses, so the CSS must
  // carve it out by data-action. Renderer and stylesheet are a replica pair; this is the
  // only place they are compared.
  const html = makeRenderer()._renderMapAnimalControls(state(true));

  assert.ok(html.includes(`data-action="${CARET_ACTION}"`),
    "the renderer must emit the caret with the agreed data-action");

  const rule = `.evcc-mascot-group--collapsed > :not([data-action="${CARET_ACTION}"])`;
  assert.ok(mapStyles.includes(rule),
    `the stylesheet must hide the collapsed row while EXCLUDING the caret.\n` +
    `  expected selector: ${rule}\n` +
    `  Rename the data-action on one side only and the collapse swallows its own control:\n` +
    `  the row hides, the caret hides with it, and nothing can expand it again.`);

  // And the caret is still IN the markup when collapsed — the class hides its siblings,
  // never itself. If this ever goes red the user has no way back.
  assert.ok(html.includes(CARET_ACTION),
    "the caret must survive the collapse; it is the only control that can undo it");
});


/* ---------------------------------------------------------------------------
   Persistence. State layer rather than renderer, but it lives here because it is
   the same feature and the same failure: a row the user said they do not want,
   reappearing (or vanishing) for a reason nothing on screen explains.
   --------------------------------------------------------------------------- */

function makeState(store) {
  const proto = {};
  applyMapState(proto);
  const s = Object.create(proto);
  s.vacuumObjectId = () => "robot";
  globalThis.localStorage = store;
  return s;
}

const memStore = (seed = {}) => ({
  _d: { ...seed },
  getItem(k) { return k in this._d ? this._d[k] : null; },
  setItem(k, v) { this._d[k] = String(v); },
});

test("[MBC-4] the collapse persists per robot, and ABSENT reads as expanded", () => {
  const KEY = "evcc_mascot_bar_collapsed_robot";

  // THE INPUT THAT MAKES THIS RED: copying the neighbour. `mapAnimalEnabled` sits a few
  // lines above and reads `localStorage.getItem(key) !== "0"`, because its default is ON.
  // This one's default is the opposite, so the same expression inverts it — and an absent
  // key would then read as COLLAPSED, hiding the row for every existing user the moment
  // they upgrade, with nothing on screen to explain it. Hence `=== "1"`.
  assert.equal(makeState(memStore()).isMascotBarCollapsed(), false,
    "a user who never touched this must still see the controls");

  assert.equal(makeState(memStore({ [KEY]: "1" })).isMascotBarCollapsed(), true);
  assert.equal(makeState(memStore({ [KEY]: "0" })).isMascotBarCollapsed(), false);

  // Round trip: the toggle writes, and the next session reads it back.
  const store = memStore();
  const s = makeState(store);
  s.toggleMascotBarCollapsed();
  assert.equal(s.isMascotBarCollapsed(), true, "toggling collapses in-session");
  assert.equal(store._d[KEY], "1", "...and writes it, or it will not survive a reload");
  assert.equal(makeState(store).isMascotBarCollapsed(), true, "a fresh session reads it back");

  s.toggleMascotBarCollapsed();
  assert.equal(store._d[KEY], "0", "and toggling back clears it");

  // Keyed on the VACUUM, so two robots do not share one answer.
  const shared = memStore({ [KEY]: "1" });
  const other = makeState(shared);
  other.vacuumObjectId = () => "other_robot";
  assert.equal(other.isMascotBarCollapsed(), false,
    "a second robot must not inherit the first robot's collapse");
});

test("[MBC-5] a storage that throws degrades to EXPANDED, never to a hidden row", () => {
  // Private-browsing and blocked site-data both make localStorage throw on access. The
  // degrade has to go toward SHOWING the controls: a user who cannot store a preference
  // and also cannot see the control that sets it has no way out of the state.
  const hostile = {
    getItem() { throw new Error("SecurityError"); },
    setItem() { throw new Error("SecurityError"); },
  };
  const s = makeState(hostile);
  assert.equal(s.isMascotBarCollapsed(), false, "unreadable storage must not hide the row");
  assert.doesNotThrow(() => s.toggleMascotBarCollapsed(), "an unwritable store must not throw");
  assert.equal(s.isMascotBarCollapsed(), true, "the in-session toggle still works");
});
