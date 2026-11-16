// Run: node --test src/cards/card-companion.test.mjs
//
// [CMP-*] HIDING THE COMPANION TOTALLY — issue #82, and the half-fix that looks whole.
//
// WHAT #82 ACTUALLY ASKED. 2.7.0 answered an earlier report by putting the companion
// control row behind a caret (renderers/map.js carries that note). The reporter came
// back: "Still this will take space on the card. Can you please add a config in the card
// to hide that totally?" A collapsed row still occupies a line — the caret IS the line —
// so the fix is a config option that OMITS the row, not one that folds it.
//
// THE HALF-FIX THAT LOOKS WHOLE, and the reason this file exists. The paw button that
// hides the companion SPRITE lives INSIDE the control row. So gating only the row leaves
// an animal walking across the map with nothing on the card able to stop it, and gating
// only the sprite leaves the row taking the space that was complained about. Each half is
// individually plausible, individually reviewable, and individually wrong. [CMP-4] and
// [CMP-5] are the two halves; neither alone is satisfied by a half implementation.
//
// WHY THESE ARE TEXT ASSERTIONS, stated because it is a real limit and not a preference.
// The gates live in <eufy-vacuum-map>, which NO runtime in this repo can load:
//   - node cannot — the module does `class EufyVacuumMap extends HTMLElement` at top
//     level and calls customElements.define, so importing it throws immediately;
//   - the Playwright harness cannot — harness/build.mjs marks `/eufy_vacuum/frontend/*`
//     external, because the dashboard card pulls the map host in by its SERVED url at
//     runtime rather than as a bundle edge. The harness serves no such url.
// That is also why the predicate itself went into cards/_shared.js: moving the one
// decidable part somewhere node CAN import is what gives [CMP-1]/[CMP-2] teeth, and
// [CMP-3] is the reachability link between them — a correct predicate with no caller
// passes every audit. Same shape, and same reason, as [MAPV-*] in scripts/.
//
// NOT COVERED HERE, deliberately: that all 17 shipped locale packs carry the new editor
// string. [LOCCOV-1] already gates every English key across every pack and carries its
// own ablation proof ([LOCCOV-2]), so a second check would be duplicate. Measured, not
// assumed: `npm run check:i18n` passes with a pack missing the key — LOCCOV is the gate
// that fails, so LOCCOV is the gate that covers it.
//
// Coverage
// --------
// [CMP-1] the show_* predicate defaults ON — an older config carries no key at all
// [CMP-2] it tests `!== false`, not truthiness
// [CMP-3] the host's _companionEnabled() routes through that predicate
// [CMP-4] the CONTROL-ROW half — the mascot gate consults _companionEnabled()
// [CMP-5] the SPRITE half — mapAnimalEnabled is WRAPPED, so the paw toggle still works
// [CMP-6] the editor both RENDERS the checkbox and PERSISTS it

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { cardSectionEnabled } from "./_shared.js";

const HOST = readFileSync("src/cards/vacuum-map-host.js", "utf8");
const CARD = readFileSync("src/cards/dashboard-card.js", "utf8");

/* ========================================================================== *
 * THE PREDICATE
 * ========================================================================== */

test("[CMP-1] an optional card section defaults ON when the key is absent", () => {
  // THE RED INPUT: `return !!(config ?? {})[key]`. Every dashboard saved before this
  // option existed carries no `show_companion` key, so truthiness would switch the
  // companion OFF for every existing user on upgrade — a silent behaviour change that
  // reads as a bug in the companion rather than in the default.
  assert.equal(cardSectionEnabled({}, "show_companion"), true, "absent key must mean ON");
  assert.equal(cardSectionEnabled(undefined, "show_companion"), true, "absent config must mean ON");
  assert.equal(cardSectionEnabled(null, "show_companion"), true, "null config must mean ON");

  // The same must hold for the four options that shipped before it, because the editor
  // writes them all through one loop and the card must read them one way.
  for (const key of ["show_profiles", "show_scenes", "show_dock", "show_map"]) {
    assert.equal(cardSectionEnabled({}, key), true, key + " must default ON");
  }
});

test("[CMP-2] the test is !== false, not truthiness", () => {
  // THE RED INPUT: any rewrite to `!!`. These three values separate the two spellings,
  // and they are the whole reason the predicate is a named function rather than four
  // inline comparisons that can each drift.
  assert.equal(cardSectionEnabled({ show_companion: false }, "show_companion"), false);
  assert.equal(cardSectionEnabled({ show_companion: true }, "show_companion"), true);
  assert.equal(cardSectionEnabled({ show_companion: 0 }, "show_companion"), true,
    "0 is not false here — the editor only ever writes a real boolean, and matching the " +
    "four sibling options exactly matters more than guessing at hand-written YAML");
});

/* ========================================================================== *
 * THE TWO HALVES
 * ========================================================================== */

test("[CMP-3] the host reads the option through the shared predicate", () => {
  // THE RED INPUT: `_companionEnabled() { return this._config?.show_companion === true; }`
  // — wrong in exactly the way [CMP-1] describes, and invisible to [CMP-1] on its own
  // because the predicate would still be correct and simply unused.
  const fn = HOST.match(/_companionEnabled\(\)\s*\{([^}]*)\}/);
  assert.ok(fn, "the host must define _companionEnabled()");
  assert.match(fn[1], /cardSectionEnabled\(\s*this\._config\s*,\s*"show_companion"\s*\)/,
    "_companionEnabled must delegate to cardSectionEnabled, not re-spell the comparison");
  assert.match(HOST, /import\s*\{\s*cardSectionEnabled\s*\}\s*from\s*"\.\/_shared\.js"/,
    "...and must actually import it");
});

test("[CMP-4] the CONTROL-ROW half: the mascot gate consults the option", () => {
  // THE RED INPUT: drop `this._companionEnabled() &&` from the gate. The card then renders
  // the row for everyone regardless of the setting, while the setting still appears in the
  // editor and still saves — so the only symptom is that it does nothing.
  const gate = HOST.match(/const mascot =([\s\S]*?)\?\s*`/);
  assert.ok(gate, "could not find the `const mascot = (...) ? ... : \"\"` gate");
  assert.match(gate[1], /this\._companionEnabled\(\)/,
    "the mascot bar must be OMITTED when the option is off — a collapsed row still takes " +
    "a line, which is the whole of #82");
});

test("[CMP-5] the SPRITE half: mapAnimalEnabled is wrapped, not replaced", () => {
  // TWO RED INPUTS, and the second is the subtle one.
  //  (a) delete the override => the row goes but the animal keeps walking, and the only
  //      control that could have stopped it went with the row.
  //  (b) `= () => this._companionEnabled()` => the companion can no longer be hidden by
  //      the user's own paw toggle, because the override REPLACED the state's answer
  //      instead of ANDing with it. With the option left on, everything still looks right.
  const ov = HOST.match(/this\._state\.mapAnimalEnabled\s*=\s*([^;]*);/);
  assert.ok(ov, "the host must override _state.mapAnimalEnabled for the sprite");
  assert.match(ov[1], /this\._companionEnabled\(\)/, "the override must consult the option");
  assert.match(ov[1], /baseAnimalEnabled\(\)/,
    "the override must AND with the state's own answer, or the paw toggle stops working");
  assert.match(HOST,
    /const baseAnimalEnabled\s*=\s*this\._state\.mapAnimalEnabled\.bind\(this\._state\)/,
    "the base must be captured from the state BEFORE the override shadows it");

  // The setter is deliberately NOT neutered (contrast useVaRender immediately above it):
  // it writes the SHARED per-vacuum key, and it is only reachable from the row that is
  // now gone. Pinned so a later "symmetry" tidy-up has to argue with a test.
  assert.doesNotMatch(HOST, /this\._state\.setMapAnimalEnabled\s*=\s*\(\)\s*=>\s*\{\s*\}/,
    "do not stub setMapAnimalEnabled — a card that merely hid its companion must not " +
    "overwrite the panel's own stored choice");
});

/* ========================================================================== *
 * THE EDITOR
 * ========================================================================== */

test("[CMP-6] the editor both renders the checkbox and persists it", () => {
  // TWO RED INPUTS, one per half, and each fails silently on its own:
  //  (a) no checkbox => the option exists but nothing in the UI can reach it;
  //  (b) not in the persist loop => the checkbox renders, the user ticks it, the tick
  //      reverts on the next render, and nothing anywhere reports a problem.
  assert.match(CARD, /id="show_companion"\s+type="checkbox"/,
    "the editor must render a show_companion checkbox");
  assert.match(CARD, /bool\("show_companion",\s*true\)/,
    "...seeded from the ON default, like its four siblings");

  const loop = CARD.match(/for \(const key of \[([^\]]*)\]\)/);
  assert.ok(loop, "could not find the editor's show_* persist loop");
  assert.match(loop[1], /"show_companion"/,
    "show_companion must be in the persist loop or the tick never reaches the config");
});
